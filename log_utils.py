import functools
import io
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional


class _BufferedTeeStream:
    """
    Buffers output in memory and writes to original stream and run log file.
    Buffered content can be retrieved via get_buffer_content() for error logging.
    """
    def __init__(self, original_stream, run_log_path):
        self._original = original_stream
        self._run_log_path = Path(run_log_path)
        self._run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer = io.StringIO()
        self._run_log_file = open(self._run_log_path, "a", buffering=1)

    def write(self, data):
        self._original.write(data)
        self._buffer.write(data)
        self._run_log_file.write(data)

    def flush(self):
        self._original.flush()
        self._run_log_file.flush()

    def get_buffer_content(self) -> str:
        """Get all buffered content."""
        return self._buffer.getvalue()

    def flush_to_error_log(self, error_log_path: Path, exception: Optional[BaseException] = None) -> None:
        """
        Write all buffered content + error to error log file.
        Only creates the error log file if it doesn't exist.
        """
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(error_log_path, "w", encoding="utf-8") as err_file:
            # Write all buffered content
            buffer_content = self.get_buffer_content()
            if buffer_content:
                err_file.write("=" * 80 + "\n")
                err_file.write("BUFFERED OUTPUT (stdout/stderr)\n")
                err_file.write("=" * 80 + "\n")
                err_file.write(buffer_content)
                err_file.write("\n")
            
            # Write the exception if provided
            if exception:
                err_file.write("=" * 80 + "\n")
                err_file.write("ERROR DETAILS\n")
                err_file.write("=" * 80 + "\n")
                err_file.write("".join(
                    traceback.format_exception(
                        exception.__class__, exception, exception.__traceback__
                    )
                ))
                err_file.write("\n")


# Global references to buffered streams for error handling
_buffered_stdout: Optional[_BufferedTeeStream] = None
_buffered_stderr: Optional[_BufferedTeeStream] = None
_error_log_path: Optional[Path] = None


def attach_log_streams(module_name: str) -> None:
    """
    Attach buffered tee streams to stdout/stderr.
    Logs are kept in memory and written to run log files.
    Error log files are only created when flush_to_error_log() is called.
    """
    global _buffered_stdout, _buffered_stderr, _error_log_path
    
    base_dir = Path(__file__).resolve().parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    run_log = os.environ.get("GALLARDO_RUN_LOG")
    if not run_log:
        run_log = str(logs_dir / f"{module_name}_run_{timestamp}.log")

    # Determine error log path (but don't create it yet)
    err_log = os.environ.get("GALLARDO_ERR_LOG")
    if not err_log:
        err_log = str(logs_dir / f"{module_name}_err_{timestamp}.log")
    
    _error_log_path = Path(err_log)

    # Only attach if not already attached
    if not isinstance(sys.stdout, _BufferedTeeStream):
        _buffered_stdout = _BufferedTeeStream(sys.stdout, run_log)
        sys.stdout = _buffered_stdout

    if not isinstance(sys.stderr, _BufferedTeeStream):
        _buffered_stderr = _BufferedTeeStream(sys.stderr, run_log)
        sys.stderr = _buffered_stderr

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def flush_error_log(exception: Optional[BaseException] = None) -> None:
    """
    Create error log file and write all buffered content + error to it.
    Should be called when an error occurs.
    """
    global _buffered_stdout, _buffered_stderr, _error_log_path
    
    if not _error_log_path:
        # Fallback: create error log path if not set
        base_dir = Path(__file__).resolve().parent
        logs_dir = base_dir / "logs"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _error_log_path = logs_dir / f"error_{timestamp}.log"
    
    _error_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(_error_log_path, "w", encoding="utf-8") as err_file:
        # Collect all buffered content from both streams
        all_buffer_content = []
        
        if _buffered_stdout:
            stdout_content = _buffered_stdout.get_buffer_content()
            if stdout_content:
                all_buffer_content.append(("STDOUT", stdout_content))
        
        if _buffered_stderr:
            stderr_content = _buffered_stderr.get_buffer_content()
            if stderr_content:
                all_buffer_content.append(("STDERR", stderr_content))
        
        # Write all buffered content
        if all_buffer_content:
            err_file.write("=" * 80 + "\n")
            err_file.write("BUFFERED OUTPUT\n")
            err_file.write("=" * 80 + "\n")
            for stream_name, content in all_buffer_content:
                if len(all_buffer_content) > 1:
                    err_file.write(f"\n--- {stream_name} ---\n")
                err_file.write(content)
                err_file.write("\n")
        
        # Write the exception if provided
        if exception:
            err_file.write("=" * 80 + "\n")
            err_file.write("ERROR DETAILS\n")
            err_file.write("=" * 80 + "\n")
            err_file.write("".join(
                traceback.format_exception(
                    exception.__class__, exception, exception.__traceback__
                )
            ))
            err_file.write("\n")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def write_sheet_value(
    logger: logging.Logger,
    worksheet,
    row_idx: int,
    col_idx: Optional[int],
    value: str,
    *,
    context: str = "status",
) -> None:
    if not worksheet or not col_idx:
        logger.debug(
            "Skipping sheet write for row %s context '%s' (worksheet or column missing)",
            row_idx,
            context,
        )
        return
    try:
        worksheet.update_cell(row_idx, col_idx, value)
    except Exception as exc:
        logger.error(
            "Failed to write '%s' for row %s: %s", context, row_idx, exc, exc_info=True
        )


def record_error(
    logger: logging.Logger,
    worksheet,
    row_idx: int,
    col_idx: Optional[int],
    user_message: str,
    *,
    details: Optional[str] = None,
    exception: Optional[BaseException] = None,
) -> None:
    extra = details or ""
    if exception:
        if not details:
            extra = "".join(
                traceback.format_exception(
                    exception.__class__, exception, exception.__traceback__
                )
            )
    logger.error("Row %s error: %s %s", row_idx, user_message, extra)
    write_sheet_value(
        logger,
        worksheet,
        row_idx,
        col_idx,
        user_message,
        context="error message",
    )


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
