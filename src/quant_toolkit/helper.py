import datetime
from quant_toolkit.datetime_API import FNOExpiry
from quant_toolkit.data_API import DBPaths
from pathlib import Path
from typing import Union


def data_batches(
    start_date: datetime.date = datetime.date(2017, 1, 1),
    end_date: datetime.date = datetime.date.today() - datetime.timedelta(1),
    batch_size: int = 95,
) -> list[dict]:
    """_summary_
    This function takes in a datetime.date object with starting and ending date and then returns a list of dicts.
    Args:
     start_date (datetime.date, optional): Defaults to datetime.date(2017,1,1).
     end_date (datetime.date, optional): Defaults to datetime.date.today()-datetime.timedelta(1).
     batch_size (int, optional): Defaults to 95. This is because the API can only send 100 days worth of da in one call.

    Returns:
     list: Returns a list with each element being a dict. The dict has two keys, start and end.
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
    symbol: str, dt: datetime.date = datetime.date.today()
) -> str:
    assert symbol, print("You need to pass a symbol to convert it to a ticker.")
    if "FUT" in symbol:
        if "2" in symbol:
            return FNOExpiry().next_month_fut_expiry(symbol, dt)
        return FNOExpiry().current_month_fut_expiry(symbol, dt)
    else:
        return symbol


def check_last_modified(
    file_path: Union[str, Path], days: Union[int, datetime.date, datetime.datetime]
) -> bool:
    """
    Check if a file's last modification time is older than specified days or date.

    Args:
        file_path (Union[str, Path]): Path to the file to check
        days (Union[int, date]): Number of days or specific date to compare against

    Returns:
        bool: True if file is older than specified days/date, False otherwise

    Raises:
        FileNotFoundError: If the specified file doesn't exist
        TypeError: If days parameter is neither an integer nor a date object
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
    elif type(days) is datetime.date:
        # Convert file_time to date for comparison with date object
        return file_time.date() < days
    elif type(days) is datetime.datetime:
        return file_time < days
    else:
        raise TypeError(
            "days parameter must be either an int, a datetime.date or a datetime.datetime object"
        )


def main():
    obj = DBPaths().get_index_symbols()
    for sym in obj:
        print(
            f"For symbol {sym}, ticker is {convert_symbol_to_ticker(sym, dt=datetime.date(2025, 1, 30))}"
        )
    days = datetime.datetime(2025, 1, 30)
    file_path = r"/home/cheesecake/Quant/quant_toolkit/pyproject.toml"
    # file_path = r"/home/cheesecake/Quant/quant_toolkit/src/quant_toolkit/data_API.py"
    print(check_last_modified(file_path, days))


if __name__ == "__main__":
    main()
