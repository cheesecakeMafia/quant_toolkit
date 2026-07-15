# Quant Toolkit Test Suite

This directory contains the comprehensive test suite for the Quant Toolkit library.

## Directory Structure

```
tests/
├── unit/                   # Unit tests for individual modules
│   ├── test_decorators.py         # Tests for decorators module
│   ├── test_market_contracts.py   # Tests for market contracts module
│   ├── test_sqlite_data_manager.py # Tests for database operations
│   ├── test_helper.py             # Tests for helper utilities
│   └── test_quantlogger.py        # Tests for logging module
├── integration/            # Integration tests across modules
│   ├── test_database_operations.py     # Database integration tests
│   ├── test_contract_generation.py     # Contract generation integration
│   └── test_decorator_integration.py   # Decorator integration tests
├── performance/            # Performance and benchmark tests
│   ├── test_database_performance.py        # Database performance tests
│   ├── test_contract_generation_performance.py # Contract performance tests
│   └── test_decorator_performance.py       # Decorator performance tests
├── fixtures/               # Test data and utilities
│   ├── sample_data.py             # Sample OHLCV and contract data
│   └── database_fixtures.py       # Database testing utilities
├── conftest.py            # Pytest configuration and global fixtures
└── README.md              # This file
```

## Running Tests

### Prerequisites

Install test dependencies:
```bash
# Install test dependencies
uv sync --extra test

# Or install development dependencies (includes test dependencies)
uv sync --extra dev
```

### Basic Test Commands

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests only
uv run pytest -m performance   # Performance tests only

# Run tests with coverage
uv run pytest --cov=src/quant_toolkit --cov-report=html

# Run tests in parallel (faster)
uv run pytest -n auto

# Run specific test file
uv run pytest tests/unit/test_decorators.py

# Run specific test method
uv run pytest tests/unit/test_decorators.py::TestValidateParams::test_valid_params
```

### Advanced Test Options

```bash
# Benchmark tests
uv run pytest -m benchmark --benchmark-only

# Skip slow tests
uv run pytest -m "not slow"

# Stop on first failure
uv run pytest -x

# Show test durations
uv run pytest --durations=10

# Verbose output with test names
uv run pytest -v

# Run tests and generate coverage report
uv run pytest --cov=src/quant_toolkit --cov-report=html --cov-report=term-missing
```

## Test Categories

### Unit Tests (`tests/unit/`)

Test individual modules in isolation with mocked dependencies:

- **test_decorators.py**: Tests for validation, timing, retry, caching, and rate limiting decorators
- **test_market_contracts.py**: Tests for contract ticker generation and expiry calculations
- **test_sqlite_data_manager.py**: Tests for database operations and CRUD functionality
- **test_helper.py**: Tests for utility functions including data batching and symbol conversion
- **test_quantlogger.py**: Tests for logging functionality and configuration

### Integration Tests (`tests/integration/`)

Test interactions between multiple modules:

- **test_database_operations.py**: End-to-end database workflows and data integrity
- **test_contract_generation.py**: Complete contract generation workflows with real data
- **test_decorator_integration.py**: Decorator behavior when applied to real module methods

### Performance Tests (`tests/performance/`)

Benchmark and performance regression tests:

- **test_database_performance.py**: Database operation performance and scalability
- **test_contract_generation_performance.py**: Contract generation speed and memory usage
- **test_decorator_performance.py**: Decorator overhead and optimization

## Test Configuration

### Environment Variables

Test environment variables are configured in `.env.test`:

```bash
QUANT_TOOLKIT_ENV=test
TESTING=1
QUANT_TOOLKIT_USE_MEMORY_DB=1
QUANT_TOOLKIT_DISABLE_CACHE=1
```

### Pytest Configuration

Configuration is set in both `pytest.ini` and `pyproject.toml`:

- Test discovery patterns
- Coverage settings
- Timeout configurations
- Warning filters
- Custom markers

### Fixtures

Global fixtures are defined in `conftest.py`:

- **Database fixtures**: Temporary databases with sample data
- **Mock fixtures**: Mock external dependencies and web requests
- **Data fixtures**: Sample OHLCV, contract, and holiday data
- **Environment fixtures**: Test environment setup and cleanup

## Writing Tests

### Test Structure

Follow the Arrange-Act-Assert pattern:

```python
def test_function_behavior():
    # Arrange: Set up test data and mocks
    sample_data = create_sample_data()
    
    # Act: Execute the function under test
    result = function_under_test(sample_data)
    
    # Assert: Verify expected outcomes
    assert result == expected_value
    assert mock_dependency.called
```

### Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Use descriptive names that explain what is being tested

### Mock External Dependencies

Mock external dependencies to ensure tests are fast and reliable:

```python
@patch('requests.get')
def test_web_scraping_fallback(self, mock_get):
    # Configure mock response
    mock_get.return_value.status_code = 404
    
    # Test fallback behavior
    result = function_that_scrapes_web()
    assert result.used_fallback is True
```

### Parametrized Tests

Use parametrized tests for testing multiple scenarios:

```python
@pytest.mark.parametrize("month,expected_code", [
    (1, "1"), (2, "2"), (10, "O"), (11, "N"), (12, "D")
])
def test_weekly_month_codes(self, month, expected_code):
    result = get_weekly_month_code(month)
    assert result == expected_code
```

## Coverage Requirements

- Minimum coverage target: 80%
- Critical modules (decorators, database operations): 95%
- New code should maintain or improve coverage
- Coverage reports available in `htmlcov/` directory

## Continuous Integration

Tests are designed to run in CI environments:

- Use environment variables for configuration
- Mock external dependencies
- Include timeout settings for long-running tests
- Generate coverage reports in multiple formats

## Test Data

### Sample Data

The `fixtures/sample_data.py` module provides:

- Realistic OHLCV data with proper price relationships
- Valid contract tickers for various instruments
- Holiday calendars for testing date calculations
- Invalid data for error condition testing

### Database Fixtures

The `fixtures/database_fixtures.py` module provides:

- Temporary SQLite databases for testing
- Pre-populated databases with sample data
- Corrupted data scenarios for error handling tests
- Multi-timeframe data for complex queries

## Debugging Tests

### Running Failed Tests

```bash
# Re-run only failed tests
uv run pytest --lf

# Run failed tests first, then all others
uv run pytest --ff

# Drop into debugger on failures
uv run pytest --pdb

# Capture print statements
uv run pytest -s
```

### Test Debugging Tips

1. Use `pytest.set_trace()` to drop into debugger
2. Add print statements with `-s` flag
3. Check log files in `/tmp/` directory
4. Use `--tb=long` for detailed tracebacks
5. Run single tests to isolate issues

## Best Practices

1. **Test Independence**: Tests should not depend on each other
2. **Mock External Dependencies**: Don't rely on external services
3. **Clear Test Names**: Test names should explain what is being tested
4. **Fast Tests**: Keep unit tests under 100ms each
5. **Reliable Tests**: Tests should pass consistently
6. **Good Coverage**: Test both success and failure paths
7. **Readable Tests**: Tests serve as documentation for expected behavior