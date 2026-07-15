"""Sample data fixtures for testing."""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from pathlib import Path
import json


class SampleOHLCVData:
    """Sample OHLCV data for testing."""

    @staticmethod
    def generate_daily_ohlcv(
        start_date: str = "2024-01-01",
        periods: int = 100,
        base_price: float = 100.0,
        volatility: float = 0.02
    ) -> pd.DataFrame:
        """Generate sample daily OHLCV data."""
        dates = pd.date_range(start_date, periods=periods, freq='D')
        
        # Generate price data with random walk
        np.random.seed(42)  # For reproducible test data
        price_changes = np.random.normal(0, volatility, periods)
        prices = [base_price]
        
        for change in price_changes[1:]:
            prices.append(prices[-1] * (1 + change))
        
        # Generate OHLCV from prices
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            high = price * (1 + abs(np.random.normal(0, 0.01)))
            low = price * (1 - abs(np.random.normal(0, 0.01)))
            open_price = prices[i-1] if i > 0 else price
            close_price = price
            volume = np.random.randint(10000, 100000)
            oi = np.random.randint(1000, 10000)
            
            data.append({
                'datetime': date.strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'oi': oi
            })
        
        return pd.DataFrame(data)

    @staticmethod
    def generate_intraday_ohlcv(
        date: str = "2024-01-01",
        freq: str = "1min",
        base_price: float = 100.0
    ) -> pd.DataFrame:
        """Generate sample intraday OHLCV data."""
        start_time = datetime.strptime(f"{date} 09:15:00", '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(f"{date} 15:30:00", '%Y-%m-%d %H:%M:%S')
        
        dates = pd.date_range(start_time, end_time, freq=freq)
        periods = len(dates)
        
        # Generate price data
        np.random.seed(42)
        price_changes = np.random.normal(0, 0.001, periods)
        prices = [base_price]
        
        for change in price_changes[1:]:
            prices.append(prices[-1] * (1 + change))
        
        # Generate OHLCV
        data = []
        for i, (timestamp, price) in enumerate(zip(dates, prices)):
            high = price * (1 + abs(np.random.normal(0, 0.002)))
            low = price * (1 - abs(np.random.normal(0, 0.002)))
            open_price = prices[i-1] if i > 0 else price
            close_price = price
            volume = np.random.randint(100, 10000)
            oi = np.random.randint(100, 5000)
            
            data.append({
                'datetime': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'oi': oi
            })
        
        return pd.DataFrame(data)


class SampleContractData:
    """Sample contract data for testing."""

    @staticmethod
    def get_sample_symbols() -> list[str]:
        """Get sample symbol list."""
        return [
            "NIFTY", "BANKNIFTY", "FINNIFTY",
            "RELIANCE", "TCS", "INFY", "HDFC",
            "ICICIBANK", "KOTAKBANK", "SBIN"
        ]

    @staticmethod
    def get_sample_futures_tickers() -> list[str]:
        """Get sample futures tickers."""
        return [
            "NSE:NIFTY24JANFUT",
            "NSE:BANKNIFTY24JANFUT",
            "NSE:RELIANCE24JANFUT",
            "NSE:TCS24JANFUT"
        ]

    @staticmethod
    def get_sample_options_tickers() -> dict[str, list[str]]:
        """Get sample options tickers."""
        return {
            "monthly": [
                "NSE:NIFTY24JAN21000CE",
                "NSE:NIFTY24JAN21000PE",
                "NSE:BANKNIFTY24JAN45000CE",
                "NSE:BANKNIFTY24JAN45000PE"
            ],
            "weekly": [
                "NSE:NIFTY241121000CE",
                "NSE:NIFTY241121000PE",
                "NSE:BANKNIFTY24O1145000CE",
                "NSE:BANKNIFTY24O1145000PE"
            ]
        }

    @staticmethod
    def get_expiry_dates() -> dict[str, date]:
        """Get sample expiry dates."""
        return {
            "current_month": date(2024, 1, 25),
            "next_month": date(2024, 2, 29),
            "weekly_current": date(2024, 1, 11),
            "weekly_next": date(2024, 1, 18)
        }


class SampleHolidayData:
    """Sample holiday data for testing."""

    @staticmethod
    def get_sample_holidays_2024() -> list[date]:
        """Get sample holidays for 2024."""
        return [
            date(2024, 1, 26),  # Republic Day
            date(2024, 3, 8),   # Holi
            date(2024, 3, 29),  # Good Friday
            date(2024, 4, 17),  # Ram Navami
            date(2024, 8, 15),  # Independence Day
            date(2024, 10, 2),  # Gandhi Jayanti
            date(2024, 11, 1),  # Diwali
            date(2024, 12, 25)  # Christmas
        ]

    @staticmethod
    def get_sample_holidays_json() -> str:
        """Get sample holidays as JSON string."""
        holidays = SampleHolidayData.get_sample_holidays_2024()
        holiday_strings = [h.strftime('%Y-%m-%d') for h in holidays]
        return json.dumps({"holidays": holiday_strings})


class SampleErrorData:
    """Sample error scenarios for testing."""

    @staticmethod
    def get_invalid_ohlcv_data() -> list[dict]:
        """Get invalid OHLCV data for error testing."""
        return [
            # Missing required fields
            {'datetime': '2024-01-01', 'open': 100},
            # Invalid data types
            {'datetime': '2024-01-01', 'open': 'invalid', 'high': 105, 'low': 95, 'close': 102, 'volume': 1000},
            # Negative volume
            {'datetime': '2024-01-01', 'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': -1000},
            # High < Low
            {'datetime': '2024-01-01', 'open': 100, 'high': 95, 'low': 105, 'close': 102, 'volume': 1000}
        ]

    @staticmethod
    def get_invalid_symbols() -> list[str]:
        """Get invalid symbols for error testing."""
        return [
            "",  # Empty string
            "INVALID_SYMBOL_TOO_LONG",  # Too long
            "123INVALID",  # Starts with number
            "INVALID@SYMBOL"  # Special characters
        ]

    @staticmethod
    def get_invalid_dates() -> list[str]:
        """Get invalid dates for error testing."""
        return [
            "2024-13-01",  # Invalid month
            "2024-02-30",  # Invalid day
            "invalid-date",  # Invalid format
            "2024/01/01",  # Wrong format
            ""  # Empty string
        ]