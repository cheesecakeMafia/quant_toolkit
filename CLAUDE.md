# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quant Toolkit is a private library for quantitative finance projects. It provides tools for:
- Database interaction with time-series financial data (SQLite-based)
- Contract ticker generation for NSE/BSE derivatives (futures and options)
- Production-ready decorators for validation, timing, and logging
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

### Database Design (data_API.py)
- **Schema**: `datetime | open | high | low | close | volume | oi(optional)`
- Each security has its own table in SQLite
- `DataHandler` class provides the main interface
- `DBPaths` manages database file paths and symbol lists
- Note: Module marked as WIP, considering migration from SQLite to TimeScaleDB

### Contract Ticker Generation (datetime_API.py)
- `FNOExpiry` class generates contract tickers based on exchange formats:
  - Monthly futures: `{Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}FUT`
  - Monthly options: `{Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}{Strike}{Opt_Type}`
  - Weekly options: `{Ex}:{Ex_UnderlyingSymbol}{YY}{M}{dd}{Strike}{Opt_Type}`
- Handles holiday adjustments and expiry date calculations
- Options methods marked as requiring testing

### Decorator Pattern Usage
The codebase extensively uses decorators in `decorators.py`:
- `@validate_params` - Type validation against function annotations
- `@time_logger` - Performance measurement
- `@retry` - Retry logic with configurable attempts
- `@memoize` - Result caching
- `@rate_limiter` - API call rate limiting

### Data Processing Patterns
- `data_batches()` in helper.py splits date ranges into 95-day chunks (API limit optimization)
- Uses both pandas and polars for data processing
- Symbol to ticker conversion integrates with FNOExpiry for proper formatting

## Testing Approach

Currently, only a placeholder test.py exists. When implementing tests:
- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Mock database connections and external APIs
- Focus on contract ticker generation edge cases (holidays, expiries)
- Test decorator behavior thoroughly

## Important Notes

1. **Python 3.12+ required** - Uses modern Python features
2. **No existing test suite** - Testing infrastructure needs to be built
3. **WIP Components** - data_API considering database migration, options ticker generation needs testing
4. **Branch Strategy** - Work on `dev` branch, main branch for stable releases
5. **Virtual Environment** - Always use the uv-managed .venv

## Common Pitfalls to Avoid

1. Don't assume SQLite will remain the database - code may migrate to TimeScaleDB
2. Contract ticker generation has complex logic - thoroughly test any modifications
3. Holiday lists in datetime_API need periodic updates
4. Decorator stacking order matters - validate_params should typically be innermost
5. API batch size (95 days) is intentionally below 100-day limits