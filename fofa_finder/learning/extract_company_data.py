# -*- coding: utf-8 -*-
import re
import os
import pandas as pd
import html

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(BASE_DIR, "fofa_finder", "output", "fofa_finder.log")
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_dataset.csv")

def extract():
    if not os.path.exists(LOG_FILE):
        print(f"Log file not found: {LOG_FILE}")
        return

    print(f"Scanning log file: {LOG_FILE}...")
    
    data = []
    
    # Patterns
    # [2026-02-13 17:37:13] INFO | Analyzer | 正在进行公司资质预判: 北京出行汽车服务有限公司
    start_pattern = re.compile(r"正在进行公司资质预判:\s*(.+)")
    
    # [2026-02-13 17:37:16] INFO | Analyzer | 资质预判结果: False - 公司名称为汽车服务公司...
    result_pattern = re.compile(r"资质预判结果:\s*(True|False)\s*-\s*(.+)")
    
    current_company = None
    
    # Read with error ignoring for encoding safety
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            
            # Check for start
            start_match = start_pattern.search(line)
            if start_match:
                current_company = start_match.group(1).strip()
                continue
                
            # Check for result (must have a current company pending)
            if current_company:
                result_match = result_pattern.search(line)
                if result_match:
                    eligible_str = result_match.group(1)
                    reason = result_match.group(2).strip()
                    
                    label = 1 if eligible_str == 'True' else 0
                    
                    data.append({
                        "company": current_company,
                        "label": label,
                        "reason": reason
                    })
                    
                    # Reset
                    current_company = None

    if not data:
        print("No company eligibility data found in logs.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Remove duplicates (same company might be checked multiple times)
    # Keep the last judgment
    df.drop_duplicates(subset=['company'], keep='last', inplace=True)
    
    print(f"Extracted {len(df)} unique samples.")
    
    # Save/Append
    if os.path.exists(DATASET_FILE):
        print("Appending to existing dataset...")
        existing_df = pd.read_csv(DATASET_FILE)
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df.drop_duplicates(subset=['company'], keep='last', inplace=True)
        combined_df.to_csv(DATASET_FILE, index=False, encoding='utf-8-sig')
    else:
        print("Creating new dataset...")
        df.to_csv(DATASET_FILE, index=False, encoding='utf-8-sig')
        
    print(f"Dataset saved to {DATASET_FILE}")
    print("\nSample Data:")
    print(df.head())

if __name__ == "__main__":
    extract()
