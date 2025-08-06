#!/usr/bin/env python3
"""Test expiry dates for NIFTY and SENSEX on 2025-08-06."""

import datetime
from src.quant_toolkit.market_contracts import (
    ContractGenerator,
    MarketCalendar,
    Exchange,
)


def main():
    # Today's date: 2025-08-06 (Wednesday)
    today = datetime.date(2025, 12, 25)

    gen = ContractGenerator()
    calendar = MarketCalendar()

    print("\n" + "=" * 80)
    print(f"EXPIRY DATES FOR: {today} ({today.strftime('%A, %B %d, %Y')})")
    print("=" * 80)

    # Check if today is a holiday
    if not calendar.is_trading_day(today):
        adjusted = gen._adjust_reference_date(today)
        print(f"⚠️  {today} is a holiday/weekend")
        print(
            f"📅 Using next trading day as reference: {adjusted} ({adjusted.strftime('%A')})"
        )
        print("=" * 80)

    # Calculate expiry dates
    nse_current_week = calendar.find_current_week_expiry(today, Exchange.NSE)
    nse_next_week = calendar.find_next_week_expiry(today, Exchange.NSE)
    nse_current_month = calendar.find_current_month_expiry(today, Exchange.NSE)
    nse_next_month = calendar.find_next_month_expiry(today, Exchange.NSE)

    bse_current_week = calendar.find_current_week_expiry(today, Exchange.BSE)
    bse_next_week = calendar.find_next_week_expiry(today, Exchange.BSE)
    bse_current_month = calendar.find_current_month_expiry(today, Exchange.BSE)
    bse_next_month = calendar.find_next_month_expiry(today, Exchange.BSE)

    # Format as table
    print(
        "\n| Index   | Exchange | Expiry Type      | Date       | Day       | Ticker Example                |"
    )
    print(
        "|---------|----------|------------------|------------|-----------|-------------------------------|"
    )

    # NIFTY (NSE - Thursday expiry)
    print(
        f"| NIFTY   | NSE      | Current Week     | {nse_current_week} | {nse_current_week.strftime('%A')[:3]} | {gen.current_week_option(Exchange.NSE, 'NIFTY', 25000, 'CE', today)} |"
    )
    print(
        f"| NIFTY   | NSE      | Next Week        | {nse_next_week} | {nse_next_week.strftime('%A')[:3]} | {gen.next_week_option(Exchange.NSE, 'NIFTY', 25000, 'PE', today)} |"
    )
    print(
        f"| NIFTY   | NSE      | Current Month    | {nse_current_month} | {nse_current_month.strftime('%A')[:3]} | {gen.current_month_option(Exchange.NSE, 'NIFTY', 25000, 'CE', today)} |"
    )
    print(
        f"| NIFTY   | NSE      | Next Month       | {nse_next_month} | {nse_next_month.strftime('%A')[:3]} | {gen.next_month_option(Exchange.NSE, 'NIFTY', 25000, 'PE', today)} |"
    )

    print(
        "|---------|----------|------------------|------------|-----------|-------------------------------|"
    )

    # SENSEX (BSE - Tuesday expiry)
    print(
        f"| SENSEX  | BSE      | Current Week     | {bse_current_week} | {bse_current_week.strftime('%A')[:3]} | {gen.current_week_option(Exchange.BSE, 'SENSEX', 80000, 'CE', today)} |"
    )
    print(
        f"| SENSEX  | BSE      | Next Week        | {bse_next_week} | {bse_next_week.strftime('%A')[:3]} | {gen.next_week_option(Exchange.BSE, 'SENSEX', 80000, 'PE', today)} |"
    )
    print(
        f"| SENSEX  | BSE      | Current Month    | {bse_current_month} | {bse_current_month.strftime('%A')[:3]} | {gen.current_month_option(Exchange.BSE, 'SENSEX', 80000, 'CE', today)} |"
    )
    print(
        f"| SENSEX  | BSE      | Next Month       | {bse_next_month} | {bse_next_month.strftime('%A')[:3]} | {gen.next_month_option(Exchange.BSE, 'SENSEX', 80000, 'PE', today)} |"
    )

    print("\n" + "=" * 80)
    print("CALENDAR REFERENCE FOR DECEMBER 2025:")
    print("=" * 80)
    print("""
    December 2025
    Mo Tu We Th Fr Sa Su
     1  2  3  4  5  6  7
     8  9 10 11 12 13 14
    15 16 17 18 19 20 21
    22 23 24 25 26 27 28
    29 30 31
    
    Dec 25: Christmas (Holiday - Thursday)
    Adjusted to: Dec 26 (Friday)
    NSE Weekly: Thursdays
    BSE Weekly: Tuesdays
    NSE Monthly: Last Thursday (Dec 25 -> Dec 24)
    BSE Monthly: Last Tuesday (Dec 30)
    """)

    print("=" * 80)
    print("FUTURES CONTRACTS:")
    print("=" * 80)

    # Futures examples
    nifty_current_fut = gen.current_month_future(Exchange.NSE, "NIFTY", today)
    nifty_next_fut = gen.next_month_future(Exchange.NSE, "NIFTY", today)
    sensex_current_fut = gen.current_month_future(Exchange.BSE, "SENSEX", today)
    sensex_next_fut = gen.next_month_future(Exchange.BSE, "SENSEX", today)

    print(f"NIFTY Current Month Future: {nifty_current_fut}")
    print(f"NIFTY Next Month Future:    {nifty_next_fut}")
    print(f"SENSEX Current Month Future: {sensex_current_fut}")
    print(f"SENSEX Next Month Future:    {sensex_next_fut}")


if __name__ == "__main__":
    main()
