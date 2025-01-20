import pandas as pd
from typing import List, Union
import os
from pathlib import Path
import sqlite3
import datetime
from quant_toolkit.datetime_API import FNOExpiry

"""This file is a work in progress. Still need to decide on the DB of choice for storing time series data. 
    Torn between TimeScaleDB and sqlite3.
"""


class SecurityDataHandler:
    """
    A class to retrieve security data like start datetime, end datetime, duration of candlesticks, et cetera from an SQLite database.

    Schema of the table in a database is as follows-
            | datetime(index) | open | high | low | close | volume | oi(optional) |


    Attributes:
        db_path (Path): Path to the SQLite database file.


    Methods:
        _security_first_datetime(symbol: str) -> datetime.datetime:

        _security_latest_datetime(symbol: str) -> datetime.datetime:

        get_security_data(symbol: str, start_date: Union[int | None | str | datetime.datetime] = None) -> pd.DataFrame:

        get_available_symbols() -> List[str]:

        delete_security(symbol: str) -> None:

        delete_security_from_date(symbol: str, from_date: Union[int | None | str | datetime.datetime] = 252) -> None:
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not os.path.isfile(self.db_path):
            raise FileNotFoundError(f"Database file '{self.db_path}' does not exist.")
        self.db_conn = sqlite3.connect(self.db_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "db_conn"):
            self.db_conn.close()
            print("We have successfully closed the DB connection.")

    def _symbol_exists(self, symbol: str) -> bool:
        if not os.path.isfile(self.db_path):
            return False
        cursor = self.db_conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            _symbols_in_db = [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"SQLITE3 ERROR!! >> We ran into an sqlite3 exception: {e}")
        except Exception as e:
            print(f"EXCEPTION!! >> We ran into a general exception: {e}")
        finally:
            cursor.close()
        if symbol in _symbols_in_db:
            return True
        return False

    def _security_first_datetime(self, symbol: str) -> datetime.datetime:
        """Retrieves the earliest datetime available for the data of a given security symbol."""
        if self._symbol_exists(symbol):
            cursor = self.db_conn.cursor()
            if cursor.fetchone() is None:
                return datetime.datetime.now()
            cursor.execute(f"SELECT * FROM '{symbol}' ORDER BY ROWID LIMIT 1")
            start_date = datetime.datetime.strptime(
                cursor.fetchone()[0], "%Y-%m-%d %H:%M:%S"
            )
            cursor.close()
            return start_date
        else:
            print(
                f"data for symbol {symbol} doesn't exist in the DataBase at path {self.db_path}."
            )
            return datetime.datetime.now()

    def _security_latest_datetime(self, symbol: str) -> datetime.datetime:
        """Retrieves the most recent datetime available for a given security symbol."""
        if self._symbol_exists(symbol):
            cursor = self.db_conn.cursor()
            if cursor.fetchone() is None:
                return datetime.datetime.now()
            cursor.execute(f"SELECT * FROM '{symbol}' ORDER BY ROWID DESC LIMIT 1")
            latest_date = datetime.datetime.strptime(
                cursor.fetchone()[0], "%Y-%m-%d %H:%M:%S"
            )
            cursor.close()
            return latest_date
        else:
            print(
                f"data for symbol {symbol} doesn't exist in the DataBase at path {self.db_path}."
            )
            return datetime.datetime.now()

    def _convert_symbol_to_ticker(self, symbol: str) -> str:
        if "FUT" in symbol:
            if "NSE:BANKNIFTY" in symbol:
                return FNOExpiry().banknifty_current_month_fut_expiry()
            elif "NSE:FINNIFTY" in symbol:
                return FNOExpiry().finnifty_current_month_fut_expiry()
            elif "NSE:NIFTY" in symbol:
                return FNOExpiry().nifty_current_month_fut_expiry()
            else:
                return FNOExpiry().stock_current_month_fut_expiry(symbol)
        return symbol

    def get_available_securities(self) -> List[str]:
        """Retrieves a list of all available security symbols in the database."""
        if self.database_exists():
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            symbols_in_db = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return symbols_in_db
        return []

    def get_security_data(
        self,
        symbol: str,
        start_datetime: Union[int, None, str, datetime.datetime] = None,
    ) -> Union[pd.DataFrame, None]:
        """
        Retrieves security data for a given symbol from a specified start date.

        If start_date is an integer, it's treated as the number of days before the latest date.
        If the start_date is a datetime.date obj, we get the data from that date onwards.
        If start_date is a str, then we convert it into an datetime.datetime object to complete our operations.
        If start_date is None, it retrieves data from the earliest available date.

        Schema of the table in a database is as follows-
        | datetime(index) | open | high | low | close | volume | oi(optional) |
        """
        assert symbol, print("You need to pass a symbol to get the data for.")
        if not self._symbol_exists(symbol):
            print(
                f"we don't have any table for symbol {symbol} in the database {self.db_path}"
            )
            return
        if type(start_datetime) is int:
            start_datetime = self._security_latest_datetime(
                symbol
            ) - datetime.timedelta(days=start_datetime)
        elif isinstance(start_datetime, datetime.datetime):
            start_datetime = start_datetime.date()
        elif type(start_datetime) is str:
            start_datetime = datetime.datetime.strptime(
                start_datetime, "%Y-%m-%d"
            ).date()
        else:
            start_datetime = self._security_first_datetime(symbol)

        cursor = self.db_conn.cursor()
        query = f"""SELECT * FROM '{symbol}' WHERE 'datetime' >= '{start_datetime}' ORDER BY 'datetime' """
        results = pd.read_sql_query(query, self.db_conn, index_col=None)
        results["datetime"] = pd.to_datetime(
            results["datetime"], format="%Y-%m-%d %H:%M:%S"
        )
        cursor.close()
        return results

    def delete_security(self, symbol: str) -> None:
        """Deleted the whole table for the security symbol from the database."""
        assert symbol, print("You need to pass a symbol to delete data for.")
        if self._symbol_exists(symbol):
            cursor = self.db_conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS '{symbol}'")
            self.db_conn.commit()
            print(f"We have deleted the data for symbol {symbol}.")
            cursor.close()
            return None
        else:
            print(f"We don't have any symbol {symbol} in the database to delete.")

    def delete_security_from_date(
        self,
        symbol: str,
        from_datetime: Union[int | None | str | datetime.datetime] = 252,
    ) -> None:
        """Deletes the data from table of the particular security from the passed date or for the last x days if type is int."""
        assert from_datetime, print(
            "You need to either pass an 'int', 'str' or a 'datetime.datetime' obj to delete data for symbol from it's table."
        )
        if not self._symbol_exists(symbol):
            print(
                f"we don't have any table for symbol {symbol} in the database {self.db_path}"
            )
            return

        if type(from_datetime) is int:
            from_datetime = self._security_latest_datetime(symbol) - datetime.timedelta(
                days=from_datetime
            )
        elif type(from_datetime) is datetime.datetime:
            from_datetime = from_datetime.date()
        elif type(from_datetime) is str:
            from_datetime = datetime.datetime.strptime(from_datetime, "%Y-%m-%d").date()
        else:
            from_datetime = self._security_first_datetime(symbol)

        cursor = self.db_conn.cursor()
        try:
            from_datetime = datetime.datetime.strftime(
                from_datetime, format="%Y-%m-%d %H:%M-%S"
            )
            cursor.execute(
                f"""DELETE FROM '{symbol}' WHERE 'date-time'> '{from_datetime}' """
            )
            self.db_conn.commit()
            print(
                f"We have deleted data for symbol {symbol} from {from_datetime} to latest!"
            )
        except sqlite3.Error as e:
            print(f"We ran into an sqlite3 error while deleting the data: {e}")
        except Exception as e:
            print(f"We ran into a general error while deleting the data: {e}")
        finally:
            cursor.close()
        return

    def check_db_integrity(
        self,
        year: Union[int | str] = datetime.datetime.now().year - 3,
        log_csv=False,
        delete_symbol=False,
    ) -> None:
        """This method will show all the securities which have data for time less than the arg years. You could also save them
        in a .csv file and could further delete them from the universe."""
        if type(year) is str:
            year = int(year)
        symbols = self.get_available_symbols()
        df = pd.DataFrame(columns=["symbol", "start", "end"])
        for i, symbol in enumerate(symbols):
            if self._security_first_datetime(symbol) > (
                datetime.datetime.now() - datetime.timedelta(days=360 * year)
            ):
                df.loc[i, "symbol"] = symbol
                df.loc[i, "start"] = self._security_first_datetime(symbol)
                df.loc[i, "end"] = self._security_latest_datetime(symbol)
                if delete_symbol:
                    self.delete_security(symbol=symbol)
        df.reset_index(drop=True, inplace=True)
        print(df)
        if log_csv and not df.shape[0]:
            df.to_csv(
                r"/home/cheesecake/Downloads/Data/data_API/"
                + self.db_path.split("/")[-1].split(".")[0]
                + ".csv"
            )
        return

    def database_exists(self) -> bool:
        if not os.path.isfile(self.db_path):
            return False
        return True


class DBPaths:
    """This class provides the file paths of the respective databases and the list of symbols to pull."""

    def __init__(self):
        self.index_db_path = r"/home/cheesecake/Downloads/Data/index/index_data.db"
        self.futures_db_path = (
            r"/home/cheesecake/Downloads/Data/futures/futures_data.db"
        )
        self.stocks_db_path = r"/home/cheesecake/Downloads/Data/stocks/stocks_data.db"

    def get_stocks_symbols(self) -> List[str]:
        """Returns a list of symbols for the category of security from either the DB or from saved csv"""
        if os.path.isfile(self.stocks_db_path):
            return SecurityDataHandler(self.stocks_db_path).get_available_securities()

        df = pd.read_csv(r"/home/cheesecake/Downloads/fyers/utils/nse_500_stocks.csv")
        return df["Ticker"].to_list()

    def get_index_symbols(self) -> List[str]:
        """Returns a list of symbols for the category of security from either the DB or from saved csv"""
        if os.path.isfile(self.index_db_path):
            return SecurityDataHandler(self.index_db_path).get_available_securities()

        df = pd.read_csv(r"/home/cheesecake/Downloads/fyers/utils/nse_index.csv")
        return df["Ticker"].to_list()

    def get_futures_symbols(self) -> List[str]:
        """Returns a list of symbols for the category of security from either the DB or from saved csv"""
        if os.path.isfile(self.futures_db_path):
            return SecurityDataHandler(self.futures_db_path).get_available_securities()

        df = pd.read_csv(
            r"/home/cheesecake/Downloads/fyers/utils/nse_fyers_futures.csv"
        )
        return df["Ticker"].to_list()


if __name__ == "__main__":
    print(DBPaths().get_index_symbols())
    print(DBPaths().get_futures_symbols())
    print(DBPaths().get_stocks_symbols())
    print(DBPaths().futures_db_path)
    print(DBPaths().stocks_db_path)
    print(DBPaths().index_db_path)
