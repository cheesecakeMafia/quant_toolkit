"""Database fixtures for testing."""

import sqlite3
import tempfile
import shutil
from pathlib import Path
from contextlib import contextmanager
import pytest
import pandas as pd

from .sample_data import SampleOHLCVData


class TestDatabase:
    """Test database management utilities."""

    def __init__(self, db_path: Path):
        """Initialize test database."""
        self.db_path = db_path
        self.connection = None

    @contextmanager
    def get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def create_sample_table(self, table_name: str, with_oi: bool = True):
        """Create sample OHLCV table."""
        schema = '''
        CREATE TABLE IF NOT EXISTS {} (
            datetime TEXT PRIMARY KEY,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL{}
        )
        '''.format(table_name, ',\n            oi INTEGER' if with_oi else '')
        
        with self.get_connection() as conn:
            conn.execute(schema)
            conn.commit()

    def insert_sample_data(self, table_name: str, data: pd.DataFrame):
        """Insert sample data into table."""
        with self.get_connection() as conn:
            data.to_sql(table_name, conn, if_exists='append', index=False)
            conn.commit()

    def create_populated_table(
        self,
        table_name: str,
        periods: int = 100,
        with_oi: bool = True,
        start_date: str = "2024-01-01"
    ):
        """Create and populate table with sample data."""
        self.create_sample_table(table_name, with_oi)
        sample_data = SampleOHLCVData.generate_daily_ohlcv(
            start_date=start_date,
            periods=periods
        )
        if not with_oi:
            sample_data = sample_data.drop('oi', axis=1)
        
        self.insert_sample_data(table_name, sample_data)

    def get_table_row_count(self, table_name: str) -> int:
        """Get row count for table."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]

    def get_table_schema(self, table_name: str) -> list[tuple]:
        """Get table schema information."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            return cursor.fetchall()

    def drop_table(self, table_name: str):
        """Drop table if exists."""
        with self.get_connection() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()

    def cleanup(self):
        """Clean up database file."""
        if self.db_path.exists():
            self.db_path.unlink()


@pytest.fixture
def temp_database():
    """Create temporary test database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    test_db = TestDatabase(db_path)
    
    yield test_db
    
    test_db.cleanup()
    shutil.rmtree(temp_dir)


@pytest.fixture
def populated_database():
    """Create temporary database with sample data."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    test_db = TestDatabase(db_path)
    
    # Create sample tables with data
    test_db.create_populated_table("NIFTY", periods=100)
    test_db.create_populated_table("RELIANCE", periods=150)
    test_db.create_populated_table("TCS", periods=75, with_oi=False)
    
    yield test_db
    
    test_db.cleanup()
    shutil.rmtree(temp_dir)


@pytest.fixture
def multiple_timeframe_database():
    """Create database with multiple timeframe data."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    test_db = TestDatabase(db_path)
    
    # Create daily data
    test_db.create_populated_table("NIFTY_DAILY", periods=365, start_date="2023-01-01")
    
    # Create intraday data
    test_db.create_sample_table("NIFTY_1MIN")
    intraday_data = SampleOHLCVData.generate_intraday_ohlcv("2024-01-01")
    test_db.insert_sample_data("NIFTY_1MIN", intraday_data)
    
    yield test_db
    
    test_db.cleanup()
    shutil.rmtree(temp_dir)


@pytest.fixture
def corrupted_database():
    """Create database with corrupted/invalid data for error testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    test_db = TestDatabase(db_path)
    
    # Create table with some invalid data
    test_db.create_sample_table("CORRUPTED_DATA")
    
    # Insert valid data first
    valid_data = SampleOHLCVData.generate_daily_ohlcv(periods=50)
    test_db.insert_sample_data("CORRUPTED_DATA", valid_data)
    
    # Insert some problematic data directly via SQL
    with test_db.get_connection() as conn:
        # Insert duplicate datetime
        conn.execute('''
        INSERT INTO CORRUPTED_DATA 
        (datetime, open, high, low, close, volume, oi)
        VALUES ('2024-01-01 00:00:00', 100, 105, 95, 102, 1000, 500)
        ''')
        
        # Insert invalid OHLC relationships (high < low)
        conn.execute('''
        INSERT INTO CORRUPTED_DATA 
        (datetime, open, high, low, close, volume, oi)
        VALUES ('2024-12-31 00:00:00', 100, 95, 105, 102, 1000, 500)
        ''')
        
        conn.commit()
    
    yield test_db
    
    test_db.cleanup()
    shutil.rmtree(temp_dir)