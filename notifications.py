import sqlite3
import time
import urllib.request
import urllib.parse

DB_PATH = "alerts.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  bot_token TEXT, chat_id TEXT,
                  patient_id TEXT, analyte TEXT, result TEXT,
                  acked INTEGER DEFAULT 0,
                  timestamp REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- AI SUGGESTION ENGINE ---
def get_ai_suggestion(analyte, result, status):
    analyte = analyte.lower()
    if "potassium" in analyte:
        if "HIGH" in status: return "Consider ECG, check for hemolysis, repeat test urgently."
        if "LOW" in status: return "Consider ECG, check for diuretics, repeat test urgently."
    elif "sodium" in analyte:
        if "HIGH" in status: return "Assess fluid status, check for diabetes insipidus, repeat test."
        if "LOW" in status: return "Assess fluid status, check for SIADH, repeat test."
    elif "glucose" in analyte:
        if "HIGH" in status: return "Check ketones, assess for DKA/HHS, repeat test."
        if "LOW" in status: return "Rule out hypoglycemia, administer glucose if symptomatic, repeat test."
    elif "creatinine" in analyte:
        return "Assess renal function, check for AKI/CKD, repeat test."
    elif "bilirubin" in analyte:
        return "Assess liver function, check for obstruction/hemolysis, repeat test."
    return "Repeat test, notify clinician immediately."

# --- TELEGRAM ---
def send_telegram_alert(bot_token, chat_id, message):
    if not bot_token or not chat_id or "YOUR" in bot_token:
        return False, "Telegram credentials not configured."
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            return True, "Telegram alert sent successfully!"
    except Exception as e:
        return False, f"Telegram Error: {e}"