# Quant-Toolkit

## A private library for quantitative finance projects focused on Indian markets (NSE/BSE)

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
- SQLite-based storage (migration to TimeScaleDB planned)
- Schema: `datetime | open | high | low | close | volume | oi`
- Context-managed database operations
- Efficient batch processing

### 3. **decorators.py**
Production-ready function decorators:
- `@validate_params` - Runtime type validation
- `@time_logger` - Performance measurement with logging
- `@retry` - Configurable retry logic with exponential backoff
- `@memoize` - LRU caching with TTL support
- `@rate_limiter` - API rate limiting
- `@deprecated` - Deprecation warnings

### 4. **quantlogger.py**
Advanced logging system with comprehensive features:
- `QuantLogger` - Singleton logger with structured logging
- Multiple handlers (console, file, rotating)
- Performance tracking and metrics
- Context management for tracing
- Automatic log rotation and cleanup

### 5. **helper.py**
Utility functions for data processing:
- `data_batches()` - Splits date ranges into API-friendly chunks
- Symbol to ticker conversion
- File timestamp validation
- Integration with market contracts
