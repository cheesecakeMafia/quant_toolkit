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
    assert symbol, print("You need to pass a symbol to convert to ticker.")
    if "FUT" in symbol:
        if "NIFTY50" in symbol:
            if "II" in symbol:
                return FNOExpiry().nifty_next_month_fut_expiry(dt)
            else:
                return FNOExpiry().nifty_current_month_fut_expiry(dt)
        elif "BANKNIFTY" in symbol:
            if "II" in symbol:
                return FNOExpiry().banknifty_next_month_fut_expiry(dt)
            else:
                return FNOExpiry().banknifty_current_month_fut_expiry(dt)
        elif "NIFTY" in symbol:
            if "II" in symbol:
                return FNOExpiry().index_next_month_fut_expiry(symbol, dt)
            else:
                return FNOExpiry().index_current_month_fut_expiry(symbol, dt)
        else:
            return FNOExpiry().stock_current_month_fut_expiry(symbol, dt)
    return symbol


def main():
    obj = DBPaths().get_index_symbols()
    for sym in obj:
        print(
            f"For symbol {sym}, ticker is {convert_symbol_to_ticker(sym, dt=datetime.date(2025, 1, 30))}"
        )


if __name__ == "__main__":
    main()

"""
Result on 23 of Jan 2025 which is the monthly expiry 

For symbol NSE:INDIAVIX-INDEX, ticker is NSE:INDIAVIX-INDEX
For symbol NSE:NIFTY50-INDEX, ticker is NSE:NIFTY50-INDEX
For symbol NSE:NIFTY-FUT-I, ticker is NSE:NIFTY25JANFUT
For symbol NSE:NIFTY-FUT-II, ticker is NSE:NIFTY25FEBFUT
For symbol NSE:NIFTYBANK-INDEX, ticker is NSE:NIFTYBANK-INDEX
For symbol NSE:BANKNIFTY-FUT-I, ticker is NSE:BANKNIFTY25JANFUT
For symbol NSE:BANKNIFTY-FUT-II, ticker is NSE:BANKNIFTY25FEBFUT
For symbol NSE:FINNIFTY-INDEX, ticker is NSE:FINNIFTY-INDEX
For symbol NSE:FINNIFTY-FUT-I, ticker is NSE:FINNIFTY25JANFUT
For symbol NSE:FINNIFTY-FUT-II, ticker is NSE:FINNIFTY25FEBFUT
For symbol NSE:MIDCPNIFTY-INDEX, ticker is NSE:MIDCPNIFTY-INDEX
For symbol NSE:MIDCPNIFTY-FUT-I, ticker is NSE:MIDCPNIFTY25JANFUT
For symbol NSE:MIDCPNIFTY-FUT-II, ticker is NSE:MIDCPNIFTY25FEBFUT
For symbol NSE:NIFTYNXT50-INDEX, ticker is NSE:NIFTYNXT50-INDEX
For symbol NSE:NIFTYNXT50-FUT-I, ticker is NSE:NIFTYNXT5025JANFUT
For symbol NSE:NIFTYNXT50-FUT-II, ticker is NSE:NIFTYNXT5025FEBFUT

Please also run this code on any day after 23 Jan to check the 
"""
