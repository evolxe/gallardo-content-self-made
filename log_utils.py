import functools
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


class _TeeStream:
    def __init__(self, original_stream, log_path):
        self._original = original_stream
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(self._log_path, "a", buffering=1)

    def write(self, data):
        self._original.write(data)
        self._log_file.write(data)

    def flush(self):
        self._original.flush()
        self._log_file.flush()


def attach_log_streams(module_name: str) -> None:
    """
    Tee stdout/stderr to timestamped log files.
    If runPython.sh exported GALLARDO_RUN_LOG / GALLARDO_ERR_LOG we reuse them.
    Otherwise we create per-module logs in logs/.
    """
    base_dir = Path(__file__).resolve().parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    run_log = os.environ.get("GALLARDO_RUN_LOG")
    if not run_log:
        run_log = logs_dir / f"{module_name}_run_{timestamp}.log"

    err_log = os.environ.get("GALLARDO_ERR_LOG")
    if not err_log:
        err_log = logs_dir / f"{module_name}_err_{timestamp}.log"

    if not isinstance(sys.stdout, _TeeStream) or getattr(sys.stdout, "_log_path", None) != Path(run_log):
        sys.stdout = _TeeStream(sys.stdout, run_log)

    if not isinstance(sys.stderr, _TeeStream) or getattr(sys.stderr, "_log_path", None) != Path(err_log):
        sys.stderr = _TeeStream(sys.stderr, err_log)

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_call(logger: logging.Logger):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(
                "CALL %s args=%s kwargs=%s",
                func.__name__,
                args,
                kwargs,
            )
            result = func(*args, **kwargs)
            logger.info("RETURN %s -> %s", func.__name__, result)
            return result

        return wrapper

    return decorator

