"""
Centralised diagnostic logging for the EASD transcript pipeline.

Every module gets its logger via ``get_logger("<area>")`` (-> "easd.<area>").

Where logs go
-------------
* ALWAYS: ``app_service.log`` next to app.py (UTF-8, append). Override the
  location with the env var ``EASD_LOG_FILE``.
* ALSO the console (stderr) when one exists - i.e. ``Launch_App.bat debug``
  or ``python run_app.pyw`` from a terminal. Under pythonw / the .vbs
  launcher, run_app.pyw already redirects stdout/stderr into
  app_service.log, so the console handler is skipped to avoid every line
  being written twice.

Set ``EASD_LOG_LEVEL=DEBUG`` for extra detail.

Correlation ids
---------------
``bind_job_id(job_id)`` stores a short request id in a ``contextvars`` slot.
Every log line then carries ``[job=<id>]`` (or ``[job=-]`` outside a request),
so one failed request can be pulled out of ``app_service.log`` with
``grep "job=<id>" app_service.log`` even when several users are active.
``asyncio.to_thread`` copies the context automatically; worker pools must
submit through ``contextvars.copy_context().run`` (see ``stt_pipeline``).
"""

import contextvars
import logging
import os
import sys
import threading
import uuid

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.environ.get("EASD_LOG_FILE") or os.path.join(_BASE_DIR, "app_service.log")

_setup_lock = threading.Lock()
_is_setup = False

_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-7s [%(name)s] [%(threadName)s] [job=%(job_id)s] %(message)s"

_current_job_id: "contextvars.ContextVar[str]" = contextvars.ContextVar("easd_job_id", default="-")


class _JobIdFilter(logging.Filter):
    """Stamps every record with the request correlation id bound in this context."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = _current_job_id.get()
        return True
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _stderr_is_real_console() -> bool:
    err = sys.stderr
    if err is None:
        return False
    name = os.path.abspath(str(getattr(err, "name", ""))) if getattr(err, "name", None) else ""
    if name and os.path.normcase(name) == os.path.normcase(os.path.abspath(LOG_FILE_PATH)):
        return False  # pythonw mode: stderr IS the log file already
    if name == os.devnull or name.endswith("nul"):
        return False
    return True


def setup_logging() -> logging.Logger:
    global _is_setup
    root = logging.getLogger("easd")
    if _is_setup:
        return root
    with _setup_lock:
        if _is_setup:
            return root
        level_name = (os.environ.get("EASD_LOG_LEVEL") or "INFO").upper()
        root.setLevel(getattr(logging, level_name, logging.INFO))
        root.propagate = False
        fmt = logging.Formatter(_FORMAT, datefmt=_DATEFMT)
        try:
            fh = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8", delay=False)
            fh.setFormatter(fmt)
            fh.addFilter(_JobIdFilter())
            root.addHandler(fh)
        except Exception as e:  # never let logging setup crash the app
            try:
                sys.__stderr__ and sys.__stderr__.write(f"[diag_logging] cannot open {LOG_FILE_PATH}: {e}\n")
            except Exception:
                pass
        if _stderr_is_real_console():
            try:
                sh = logging.StreamHandler(sys.stderr)
                sh.setFormatter(fmt)
                sh.addFilter(_JobIdFilter())
                root.addHandler(sh)
            except Exception:
                pass
        _is_setup = True
        root.info("Logging initialised -> file=%s console=%s pid=%s python=%s",
                  LOG_FILE_PATH, _stderr_is_real_console(), os.getpid(), sys.executable)
    return root


def get_logger(area: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"easd.{area}")


def new_job_id() -> str:
    return uuid.uuid4().hex[:8]


def bind_job_id(job_id: str = "") -> str:
    """Bind ``job_id`` (or a fresh one) to the current context so every log line carries it. Returns the id."""
    jid = (job_id or "").strip() or new_job_id()
    _current_job_id.set(jid)
    return jid


def current_job_id() -> str:
    """The correlation id bound to this context, or '-' when none is bound."""
    return _current_job_id.get()


def redact_key(key: str) -> str:
    """Log-safe description of a secret: '***abcd' (last 4 chars) or 'none'. Never logs the full key."""
    k = (key or "").strip()
    if not k:
        return "none"
    return f"***{k[-4:]}" if len(k) > 8 else "***"


def fmt_ts(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def describe_exception(e: BaseException) -> str:
    """type + message + HTTP status/body for google-genai / httpx errors."""
    parts = [f"{type(e).__module__}.{type(e).__name__}: {e}"]
    for attr in ("code", "status", "status_code", "message"):
        v = getattr(e, attr, None)
        if v not in (None, "") and str(v) not in parts[0]:
            parts.append(f"{attr}={v}")
    details = getattr(e, "details", None)
    if details:
        parts.append(f"details={str(details)[:2000]}")
    resp = getattr(e, "response", None)
    if resp is not None:
        try:
            sc = getattr(resp, "status_code", None)
            body = getattr(resp, "text", None)
            if callable(body):
                body = None
            parts.append(f"http_status={sc} body={str(body)[:2000] if body else '<n/a>'}")
        except Exception:
            pass
    return " | ".join(parts)


def probe_duration_sec(path: str) -> float:
    """Duration via ffprobe; -1 if unknown."""
    try:
        import subprocess
        import media_processor
        probe = media_processor.find_ffprobe_binary()
        if not probe:
            return -1.0
        r = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return float((r.stdout or "").strip() or -1)
    except Exception:
        return -1.0
