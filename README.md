# Quant-Toolkit

## A library for quantitative finance projects focused on Indian markets (NSE/BSE)

> **Version**: 0.1.1 | **Python**: >= 3.12

This library provides production-ready tools for interacting with financial data, generating market contracts, and implementing quantitative strategies.

## Installation

This project uses UV for package management. To set up your environment:

```bash
# Create and sync virtual environment
uv sync

# Install in development mode
uv pip install -e .
```

## Core Modules

### 1. **market_contracts.py**
Modern contract ticker generation system for NSE/BSE derivatives:
- `ContractGenerator` - Generates futures and options contract tickers
- `MarketCalendar` - Handles market holidays and trading days
- Support for monthly/weekly expiries, futures, and options
- Automatic holiday adjustments with web scraping fallback

### 2. **sqlite_data_manager.py**
Database interaction for time-series OHLCV financial data:
- SQLite-based storage (migration to TimeScaleDB under consideration)
- Schema: `datetime | open | high | low | close | volume | oi`
- Database paths configured via `.env` (`DATA_DIR` environment variable)
- Connection pooling with WAL mode optimization
- Context-managed database operations

### 3. **decorators.py**
Production-ready function decorators:
- `@validate_params` - Runtime type validation
- `@time_logger` - Performance measurement with logging
- `@retry` - Configurable retry logic with exponential backoff
- `@memoize` - LRU caching with TTL support
- `@rate_limiter` - API rate limiting (token bucket algorithm)
- `@deprecated` - Deprecation warnings
- `@debug` - Debug output with argument/return value logging
- `@slow_down` - Intentional delay for rate-sensitive operations
- `@singleton` - Thread-safe singleton pattern enforcement

### 4. **quantlogger.py**
Async-first logging system with notification support:
- `QuantLogger` - Pydantic dataclass used as a decorator with structured logging
- Multiple handlers (console, file, rotating)
- Performance tracking and metrics
- Automatic log rotation and cleanup
- **Notification integrations**: Discord webhooks, Slack webhooks, Twilio SMS
  - Fire-and-forget async dispatch (non-blocking)
  - Configurable per-function via `services=["discord", "slack", "twilio"]`
  - Notification level filtering (default: ERROR, CRITICAL)

### 5. **helper.py**
Utility functions for data processing:
- `data_batches()` - Splits date ranges into API-friendly chunks
- Symbol to ticker conversion
- File timestamp validation
- Integration with market contracts

## Running Tests

```bash
# Install test/dev dependencies
uv sync --extra dev

# Run all tests
uv run pytest

# Run by category
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m performance

# Run with coverage
uv run pytest --cov=src/quant_toolkit --cov-report=html
```
