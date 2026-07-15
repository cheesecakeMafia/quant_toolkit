"""Pytest configuration and global fixtures."""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd
import sqlite3
from datetime import datetime, date

# Add src to path for importing modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import fixtures from fixtures directory
from tests.fixtures.sample_data import (
    SampleOHLCVData,
    SampleContractData, 
    SampleHolidayData,
    SampleErrorData
)
from tests.fixtures.database_fixtures import (
    TestDatabase,
    temp_database,
    populated_database,
    multiple_timeframe_database,
    corrupted_database
)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Set test environment
    os.environ['TESTING'] = '1'
    os.environ['QUANT_TOOLKIT_ENV'] = 'test'
    
    # Configure pandas for testing
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    
    # Disable warnings for cleaner test output
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)


def pytest_unconfigure(config):
    """Clean up after pytest run."""
    # Clean up environment variables
    os.environ.pop('TESTING', None)
    os.environ.pop('QUANT_TOOLKIT_ENV', None)


# Scope fixtures
@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix="quant_toolkit_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="session") 
def reference_data_dir():
    """Get reference data directory path."""
    project_root = Path(__file__).parent.parent
    return project_root / "reference_data"


# Mock fixtures
@pytest.fixture
def mock_database_paths():
    """Mock database paths for testing."""
    with patch('quant_toolkit.sqlite_data_manager.DBPaths') as mock_paths:
        # Configure mock paths to use temporary directories
        mock_paths.index_db = "/tmp/test_index.db"
        mock_paths.futures_db = "/tmp/test_futures.db" 
        mock_paths.stocks_db = "/tmp/test_stocks.db"
        mock_paths.nse_futures_csv = "/tmp/test_nse_futures.csv"
        mock_paths.nse_stocks_csv = "/tmp/test_nse_stocks.csv"
        mock_paths.nse_index_csv = "/tmp/test_nse_index.csv"
        yield mock_paths


@pytest.fixture
def mock_web_requests():
    """Mock web requests for testing."""
    with patch('requests.get') as mock_get:
        # Configure default successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SampleHolidayData.get_sample_holidays_json()
        mock_response.text = SampleHolidayData.get_sample_holidays_json()
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing."""
    test_date = datetime(2024, 1, 15, 10, 30, 0)
    with patch('quant_toolkit.market_contracts.datetime') as mock_dt:
        mock_dt.now.return_value = test_date
        mock_dt.today.return_value = test_date.date()
        yield mock_dt


# Data fixtures
@pytest.fixture
def sample_ohlcv_daily():
    """Sample daily OHLCV data."""
    return SampleOHLCVData.generate_daily_ohlcv()


@pytest.fixture
def sample_ohlcv_intraday():
    """Sample intraday OHLCV data."""
    return SampleOHLCVData.generate_intraday_ohlcv()


@pytest.fixture
def sample_symbols():
    """Sample symbol list."""
    return SampleContractData.get_sample_symbols()


@pytest.fixture
def sample_futures_tickers():
    """Sample futures tickers."""
    return SampleContractData.get_sample_futures_tickers()


@pytest.fixture
def sample_options_tickers():
    """Sample options tickers."""
    return SampleContractData.get_sample_options_tickers()


@pytest.fixture
def sample_expiry_dates():
    """Sample expiry dates."""
    return SampleContractData.get_expiry_dates()


@pytest.fixture
def sample_holidays():
    """Sample holiday dates."""
    return SampleHolidayData.get_sample_holidays_2024()


@pytest.fixture
def invalid_ohlcv_data():
    """Invalid OHLCV data for error testing."""
    return SampleErrorData.get_invalid_ohlcv_data()


@pytest.fixture
def invalid_symbols():
    """Invalid symbols for error testing."""
    return SampleErrorData.get_invalid_symbols()


@pytest.fixture
def invalid_dates():
    """Invalid dates for error testing."""
    return SampleErrorData.get_invalid_dates()


# Performance fixtures
@pytest.fixture
def benchmark_config():
    """Configuration for benchmark tests."""
    return {
        'min_rounds': 10,
        'max_time': 1.0,
        'disable_gc': True,
        'timer': 'time.perf_counter'
    }


# Integration fixtures
@pytest.fixture
def integration_test_env():
    """Set up integration test environment."""
    # Set environment variables for integration tests
    original_env = os.environ.copy()
    
    os.environ.update({
        'QUANT_TOOLKIT_TEST_MODE': 'integration',
        'QUANT_TOOLKIT_LOG_LEVEL': 'DEBUG',
        'QUANT_TOOLKIT_DISABLE_CACHE': '1'
    })
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Clean up temporary files after each test."""
    temp_files = []
    
    yield temp_files
    
    # Clean up any temporary files created during tests
    for file_path in temp_files:
        try:
            if isinstance(file_path, (str, Path)):
                path = Path(file_path)
                if path.exists():
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        shutil.rmtree(path)
        except Exception:
            pass  # Ignore cleanup errors


# Logging fixtures
@pytest.fixture
def capture_logs():
    """Capture log output for testing."""
    import logging
    from io import StringIO
    
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    # Add handler to quant_toolkit loggers
    logger = logging.getLogger('quant_toolkit')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield log_capture
    
    # Clean up handler
    logger.removeHandler(handler)


# Async fixtures (if needed for future async code)
@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()