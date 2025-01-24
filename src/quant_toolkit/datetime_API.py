import datetime
from typing import List
import calendar
import pandas as pd
from typing import Union

"""
/** 
* ! This is in red. 
* ? This is in blue.
* TODO: This is in orange.
*/ 
"""


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

    def get_holiday_list(self) -> List[datetime.date]:
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
        except Exception as e:
            print(e)
            holiday_list = (
                pd.read_csv(
                    r"/home/cheesecake/Downloads/fyers/utils/holidays_2024.csv",
                    index_col=0,
                )["str_date"]
                .apply(lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").date())
                .to_list()
            )
        return holiday_list

    def validate_holiday(self, dt: datetime.date) -> datetime.date:
        """Checks whether a given day is a holiday or not.
        If it is returns the datetime.date of the next working day.

        Args:
            dt (datetime.date): A datetime.date object of the date you want to verify.

        Returns:
            datetime.date: Returns the datetime.date object of the
            next day is a holiday is on the argument date.
        """
        holiday_list = self.get_holiday_list()
        while dt in holiday_list:
            dt = dt + datetime.timedelta(days=1)
        return dt

    def validate_weekday(self, dt: datetime.date) -> datetime.date:
        """Checks if he given day is a weekday or weekend.
        If it is a weekend, returns the next working day.

        Args:
            dt (datetime.date): A datetime.date object of the date you want to verify.

        Returns:
            datetime.date: Returns datetime.date object of the working day.
        """
        if dt.weekday() > 4:
            return dt + datetime.timedelta(days=(7 - dt.weekday()))
        return dt

    def validate_expiry(self, dt: datetime.date) -> datetime.date:
        """Check if the inputed datetime.date object is a valid expiry for
        the selected security or not.

        Args:
            dt (datetime.date): A datetime.date object of the date you want to verify.

        Returns:
            datetime.date: Returns datetime.date object of the new updated expiry date.
        """
        holiday_dates = self.get_holiday_list()
        while (datetime.datetime(dt.year, dt.month, dt.day) in holiday_dates) or (
            dt.weekday() > 4
        ):
            dt = dt - datetime.timedelta(days=1)
        return dt

    def find_current_weekday(
        self, today_date: datetime.date, target_day: Union[int, str] = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the coming specified weekday.

        Args:
            today_date (datetime.date): The reference date
            target_day (int or str): Target weekday either as:
                - int (0-6, where 0=Monday, 6=Sunday)
                - str (full name like "Monday" or abbreviated "Mon")

        Returns:
            datetime.date: Date of the target weekday in the current week

        Raises:
            ValueError: If target_day is invalid
        """

        if isinstance(target_day, str):
            day_str = target_day.lower()
            if day_str not in self.WEEKDAY_MAP:
                raise ValueError(
                    "Invalid day string. Use full names (e.g., 'Monday') "
                    "or three-letter abbreviations (e.g., 'Mon')"
                )
            target_day = self.WEEKDAY_MAP[day_str]

        days_until = (target_day - today_date.weekday() + 7) % 7
        return today_date + datetime.timedelta(days=days_until)

    def find_next_weekday(
        self, today_date: datetime.date, target_day: Union[int, str] = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the specified weekday which is a week after the current.
        """

        return self.find_current_weekday(today_date, target_day) + datetime.timedelta(
            days=7
        )

    def find_last_weekday(
        self, today_date: datetime.date, target_day: Union[int, str] = "Thursday"
    ) -> datetime.date:
        """
        Find the date of the specified weekday in the last week.
        """
        # Write a function to get the date of the weekday of the last week of the month
        pass


class FNOExpiry(DatetimeValidator):
    """_summary_
    This class helps in genrating the correct ticker we require for trading that particular derivative i.e. futures and options.
    It is a child class of DatetimeValidator class which helps in validating the dates and adjusting them accordingly.

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

    After we receive the string of the ticker, we need to check if that day is a holiday or not. If yes, we need to shift the expiry one working day backward
    and if the day on which we want is a weekend or a holiday, we need to move to the next working day forward.
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

    """Index futures expiry"""

    def banknifty_current_month_fut_expiry(
        self,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:BANKNIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + "FUT"
        )

    def banknifty_next_month_fut_expiry(
        self,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:BANKNIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + "FUT"
        )

    def nifty_current_month_fut_expiry(
        self,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY" + str(_year)[-2:] + calendar.month_abbr[_month].upper() + "FUT"
        )

    def nifty_next_month_fut_expiry(
        self,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY" + str(_year)[-2:] + calendar.month_abbr[_month].upper() + "FUT"
        )

    def index_current_month_fut_expiry(
        self, symbol: str, today_date: datetime.date = datetime.date.today()
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        _symbol = symbol.split("-")[0]
        return _symbol + str(_year)[-2:] + calendar.month_abbr[_month].upper() + "FUT"

    def index_next_month_fut_expiry(
        self,
        symbol: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1

        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        _symbol = symbol.split("-")[0]
        return _symbol + str(_year)[-2:] + calendar.month_abbr[_month].upper() + "FUT"

    """Stock futures expiry"""

    def stock_current_month_fut_expiry(
        self, stock_symbol: str, today_date: datetime.date = datetime.date.today()
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            f"{stock_symbol.upper()[:-4]}"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + "FUT"
        )

    def stock_next_month_fut_expiry(
        self,
        stock_symbol: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            f"{stock_symbol.upper()[:-4]}"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + "FUT"
        )

    """Index options monthly expiry"""

    def finnifty_current_month_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:FINNIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    def finnifty_next_month_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:FINNIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    def banknifty_current_month_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:BANKNIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    def banknifty_next_month_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:BANKNIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    def nifty_current_month_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month
        else:
            _month = _month + 1
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    def nifty_next_month_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        today_date = self.validate_holiday(today_date)
        today_date = self.validate_weekday(today_date)
        _year, _month, _day = today_date.year, today_date.month, today_date.day
        if _day <= max(
            week[3] for week in calendar.monthcalendar(_year, _month)
        ):  # 3 is for Thursday and 2 is for Wednesday. [Mon, Sun] -> [0,6] mapping
            _month = _month + 1
        else:
            _month = _month + 2
        if _month > 12:
            _month = _month - 12
            _year = _year + 1
        expiry_date = datetime.date(_year, _month, _day)
        expiry_date = self.validate_expiry(expiry_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + calendar.month_abbr[_month].upper()
            + str(strike_price)
            + opt_type
        )

    """Nifty options weekly expiry"""

    def nifty_current_week_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        expiry_date = self.find_current_weekday(today_date)
        expiry_date = self.validate_expiry(expiry_date)
        if expiry_date < today_date:
            expiry_date = self.find_next_weekday(today_date)
        _year, _month, _day = expiry_date.year, expiry_date.month, expiry_date.day
        return (
            "NSE:NIFTY"
            + str(_year)[-2:]
            + self.MONTH_KEY_MAP[calendar.month_abbr[_month].upper()]
            + str(_day).zfill(2)
            + str(strike_price)
            + opt_type
        )

    def nifty_next_week_opt_expiry(
        self,
        strike_price: int,
        opt_type: str,
        today_date: datetime.date = datetime.date.today(),
    ) -> str:
        expiry_date = self.find_current_weekday(today_date)
        expiry_date = self.validate_expiry(expiry_date)
        if expiry_date - today_date <= datetime.timedelta(days=7):
            expiry_date = self.find_next_weekday(today_date)
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
    calc = FNOExpiry()

    # For futures
    nifty_fut = calc.nifty_current_month_fut_expiry()
    banknifty_fut = calc.banknifty_next_month_fut_expiry()

    # For monthly options
    nifty_monthly = calc.nifty_current_month_opt_expiry(
        23500, "CE", datetime.date.today()
    )
    banknifty_monthly = calc.banknifty_next_month_opt_expiry(
        49000, "CE", datetime.date.today()
    )

    # For weekly options
    nifty_weekly = calc.nifty_current_week_opt_expiry(
        24000, "PE", datetime.date.today()
    )
    nifty_next_weekly = calc.nifty_next_week_opt_expiry(
        25000, "PE", datetime.date.today()
    )

    print(f"{nifty_fut=}")
    print(f"{banknifty_fut=}")
    print(f"{nifty_monthly=}")
    print(f"{banknifty_monthly=}")
    print(f"{nifty_weekly=}")
    print(f"{nifty_next_weekly=}")


if __name__ == "__main__":
    main()
