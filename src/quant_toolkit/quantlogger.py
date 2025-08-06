"""
QuantLogger: Comprehensive async-first logging decorator for quant_toolkit.
Provides thread-safe, async-compatible logging with Pydantic validation.
"""

from pydantic.dataclasses import dataclass
from pydantic import Field, validator
import asyncio
import aiofiles
import json
import time
import traceback
from pathlib import Path
from typing import Optional, Literal, Any, Callable, Dict, ClassVar
from datetime import datetime
from functools import wraps


@dataclass
class QuantLogger:
    """
    Comprehensive async-first logging decorator with validation.
    Handles logging, JSON conversion, and all configuration in a single class.

    Features:
    - Async-first design with sync function support
    - Thread-safe file operations using asyncio.Lock
    - Automatic daily log rotation
    - Pydantic validation for all configuration
    - JSON conversion utilities
    - Global and instance-level configuration

    Usage:
        @QuantLogger(log_args=True, log_time=True)
        def my_function(x: int) -> int:
            return x * 2
    """

    # Instance configuration with Pydantic validation
    name: Optional[str] = Field(
        default=None, description="Logger name, defaults to module.function"
    )
    log_path: Optional[Path] = Field(
        default=None, description="Directory for log files"
    )
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_args: bool = Field(default=False, description="Log function arguments")
    log_result: bool = Field(default=False, description="Log function return value")
    log_time: bool = Field(
        default=False, description="Log execution duration in milliseconds"
    )
    to_stdout: bool = Field(default=True, description="Also print to stdout")

    # Class-level shared resources (using ClassVar to exclude from dataclass fields)
    _global_log_path: ClassVar[Optional[Path]] = None
    _log_queue: ClassVar[Optional[asyncio.Queue]] = None
    _writer_task: ClassVar[Optional[asyncio.Task]] = None
    _file_locks: ClassVar[Dict[Path, asyncio.Lock]] = {}
    _initialized: ClassVar[bool] = False

    @validator("log_path")
    def validate_path(cls, v, values):
        """Validate and create log path if needed"""
        # Use instance path, fall back to global path
        path = v or cls._global_log_path
        if path and not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path

    def __post_init__(self):
        """Initialize async components after dataclass init"""
        if not self.__class__._initialized:
            self.__class__._initialize_async_components()

    @classmethod
    def _initialize_async_components(cls):
        """Initialize class-level async components once"""
        if not cls._initialized:
            cls._log_queue = asyncio.Queue()
            cls._initialized = True
            # Try to start writer task if event loop exists
            try:
                loop = asyncio.get_running_loop()
                cls._writer_task = loop.create_task(cls._log_writer())
            except RuntimeError:
                # No event loop yet, will be created when first decorator is used
                pass

    @classmethod
    def set_global_path(cls, path: Path):
        """Set global log directory for all instances"""
        cls._global_log_path = path
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

    def __call__(self, func: Callable) -> Callable:
        """Main decorator logic - detects async vs sync functions"""
        # Ensure writer task is running
        self._ensure_writer_task()

        if asyncio.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        else:
            return self._create_sync_wrapper(func)

    @classmethod
    def _ensure_writer_task(cls):
        """Ensure background writer task is running"""
        try:
            loop = asyncio.get_running_loop()
            if cls._writer_task is None or cls._writer_task.done():
                cls._writer_task = loop.create_task(cls._log_writer())
        except RuntimeError:
            # No event loop running yet, will be created later
            pass

    @classmethod
    async def _log_writer(cls):
        """Background task to write logs from queue"""
        while True:
            try:
                entry_data = await cls._log_queue.get()
                await cls._write_log_entry(entry_data)
            except asyncio.CancelledError:
                # Flush remaining logs before exit
                while not cls._log_queue.empty():
                    entry_data = cls._log_queue.get_nowait()
                    await cls._write_log_entry(entry_data)
                break
            except Exception as e:
                print(f"Error in log writer: {e}")

    @classmethod
    async def _write_log_entry(cls, entry_data: dict):
        """Write single log entry to file and optionally stdout"""
        # Extract data
        timestamp = entry_data["timestamp"]
        module = entry_data["module"]
        log_path = entry_data["log_path"]
        to_stdout = entry_data["to_stdout"]
        formatted_entry = entry_data["formatted"]

        # Generate filename: module_name-2025-08-06.log
        date_str = timestamp.strftime("%Y-%m-%d")
        filename = f"{module}-{date_str}.log"

        if log_path is None:
            log_path = Path("logs")
            log_path.mkdir(exist_ok=True)

        file_path = log_path / filename

        # Get or create lock for this file
        if file_path not in cls._file_locks:
            cls._file_locks[file_path] = asyncio.Lock()

        async with cls._file_locks[file_path]:
            # Write to file using aiofiles
            async with aiofiles.open(file_path, "a") as f:
                await f.write(formatted_entry + "\n")

        # Optionally write to stdout
        if to_stdout:
            print(formatted_entry)

    def _format_log_entry(
        self,
        timestamp: datetime,
        level: str,
        module: str,
        function: str,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        result: Any = None,
        duration_ms: Optional[float] = None,
        exception: Optional[Exception] = None,
        tb: Optional[str] = None,
    ) -> str:
        """Format log entry based on level and configuration"""

        # Build log parts
        parts = [
            timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            f"| {level}",
            f"| {module}.{function}",
        ]

        # Add optional parts based on configuration
        if self.log_args and (args or kwargs):
            args_str = self._format_arguments(args, kwargs)
            parts.append(f"| Args: {args_str}")

        if self.log_time and duration_ms is not None:
            parts.append(f"| Duration: {duration_ms:.2f}ms")

        if self.log_result and result is not None:
            result_str = str(result)[:100]  # Limit result length
            if len(str(result)) > 100:
                result_str += "..."
            parts.append(f"| Result: {result_str}")

        # Special formatting for ERROR and CRITICAL levels
        if level in ["ERROR", "CRITICAL"]:
            separator = "=" * 80
            formatted = f"\n{separator}\n"
            formatted += " ".join(parts)
            if exception:
                formatted += f"\nException: {type(exception).__name__}: {exception}"
                if tb:
                    formatted += f"\n{tb}"
            formatted += f"\n{separator}"
            return formatted

        return " ".join(parts)

    def _format_arguments(self, args: tuple, kwargs: dict) -> str:
        """Format function arguments for logging"""
        parts = []
        if args:
            args_str = ", ".join(repr(arg)[:50] for arg in args)
            parts.append(args_str)
        if kwargs:
            kwargs_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in kwargs.items())
            parts.append(kwargs_str)
        return "(" + ", ".join(parts) + ")"

    def _create_async_wrapper(self, func: Callable) -> Callable:
        """Create wrapper for async functions"""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            timestamp = datetime.now()
            # Get filename without extension from the function's code object
            filename = Path(func.__code__.co_filename).stem
            module = filename if filename else "unknown"
            function = func.__name__
            level = self.level
            exception = None
            tb = None
            result = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                exception = e
                tb = traceback.format_exc()
                level = "ERROR"
                # Always print exceptions to stdout
                print(f"Exception in {function}: {e}")
                # Don't re-raise as per requirement
            finally:
                duration_ms = None
                if self.log_time:
                    duration_ms = (time.perf_counter() - start_time) * 1000

                # Format entry
                formatted = self._format_log_entry(
                    timestamp=timestamp,
                    level=level,
                    module=module,
                    function=function,
                    args=args if self.log_args else None,
                    kwargs=kwargs if self.log_args else None,
                    result=result if self.log_result else None,
                    duration_ms=duration_ms,
                    exception=exception,
                    tb=tb,
                )

                # Queue the log entry
                entry_data = {
                    "timestamp": timestamp,
                    "module": module,
                    "log_path": self.log_path or self._global_log_path,
                    "to_stdout": self.to_stdout,
                    "formatted": formatted,
                }

                await self._log_queue.put(entry_data)

        return wrapper

    def _create_sync_wrapper(self, func: Callable) -> Callable:
        """Create wrapper for sync functions"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            timestamp = datetime.now()
            # Get filename without extension from the function's code object
            filename = Path(func.__code__.co_filename).stem
            module = filename if filename else "unknown"
            function = func.__name__
            level = self.level
            exception = None
            tb = None
            result = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                exception = e
                tb = traceback.format_exc()
                level = "ERROR"
                # Always print exceptions to stdout
                print(f"Exception in {function}: {e}")
                # Don't re-raise as per requirement
            finally:
                duration_ms = None
                if self.log_time:
                    duration_ms = (time.perf_counter() - start_time) * 1000

                # Format entry
                formatted = self._format_log_entry(
                    timestamp=timestamp,
                    level=level,
                    module=module,
                    function=function,
                    args=args if self.log_args else None,
                    kwargs=kwargs if self.log_args else None,
                    result=result if self.log_result else None,
                    duration_ms=duration_ms,
                    exception=exception,
                    tb=tb,
                )

                # Queue the log entry
                entry_data = {
                    "timestamp": timestamp,
                    "module": module,
                    "log_path": self.log_path or self._global_log_path,
                    "to_stdout": self.to_stdout,
                    "formatted": formatted,
                }

                # Handle sync context - try to use existing loop or create one
                try:
                    loop = asyncio.get_running_loop()  # noqa: F841
                    asyncio.create_task(self._log_queue.put(entry_data))
                except RuntimeError:
                    # No event loop, need to handle differently
                    # For now, write synchronously
                    asyncio.run(self._write_sync_fallback(entry_data))

        return wrapper

    async def _write_sync_fallback(self, entry_data: dict):
        """Fallback for sync functions when no event loop exists"""
        await self._log_queue.put(entry_data)
        # Ensure writer task processes it
        if self._writer_task is None:
            await self._write_log_entry(entry_data)

    @classmethod
    async def flush_logs(cls):
        """Force flush all pending logs"""
        if cls._log_queue:
            while not cls._log_queue.empty():
                entry_data = cls._log_queue.get_nowait()
                await cls._write_log_entry(entry_data)

    @staticmethod
    def log_to_json(log_file: Path, output_file: Optional[Path] = None) -> Path:
        """
        Convert human-readable log file to JSON format.

        Args:
            log_file: Path to log file to convert
            output_file: Optional output path (defaults to same name with .json)

        Returns:
            Path to created JSON file
        """
        if not log_file.exists():
            raise FileNotFoundError(f"Log file not found: {log_file}")

        entries = []
        with open(log_file, "r") as f:
            current_entry = []
            in_error_block = False

            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("=" * 80):
                    if in_error_block and current_entry:
                        # End of error block, parse it
                        entries.append(QuantLogger._parse_error_block(current_entry))
                        current_entry = []
                    in_error_block = not in_error_block
                elif in_error_block:
                    current_entry.append(line)
                else:
                    # Normal log line
                    parsed = QuantLogger._parse_log_line(line)
                    if parsed:
                        entries.append(parsed)

        # Save to JSON
        if output_file is None:
            output_file = log_file.with_suffix(".json")

        with open(output_file, "w") as f:
            json.dump(entries, f, indent=2, default=str)

        return output_file

    @staticmethod
    def _parse_log_line(line: str) -> Optional[dict]:
        """Parse a single log line into dictionary"""
        try:
            parts = line.split(" | ")
            if len(parts) < 3:
                return None

            entry = {"timestamp": parts[0], "level": parts[1], "function": parts[2]}

            # Parse optional parts
            for part in parts[3:]:
                if part.startswith("Args:"):
                    entry["args"] = part[6:]
                elif part.startswith("Duration:"):
                    entry["duration_ms"] = float(part[10:-2])
                elif part.startswith("Result:"):
                    entry["result"] = part[8:]

            return entry
        except Exception:
            return None

    @staticmethod
    def _parse_error_block(lines: list[str]) -> dict:
        """Parse an error block into dictionary"""
        entry = {}
        for line in lines:
            if " | " in line:
                # Parse the main log line
                entry.update(QuantLogger._parse_log_line(line) or {})
            elif line.startswith("Exception:"):
                entry["exception"] = line[11:]
            elif line.startswith("Traceback"):
                entry["traceback"] = "\n".join(lines[lines.index(line) :])
                break

        return entry
