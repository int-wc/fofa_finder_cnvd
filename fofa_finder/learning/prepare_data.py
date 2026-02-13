# -*- coding: utf-8 -*-
import os
import pandas as pd
import json
import random
from collections import Counter

# Configuration
# Dynamic path resolution to support WSL/Linux/Windows
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "fofa_finder", "output")
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "dataset.csv")

def scan_reports():
    """
    扫描 output 目录，寻找成对的 _raw.xlsx 和 _analysis.xlsx
    """
    dataset = []
    
    if not os.path.exists(OUTPUT_DIR):
        print(f"Error: Output directory not found: {OUTPUT_DIR}")
        return []
        
    print(f"Scanning {OUTPUT_DIR} for training data...")
    
    # Walk through all timestamped directories
    for root, dirs, files in os.walk(OUTPUT_DIR):
        if "ai_reports" in root: # We look into ai_reports folder for analyzed files
            # Check for _analysis.xlsx files
            for file in files:
                if file.endswith("_analysis.xlsx"):
                    analysis_path = os.path.join(root, file)
                    company_name = file.replace("_analysis.xlsx", "")
                    
                    # Try to find corresponding raw file
                    # Usually raw file is in the parent folder of ai_reports, or grandparent?
                    # Structure: output/TIMESTAMP/ai_reports/Company_analysis.xlsx
                    # Raw file: output/TIMESTAMP/Company_raw.xlsx (Maybe? Let's check logic in reporter.py)
                    # Actually Reporter saves raw data to session_dir directly.
                    # So raw path should be: root/../Company_raw.xlsx
                    
                    session_dir = os.path.dirname(root) # Go up one level
                    raw_filename = f"{company_name}_raw.xlsx"
                    raw_path = os.path.join(session_dir, raw_filename)
                    
                    if not os.path.exists(raw_path):
                        # Try to find anywhere in session_dir
                        possible_raw = os.path.join(session_dir, raw_filename)
                        if not os.path.exists(possible_raw):
                             # Maybe name sanitization changed something?
                             # Let's just look for any *_raw.xlsx in session_dir that matches start
                             pass
                    
                    if os.path.exists(raw_path):
                        process_pair(raw_path, analysis_path, dataset)
                    else:
                        # print(f"Missing raw file for {company_name}")
                        pass
                        
    return dataset

def process_pair(raw_path, analysis_path, dataset):
    try:
        # Read Raw Data (All Candidates)
        df_raw = pd.read_excel(raw_path)
        raw_titles = set()
        if 'title' in df_raw.columns:
            raw_titles = {str(t).strip() for t in df_raw['title'].dropna() if str(t).strip()}
            
        # Read Analysis Data (Valid Assets)
        # Sheet 'Valid Assets' contains the positives
        try:
            df_valid = pd.read_excel(analysis_path, sheet_name='Valid Assets')
            valid_titles = set()
            if 'title' in df_valid.columns:
                valid_titles = {str(t).strip() for t in df_valid['title'].dropna() if str(t).strip()}
        except ValueError:
            # Maybe old format or sheet missing
            return

        # Labeling
        # Positive: In Valid Assets
        # Negative: In Raw but NOT in Valid Assets
        
        pos_count = 0
        neg_count = 0
        
        for title in raw_titles:
            # Simple cleaning
            if len(title) < 2: continue
            
            if title in valid_titles:
                dataset.append({"text": title, "label": 1})
                pos_count += 1
            else:
                dataset.append({"text": title, "label": 0})
                neg_count += 1
                
        # print(f"Processed {os.path.basename(raw_path)}: +{pos_count} / -{neg_count}")
        
    except Exception as e:
        print(f"Error processing {raw_path}: {e}")

def main():
    dataset = scan_reports()
    
    if not dataset:
        print("No training data found! Please run some AI analysis tasks first.")
        return
        
    df = pd.DataFrame(dataset)
    
    # Remove duplicates
    df.drop_duplicates(subset=['text'], inplace=True)
    
    # Check balance
    counts = df['label'].value_counts()
    print("\nDataset Balance:")
    print(counts)
    
    # Save
    df.to_csv(DATASET_FILE, index=False, encoding='utf-8')
    print(f"\nSaved {len(df)} samples to {DATASET_FILE}")
    print("Ready for training!")

if __name__ == "__main__":
    main()