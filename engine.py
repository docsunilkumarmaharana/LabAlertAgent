import pandas as pd

def run_alert_engine(results_file, rules_file):
    # 1. Load the data
    df = pd.read_csv(results_file)
    
    # Check if rules_file is already a DataFrame (from the sidebar editor) or a file path
    if isinstance(rules_file, pd.DataFrame):
        rules_df = rules_file.copy()
    else:
        rules_df = pd.read_csv(rules_file)

    # 2. Merge patient results with rules based on the 'Analyte' column
    merged_df = pd.merge(df, rules_df, on='Analyte', how='left', suffixes=('', '_rule'))

    # 3. Function to check each row against the rules
    def check_critical(row):
        # Check High Critical
        if pd.notna(row['Critical_High']) and row['Critical_High_Operator'] == '>':
            if row['Result'] > row['Critical_High']:
                return 'CRITICAL (HIGH)'
        
        # Check Low Critical
        if pd.notna(row['Critical_Low']) and row['Critical_Low_Operator'] == '<':
            if row['Result'] < row['Critical_Low']:
                return 'CRITICAL (LOW)'
        
        # Check Abnormal (not critical)
        if pd.notna(row['Reference_Low']) and row['Result'] < row['Reference_Low']:
            return 'ABNORMAL (LOW)'
        if pd.notna(row['Reference_High']) and row['Result'] > row['Reference_High']:
            return 'ABNORMAL (HIGH)'
        
        return 'NORMAL'

    # 4. Apply the check to every row
    merged_df['Alert_Status'] = merged_df.apply(check_critical, axis=1)

    # 5. Filter out only the critical alerts
    critical_alerts = merged_df[merged_df['Alert_Status'].str.contains('CRITICAL')]

    return merged_df, critical_alerts

# --- Test the engine locally ---
if __name__ == "__main__":
    print("Running engine test...")
    all_results, criticals = run_alert_engine('patient_results.csv', 'rules.csv')
    
    print(f"\nTotal Results Processed: {len(all_results)}")
    print(f"Critical Alerts Found: {len(criticals)}")
    
    if not criticals.empty:
        print("\n--- CRITICAL ALERTS ---")
        for index, row in criticals.iterrows():
            print(f"Patient: {row['Patient_ID']} | Test: {row['Analyte']} | Result: {row['Result']} {row['Unit']} | Status: {row['Alert_Status']}")