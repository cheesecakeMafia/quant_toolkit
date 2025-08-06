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
from typing import Optional, Literal, Tuple  # noqa: F401
from pathlib import Path
import os
from functools import lru_cache
from dataclasses import dataclass


class Exchange(Enum):
    """Supported exchanges for derivatives trading in India.
    
    This enum defines the two major derivatives exchanges in India:
    - NSE (National Stock Exchange): Weekly and monthly expiry on Thursdays
    - BSE (Bombay Stock Exchange): Weekly and monthly expiry on Tuesdays
    
    Attributes:
        NSE: National Stock Exchange with Thursday expiry
        BSE: Bombay Stock Exchange with Tuesday expiry
    """

    NSE = "NSE"
    BSE = "BSE"

    @property
    def expiry_day(self) -> str:
        """Get the standard expiry day for this exchange.
        
        Returns:
            str: "Thursday" for NSE, "Tuesday" for BSE
        """
        return "Thursday" if self == Exchange.NSE else "Tuesday"


class OptionType(Enum):
    """Option types for derivatives in Indian markets.
    
    Both NSE and BSE support European-style options which can only be
    exercised on the expiry date.
    
    Attributes:
        CE: Call European - Right to buy the underlying at strike price
        PE: Put European - Right to sell the underlying at strike price
    """

    CE = "CE"  # Call European
    PE = "PE"  # Put European


class ContractType(Enum):
    """Contract types for derivatives trading.
    
    Attributes:
        FUT: Futures contracts - Obligation to buy/sell at expiry
        OPT: Options contracts - Right (not obligation) to buy/sell
    """

    FUT = "FUT"
    OPT = "OPT"


class ExpiryType(Enum):
    """Expiry types for derivative contracts.
    
    Indian derivatives markets support both weekly and monthly expiries:
    - WEEKLY: Options only, expire every week on exchange-specific day
    - MONTHLY: Both futures and options, expire on last occurrence of exchange day
    
    Attributes:
        WEEKLY: Weekly expiry (options only)
        MONTHLY: Monthly expiry (futures and options)
    """

    WEEKLY = auto()
    MONTHLY = auto()


@dataclass
class ContractDetails:
    """Complete specification for a derivative contract.
    
    This dataclass encapsulates all the information needed to uniquely
    identify a derivative contract in Indian markets.
    
    Attributes:
        exchange: Trading exchange (NSE/BSE)
        symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
        expiry_date: Contract expiry date
        contract_type: Type of contract (FUT/OPT)
        expiry_type: Expiry frequency (WEEKLY/MONTHLY)
        strike: Strike price for options (required for options)
        option_type: Call/Put type for options (required for options)
    
    Raises:
        ValueError: If options are missing strike price or option type
        ValueError: If attempting to create weekly futures (not supported)
    
    Example:
        >>> details = ContractDetails(
        ...     exchange=Exchange.NSE,
        ...     symbol="NIFTY",
        ...     expiry_date=datetime.date(2024, 12, 26),
        ...     contract_type=ContractType.OPT,
        ...     expiry_type=ExpiryType.WEEKLY,
        ...     strike=25000,
        ...     option_type=OptionType.CE
        ... )
    """

    exchange: Exchange
    symbol: str
    expiry_date: datetime.date
    contract_type: ContractType
    expiry_type: ExpiryType
    strike: Optional[int] = None
    option_type: Optional[OptionType] = None

    def __post_init__(self):
        """Validate contract details after initialization.
        
        Raises:
            ValueError: If options are missing required fields
            ValueError: If attempting to create weekly futures
        """
        if self.contract_type == ContractType.OPT:
            if self.strike is None or self.option_type is None:
                raise ValueError("Options require strike and option_type")
        if (
            self.contract_type == ContractType.FUT
            and self.expiry_type == ExpiryType.WEEKLY
        ):
            raise ValueError("Futures don't have weekly expiry")


class MarketConfig:
    """Configuration constants and utilities for market contracts module.
    
    This class centralizes all configuration data including:
    - Holiday data sources (web scraping URL and local CSV fallback)
    - Strike price multiples for different underlying symbols
    - Weekly month encoding for ticker generation
    
    The class provides methods to retrieve symbol-specific configurations
    and file paths for holiday data.
    
    Attributes:
        HOLIDAY_URL: Web source for holiday data (Groww NSE holidays page)
        HOLIDAY_CSV_PATH: Local fallback directory for holiday CSV files
        STRIKE_MULTIPLES: Dictionary mapping symbols to their strike intervals
        WEEKLY_MONTH_MAP: Month-to-character mapping for weekly option tickers
    """

    # Holiday data sources
    HOLIDAY_URL = "https://groww.in/p/nse-holidays"
    HOLIDAY_CSV_PATH = os.getenv(
        "HOLIDAY_CSV_PATH",
        str(Path.home() / "Downloads" / "fyers" / "src" / "fyers" / "utils"),
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
        1: "1",
        2: "2",
        3: "3",
        4: "4",
        5: "5",
        6: "6",
        7: "7",
        8: "8",
        9: "9",
        10: "O",
        11: "N",
        12: "D",
    }

    @classmethod
    def get_holiday_csv_path(cls, year: int) -> Path:
        """Get the filesystem path for holiday CSV file for a given year.
        
        Args:
            year: Year for which to get the holiday file path
            
        Returns:
            Path: Complete path to the holiday CSV file
            
        Example:
            >>> MarketConfig.get_holiday_csv_path(2024)
            Path('/home/user/Downloads/fyers/src/fyers/utils/holidays_2024.csv')
        """
        return Path(cls.HOLIDAY_CSV_PATH) / f"holidays_{year}.csv"

    @classmethod
    def get_strike_multiple(cls, symbol: str) -> int:
        """Get the minimum strike price interval for a given symbol.
        
        Different underlying instruments have different strike price intervals:
        - NIFTY, FINNIFTY: 50 points
        - BANKNIFTY, SENSEX, BANKEX: 100 points  
        - MIDCPNIFTY: 25 points
        - Others: 100 points (default)
        
        Args:
            symbol: Underlying symbol name (case-insensitive)
            
        Returns:
            int: Strike price multiple/interval
            
        Example:
            >>> MarketConfig.get_strike_multiple("NIFTY")
            50
            >>> MarketConfig.get_strike_multiple("BANKNIFTY")
            100
        """
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
    """Comprehensive market calendar for Indian stock exchanges.
    
    This class handles all calendar-related operations for Indian markets including:
    - Holiday detection and management
    - Weekend identification
    - Trading day validation
    - Expiry date calculations for different contract types
    - Holiday adjustment logic
    
    The class automatically fetches holiday data from web sources with local
    CSV fallback and implements caching for performance.
    
    Features:
    - Automatic holiday data fetching from Groww.in
    - Local CSV fallback for reliability
    - LRU caching for performance optimization
    - Support for both NSE and BSE expiry rules
    - Automatic holiday adjustment for expiry dates
    
    Attributes:
        _holiday_cache: Cached list of holiday dates
        _cache_date: Date when cache was last updated
    """

    def __init__(self):
        """Initialize MarketCalendar with empty cache."""
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
            holiday_list = (
                df["Date"]
                .apply(lambda x: datetime.datetime.strptime(x, "%B %d, %Y").date())
                .to_list()
            )
        except Exception as e:
            # Fallback to CSV
            try:
                csv_path = MarketConfig.get_holiday_csv_path(year)
                df = pd.read_csv(csv_path, index_col=0)
                holiday_list = (
                    df["str_date"]
                    .apply(lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").date())
                    .to_list()
                )
            except FileNotFoundError:
                print(f"Warning: Could not fetch holiday list - {e}")
                holiday_list = []

        self._holiday_cache = holiday_list
        self._cache_date = today
        return [h for h in holiday_list if h.year == year]

    def is_holiday(self, date: datetime.date) -> bool:
        """Check if a given date is a market holiday.
        
        Args:
            date: Date to check for holiday status
            
        Returns:
            bool: True if the date is a market holiday, False otherwise
            
        Example:
            >>> calendar = MarketCalendar()
            >>> calendar.is_holiday(datetime.date(2024, 1, 26))  # Republic Day
            True
        """
        holidays = self._get_holiday_list(date.year)
        return date in holidays

    def is_weekend(self, date: datetime.date) -> bool:
        """Check if a given date falls on a weekend.
        
        Indian markets are closed on Saturdays and Sundays.
        
        Args:
            date: Date to check for weekend status
            
        Returns:
            bool: True if Saturday or Sunday, False otherwise
            
        Example:
            >>> calendar = MarketCalendar()
            >>> calendar.is_weekend(datetime.date(2024, 6, 15))  # Saturday
            True
        """
        return date.weekday() > 4  # Saturday = 5, Sunday = 6

    def is_trading_day(self, date: datetime.date) -> bool:
        """Check if a given date is a valid trading day.
        
        A trading day is one that is neither a weekend nor a market holiday.
        
        Args:
            date: Date to check for trading status
            
        Returns:
            bool: True if it's a trading day, False if weekend or holiday
            
        Example:
            >>> calendar = MarketCalendar()
            >>> calendar.is_trading_day(datetime.date(2024, 6, 17))  # Monday
            True
            >>> calendar.is_trading_day(datetime.date(2024, 6, 15))  # Saturday
            False
        """
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
        """Get the weekday number for exchange-specific expiry day.
        
        Indian exchanges have different expiry days:
        - NSE: Thursday (weekday 3)
        - BSE: Tuesday (weekday 1)
        
        Args:
            exchange: Exchange enum (NSE or BSE)
            
        Returns:
            int: Weekday number (0=Monday, 1=Tuesday, ..., 6=Sunday)
            
        Example:
            >>> calendar = MarketCalendar()
            >>> calendar.get_expiry_day_of_week(Exchange.NSE)
            3  # Thursday
            >>> calendar.get_expiry_day_of_week(Exchange.BSE)
            1  # Tuesday
        """
        return 3 if exchange == Exchange.NSE else 1  # Thursday=3, Tuesday=1

    def find_current_week_expiry(
        self, today: datetime.date, exchange: Exchange
    ) -> datetime.date:
        """Find the current week's expiry date for a given exchange.
        
        For weekly options, expiry occurs every week on:
        - NSE: Thursday
        - BSE: Tuesday
        
        If today is after the weekly expiry, returns next week's expiry.
        If the calculated expiry falls on a holiday, it's adjusted to the
        previous trading day.

        Args:
            today: Reference date to calculate from
            exchange: Exchange (NSE or BSE) to determine expiry day

        Returns:
            datetime.date: Current week's expiry date (holiday-adjusted)
            
        Example:
            >>> calendar = MarketCalendar()
            >>> # If today is Monday, June 17, 2024
            >>> calendar.find_current_week_expiry(
            ...     datetime.date(2024, 6, 17), Exchange.NSE
            ... )
            datetime.date(2024, 6, 20)  # Thursday
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
        self, today: datetime.date, exchange: Exchange
    ) -> datetime.date:
        """Find the next week's expiry date for a given exchange.
        
        Calculates the expiry date for the week following the current week's expiry.
        Useful for trading strategies that need to roll positions to the next
        weekly expiry.

        Args:
            today: Reference date to calculate from
            exchange: Exchange (NSE or BSE) to determine expiry day

        Returns:
            datetime.date: Next week's expiry date (holiday-adjusted)
            
        Example:
            >>> calendar = MarketCalendar()
            >>> # If today is Monday, June 17, 2024
            >>> calendar.find_next_week_expiry(
            ...     datetime.date(2024, 6, 17), Exchange.NSE
            ... )
            datetime.date(2024, 6, 27)  # Next Thursday
        """
        current_expiry = self.find_current_week_expiry(today, exchange)
        next_expiry = current_expiry + datetime.timedelta(days=7)
        return self.adjust_for_holiday(next_expiry)

    def find_last_weekday_of_month(
        self, year: int, month: int, weekday: int
    ) -> datetime.date:
        """Find the last occurrence of a specific weekday in a month.
        
        This is used to calculate monthly expiry dates which occur on the
        last Thursday (NSE) or Tuesday (BSE) of each month.

        Args:
            year: Target year
            month: Target month (1-12)
            weekday: Target weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)

        Returns:
            datetime.date: Date of the last occurrence of the weekday in the month
            
        Example:
            >>> calendar = MarketCalendar()
            >>> # Last Thursday of December 2024
            >>> calendar.find_last_weekday_of_month(2024, 12, 3)
            datetime.date(2024, 12, 26)
        """
        month_cal = calendar.monthcalendar(year, month)

        # Check last week, if 0 then check second-to-last week
        last_occurrence = month_cal[-1][weekday]
        if last_occurrence == 0:
            last_occurrence = month_cal[-2][weekday]

        return datetime.date(year, month, last_occurrence)

    def find_current_month_expiry(
        self, today: datetime.date, exchange: Exchange
    ) -> datetime.date:
        """Find the current month's expiry date for a given exchange.
        
        Monthly expiry occurs on the last occurrence of the exchange-specific
        day in each month:
        - NSE: Last Thursday of the month
        - BSE: Last Tuesday of the month
        
        If today is after the monthly expiry, returns next month's expiry.
        This is used for both futures and monthly options.

        Args:
            today: Reference date to calculate from
            exchange: Exchange (NSE or BSE) to determine expiry day

        Returns:
            datetime.date: Current month's expiry date (holiday-adjusted)
            
        Example:
            >>> calendar = MarketCalendar()
            >>> # If today is June 15, 2024
            >>> calendar.find_current_month_expiry(
            ...     datetime.date(2024, 6, 15), Exchange.NSE
            ... )
            datetime.date(2024, 6, 27)  # Last Thursday of June
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
        self, today: datetime.date, exchange: Exchange
    ) -> datetime.date:
        """Find the next month's expiry date for a given exchange.
        
        Calculates the expiry date for the month following the current month's expiry.
        This is useful for position rolling strategies and analyzing forward
        expiry dates.

        Args:
            today: Reference date to calculate from
            exchange: Exchange (NSE or BSE) to determine expiry day

        Returns:
            datetime.date: Next month's expiry date (holiday-adjusted)
            
        Example:
            >>> calendar = MarketCalendar()
            >>> # If today is June 15, 2024
            >>> calendar.find_next_month_expiry(
            ...     datetime.date(2024, 6, 15), Exchange.NSE
            ... )
            datetime.date(2024, 7, 25)  # Last Thursday of July
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
    """Advanced contract ticker generator for Indian derivatives markets.
    
    This class provides comprehensive functionality for generating standardized
    contract tickers according to NSE and BSE naming conventions. It handles:
    
    - Options (both weekly and monthly expiry)
    - Futures (monthly expiry only)
    - Strike price validation against symbol-specific multiples
    - Automatic holiday adjustment for expiry dates
    - Reference date adjustment for non-trading days
    
    Ticker Formats:
    - Monthly Futures: {Exchange}:{Symbol}{YY}{MMM}FUT
      Example: NSE:NIFTY24DECFUT
    
    - Monthly Options: {Exchange}:{Symbol}{YY}{MMM}{Strike}{Type}
      Example: NSE:NIFTY24DEC25000CE
    
    - Weekly Options: {Exchange}:{Symbol}{YY}{M}{DD}{Strike}{Type}
      Example: NSE:NIFTY24D1825000CE
      Note: Uses special month encoding (1-9, O, N, D) for weeks
    
    Key Features:
    - Automatic strike price validation
    - Holiday-aware expiry calculation
    - Support for both NSE and BSE formats
    - Comprehensive input validation
    - Reference date adjustment for weekends/holidays
    
    Attributes:
        calendar: MarketCalendar instance for date operations
    """

    def __init__(self):
        """Initialize ContractGenerator with market calendar."""
        self.calendar = MarketCalendar()

    def _adjust_reference_date(self, date: datetime.date) -> datetime.date:
        """Adjust reference date to next trading day if it's a holiday/weekend.

        This ensures that when calculating expiries from a non-trading day,
        we use the next trading day as reference for more logical results.
        This prevents counterintuitive behavior when generating contracts
        from weekend dates or holidays.

        Args:
            date: Input date (possibly a holiday/weekend)

        Returns:
            datetime.date: Next trading day if input is holiday/weekend, 
                          otherwise same date
                          
        Example:
            >>> generator = ContractGenerator()
            >>> # Saturday gets adjusted to Monday
            >>> generator._adjust_reference_date(datetime.date(2024, 6, 15))
            datetime.date(2024, 6, 17)
        """
        while not self.calendar.is_trading_day(date):
            date = date + datetime.timedelta(days=1)
        return date

    @staticmethod
    def validate_inputs(
        symbol: str,
        strike: Optional[int] = None,
        option_type: Optional[str] = None,
        contract_type: ContractType = ContractType.OPT,
    ) -> Tuple[Optional[int], Optional[OptionType]]:
        """Validate and normalize contract inputs.
        
        Performs comprehensive validation of contract parameters including:
        - Strike price validation against symbol-specific multiples
        - Option type validation (CE/PE)
        - Required field validation for options
        
        Strike Price Rules:
        - NIFTY, FINNIFTY: Must be multiple of 50
        - BANKNIFTY, SENSEX, BANKEX: Must be multiple of 100
        - MIDCPNIFTY: Must be multiple of 25
        - Others: Must be multiple of 100

        Args:
            symbol: Underlying symbol name
            strike: Strike price (required for options)
            option_type: "CE" or "PE" (required for options)
            contract_type: Contract type (FUT or OPT)

        Returns:
            Tuple[Optional[int], Optional[OptionType]]: Validated strike and option type
            
        Raises:
            ValueError: If options are missing required parameters
            ValueError: If strike price is not a valid multiple
            ValueError: If option type is invalid
            
        Example:
            >>> ContractGenerator.validate_inputs("NIFTY", 25000, "CE")
            (25000, OptionType.CE)
            >>> ContractGenerator.validate_inputs("NIFTY", 25050, "CE")
            ValueError: NIFTY strike must be multiple of 50, got 25050
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
        """Generate standardized contract ticker from contract details.
        
        Creates ticker strings according to Indian exchange formats:
        
        Futures Format:
            {Exchange}:{Symbol}{YY}{MMM}FUT
            Example: NSE:NIFTY24DECFUT
            
        Monthly Options Format:
            {Exchange}:{Symbol}{YY}{MMM}{Strike}{Type}
            Example: NSE:NIFTY24DEC25000CE
            
        Weekly Options Format:
            {Exchange}:{Symbol}{YY}{M}{DD}{Strike}{Type}
            Example: NSE:NIFTY24D1825000CE
            
        Note: Weekly options use special month encoding:
        Jan-Sep: 1-9, Oct: O, Nov: N, Dec: D

        Args:
            details: Complete contract specification

        Returns:
            str: Standardized ticker string ready for trading systems
            
        Example:
            >>> details = ContractDetails(
            ...     exchange=Exchange.NSE,
            ...     symbol="NIFTY",
            ...     expiry_date=datetime.date(2024, 12, 26),
            ...     contract_type=ContractType.OPT,
            ...     expiry_type=ExpiryType.MONTHLY,
            ...     strike=25000,
            ...     option_type=OptionType.CE
            ... )
            >>> generator.generate_ticker(details)
            'NSE:NIFTY24DEC25000CE'
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
        today: Optional[datetime.date] = None,
    ) -> str:
        """Generate ticker for current week's option expiry.
        
        Creates weekly option tickers that expire on the current week's
        exchange-specific expiry day (Thursday for NSE, Tuesday for BSE).
        If today is past this week's expiry, automatically returns next
        week's expiry.
        
        Args:
            exchange: Trading exchange (NSE or BSE)
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price (must be multiple of symbol's interval)
            option_type: "CE" for Call or "PE" for Put
            today: Reference date (defaults to today, adjusted if holiday)
            
        Returns:
            str: Weekly option ticker
            
        Raises:
            ValueError: If strike is not valid multiple or option type invalid
            
        Example:
            >>> generator = ContractGenerator()
            >>> generator.current_week_option(
            ...     Exchange.NSE, "NIFTY", 25000, "CE", 
            ...     datetime.date(2024, 6, 17)
            ... )
            'NSE:NIFTY24620025000CE'
        """
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
            option_type=opt_type,
        )

        return self.generate_ticker(details)

    # Next Week Options
    def next_week_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None,
    ) -> str:
        """Generate ticker for next week's option expiry.
        
        Creates weekly option tickers for the week following the current
        week's expiry. Useful for position rolling strategies and planning
        ahead for upcoming expiries.
        
        Args:
            exchange: Trading exchange (NSE or BSE)
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price (must be multiple of symbol's interval)
            option_type: "CE" for Call or "PE" for Put
            today: Reference date (defaults to today, adjusted if holiday)
            
        Returns:
            str: Next week's option ticker
            
        Raises:
            ValueError: If strike is not valid multiple or option type invalid
            
        Example:
            >>> generator = ContractGenerator()
            >>> generator.next_week_option(
            ...     Exchange.NSE, "BANKNIFTY", 50000, "PE",
            ...     datetime.date(2024, 6, 17)
            ... )
            'NSE:BANKNIFTY24627050000PE'
        """
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
            option_type=opt_type,
        )

        return self.generate_ticker(details)

    # Current Month Options
    def current_month_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None,
    ) -> str:
        """Generate ticker for current month's option expiry.
        
        Creates monthly option tickers that expire on the last exchange-specific
        day of the current month (last Thursday for NSE, last Tuesday for BSE).
        If today is past this month's expiry, automatically returns next month's expiry.
        
        Monthly options typically have higher liquidity and are preferred for
        longer-term strategies compared to weekly options.
        
        Args:
            exchange: Trading exchange (NSE or BSE)
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price (must be multiple of symbol's interval)
            option_type: "CE" for Call or "PE" for Put
            today: Reference date (defaults to today, adjusted if holiday)
            
        Returns:
            str: Monthly option ticker
            
        Raises:
            ValueError: If strike is not valid multiple or option type invalid
            
        Example:
            >>> generator = ContractGenerator()
            >>> generator.current_month_option(
            ...     Exchange.NSE, "NIFTY", 25000, "CE",
            ...     datetime.date(2024, 6, 15)
            ... )
            'NSE:NIFTY24JUN25000CE'
        """
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
            option_type=opt_type,
        )

        return self.generate_ticker(details)

    # Next Month Options
    def next_month_option(
        self,
        exchange: Exchange,
        symbol: str,
        strike: int,
        option_type: str,
        today: Optional[datetime.date] = None,
    ) -> str:
        """Generate ticker for next month's option expiry.
        
        Creates monthly option tickers for the month following the current
        month's expiry. These contracts typically have lower time decay
        and are used for strategies requiring more time until expiration.
        
        Args:
            exchange: Trading exchange (NSE or BSE)
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price (must be multiple of symbol's interval)
            option_type: "CE" for Call or "PE" for Put
            today: Reference date (defaults to today, adjusted if holiday)
            
        Returns:
            str: Next month's option ticker
            
        Raises:
            ValueError: If strike is not valid multiple or option type invalid
            
        Example:
            >>> generator = ContractGenerator()
            >>> generator.next_month_option(
            ...     Exchange.BSE, "SENSEX", 70000, "PE",
            ...     datetime.date(2024, 6, 15)
            ... )
            'BSE:SENSEX24JUL70000PE'
        """
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
            option_type=opt_type,
        )

        return self.generate_ticker(details)

    # Current Month Futures
    def current_month_future(
        self, exchange: Exchange, symbol: str, today: Optional[datetime.date] = None
    ) -> str:
        """Generate ticker for current month's futures contract.
        
        Creates futures contract tickers that expire on the last exchange-specific
        day of the current month. Futures contracts create an obligation to buy/sell
        the underlying at expiry, unlike options which provide the right but not
        the obligation.
        
        Note: Futures only have monthly expiry, not weekly expiry like options.
        If today is past this month's expiry, automatically returns next month's expiry.
        
        Args:
            exchange: Trading exchange (NSE or BSE)
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            today: Reference date (defaults to today, adjusted if holiday)
            
        Returns:
            str: Current month futures ticker
            
        Example:
            >>> generator = ContractGenerator()
            >>> generator.current_month_future(
            ...     Exchange.NSE, "NIFTY",
            ...     datetime.date(2024, 6, 15)
            ... )
            'NSE:NIFTY24JUNFUT'
        """
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday

        expiry = self.calendar.find_current_month_expiry(today, exchange)

        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.FUT,
            expiry_type=ExpiryType.MONTHLY,
        )

        return self.generate_ticker(details)

    # Next Month Futures
    def next_month_future(
        self, exchange: Exchange, symbol: str, today: Optional[datetime.date] = None
    ) -> str:
        """Generate ticker for next month's futures contract.
        
        Creates futures contract tickers for the month following the current
        month's expiry. These contracts are commonly used for position rolling
        strategies and for establishing positions with more time until expiration.
        
        Args:
            exchange: Trading exchange (NSE or BSE)
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            today: Reference date (defaults to today, adjusted if holiday)
            
        Returns:
            str: Next month futures ticker
            
        Example:
            >>> generator = ContractGenerator()
            >>> generator.next_month_future(
            ...     Exchange.BSE, "SENSEX",
            ...     datetime.date(2024, 6, 15)
            ... )
            'BSE:SENSEX24JULFUT'
        """
        today = today or datetime.date.today()
        today = self._adjust_reference_date(today)  # Adjust if holiday

        expiry = self.calendar.find_next_month_expiry(today, exchange)

        details = ContractDetails(
            exchange=exchange,
            symbol=symbol,
            expiry_date=expiry,
            contract_type=ContractType.FUT,
            expiry_type=ExpiryType.MONTHLY,
        )

        return self.generate_ticker(details)


# Convenience functions for backward compatibility
def get_contract_generator() -> ContractGenerator:
    """Get a contract generator instance for backward compatibility.
    
    This function provides a simple way to obtain a ContractGenerator instance
    without needing to import and instantiate the class directly. Maintained
    for backward compatibility with existing code.
    
    Returns:
        ContractGenerator: New instance ready for contract generation
        
    Example:
        >>> generator = get_contract_generator()
        >>> ticker = generator.current_month_future(Exchange.NSE, "NIFTY")
    """
    return ContractGenerator()


class MarketContracts:
    """
    Unified interface for market contract operations.

    This is the main entry point for all market contract functionality.
    Provides a simple, single-import interface for:
    - Generating option and futures tickers
    - Checking market calendar (holidays, trading days)
    - Getting expiry dates

    Important: When the reference date is a holiday/weekend, all ticker generation
    and expiry calculation methods automatically adjust to the next trading day
    for more logical results.

    Example:
        from quant_toolkit.market_contracts import MarketContracts

        mc = MarketContracts()

        # Generate tickers
        ticker = mc.option("NSE", "NIFTY", 25000, "CE", "current_week")
        ticker = mc.future("BSE", "SENSEX", "next_month")

        # Check calendar
        is_holiday = mc.is_holiday(date)
        expiry = mc.get_expiry("NSE", "current_month")
    """

    def __init__(self):
        """Initialize the MarketContracts facade."""
        self._generator = ContractGenerator()
        self._calendar = MarketCalendar()
        self._config = MarketConfig

    # ============= Option Methods =============

    def option(
        self,
        exchange: str,
        symbol: str,
        strike: int,
        option_type: str,
        expiry: str,
        date: Optional[datetime.date] = None,
    ) -> str:
        """
        Generate option ticker.

        Args:
            exchange: "NSE" or "BSE"
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price (must be multiple of symbol's strike interval)
            option_type: "CE" or "PE"
            expiry: "current_week", "next_week", "current_month", or "next_month"
            date: Reference date (defaults to today). If holiday/weekend,
                  automatically adjusts to next trading day.

        Returns:
            Formatted ticker string

        Example:
            >>> mc.option("NSE", "NIFTY", 25000, "CE", "current_week")
            'NSE:NIFTY25D0825000CE'
        """
        exchange_enum = Exchange[exchange.upper()]
        date = date or datetime.date.today()

        # Adjust reference date if it's a holiday/weekend
        date = self._generator._adjust_reference_date(date)

        if expiry == "current_week":
            return self._generator.current_week_option(
                exchange_enum, symbol, strike, option_type, date
            )
        elif expiry == "next_week":
            return self._generator.next_week_option(
                exchange_enum, symbol, strike, option_type, date
            )
        elif expiry == "current_month":
            return self._generator.current_month_option(
                exchange_enum, symbol, strike, option_type, date
            )
        elif expiry == "next_month":
            return self._generator.next_month_option(
                exchange_enum, symbol, strike, option_type, date
            )
        else:
            raise ValueError(
                f"Invalid expiry type: {expiry}. "
                "Use 'current_week', 'next_week', 'current_month', or 'next_month'"
            )

    # ============= Futures Methods =============

    def future(
        self,
        exchange: str,
        symbol: str,
        expiry: str,
        date: Optional[datetime.date] = None,
    ) -> str:
        """
        Generate futures ticker.

        Args:
            exchange: "NSE" or "BSE"
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            expiry: "current_month" or "next_month" (futures don't have weekly expiry)
            date: Reference date (defaults to today)

        Returns:
            Formatted ticker string

        Example:
            >>> mc.future("NSE", "NIFTY", "current_month")
            'NSE:NIFTY25DECFUT'
        """
        exchange_enum = Exchange[exchange.upper()]
        date = date or datetime.date.today()

        # Adjust reference date if it's a holiday/weekend
        date = self._generator._adjust_reference_date(date)

        if expiry == "current_month":
            return self._generator.current_month_future(exchange_enum, symbol, date)
        elif expiry == "next_month":
            return self._generator.next_month_future(exchange_enum, symbol, date)
        else:
            raise ValueError(
                f"Invalid expiry type for futures: {expiry}. "
                "Use 'current_month' or 'next_month'"
            )

    # ============= Calendar Methods =============

    def is_holiday(self, date: datetime.date) -> bool:
        """
        Check if a date is a market holiday.

        Args:
            date: Date to check

        Returns:
            True if holiday, False otherwise
        """
        return self._calendar.is_holiday(date)

    def is_weekend(self, date: datetime.date) -> bool:
        """
        Check if a date is a weekend.

        Args:
            date: Date to check

        Returns:
            True if weekend (Saturday/Sunday), False otherwise
        """
        return self._calendar.is_weekend(date)

    def is_trading_day(self, date: datetime.date) -> bool:
        """
        Check if a date is a trading day.

        Args:
            date: Date to check

        Returns:
            True if trading day (not holiday or weekend), False otherwise
        """
        return self._calendar.is_trading_day(date)

    def adjust_for_holiday(self, date: datetime.date) -> datetime.date:
        """
        Adjust date to previous trading day if it falls on holiday/weekend.

        Args:
            date: Date to adjust

        Returns:
            Adjusted date (moves backward to nearest trading day)
        """
        return self._calendar.adjust_for_holiday(date)

    # ============= Expiry Date Methods =============

    def get_expiry(
        self, exchange: str, expiry_type: str, date: Optional[datetime.date] = None
    ) -> datetime.date:
        """
        Get expiry date for given exchange and expiry type.

        Args:
            exchange: "NSE" or "BSE"
            expiry_type: "current_week", "next_week", "current_month", or "next_month"
            date: Reference date (defaults to today)

        Returns:
            Expiry date (adjusted for holidays)

        Example:
            >>> mc.get_expiry("NSE", "current_month")
            datetime.date(2025, 12, 24)
        """
        exchange_enum = Exchange[exchange.upper()]
        date = date or datetime.date.today()

        # Adjust reference date if it's a holiday/weekend
        date = self._generator._adjust_reference_date(date)

        if expiry_type == "current_week":
            return self._calendar.find_current_week_expiry(date, exchange_enum)
        elif expiry_type == "next_week":
            return self._calendar.find_next_week_expiry(date, exchange_enum)
        elif expiry_type == "current_month":
            return self._calendar.find_current_month_expiry(date, exchange_enum)
        elif expiry_type == "next_month":
            return self._calendar.find_next_month_expiry(date, exchange_enum)
        else:
            raise ValueError(
                f"Invalid expiry type: {expiry_type}. "
                "Use 'current_week', 'next_week', 'current_month', or 'next_month'"
            )

    # ============= Configuration Methods =============

    def get_strike_multiple(self, symbol: str) -> int:
        """
        Get strike price multiple for a symbol.

        Args:
            symbol: Symbol name (e.g., "NIFTY", "BANKNIFTY")

        Returns:
            Strike price multiple (e.g., 50 for NIFTY, 100 for BANKNIFTY)

        Example:
            >>> mc.get_strike_multiple("NIFTY")
            50
        """
        return self._config.get_strike_multiple(symbol)

    def get_holiday_list(self, year: Optional[int] = None) -> list[datetime.date]:
        """
        Get list of holidays for a year.

        Args:
            year: Year to get holidays for (defaults to current year)

        Returns:
            List of holiday dates
        """
        year = year or datetime.date.today().year
        return self._calendar._get_holiday_list(year)

    # ============= Convenience Methods =============

    def create_contract_details(
        self,
        exchange: str,
        symbol: str,
        expiry_date: datetime.date,
        contract_type: str,
        expiry_type: str,
        strike: Optional[int] = None,
        option_type: Optional[str] = None,
    ) -> ContractDetails:
        """
        Create a ContractDetails object.

        This is useful for advanced users who want to work with the underlying
        data structures directly.

        Args:
            exchange: "NSE" or "BSE"
            symbol: Underlying symbol
            expiry_date: Expiry date
            contract_type: "FUT" or "OPT"
            expiry_type: "WEEKLY" or "MONTHLY"
            strike: Strike price (required for options)
            option_type: "CE" or "PE" (required for options)

        Returns:
            ContractDetails object
        """
        return ContractDetails(
            exchange=Exchange[exchange.upper()],
            symbol=symbol,
            expiry_date=expiry_date,
            contract_type=ContractType[contract_type.upper()],
            expiry_type=ExpiryType[expiry_type.upper()],
            strike=strike,
            option_type=OptionType[option_type.upper()] if option_type else None,
        )

    def generate_ticker_from_details(self, details: ContractDetails) -> str:
        """
        Generate ticker from ContractDetails object.

        Args:
            details: ContractDetails object

        Returns:
            Formatted ticker string
        """
        return self._generator.generate_ticker(details)
