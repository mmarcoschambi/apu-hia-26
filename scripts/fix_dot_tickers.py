#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys

DB_PATH = "data/ticker_cache.db"

# List of tickers to merge: (dot_version, dash_version)
TICKERS_TO_FIX = [
    ("BF.A", "BF-A"),
    ("BF.B", "BF-B"),
    ("BRK.B", "BRK-B"),
    ("HEI.A", "HEI-A"),
    ("LEN.B", "LEN-B")
]

def main():
    parser = argparse.ArgumentParser(description="Merge dot tickers to dash counterpart in SQLite database.")
    parser.add_argument("--execute", action="store_true", help="Actually apply the changes to the database. If not set, runs in dry-run mode.")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        sys.exit(1)

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    is_dry_run = not args.execute
    if is_dry_run:
        print("=== DRY RUN MODE: No changes will be saved ===")
    else:
        print("=== EXECUTE MODE: Changes will be applied to the database ===")

    try:
        # Check current status
        print("\n--- Diagnostic Check ---")
        for dot_t, dash_t in TICKERS_TO_FIX:
            dot_ohlcv = cursor.execute("SELECT COUNT(*) FROM ohlcv_cache WHERE ticker = ?", (dot_t,)).fetchone()[0]
            dash_ohlcv = cursor.execute("SELECT COUNT(*) FROM ohlcv_cache WHERE ticker = ?", (dash_t,)).fetchone()[0]
            dot_rs = cursor.execute("SELECT COUNT(*) FROM daily_rs_rankings WHERE ticker = ?", (dot_t,)).fetchone()[0]
            dash_rs = cursor.execute("SELECT COUNT(*) FROM daily_rs_rankings WHERE ticker = ?", (dash_t,)).fetchone()[0]
            dot_pit = cursor.execute("SELECT COUNT(*) FROM pit_constituents WHERE ticker = ?", (dot_t,)).fetchone()[0]
            dash_pit = cursor.execute("SELECT COUNT(*) FROM pit_constituents WHERE ticker = ?", (dash_t,)).fetchone()[0]
            
            print(f"Ticker Pair ({dot_t} -> {dash_t}):")
            print(f"  ohlcv_cache: {dot_t}={dot_ohlcv} rows | {dash_t}={dash_ohlcv} rows")
            print(f"  daily_rs_rankings: {dot_t}={dot_rs} rows | {dash_t}={dash_rs} rows")
            print(f"  pit_constituents: {dot_t}={dot_pit} rows | {dash_t}={dash_pit} rows")

        # Perform Merge / Update Operations
        print("\n--- Merging and Updating ---")
        for dot_t, dash_t in TICKERS_TO_FIX:
            # 1. Merge ohlcv_cache from dot to dash (INSERT OR IGNORE to prevent duplicate primary keys)
            # The ohlcv_cache table has PRIMARY KEY (ticker, date).
            # We select all records from dot_t, change ticker to dash_t, and insert them if not exists.
            print(f"Merging ohlcv_cache: {dot_t} -> {dash_t}...")
            
            # Find how many rows would actually be copied (dates in dot that are not in dash)
            new_dates = cursor.execute(
                """
                SELECT COUNT(*) FROM ohlcv_cache 
                WHERE ticker = ? AND date NOT IN (SELECT date FROM ohlcv_cache WHERE ticker = ?)
                """, (dot_t, dash_t)
            ).fetchone()[0]
            print(f"  Dates to merge from {dot_t} to {dash_t}: {new_dates}")

            if not is_dry_run:
                # Perform the merge
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO ohlcv_cache (
                        ticker, date, open, high, low, close, volume, dollar_volume,
                        rolling_dollar_vol_20, sma20, sma50, adr_pct_20, adr_pct_14,
                        sma_50, sma_200, trend_aligned, price_above_sma50, price_above_sma200,
                        sma50_above_sma200, avg_volume_20, adr_14, market_cap, ema_8, ema_21,
                        sma100, sma200
                    )
                    SELECT 
                        ? as ticker, date, open, high, low, close, volume, dollar_volume,
                        rolling_dollar_vol_20, sma20, sma50, adr_pct_20, adr_pct_14,
                        sma_50, sma_200, trend_aligned, price_above_sma50, price_above_sma200,
                        sma50_above_sma200, avg_volume_20, adr_14, market_cap, ema_8, ema_21,
                        sma100, sma200
                    FROM ohlcv_cache WHERE ticker = ?
                    """, (dash_t, dot_t)
                )
                print(f"  Merged records into {dash_t}.")

                # Delete dot_t records from ohlcv_cache
                cursor.execute("DELETE FROM ohlcv_cache WHERE ticker = ?", (dot_t,))
                print(f"  Deleted {dot_t} records from ohlcv_cache.")

            # 2. Update pit_constituents: normalise dot_t -> dash_t
            pit_rows = cursor.execute("SELECT COUNT(*) FROM pit_constituents WHERE ticker = ?", (dot_t,)).fetchone()[0]
            print(f"Updating pit_constituents: {dot_t} -> {dash_t} ({pit_rows} rows to update)...")
            
            if not is_dry_run and pit_rows > 0:
                # Update rows in pit_constituents. To prevent primary key conflicts (date, ticker, index_member), 
                # we do INSERT OR IGNORE / UPDATE OR REPLACE depending on behavior. Since date/ticker/index_member is PK,
                # let's update. If dash_t already exists for the same date and index_member, we can delete the dot_t row.
                # Let's do a safe update:
                # First delete any dot_t row where dash_t already exists for the same date and index_member
                cursor.execute(
                    """
                    DELETE FROM pit_constituents
                    WHERE ticker = ?
                      AND date || index_member IN (
                          SELECT date || index_member FROM pit_constituents WHERE ticker = ?
                      )
                    """, (dot_t, dash_t)
                )
                # Then update the remaining dot_t rows
                cursor.execute("UPDATE pit_constituents SET ticker = ? WHERE ticker = ?", (dash_t, dot_t))
                print(f"  Updated pit_constituents.")

            # 3. Clean up any remaining dot_t rows in daily_rs_rankings (since they will be re-populated as dash_t)
            rs_rows = cursor.execute("SELECT COUNT(*) FROM daily_rs_rankings WHERE ticker = ?", (dot_t,)).fetchone()[0]
            if rs_rows > 0:
                print(f"Deleting {dot_t} records from daily_rs_rankings ({rs_rows} rows)...")
                if not is_dry_run:
                    cursor.execute("DELETE FROM daily_rs_rankings WHERE ticker = ?", (dot_t,))
                    print(f"  Deleted {dot_t} records from daily_rs_rankings.")

        if not is_dry_run:
            conn.commit()
            print("\nDatabase transactions committed successfully!")
        else:
            print("\nDry run completed. No changes were committed.")

    except Exception as e:
        conn.rollback()
        print(f"\nError occurred: {e}")
        print("Database transaction rolled back.")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
