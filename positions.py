"""
ניהול פוזיציות חי + יומן עסקאות (paper-trading). כל אות קנייה שעובר את
מגבלות ניהול הסיכון (מספר פוזיציות, קורלציית סקטור) נפתח כ"פוזיציה" -
לא מסחר אמיתי, סימולציה שנבדקת כל יום מול סטופ/יעד ונסגרת עם התראת
יציאה. זה גם משמש כרישום ה-live/forward היחיד שבאמת יכול להוכיח (או
לשלול) יתרון סטטיסטי - לא עוד בקטסט על אותו דאטה היסטורי.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent
POSITIONS_FILE = BASE_DIR / "positions.json"
TRADE_LOG_FILE = BASE_DIR / "trade_log.json"


def load_positions() -> dict:
    if POSITIONS_FILE.exists():
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_positions(positions: dict) -> None:
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def load_trade_log() -> list:
    if TRADE_LOG_FILE.exists():
        with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def append_trade_log(trade: dict) -> None:
    log = load_trade_log()
    log.append(trade)
    with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def compute_position_size(entry_price: float, stop_price: float, cfg: dict) -> dict:
    port = cfg["portfolio"]
    risk_dollars = port["account_size_usd"] * port["risk_per_trade_pct"] / 100
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0:
        return {"shares": 0.0, "position_value": 0.0, "risk_dollars": 0.0}
    shares = risk_dollars / risk_per_share
    if not port.get("fractional_shares", True):
        shares = float(int(shares))
    return {
        "shares": round(shares, 4),
        "position_value": round(shares * entry_price, 2),
        "risk_dollars": round(risk_dollars, 2),
    }


def can_open_position(ticker: str, cfg: dict, positions: dict):
    """מחזיר (מותר: bool, סיבה אם לא: str)."""
    port = cfg["portfolio"]
    sectors = cfg.get("sectors", {})
    if ticker in positions:
        return False, "כבר קיימת פוזיציה פתוחה בטיקר הזה"
    if len(positions) >= port["max_concurrent_positions"]:
        return False, f"הגעה למגבלת {port['max_concurrent_positions']} פוזיציות פתוחות בו-זמנית"
    my_sector = sectors.get(ticker, "unknown")
    same_sector = sum(1 for t in positions if sectors.get(t, "unknown") == my_sector)
    limit = port.get("max_positions_per_sector", 1)
    if same_sector >= limit:
        return False, f"הגעה למגבלת {limit} פוזיציות בסקטור '{my_sector}' (קורלציה)"
    return True, ""


def open_position(ticker: str, cfg: dict, positions: dict, entry_date: str, entry_price: float,
                   stop: float, target: float, atr_val: float) -> dict:
    sizing = compute_position_size(entry_price, stop, cfg)
    position = {
        "ticker": ticker, "entry_date": entry_date, "entry_price": round(entry_price, 4),
        "stop": round(stop, 4), "target": round(target, 4), "atr": round(atr_val, 4),
        **sizing,
    }
    positions[ticker] = position
    save_positions(positions)
    return position


def check_exit(ticker: str, position: dict, today_high: float, today_low: float, today_close: float,
                today_date: str, max_hold_days: int = 40) -> Optional[dict]:
    stop, target = position["stop"], position["target"]
    exit_price, outcome = None, None

    if today_low <= stop:
        exit_price, outcome = stop, "stop"
    elif today_high >= target:
        exit_price, outcome = target, "target"
    else:
        days_held = (datetime.fromisoformat(today_date) - datetime.fromisoformat(position["entry_date"])).days
        if days_held >= max_hold_days:
            exit_price, outcome = today_close, "timeout"

    if exit_price is None:
        return None

    risk_per_share = abs(position["entry_price"] - position["stop"])
    r_multiple = (exit_price - position["entry_price"]) / risk_per_share if risk_per_share > 0 else 0.0
    days_held = (datetime.fromisoformat(today_date) - datetime.fromisoformat(position["entry_date"])).days

    return {
        "ticker": ticker,
        "entry_date": position["entry_date"],
        "exit_date": today_date,
        "entry_price": position["entry_price"],
        "exit_price": round(exit_price, 4),
        "shares": position["shares"],
        "outcome": outcome,
        "r_multiple": round(r_multiple, 2),
        "pnl_dollars": round((exit_price - position["entry_price"]) * position["shares"], 2),
        "days_held": days_held,
    }
