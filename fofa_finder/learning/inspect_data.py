# -*- coding: utf-8 -*-
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "dataset.csv")

def inspect():
    if not os.path.exists(DATASET_FILE):
        print("Dataset not found")
        return
        
    df = pd.read_csv(DATASET_FILE)
    print(f"Total samples: {len(df)}")
    
    keywords = ["404", "nginx", "VPN", "后台", "管理"]
    
    for kw in keywords:
        print(f"\n--- Searching for '{kw}' ---")
        matches = df[df['text'].str.contains(kw, case=False, na=False)]
        print(f"Found {len(matches)} matches.")
        if len(matches) > 0:
            print("Sample (Text -> Label):")
            # Show first 10 matches with their labels
            for idx, row in matches.head(10).iterrows():
                label_str = "保留(1)" if row['label'] == 1 else "丢弃(0)"
                print(f"  [{label_str}] {row['text'][:60]}")
                
            # Stats
            label_1 = len(matches[matches['label'] == 1])
            label_0 = len(matches[matches['label'] == 0])
            print(f"Stats: 1 (保留): {label_1}, 0 (丢弃): {label_0}")

if __name__ == "__main__":
    inspect()
