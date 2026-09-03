"""ניתוח אבחוני: אילו פרמטרים בכניסה בפועל מנבאים הצלחה, ואילו הם רעש/פיגור."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).parent


def bucket_stats(trades, key_fn, label):
    buckets = {}
    for t in trades:
        k = key_fn(t)
        buckets.setdefault(k, []).append(t["r_multiple"])
    print(f"\n--- {label} ---")
    for k in sorted(buckets, key=str):
        rs = buckets[k]
        wins = sum(1 for r in rs if r > 0)
        avg = sum(rs) / len(rs)
        print(f"  {k}: n={len(rs)}  win_rate={wins/len(rs)*100:.1f}%  avg_r={avg:.3f}  total_r={sum(rs):.2f}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "backtest_diag_3y.json"
    data = json.load(open(BASE_DIR / path, encoding="utf-8"))

    all_trades = []
    for ticker, v in data["per_ticker"].items():
        all_trades.extend(v["trades"])

    print(f"סה\"כ עסקאות: {len(all_trades)}")

    bucket_stats(all_trades, lambda t: t["had_reversal_pattern"], "עם תבנית היפוך (near S/R) מול בלי")
    bucket_stats(all_trades, lambda t: t["crossed_ma_cross"], "עם חציית MA150 (עד 20 בר אחורה) מול בלי")
    bucket_stats(all_trades, lambda t: t["high_volume"], "עם נפח גבוה מול בלי")
    bucket_stats(all_trades, lambda t: t["near_support"], "קרוב לתמיכה (פיבוט) מול לא")
    bucket_stats(all_trades, lambda t: t["vp_near_support"], "קרוב ל-Volume Profile תמיכה מול לא")

    def ext_bucket(t):
        e = t["extension_atr"]
        if e < 0:
            return "מתחת ל-MA50"
        if e < 1:
            return "0-1 ATR מעל MA50"
        if e < 2:
            return "1-2 ATR מעל MA50"
        if e < 3:
            return "2-3 ATR מעל MA50"
        return "3+ ATR מעל MA50 (מתוח מאוד)"

    bucket_stats(all_trades, ext_bucket, "מרחק מ-MA50 ביחידות ATR (extension) בכניסה")

    # שילוב: תבנית היפוך + לא מתוח
    def combo(t):
        fresh = t["extension_atr"] < 1.5
        return f"reversal={t['had_reversal_pattern']} fresh(<1.5ATR)={fresh}"

    bucket_stats(all_trades, combo, "שילוב: תבנית היפוך + לא מתוח")

    # שכיחות תבניות בודדות בעסקאות מנצחות מול מפסידות
    win_patterns = Counter()
    loss_patterns = Counter()
    for t in all_trades:
        target = win_patterns if t["r_multiple"] > 0 else loss_patterns
        for p in t["active_patterns"]:
            target[p] += 1
    print("\n--- שכיחות תבניות בעסקאות מנצחות ---")
    for p, c in win_patterns.most_common(15):
        print(f"  {p}: {c}")
    print("\n--- שכיחות תבניות בעסקאות מפסידות ---")
    for p, c in loss_patterns.most_common(15):
        print(f"  {p}: {c}")


if __name__ == "__main__":
    main()
