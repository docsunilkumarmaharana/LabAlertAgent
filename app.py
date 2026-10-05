import streamlit as st
import pandas as pd
from engine import run_alert_engine
import os
import sqlite3
import time
from notifications import send_telegram_alert, get_ai_suggestion, DB_PATH

# --- Page Setup ---
st.set_page_config(page_title="Lab Alert Agent", page_icon="🚨", layout="wide")
st.title("🚨 Critical Value Alert Agent")
st.write("Upload your lab results (CSV or Excel) to automatically check for critical values.")

# --- Load Default Rules ---
@st.cache_data
def load_default_rules():
    return pd.read_csv('rules.csv')

if 'custom_rules' not in st.session_state:
    st.session_state.custom_rules = load_default_rules()

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    with st.expander("📖 Telegram Setup Guide"):
        st.markdown("""
        **1. Create Bot:**
        Message `@BotFather` → `/newbot` → Copy **Token**.
        
        **2. Get ID:**
        Message `@userinfobot` → Copy **ID**.
        
        **3. Start Bot:**
        Search your bot's **username** → Open it → Click **START** or type `/start`.
        """)

    st.subheader("📱 Telegram Alerts")
    bot_token = st.text_input("Bot Token", value="YOUR_BOT_TOKEN_HERE", type="password")
    chat_id = st.text_input("Chat ID", value="YOUR_CHAT_ID_HERE")
    st.caption("Change these to send alerts to a different user.")
    
    st.divider()
    
    st.subheader("📝 Critical Limits Editor")
    edited_rules = st.data_editor(
        st.session_state.custom_rules,
        num_rows="fixed",
        hide_index=True,
        use_container_width=True
    )
    
    col_reset, col_save = st.columns(2)
    with col_reset:
        if st.button("Reset to Default"):
            st.session_state.custom_rules = load_default_rules()
            st.rerun()
    with col_save:
        if st.button("Save Changes"):
            st.session_state.custom_rules = edited_rules
            st.success("Rules updated!")

# =========================================================
# NEW: FILE UPLOADER WITH TEMPLATE DOWNLOAD
# =========================================================
st.subheader("📂 Upload Results")
col_upload, col_template = st.columns([2, 1])

with col_upload:
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=['csv', 'xlsx'])

with col_template:
    st.write("**Need a template?**")
    # Create an empty dataframe with the required columns + a sample row
    template_cols = ["Patient_ID", "Sample_ID", "Age", "Sex", "Department", "Location", "Result_DateTime", "Analyte", "Unit", "Result", "Previous_Result"]
    template_df = pd.DataFrame(columns=template_cols)
    
    # Add a sample row so the user knows the exact format needed
    template_df.loc[0] = ["P1001", "S1001-01", 45, "M", "ICU", "ICU", "2026-10-06 10:00:00", "Glucose", "mg/dL", 450, 95]
    
    csv = template_df.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Download Template",
        data=csv,
        file_name="lab_results_template.csv",
        mime="text/csv",
        use_container_width=True
    )
    st.caption("Fill the template and upload it above.")
# =========================================================

if uploaded_file is not None:
    temp_file_path = "temp_uploaded_file." + uploaded_file.name.split('.')[-1]
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        all_results, critical_alerts = run_alert_engine(temp_file_path, st.session_state.custom_rules)

        st.subheader("Analysis Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Results", len(all_results))
        col2.metric("Normal", len(all_results[all_results['Alert_Status'] == 'NORMAL']))
        col3.metric("Abnormal (Non-Critical)", len(all_results[all_results['Alert_Status'].str.startswith('ABNORMAL')]))
        col4.metric("Critical Alerts", len(critical_alerts), delta_color="inverse")

        if not critical_alerts.empty:
            st.error(f"🚨 Found {len(critical_alerts)} CRITICAL ALERTS! Immediate action required.")
            
            critical_alerts['AI_Suggestion'] = critical_alerts.apply(
                lambda row: get_ai_suggestion(row['Analyte'], row['Result'], row['Alert_Status']), axis=1
            )
            
            alert_key = f"alert_sent_{uploaded_file.name}"
            if alert_key not in st.session_state:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM alerts WHERE chat_id=?", (chat_id,))
                
                for _, row in critical_alerts.iterrows():
                    c.execute("INSERT INTO alerts (bot_token, chat_id, patient_id, analyte, result, acked, timestamp) VALUES (?, ?, ?, ?, ?, 0, ?)",
                              (bot_token, chat_id, str(row['Patient_ID']), str(row['Analyte']), str(row['Result']), time.time()))
                conn.commit()
                conn.close()
                
                alert_message = "🚨 CRITICAL LAB ALERTS 🚨\n\n"
                count = 0
                max_alerts = 15
                for _, row in critical_alerts.iterrows():
                    if count < max_alerts:
                        alert_message += f"Patient: {row['Patient_ID']} | Test: {row['Analyte']} | Result: {row['Result']} {row['Unit']} ({row['Alert_Status']})\nSuggestion: {row['AI_Suggestion']}\n\n"
                    count += 1
                if count > max_alerts:
                    alert_message += f"\n...and {count - max_alerts} more critical alerts."
                
                send_telegram_alert(bot_token, chat_id, alert_message)
                st.session_state.last_alert_time = time.time()
                st.session_state[alert_key] = True
                st.success("✅ Initial Telegram alert sent!")

            st.dataframe(
                critical_alerts[['Patient_ID', 'Analyte', 'Result', 'Unit', 'Alert_Status', 'AI_Suggestion', 'Department', 'Location']], 
                use_container_width=True
            )
            
            st.divider()
            st.subheader("✅ Acknowledge Alerts")
            
            if st.button("🚨 Acknowledge ALL Alerts", use_container_width=True):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE alerts SET acked=1 WHERE chat_id=? AND acked=0", (chat_id,))
                conn.commit()
                conn.close()
                
                send_telegram_alert(bot_token, chat_id, "✅ ALL CRITICAL ALERTS ACKNOWLEDGED ✅")
                st.success("All alerts acknowledged!")
                st.rerun()
            
            st.write("---")
            st.caption("Or acknowledge individual alerts:")
            
            for idx, row in critical_alerts.iterrows():
                col_a, col_b, col_c = st.columns([3, 2, 1]) 
                with col_a:
                    st.write(f"**{row['Patient_ID']}** - {row['Analyte']} ({row['Result']} {row['Unit']})")
                with col_b:
                    st.write(f"_{row['AI_Suggestion']}_")
                with col_c:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("SELECT id, acked FROM alerts WHERE chat_id=? AND patient_id=? AND analyte=? ORDER BY id DESC LIMIT 1", 
                              (chat_id, str(row['Patient_ID']), str(row['Analyte'])))
                    db_row = c.fetchone()
                    conn.close()
                    
                    if db_row and db_row[1] == 1:
                        st.success("Acknowledged")
                    else:
                        if st.button("Acknowledge", key=f"ack_{idx}"):
                            if db_row:
                                conn = sqlite3.connect(DB_PATH)
                                c = conn.cursor()
                                c.execute("UPDATE alerts SET acked=1 WHERE id=?", (db_row[0],))
                                conn.commit()
                                conn.close()
                                
                                send_telegram_alert(bot_token, chat_id, f"✅ ALERT ACKNOWLEDGED ✅\nPatient: {row['Patient_ID']} | Test: {row['Analyte']}")
                                st.rerun()

            st.divider()
            st.subheader("⏱️ Re-alert Check")
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM alerts WHERE chat_id=? AND acked=0", (chat_id,))
            pending = c.fetchone()[0]
            conn.close()
            
            if pending > 0:
                st.warning(f"Currently {pending} unacknowledged alerts.")
                elapsed = time.time() - st.session_state.get('last_alert_time', time.time())
                st.write(f"Time since last alert: {int(elapsed)} seconds.")
                
                if st.button("🔔 Send Re-alert to Telegram"):
                    realert_msg = f"⚠️ RE-ALERT ({pending} UNACKNOWLEDGED) ⚠️\n\nPlease check the dashboard immediately."
                    send_telegram_alert(bot_token, chat_id, realert_msg)
                    st.session_state.last_alert_time = time.time()
                    st.success("Re-alert sent!")
                    st.rerun()
            else:
                st.success("All alerts acknowledged! No re-alerts needed.")
                
        else:
            st.success("✅ No critical values found in this dataset.")

        with st.expander("View All Processed Results"):
            st.dataframe(all_results[['Patient_ID', 'Analyte', 'Result', 'Unit', 'Alert_Status']], use_container_width=True)

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
        
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)