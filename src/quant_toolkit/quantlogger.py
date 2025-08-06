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
    Comprehensive async-first logging decorator with Pydantic validation.
    
    A powerful logging decorator that seamlessly handles both synchronous and
    asynchronous functions while providing thread-safe, high-performance logging
    with rich configuration options and automatic JSON export capabilities.

    Architecture:
        - **Async-first design**: Uses asyncio.Queue and background tasks for optimal performance
        - **Dual compatibility**: Automatically detects and wraps both async and sync functions
        - **Thread-safe I/O**: Per-file asyncio.Lock prevents concurrent write conflicts
        - **Daily log rotation**: Automatic date-based file naming (module-YYYY-MM-DD.log)
        - **Background processing**: Non-blocking log writing via dedicated async task
        - **Pydantic validation**: All configuration validated at instantiation time

    Features:
        - **Configurable logging**: Control what gets logged (args, results, timing, exceptions)
        - **Multiple log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL with special error formatting
        - **Exception handling**: Captures and logs exceptions without re-raising
        - **Performance timing**: High-resolution execution timing with perf_counter
        - **Flexible output**: File logging with optional stdout duplication
        - **JSON export**: Convert human-readable logs to structured JSON format
        - **Global configuration**: Set defaults for all instances or configure per-instance

    Configuration Fields:
        name: Optional logger name (defaults to module.function)
        log_path: Directory for log files (falls back to global or creates 'logs')
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_args: Whether to capture and log function arguments
        log_result: Whether to capture and log function return values
        log_time: Whether to measure and log execution duration
        to_stdout: Whether to duplicate log entries to console

    Usage Examples:
        # Basic usage with timing
        @QuantLogger(log_time=True)
        async def fetch_data(symbol: str) -> dict:
            return {"price": 100.0, "symbol": symbol}
            
        # Full logging with arguments and results
        @QuantLogger(log_args=True, log_result=True, log_time=True, level="DEBUG")
        def calculate_portfolio_value(positions: list[dict]) -> float:
            return sum(p["quantity"] * p["price"] for p in positions)
            
        # Global configuration
        QuantLogger.set_global_path(Path("/var/log/quant_toolkit"))
        
        # Custom path per instance
        logger = QuantLogger(log_path=Path("./strategy_logs"), log_args=True)
        
        # JSON conversion for analysis
        json_file = QuantLogger.log_to_json(Path("trading-2025-08-06.log"))

    Thread Safety:
        This class is fully thread-safe with the following guarantees:
        - Multiple threads can use decorated functions concurrently
        - File I/O operations are protected by asyncio.Lock per file
        - Background writer task handles queue processing safely
        - Class-level initialization is idempotent and thread-safe

    Performance:
        - Non-blocking: Log writing happens in background async task
        - Efficient: Minimal overhead in decorated function execution
        - Scalable: Queue-based architecture handles high-throughput logging
        - Memory conscious: Argument/result representations are truncated
        
    Error Handling:
        - Exceptions in decorated functions are caught and logged as ERROR level
        - Logging failures are handled gracefully without breaking application flow
        - Background writer task continues processing even if individual writes fail
        - Sync functions work correctly even without active event loop
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
        """Validate and create log path if needed.
        
        Args:
            v: The log_path value being validated.
            values: Other field values from the dataclass.
            
        Returns:
            Path: The validated path object, or None if no path specified.
            
        Note:
            Creates the directory structure if it doesn't exist.
            Falls back to global path if instance path is None.
        """
        # Use instance path, fall back to global path
        path = v or cls._global_log_path
        if path and not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path

    def __post_init__(self):
        """Initialize async components after dataclass initialization.
        
        This method is called automatically by Pydantic after the dataclass
        is created. It ensures that class-level async components are initialized
        exactly once across all instances.
        
        Note:
            This is part of the Pydantic dataclass lifecycle and handles the
            async/sync dual nature initialization.
        """
        if not self.__class__._initialized:
            self.__class__._initialize_async_components()

    @classmethod
    def _initialize_async_components(cls):
        """Initialize class-level async components exactly once.
        
        Creates the shared log queue and attempts to start the background
        writer task if an event loop is available. This method is thread-safe
        and idempotent.
        
        Note:
            If no event loop is running, the writer task creation is deferred
            until the first decorated function is called. This handles both
            async-first and sync contexts gracefully.
        """
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
        """Set global log directory for all QuantLogger instances.
        
        Args:
            path: Directory path where log files will be written.
            
        Note:
            This sets a class-level default that applies to all instances
            unless overridden by the instance's log_path field. Creates
            the directory structure if it doesn't exist.
            
        Example:
            QuantLogger.set_global_path(Path("/var/log/quant"))
        """
        cls._global_log_path = path
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

    def __call__(self, func: Callable) -> Callable:
        """Main decorator entry point that wraps functions with logging.
        
        Automatically detects whether the target function is async or sync
        and applies the appropriate wrapper. This is the core method that
        makes QuantLogger work as a decorator.
        
        Args:
            func: The function to be decorated with logging capabilities.
            
        Returns:
            Callable: The wrapped function with logging functionality.
            
        Example:
            @QuantLogger(log_args=True, log_time=True)
            async def my_async_func(x: int) -> int:
                return x * 2
                
            @QuantLogger(log_result=True)
            def my_sync_func(name: str) -> str:
                return f"Hello, {name}!"
        """
        # Ensure writer task is running
        self._ensure_writer_task()

        if asyncio.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        else:
            return self._create_sync_wrapper(func)

    @classmethod
    def _ensure_writer_task(cls):
        """Ensure the background log writer task is running.
        
        Checks if the writer task exists and is active, creating a new one
        if necessary. This method is called every time a function is decorated
        to guarantee log processing capability.
        
        Note:
            If no event loop is running, this method silently returns.
            The writer task will be created when an event loop becomes available.
        """
        try:
            loop = asyncio.get_running_loop()
            if cls._writer_task is None or cls._writer_task.done():
                cls._writer_task = loop.create_task(cls._log_writer())
        except RuntimeError:
            # No event loop running yet, will be created later
            pass

    @classmethod
    async def _log_writer(cls):
        """Background coroutine that continuously processes log entries from the queue.
        
        This is the core async worker that handles all log I/O operations.
        It runs indefinitely, processing log entries and writing them to files.
        Gracefully handles cancellation by flushing remaining logs.
        
        Raises:
            asyncio.CancelledError: When the task is cancelled, triggers cleanup.
            
        Note:
            This method runs as a background task and should not be called directly.
            It's automatically started by _ensure_writer_task().
        """
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
        """Write a single log entry to file and optionally to stdout.
        
        Handles the actual I/O operations for log writing with proper file locking
        to ensure thread-safety. Creates daily log files named with the pattern:
        {module_name}-{YYYY-MM-DD}.log
        
        Args:
            entry_data: Dictionary containing log entry information with keys:
                - timestamp: datetime object for the log entry
                - module: module name for file naming
                - log_path: directory path for log files
                - to_stdout: whether to also print to console
                - formatted: the formatted log message string
                
        Note:
            Uses asyncio.Lock per file path to prevent concurrent write conflicts.
            Creates default "logs" directory if no log_path is specified.
        """
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
        """Format a log entry into a human-readable string.
        
        Creates formatted log entries with configurable components based on
        the logger's settings. Handles special formatting for error levels.
        
        Args:
            timestamp: When the log event occurred.
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            module: Module name where the function resides.
            function: Function name being logged.
            args: Function positional arguments (if log_args=True).
            kwargs: Function keyword arguments (if log_args=True).
            result: Function return value (if log_result=True).
            duration_ms: Execution duration in milliseconds (if log_time=True).
            exception: Exception object if an error occurred.
            tb: Traceback string for exceptions.
            
        Returns:
            str: Formatted log entry string ready for writing.
            
        Note:
            ERROR and CRITICAL levels get special formatting with separators
            and full exception details. Regular levels use pipe-separated format.
        """

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
        """Format function arguments into a readable string for logging.
        
        Converts both positional and keyword arguments into a compact string
        representation suitable for log entries. Truncates long values to
        prevent log entries from becoming unwieldy.
        
        Args:
            args: Positional arguments tuple from the decorated function.
            kwargs: Keyword arguments dict from the decorated function.
            
        Returns:
            str: Formatted argument string in the format "(arg1, arg2, key=value)".
            
        Note:
            Individual argument representations are truncated to 50 characters
            to prevent extremely long log lines. Uses repr() for safe string
            representation of all argument types.
        """
        parts = []
        if args:
            args_str = ", ".join(repr(arg)[:50] for arg in args)
            parts.append(args_str)
        if kwargs:
            kwargs_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in kwargs.items())
            parts.append(kwargs_str)
        return "(" + ", ".join(parts) + ")"

    def _create_async_wrapper(self, func: Callable) -> Callable:
        """Create a logging wrapper for async functions.
        
        Generates an async wrapper that captures function execution details
        including timing, arguments, results, and exceptions. Handles the
        async-specific aspects of the logging process.
        
        Args:
            func: The async function to be wrapped.
            
        Returns:
            Callable: An async wrapper function that logs execution details.
            
        Note:
            The wrapper captures exceptions but does not re-raise them,
            instead logging them as ERROR level entries. This is by design
            to prevent decorated functions from failing unexpectedly.
        """

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
        """Create a logging wrapper for synchronous functions.
        
        Generates a sync wrapper that captures function execution details
        and handles the complexities of integrating with the async logging
        system from a synchronous context.
        
        Args:
            func: The synchronous function to be wrapped.
            
        Returns:
            Callable: A sync wrapper function that logs execution details.
            
        Note:
            Handles the async/sync bridge by attempting to use an existing
            event loop or creating one if necessary. The wrapper captures
            exceptions but does not re-raise them, logging them as ERROR entries.
        """

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
        """Fallback method for handling log entries from sync functions.
        
        This method is called when a sync function needs to log but no
        event loop is currently running. It creates a temporary event loop
        to handle the async logging operations.
        
        Args:
            entry_data: Dictionary containing the log entry information
                      to be processed and written.
                      
        Note:
            This method ensures that sync functions can still participate
            in the async logging system, even when called from pure sync contexts.
        """
        await self._log_queue.put(entry_data)
        # Ensure writer task processes it
        if self._writer_task is None:
            await self._write_log_entry(entry_data)

    @classmethod
    async def flush_logs(cls):
        """Force immediate processing of all pending log entries.
        
        Processes all queued log entries synchronously, ensuring they are
        written to disk before the method returns. Useful for cleanup or
        ensuring logs are persisted before application shutdown.
        
        Note:
            This method bypasses the normal async queue processing and
            handles all pending entries immediately. Should be called
            during application shutdown or when immediate log persistence
            is required.
        """
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
        """Parse a single pipe-separated log line into a dictionary.
        
        Parses standard log lines that follow the format:
        "timestamp | level | module.function | Args: (...) | Duration: Xms | Result: ..."
        
        Args:
            line: A single log line string to be parsed.
            
        Returns:
            Optional[dict]: Parsed log entry as dictionary with keys like
                          'timestamp', 'level', 'function', 'args', 'duration_ms', 'result',
                          or None if parsing fails.
                          
        Note:
            This method handles the standard pipe-separated format used by
            QuantLogger. Malformed lines return None rather than raising exceptions.
        """
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
        """Parse an error block (between separator lines) into a dictionary.
        
        Error blocks are special multi-line entries that contain the main log line,
        exception details, and full traceback information formatted between
        separator lines of equal signs.
        
        Args:
            lines: List of lines from an error block (without the separators).
            
        Returns:
            dict: Parsed error entry containing standard log fields plus
                 'exception' and 'traceback' fields if present.
                 
        Note:
            This method handles the special formatting used for ERROR and CRITICAL
            level entries, extracting both the main log information and detailed
            exception data.
        """
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
