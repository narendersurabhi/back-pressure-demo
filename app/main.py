import os
import asyncio
import signal
from app.api import app
import uvicorn

async def worker_loop(idx, queue, metrics, stop_event):
    while not stop_event.is_set():
        try:
            item = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        # mark busy
        metrics["busy"] = metrics.get("busy", 0) + 1
        try:
            # simulate work; in real system replace with real processing
            await asyncio.sleep(0.05)
        finally:
            metrics["busy"] = max(0, metrics.get("busy", 1) - 1)
            metrics["processed"] = metrics.get("processed", 0) + 1
            try:
                queue.task_done()
            except Exception:
                pass


async def start_workers(count, queue, metrics):
    stop_event = asyncio.Event()
    app.state.ready = False
    tasks = [asyncio.create_task(worker_loop(i, queue, metrics, stop_event)) for i in range(count)]
    # small grace to ensure tasks started
    await asyncio.sleep(0)
    app.state.ready = True
    return stop_event, tasks


def run():
    maxsize = int(os.getenv("QUEUE_MAXSIZE", "100"))
    workers = int(os.getenv("WORKER_COUNT", "4"))
    queue = asyncio.Queue(maxsize=maxsize)
    metrics = {"rejected": 0, "enqueued": 0, "processed": 0, "busy": 0}
    app.state.queue = queue
    app.state.metrics = metrics

    async def _main():
        stop_event, tasks = await start_workers(workers, queue, metrics)
        loop = asyncio.get_running_loop()
        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(s, stop_event.set)
            except NotImplementedError:
                pass
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        finally:
            stop_event.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), loop="asyncio")
    server = uvicorn.Server(config)

    async def serve():
        await asyncio.gather(server.serve(), _main())

    asyncio.run(serve())


if __name__ == "__main__":
    run()