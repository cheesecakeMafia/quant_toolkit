import datetime
from typing import List
import calendar
import pandas as pd
from typing import Union


class DatetimeValidator:
    def __init__(self):
        self.WEEKDAY_MAP = {
            # Full names
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
            # Three letter abbreviations
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6,
        }

    def _get_holiday_list(self) -> List[datetime.date]:
        """Returns a list of all the holidays in they year so that expiries can be adjusted accordingly.

        Returns:
            List[datetime.date]: Returns a list of datatime.date objects where each element is a holiday date.
        """
        try:
            url = "https://groww.in/p/nse-holidays"
            holiday_list = (
                pd.read_html(url, header=0)[0]["Date"]
                .apply(lambda x: datetime.datetime.strptime(x, "%B %d, %Y").date())
                .to_list()
            )
            return holiday_list
        except Exception:
            _year = datetime.date.today().year
            holiday_list = (
                pd.read_csv(
                    rf"/home/cheesecake/Downloads/fyers/src/fyers/utils/holidays_{_year}.csv",
                    index_col=0,
                )["str_date"]
                .apply(lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").date())
                .to_list()
            )
        return holiday_list

    def _validate_holiday(self, dt: datetime.date) -> datetime.date:
        """Checks whether a given day is a holiday or not.
        If it is returns the datetime.date of the next working day.

        Args:
            dt (datetime.date): A datetime.date object of the date you want to verify.

        Returns:
            datetime.date: Returns the datetime.date object of the
            next day is a holiday is on the argument date.
        """
        holiday_list = self._get_holiday_list()
        for holiday in holiday_list:
            if holiday == dt:
                return dt - datetime.timedelta(days=1)
        return dt

    def _validate_weekday(self, dt: datetime.date) -> datetime.date:
        """Checks if he given day is a weekday or weekend.
        If it is a weekend, returns the next working day.

        Args:
            dt (datetime.date): A datetime.date object of the date you want to verify.

        Returns:
            datetime.date: Returns datetime.date object of the working day.
        """
        while dt.weekday() > 4:
            dt = dt - datetime.timedelta(days=1)
        return dt

    def _find_current_expiry_day(
        self, today_date: datetime.date, target_day: str = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the coming nearest expiry specified weekday.

        Args:
            today_date (datetime.date): The reference date
            target_day (str): Target weekday (full name like "Monday" or abbreviated "Mon")

        Returns:
            datetime.date: Date of the target weekday in the current week

        Raises:
            ValueError: If target_day is invalid
        """

        day_str = target_day.lower()
        if day_str not in self.WEEKDAY_MAP:
            raise ValueError(
                "Invalid day string. Use full names (e.g., 'Monday') "
                "or three-letter abbreviations (e.g., 'Mon')"
            )
        target_day = self.WEEKDAY_MAP[day_str]

        days_until = (target_day - today_date.weekday() + 7) % 7
        return today_date + datetime.timedelta(days=days_until)

    def _find_next_expiry_day(
        self, today_date: datetime.date, target_day: Union[int, str] = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the specified weekday which is a week after the current.
        """

        return self._find_current_weekday(today_date, target_day) + datetime.timedelta(
            days=7
        )

    def find_current_week_expiry(
        self, today_date: datetime.date, target_day: str = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the weekly expiry of the current week.
        """
        return self._find_current_expiry_day(today_date, target_day)

    def find_next_week_expiry(
        self, today_date: datetime.date, target_day: str = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the weekly expiry of the next week.
        """
        return self._find_current_weekday(today_date, target_day) + datetime.timedelta(
            days=7
        )

    def _get_last_day_month(self, year, month, target_day="Thursday") -> datetime.date:
        """
        Get the last target_day of the month.
        # To get the last working Thursday of the month, we use index 3. Mon-Sun -> 0-6 is the mapping.
        """
        day_idx = self.WEEKDAY_MAP[target_day.lower()]
        return datetime.date(
            year,
            month,
            (
                calendar.monthcalendar(year, month)[-1][day_idx]
                if calendar.monthcalendar(year, month)[-1][day_idx] != 0
                else calendar.monthcalendar(year, month)[-2][day_idx]
            ),
        )

    def find_current_monthly_expiry(
        self, today_date: datetime.date, target_day: str = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the monthly expiry of the current month.
        """
        _year = today_date.year
        _month = today_date.month
        last_thu = self._get_last_day_month(_year, _month, target_day)
        if last_thu >= today_date:
            return last_thu
        _month += 1
        if _month > 12:
            _month = _month - 12
            _year += 1
        last_thu = self._get_last_day_month(_year, _month, target_day)
        return last_thu

    def find_next_monthly_expiry(
        self, today_date: datetime.date, target_day: str = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the monthly expiry of the next month.
        """
        _year = today_date.year
        _month = today_date.month + 1
        if _month > 12:
            _month = _month - 12
            _year += 1
        last_thu = self._get_last_day_month(_year, _month, target_day)
        if last_thu > self.find_current_monthly_expiry(today_date, target_day):
            return last_thu
        _month += 1
        if _month > 12:
            _month = _month - 12
            _year += 1
        last_thu = self._get_last_day_month(_year, _month, target_day)
        return last_thu

    def validate_expiry(self, expiry_date: datetime.date) -> datetime.date:
        """Validates the expiry date and adjusts it to the nearest working day if it is a holiday or weekend.

        Args:
            expiry_date (datetime.date): The date you want to validate.

        Returns:
            datetime.date: Returns the nearest working day if the input date is a holiday or weekend.
        """
        expiry_date = self._validate_holiday(expiry_date)
        expiry_date = self._validate_weekday(expiry_date)
        return expiry_date


class FNOExpiry(DatetimeValidator):
    """_summary_
    This class helps in generating the correct ticker(contract name) we require for trading that particular derivative i.e. futures and options.
    It is a child class of DatetimeValidator class which helps in validating the expiry dates and adjusting them accordingly.

    The format of Index/Equity monthly futures is as follows-
    {Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}FUT
    Some examples are - NSE:NIFTY20OCTFUT, NSE:BANKNIFTY20NOVFUT, BSE:SENSEX23AUGFUT

    The format of Index/Equity monthly options is as follows-
    {Ex}:{Ex_UnderlyingSymbol}{YY}{MMM}{Strike}{Opt_Type}
    Some examples are - NSE:NIFTY20OCT11000CE, NSE:BANKNIFTY20NOV25000PE, BSE:SENSEX23AUG60400CE

    The format for weekly index options is as follows-
    {Ex}:{Ex_UnderlyingSymbol}{YY}{M}{dd}{Strike}{Opt_Type}
    NSE:NIFTY2010811000CE, NSE:NIFTY20O0811000CE, BSE:SENSEX2381161000CE, NSE:NIFTY20D1025000CE
    Here, M is the month and as it is a single character, we have a special dict defined to access it.
    Jan => 1, Feb => 2, Mar => 3, Apr => 4
    May => 5, Jun => 6, Jul => 7, Aug => 8
    Sep => 9, Oct => O (Letter), Nov => N, Dec => D

    """

    def __init__(self):
        super().__init__()
        self.MONTH_KEY_MAP = {
            "JAN": "1",
            "FEB": "2",
            "MAR": "3",
            "APR": "4",
            "MAY": "5",
            "JUN": "6",
            "JUL": "7",
            "AUG": "8",
            "SEP": "9",
            "OCT": "O",
            "NOV": "N",
            "DEC": "D",
        }

    """Futures expiry contract(Testing Done!)"""

    def current_month_fut_expiry(
        self, symbol: str, today_date: datetime.date = datetime.date.today()
    ) -> str:
        assert "FUT" in symbol, print("The symbol should be a future symbol.")
        if "BSE" in symbol:
            expiry_date = self.find_current_monthly_expiry(today_date, "Tuesday")
        else:
            expiry_date = self.find_current_monthly_expiry(today_date, "Thursday")
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month = expiry_date.year, expiry_date.month
        _symbol = symbol.split("-")[0].upper()
        return _symbol + str(_year)[-2:] + calendar.month_abbr[_month].upper() + "FUT"

    def next_month_fut_expiry(
        self,
        symbol: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        assert "FUT" in symbol, print("The symbol should be a future symbol.")
        if "BSE" in symbol:
            expiry_date = self.find_next_monthly_expiry(today_date, "Tuesday")
        else:
            expiry_date = self.find_next_monthly_expiry(today_date, "Thursday")
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month = expiry_date.year, expiry_date.month
        _symbol = symbol.split("-")[0].upper()
        return _symbol + str(_year)[-2:] + calendar.month_abbr[_month].upper() + "FUT"

    """Index monthly options expiry contract(Testing Required!)"""

    # TODO: Testing required
    def index_current_month_opt_expiry(
        self,
        symbol: str,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        assert "INDEX" in symbol, print("The symbol should be of a valid Index.")
        if "BSE" in symbol:
            expiry_date = self.find_current_monthly_expiry(today_date, "Tuesday")
        else:
            expiry_date = self.find_current_monthly_expiry(today_date, "Thursday")
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month = expiry_date.year, expiry_date.month
        _symbol = symbol.split("-")[0]
        return (
            _symbol
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    # TODO: Testing required
    def index_next_month_opt_expiry(
        self,
        symbol: str,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        assert "INDEX" in symbol, print("The symbol should be of a valid Index.")
        if "BSE" in symbol:
            expiry_date = self.find_current_monthly_expiry(today_date, "Tuesday")
        else:
            expiry_date = self.find_current_monthly_expiry(today_date, "Thursday")
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month = expiry_date.year, expiry_date.month
        _symbol = symbol.split("-")[0]
        return (
            _symbol
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    """Nifty options weekly expiry contract(Testing Required!)"""

    # TODO: Testing required
    def nifty_current_week_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        expiry_date = self.find_current_week_expiry(today_date)
        expiry_date = self.validate_expiry(expiry_date)
        if expiry_date < today_date:
            expiry_date = self._find_current_expiry_day(today_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + self.MONTH_KEY_MAP[calendar.month_abbr[_month].upper()]
            + str(_day).zfill(2)
            + str(strike_price)
            + opt_type
        )

    # TODO: Testing required
    def nifty_next_week_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        expiry_date = self.find_next_week_expiry(today_date)
        expiry_date = self.validate_expiry(expiry_date)
        if expiry_date - today_date <= datetime.timedelta(days=7):
            expiry_date = self._find_current_expiry_day(today_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + self.MONTH_KEY_MAP[calendar.month_abbr[_month].upper()]
            + str(_day).zfill(2)
            + str(strike_price)
            + opt_type
        )

    """Sensex options weekly expiry contract(Testing Required!)"""

    # TODO: Testing required
    def sensex_current_week_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        expiry_date = self.find_current_week_expiry(today_date, "Tuesday")
        expiry_date = self.validate_expiry(expiry_date)
        if expiry_date < today_date:
            expiry_date = self._find_current_expiry_day(today_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + self.MONTH_KEY_MAP[calendar.month_abbr[_month].upper()]
            + str(_day).zfill(2)
            + str(strike_price)
            + opt_type
        )

    # TODO: Testing required
    def sensex_next_week_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        expiry_date = self.find_next_week_expiry(today_date, "Tuesday")
        expiry_date = self.validate_expiry(expiry_date)
        if expiry_date - today_date <= datetime.timedelta(days=7):
            expiry_date = self._find_current_expiry_day(today_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + self.MONTH_KEY_MAP[calendar.month_abbr[_month].upper()]
            + str(_day).zfill(2)
            + str(strike_price)
            + opt_type
        )


def main():
    pass


if __name__ == "__main__":
    main()
