"""
סיכום ביצועי ה-paper trading החי - זו העדות האמיתית היחידה (out-of-sample,
forward) לשאלה האם יש כאן יתרון סטטיסטי. תוצאות בקטסט לא מחליפות את זה.

הרצה:  python3 paper_trading_summary.py
"""
from __future__ import annotations

import json
from pathlib import Path

import positions as pos_mgr

BASE_DIR = Path(__file__).parent


def main():
    log = pos_mgr.load_trade_log()
    open_positions = pos_mgr.load_positions()

    print(f"פוזיציות פתוחות כרגע: {len(open_positions)}")
    for t, p in open_positions.items():
        print(f"  {t}: נכנס {p['entry_date']} ב-{p['entry_price']}, סטופ {p['stop']}, יעד {p['target']}")

    if not log:
        print("\nעדיין אין עסקאות סגורות ב-live/paper trading. זה בסדר - זה בדיוק העדות שאנחנו צריכים לצבור עם הזמן.")
        return

    wins = [t for t in log if t["r_multiple"] > 0]
    total_r = sum(t["r_multiple"] for t in log)
    total_pnl = sum(t["pnl_dollars"] for t in log)

    print(f"\n=== עסקאות live/paper סגורות: {len(log)} ===")
    print(f"שיעור הצלחה: {len(wins)/len(log)*100:.1f}%")
    print(f"R ממוצע: {total_r/len(log):.3f}")
    print(f"סה\"כ R: {total_r:.2f}")
    print(f"רווח/הפסד מצטבר: ${total_pnl:+.2f}")
    print("\nהערה: ככל שיצטברו יותר עסקאות live, כך התוצאה הזו הופכת אמינה יותר -")
    print("בניגוד לבקטסט, אין כאן שום סיכון ל-overfitting כי הדאטה לא היה זמין מראש.")

    print("\n--- כל העסקאות ---")
    for t in log:
        print(f"  {t['ticker']}: {t['entry_date']}→{t['exit_date']} ({t['outcome']}) R={t['r_multiple']:+.2f} ${t['pnl_dollars']:+.2f}")


if __name__ == "__main__":
    main()
