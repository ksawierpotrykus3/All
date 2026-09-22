"""server package.

Lazy-loads `app` via __getattr__ to prevent circular import
when running `python -m server.main` or `uvicorn server:app`.
"""


def __getattr__(name):
    if name == "app":
        from server.main import app  # pylint: disable=import-outside-toplevel
        return app
    raise AttributeError(f"module 'server' has no attribute '{name}'")
