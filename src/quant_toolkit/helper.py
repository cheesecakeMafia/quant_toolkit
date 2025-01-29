import datetime
from quant_toolkit.datetime_API import FNOExpiry
from quant_toolkit.data_API import DBPaths


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


def convert_symbol_to_ticker(symbol: str, dt=datetime.date.today()) -> str:
    if "FUT-2" in symbol:
        return FNOExpiry().next_month_fut_expiry(symbol, dt)
    elif "FUT-1" in symbol:
        return FNOExpiry().current_month_fut_expiry(symbol, dt)
    elif "FUT" == symbol[-3:]:
        return FNOExpiry().current_month_fut_expiry(symbol, dt)
    else:
        return symbol


def main():
    obj = DBPaths().get_index_symbols()
    for sym in obj:
        print(
            f"For symbol {sym}, ticker is {convert_symbol_to_ticker(sym, dt=datetime.date(2025, 1, 30))}"
        )


if __name__ == "__main__":
    main()
