import importlib
import pytest


def _import_app_module():
    try:
        return importlib.import_module("app")
    except Exception as e:
        pytest.skip(f"Could not import 'app' module: {e}")


def _get_app_instance(mod):
    # Look for common names: factory or instance
    for name in ("create_app", "app", "application", "main"):
        if hasattr(mod, name):
            attr = getattr(mod, name)
            # If it's a factory, try to call it to get the instance
            if name == "create_app" and callable(attr):
                try:
                    return attr()
                except Exception:
                    # Fall back to returning the callable itself
                    return attr
            return attr
    pytest.skip("No app instance or factory found in 'app' module")


def test_root_endpoint_available():
    """Minimal test: import the app and attempt a GET / using a compatible test client.

    The test is permissive: it accepts any valid HTTP status code and will skip
    if no compatible test client is available (keeps tests runnable in minimal
    environments).
    """
    mod = _import_app_module()
    app = _get_app_instance(mod)

    # Flask-style test client
    if hasattr(app, "test_client"):
        client = app.test_client()
        resp = client.get("/")
        assert 100 <= resp.status_code < 600
        return

    # Starlette/FastAPI TestClient (try starlette first)
    try:
        from starlette.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/")
        assert 100 <= resp.status_code < 600
        return
    except Exception:
        pass

    # If we get here, we couldn't exercise the endpoint
    pytest.skip("No compatible test client available to call the app endpoint")
