"""
מנוע אסטרטגיה - מרכיב "כניסה מומלצת" מתוך תוצאות הניתוח: קונפלואנס בין
מסגרות זמן, הקשר Volume Profile, והצעת סטופ/יעד מבוססי ATR (טכניקת סווינג
נפוצה: סטופ ~1.5×ATR מתחת/מעל הכניסה, יעד ראשון ~2×הסיכון = יחס סיכוי/סיכון 1:2).
"""
from __future__ import annotations


def build_message(ticker: str, daily: dict, h4_buy: float, h4_sell: float, w_buy: float, w_sell: float,
                   direction: str, thresholds: dict, position_info: dict = None, skip_reason: str = None) -> str:
    close = daily["close"]
    atr_val = daily["atr"]

    if direction == "buy":
        stop = close - atr_val * 1.5
        target = close + atr_val * 3.0
        emoji = "🟢"
        label = "אות קנייה"
        active = daily["active_bull"]
        htf_agree = h4_buy >= thresholds["htf"] or w_buy >= thresholds["htf"]
    else:
        stop = close + atr_val * 1.5
        target = close - atr_val * 3.0
        emoji = "🔴"
        label = "אות מכירה"
        active = daily["active_bear"]
        htf_agree = h4_sell >= thresholds["htf"] or w_sell >= thresholds["htf"]

    lines = [
        f"{emoji} <b>{label}: {ticker}</b>",
        f"מחיר: {close:.2f}",
        f"ניקוד יומי: {daily['buy_score_pct' if direction == 'buy' else 'sell_score_pct']:.1f}%",
        f"ניקוד 4H: {h4_buy:.0f}% קנייה / {h4_sell:.0f}% מכירה",
        f"ניקוד שבועי: {w_buy:.0f}% קנייה / {w_sell:.0f}% מכירה",
    ]

    if active:
        lines.append("תבניות פעילות: " + ", ".join(active))

    if daily.get("vp_poc"):
        lines.append(
            f"Volume Profile - POC: {daily['vp_poc']:.2f} | VAH: {daily['vp_vah']:.2f} | VAL: {daily['vp_val']:.2f}"
        )

    lines.append("✅ מסגרות זמן גבוהות תומכות" if htf_agree else "⚠️ מסגרות זמן גבוהות לא מאשרות עדיין - זהירות")

    lines.append(f"סטופ מוצע (ATR×1.5): {stop:.2f}")
    lines.append(f"יעד ראשון (יחס 1:2): {target:.2f}")

    if position_info:
        lines.append(
            f"📊 גודל פוזיציה מוצע: {position_info['shares']:.2f} מניות "
            f"(~${position_info['position_value']:.0f}, סיכון ${position_info['risk_dollars']:.0f})"
        )
        lines.append("✅ נפתחה כפוזיציית מעקב (paper) - תישלח התראה כשתיסגר")
    elif skip_reason:
        lines.append(f"🚫 לא נפתחה פוזיציית מעקב: {skip_reason}")

    lines.append(f'📈 גרף: <a href="https://www.tradingview.com/symbols/{ticker}/">tradingview.com/symbols/{ticker}</a>')
    lines.append("⚠️ לא ייעוץ השקעות - כלי עזר בלבד להחלטה שלך.")

    return "\n".join(lines)


def build_exit_message(exit_info: dict) -> str:
    r = exit_info["r_multiple"]
    emoji = "✅" if r > 0 else "❌" if r < 0 else "➖"
    outcome_label = {"stop": "סטופ הופעל", "target": "יעד הושג", "timeout": "נסגרה בתום הזמן"}.get(
        exit_info["outcome"], exit_info["outcome"]
    )
    lines = [
        f"{emoji} <b>פוזיציה נסגרה: {exit_info['ticker']}</b>",
        f"סיבה: {outcome_label}",
        f"כניסה: {exit_info['entry_price']:.2f} ({exit_info['entry_date']}) → יציאה: {exit_info['exit_price']:.2f} ({exit_info['exit_date']})",
        f"ימי החזקה: {exit_info['days_held']}",
        f"תוצאה: R={r:+.2f} | רווח/הפסד: ${exit_info['pnl_dollars']:+.2f}",
    ]
    return "\n".join(lines)
