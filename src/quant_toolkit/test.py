from quant_toolkit.data_API import DBPaths
from quant_toolkit.helper import convert_symbol_to_ticker
import datetime


def main():
    dt = datetime.date(2025, 2, 27)
    symbols = DBPaths().get_index_symbols()
    for symbol in symbols:
        print(f"{symbol} -> {convert_symbol_to_ticker(symbol, dt)}")


if __name__ == "__main__":
    main()
