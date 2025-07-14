# Software Engineering Best Practices for quant_toolkit

## Overview
This document outlines the software engineering improvements needed to transform quant_toolkit into a production-ready, maintainable library following industry best practices.

## 1. Testing Infrastructure

### Current State
- No unit tests exist
- Only an empty `test.py` file
- No test framework configured
- No coverage reporting

### Required Implementation

#### Test Structure
```
tests/
├── unit/
│   ├── test_data_api.py
│   ├── test_datetime_api.py
│   ├── test_decorators.py
│   └── test_helper.py
├── integration/
│   ├── test_database_operations.py
│   └── test_broker_integrations.py
├── fixtures/
│   ├── sample_data.py
│   └── mock_responses.py
└── conftest.py
```

#### Testing Framework Setup
```toml
# pyproject.toml additions
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = [
    "--cov=src/quant_toolkit",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]

[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.21",
    "pytest-mock>=3.10",
]
```

#### Example Test Implementation
```python
# tests/unit/test_data_api.py
import pytest
from unittest.mock import Mock, patch
from quant_toolkit.data_API import DataHandler

class TestDataHandler:
    @pytest.fixture
    def mock_db(self, tmp_path):
        """Create a temporary database for testing"""
        db_path = tmp_path / "test.db"
        return DataHandler(db_path)
    
    def test_get_available_securities(self, mock_db):
        """Test listing available securities"""
        # Test implementation
        
    @patch('sqlite3.connect')
    def test_database_connection_error(self, mock_connect):
        """Test handling of database connection errors"""
        mock_connect.side_effect = Exception("Connection failed")
        # Test error handling
```

### Testing Best Practices
1. **Test Coverage**: Minimum 80% coverage, aim for 90%+
2. **Test Isolation**: Each test should be independent
3. **Mock External Dependencies**: Database, API calls, file I/O
4. **Property-Based Testing**: For algorithmic functions
5. **Performance Tests**: For critical paths

## 2. Security Improvements

### Critical Security Issues

#### SQL Injection Vulnerabilities
```python
# VULNERABLE CODE (current)
def get_security_data(self, security: str):
    query = f"SELECT * FROM {security}"  # SQL Injection risk!
    
# SECURE CODE (improved)
def get_security_data(self, security: str):
    # Validate security name against whitelist
    if not self._is_valid_security(security):
        raise ValueError(f"Invalid security name: {security}")
    
    # Use parameterized queries where possible
    query = "SELECT * FROM securities WHERE symbol = ?"
    cursor.execute(query, (security,))
```

#### Input Validation Framework
```python
# validators.py
from typing import TypeVar, Callable
import re

T = TypeVar('T')

class Validator:
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate trading symbol format"""
        pattern = r'^[A-Z0-9_-]+$'
        if not re.match(pattern, symbol):
            raise ValueError(f"Invalid symbol format: {symbol}")
        return symbol
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> tuple:
        """Validate date range logic"""
        # Implementation
        
    @staticmethod
    def sanitize_sql_identifier(identifier: str) -> str:
        """Sanitize SQL identifiers"""
        # Remove or escape special characters
        return re.sub(r'[^a-zA-Z0-9_]', '', identifier)
```

#### Secure Configuration Management
```python
# config/settings.py
import os
from pathlib import Path
from typing import Optional
import json

class Settings:
    """Centralized configuration management"""
    
    def __init__(self, env: str = "development"):
        self.env = env
        self._load_config()
        self._load_secrets()
    
    def _load_config(self):
        """Load configuration from file"""
        config_path = Path(__file__).parent / f"{self.env}.json"
        with open(config_path) as f:
            self.config = json.load(f)
    
    def _load_secrets(self):
        """Load secrets from environment variables"""
        self.db_password = os.environ.get("DB_PASSWORD")
        self.api_key = os.environ.get("API_KEY")
        
    @property
    def database_url(self) -> str:
        """Build database URL with credentials"""
        return self.config["database"]["url"].format(
            password=self.db_password
        )
```

## 3. Error Handling & Logging

### Implement Structured Logging
```python
# logging_config.py
import logging
import logging.config
from pathlib import Path

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "logs/quant_toolkit.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "loggers": {
        "quant_toolkit": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        }
    }
}

def setup_logging():
    """Initialize logging configuration"""
    Path("logs").mkdir(exist_ok=True)
    logging.config.dictConfig(LOGGING_CONFIG)
```

### Custom Exception Hierarchy
```python
# exceptions.py
class QuantToolkitError(Exception):
    """Base exception for all quant_toolkit errors"""
    pass

class DataError(QuantToolkitError):
    """Raised when data operations fail"""
    pass

class ValidationError(QuantToolkitError):
    """Raised when validation fails"""
    pass

class BrokerConnectionError(QuantToolkitError):
    """Raised when broker connection fails"""
    pass

class InsufficientDataError(DataError):
    """Raised when not enough data is available"""
    pass
```

### Error Handling Patterns
```python
# Consistent error handling
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@contextmanager
def error_handler(operation: str, reraise: bool = True):
    """Centralized error handling context manager"""
    try:
        yield
    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        if reraise:
            raise
        
# Usage
def get_security_data(self, security: str):
    with error_handler(f"fetching data for {security}"):
        # Implementation
```

## 4. Code Organization & Architecture

### Repository Pattern for Data Access
```python
# repositories/base.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class BaseRepository(ABC):
    """Abstract base class for repositories"""
    
    @abstractmethod
    def find_by_id(self, id: str) -> Optional[Any]:
        """Find entity by ID"""
        pass
    
    @abstractmethod
    def find_all(self) -> List[Any]:
        """Find all entities"""
        pass
    
    @abstractmethod
    def save(self, entity: Any) -> None:
        """Save entity"""
        pass

# repositories/security_repository.py
class SecurityRepository(BaseRepository):
    """Repository for security data operations"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def find_by_symbol(self, symbol: str) -> Optional[Security]:
        """Find security by symbol"""
        # Implementation
```

### Dependency Injection
```python
# container.py
from typing import Dict, Type, Any

class DIContainer:
    """Simple dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
    
    def register(self, interface: Type, implementation: Any, singleton: bool = False):
        """Register a service"""
        if singleton:
            self._singletons[interface] = implementation
        else:
            self._services[interface] = implementation
    
    def resolve(self, interface: Type) -> Any:
        """Resolve a service"""
        if interface in self._singletons:
            return self._singletons[interface]
        if interface in self._services:
            return self._services[interface]()
        raise ValueError(f"Service {interface} not registered")

# Usage
container = DIContainer()
container.register(DatabaseConnection, SQLiteConnection, singleton=True)
container.register(SecurityRepository, SecurityRepositoryImpl)
```

## 5. CI/CD Pipeline

### GitHub Actions Workflow
```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install uv
      run: pip install uv
    
    - name: Install dependencies
      run: uv sync
    
    - name: Lint with ruff
      run: |
        uv run ruff check src/
        uv run ruff format --check src/
    
    - name: Type check with mypy
      run: uv run mypy src/
    
    - name: Test with pytest
      run: uv run pytest tests/ --cov=src/quant_toolkit --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
    
    - name: Security scan
      run: |
        pip install bandit
        bandit -r src/

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build package
      run: |
        pip install uv
        uv build
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: dist
        path: dist/
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.261
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
      
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## 6. Documentation Standards

### Docstring Format (Google Style)
```python
def calculate_returns(
    prices: pd.Series,
    method: str = "simple",
    annualize: bool = False
) -> pd.Series:
    """Calculate returns from price series.
    
    Args:
        prices: Series of prices indexed by date.
        method: Return calculation method ('simple' or 'log').
        annualize: Whether to annualize the returns.
        
    Returns:
        Series of returns with same index as prices (excluding first).
        
    Raises:
        ValueError: If method is not 'simple' or 'log'.
        TypeError: If prices is not a pandas Series.
        
    Examples:
        >>> prices = pd.Series([100, 110, 121], 
        ...                   index=pd.date_range('2023-01-01', periods=3))
        >>> returns = calculate_returns(prices)
        >>> print(returns)
        2023-01-02    0.10
        2023-01-03    0.10
        dtype: float64
    """
```

### API Documentation with Sphinx
```python
# docs/conf.py
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme',
]

# Auto-generate API docs
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
}
```

## 7. Development Environment

### Development Setup Script
```bash
#!/bin/bash
# scripts/setup_dev.sh

echo "Setting up development environment..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    pip install uv
fi

# Create virtual environment and install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Create necessary directories
mkdir -p logs tests/unit tests/integration docs

# Run initial checks
echo "Running initial checks..."
uv run ruff check src/
uv run mypy src/

echo "Development environment ready!"
```

### Makefile for Common Tasks
```makefile
# Makefile
.PHONY: install test lint format docs clean

install:
	uv sync

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=src/quant_toolkit --cov-report=html

lint:
	uv run ruff check src/
	uv run mypy src/

format:
	uv run ruff format src/

docs:
	cd docs && uv run make html

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

all: lint test
```

## Implementation Priority

### Phase 1: Security & Testing (Week 1-2)
1. Fix SQL injection vulnerabilities
2. Set up pytest and write initial tests
3. Add input validation
4. Configure logging

### Phase 2: Code Quality (Week 3-4)
1. Set up CI/CD pipeline
2. Add pre-commit hooks
3. Refactor for better architecture
4. Add comprehensive error handling

### Phase 3: Documentation (Week 5)
1. Add proper docstrings
2. Set up Sphinx documentation
3. Create example notebooks
4. Write developer guide

### Phase 4: Advanced Features (Week 6+)
1. Implement dependency injection
2. Add performance monitoring
3. Create integration test suite
4. Set up automated releases

## Success Criteria

1. **Test Coverage**: >80% coverage achieved
2. **Security**: All SQL injection vulnerabilities fixed
3. **Documentation**: 100% public API documented
4. **CI/CD**: All commits pass automated checks
5. **Code Quality**: Zero linting errors, type checking passes
6. **Error Handling**: No unhandled exceptions in production

This comprehensive improvement plan will transform quant_toolkit into a professional, production-ready library that follows software engineering best practices.