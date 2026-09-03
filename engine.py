"""
מנוע הניקוד - שכפול בפייתון של הלוגיקה שבאינדיקטור full_indicator_6.pine
(תבניות נרות, תבניות גרפיות, Volume Profile מעוגן, ניקוד משוקלל לפי פרמטר).

הערה: זהו קירוב קרוב ללוגיקה של Pine Script, לא זהה ביט-לביט. בפרט זיהוי
הפיבוטים (תמיכה/התנגדות) משתמש בשיטה שקולה אך לא זהה למימוש הפנימי של
TradingView. המטרה היא עקביות התנהגותית, לא שכפול מדויק של כל תו.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# אינדיקטורים בסיסיים
# ============================================================
def rma(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1 / length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.fillna(50)


def atr(df: pd.DataFrame, length: int) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return rma(tr, length)


# ============================================================
# פיבוטים (תמיכה/התנגדות + בסיס לתבניות גרפיות)
# תוקן ב-2026-08-08 להתאמה מדויקת יותר ל-ta.pivothigh/pivotlow של Pine:
# ההגדרה הסטנדרטית של פיבוט "פרקטלי" היא השוואה זוגית (strict) מול כל בר
# בצד שמאל ובכל בר בצד ימין בנפרד - לא רק "הכי גבוה בחלון" (שהיה יכול
# לתת כמה "פיבוטים" בו-זמנית בפסגה שטוחה עם ערכים זהים).
# ============================================================
def find_pivots(df: pd.DataFrame, lookback: int, max_pivots: int):
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)
    last = n - 1
    pivot_highs, pivot_lows = [], []
    end = last - lookback + 1
    for i in range(lookback, max(end, lookback)):
        left_h = highs[i - lookback : i]
        right_h = highs[i + 1 : i + lookback + 1]
        if highs[i] > left_h.max() and highs[i] > right_h.max():
            pivot_highs.append((i, float(highs[i])))
        left_l = lows[i - lookback : i]
        right_l = lows[i + 1 : i + lookback + 1]
        if lows[i] < left_l.min() and lows[i] < right_l.min():
            pivot_lows.append((i, float(lows[i])))
    return pivot_highs[-max_pivots:], pivot_lows[-max_pivots:]


def near_any_level(price: float, levels, proximity_pct: float) -> bool:
    if not levels:
        return False
    return any(abs(price - lvl) / lvl * 100 <= proximity_pct for _, lvl in levels)


# ============================================================
# תבניות נרות (מבוססות על 3 הבארים האחרונים)
# ============================================================
def candle_patterns(df: pd.DataFrame, near_support: bool, near_resistance: bool) -> dict:
    c0, o0, h0, l0 = df["Close"].iloc[-1], df["Open"].iloc[-1], df["High"].iloc[-1], df["Low"].iloc[-1]
    c1, o1 = df["Close"].iloc[-2], df["Open"].iloc[-2]
    c2, o2 = df["Close"].iloc[-3], df["Open"].iloc[-3]
    h1, l1 = df["High"].iloc[-2], df["Low"].iloc[-2]

    body = abs(c0 - o0)
    body1 = abs(c1 - o1)
    body2 = abs(c2 - o2)
    upper_wick = h0 - max(c0, o0)
    lower_wick = min(c0, o0) - l0
    avg_body = (df["Close"] - df["Open"]).abs().rolling(14).mean().iloc[-1]

    is_hammer_shape = (lower_wick > body * 2) and (upper_wick < body * 0.6) and (body > 0)
    is_inv_hammer_shape = (upper_wick > body * 2) and (lower_wick < body * 0.6) and (body > 0)

    is_bull_engulf = c0 > o0 and c1 < o1 and c0 >= o1 and o0 <= c1
    is_bear_engulf = c0 < o0 and c1 > o1 and c0 <= o1 and o0 >= c1

    is_bull_harami = c1 < o1 and c0 > o0 and o0 >= c1 and c0 <= o1 and body < body1
    is_bear_harami = c1 > o1 and c0 < o0 and o0 <= c1 and c0 >= o1 and body < body1

    is_piercing = c1 < o1 and c0 > o0 and o0 < c1 and c0 > (o1 + c1) / 2 and c0 < o1
    is_dark_cloud = c1 > o1 and c0 < o0 and o0 > c1 and c0 < (o1 + c1) / 2 and c0 > o1

    is_morning_star = c2 < o2 and abs(c1 - o1) < (body2 * 0.4) and c0 > o0 and c0 > (o2 + c2) / 2
    is_evening_star = c2 > o2 and abs(c1 - o1) < (body2 * 0.4) and c0 < o0 and c0 < (o2 + c2) / 2

    is_tweezer_bottom = abs(l0 - l1) / l1 * 100 <= 0.15 and c0 > o0
    is_tweezer_top = abs(h0 - h1) / h1 * 100 <= 0.15 and c0 < o0

    three_white = (
        c0 > o0 and c1 > o1 and c2 > o2 and c0 > c1 > c2 and o0 > o1 > o2
        and body > avg_body * 0.5 and body1 > avg_body * 0.5 and body2 > avg_body * 0.5
    )
    three_black = (
        c0 < o0 and c1 < o1 and c2 < o2 and c0 < c1 < c2 and o0 < o1 < o2
        and body > avg_body * 0.5 and body1 > avg_body * 0.5 and body2 > avg_body * 0.5
    )

    bull_marubozu = c0 > o0 and body > avg_body * 1.5 and upper_wick < body * 0.05 and lower_wick < body * 0.05
    bear_marubozu = c0 < o0 and body > avg_body * 1.5 and upper_wick < body * 0.05 and lower_wick < body * 0.05

    return {
        "hammer": is_hammer_shape and near_support,
        "hanging_man": is_hammer_shape and near_resistance,
        "inverted_hammer": is_inv_hammer_shape and near_support,
        "shooting_star": is_inv_hammer_shape and near_resistance,
        "bullish_engulfing": is_bull_engulf and near_support,
        "bearish_engulfing": is_bear_engulf and near_resistance,
        "bullish_harami": is_bull_harami and near_support,
        "bearish_harami": is_bear_harami and near_resistance,
        "piercing_line": is_piercing and near_support,
        "dark_cloud_cover": is_dark_cloud and near_resistance,
        "morning_star": is_morning_star and near_support,
        "evening_star": is_evening_star and near_resistance,
        "tweezer_bottom": is_tweezer_bottom and near_support,
        "tweezer_top": is_tweezer_top and near_resistance,
        "three_white_soldiers": three_white,
        "three_black_crows": three_black,
        "bull_marubozu": bull_marubozu,
        "bear_marubozu": bear_marubozu,
    }


# ============================================================
# תבניות גרפיות (מבוססות פיבוטים אחרונים)
# ============================================================
def chart_patterns(df: pd.DataFrame, pivot_highs, pivot_lows, close: float) -> dict:
    def lowest_between(b1, b2):
        if b2 <= b1:
            return None
        return df["Low"].iloc[b1 : b2 + 1].min()

    def highest_between(b1, b2):
        if b2 <= b1:
            return None
        return df["High"].iloc[b1 : b2 + 1].max()

    res = {k: False for k in [
        "double_top", "double_bottom", "triple_top", "triple_bottom",
        "head_shoulders", "inverse_head_shoulders", "cup_handle",
        "rectangle_break_up", "rectangle_break_down",
        "ascending_triangle", "descending_triangle",
        "symmetrical_triangle_up", "symmetrical_triangle_down",
        "falling_wedge", "rising_wedge",
        "rounding_bottom", "rounding_top",
    ]}

    nH, nL = len(pivot_highs), len(pivot_lows)

    if nH >= 2:
        (b1, h1), (b2, h2) = pivot_highs[-2], pivot_highs[-1]
        if abs(h1 - h2) / h1 * 100 <= 2.0:
            neck = lowest_between(b1, b2)
            if neck is not None and close < neck:
                res["double_top"] = True

    if nL >= 2:
        (b1, l1), (b2, l2) = pivot_lows[-2], pivot_lows[-1]
        if abs(l1 - l2) / l1 * 100 <= 2.0:
            neck = highest_between(b1, b2)
            if neck is not None and close > neck:
                res["double_bottom"] = True

    if nH >= 3:
        (b1, h1), (b2, h2), (b3, h3) = pivot_highs[-3], pivot_highs[-2], pivot_highs[-1]
        avg_h = (h1 + h2 + h3) / 3
        if all(abs(x - avg_h) / avg_h * 100 <= 2.5 for x in (h1, h2, h3)):
            neck = lowest_between(b1, b3)
            if neck is not None and close < neck:
                res["triple_top"] = True
        if h2 > h1 and h2 > h3 and abs(h1 - h3) / h1 * 100 <= 4.0:
            neck = lowest_between(b2, b3)
            if neck is not None and close < neck:
                res["head_shoulders"] = True

    if nL >= 3:
        (b1, l1), (b2, l2), (b3, l3) = pivot_lows[-3], pivot_lows[-2], pivot_lows[-1]
        avg_l = (l1 + l2 + l3) / 3
        if all(abs(x - avg_l) / avg_l * 100 <= 2.5 for x in (l1, l2, l3)):
            neck = highest_between(b1, b3)
            if neck is not None and close > neck:
                res["triple_bottom"] = True
        if l2 < l1 and l2 < l3 and abs(l1 - l3) / l1 * 100 <= 4.0:
            neck = highest_between(b2, b3)
            if neck is not None and close > neck:
                res["inverse_head_shoulders"] = True
        if nH >= 1:
            cup_bottom, handle_low, rim = l2, l3, pivot_highs[-1][1]
            if handle_low > cup_bottom and handle_low < rim and (rim - handle_low) / rim * 100 <= 8.0:
                if close > rim:
                    res["cup_handle"] = True
        rising = l2 > l1 and l3 > l2
        gradual = (l2 - l1) < (l1 * 0.05) and (l3 - l2) < (l1 * 0.05)
        if rising and gradual and nH >= 1:
            rim = pivot_highs[-1][1]
            if close > rim:
                res["rounding_bottom"] = True

    if nH >= 3:
        (h1b, h1), (h2b, h2), (h3b, h3) = pivot_highs[-3], pivot_highs[-2], pivot_highs[-1]
        falling = h2 < h1 and h3 < h2
        gradual = (h1 - h2) < (h1 * 0.05) and (h2 - h3) < (h1 * 0.05)
        if falling and gradual and nL >= 1:
            rim = pivot_lows[-1][1]
            if close < rim:
                res["rounding_top"] = True

    if nH >= 2 and nL >= 2:
        (_, h1), (_, h2) = pivot_highs[-2], pivot_highs[-1]
        (_, l1), (_, l2) = pivot_lows[-2], pivot_lows[-1]

        if abs(h1 - h2) / h1 * 100 <= 2.0 and abs(l1 - l2) / l1 * 100 <= 2.0:
            if close > max(h1, h2):
                res["rectangle_break_up"] = True
            if close < min(l1, l2):
                res["rectangle_break_down"] = True

        if h2 <= h1 * 1.005 and l2 > l1 and close > h2:
            res["ascending_triangle"] = True
        if l2 >= l1 * 0.995 and h2 < h1 and close < l2:
            res["descending_triangle"] = True

        converging = h2 < h1 and l2 > l1
        if converging and close > h2:
            res["symmetrical_triangle_up"] = True
        if converging and close < l2:
            res["symmetrical_triangle_down"] = True

        if h2 < h1 and l2 < l1 and (h2 - l2) < (h1 - l1) * 0.8 and close > h2:
            res["falling_wedge"] = True
        if h2 > h1 and l2 > l1 and (h2 - l2) < (h1 - l1) * 0.8 and close < l2:
            res["rising_wedge"] = True

    return res


def flag_pennant_patterns(df: pd.DataFrame, atr_series: pd.Series, chart_up: bool, chart_down: bool) -> dict:
    close = df["Close"]
    strong_up = (close - close.shift(10)) > atr_series * 3
    strong_down = (close.shift(10) - close) > atr_series * 3
    highest5 = df["High"].rolling(5).max()
    lowest5 = df["Low"].rolling(5).min()
    highest5_prev = highest5.shift(1)
    lowest5_prev = lowest5.shift(1)
    tight_range = (highest5 - lowest5) < atr_series * 1.5

    if len(df) < 14:
        return {"flag_up": False, "flag_down": False, "pennant_up": False, "pennant_down": False}

    strong_up_3ago = bool(strong_up.iloc[-4]) if len(strong_up) >= 4 else False
    strong_down_3ago = bool(strong_down.iloc[-4]) if len(strong_down) >= 4 else False

    flag_up = strong_up_3ago and bool(tight_range.iloc[-1]) and close.iloc[-1] > highest5_prev.iloc[-1]
    flag_down = strong_down_3ago and bool(tight_range.iloc[-1]) and close.iloc[-1] < lowest5_prev.iloc[-1]
    pennant_up = strong_up_3ago and chart_up
    pennant_down = strong_down_3ago and chart_down

    return {"flag_up": flag_up, "flag_down": flag_down, "pennant_up": pennant_up, "pennant_down": pennant_down}


# ============================================================
# Volume Profile מעוגן (POC / VAH / VAL)
# ============================================================
def anchored_volume_profile(df: pd.DataFrame, lookback: int, bins: int, value_area_pct: float):
    if len(df) < lookback:
        lookback = len(df)
    sub = df.iloc[-lookback:]
    highs = sub["High"].values
    lows = sub["Low"].values
    vols = sub["Volume"].values
    typical = (highs + lows) / 2

    hi_range, lo_range = highs.max(), lows.min()
    bin_size = (hi_range - lo_range) / bins
    if bin_size <= 0:
        return None, None, None

    bin_vol = np.zeros(bins)
    idx = np.clip(((typical - lo_range) / bin_size).astype(int), 0, bins - 1)
    for b, v in zip(idx, vols):
        bin_vol[b] += v

    poc_idx = int(np.argmax(bin_vol))
    total_vol = bin_vol.sum()
    target = total_vol * value_area_pct / 100
    lo_idx = hi_idx = poc_idx
    cum = bin_vol[poc_idx]

    for _ in range(bins):
        if cum >= target:
            break
        can_down, can_up = lo_idx > 0, hi_idx < bins - 1
        if not can_down and not can_up:
            break
        vol_down = bin_vol[lo_idx - 1] if can_down else -1
        vol_up = bin_vol[hi_idx + 1] if can_up else -1
        if vol_down >= vol_up:
            lo_idx -= 1
            cum += vol_down
        else:
            hi_idx += 1
            cum += vol_up

    poc = lo_range + (poc_idx + 0.5) * bin_size
    val = lo_range + lo_idx * bin_size
    vah = lo_range + (hi_idx + 1) * bin_size
    return poc, vah, val


# ============================================================
# ניקוד קל למסגרות זמן גבוהות (4H / שבועי) - כמו f_htfScore ב-Pine
# ============================================================
def htf_score(df: pd.DataFrame):
    if len(df) < 55:
        return 0.0, 0.0
    ma50 = sma(df["Close"], 50).iloc[-1]
    rsi14 = rsi(df["Close"], 14).iloc[-1]
    vol_avg = sma(df["Volume"], 20).iloc[-1]
    c0, o0 = df["Close"].iloc[-1], df["Open"].iloc[-1]
    c1 = df["Close"].iloc[-2]
    high_vol = df["Volume"].iloc[-1] > vol_avg * 1.5
    bull = c0 > o0 and c0 > c1
    bear = c0 < o0 and c0 < c1

    buy_pts = (25.0 if c0 > ma50 else 0.0) + (20.0 if rsi14 <= 35 else 0.0) + (20.0 if high_vol else 0.0) + (35.0 if bull else 0.0)
    sell_pts = (25.0 if c0 < ma50 else 0.0) + (20.0 if rsi14 >= 65 else 0.0) + (20.0 if high_vol else 0.0) + (35.0 if bear else 0.0)
    return buy_pts, sell_pts


# ============================================================
# ניתוח מלא (מסגרת הזמן הראשית - יומי)
# ============================================================
def analyze(df: pd.DataFrame, cfg: dict) -> dict:
    if len(df) < 160:
        return {"error": "not_enough_history"}

    w = cfg["weights"]
    proximity_pct = cfg["proximity_pct"]
    pivot_lb = cfg["pivot_lookback"]
    max_pivots = cfg["max_pivots"]
    vp_cfg = cfg["volume_profile"]

    close = df["Close"].iloc[-1]

    ma50 = sma(df["Close"], 50)
    ma150 = sma(df["Close"], 150)
    rsi_series = rsi(df["Close"], 14)
    atr_series = atr(df, 14)
    vol_avg = sma(df["Volume"], 20)

    trend_bullish = close > ma50.iloc[-1]
    trend_bearish = close < ma50.iloc[-1]

    atr_now = atr_series.iloc[-1]
    ma50_now = ma50.iloc[-1]
    extension_atr = (close - ma50_now) / atr_now if atr_now > 0 else 0.0

    crossed_above_150 = bool(
        ((df["Close"] > ma150) & (df["Close"].shift(1) <= ma150.shift(1))).iloc[-20:].any()
    )
    crossed_below_150 = bool(
        ((df["Close"] < ma150) & (df["Close"].shift(1) >= ma150.shift(1))).iloc[-20:].any()
    )

    rsi_bounce = rsi_series.iloc[-1] <= 30 and rsi_series.iloc[-1] > rsi_series.iloc[-2]
    rsi_reject = rsi_series.iloc[-1] >= 70 and rsi_series.iloc[-1] < rsi_series.iloc[-2]

    high_volume = df["Volume"].iloc[-1] > vol_avg.iloc[-1] * 1.5

    pivot_highs, pivot_lows = find_pivots(df, pivot_lb, max_pivots)
    near_support = near_any_level(close, pivot_lows, proximity_pct)
    near_resistance = near_any_level(close, pivot_highs, proximity_pct)

    poc, vah, val = anchored_volume_profile(df, vp_cfg["lookback_days"], vp_cfg["bins"], vp_cfg["value_area_pct"])
    vp_near_support = False
    vp_near_resistance = False
    if poc is not None:
        if val and (abs(close - val) / val * 100 <= proximity_pct):
            vp_near_support = True
        if poc and (abs(close - poc) / poc * 100 <= proximity_pct) and close >= poc:
            vp_near_support = True
        if vah and (abs(close - vah) / vah * 100 <= proximity_pct):
            vp_near_resistance = True
        if poc and (abs(close - poc) / poc * 100 <= proximity_pct) and close <= poc:
            vp_near_resistance = True

    candles = candle_patterns(df, near_support, near_resistance)
    charts = chart_patterns(df, pivot_highs, pivot_lows, close)
    flags = flag_pennant_patterns(
        df, atr_series,
        charts["symmetrical_triangle_up"], charts["symmetrical_triangle_down"],
    )
    charts.update({
        "flag_up": flags["flag_up"], "flag_down": flags["flag_down"],
        "pennant_up": flags["pennant_up"], "pennant_down": flags["pennant_down"],
    })

    wt = w["technical"]
    buy_raw = 0.0
    buy_raw += wt["trend_ma50_buy"] if trend_bullish else 0
    buy_raw += wt["ma150_cross_buy"] if crossed_above_150 else 0
    buy_raw += wt["rsi_bounce"] if rsi_bounce else 0
    buy_raw += wt["volume_buy"] if high_volume else 0
    buy_raw += wt["pivot_sr_buy"] if near_support else 0
    buy_raw += wt["vp_strong_buy"] if vp_near_support else 0

    sell_raw = 0.0
    sell_raw += wt["trend_ma50_sell"] if trend_bearish else 0
    sell_raw += wt["ma150_cross_sell"] if crossed_below_150 else 0
    sell_raw += wt["rsi_reject"] if rsi_reject else 0
    sell_raw += wt["volume_sell"] if high_volume else 0
    sell_raw += wt["pivot_sr_sell"] if near_resistance else 0
    sell_raw += wt["vp_strong_sell"] if vp_near_resistance else 0

    active_bull, active_bear = [], []
    for name, active in candles.items():
        if not active:
            continue
        if name in w["bull_candles"]:
            buy_raw += w["bull_candles"][name]
            active_bull.append(name)
        elif name in w["bear_candles"]:
            sell_raw += w["bear_candles"][name]
            active_bear.append(name)

    for name, active in charts.items():
        if not active:
            continue
        if name in w["bull_charts"]:
            buy_raw += w["bull_charts"][name]
            active_bull.append(name)
        elif name in w["bear_charts"]:
            sell_raw += w["bear_charts"][name]
            active_bear.append(name)

    # === שילוב "פריצה/היפוך בריא" ===
    # התגלה בבקטסט (2026-08-08, 109 עסקאות/3 שנים): תבנית היפוך שמתרחשת בזמן
    # שהמחיר כבר 1-3 ATR מעל MA50 (לא צמוד אליו, לא מתוח מדי) - שיעור הצלחה
    # 57% וR ממוצע +0.71, הקומבינציה החזקה ביותר בכל הדאטה. חשוב: זה נמצא
    # ונבדק על אותו דאטה (in-sample) - לא אימות אמיתי מחוץ למדגם, רק השערה
    # מבוססת-נתונים שדורשת מעקב live להוכחה אמיתית.
    bull_reversal_patterns = {
        "hammer", "inverted_hammer", "bullish_engulfing", "bullish_harami",
        "piercing_line", "morning_star", "tweezer_bottom", "double_bottom",
        "triple_bottom", "inverse_head_shoulders", "rounding_bottom",
    }
    had_bull_reversal = any(p in bull_reversal_patterns for p in active_bull)
    healthy_pullback_setup = had_bull_reversal and (1.0 <= extension_atr <= 3.0)
    buy_raw += wt["healthy_pullback"] if healthy_pullback_setup else 0

    total_buy_weight = sum(wt[k] for k in (
        "trend_ma50_buy", "ma150_cross_buy", "rsi_bounce", "volume_buy", "pivot_sr_buy", "vp_strong_buy",
        "healthy_pullback",
    )) + sum(w["bull_candles"].values()) + sum(w["bull_charts"].values())

    total_sell_weight = sum(wt[k] for k in (
        "trend_ma50_sell", "ma150_cross_sell", "rsi_reject", "volume_sell", "pivot_sr_sell", "vp_strong_sell"
    )) + sum(w["bear_candles"].values()) + sum(w["bear_charts"].values())

    buy_pct = (buy_raw / total_buy_weight * 100) if total_buy_weight > 0 else 0.0
    sell_pct = (sell_raw / total_sell_weight * 100) if total_sell_weight > 0 else 0.0

    return {
        "close": close,
        "buy_score_pct": round(buy_pct, 1),
        "sell_score_pct": round(sell_pct, 1),
        "active_bull": active_bull,
        "active_bear": active_bear,
        "vp_poc": poc,
        "vp_vah": vah,
        "vp_val": val,
        "atr": atr_now,
        "above_ma150": bool(close > ma150.iloc[-1]),
        # שדות אבחון (לא משפיעים על הניקוד עצמו - לצורך ניתוח בקטסט)
        "ma50": ma50_now,
        "extension_atr": extension_atr,  # מרחק המחיר מ-MA50 ביחידות ATR - "כמה כבר רחוק מהבסיס"
        "trend_bullish": bool(trend_bullish),
        "crossed_above_150": bool(crossed_above_150),
        "rsi_bounce": bool(rsi_bounce),
        "high_volume": bool(high_volume),
        "near_support": bool(near_support),
        "vp_near_support": bool(vp_near_support),
        "healthy_pullback_setup": bool(healthy_pullback_setup),
    }
