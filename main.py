"""
מערכת ההתראות הראשית - לולאה רצה שבודקת את רשימת המעקב בשעות המסחר,
מחשבת ניקוד (יומי מלא + 4H/שבועי קל) ושולחת התראת טלגרם כשמצב האות
משתנה (כניסה חדשה ל-buy/sell, לא חוזרת על אותה התראה כל מחזור).

הרצה חד-פעמית לבדיקה:   python3 main.py --once
הרצה רציפה (ברירת מחדל): python3 main.py
"""
from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

import data_fetcher
import engine
import positions as pos_mgr
import telegram_notifier
from advisory import build_exit_message, build_message

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "state.json"


def load_config() -> dict:
    with open(BASE_DIR / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_market_open(cfg: dict) -> bool:
    tz = ZoneInfo(cfg["market_timezone"])
    now = datetime.now(tz)
    if now.weekday() >= 5:  # שבת/ראשון
        return False
    open_h, open_m = map(int, cfg["market_open"].split(":"))
    close_h, close_m = map(int, cfg["market_close"].split(":"))
    open_t = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    close_t = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    return open_t <= now <= close_t


def process_ticker(ticker: str, cfg: dict, state: dict, open_positions: dict) -> None:
    frames = data_fetcher.fetch_all_timeframes(ticker)
    daily, h4, weekly = frames["daily"], frames["4h"], frames["weekly"]

    if daily.empty or len(daily) < 160:
        print(f"  {ticker}: אין מספיק היסטוריה יומית - מדלג")
        return

    today_date = str(daily.index[-1].date())

    # --- 1. בדיקת יציאה מפוזיציה פתוחה (סטופ/יעד/פקיעת זמן) ---
    if ticker in open_positions:
        exit_info = pos_mgr.check_exit(
            ticker, open_positions[ticker],
            today_high=daily["High"].iloc[-1], today_low=daily["Low"].iloc[-1],
            today_close=daily["Close"].iloc[-1], today_date=today_date,
        )
        if exit_info:
            pos_mgr.append_trade_log(exit_info)
            del open_positions[ticker]
            pos_mgr.save_positions(open_positions)
            sent = telegram_notifier.send_message(build_exit_message(exit_info))
            print(f"  {ticker}: פוזיציה נסגרה ({exit_info['outcome']}, R={exit_info['r_multiple']:+.2f}) - התראה {'נשלחה' if sent else 'נכשלה'}")

    result = engine.analyze(daily, cfg)
    if "error" in result:
        print(f"  {ticker}: {result['error']}")
        return

    h4_buy, h4_sell = engine.htf_score(h4) if not h4.empty else (0.0, 0.0)
    w_buy, w_sell = engine.htf_score(weekly) if not weekly.empty else (0.0, 0.0)

    th = cfg["thresholds"]
    enabled = cfg.get("signals_enabled", {"buy": True, "sell": True})
    buy_signal = enabled.get("buy", True) and result["buy_score_pct"] >= th["buy"]
    sell_signal = enabled.get("sell", True) and result["sell_score_pct"] >= th["sell"]

    direction = "buy" if buy_signal else "sell" if sell_signal else "none"
    prev = state.get(ticker, "none")

    print(
        f"  {ticker}: קנייה={result['buy_score_pct']}% מכירה={result['sell_score_pct']}% "
        f"4H(B/S)={h4_buy:.0f}/{h4_sell:.0f} שבועי(B/S)={w_buy:.0f}/{w_sell:.0f} -> {direction}"
    )

    # --- 2. כניסה חדשה - רק במעבר מצב, ורק לכיוון קנייה (ניהול פוזיציה חי בנוי לכיוון אחד כרגע) ---
    if direction != "none" and direction != prev:
        position_info, skip_reason = None, None
        if direction == "buy":
            can_open, reason = pos_mgr.can_open_position(ticker, cfg, open_positions)
            if can_open:
                atr_val = result["atr"]
                entry_price = result["close"]
                stop = entry_price - atr_val * 1.5
                target = entry_price + atr_val * 3.0
                position_info = pos_mgr.open_position(
                    ticker, cfg, open_positions, today_date, entry_price, stop, target, atr_val
                )
            else:
                skip_reason = reason

        msg = build_message(ticker, result, h4_buy, h4_sell, w_buy, w_sell, direction, th,
                             position_info=position_info, skip_reason=skip_reason)
        sent = telegram_notifier.send_message(msg)
        print(f"    התראה {'נשלחה' if sent else 'נכשלה'} ({direction})")

    state[ticker] = direction


def run_once(cfg: dict) -> None:
    state = load_state()
    open_positions = pos_mgr.load_positions()
    print(f"--- סריקה {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} --- (פוזיציות פתוחות: {len(open_positions)})")
    for i, ticker in enumerate(cfg["watchlist"]):
        if i > 0:
            time.sleep(1.5)  # מרווח בין טיקרים - Yahoo חוסם בקשות רצופות מהירות מדי
        try:
            process_ticker(ticker, cfg, state, open_positions)
        except Exception as e:
            print(f"  {ticker}: שגיאה - {e}")
            traceback.print_exc()
    save_state(state)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="הרצה חד-פעמית ויציאה (לבדיקה / GitHub Actions)")
    parser.add_argument("--force", action="store_true", help="עם --once: מריץ גם אם השוק סגור (לבדיקה ידנית)")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")
    cfg = load_config()

    if args.once:
        # ב-GitHub Actions ה-cron רץ בטווח UTC רחב יותר משעות המסחר בפועל (חוצה
        # קיץ/חורף) - הבדיקה כאן חוסכת סריקה מיותרת כשקוראים מחוץ לשעות האמיתיות.
        if args.force or is_market_open(cfg):
            run_once(cfg)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] השוק סגור - מדלג על הסריקה (--once).")
        return

    print("מערכת ההתראות פועלת. Ctrl+C לעצירה.")
    while True:
        try:
            if is_market_open(cfg):
                run_once(cfg)
                time.sleep(cfg["loop_interval_seconds"])
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] השוק סגור - ממתין...")
                time.sleep(cfg["idle_sleep_seconds"])
        except KeyboardInterrupt:
            print("נעצר על ידי המשתמש.")
            break
        except Exception as e:
            print(f"שגיאה בלולאה הראשית: {e}")
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    main()
