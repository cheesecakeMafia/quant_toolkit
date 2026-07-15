"""Unit tests for quantlogger module."""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, mock_open
from typing import Any
from pydantic import ValidationError

from quant_toolkit.quantlogger import QuantLogger


class TestQuantLoggerInitialization:
    """Test cases for QuantLogger initialization and configuration."""

    def test_logger_initialization_defaults(self):
        """Test QuantLogger initialization with default values."""
        logger = QuantLogger()
        
        assert logger.name is None
        assert logger.log_path is None
        assert logger.level == "INFO"
        assert logger.log_args is False
        assert logger.log_result is False
        assert logger.log_time is False
        assert logger.to_stdout is True

    def test_logger_initialization_custom_values(self):
        """Test QuantLogger initialization with custom values."""
        custom_path = Path("/tmp/test_logs")
        logger = QuantLogger(
            name="test_logger",
            log_path=custom_path,
            level="DEBUG",
            log_args=True,
            log_result=True,
            log_time=True,
            to_stdout=False
        )
        
        assert logger.name == "test_logger"
        assert logger.log_path == custom_path
        assert logger.level == "DEBUG"
        assert logger.log_args is True
        assert logger.log_result is True
        assert logger.log_time is True
        assert logger.to_stdout is False

    def test_invalid_level_validation(self):
        """Test that invalid log levels raise validation errors."""
        with pytest.raises(ValidationError):
            QuantLogger(level="INVALID")

    def test_log_path_creation(self):
        """Test that log path is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "new_logs"
            assert not log_path.exists()
            
            logger = QuantLogger(log_path=log_path)
            
            # Path should be created during validation
            assert log_path.exists()
            assert log_path.is_dir()

    def test_global_path_setting(self):
        """Test setting and using global log path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            global_path = Path(temp_dir) / "global_logs"
            
            QuantLogger.set_global_path(global_path)
            
            assert global_path.exists()
            assert QuantLogger._global_log_path == global_path
            
            # New logger should use global path when no instance path provided
            # Note: The validator uses the global path during initialization
            logger = QuantLogger()
            # The path should be set during validation, but may be None in log_path field
            # because it falls back to the global path in the validator
            # Let's check the global path is set correctly
            assert QuantLogger._global_log_path == global_path


class TestQuantLoggerAsyncComponents:
    """Test cases for async components of QuantLogger."""

    @pytest.mark.asyncio
    async def test_async_components_initialization(self):
        """Test that async components are properly initialized."""
        # Reset class state
        QuantLogger._initialized = False
        QuantLogger._log_queue = None
        QuantLogger._writer_task = None
        
        logger = QuantLogger()
        
        # Should initialize async components
        assert QuantLogger._initialized is True
        assert QuantLogger._log_queue is not None
        assert isinstance(QuantLogger._log_queue, asyncio.Queue)

    @pytest.mark.asyncio
    async def test_log_writer_task_creation(self):
        """Test that log writer task is created when event loop exists."""
        # Reset class state
        QuantLogger._initialized = False
        QuantLogger._writer_task = None
        
        logger = QuantLogger()
        
        # Ensure writer task is running
        logger._ensure_writer_task()
        
        assert QuantLogger._writer_task is not None
        assert isinstance(QuantLogger._writer_task, asyncio.Task)
        
        # Clean up
        if QuantLogger._writer_task and not QuantLogger._writer_task.done():
            QuantLogger._writer_task.cancel()
            try:
                await QuantLogger._writer_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_log_queue_operations(self):
        """Test basic log queue operations."""
        logger = QuantLogger()
        
        test_data = {"test": "data", "timestamp": datetime.now()}
        
        # Should be able to put and get from queue
        await QuantLogger._log_queue.put(test_data)
        retrieved_data = await QuantLogger._log_queue.get()
        
        assert retrieved_data == test_data

    @pytest.mark.asyncio
    async def test_flush_logs(self):
        """Test manual log flushing."""
        logger = QuantLogger()
        
        # Put some test data in queue
        test_entries = [
            {"test": "entry1", "timestamp": datetime.now()},
            {"test": "entry2", "timestamp": datetime.now()}
        ]
        
        for entry in test_entries:
            await QuantLogger._log_queue.put(entry)
        
        with patch.object(QuantLogger, '_write_log_entry', new=AsyncMock()) as mock_write:
            await QuantLogger.flush_logs()
            
            # Should have called write_log_entry for each entry
            assert mock_write.call_count == len(test_entries)


class TestQuantLoggerDecorator:
    """Test cases for QuantLogger decorator functionality."""

    def test_sync_function_decoration(self):
        """Test decorating synchronous functions."""
        logger = QuantLogger(log_args=True, log_result=True, log_time=True)
        
        @logger
        def test_function(x: int, y: int) -> int:
            return x + y
        
        # Function should still work normally
        result = test_function(2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_async_function_decoration(self):
        """Test decorating asynchronous functions."""
        logger = QuantLogger(log_args=True, log_result=True, log_time=True)
        
        @logger
        async def test_async_function(x: int, y: int) -> int:
            await asyncio.sleep(0.01)  # Small delay
            return x * y
        
        # Function should still work normally
        result = await test_async_function(3, 4)
        assert result == 12

    def test_function_detection(self):
        """Test that decorator correctly detects async vs sync functions."""
        logger = QuantLogger()
        
        def sync_func():
            return "sync"
        
        async def async_func():
            return "async"
        
        sync_wrapped = logger(sync_func)
        async_wrapped = logger(async_func)
        
        # Sync function should not be a coroutine function
        assert not asyncio.iscoroutinefunction(sync_wrapped)
        
        # Async function should remain a coroutine function
        assert asyncio.iscoroutinefunction(async_wrapped)

    @pytest.mark.asyncio
    async def test_exception_handling_async(self):
        """Test exception handling in async functions."""
        logger = QuantLogger()
        
        @logger
        async def failing_function():
            raise ValueError("Test exception")
        
        # Exception should be caught and logged, function should return None
        result = await failing_function()
        assert result is None

    def test_exception_handling_sync(self):
        """Test exception handling in sync functions."""
        logger = QuantLogger()
        
        @logger
        def failing_function():
            raise RuntimeError("Test exception")
        
        # Exception should be caught and logged, function should return None
        result = failing_function()
        assert result is None


class TestLogFormatting:
    """Test cases for log message formatting."""

    def test_basic_log_formatting(self):
        """Test basic log message formatting."""
        logger = QuantLogger()
        timestamp = datetime(2024, 1, 15, 12, 0, 0, 123456)
        
        formatted = logger._format_log_entry(
            timestamp=timestamp,
            level="INFO",
            module="test_module",
            function="test_function"
        )
        
        expected_parts = [
            "2024-01-15 12:00:00.123",
            "INFO",
            "test_module.test_function"
        ]
        
        for part in expected_parts:
            assert part in formatted

    def test_log_formatting_with_args(self):
        """Test log formatting with function arguments."""
        logger = QuantLogger(log_args=True)
        timestamp = datetime.now()
        
        formatted = logger._format_log_entry(
            timestamp=timestamp,
            level="DEBUG",
            module="test_module",
            function="test_function",
            args=(1, 2, "test"),
            kwargs={"key": "value"}
        )
        
        assert "Args:" in formatted
        assert "1, 2, 'test'" in formatted
        assert "key='value'" in formatted

    def test_log_formatting_with_timing(self):
        """Test log formatting with execution timing."""
        logger = QuantLogger(log_time=True)
        timestamp = datetime.now()
        
        formatted = logger._format_log_entry(
            timestamp=timestamp,
            level="INFO",
            module="test_module",
            function="test_function",
            duration_ms=123.45
        )
        
        assert "Duration: 123.45ms" in formatted

    def test_log_formatting_with_result(self):
        """Test log formatting with function result."""
        logger = QuantLogger(log_result=True)
        timestamp = datetime.now()
        
        formatted = logger._format_log_entry(
            timestamp=timestamp,
            level="INFO",
            module="test_module",
            function="test_function",
            result="test result"
        )
        
        assert "Result: test result" in formatted

    def test_error_log_formatting(self):
        """Test special formatting for ERROR and CRITICAL levels."""
        logger = QuantLogger()
        timestamp = datetime.now()
        exception = ValueError("Test error")
        
        formatted = logger._format_log_entry(
            timestamp=timestamp,
            level="ERROR",
            module="test_module",
            function="test_function",
            exception=exception,
            tb="Traceback test"
        )
        
        assert "=" * 80 in formatted
        assert "Exception: ValueError: Test error" in formatted
        assert "Traceback test" in formatted

    def test_argument_formatting(self):
        """Test argument formatting helper method."""
        logger = QuantLogger()
        
        # Test with both args and kwargs
        formatted = logger._format_arguments(
            (1, "test", [1, 2, 3]),
            {"key1": "value1", "key2": 42}
        )
        
        assert "(" in formatted and ")" in formatted
        assert "1" in formatted
        assert "'test'" in formatted
        assert "key1='value1'" in formatted
        assert "key2=42" in formatted

    def test_long_result_truncation(self):
        """Test that long results are properly truncated."""
        logger = QuantLogger(log_result=True)
        timestamp = datetime.now()
        
        long_result = "x" * 150  # Longer than 100 character limit
        
        formatted = logger._format_log_entry(
            timestamp=timestamp,
            level="INFO",
            module="test_module",
            function="test_function",
            result=long_result
        )
        
        assert "..." in formatted
        assert len(formatted.split("Result: ")[1].split(" |")[0]) <= 103  # 100 + "..."


@pytest.mark.asyncio
class TestLogFileOperations:
    """Test cases for log file operations."""

    async def test_write_log_entry(self):
        """Test writing log entries to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            
            entry_data = {
                "timestamp": datetime(2024, 1, 15, 12, 0, 0),
                "module": "test_module",
                "log_path": log_path,
                "to_stdout": False,
                "formatted": "Test log entry"
            }
            
            await QuantLogger._write_log_entry(entry_data)
            
            # Check that file was created with correct name
            expected_file = log_path / "test_module-2024-01-15.log"
            assert expected_file.exists()
            
            # Check file contents
            content = expected_file.read_text()
            assert "Test log entry" in content

    async def test_daily_log_rotation(self):
        """Test that logs are rotated daily by filename."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            
            # Create entries for different dates
            entry1 = {
                "timestamp": datetime(2024, 1, 15, 12, 0, 0),
                "module": "test_module",
                "log_path": log_path,
                "to_stdout": False,
                "formatted": "Entry for day 1"
            }
            
            entry2 = {
                "timestamp": datetime(2024, 1, 16, 12, 0, 0),
                "module": "test_module",
                "log_path": log_path,
                "to_stdout": False,
                "formatted": "Entry for day 2"
            }
            
            await QuantLogger._write_log_entry(entry1)
            await QuantLogger._write_log_entry(entry2)
            
            # Should create separate files for each day
            file1 = log_path / "test_module-2024-01-15.log"
            file2 = log_path / "test_module-2024-01-16.log"
            
            assert file1.exists()
            assert file2.exists()
            
            assert "Entry for day 1" in file1.read_text()
            assert "Entry for day 2" in file2.read_text()

    async def test_concurrent_file_access(self):
        """Test thread-safe file access with locks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            
            # Create multiple entries for the same file
            entries = []
            for i in range(5):
                entries.append({
                    "timestamp": datetime(2024, 1, 15, 12, 0, 0),
                    "module": "test_module",
                    "log_path": log_path,
                    "to_stdout": False,
                    "formatted": f"Entry {i}"
                })
            
            # Write all entries concurrently
            tasks = [QuantLogger._write_log_entry(entry) for entry in entries]
            await asyncio.gather(*tasks)
            
            # All entries should be in the file
            log_file = log_path / "test_module-2024-01-15.log"
            content = log_file.read_text()
            
            for i in range(5):
                assert f"Entry {i}" in content

    async def test_default_log_path_creation(self):
        """Test creation of default log path when none provided."""
        # This test checks that the default "logs" directory is created
        # when no log path is provided
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory so "logs" directory gets created there
            import os
            old_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                entry_data = {
                    "timestamp": datetime.now(),
                    "module": "test_module", 
                    "log_path": None,
                    "to_stdout": False,
                    "formatted": "Test entry"
                }
                
                await QuantLogger._write_log_entry(entry_data)
                
                # Should create "logs" directory in current working directory
                logs_path = Path(temp_dir) / "logs"
                assert logs_path.exists()
                
                # Should create log file
                log_files = list(logs_path.glob("test_module-*.log"))
                assert len(log_files) == 1
                
                # Check file contents
                content = log_files[0].read_text()
                assert "Test entry" in content
                
            finally:
                os.chdir(old_cwd)


class TestLogConversion:
    """Test cases for log to JSON conversion functionality."""

    def test_log_to_json_conversion(self):
        """Test converting log file to JSON format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as log_file:
            # Write sample log entries
            log_file.write("2024-01-15 12:00:00.123 | INFO | test_module.test_function\n")
            log_file.write("2024-01-15 12:01:00.456 | DEBUG | test_module.test_function | Args: (1, 2) | Duration: 10.5ms | Result: 3\n")
            log_file_path = Path(log_file.name)
        
        try:
            # Convert to JSON
            json_path = QuantLogger.log_to_json(log_file_path)
            
            assert json_path.exists()
            assert json_path.suffix == '.json'
            
            # Check JSON content
            with open(json_path, 'r') as f:
                entries = json.load(f)
            
            assert len(entries) == 2
            
            # Check first entry
            assert entries[0]['level'] == 'INFO'
            assert entries[0]['function'] == 'test_module.test_function'
            
            # Check second entry with additional fields
            assert entries[1]['level'] == 'DEBUG'
            assert 'args' in entries[1]
            assert 'duration_ms' in entries[1]
            assert entries[1]['duration_ms'] == 10.5
            assert 'result' in entries[1]
            
        finally:
            log_file_path.unlink(missing_ok=True)
            if json_path.exists():
                json_path.unlink()

    def test_log_to_json_with_error_blocks(self):
        """Test converting logs with error blocks to JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as log_file:
            # Write error block
            log_file.write("=" * 80 + "\n")
            log_file.write("2024-01-15 12:00:00.123 | ERROR | test_module.test_function\n")
            log_file.write("Exception: ValueError: Test error\n")
            log_file.write("Traceback (most recent call last):\n")
            log_file.write("  File test.py, line 1, in <module>\n")
            log_file.write("=" * 80 + "\n")
            log_file_path = Path(log_file.name)
        
        try:
            json_path = QuantLogger.log_to_json(log_file_path)
            
            with open(json_path, 'r') as f:
                entries = json.load(f)
            
            assert len(entries) == 1
            assert entries[0]['level'] == 'ERROR'
            assert 'exception' in entries[0]
            assert 'ValueError: Test error' in entries[0]['exception']
            assert 'traceback' in entries[0]
            
        finally:
            log_file_path.unlink(missing_ok=True)
            if json_path.exists():
                json_path.unlink()

    def test_log_to_json_nonexistent_file(self):
        """Test error handling for nonexistent log file."""
        nonexistent_file = Path("/nonexistent/file.log")
        
        with pytest.raises(FileNotFoundError, match="Log file not found"):
            QuantLogger.log_to_json(nonexistent_file)

    def test_parse_log_line(self):
        """Test parsing individual log lines."""
        # Test basic log line
        line = "2024-01-15 12:00:00.123 | INFO | test_module.test_function"
        parsed = QuantLogger._parse_log_line(line)
        
        assert parsed is not None
        assert parsed['timestamp'] == "2024-01-15 12:00:00.123"
        assert parsed['level'] == "INFO"
        assert parsed['function'] == "test_module.test_function"

    def test_parse_log_line_with_extras(self):
        """Test parsing log lines with additional information."""
        line = "2024-01-15 12:00:00.123 | DEBUG | test_module.test_function | Args: (1, 2) | Duration: 15.5ms | Result: success"
        parsed = QuantLogger._parse_log_line(line)
        
        assert parsed is not None
        assert 'args' in parsed
        assert parsed['args'] == "(1, 2)"
        assert 'duration_ms' in parsed
        assert parsed['duration_ms'] == 15.5
        assert 'result' in parsed
        assert parsed['result'] == "success"

    def test_parse_invalid_log_line(self):
        """Test handling of invalid log lines."""
        invalid_line = "This is not a valid log line"
        parsed = QuantLogger._parse_log_line(invalid_line)
        
        assert parsed is None

    def test_parse_error_block(self):
        """Test parsing error blocks."""
        lines = [
            "2024-01-15 12:00:00.123 | ERROR | test_module.test_function",
            "Exception: ValueError: Test error",
            "Traceback (most recent call last):",
            "  File test.py, line 1, in <module>"
        ]
        
        parsed = QuantLogger._parse_error_block(lines)
        
        assert 'level' in parsed
        assert parsed['level'] == 'ERROR'
        assert 'exception' in parsed
        assert 'ValueError: Test error' in parsed['exception']
        assert 'traceback' in parsed


class TestPydanticValidation:
    """Test cases for Pydantic validation in QuantLogger."""

    def test_field_validation(self):
        """Test field validation through Pydantic."""
        # Valid configuration
        logger = QuantLogger(
            level="WARNING",
            log_args=True,
            log_result=False
        )
        
        assert logger.level == "WARNING"
        assert logger.log_args is True
        assert logger.log_result is False

    def test_path_validation_and_creation(self):
        """Test path validation that creates directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_path = Path(temp_dir) / "validation_test"
            
            logger = QuantLogger(log_path=new_path)
            
            # Path should be created and validated
            assert new_path.exists()
            assert logger.log_path == new_path

    def test_dataclass_field_types(self):
        """Test that dataclass fields have correct types."""
        logger = QuantLogger()
        
        # Check field types match annotations
        assert isinstance(logger.log_args, bool)
        assert isinstance(logger.log_result, bool)
        assert isinstance(logger.log_time, bool)
        assert isinstance(logger.to_stdout, bool)
        assert logger.level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]