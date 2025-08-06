"""
SQLite Data Manager for Market Data Storage

This module provides a comprehensive interface for storing and retrieving time-series
OHLCV (Open, High, Low, Close, Volume) data in SQLite databases. It supports both
pandas and polars DataFrames and includes connection pooling, transaction support,
and comprehensive logging.

Database Schema:
    | datetime(index) | open | high | low | close | volume | oi(optional) |

Classes:
    DataHandler: Main interface for database operations with connection pooling
    DBPaths: Configuration manager for database paths and symbol lists
    ConnectionPool: Internal connection pool manager

Usage:
    from quant_toolkit.sqlite_data_manager import DataHandler, DBPaths

    # Initialize handler with database path
    handler = DataHandler(db_path)

    # Get data for a symbol
    data = handler.get_security_data("NIFTY", start_datetime="2024-01-01")

    # Batch operations with transactions
    with handler.transaction() as conn:
        handler.delete_security_from_date("NIFTY", conn=conn, from_datetime=30)
        handler.inject_data("NIFTY", new_data, conn=conn)
"""

from quant_toolkit.market_contracts import MarketContracts
from quant_toolkit.quantlogger import QuantLogger

import pandas as pd
import polars as pl
import sqlite3
import datetime
import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from contextlib import contextmanager
from typing import Optional, Union, List
from collections import deque
from threading import Lock

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Internal imports


# Configure module logger
logger = logging.getLogger(__name__)
QuantLogger.set_global_path(Path(os.getenv("LOG_PATH", "logs")))


class ConnectionPool:
    """
    Thread-safe SQLite connection pool manager.

    Manages a pool of database connections for efficient resource utilization
    and prevents connection exhaustion in multi-threaded environments.

    Attributes:
        db_path: Path to SQLite database file
        pool_size: Maximum number of connections in pool
        timeout: Connection timeout in seconds
    """

    def __init__(self, db_path: Path, pool_size: int = 5, timeout: float = 30.0):
        """
        Initialize connection pool.

        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of connections (default: 5)
            timeout: Connection timeout in seconds (default: 30.0)
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: deque = deque()
        self._lock = Lock()
        self._created_connections = 0

    def _create_connection(self) -> sqlite3.Connection:
        """
        Create a new database connection with optimized settings.

        Returns:
            Configured SQLite connection
        """
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        # Optimize for performance
        conn.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging
        conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
        conn.execute("PRAGMA cache_size=10000")  # Larger cache
        conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a connection from the pool or create a new one.

        Returns:
            SQLite connection from pool

        Raises:
            RuntimeError: If pool is exhausted and max connections reached
        """
        with self._lock:
            # Try to get from pool
            if self._pool:
                conn = self._pool.popleft()
                # Verify connection is still valid
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    # Connection is dead, create a new one
                    self._created_connections -= 1

            # Create new connection if under limit
            if self._created_connections < self.pool_size:
                conn = self._create_connection()
                self._created_connections += 1
                return conn

            raise RuntimeError(f"Connection pool exhausted (size: {self.pool_size})")

    def return_connection(self, conn: sqlite3.Connection):
        """
        Return a connection to the pool.

        Args:
            conn: Connection to return to pool
        """
        with self._lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
            else:
                conn.close()
                self._created_connections -= 1

    def close_all(self):
        """Close all connections in the pool."""
        with self._lock:
            while self._pool:
                conn = self._pool.popleft()
                conn.close()
            self._created_connections = 0


class DataHandler:
    """
    Main interface for SQLite market data operations.

    Provides methods for storing, retrieving, and managing time-series OHLCV data
    with support for both pandas and polars DataFrames, connection pooling,
    and transaction management.

    Attributes:
        db_path: Path to SQLite database file
        pool: Connection pool manager
        market_contracts: MarketContracts instance for ticker generation
    """

    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize DataHandler with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.pool = ConnectionPool(
            self.db_path,
            pool_size=int(os.getenv("DB_POOL_SIZE", 5)),
            timeout=float(os.getenv("DB_TIMEOUT", 30.0)),
        )
        self.market_contracts = MarketContracts()

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"DataHandler initialized with database: {self.db_path}")

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Provides atomic operations with automatic commit/rollback.

        Yields:
            SQLite connection with transaction started

        Example:
            with handler.transaction() as conn:
                handler.delete_old_data(symbol, conn=conn)
                handler.inject_new_data(symbol, data, conn=conn)
                # Automatically commits on success, rolls back on error
        """
        conn = self.pool.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise
        finally:
            self.pool.return_connection(conn)

    @contextmanager
    def _db_cursor(self, conn: Optional[sqlite3.Connection] = None):
        """
        Context manager for database cursor operations.

        Args:
            conn: Optional connection to use, creates new if None

        Yields:
            Database cursor
        """
        if conn is None:
            conn = self.pool.get_connection()
            cursor = conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()
                self.pool.return_connection(conn)
        else:
            cursor = conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    @QuantLogger(log_time=True, log_args=True)
    def database_exists(self) -> bool:
        """
        Check if the database file exists.

        Returns:
            True if database file exists, False otherwise
        """
        return self.db_path.is_file()

    def _symbol_exists(
        self, symbol: str, conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """
        Check if a symbol table exists in the database.

        Args:
            symbol: Symbol to check for
            conn: Optional database connection

        Returns:
            True if symbol table exists, False otherwise
        """
        if not self.database_exists():
            return False

        try:
            with self._db_cursor(conn) as cursor:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (symbol,),
                )
                result = cursor.fetchone()
                return result is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking symbol existence: {e}")
            return False

    def _security_earliest_datetime(
        self,
        symbol: str,
        conn: Optional[sqlite3.Connection] = None,
        default_start: datetime.date = datetime.date(2017, 1, 1),
    ) -> datetime.date:
        """
        Get the earliest datetime available for a security.

        Args:
            symbol: Security symbol
            conn: Optional database connection
            default_start: Default date if symbol doesn't exist

        Returns:
            Earliest date for the security
        """
        if self._symbol_exists(symbol, conn):
            with self._db_cursor(conn) as cursor:
                cursor.execute(
                    f"SELECT datetime FROM '{symbol}' ORDER BY datetime LIMIT 1"
                )
                result = cursor.fetchone()
                if result:
                    return datetime.datetime.strptime(
                        result[0], "%Y-%m-%d %H:%M:%S"
                    ).date()

        logger.warning(f"Symbol {symbol} not found, returning default date")
        return default_start

    def _security_latest_datetime(
        self, symbol: str, conn: Optional[sqlite3.Connection] = None
    ) -> datetime.date:
        """
        Get the latest datetime available for a security.

        Args:
            symbol: Security symbol
            conn: Optional database connection

        Returns:
            Latest date for the security
        """
        if self._symbol_exists(symbol, conn):
            with self._db_cursor(conn) as cursor:
                cursor.execute(
                    f"SELECT datetime FROM '{symbol}' ORDER BY datetime DESC LIMIT 1"
                )
                result = cursor.fetchone()
                if result:
                    return datetime.datetime.strptime(
                        result[0], "%Y-%m-%d %H:%M:%S"
                    ).date()

        logger.warning(f"Symbol {symbol} not found, returning today's date")
        return datetime.date.today()

    def _convert_symbol_to_ticker(
        self, symbol: str, dt: datetime.date = None, exchange: str = None
    ) -> str:
        """
        Convert a symbol to a ticker for futures contracts.

        Args:
            symbol: Base symbol (e.g., "NIFTY_FUT" or "NIFTY_FUT2")
            dt: Reference date for expiry calculation
            exchange: Exchange ("NSE" or "BSE"), defaults to environment variable

        Returns:
            Full ticker with expiry (e.g., "NSE:NIFTY24OCTFUT")

        Note:
            - Suffix "2" indicates next month futures
            - No suffix indicates current month futures
            - Non-futures symbols are returned unchanged
            - Options conversion not currently supported
        """
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        dt = dt or datetime.date.today()
        exchange = exchange or os.getenv("DEFAULT_EXCHANGE", "NSE")

        if "FUT" in symbol:
            base_symbol = symbol.replace("_FUT", "").replace("2", "")

            if "2" in symbol:
                # Next month futures
                return self.market_contracts.future(
                    exchange, base_symbol, "next_month", dt
                )
            else:
                # Current month futures
                return self.market_contracts.future(
                    exchange, base_symbol, "current_month", dt
                )

        # Return non-futures symbols unchanged
        return symbol

    @QuantLogger(log_time=True)
    def get_available_securities(
        self, conn: Optional[sqlite3.Connection] = None
    ) -> List[str]:
        """
        Get list of all available securities in the database.

        Args:
            conn: Optional database connection

        Returns:
            List of symbol names
        """
        if not self.database_exists():
            return []

        with self._db_cursor(conn) as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            symbols = [row[0] for row in cursor.fetchall()]
            return symbols

    @QuantLogger(log_time=True, log_args=True)
    def get_security_data(
        self,
        symbol: str,
        start_datetime: Union[int, str, datetime.date, None] = None,
        end_datetime: Optional[Union[str, datetime.date]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve security data for a given symbol.

        Args:
            symbol: Security symbol to retrieve
            start_datetime: Start date/time for data:
                - int: Number of days before latest date
                - str: Date string in "YYYY-MM-DD" format
                - datetime.date: Date object
                - None: Retrieve all available data
            end_datetime: Optional end date (str or datetime.date)
            conn: Optional database connection

        Returns:
            DataFrame with OHLCV data or None if symbol doesn't exist

        Example:
            # Get last 30 days of data
            data = handler.get_security_data("NIFTY", start_datetime=30)

            # Get data from specific date
            data = handler.get_security_data("BANKNIFTY", start_datetime="2024-01-01")
        """
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        if not self._symbol_exists(symbol, conn):
            logger.warning(f"Symbol {symbol} not found in database")
            return None

        # Process start_datetime
        if isinstance(start_datetime, int):
            start_datetime = self._security_latest_datetime(
                symbol, conn
            ) - datetime.timedelta(days=start_datetime)
        elif isinstance(start_datetime, str):
            start_datetime = datetime.datetime.strptime(
                start_datetime, "%Y-%m-%d"
            ).date()
        elif start_datetime is None:
            start_datetime = self._security_earliest_datetime(symbol, conn)

        # Process end_datetime
        if isinstance(end_datetime, str):
            end_datetime = datetime.datetime.strptime(end_datetime, "%Y-%m-%d").date()

        # Build query with parameterized values
        if end_datetime:
            query = f"SELECT * FROM '{symbol}' WHERE datetime >= ? AND datetime <= ? ORDER BY datetime"
            params = (
                start_datetime.strftime("%Y-%m-%d"),
                end_datetime.strftime("%Y-%m-%d"),
            )
        else:
            query = f"SELECT * FROM '{symbol}' WHERE datetime >= ? ORDER BY datetime"
            params = (start_datetime.strftime("%Y-%m-%d"),)

        # Execute query
        if conn:
            df = pd.read_sql_query(query, conn, params=params)
        else:
            with self.transaction() as conn:
                df = pd.read_sql_query(query, conn, params=params)

        # Convert datetime column
        df["datetime"] = pd.to_datetime(df["datetime"], format="%Y-%m-%d %H:%M:%S")

        return df

    @QuantLogger(log_time=True, log_args=True)
    def delete_security(self, symbol: str, conn: Optional[sqlite3.Connection] = None):
        """
        Delete entire table for a security symbol.

        Args:
            symbol: Security symbol to delete
            conn: Optional database connection

        Raises:
            ValueError: If symbol is empty
        """
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        if not self._symbol_exists(symbol, conn):
            logger.warning(f"Symbol {symbol} doesn't exist, nothing to delete")
            return

        def _delete(connection):
            with self._db_cursor(connection) as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS '{symbol}'")
                logger.info(f"Deleted table for symbol {symbol}")

        if conn:
            _delete(conn)
        else:
            with self.transaction() as conn:
                _delete(conn)

    @QuantLogger(log_time=True, log_args=True)
    def delete_security_from_date(
        self,
        symbol: str,
        from_datetime: Union[int, str, datetime.date] = 252,
        conn: Optional[sqlite3.Connection] = None,
    ):
        """
        Delete security data from a specific date onwards.

        Args:
            symbol: Security symbol
            from_datetime: Date from which to delete:
                - int: Number of days before latest date (default: 252)
                - str: Date string in "YYYY-MM-DD" format
                - datetime.date: Date object
            conn: Optional database connection

        Raises:
            ValueError: If symbol is empty or from_datetime is invalid
        """
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        if not from_datetime:
            raise ValueError("from_datetime cannot be empty")

        if not self._symbol_exists(symbol, conn):
            logger.warning(f"Symbol {symbol} doesn't exist, nothing to delete")
            return

        # Process from_datetime
        if isinstance(from_datetime, int):
            from_datetime = self._security_latest_datetime(
                symbol, conn
            ) - datetime.timedelta(days=from_datetime)
        elif isinstance(from_datetime, str):
            from_datetime = datetime.datetime.strptime(from_datetime, "%Y-%m-%d").date()

        def _delete(connection):
            with self._db_cursor(connection) as cursor:
                cursor.execute(
                    f"DELETE FROM '{symbol}' WHERE datetime >= ?",
                    (from_datetime.strftime("%Y-%m-%d"),),
                )
                deleted_count = cursor.rowcount
                logger.info(
                    f"Deleted {deleted_count} rows for {symbol} from {from_datetime}"
                )

        if conn:
            _delete(conn)
        else:
            with self.transaction() as conn:
                _delete(conn)

    @QuantLogger(log_time=True, log_args=True, log_result=True)
    def inject_data(
        self,
        symbol: str,
        data: Union[pd.DataFrame, pl.DataFrame],
        conn: Optional[sqlite3.Connection] = None,
        if_exists: str = "append",
    ):
        """
        Inject OHLCV data into the database for a given symbol.

        Args:
            symbol: Security symbol
            data: DataFrame with OHLCV data (pandas or polars)
            conn: Optional database connection for transaction
            if_exists: How to behave if table exists:
                - "append": Append data to existing table (default)
                - "replace": Replace entire table
                - "fail": Raise error if table exists

        Raises:
            ValueError: If data validation fails
            TypeError: If data is not pandas or polars DataFrame

        Note:
            Expected DataFrame columns:
            - Required: datetime, open, high, low, close, volume
            - Optional: oi (open interest)

        Example:
            # Single injection
            handler.inject_data("NIFTY", df)

            # Batch injection with transaction
            with handler.transaction() as conn:
                handler.inject_data("NIFTY", df1, conn=conn)
                handler.inject_data("BANKNIFTY", df2, conn=conn)
        """
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        # Validate and convert data
        if isinstance(data, pl.DataFrame):
            # Convert polars to pandas
            data = data.to_pandas()
        elif not isinstance(data, pd.DataFrame):
            raise TypeError(
                f"Data must be pandas or polars DataFrame, got {type(data)}"
            )

        if data.empty:
            logger.warning(f"Empty DataFrame provided for {symbol}, skipping injection")
            return

        # Validate required columns
        required_columns = {"datetime", "open", "high", "low", "close", "volume"}
        missing_columns = required_columns - set(data.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Ensure datetime column is properly formatted
        if not pd.api.types.is_datetime64_any_dtype(data["datetime"]):
            data["datetime"] = pd.to_datetime(data["datetime"])

        # Format datetime as string for SQLite
        data = data.copy()
        data["datetime"] = data["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

        # Validate OHLC relationships
        invalid_ohlc = (
            (data["high"] < data["low"])
            | (data["high"] < data["open"])
            | (data["high"] < data["close"])
            | (data["low"] > data["open"])
            | (data["low"] > data["close"])
        )

        if invalid_ohlc.any():
            invalid_count = invalid_ohlc.sum()
            logger.warning(
                f"Found {invalid_count} rows with invalid OHLC relationships"
            )
            # Optionally fix or remove invalid rows
            data = data[~invalid_ohlc]

        # Check for duplicates
        duplicates = data.duplicated(subset=["datetime"], keep="last")
        if duplicates.any():
            dup_count = duplicates.sum()
            logger.warning(f"Removing {dup_count} duplicate datetime entries")
            data = data[~duplicates]

        # Sort by datetime
        data = data.sort_values("datetime")

        def _inject(connection):
            # Use pandas to_sql for efficient insertion
            data.to_sql(
                symbol,
                connection,
                if_exists=if_exists,
                index=False,
                method="multi",  # Batch insert for performance
            )
            logger.info(f"Injected {len(data)} rows for {symbol}")

        if conn:
            _inject(conn)
        else:
            with self.transaction() as conn:
                _inject(conn)

    @QuantLogger(log_time=True, log_args=True, log_result=True)
    def check_db_integrity(
        self,
        min_years: Union[int, float] = 3,
        log_csv: bool = False,
        csv_path: Optional[Path] = None,
        delete_stale: bool = False,
        conn: Optional[sqlite3.Connection] = None,
    ) -> pd.DataFrame:
        """
        Check database integrity and identify stale/incomplete data.

        Args:
            min_years: Minimum years of data required for a symbol
            log_csv: Whether to save results to CSV file
            csv_path: Path for CSV output (auto-generated if None)
            delete_stale: Whether to delete symbols with insufficient data
            conn: Optional database connection

        Returns:
            DataFrame with integrity check results containing:
            - symbol: Security symbol
            - start_date: Earliest data date
            - end_date: Latest data date
            - days_of_data: Total days of data
            - is_stale: Whether data is stale
            - missing_recent: Days missing from recent data

        Example:
            # Check integrity and save report
            report = handler.check_db_integrity(min_years=2, log_csv=True)

            # Check and delete stale symbols
            report = handler.check_db_integrity(min_years=3, delete_stale=True)
        """
        if not self.database_exists():
            logger.warning("Database doesn't exist, returning empty report")
            return pd.DataFrame()

        symbols = self.get_available_securities(conn)
        if not symbols:
            logger.warning("No symbols found in database")
            return pd.DataFrame()

        results = []
        today = datetime.date.today()
        min_date = today - datetime.timedelta(days=365 * min_years)

        for symbol in symbols:
            try:
                start_date = self._security_earliest_datetime(symbol, conn)
                end_date = self._security_latest_datetime(symbol, conn)

                days_of_data = (end_date - start_date).days
                is_stale = start_date > min_date or end_date < (
                    today - datetime.timedelta(days=5)
                )
                missing_recent = (today - end_date).days

                results.append(
                    {
                        "symbol": symbol,
                        "start_date": start_date,
                        "end_date": end_date,
                        "days_of_data": days_of_data,
                        "is_stale": is_stale,
                        "missing_recent": missing_recent,
                    }
                )

                if delete_stale and is_stale:
                    logger.info(f"Deleting stale symbol: {symbol}")
                    self.delete_security(symbol, conn)

            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")
                results.append(
                    {
                        "symbol": symbol,
                        "start_date": None,
                        "end_date": None,
                        "days_of_data": 0,
                        "is_stale": True,
                        "missing_recent": -1,
                    }
                )

        report_df = pd.DataFrame(results)

        # Sort by staleness and missing data
        report_df = report_df.sort_values(
            ["is_stale", "missing_recent"], ascending=[False, False]
        )

        # Log statistics
        stale_count = report_df["is_stale"].sum()
        total_count = len(report_df)
        logger.info(
            f"Integrity check complete: {stale_count}/{total_count} symbols are stale"
        )

        # Save to CSV if requested
        if log_csv:
            if csv_path is None:
                csv_path = (
                    Path(os.getenv("LOG_PATH", "logs"))
                    / f"integrity_report_{today}.csv"
                )
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            report_df.to_csv(csv_path, index=False)
            logger.info(f"Integrity report saved to {csv_path}")

        return report_df

    def __del__(self):
        """Cleanup connection pool on deletion."""
        if hasattr(self, "pool"):
            self.pool.close_all()


@dataclass
class DBPaths:
    """
    Configuration manager for database paths and symbol lists.

    Reads configuration from environment variables and provides
    paths to databases and symbol CSV files.

    Attributes:
        data_dir: Base directory for all data files
        index_db_path: Path to index database
        futures_db_path: Path to futures database
        stocks_db_path: Path to stocks database
    """

    data_dir: Path = field(init=False)
    index_db_path: Path = field(init=False)
    futures_db_path: Path = field(init=False)
    stocks_db_path: Path = field(init=False)

    def __post_init__(self):
        """
        Initialize paths from environment variables.

        Reads from .env file or environment variables:
        - DATA_DIR: Base directory for databases
        - STOCKS_CSV_PATH: Path to stocks symbol list
        - INDEX_CSV_PATH: Path to index symbol list
        - FUTURES_CSV_PATH: Path to futures symbol list
        """
        # Get base data directory from environment
        data_dir_str = os.getenv("DATA_DIR")
        if not data_dir_str:
            raise ValueError(
                "DATA_DIR environment variable not set. Please configure .env file."
            )

        self.data_dir = Path(data_dir_str)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Set database paths
        self.index_db_path = self.data_dir / "index" / "index_data.db"
        self.futures_db_path = self.data_dir / "futures" / "futures_data.db"
        self.stocks_db_path = self.data_dir / "stocks" / "stocks_data.db"

        # Ensure database directories exist
        for db_path in [self.index_db_path, self.futures_db_path, self.stocks_db_path]:
            db_path.parent.mkdir(parents=True, exist_ok=True)

    @QuantLogger(log_time=True)
    def get_stocks_symbols(self) -> List[str]:
        """
        Get list of stock symbols from database or CSV file.

        Returns:
            List of stock symbols

        Raises:
            FileNotFoundError: If neither database nor CSV file exists
        """
        # Try to get from database first
        if self.stocks_db_path.is_file():
            handler = DataHandler(self.stocks_db_path)
            symbols = handler.get_available_securities()
            if symbols:
                return symbols

        # Fall back to CSV file
        csv_path = os.getenv("STOCKS_CSV_PATH")
        if not csv_path:
            raise FileNotFoundError(
                "STOCKS_CSV_PATH not configured and no database found"
            )

        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Stocks CSV file not found: {csv_file}")

        df = pd.read_csv(csv_file)
        return df["Ticker"].tolist()

    @QuantLogger(log_time=True)
    def get_index_symbols(self) -> List[str]:
        """
        Get list of index symbols from database or CSV file.

        Returns:
            List of index symbols

        Raises:
            FileNotFoundError: If neither database nor CSV file exists
        """
        # Try to get from database first
        if self.index_db_path.is_file():
            handler = DataHandler(self.index_db_path)
            symbols = handler.get_available_securities()
            if symbols:
                return symbols

        # Fall back to CSV file
        csv_path = os.getenv("INDEX_CSV_PATH")
        if not csv_path:
            raise FileNotFoundError(
                "INDEX_CSV_PATH not configured and no database found"
            )

        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Index CSV file not found: {csv_file}")

        df = pd.read_csv(csv_file)
        return df["Ticker"].tolist()

    @QuantLogger(log_time=True)
    def get_futures_symbols(self) -> List[str]:
        """
        Get list of futures symbols from database or CSV file.

        Returns:
            List of futures symbols

        Raises:
            FileNotFoundError: If neither database nor CSV file exists
        """
        # Try to get from database first
        if self.futures_db_path.is_file():
            handler = DataHandler(self.futures_db_path)
            symbols = handler.get_available_securities()
            if symbols:
                return symbols

        # Fall back to CSV file
        csv_path = os.getenv("FUTURES_CSV_PATH")
        if not csv_path:
            raise FileNotFoundError(
                "FUTURES_CSV_PATH not configured and no database found"
            )

        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Futures CSV file not found: {csv_file}")

        df = pd.read_csv(csv_file)
        return df["Ticker"].tolist()


if __name__ == "__main__":
    """Example usage and testing."""

    # Load environment variables
    load_dotenv()

    # Initialize paths
    paths = DBPaths()

    # Test with index database
    handler = DataHandler(paths.index_db_path)

    # Get available symbols
    symbols = handler.get_available_securities()
    print(f"Available symbols: {symbols[:5] if symbols else 'None'}")

    # Test ticker conversion
    if symbols:
        test_symbol = "NIFTY_FUT"
        test_date = datetime.date(2025, 1, 31)
        ticker = handler._convert_symbol_to_ticker(test_symbol, test_date)
        print(f"Ticker for {test_symbol} on {test_date}: {ticker}")

    # Check database integrity
    if handler.database_exists():
        report = handler.check_db_integrity(min_years=2)
        print(f"\nIntegrity Report:\n{report.head()}")
