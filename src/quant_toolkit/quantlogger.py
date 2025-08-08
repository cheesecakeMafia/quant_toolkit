"""
QuantLogger: Comprehensive async-first logging decorator for quant_toolkit.
Provides thread-safe, async-compatible logging with Pydantic validation.
"""

from pydantic.dataclasses import dataclass
from pydantic import Field, validator
import asyncio
import aiofiles
import aiohttp
import json
import os
import time
import traceback
from pathlib import Path
from typing import Optional, Literal, Any, Callable, Dict, ClassVar, List
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
        - **Notification services**: Send log messages to Discord, Slack, and Twilio SMS
        - **Service selection**: Fine-grained control per function via services parameter
        - **Failure tracking**: Notification failures logged to separate third-party.log

    Configuration Fields:
        name: Optional logger name (defaults to module.function)
        log_path: Directory for log files (falls back to global or creates 'logs')
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_args: Whether to capture and log function arguments
        log_result: Whether to capture and log function return values
        log_time: Whether to measure and log execution duration
        to_stdout: Whether to duplicate log entries to console
        services: List of notification services ('discord', 'slack', 'twilio')

    Usage Examples:
        # Basic usage with timing
        @QuantLogger(log_time=True)
        async def fetch_data(symbol: str) -> dict:
            return {"price": 100.0, "symbol": symbol}

        # Full logging with arguments and results
        @QuantLogger(log_args=True, log_result=True, log_time=True, level="DEBUG")
        def calculate_portfolio_value(positions: list[dict]) -> float:
            return sum(p["quantity"] * p["price"] for p in positions)

        # With notification services
        @QuantLogger(level="ERROR", services=["discord", "slack"])
        def critical_operation():
            # Errors will be sent to Discord and Slack
            pass

        # Instance-based pattern with notifications
        alert_logger = QuantLogger(level="ERROR", services=["discord", "twilio"])

        @alert_logger
        def monitored_function():
            # Errors sent to Discord and SMS via Twilio
            pass

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
    services: List[str] = Field(
        default_factory=list,
        description="List of notification services: 'discord', 'slack', 'twilio'",
    )

    # Class-level shared resources (using ClassVar to exclude from dataclass fields)
    _global_log_path: ClassVar[Optional[Path]] = None
    _log_queue: ClassVar[Optional[asyncio.Queue]] = None
    _writer_task: ClassVar[Optional[asyncio.Task]] = None
    _file_locks: ClassVar[Dict[Path, asyncio.Lock]] = {}
    _initialized: ClassVar[bool] = False

    # Notification configuration
    _discord_webhook_url: ClassVar[Optional[str]] = None
    _slack_webhook_url: ClassVar[Optional[str]] = None
    _twilio_config: ClassVar[Optional[Dict[str, str]]] = None
    _notification_level: ClassVar[str] = (
        "ERROR"  # Changed from list to single threshold
    )
    _third_party_log_path: ClassVar[Optional[Path]] = None
    _notifications_enabled: ClassVar[bool] = True
    _notification_prefix: ClassVar[str] = ""
    _notification_suffix: ClassVar[str] = ""
    _notification_timeout: ClassVar[int] = 10

    # Define log level hierarchy (lower number = higher priority)
    _level_hierarchy: ClassVar[Dict[str, int]] = {
        "CRITICAL": 50,
        "ERROR": 40,
        "WARNING": 30,
        "INFO": 20,
        "DEBUG": 10,
    }

    @validator("services")
    def validate_services(cls, v):
        """Validate service names."""
        valid_services = {"discord", "slack", "twilio"}
        invalid = set(v) - valid_services
        if invalid:
            raise ValueError(
                f"Invalid services: {invalid}. Valid options: {valid_services}"
            )
        return v

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
    def load_notification_config(cls):
        """Load notification configuration from .env file."""
        # Don't call load_dotenv() here - let the user load their env file first
        # load_dotenv()  # Commented out - user should load env before importing

        # Discord configuration
        if os.getenv("DISCORD_NOTIFICATIONS_ENABLED", "false").lower() == "true":
            cls._discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

        # Slack configuration
        if os.getenv("SLACK_NOTIFICATIONS_ENABLED", "false").lower() == "true":
            cls._slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

        # Twilio configuration
        if os.getenv("TWILIO_NOTIFICATIONS_ENABLED", "false").lower() == "true":
            cls._twilio_config = {
                "account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
                "auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
                "from_phone": os.getenv("TWILIO_FROM_PHONE"),
                "to_phone": os.getenv("TWILIO_TO_PHONE"),
            }

        # Notification level threshold
        cls._notification_level = (
            os.getenv("NOTIFICATION_LEVEL", "ERROR").strip().upper()
        )
        if cls._notification_level not in cls._level_hierarchy:
            print(
                f"Warning: Invalid NOTIFICATION_LEVEL '{cls._notification_level}', defaulting to ERROR"
            )
            cls._notification_level = "ERROR"

        # Third-party log path
        if os.getenv("THIRD_PARTY_LOG_ENABLED", "true").lower() == "true":
            third_party_path = os.getenv("THIRD_PARTY_LOG_PATH", "logs/third-party.log")
            cls._third_party_log_path = Path(third_party_path)
            # Create directory if doesn't exist
            cls._third_party_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Global settings
        cls._notifications_enabled = (
            os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"
        )
        cls._notification_prefix = os.getenv("NOTIFICATION_PREFIX", "")
        cls._notification_suffix = os.getenv("NOTIFICATION_SUFFIX", "")
        cls._notification_timeout = int(os.getenv("NOTIFICATION_TIMEOUT", "10"))

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
            cls.load_notification_config()  # Load notification configuration
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

        # Check if notifications should be sent
        if entry_data.get("services") and cls._notifications_enabled:
            # Fire-and-forget notification sending
            asyncio.create_task(cls._send_notifications(entry_data))

    @classmethod
    async def _send_notifications(cls, entry_data: dict):
        """Send notifications to configured services."""
        # Get services list from entry_data
        services = entry_data.get("services", [])

        # If no services specified, return early
        if not services:
            return

        # Check if this level should trigger notifications based on hierarchy
        level = entry_data.get("level")

        # Get priority values (higher number = lower priority)
        log_level_priority = cls._level_hierarchy.get(level, 0)
        threshold_priority = cls._level_hierarchy.get(cls._notification_level, 40)

        # Only send notification if log level priority is >= threshold priority
        # (e.g., ERROR(40) >= ERROR(40), CRITICAL(50) >= ERROR(40), but INFO(20) < ERROR(40))
        if log_level_priority < threshold_priority:
            return

        # Build tasks based on requested services
        tasks = []
        service_names = []

        if "discord" in services:
            if cls._discord_webhook_url:
                tasks.append(cls._send_discord_notification(entry_data))
                service_names.append("discord")
            else:
                # Log that Discord was requested but not configured
                await cls._log_third_party_failure(
                    "discord",
                    Exception("Discord webhook URL not configured"),
                    entry_data,
                )

        if "slack" in services:
            if cls._slack_webhook_url:
                tasks.append(cls._send_slack_notification(entry_data))
                service_names.append("slack")
            else:
                await cls._log_third_party_failure(
                    "slack", Exception("Slack webhook URL not configured"), entry_data
                )

        if "twilio" in services:
            if cls._twilio_config:
                tasks.append(cls._send_twilio_notification(entry_data))
                service_names.append("twilio")
            else:
                await cls._log_third_party_failure(
                    "twilio", Exception("Twilio configuration not set"), entry_data
                )

        # Execute notifications in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any failures
            for service_name, result in zip(service_names, results):
                if isinstance(result, Exception):
                    await cls._log_third_party_failure(service_name, result, entry_data)

    @classmethod
    async def _send_discord_notification(cls, entry_data: dict):
        """Send notification to Discord webhook."""
        # Use same format as logs
        message = entry_data.get("formatted", "")

        # Add prefix/suffix if configured
        if cls._notification_prefix:
            message = f"{cls._notification_prefix} {message}"
        if cls._notification_suffix:
            message = f"{message} {cls._notification_suffix}"

        # Discord has a 2000 character limit
        if len(message) > 2000:
            message = message[:1997] + "..."

        payload = {"content": message}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                cls._discord_webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=cls._notification_timeout),
            ) as response:
                if response.status not in (200, 204):
                    text = await response.text()
                    raise Exception(
                        f"Discord webhook failed with status {response.status}: {text}"
                    )

    @classmethod
    async def _send_slack_notification(cls, entry_data: dict):
        """Send notification to Slack webhook."""
        # Use same format as logs
        message = entry_data.get("formatted", "")

        # Add prefix/suffix if configured
        if cls._notification_prefix:
            message = f"{cls._notification_prefix} {message}"
        if cls._notification_suffix:
            message = f"{message} {cls._notification_suffix}"

        payload = {"text": message}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                cls._slack_webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=cls._notification_timeout),
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(
                        f"Slack webhook failed with status {response.status}: {text}"
                    )

    @classmethod
    async def _send_twilio_notification(cls, entry_data: dict):
        """Send SMS notification via Twilio."""
        # SMS has character limits, so we need a condensed format
        level = entry_data.get("level", "INFO")
        module = entry_data.get("module", "unknown")
        function = entry_data.get("function", "unknown")
        timestamp = entry_data.get("timestamp", datetime.now())
        time_str = timestamp.strftime("%H:%M:%S")

        # Create condensed message (SMS limit is 160 chars typically)
        message = f"[{level}] {module}.{function} @ {time_str}"

        # Add exception info if present
        if "exception" in entry_data and entry_data["exception"]:
            exception_str = str(entry_data["exception"])[:50]
            message += f"\n{exception_str}"

        # Add prefix/suffix if they fit
        if (
            cls._notification_prefix
            and len(message) + len(cls._notification_prefix) < 155
        ):
            message = f"{cls._notification_prefix} {message}"
        if (
            cls._notification_suffix
            and len(message) + len(cls._notification_suffix) < 160
        ):
            message = f"{message} {cls._notification_suffix}"

        # Ensure message doesn't exceed 160 characters
        if len(message) > 160:
            message = message[:157] + "..."

        # Twilio API endpoint
        url = f"https://api.twilio.com/2010-04-01/Accounts/{cls._twilio_config['account_sid']}/Messages.json"

        auth = aiohttp.BasicAuth(
            cls._twilio_config["account_sid"], cls._twilio_config["auth_token"]
        )

        data = {
            "From": cls._twilio_config["from_phone"],
            "To": cls._twilio_config["to_phone"],
            "Body": message,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=data,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=cls._notification_timeout),
            ) as response:
                if response.status != 201:
                    text = await response.text()
                    raise Exception(
                        f"Twilio SMS failed with status {response.status}: {text}"
                    )

    @classmethod
    async def _log_third_party_failure(
        cls, service: str, error: Exception, entry_data: dict
    ):
        """Log notification failures to third-party.log."""
        if not cls._third_party_log_path:
            return

        timestamp = datetime.now()
        level = entry_data.get("level", "INFO")
        module = entry_data.get("module", "unknown")
        function = entry_data.get("function", "unknown")

        # Format the failure log entry
        failure_entry = (
            f"{timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | "
            f"NOTIFICATION_FAILURE | {service.upper()} | "
            f"Error: {error}\n"
            f"  Original log: [{level}] {module}.{function}\n"
        )

        # Get or create lock for third-party log file
        if cls._third_party_log_path not in cls._file_locks:
            cls._file_locks[cls._third_party_log_path] = asyncio.Lock()

        async with cls._file_locks[cls._third_party_log_path]:
            # Write to third-party log file
            async with aiofiles.open(cls._third_party_log_path, "a") as f:
                await f.write(failure_entry)

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
                    "level": level,  # For notification filtering
                    "services": self.services,  # List of notification services
                    "function": function,  # For notification context
                    "exception": exception,  # For error notifications
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
                    "level": level,  # For notification filtering
                    "services": self.services,  # List of notification services
                    "function": function,  # For notification context
                    "exception": exception,  # For error notifications
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
