# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quant Toolkit is a private library for quantitative finance projects focused on Indian markets (NSE/BSE). It provides tools for:
- Database interaction with time-series OHLCV financial data (SQLite-based, considering migration to TimeScaleDB)
- Contract ticker generation for NSE/BSE derivatives (futures and options)
- Production-ready decorators for validation, timing, retry logic, caching, and rate limiting
- Helper utilities for data batching and symbol conversion

## Development Commands

```bash
# Setup environment (uses uv package manager)
uv sync

# Run linting
uv run ruff check src/

# Format code
uv run ruff format src/

# Fix auto-fixable linting issues
uv run ruff check --fix src/

# Build package
uv build

# Install in development mode
uv pip install -e .

# Profile performance (after adding @profile decorator)
uv run kernprof -l -v src/quant_toolkit/module.py
```

## Architecture & Key Patterns

### Database Design (sqlite_data_manager.py)
- **Schema**: `datetime(index) | open | high | low | close | volume | oi(optional)`
- Each security has its own table in SQLite database
- `DataHandler` class provides the main interface for CRUD operations
- `DBPaths` dataclass manages hardcoded database file paths (index/futures/stocks) and symbol lists
- Uses context managers for database cursor operations
- Note: Module marked as WIP, considering migration from SQLite to TimeScaleDB

### Contract Ticker Generation (market_contracts.py)
- **ContractGenerator** class provides unified interface for contract generation
- **MarketCalendar** handles holiday validation and trading day calculations
- Generates contract tickers based on exchange formats:
  - Monthly futures: `{Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}FUT`
  - Monthly options: `{Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}{Strike}{Opt_Type}`
  - Weekly options: `{Ex}:{Ex_UnderlyingSymbol}{YY}{M}{dd}{Strike}{Opt_Type}`
    - Special month encoding for weekly: Jan=1, Feb=2...Sep=9, Oct=O, Nov=N, Dec=D
- Uses Enums for type safety (Exchange, OptionType, ContractType, ExpiryType)
- Handles holiday adjustments via web scraping (fallback to local CSV)
- Expiry date calculations for current/next month contracts
- Comprehensive validation and error handling

### Logging System (quantlogger.py)
- **QuantLogger** singleton pattern ensures single logger instance
- Structured logging with JSON formatter support
- Multiple handlers: console, file, rotating file
- Performance metrics tracking with context management
- Automatic log rotation and cleanup
- Thread-safe implementation
- Integration with decorators for automatic logging

### Decorator Pattern Usage
The codebase extensively uses decorators in `decorators.py`:
- `@validate_params` - Type validation against function annotations
- `@time_logger` - Performance measurement with QuantLogger integration
- `@retry` - Retry logic with exponential backoff and jitter
- `@memoize` - LRU caching with TTL support
- `@rate_limiter` - Token bucket algorithm for API rate limiting
- `@deprecated` - Deprecation warnings with migration guidance
- All decorators integrate with QuantLogger for comprehensive logging

### Data Processing Patterns
- `data_batches()` in helper.py splits date ranges into 95-day chunks (API limit optimization)
- Uses both pandas and polars for data processing
- Symbol to ticker conversion integrates with FNOExpiry for proper formatting
- `check_last_modified()` utility for file timestamp validation

### Module Dependencies
- **helper.py** imports from market_contracts and sqlite_data_manager
- **sqlite_data_manager.py** imports from market_contracts
- **market_contracts.py** imports from quantlogger (no other internal dependencies)
- **decorators.py** imports from quantlogger (no other internal dependencies) 
- **quantlogger.py** is standalone (no internal dependencies)

## Testing Approach

Currently no test infrastructure exists. When implementing tests:
- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Mock database connections and external APIs
- Focus on contract ticker generation edge cases (holidays, expiries)
- Test decorator behavior thoroughly
- Test batch generation for API limits

## Important Notes

1. **Python 3.12+ required** - Uses modern Python features like union type hints (`|`)
2. **No existing test suite** - Testing infrastructure needs to be built from scratch
3. **Recent Updates** (as of latest commit):
   - Renamed `datetime_API.py` to `market_contracts.py` with complete refactor
   - Added comprehensive logging system via `quantlogger.py`
   - Enhanced decorators with QuantLogger integration
   - Improved type safety with Enums in market_contracts
4. **WIP Components**:
   - `sqlite_data_manager` methods need completion
   - Database migration from SQLite to TimeScaleDB under consideration
   - Helper module needs updates to work with new structure
5. **Branch Strategy** - Work on feature branches, merge to main
6. **Virtual Environment** - Always use the uv-managed .venv
7. **Hardcoded Paths** - Database paths in DBPaths are hardcoded to `/home/cheesecake/Downloads/Data`

## Common Pitfalls to Avoid

1. Don't assume SQLite will remain the database - code may migrate to TimeScaleDB
2. Contract ticker generation has complex logic - thoroughly test any modifications
3. Holiday lists in market_contracts need periodic updates (currently scrapes from Groww website)
4. Decorator stacking order matters - validate_params should typically be innermost
5. API batch size (95 days) is intentionally below 100-day limits to avoid broker API restrictions
6. Be careful with date formats - database uses "%Y-%m-%d %H:%M:%S" format
7. Symbol vs Ticker distinction - symbols are underlying names, tickers include expiry/strike info

## Future Roadmap

See `plan/new_features.md` for comprehensive feature planning including:
- Risk management and portfolio optimization modules
- Backtesting framework with event-driven architecture
- Real-time market data streaming and order management
- Technical indicators and options analytics
- Broker API integrations (Zerodha, Upstox, etc.)