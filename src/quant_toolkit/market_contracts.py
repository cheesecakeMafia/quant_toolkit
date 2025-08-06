"""
Market Contracts Module - Indian Derivatives Market Contract Generation

This module handles contract ticker generation for Indian derivatives markets (NSE/BSE).

Expiry Rules:
- Weekly Expiry: 
  * NSE: Every Thursday (Options only)
  * BSE: Every Tuesday (Options only)
  
- Monthly Expiry:
  * NSE: Last Thursday of month (Options + Futures)
  * BSE: Last Tuesday of month (Options + Futures)
  
- Holiday Adjustment: If expiry falls on holiday, moves to previous working day

Contract Formats:
- Monthly Futures: {Ex}:{Symbol}{YY}{MMM}FUT
- Monthly Options: {Ex}:{Symbol}{YY}{MMM}{Strike}{Type}
- Weekly Options: {Ex}:{Symbol}{YY}{M}{DD}{Strike}{Type}
"""

import datetime
import calendar
import pandas as pd
from enum import Enum, auto
from typing import Optional, Literal, Tuple
from pathlib import Path
import os
from functools import lru_cache
from dataclasses import dataclass


class Exchange(Enum):
    """Supported exchanges for derivatives trading."""
    NSE = "NSE"
    BSE = "BSE"
    
    @property
    def expiry_day(self) -> str:
        """Get the standard expiry day for this exchange."""
        return "Thursday" if self == Exchange.NSE else "Tuesday"


class OptionType(Enum):
    """Option types for derivatives."""
    CE = "CE"  # Call European
    PE = "PE"  # Put European


class ContractType(Enum):
    """Contract types for derivatives."""
    FUT = "FUT"
    OPT = "OPT"


class ExpiryType(Enum):
    """Expiry types for contracts."""
    WEEKLY = auto()
    MONTHLY = auto()


@dataclass
class ContractDetails:
    """Details for a derivative contract."""
    exchange: Exchange
    symbol: str
    expiry_date: datetime.date
    contract_type: ContractType
    expiry_type: ExpiryType
    strike: Optional[int] = None
    option_type: Optional[OptionType] = None
    
    def __post_init__(self):
        """Validate contract details."""
        if self.contract_type == ContractType.OPT:
            if self.strike is None or self.option_type is None:
                raise ValueError("Options require strike and option_type")
        if self.contract_type == ContractType.FUT and self.expiry_type == ExpiryType.WEEKLY:
            raise ValueError("Futures don't have weekly expiry")


class MarketConfig:
    """Configuration for market contracts module."""
    
    # Holiday data sources
    HOLIDAY_URL = "https://groww.in/p/nse-holidays"
    HOLIDAY_CSV_PATH = os.getenv(
        "HOLIDAY_CSV_PATH", 
        str(Path.home() / "Downloads" / "fyers" / "src" / "fyers" / "utils")
    )
    
    # Strike price multiples
    STRIKE_MULTIPLES = {
        "NIFTY": 50,
        "BANKNIFTY": 100,
        "FINNIFTY": 50,
        "MIDCPNIFTY": 25,
        "SENSEX": 100,
        "BANKEX": 100,
    }
    
    # Weekly month encoding for ticker format
    WEEKLY_MONTH_MAP = {
        1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
        7: "7", 8: "8", 9: "9", 10: "O", 11: "N", 12: "D"
    }
    
    @classmethod
    def get_holiday_csv_path(cls, year: int) -> Path:
        """Get the path for holiday CSV file."""
        return Path(cls.HOLIDAY_CSV_PATH) / f"holidays_{year}.csv"
    
    @classmethod
    def get_strike_multiple(cls, symbol: str) -> int:
        """Get strike multiple for a symbol."""
        symbol_upper = symbol.upper()
        
        # Check for exact matches first (handle BANKNIFTY before NIFTY)
        if "BANKNIFTY" in symbol_upper:
            return cls.STRIKE_MULTIPLES["BANKNIFTY"]
        elif "BANKEX" in symbol_upper:
            return cls.STRIKE_MULTIPLES["BANKEX"]
        
        # Then check other symbols
        for key, multiple in cls.STRIKE_MULTIPLES.items():
            if key in symbol_upper and key not in ["BANKNIFTY", "BANKEX"]:
                return multiple
        return 100  # Default


class MarketCalendar:
    """Handles market calendar operations including holidays and expiries."""
    
    def __init__(self):
        self._holiday_cache: Optional[list[datetime.date]] = None
        self._cache_date: Optional[datetime.date] = None
    
    @lru_cache(maxsize=32)
    def _get_holiday_list(self, year: int) -> list[datetime.date]:
        """
        Get list of holidays for a specific year with caching.
        
        Args:
            year: Year to fetch holidays for
            
        Returns:
            List of holiday dates
        """
        today = datetime.date.today()
        
        # Return cached if available and current
        if self._holiday_cache and self._cache_date == today:
            return [h for h in self._holiday_cache if h.year == year]
        
        try:
            # Try fetching from web
            df = pd.read_html(MarketConfig.HOLIDAY_URL, header=0)[0]
            holiday_list = df["Date"].apply(
                lambda x: datetime.datetime.strptime(x, "%B %d, %Y").date()
            ).to_list()
        except Exception as e:
            # Fallback to CSV
            try:
                csv_path = MarketConfig.get_holiday_csv_path(year)
                df = pd.read_csv(csv_path, index_col=0)
                holiday_list = df["str_date"].apply(
                    lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").date()
                ).to_list()
            except FileNotFoundError:
                print(f"Warning: Could not fetch holiday list - {e}")
                holiday_list = []
        
        self._holiday_cache = holiday_list
        self._cache_date = today
        return [h for h in holiday_list if h.year == year]
    
    def is_holiday(self, date: datetime.date) -> bool:
        """Check if a date is a holiday."""
        holidays = self._get_holiday_list(date.year)
        return date in holidays
    
    def is_weekend(self, date: datetime.date) -> bool:
        """Check if a date is a weekend."""
        return date.weekday() > 4  # Saturday = 5, Sunday = 6
    
    def is_trading_day(self, date: datetime.date) -> bool:
        """Check if a date is a trading day."""
        return not (self.is_weekend(date) or self.is_holiday(date))
    
    def adjust_for_holiday(self, date: datetime.date) -> datetime.date:
        """
        Adjust date to previous working day if it falls on holiday/weekend.
        
        Args:
            date: Date to adjust
            
        Returns:
            Adjusted date (moves backward if holiday/weekend)
        """
        while not self.is_trading_day(date):
            date = date - datetime.timedelta(days=1)
        return date
    
    def get_expiry_day_of_week(self, exchange: Exchange) -> int:
        """Get the weekday number for exchange expiry (0=Monday, 6=Sunday)."""
        return 3 if exchange == Exchange.NSE else 1  # Thursday=3, Tuesday=1
    
    def find_current_week_expiry(
        self, 
        today: datetime.date, 
        exchange: Exchange
    ) -> datetime.date:
        """
        Find current week's expiry date for given exchange.
        
        Args:
            today: Reference date
            exchange: NSE or BSE
            
        Returns:
            Current week's expiry date (adjusted for holidays)
        """
        target_weekday = self.get_expiry_day_of_week(exchange)
        
        # Calculate days until target weekday
        days_ahead = target_weekday - today.weekday()
        if days_ahead < 0:  # Target day already passed this week
            days_ahead += 7
        
        expiry = today + datetime.timedelta(days=days_ahead)
        
        # If expiry has passed, get next week's expiry
        if expiry < today:
            expiry = expiry + datetime.timedelta(days=7)
        
        # Adjust for holidays
        return self.adjust_for_holiday(expiry)
    
    def find_next_week_expiry(
        self, 
        today: datetime.date, 
        exchange: Exchange
    ) -> datetime.date:
        """
        Find next week's expiry date for given exchange.
        
        Args:
            today: Reference date
            exchange: NSE or BSE
            
        Returns:
            Next week's expiry date (adjusted for holidays)
        """
        current_expiry = self.find_current_week_expiry(today, exchange)
        next_expiry = current_expiry + datetime.timedelta(days=7)
        return self.adjust_for_holiday(next_expiry)
    
    def find_last_weekday_of_month(
        self, 
        year: int, 
        month: int, 
        weekday: int
    ) -> datetime.date:
        """
        Find the last occurrence of a weekday in a month.
        
        Args:
            year: Year
            month: Month (1-12)
            weekday: Weekday (0=Monday, 6=Sunday)
            
        Returns:
            Date of last occurrence
        """
        month_cal = calendar.monthcalendar(year, month)
        
        # Check last week, if 0 then check second-to-last week
        last_occurrence = month_cal[-1][weekday]
        if last_occurrence == 0:
            last_occurrence = month_cal[-2][weekday]
        
        return datetime.date(year, month, last_occurrence)
    
    def find_current_month_expiry(
        self, 
        today: datetime.date, 
        exchange: Exchange
    ) -> datetime.date:
        """
        Find current month's expiry date for given exchange.
        
        Args:
            today: Reference date
            exchange: NSE or BSE
            
        Returns:
            Current month's expiry date (adjusted for holidays)
        """
        target_weekday = self.get_expiry_day_of_week(exchange)
        
        # Get last occurrence in current month
        last_day = self.find_last_weekday_of_month(
            today.year, today.month, target_weekday
        )
        
        # If it has passed, get next month's expiry
        if last_day < today:
            if today.month == 12:
                last_day = self.find_last_weekday_of_month(
                    today.year + 1, 1, target_weekday
                )
            else:
                last_day = self.find_last_weekday_of_month(
                    today.year, today.month + 1, target_weekday
                )
        
        # Adjust for holidays
        return self.adjust_for_holiday(last_day)
    
    def find_next_month_expiry(
        self, 
        today: datetime.date, 
        exchange: Exchange
    ) -> datetime.date:
        """
        Find next month's expiry date for given exchange.
        
        Args:
            today: Reference date
            exchange: NSE or BSE
            
        Returns:
            Next month's expiry date (adjusted for holidays)
        """
        current_expiry = self.find_current_month_expiry(today, exchange)
        
        # Get the month after current expiry
        if current_expiry.month == 12:
            next_year = current_expiry.year + 1
            next_month = 1
        else:
            next_year = current_expiry.year
            next_month = current_expiry.month + 1
        
        target_weekday = self.get_expiry_day_of_week(exchange)
        last_day = self.find_last_weekday_of_month(
            next_year, next_month, target_weekday
        )
        
        # Adjust for holidays
        return self.adjust_for_holiday(last_day)


class ContractGenerator:
    """Generates derivative contract tickers."""
    
    def __init__(self):
        self.calendar = MarketCalendar()
    
    def _adjust_reference_date(self, date: datetime.date) -> datetime.date:
        """
        Adjust reference date to next trading day if it's a holiday/weekend.
        
        This ensures that when calculating expiries from a non-trading day,
        we use the next trading day as reference for more logical results.
        
        Args:
            date: Input date (possibly a holiday/weekend)
            
        Returns:
            Next trading day if input is holiday/weekend, otherwise same date
        """
        while not self.calendar.is_trading_day(date):
            date = date + datetime.timedelta(days=1)
        return date
    
    @staticmethod
    def validate_inputs(
        symbol: str,
        strike: Optional[int] = None,
        option_type: Optional[str] = None,
        contract_type: ContractType = ContractType.OPT
    ) -> Tuple[Optional[int], Optional[OptionType]]:
        """
        Validate and normalize inputs.
        
        Returns:
            Tuple of (validated_strike, validated_option_type)
        """
        if contract_type == ContractType.OPT:
            if strike is None or option_type is None:
                raise ValueError("Options require strike and option_type")
            
            # Validate strike
            multiple = MarketConfig.get_strike_multiple(symbol)
            if strike % multiple != 0:
                raise ValueError(
                    f"{symbol} strike must be multiple of {multiple}, got {strike}"
                )
            
            # Validate option type
            opt_upper = option_type.upper()
            if opt_upper not in ["CE", "PE"]:
                raise ValueError(f"Invalid option type: {option_type}")
            
            return strike, OptionType[opt_upper]
        
        return None, None
    
    def generate_ticker(self, details: ContractDetails) -> str:
        """
        Generate contract ticker from details.
        
        Args:
            details: Contract details
            
        Returns:
            Formatted ticker string
        """
        year_str = str(details.expiry_date.year)[-2:]
        month_abbr = calendar.month_abbr[details.expiry_date.month].upper()
        
        if details.contract_type == ContractType.FUT:
            # Monthly futures: NSE:NIFTY24OCTFUT
            return f"{details.exchange.value}:{details.symbol}{year_str}{month_abbr}FUT"
        
        elif details.expiry_type == ExpiryType.MONTHLY:
            # Monthly options: NSE:NIFTY24OCT20000CE
            return (
                f"{details.exchange.value}:{details.symbol}"
                f"{year_str}{month_abbr}{details.strike}{details.option_type.value}"
            )
        
        else:  # Weekly options
            # Weekly options: NSE:NIFTY24O0820000CE
            month_code = MarketConfig.WEEKLY_MONTH_MAP[details.expiry_date.month]
            day_str = str(details.expiry_date.day).zfill(2)
            return (
                f"{details.exchange.value}:{details.symbol}"
                f"{year_str}{month_code}{day_str}{details.strike}{details.option_type.value}"
            )
    
    # Current Week Options
    def current_week_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None
    ) -> str:
        """Generate current week option ticker."""
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday
        strike, opt_type = self.validate_inputs(symbol, strike, option_type)
        
        expiry = self.calendar.find_current_week_expiry(today, exchange)
        
        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.OPT,
            expiry_type=ExpiryType.WEEKLY,
            strike=strike,
            option_type=opt_type
        )
        
        return self.generate_ticker(details)
    
    # Next Week Options
    def next_week_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None
    ) -> str:
        """Generate next week option ticker."""
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday
        strike, opt_type = self.validate_inputs(symbol, strike, option_type)
        
        expiry = self.calendar.find_next_week_expiry(today, exchange)
        
        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.OPT,
            expiry_type=ExpiryType.WEEKLY,
            strike=strike,
            option_type=opt_type
        )
        
        return self.generate_ticker(details)
    
    # Current Month Options
    def current_month_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None
    ) -> str:
        """Generate current month option ticker."""
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday
        strike, opt_type = self.validate_inputs(symbol, strike, option_type)
        
        expiry = self.calendar.find_current_month_expiry(today, exchange)
        
        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.OPT,
            expiry_type=ExpiryType.MONTHLY,
            strike=strike,
            option_type=opt_type
        )
        
        return self.generate_ticker(details)
    
    # Next Month Options
    def next_month_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None
    ) -> str:
        """Generate next month option ticker."""
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday
        strike, opt_type = self.validate_inputs(symbol, strike, option_type)
        
        expiry = self.calendar.find_next_month_expiry(today, exchange)
        
        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.OPT,
            expiry_type=ExpiryType.MONTHLY,
            strike=strike,
            option_type=opt_type
        )
        
        return self.generate_ticker(details)
    
    # Current Month Futures
    def current_month_future(
        self,
        exchange: Exchange,
        symbol: str,
        today: Optional[datetime.date] = None
    ) -> str:
        """Generate current month futures ticker."""
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday
        
        expiry = self.calendar.find_current_month_expiry(today, exchange)
        
        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.FUT,
            expiry_type=ExpiryType.MONTHLY
        )
        
        return self.generate_ticker(details)
    
    # Next Month Futures
    def next_month_future(
        self,
        exchange: Exchange,
        symbol: str,
        today: Optional[datetime.date] = None
    ) -> str:
        """Generate next month futures ticker."""
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday
        
        expiry = self.calendar.find_next_month_expiry(today, exchange)
        
        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.FUT,
            expiry_type=ExpiryType.MONTHLY
        )
        
        return self.generate_ticker(details)


# Convenience functions for backward compatibility
def get_contract_generator() -> ContractGenerator:
    """Get a contract generator instance."""
    return ContractGenerator()