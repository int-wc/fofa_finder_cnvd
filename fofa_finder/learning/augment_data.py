# -*- coding: utf-8 -*-
import pandas as pd
import os
import requests
import json
import time
import logging
import sys
import random

# Add project root to sys.path to import config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

from fofa_finder.config import Config
# Import shared logger setup
from fofa_finder.modules.logger import setup_logger

logger = setup_logger("Augment")

EXCEL_FILE = os.path.join(BASE_DIR, "company_list.xlsx")
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_dataset.csv")

def call_deepseek(company_name):
    """
    Call DeepSeek API to judge company eligibility
    """
    api_key = Config.DEEPSEEK_API_KEY
    base_url = Config.DEEPSEEK_BASE_URL
    
    # Adjust URL
    if "/v1" in base_url:
        url = base_url.replace("/v1", "/chat/completions")
    else:
        url = f"{base_url}/chat/completions"

    prompt = f"""
    请分析公司 "{company_name}" 的业务属性，判断其是否适合作为 CNVD (国家信息安全漏洞共享平台) 的通用型漏洞挖掘对象。
    
    判断标准 (必须同时满足):
    1. **行业属性**: 属于计算机、软件、互联网、Web开发、大数据、云计算等技术驱动型行业，或者拥有自研的 Web 软件产品（如 CMS、OA、ERP、平台系统）。
    2. **排除对象**: 纯传统行业（如房地产、餐饮、传统出版、制造、物流、投资公司等），除非它们明确转型为科技公司或以软件产品为主营业务。
    
    请非常严格地进行筛选，如果不确定或倾向于传统行业，请返回 false。
    
    请仅返回 JSON 格式结果:
    {{
        "eligible": true/false,
        "reason": "简短的判断理由"
    }}
    """
    
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
            timeout=30
        )
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            return data.get('eligible', False), data.get('reason', 'No reason')
        else:
            print(f"API Error: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"Request failed: {e}")
        return None, None

def augment(batch_size=20):
    logger.info("=== 开始数据增强流程 ===")
    
    # 1. Load Excel
    if not os.path.exists(Config.INPUT_FILE):
        logger.error(f"Input file not found: {Config.INPUT_FILE}")
        return 0
    
    logger.info(f"Reading {Config.INPUT_FILE}...")
    try:
        # Read header from row 2 (index 1)
        df_excel = pd.read_excel(Config.INPUT_FILE, header=1)
        # Assuming '企业名称' is the column name, verify
        if '企业名称' not in df_excel.columns:
            # Fallback if header detection failed, try finding column containing '公司'
            logger.warning(f"Columns: {df_excel.columns}")
            # Try to find the right column
            col = [c for c in df_excel.columns if '名称' in str(c) or '企业' in str(c)]
            if col:
                company_col = col[0]
            else:
                logger.error("Could not identify company name column.")
                return 0
        else:
            company_col = '企业名称'
            
        all_companies = df_excel[company_col].dropna().astype(str).unique().tolist()
        logger.info(f"Found {len(all_companies)} companies in Excel.")
        
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        return 0

    # 2. Load Existing Dataset
    existing_companies = set()
    if os.path.exists(DATASET_FILE):
        df_dataset = pd.read_csv(DATASET_FILE)
        existing_companies = set(df_dataset['company'].astype(str).tolist())
        logger.info(f"Existing dataset has {len(existing_companies)} samples.")
        
    # 3. Filter Candidates
    # Strategy: Prioritize "Tech" keywords to balance dataset
    keywords = ["科技", "网络", "信息", "软件", "数据", "系统", "智能", "云", "通信", "电子"]
    
    candidates = []
    for comp in all_companies:
        if comp in existing_companies:
            continue
        
        # Check if it contains any keyword
        if any(kw in comp for kw in keywords):
            candidates.append(comp)
            
    logger.info(f"Filtered {len(candidates)} high-potential candidates (containing keywords).")
    
    # If not enough candidates, add some random ones (to have negative samples too)
    if len(candidates) < batch_size:
        others = [c for c in all_companies if c not in existing_companies and c not in candidates]
        random.shuffle(others)
        candidates.extend(others[:batch_size - len(candidates)])
    
    # Shuffle and pick batch
    random.shuffle(candidates)
    target_batch = candidates[:batch_size]
    
    logger.info(f"\nSelected {len(target_batch)} companies for labeling:")
    for i, c in enumerate(target_batch):
        logger.info(f"  {i+1}. {c}")
        
    # 4. Query API
    new_data = []
    logger.info("Starting API labeling...")
    
    for i, company in enumerate(target_batch):
        # Using print for progress bar effect without newline
        # sys.stdout.write(f"[{i+1}/{len(target_batch)}] Analyzing: {company} ...")
        # sys.stdout.flush()
        
        eligible, reason = call_deepseek(company)
        
        if eligible is not None:
            status = "Eligible" if eligible else "Ineligible"
            # sys.stdout.write(f" -> {status}\n")
            logger.info(f"[{i+1}/{len(target_batch)}] {company} -> {status} ({reason})")
            new_data.append({
                "company": company,
                "label": 1 if eligible else 0,
                "reason": reason
            })
        else:
            # sys.stdout.write(" -> Failed\n")
            logger.error(f"[{i+1}/{len(target_batch)}] {company} -> Failed")
            
        # Rate limit
        time.sleep(1)
        
    # 5. Save
    if new_data:
        df_new = pd.DataFrame(new_data)
        
        if os.path.exists(DATASET_FILE):
            df_old = pd.read_csv(DATASET_FILE)
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset=['company'], keep='last', inplace=True)
            df_combined.to_csv(DATASET_FILE, index=False, encoding='utf-8-sig')
        else:
            df_new.to_csv(DATASET_FILE, index=False, encoding='utf-8-sig')
            
        logger.info(f"\nSuccessfully added {len(new_data)} new samples to {DATASET_FILE}")
        return len(new_data)
    else:
        logger.info("\nNo data added.")
        return 0

if __name__ == "__main__":
    augment(batch_size=20)
