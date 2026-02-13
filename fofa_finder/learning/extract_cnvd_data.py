# -*- coding: utf-8 -*-
import os
import pandas as pd
import glob
import logging
import sys

# Configure Logger
logger = logging.getLogger("ExtractCNVD")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('│  %(asctime)s  │  INFO      │  ExtractCNVD   │ %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Update report directory to search all timestamped folders
REPORT_DIR = os.path.join(BASE_DIR, "fofa_finder", "output")
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "cnvd_dataset.csv")

def extract():
    logger.info("=== 开始提取 CNVD 训练数据 ===")
    
    if not os.path.exists(REPORT_DIR):
        logger.error(f"Report directory not found: {REPORT_DIR}")
        return

    # Find all _analysis.xlsx files in all subdirectories of output
    # Pattern: output/YYYYMMDD_HHMMSS/ai_reports/*_analysis.xlsx
    search_pattern = os.path.join(REPORT_DIR, "**", "*_analysis.xlsx")
    files = glob.glob(search_pattern, recursive=True)
    
    logger.info(f"Found {len(files)} analysis reports.")
    
    data = []
    
    for file_path in files:
        try:
            # Read '资产分析' sheet (contains DeepSeek's judgment)
            # Or 'CNVD候选' sheet (contains positives)
            
            # Let's read '资产分析' first, it should have all valid assets and their status
            # Actually, reporter.py saves:
            # Sheet "资产分析": Valid assets with analysis
            # Sheet "CNVD候选": Subset of above
            
            # We want:
            # Positives (Label 1): Assets in "CNVD候选"
            # Negatives (Label 0): Assets in "资产分析" but NOT in "CNVD候选"
            
            # Read both sheets
            xls = pd.ExcelFile(file_path)
            
            # Debug print sheet names
            # logger.info(f"{os.path.basename(file_path)} sheets: {xls.sheet_names}")
            
            # Check for various sheet names
            sheet_map = {name.strip(): name for name in xls.sheet_names}
            
            # Find '资产分析' (Asset Analysis) sheet
            valid_sheet_name = None
            for key in ['资产分析', 'Valid Assets', 'Sheet1']:
                if key in sheet_map:
                    valid_sheet_name = sheet_map[key]
                    break
            
            if not valid_sheet_name:
                continue
                
            df_all_valid = pd.read_excel(xls, valid_sheet_name)
            
            cnvd_titles = set()
            # Try matching exact sheet name "CNVD候选" or "CNVD 候选"
            # reporter.py uses "CNVD候选"
            cnvd_sheet = next((s for s in xls.sheet_names if "CNVD" in s), None)
            
            if cnvd_sheet:
                df_cnvd = pd.read_excel(xls, cnvd_sheet)
                # Look for 'title' column, or maybe '标题'?
                # Assuming 'title' as per reporter.py
                title_col = next((c for c in df_cnvd.columns if 'title' in str(c).lower() or '标题' in str(c)), None)
                if title_col:
                    cnvd_titles = set(df_cnvd[title_col].dropna().astype(str).tolist())
            
            # Find title column in valid sheet
            title_col_valid = next((c for c in df_all_valid.columns if 'title' in str(c).lower() or '标题' in str(c)), None)
            
            if not title_col_valid:
                # Try finding column by content? No, risky.
                continue
                
            for _, row in df_all_valid.iterrows():
                title = str(row.get(title_col_valid, '')).strip()
                if not title or title.lower() == 'nan':
                    continue
                    
                label = 1 if title in cnvd_titles else 0
                
                data.append({
                    'title': title,
                    'label': label,
                    'source': os.path.basename(file_path)
                })
                
        except Exception as e:
            logger.warning(f"Error reading {os.path.basename(file_path)}: {e}")

    if not data:
        logger.warning("No data extracted.")
        return

    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Deduplicate
    df.drop_duplicates(subset=['title'], keep='last', inplace=True)
    
    # Save
    df.to_csv(DATASET_FILE, index=False, encoding='utf-8-sig')
    
    logger.info(f"Extracted {len(df)} unique samples.")
    logger.info(f"Positives (CNVD): {len(df[df.label==1])}")
    logger.info(f"Negatives (Normal): {len(df[df.label==0])}")
    logger.info(f"Dataset saved to {DATASET_FILE}")

if __name__ == "__main__":
    extract()
