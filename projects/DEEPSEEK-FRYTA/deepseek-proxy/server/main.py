"""Entry point: run with `python -m server.main` or `uvicorn server:app`."""



from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from server.services.state_service import load_conv_state, _flush_conv_state
from server.dashboard.ws_emitter import router as dashboard_ws_router
from server.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load state on startup, flush on shutdown."""
    try:
        load_conv_state()
        logger.info("[STARTUP] conv_state loaded from disk")
    except Exception as e:
        logger.error(f"[STARTUP] failed to load conv_state: {e}")
    yield
    try:
        _flush_conv_state()
        logger.info("[SHUTDOWN] conv_state flushed to disk")
    except Exception as e:
        logger.error(f"[SHUTDOWN] error flushing conv_state: {e}")


# Create the app
app = FastAPI(title="DeepSeek V4-Pro Proxy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4570", "http://127.0.0.1:4570"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire modular routes
from server.api.routes import router

app.include_router(router)
app.include_router(dashboard_ws_router)


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"[UNHANDLED] {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
            }
        },
    )


def patch_asyncio_windows_proactor():
    """Patch asyncio ProactorEventLoop to prevent listener socket closure on client disconnect errors."""
    import sys
    if sys.platform != "win32":
        return

    try:
        import asyncio.proactor_events
        import asyncio.trsock
        import _overlapped

        CLIENT_DISCONNECT_ERRORS = {
            64, 10054, 121, 995,
            getattr(_overlapped, "ERROR_NETNAME_DELETED", 64),
            getattr(_overlapped, "ERROR_OPERATION_ABORTED", 995),
        }

        orig_start_serving = asyncio.proactor_events.BaseProactorEventLoop._start_serving

        def patched_start_serving(self, protocol_factory, sock,
                                  sslcontext=None, server=None, backlog=100,
                                  ssl_handshake_timeout=None,
                                  ssl_shutdown_timeout=None):
            def loop(f=None):
                try:
                    if f is not None:
                        conn, addr = f.result()
                        if self._debug:
                            asyncio.proactor_events.logger.debug(
                                "%r got a new connection from %r: %r", server, addr, conn
                            )
                        protocol = protocol_factory()
                        if sslcontext is not None:
                            self._make_ssl_transport(
                                conn, protocol, sslcontext, server_side=True,
                                extra={'peername': addr}, server=server,
                                ssl_handshake_timeout=ssl_handshake_timeout,
                                ssl_shutdown_timeout=ssl_shutdown_timeout)
                        else:
                            self._make_socket_transport(
                                conn, protocol,
                                extra={'peername': addr}, server=server)
                    if self.is_closed():
                        return
                    f = self._proactor.accept(sock)
                except OSError as exc:
                    winerror = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
                    if winerror in CLIENT_DISCONNECT_ERRORS and not self.is_closed() and sock.fileno() != -1:
                        asyncio.proactor_events.logger.warning(
                            f"[WIN_PROACTOR_GUARD] Ignored client disconnect during accept (WinError {winerror}), keeping listener socket open."
                        )
                        try:
                            f = self._proactor.accept(sock)
                        except Exception:
                            return
                        self._accept_futures[sock.fileno()] = f
                        f.add_done_callback(loop)
                        return

                    if sock.fileno() != -1:
                        self.call_exception_handler({
                            'message': 'Accept failed on a socket',
                            'exception': exc,
                            'socket': asyncio.trsock.TransportSocket(sock),
                        })
                        sock.close()
                    elif self._debug:
                        asyncio.proactor_events.logger.debug("Accept failed on socket %r", sock, exc_info=True)
                except asyncio.exceptions.CancelledError:
                    sock.close()
                else:
                    self._accept_futures[sock.fileno()] = f
                    f.add_done_callback(loop)

            self.call_soon(loop)

        asyncio.proactor_events.BaseProactorEventLoop._start_serving = patched_start_serving
        logger.info("[STARTUP] Applied patch_asyncio_windows_proactor guard for Windows IOCP")
    except Exception as e:
        logger.warning(f"[STARTUP] Could not patch BaseProactorEventLoop: {e}")


def _ensure_port_free(port: int = 4570, max_wait: float = 3.0):
    """Kill any existing process listening on the port to prevent [Errno 10048]."""
    import os
    import time

    my_pid = os.getpid()

    # 1. First try psutil (most reliable, language-independent, avoids UnicodeDecodeError)
    try:
        import psutil
        killed = False
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                if conn.pid and conn.pid != my_pid:
                    try:
                        p = psutil.Process(conn.pid)
                        p.kill()
                        killed = True
                    except Exception:
                        pass
        if killed:
            time.sleep(0.5)
    except Exception:
        pass

    # 2. Native PowerShell fallback on Windows
    try:
        import subprocess
        ps_cmd = (
            f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.OwningProcess -ne {my_pid} }} | "
            f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            timeout=5,
        )
        time.sleep(0.5)
    except Exception:
        pass


if __name__ == "__main__":
    import time
    from server.logging import configure_logging

    _log_file = str(Path(__file__).resolve().parent.parent / "server_stdout.log")
    configure_logging(log_file=_log_file)
    patch_asyncio_windows_proactor()

    while True:
        try:
            _ensure_port_free(4570)
            uvicorn.run("server:app", host="0.0.0.0", port=4570, reload=False)
            logger.warning("[MAIN] uvicorn.run() exited. Restarting in 1s...")
            time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("[MAIN] KeyboardInterrupt received. Shutting down proxy.")
            break
        except SystemExit as exc:
            if exc.code == 0:
                break
            logger.warning(f"[MAIN] uvicorn exited with code {exc.code}. Freeing port and restarting in 1s...")
            _ensure_port_free(4570)
            time.sleep(1.0)
        except Exception as exc:
            logger.error(f"[MAIN] Unexpected error in uvicorn: {exc}. Restarting in 1s...")
            time.sleep(1.0)


