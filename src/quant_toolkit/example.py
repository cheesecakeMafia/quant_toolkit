#!/usr/bin/env python3
"""
Example usage of all major components in the quant_toolkit library.

This script demonstrates basic usage patterns for:
1. market_contracts - Contract ticker generation
2. sqlite_data_manager - Database operations
3. decorators - Function decorators
4. quantlogger - Logging system
5. helper - Utility functions
"""

from datetime import datetime, timedelta
import time
from pathlib import Path

# Import main components
from quant_toolkit import QuantLogger, ContractGenerator, MarketCalendar
from quant_toolkit.market_contracts import Exchange, OptionType, ContractType, ExpiryType
from quant_toolkit.decorators import (
    validate_params,
    time_logger,
    retry,
    memoize,
    rate_limiter,
    deprecated
)
from quant_toolkit.helper import data_batches, check_last_modified


# ============================================================================
# 1. QuantLogger - Advanced Logging System
# ============================================================================

def example_quantlogger():
    """Demonstrate QuantLogger usage."""
    print("\n" + "="*60)
    print("QUANTLOGGER EXAMPLE")
    print("="*60)
    
    # Get singleton logger instance
    logger = QuantLogger.get_logger("example_module")
    
    # Basic logging
    logger.info("Starting example demonstration")
    logger.debug("Debug information for development")
    logger.warning("This is a warning message")
    
    # Structured logging with extra fields
    logger.info(
        "Trade executed",
        extra={
            "symbol": "NIFTY",
            "quantity": 100,
            "price": 21500.50,
            "order_type": "MARKET"
        }
    )
    
    # Performance tracking context
    with logger.performance_context("data_processing"):
        # Simulate some work
        time.sleep(0.1)
        logger.info("Processing market data")
    
    # Log metrics
    logger.log_metric("portfolio_value", 1000000.00)
    logger.log_metric("daily_pnl", 15000.50)
    
    print("✓ QuantLogger demonstration complete")


# ============================================================================
# 2. Market Contracts - Contract Ticker Generation
# ============================================================================

def example_market_contracts():
    """Demonstrate market contract generation."""
    print("\n" + "="*60)
    print("MARKET CONTRACTS EXAMPLE")
    print("="*60)
    
    # Initialize contract generator
    generator = ContractGenerator()
    
    # Get current and next monthly expiry dates
    current_expiry = generator.get_monthly_expiry()
    next_expiry = generator.get_monthly_expiry(next_month=True)
    
    print(f"Current month expiry: {current_expiry}")
    print(f"Next month expiry: {next_expiry}")
    
    # Generate futures contract ticker
    future_ticker = generator.generate_contract(
        symbol="NIFTY",
        exchange=Exchange.NSE,
        contract_type=ContractType.FUTURE,
        expiry_type=ExpiryType.MONTHLY,
        expiry_date=current_expiry
    )
    print(f"\nMonthly Future: {future_ticker}")
    
    # Generate options contract ticker
    call_ticker = generator.generate_contract(
        symbol="BANKNIFTY",
        exchange=Exchange.NSE,
        contract_type=ContractType.OPTION,
        expiry_type=ExpiryType.WEEKLY,
        expiry_date=datetime.now() + timedelta(days=7),
        strike=50000,
        option_type=OptionType.CALL
    )
    print(f"Weekly Call Option: {call_ticker}")
    
    # Check if today is a trading day
    calendar = MarketCalendar()
    is_trading = calendar.is_trading_day(datetime.now())
    print(f"\nIs today a trading day? {is_trading}")
    
    # Get next trading day
    next_trading = calendar.get_next_trading_day(datetime.now())
    print(f"Next trading day: {next_trading}")
    
    print("✓ Market contracts demonstration complete")


# ============================================================================
# 3. Decorators - Function Enhancement
# ============================================================================

def example_decorators():
    """Demonstrate decorator usage."""
    print("\n" + "="*60)
    print("DECORATORS EXAMPLE")
    print("="*60)
    
    # Type validation decorator
    @validate_params
    def calculate_returns(price: float, quantity: int) -> float:
        """Calculate total returns."""
        return price * quantity
    
    # Performance timing decorator
    @time_logger
    def process_market_data():
        """Simulate data processing."""
        time.sleep(0.05)
        return "Processing complete"
    
    # Retry decorator for unreliable operations
    @retry(max_attempts=3, delay=0.1)
    def fetch_market_data():
        """Simulate API call that might fail."""
        import random
        if random.random() < 0.7:  # 70% chance of failure
            raise ConnectionError("API temporarily unavailable")
        return {"price": 100.50}
    
    # Caching decorator
    @memoize(ttl=60)
    def expensive_calculation(n: int) -> int:
        """Simulate expensive calculation."""
        time.sleep(0.1)  # Simulate computation
        return n * n
    
    # Rate limiting decorator
    @rate_limiter(calls=5, period=1.0)
    def api_call(endpoint: str):
        """Simulate rate-limited API call."""
        return f"Called {endpoint}"
    
    # Deprecation warning
    @deprecated(reason="Use calculate_returns instead", version="2.0.0")
    def old_calculation(price, qty):
        """Old function that's being phased out."""
        return price * qty
    
    # Test the decorated functions
    print("Testing @validate_params:")
    result = calculate_returns(100.5, 10)
    print(f"  Returns: {result}")
    
    print("\nTesting @time_logger:")
    process_market_data()
    
    print("\nTesting @memoize:")
    print(f"  First call: {expensive_calculation(5)}")
    print(f"  Second call (cached): {expensive_calculation(5)}")
    
    print("\nTesting @rate_limiter:")
    for i in range(3):
        print(f"  {api_call(f'/api/v1/data/{i}')}")
    
    print("\nTesting @deprecated:")
    old_calculation(100, 5)
    
    print("✓ Decorators demonstration complete")


# ============================================================================
# 4. SQLite Data Manager - Database Operations
# ============================================================================

def example_sqlite_data_manager():
    """Demonstrate database operations (mock example)."""
    print("\n" + "="*60)
    print("SQLITE DATA MANAGER EXAMPLE")
    print("="*60)
    
    # Note: This is a conceptual example since actual database requires setup
    print("SQLite Data Manager provides:")
    print("  - OHLCV data storage and retrieval")
    print("  - Context-managed database connections")
    print("  - Batch processing for large datasets")
    print("  - Schema: datetime | open | high | low | close | volume | oi")
    
    # Example schema
    example_data = {
        "datetime": "2025-01-06 09:15:00",
        "open": 21500.00,
        "high": 21550.00,
        "low": 21480.00,
        "close": 21520.00,
        "volume": 1000000,
        "oi": 500000  # Open Interest (optional)
    }
    
    print(f"\nExample OHLCV record:")
    for key, value in example_data.items():
        print(f"  {key}: {value}")
    
    print("\n✓ SQLite Data Manager concept demonstrated")


# ============================================================================
# 5. Helper Functions - Utility Operations
# ============================================================================

def example_helper_functions():
    """Demonstrate helper utility functions."""
    print("\n" + "="*60)
    print("HELPER FUNCTIONS EXAMPLE")
    print("="*60)
    
    # Data batching for API optimization
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    
    print(f"Splitting date range into API-friendly batches:")
    print(f"  Start: {start_date.date()}")
    print(f"  End: {end_date.date()}")
    
    batches = list(data_batches(start_date, end_date))
    print(f"\n  Generated {len(batches)} batches (95-day chunks):")
    for i, (batch_start, batch_end) in enumerate(batches[:3], 1):
        print(f"    Batch {i}: {batch_start.date()} to {batch_end.date()}")
    if len(batches) > 3:
        print(f"    ... and {len(batches) - 3} more batches")
    
    # File modification checking
    test_file = Path(__file__)
    if test_file.exists():
        days_old = check_last_modified(str(test_file))
        print(f"\nThis example file was last modified {days_old:.1f} days ago")
    
    print("\n✓ Helper functions demonstration complete")


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("QUANT TOOLKIT - COMPREHENSIVE EXAMPLE")
    print("="*60)
    print("\nThis example demonstrates the usage of all 5 core modules:")
    print("1. quantlogger - Advanced logging system")
    print("2. market_contracts - Contract ticker generation")
    print("3. decorators - Function enhancement")
    print("4. sqlite_data_manager - Database operations")
    print("5. helper - Utility functions")
    
    # Run each example
    example_quantlogger()
    example_market_contracts()
    example_decorators()
    example_sqlite_data_manager()
    example_helper_functions()
    
    print("\n" + "="*60)
    print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
    print("="*60)
    print("\nFor production use:")
    print("- Configure QuantLogger with appropriate handlers")
    print("- Set up database paths for SQLite Data Manager")
    print("- Update market holidays periodically")
    print("- Test thoroughly with real market data")
    print("- Monitor decorator performance impacts")


if __name__ == "__main__":
    main()