"""
בדיקת בסיס אקראי (random baseline) - כדי לענות על השאלה "האם המערכת באמת
מזהה כניסות טובות, או שהיא סתם נכנסת לטרייד ותוצאה דומה הייתה מתקבלת
מכניסה אקראית?"

עבור כל מניה, לוקחים את אותו מספר עסקאות שהמערכת האמיתית ביצעה, ומדמים
כניסה אקראית (יום אקראי) עם בדיוק אותו כלל סטופ/יעד (ATR×1.5 / ATR×3),
חוזרים על זה הרבה פעמים (bootstrap) ומשווים את הממוצע האקראי מול המערכת.

הרצה:  python3 random_baseline.py --results backtest_results_2y.json --trials 200
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import data_fetcher
import engine

BASE_DIR = Path(__file__).parent


def simulate_random_trades(df, n_trades: int, max_hold: int, start: int, rng: random.Random):
    atr_series = engine.atr(df, 14)
    eligible_days = list(range(start, len(df) - 1))
    if len(eligible_days) < n_trades:
        return []

    entry_days = rng.sample(eligible_days, n_trades)
    trades = []
    for entry_i in sorted(entry_days):
        atr_val = atr_series.iloc[entry_i]
        if not (atr_val > 0):
            continue
        entry_price = df["Close"].iloc[entry_i]
        stop = entry_price - atr_val * 1.5
        target = entry_price + atr_val * 3.0
        risk = atr_val * 1.5

        exit_price, outcome = None, None
        for j in range(entry_i + 1, min(entry_i + 1 + max_hold, len(df))):
            hi, lo = df["High"].iloc[j], df["Low"].iloc[j]
            if lo <= stop:
                exit_price, outcome = stop, "stop"
                break
            if hi >= target:
                exit_price, outcome = target, "target"
                break
        if exit_price is None:
            last_j = min(entry_i + max_hold, len(df) - 1)
            exit_price, outcome = df["Close"].iloc[last_j], "timeout"

        r_multiple = (exit_price - entry_price) / risk
        trades.append({"r_multiple": r_multiple, "outcome": outcome})

    return trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="backtest_results_2y.json")
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--max-hold", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with open(BASE_DIR / args.results, "r", encoding="utf-8") as f:
        data = json.load(f)

    rng = random.Random(args.seed)
    per_ticker = data["per_ticker"]

    system_all_r = []
    random_trial_avgs = []  # avg R per full trial (across all tickers combined)

    ticker_dfs = {}
    ticker_n_trades = {}

    for ticker, v in per_ticker.items():
        trades = v["trades"]
        if not trades:
            continue
        ticker_n_trades[ticker] = len(trades)
        system_all_r.extend(t["r_multiple"] for t in trades)
        print(f"טוען נתונים ל-{ticker} ({len(trades)} עסקאות אמיתיות)...", flush=True)
        ticker_dfs[ticker] = data_fetcher.fetch_daily(ticker, period="2y")

    system_avg_r = sum(system_all_r) / len(system_all_r)
    system_win_rate = sum(1 for r in system_all_r if r > 0) / len(system_all_r) * 100
    print(f"\nמערכת בפועל: {len(system_all_r)} עסקאות, avg_r={system_avg_r:.3f}, win_rate={system_win_rate:.1f}%")

    print(f"\nמריץ {args.trials} סימולציות אקראיות...")
    beat_count = 0
    for trial in range(args.trials):
        trial_r = []
        for ticker, n in ticker_n_trades.items():
            df = ticker_dfs[ticker]
            trades = simulate_random_trades(df, n, args.max_hold, start=160, rng=rng)
            trial_r.extend(t["r_multiple"] for t in trades)
        if trial_r:
            avg = sum(trial_r) / len(trial_r)
            random_trial_avgs.append(avg)
            if system_avg_r > avg:
                beat_count += 1

    random_trial_avgs.sort()
    mean_random = sum(random_trial_avgs) / len(random_trial_avgs)
    percentile = beat_count / len(random_trial_avgs) * 100

    print("\n=== תוצאה ===")
    print(f"ממוצע R של המערכת: {system_avg_r:.3f}")
    print(f"ממוצע R של כניסות אקראיות (ממוצע על פני {args.trials} סימולציות): {mean_random:.3f}")
    print(f"התפלגות אקראית: min={random_trial_avgs[0]:.3f} p25={random_trial_avgs[len(random_trial_avgs)//4]:.3f} "
          f"median={random_trial_avgs[len(random_trial_avgs)//2]:.3f} p75={random_trial_avgs[3*len(random_trial_avgs)//4]:.3f} "
          f"max={random_trial_avgs[-1]:.3f}")
    print(f"המערכת עקפה את הכניסה האקראית ב-{percentile:.1f}% מהסימולציות")

    out = {
        "system_avg_r": system_avg_r,
        "system_win_rate": system_win_rate,
        "system_trade_count": len(system_all_r),
        "random_mean_avg_r": mean_random,
        "random_trial_avgs_sorted": random_trial_avgs,
        "system_beats_random_pct_of_trials": percentile,
    }
    with open(BASE_DIR / "random_baseline_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nנשמר ל-random_baseline_results.json")


if __name__ == "__main__":
    main()
