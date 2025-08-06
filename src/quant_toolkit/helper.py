"""Helper functions for data processing, symbol conversion, and file utilities.

This module provides utility functions for:
- Splitting date ranges into API-friendly batches
- Converting symbols to fully qualified contract tickers
- Checking file modification timestamps

These functions are designed to be imported and used across the quant_toolkit
library and in external projects.
"""

import datetime
from quant_toolkit.market_contracts import MarketContracts
from quant_toolkit.sqlite_data_manager import DBPaths
from pathlib import Path
# Type hints use Python 3.10+ union operator | for cleaner syntax


def data_batches(
    start_date: datetime.date = datetime.date(2017, 1, 1),
    end_date: datetime.date = datetime.date.today() - datetime.timedelta(1),
    batch_size: int = 95,
) -> list[dict]:
    """Split a date range into smaller batches for API optimization.
    
    Divides a large date range into smaller chunks to comply with API limitations
    that restrict data fetching to ~100 days per request. Default batch size is 95
    days to provide a buffer below the 100-day limit.
    
    Args:
        start_date: Starting date for the range. Defaults to Jan 1, 2017.
        end_date: Ending date for the range. Defaults to yesterday.
        batch_size: Maximum days per batch. Defaults to 95 (API limit buffer).
    
    Returns:
        List of dictionaries with 'start' and 'end' keys containing date strings
        in 'YYYY-MM-DD' format. Each dict represents one batch.
    
    Example:
        >>> batches = data_batches(
        ...     datetime.date(2024, 1, 1),
        ...     datetime.date(2024, 6, 30),
        ...     batch_size=30
        ... )
        >>> print(batches[0])
        {'start': '2024-01-01', 'end': '2024-01-31'}
    """

    batches = []

    while end_date - start_date > datetime.timedelta(days=batch_size):
        batches.append(
            {
                "start": datetime.datetime.strftime(start_date, "%Y-%m-%d"),
                "end": datetime.datetime.strftime(
                    start_date + datetime.timedelta(days=batch_size), "%Y-%m-%d"
                ),
            }
        )
        start_date = start_date + datetime.timedelta(days=batch_size + 1)

    batches.append(
        {
            "start": datetime.datetime.strftime(start_date, "%Y-%m-%d"),
            "end": datetime.datetime.strftime(end_date, "%Y-%m-%d"),
        }
    )

    return batches


def convert_symbol_to_ticker(
    symbol: str, dt: datetime.date = datetime.date.today(), exchange: str = "NSE"
) -> str:
    """Convert a symbol to a fully qualified futures contract ticker.
    
    Transforms generic futures symbols into exchange-specific tickers with
    proper expiry dates. Supports current month and next month futures.
    
    Args:
        symbol: Base symbol to convert. Futures symbols should contain "_FUT".
                "_FUT" suffix = current month future
                "_FUT2" suffix = next month future
        dt: Reference date for expiry calculation. Defaults to today.
        exchange: Target exchange ("NSE" or "BSE"). Defaults to "NSE".
    
    Returns:
        For futures: Full ticker with expiry (e.g., "NSE:NIFTY24DECFUT")
        For non-futures: Original symbol unchanged
    
    Raises:
        AssertionError: If symbol is empty or None
    
    Example:
        >>> convert_symbol_to_ticker("NIFTY_FUT", datetime.date(2024, 12, 15))
        'NSE:NIFTY24DECFUT'
        >>> convert_symbol_to_ticker("BANKNIFTY_FUT2", datetime.date(2024, 12, 15))
        'NSE:BANKNIFTY25JANFUT'
    """
    assert symbol, print("You need to pass a symbol to convert it to a ticker.")
    mc = MarketContracts()

    if "FUT" in symbol:
        base_symbol = symbol.replace("_FUT", "").replace("2", "")
        if "2" in symbol:
            return mc.future(exchange, base_symbol, "next_month", dt)
        return mc.future(exchange, base_symbol, "current_month", dt)
    else:
        return symbol


def check_last_modified(
    file_path: str | Path, days: int | datetime.date | datetime.datetime
) -> bool:
    """Check if a file was last modified before a specified time threshold.
    
    Determines whether a file's modification timestamp is older than a given
    number of days ago or before a specific date/datetime.
    
    Args:
        file_path: Path to the file to check. Can be string or Path object.
        days: Time threshold for comparison. Can be:
              - int: Number of days ago from now
              - datetime.date: Specific date to compare against
              - datetime.datetime: Specific datetime to compare against
    
    Returns:
        True if file modification time is BEFORE (older than) the threshold,
        False otherwise.
    
    Raises:
        FileNotFoundError: If the specified file doesn't exist
        TypeError: If days parameter is not int, date, or datetime
    
    Example:
        >>> # Check if file is older than 7 days
        >>> check_last_modified("/path/to/file.txt", 7)
        True  # File was modified more than 7 days ago
        
        >>> # Check if file is older than specific date
        >>> check_last_modified("/path/to/file.txt", datetime.date(2024, 1, 1))
        False  # File was modified after Jan 1, 2024
    """
    # Convert string path to Path object if necessary
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Get file's last modification time as datetime
    file_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)

    # Handle different types of 'days' parameter
    if isinstance(days, int):
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
        return file_time < cutoff_time
    elif isinstance(days, datetime.date) and not isinstance(days, datetime.datetime):
        # Convert file_time to date for comparison with date object
        return file_time.date() < days
    elif isinstance(days, datetime.datetime):
        return file_time < days
    else:
        raise TypeError(
            "days parameter must be either an int, a datetime.date or a datetime.datetime object"
        )


def file_mod_recently(
    file_path: str | Path, days: int | datetime.date | datetime.datetime
) -> bool:
    """Check if a file was modified recently (after a specified threshold).
    
    Determines whether a file's modification timestamp is newer than a given
    number of days ago or after a specific date/datetime. This is the inverse
    of check_last_modified().
    
    Args:
        file_path: Path to the file to check. Can be string or Path object.
        days: Time threshold for comparison. Can be:
              - int: Number of days ago from now
              - datetime.date: Specific date to compare against
              - datetime.datetime: Specific datetime to compare against
    
    Returns:
        True if file modification time is AFTER (newer than) the threshold,
        False otherwise.
    
    Raises:
        FileNotFoundError: If the specified file doesn't exist
        TypeError: If days parameter is not int, date, or datetime
    
    Example:
        >>> # Check if file was modified within last 7 days
        >>> file_mod_recently("/path/to/file.txt", 7)
        True  # File was modified within the last 7 days
        
        >>> # Check if file was modified after specific date
        >>> file_mod_recently("/path/to/file.txt", datetime.date(2024, 1, 1))
        True  # File was modified after Jan 1, 2024
    """
    # Convert string path to Path object if necessary
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Get file's last modification time as datetime
    file_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)

    # Handle different types of 'days' parameter
    if isinstance(days, int):
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
        return file_time > cutoff_time
    elif isinstance(days, datetime.date) and not isinstance(days, datetime.datetime):
        # Convert file_time to date for comparison with date object
        return file_time.date() > days
    elif isinstance(days, datetime.datetime):
        return file_time > days
    else:
        raise TypeError(
            "days parameter must be either an int, a datetime.date or a datetime.datetime object"
        )


def main():
    """Example usage demonstrating helper functions.
    
    Shows how to:
    - Convert index symbols to tickers
    - Check file modification times
    """
    obj = DBPaths().get_index_symbols()
    for sym in obj:
        print(
            f"For symbol {sym}, ticker is {convert_symbol_to_ticker(sym, dt=datetime.date(2025, 1, 30))}"
        )
    days = datetime.datetime(2025, 6, 30)
    file_path = r"/home/cheesecake/Downloads/quant/quant_toolkit/pyproject.toml"
    print(file_mod_recently(file_path, days))
    file_path = (
        r"/home/cheesecake/Downloads/quant/quant_toolkit/src/quant_toolkit/helper.py"
    )
    print(file_mod_recently(file_path, days))


if __name__ == "__main__":
    main()
