# Python Modernization Plan for quant_toolkit

## Overview
This document outlines opportunities to modernize the quant_toolkit codebase using Python 3.12+ features and modern Python idioms.

## 1. Type Hints Modernization

### Current State
The codebase uses older typing syntax with `Union` and `Optional` imports.

### Modernization Actions

#### Use Union Types with `|` Operator (Python 3.10+)
```python
# Current (data_API.py)
from typing import Union, Optional
def method(param: Union[int, str]) -> Optional[pd.DataFrame]:
    pass

# Modern
def method(param: int | str) -> pd.DataFrame | None:
    pass
```

#### Files to Update:
- `data_API.py`: Replace all `Union[x, y]` with `x | y`
- `datetime_API.py`: Update `Union[int, str]` to `int | str`
- `decorators.py`: Modernize all Union imports
- `helper.py`: Update type hints throughout

## 2. Match/Case Statements (Python 3.10+)

### Replace if/elif Chains

#### data_API.py Opportunities:
```python
# Current approach in get_security_data()
if start_date and end_date:
    query += " WHERE datetime BETWEEN ? AND ?"
elif start_date:
    query += " WHERE datetime >= ?"
elif end_date:
    query += " WHERE datetime <= ?"

# Modern approach
match (bool(start_date), bool(end_date)):
    case (True, True):
        query += " WHERE datetime BETWEEN ? AND ?"
    case (True, False):
        query += " WHERE datetime >= ?"
    case (False, True):
        query += " WHERE datetime <= ?"
    case (False, False):
        pass
```

#### helper.py Opportunities:
```python
# Current in check_last_modified()
if isinstance(time_diff_val, int):
    # handle int
elif isinstance(time_diff_val, date):
    # handle date
elif isinstance(time_diff_val, datetime):
    # handle datetime

# Modern
match time_diff_val:
    case int() as days:
        # handle int
    case date() as d:
        # handle date
    case datetime() as dt:
        # handle datetime
```

## 3. Dataclass Usage

### Convert Classes to Dataclasses

#### DBPaths Class
```python
# Current
class DBPaths:
    def __init__(self):
        self.stocks_data_path = data_dir / 'stocks.db'
        self.index_data_path = data_dir / 'index.db'
        # ... more paths

# Modern
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class DBPaths:
    data_dir: Path = field(default_factory=lambda: Path.home() / 'MarketData' / 'DBs')
    stocks_data_path: Path = field(init=False)
    index_data_path: Path = field(init=False)
    futures_data_path: Path = field(init=False)
    
    def __post_init__(self):
        self.stocks_data_path = self.data_dir / 'stocks.db'
        self.index_data_path = self.data_dir / 'index.db'
        self.futures_data_path = self.data_dir / 'futures.db'
```

## 4. Modern Path Handling

### Replace os.path with pathlib
```python
# Current
import os
file_path = os.path.join(directory, filename)
if os.path.exists(file_path):
    pass

# Modern
from pathlib import Path
file_path = Path(directory) / filename
if file_path.exists():
    pass
```

## 5. Context Managers for Database Operations

### Implement Proper Connection Management
```python
# Current approach
def get_security_data(self, security: str, ...):
    query = f"SELECT * FROM {security}"
    # ... execute query

# Modern approach with context manager
from contextlib import contextmanager

@contextmanager
def db_connection(self):
    conn = sqlite3.connect(self.database_path)
    try:
        yield conn
    finally:
        conn.close()

def get_security_data(self, security: str, ...):
    with self.db_connection() as conn:
        query = "SELECT * FROM ?"
        # Use parameterized queries
```

## 6. Modern Exception Handling

### Use Exception Groups (Python 3.11+)
```python
# For retry decorator
class RetryError(ExceptionGroup):
    """Group of exceptions from retry attempts"""
    pass

@retry(attempts=3)
def flaky_operation():
    errors = []
    for attempt in range(3):
        try:
            # operation
        except Exception as e:
            errors.append(e)
    if errors:
        raise RetryError("All retry attempts failed", errors)
```

## 7. Performance Optimizations

### Use Built-in Functions
```python
# Current (custom memoize decorator)
def memoize(func):
    cache = {}
    # ... implementation

# Modern
from functools import cache, lru_cache

@cache  # Unlimited cache
def expensive_computation(x):
    pass

@lru_cache(maxsize=128)  # Limited cache
def frequent_computation(x):
    pass
```

### Use Slots for Memory Efficiency
```python
# Add to frequently instantiated classes
class DataHandler:
    __slots__ = ['database_path', '_connection', '_cursor']
    
    def __init__(self, database_path: Path):
        self.database_path = database_path
```

## 8. Modern Python Idioms

### Walrus Operator (Python 3.8+)
```python
# Current
result = expensive_function()
if result:
    process(result)

# Modern
if result := expensive_function():
    process(result)
```

### F-strings Everywhere
```python
# Replace all .format() calls
# Current
"Found {} securities".format(count)

# Modern
f"Found {count} securities"
```

### Type Checking with isinstance
```python
# Current
if type(value) == int:
    pass

# Modern
if isinstance(value, int):
    pass
```

## 9. Enum Usage for Constants

```python
# Current
WEEKDAY_MAP = {
    0: "Monday",
    1: "Tuesday",
    # ...
}

# Modern
from enum import Enum, auto

class Weekday(Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
    
    @property
    def is_weekend(self):
        return self in (Weekday.SATURDAY, Weekday.SUNDAY)
```

## 10. Async/Await for I/O Operations

### Future Enhancement for Database Operations
```python
# Future implementation
import asyncio
import aiosqlite

class AsyncDataHandler:
    async def get_security_data(self, security: str) -> pd.DataFrame:
        async with aiosqlite.connect(self.database_path) as db:
            async with db.execute(query, params) as cursor:
                data = await cursor.fetchall()
        return pd.DataFrame(data)
```

## Implementation Priority

1. **Immediate** (Low Risk, High Impact):
   - Type hints modernization
   - F-string conversions
   - pathlib adoption
   - isinstance usage

2. **Short-term** (Medium Risk, High Impact):
   - Dataclass conversions
   - Context managers for databases
   - Built-in decorators (cache, lru_cache)

3. **Medium-term** (Higher Risk, Medium Impact):
   - Match/case statements
   - Exception groups
   - Enum usage
   - Slots for performance

4. **Long-term** (Requires Architecture Changes):
   - Async/await implementation
   - Full database abstraction layer

## Testing Considerations

Each modernization should be accompanied by:
1. Unit tests to ensure functionality remains unchanged
2. Performance benchmarks for optimization changes
3. Type checking with mypy
4. Backwards compatibility tests if needed

## Tooling Setup

Add to `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.ruff]
target-version = "py312"
select = ["E", "F", "UP", "B", "SIM", "I"]
```

This modernization will make the codebase more maintainable, performant, and aligned with current Python best practices.