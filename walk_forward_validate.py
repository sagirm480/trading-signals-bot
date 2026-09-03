"""
אימות חוץ-מדגמי אמיתי (out-of-sample): מושך 5 שנות היסטוריה, ומריץ את
התצורה הקבועה הנוכחית (בלי לשנות אותה!) על כל הטווח. אז מפצל את העסקאות
לפי תאריך כניסה: "עתיק" (לפני 2023-08, אף פעם לא נגענו בו בשום אבחון/כיול
השבוע) מול "עדכני" (2023-08 ואילך, החלון שבו כן אבחנו וכיילנו). אם התוצאות
דומות בשני החלונות - זו עדות אמיתית שהכיול לא סתם overfitting לנתונים
שראינו. אם התקופה העתיקה נראית הרבה יותר גרועה - זה דגל אדום כן.

הרצה:  python3 walk_forward_validate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import backtest
import data_fetcher

BASE_DIR = Path(__file__).parent
CUTOFF_DATE = "2023-08-08"  # לפני התאריך הזה = דאטה שלא נגענו בו בשום כיול


def main():
    cfg = backtest.load_config()
    cfg["backtest_period"] = "5y"

    old_trades, recent_trades = [], []
    per_ticker = {}

    for ticker in cfg["watchlist"]:
        print(f"מריץ אימות חוץ-מדגמי: {ticker} ...", flush=True)
        try:
            res = backtest.simulate_ticker(ticker, cfg, max_hold=40)
        except Exception as e:
            print(f"  {ticker}: שגיאה - {e}")
            continue
        trades = res.get("trades", [])
        per_ticker[ticker] = trades
        for t in trades:
            if t["entry_date"] < CUTOFF_DATE:
                old_trades.append(t)
            else:
                recent_trades.append(t)
        print(f"  {ticker}: {len(trades)} עסקאות סה\"כ")

    old_summary = backtest.summarize(old_trades)
    recent_summary = backtest.summarize(recent_trades)

    print("\n=== תקופה עתיקה (לפני 2023-08, לא נגענו בה בשום כיול) ===")
    print(old_summary)
    print("\n=== תקופה עדכנית (2023-08 ואילך, שימשה לאבחון/כיול) ===")
    print(recent_summary)

    with open(BASE_DIR / "walk_forward_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "cutoff_date": CUTOFF_DATE,
            "old_unseen_summary": old_summary,
            "recent_tuned_summary": recent_summary,
            "old_unseen_trades": old_trades,
            "recent_tuned_trades": recent_trades,
        }, f, ensure_ascii=False, indent=2)
    print("\nנשמר ל-walk_forward_results.json")


if __name__ == "__main__":
    main()
