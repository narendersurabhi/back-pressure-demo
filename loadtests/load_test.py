#!/usr/bin/env python3
"""Lightweight asyncio load tester.
Usage examples:
  python loadtests/load_test.py --target http://localhost:8000/health --concurrency 100 --rps 500 --duration 30
  python loadtests/load_test.py --target http://service:80/ --concurrency 50 --duration 60 --metrics-port 9000

Dependencies: aiohttp, prometheus_client
"""
import argparse
import asyncio
import time
from collections import deque
import sys

try:
    import aiohttp
except Exception:
    print("Missing dependency: aiohttp. Install: pip install aiohttp prometheus_client")
    raise

try:
    from prometheus_client import start_http_server, Counter, Histogram, Gauge
    PROM_AVAILABLE = True
except Exception:
    PROM_AVAILABLE = False


def now():
    return time.monotonic()


async def worker(name, session, target, stop_at, sem, tokens, latency_buf, counters, timeout):
    while now() < stop_at:
        await sem.acquire()
        try:
            if tokens is not None:
                await tokens.get()
            start = now()
            try:
                async with session.get(target, timeout=timeout) as resp:
                    status = resp.status
                    await resp.read()
            except Exception as e:
                latency = now() - start
                counters['requests'] += 1
                counters['errors'] += 1
                if latency_buf.maxlen is not None:
                    latency_buf.append(latency)
                else:
                    latency_buf.append(latency)
                if PROM_AVAILABLE:
                    counters['prom_requests'].inc()
                    counters['prom_errors'].inc()
                    counters['prom_latency'].observe(latency)
                continue
            latency = now() - start
            counters['requests'] += 1
            if 200 <= status < 300:
                counters['success'] += 1
                if PROM_AVAILABLE:
                    counters['prom_success'].inc()
            else:
                counters['errors'] += 1
                if PROM_AVAILABLE:
                    counters['prom_errors'].inc()
            if latency_buf.maxlen is not None:
                latency_buf.append(latency)
            else:
                latency_buf.append(latency)
            if PROM_AVAILABLE:
                counters['prom_requests'].inc()
                counters['prom_latency'].observe(latency)
        finally:
            sem.release()
    return


async def token_refiller(tokens, rps, stop_at):
    interval = 1.0 / float(rps)
    while now() < stop_at:
        try:
            await tokens.put(1)
        except Exception:
            pass
        await asyncio.sleep(interval)


def summarize(latencies, counters):
    req = counters['requests']
    succ = counters['success']
    err = counters['errors']
    min_l = min(latencies) if latencies else 0
    max_l = max(latencies) if latencies else 0
    avg = (sum(latencies) / len(latencies)) if latencies else 0
    lat_sorted = sorted(latencies)
    def pct(p):
        if not lat_sorted:
            return 0
        idx = int(len(lat_sorted) * p / 100.0)
        idx = max(0, min(len(lat_sorted)-1, idx))
        return lat_sorted[idx]
    return {
        'requests': req,
        'success': succ,
        'errors': err,
        'min_ms': min_l*1000,
        'max_ms': max_l*1000,
        'avg_ms': avg*1000,
        'p50_ms': pct(50)*1000,
        'p90_ms': pct(90)*1000,
        'p99_ms': pct(99)*1000,
    }


async def reporter(latency_buf, counters, interval, stop_at):
    while now() < stop_at:
        await asyncio.sleep(interval)
        snap = summarize(list(latency_buf), counters)
        print(f"[report] req={snap['requests']} succ={snap['success']} err={snap['errors']} avg={snap['avg_ms']:.1f}ms p90={snap['p90_ms']:.1f}ms")
    return


def setup_prometheus(port):
    if not PROM_AVAILABLE:
        print("prometheus_client not installed; metrics endpoint will not be available")
        return None
    start_http_server(port)
    prom_reqs = Counter('loadtester_requests_total', 'Total requests')
    prom_success = Counter('loadtester_success_total', 'Successful responses')
    prom_errors = Counter('loadtester_errors_total', 'Errored responses')
    prom_latency = Histogram('loadtester_request_seconds', 'Request latency seconds')
    return dict(prom_requests=prom_reqs, prom_success=prom_success, prom_errors=prom_errors, prom_latency=prom_latency)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--target', required=True)
    p.add_argument('--concurrency', type=int, default=50)
    p.add_argument('--duration', type=int, default=30, help='seconds')
    p.add_argument('--rps', type=int, default=0, help='requests per second (0=unlimited)')
    p.add_argument('--timeout', type=float, default=10.0)
    p.add_argument('--metrics-port', type=int, default=0, help='expose prometheus metrics (requires prometheus_client)')
    p.add_argument('--report-interval', type=int, default=5)
    return p.parse_args()


async def main():
    args = parse_args()
    duration = args.duration
    concurrency = args.concurrency
    rps = args.rps if args.rps > 0 else None
    stop_at = now() + duration

    sem = asyncio.Semaphore(concurrency)
    tokens = None
    refill_task = None
    if rps:
        tokens = asyncio.Queue(maxsize=max(1, rps))
        refill_task = asyncio.create_task(token_refiller(tokens, rps, stop_at))

    latency_buf = deque(maxlen=100000)
    counters = {'requests': 0, 'success': 0, 'errors': 0}

    if args.metrics_port:
        prom = setup_prometheus(args.metrics_port)
        if prom:
            counters.update(prom)
            print(f"Prometheus metrics available on :{args.metrics_port}/")

    timeout = aiohttp.ClientTimeout(total=args.timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        n_workers = max(1, concurrency)
        workers = [asyncio.create_task(worker(f'w{i}', session, args.target, stop_at, sem, tokens, latency_buf, counters, timeout)) for i in range(n_workers)]
        rep = asyncio.create_task(reporter(latency_buf, counters, args.report_interval, stop_at))
        await asyncio.gather(*workers)
        await rep

    stats = summarize(list(latency_buf), counters)
    print("--- SUMMARY ---")
    print(f"requests={stats['requests']} success={stats['success']} errors={stats['errors']}")
    print(f"latency ms: p50={stats['p50_ms']:.1f} p90={stats['p90_ms']:.1f} p99={stats['p99_ms']:.1f} avg={stats['avg_ms']:.1f} min={stats['min_ms']:.1f} max={stats['max_ms']:.1f}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted', file=sys.stderr)
        sys.exit(1)
