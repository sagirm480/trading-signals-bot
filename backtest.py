"""
בקטסטר היסטורי - הליכה קדימה (walk-forward) על נתונים יומיים: בכל יום מריץ
את אותה engine.analyze() שהמערכת החיה משתמשת בה על הנתונים הידועים עד אותו
יום בלבד (ללא הצצה קדימה), ופותח "עסקה" בדיוק כמו שהיה קורה בהתראת טלגרם -
רק כשהאות משתנה. סטופ/יעד זהים ללוגיקה ב-advisory.py (ATR×1.5 / ATR×3, יחס 1:2).

הרצה:  python3 backtest.py [--period 3y] [--max-hold 40]
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

import data_fetcher
import engine
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent


def load_config() -> dict:
    with open(BASE_DIR / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def simulate_ticker(ticker: str, cfg: dict, max_hold: int) -> dict:
    df = data_fetcher.fetch_daily(ticker, period=cfg.get("backtest_period", "3y"))
    if len(df) < 200:
        return {"ticker": ticker, "trades": [], "error": "not_enough_history"}

    th = cfg["thresholds"]
    trades = []
    open_trade = None  # {"direction","entry_i","entry_price","stop","target"}
    prev_direction = "none"

    start = 160
    for i in range(start, len(df)):
        window = df.iloc[: i + 1]
        result = engine.analyze(window, cfg)
        if "error" in result:
            continue

        enabled = cfg.get("signals_enabled", {"buy": True, "sell": True})
        direction = (
            "buy" if enabled.get("buy", True) and result["buy_score_pct"] >= th["buy"]
            else "sell" if enabled.get("sell", True) and result["sell_score_pct"] >= th["sell"]
            else "none"
        )

        # בדיקת יציאה מעסקה פתוחה (סטופ/יעד/פקיעת זמן) - נבדק לפני כניסה חדשה
        if open_trade is not None:
            hi, lo, close_today = df["High"].iloc[i], df["Low"].iloc[i], df["Close"].iloc[i]
            days_held = i - open_trade["entry_i"]
            exit_price = None
            outcome = None

            if open_trade["direction"] == "buy":
                if lo <= open_trade["stop"]:
                    exit_price, outcome = open_trade["stop"], "stop"
                elif hi >= open_trade["target"]:
                    exit_price, outcome = open_trade["target"], "target"
            else:
                if hi >= open_trade["stop"]:
                    exit_price, outcome = open_trade["stop"], "stop"
                elif lo <= open_trade["target"]:
                    exit_price, outcome = open_trade["target"], "target"

            if exit_price is None and days_held >= max_hold:
                exit_price, outcome = close_today, "timeout"

            if exit_price is not None:
                risk = open_trade["risk"]
                if open_trade["direction"] == "buy":
                    r_multiple = (exit_price - open_trade["entry_price"]) / risk
                else:
                    r_multiple = (open_trade["entry_price"] - exit_price) / risk
                trades.append({
                    "direction": open_trade["direction"],
                    "entry_date": str(df.index[open_trade["entry_i"]].date()),
                    "exit_date": str(df.index[i].date()),
                    "entry_price": round(open_trade["entry_price"], 2),
                    "exit_price": round(exit_price, 2),
                    "outcome": outcome,
                    "r_multiple": round(r_multiple, 2),
                    "days_held": days_held,
                    "active_patterns": open_trade["active_patterns"],
                    "extension_atr": round(open_trade["extension_atr"], 2),
                    "crossed_ma_cross": open_trade["crossed_ma_cross"],
                    "high_volume": open_trade["high_volume"],
                    "near_support": open_trade["near_support"],
                    "vp_near_support": open_trade["vp_near_support"],
                    "had_reversal_pattern": open_trade["had_reversal_pattern"],
                })
                open_trade = None

        # כניסה חדשה - רק במעבר מצב (בדיוק כמו התראת הטלגרם החיה)
        if open_trade is None and direction != "none" and direction != prev_direction:
            entry_price = result["close"]
            atr_val = result["atr"]
            if direction == "buy":
                stop = entry_price - atr_val * 1.5
                target = entry_price + atr_val * 3.0
                active_patterns = list(result["active_bull"])
                crossed = result["crossed_above_150"]
                near_sup = result["near_support"]
                vp_sup = result["vp_near_support"]
            else:
                stop = entry_price + atr_val * 1.5
                target = entry_price - atr_val * 3.0
                active_patterns = list(result["active_bear"])
                crossed = result.get("crossed_below_150", False)
                near_sup = result.get("near_resistance", False)
                vp_sup = result.get("vp_near_resistance", False)

            reversal_patterns = {
                "hammer", "inverted_hammer", "hanging_man", "shooting_star",
                "bullish_engulfing", "bearish_engulfing", "bullish_harami", "bearish_harami",
                "piercing_line", "dark_cloud_cover", "morning_star", "evening_star",
                "tweezer_bottom", "tweezer_top", "double_bottom", "double_top",
                "triple_bottom", "triple_top", "inverse_head_shoulders", "head_shoulders",
                "rounding_bottom", "rounding_top",
            }
            had_reversal = any(p in reversal_patterns for p in active_patterns)

            open_trade = {
                "direction": direction,
                "entry_i": i,
                "entry_price": entry_price,
                "stop": stop,
                "target": target,
                "risk": atr_val * 1.5,
                "active_patterns": active_patterns,
                "extension_atr": result["extension_atr"],
                "crossed_ma_cross": crossed,
                "high_volume": result["high_volume"],
                "near_support": near_sup,
                "vp_near_support": vp_sup,
                "had_reversal_pattern": had_reversal,
            }

        prev_direction = direction

    return {"ticker": ticker, "trades": trades}


def summarize(trades: list) -> dict:
    if not trades:
        return {"count": 0, "win_rate": None, "avg_r": None, "total_r": 0.0, "profit_factor": None}
    wins = [t for t in trades if t["r_multiple"] > 0]
    losses = [t for t in trades if t["r_multiple"] <= 0]
    total_r = sum(t["r_multiple"] for t in trades)
    gross_win = sum(t["r_multiple"] for t in wins)
    gross_loss = abs(sum(t["r_multiple"] for t in losses))
    return {
        "count": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_r": round(total_r / len(trades), 2),
        "total_r": round(total_r, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="3y")
    parser.add_argument("--max-hold", type=int, default=40)
    parser.add_argument("--out", default="backtest_results.json")
    args = parser.parse_args()

    cfg = load_config()
    cfg["backtest_period"] = args.period

    all_results = {}
    all_trades = []

    for ticker in cfg["watchlist"]:
        print(f"מריץ בקטסט: {ticker} ...", flush=True)
        try:
            res = simulate_ticker(ticker, cfg, args.max_hold)
        except Exception as e:
            print(f"  {ticker}: שגיאה - {e}")
            continue
        trades = res.get("trades", [])
        summary = summarize(trades)
        all_results[ticker] = {"summary": summary, "trades": trades}
        all_trades.extend(trades)
        print(f"  {ticker}: {summary}")

    overall = summarize(all_trades)
    print("\n=== סיכום כולל ===")
    print(overall)

    with open(BASE_DIR / args.out, "w", encoding="utf-8") as f:
        json.dump({"overall": overall, "per_ticker": all_results}, f, ensure_ascii=False, indent=2)
    print(f"\nנשמר ל-{args.out}")


if __name__ == "__main__":
    main()
