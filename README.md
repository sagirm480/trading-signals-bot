# Trading Signals Bot

מערכת סווינג-טריידינג עצמאית: סורקת רשימת מעקב של מניות, מחשבת ניקוד משוקלל
מבוסס תבניות נרות/גרפיות/Volume Profile/ריבוי מסגרות-זמן, ומנהלת "פוזיציות
מעקב" (paper trading, לא כסף אמיתי) עם גודל פוזיציה לפי סיכון % מהתיק.
שולחת התראות כניסה ויציאה לטלגרם.

רץ אוטומטית דרך GitHub Actions (`.github/workflows/scan.yml`) כל 15 דקות
בשעות המסחר של NYSE - לא תלוי במחשב אישי דולק/ער.

## ⚠️ חשוב

- **זו לא מערכת עם יתרון סטטיסטי מוכח.** בדיקות היסטוריות (`backtest.py`,
  `walk_forward_validate.py`) הראו תוצאות מעודדות אבל לא סופיות - ראו
  `MEMORY`/היסטוריית השיחה לפירוט. `paper_trading_summary.py` עוקב אחרי
  ביצועים אמיתיים (forward, לא רטרואקטיבי) לאורך זמן.
- **אין חיבור לברוקר.** כל "פוזיציה" היא מעקב סימולציה בלבד. שום כסף אמיתי
  לא זז כתוצאה מהמערכת הזו.
- **זה לא ייעוץ השקעות.**

## מבנה

| קובץ | תפקיד |
|---|---|
| `config.yaml` | רשימת מעקב, משקלים, ספים, ניהול סיכונים (תיק/סקטורים) |
| `engine.py` | מנוע הניקוד - זיהוי תבניות נרות/גרפיות, Volume Profile, ניקוד משוקלל |
| `data_fetcher.py` | שליפת נתונים מ-yfinance עם retry/backoff |
| `positions.py` | ניהול פוזיציות, גודל לפי סיכון, מגבלות תיק/קורלציה |
| `advisory.py` | בניית הודעות טלגרם (כניסה/יציאה) |
| `main.py` | לולאת הסריקה הראשית |
| `backtest.py`, `random_baseline.py`, `walk_forward_validate.py` | כלי אימות היסטוריים |
| `paper_trading_summary.py` | סיכום ביצועים אמיתיים (live) עד כה |
| `state.json`, `positions.json`, `trade_log.json` | מצב מתמשך - מתעדכן אוטומטית ע"י ה-workflow |

## הרצה מקומית (לבדיקה)

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env   # למלא TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
./venv/bin/python3 main.py --once --force
```
