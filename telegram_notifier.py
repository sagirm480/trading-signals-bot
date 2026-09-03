"""שליחת התראות לטלגרם - עצמאי לגמרי מ-TradingView, ללא מגבלת מספר התראות."""
from __future__ import annotations

import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[טלגרם] חסרים TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ב-.env - לא נשלחה הודעה.")
        return False

    url = TELEGRAM_API.format(token=token)
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[טלגרם] שליחה נכשלה ({resp.status_code}): {resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[טלגרם] שגיאת רשת בשליחה: {e}")
        return False
