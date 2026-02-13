# -*- coding: utf-8 -*-
import pandas as pd
import re
import warnings
from .logger import setup_logger
from ..config import Config
from .local_engine import LocalEngine

# Filter warnings
warnings.filterwarnings("ignore", category=UserWarning)

logger = setup_logger("ExcelLoader")

class ExcelLoader:
    def __init__(self, file_path=None):
        self.file_path = file_path or Config.INPUT_FILE
        # Initialize Local Engine for pre-filtering
        self.local_engine = LocalEngine()

    def parse_capital(self, value):
        """
        解析注册资本/实缴资本
        返回单位：元
        """
        if pd.isna(value) or value == "":
            return 0
            
        value_str = str(value).strip()
        
        # 移除逗号
        value_str = value_str.replace(',', '')
        
        # 提取数字部分
        num_match = re.search(r'([\d\.]+)', value_str)
        if not num_match:
            return 0
            
        try:
            num = float(num_match.group(1))
        except ValueError:
            return 0
            
        # 处理单位
        if '亿' in value_str:
            return num * 100000000
        elif '万' in value_str:
            return num * 10000
        else:
            # 如果没有单位，尝试根据数值大小判断，或者默认为元
            # 这里假设如果只是纯数字，通常是元
            return num

    def load_companies(self):
        """
        读取 Excel，筛选实缴资本 > 5000万 且 经营范围包含特定关键词 的公司
        返回: list of dicts [{'name': '...', 'matched_keyword': '...'}]
        """
        logger.info(f"正在加载 Excel 文件: {self.file_path}")
        
        try:
            # 尝试读取 Excel，不带 header，因为不确定第一行是不是 header
            # 用户说 E 列是实缴资本，A 列是企业名称，AA 列 (index 26) 是经营范围
            # Pandas use 0-based index. A=0, E=4, AA=26.
            df = pd.read_excel(self.file_path, header=None)
            
            valid_companies = []
            
            for index, row in df.iterrows():
                company_name = row[0] # Column A
                capital_raw = row[4]  # Column E
                business_scope = row[26] if len(row) > 26 else "" # Column AA
                
                # 跳过空名称
                if pd.isna(company_name) or str(company_name).strip() == "":
                    continue
                    
                company_name = str(company_name).strip()
                
                # 简单的跳过表头逻辑
                if isinstance(capital_raw, str) and ("实缴" in capital_raw or "资本" in capital_raw):
                    continue
                    
                # 1. 检查实缴资本
                capital_val = self.parse_capital(capital_raw)
                if capital_val <= Config.CAPITAL_THRESHOLD:
                    continue
                    
                # 2. 检查经营范围 (Column AA)
                if pd.isna(business_scope):
                    continue
                    
                scope_str = str(business_scope)
                matched_kw = None
                for kw in Config.BUSINESS_SCOPE_KEYWORDS:
                    if kw in scope_str:
                        matched_kw = kw
                        break
                        
                if matched_kw:
                    # Filter 2: Local AI Check (Pre-filtering)
                    # Check if company name sounds like a tech company
                    # This saves API calls and FOFA search credits
                    is_eligible, reason, _ = self.local_engine.predict_company_eligibility(company_name)
                    
                    if is_eligible:
                        valid_companies.append({
                            'name': company_name,
                            'matched_keyword': matched_kw
                        })
                    else:
                        # Log implicitly or just skip
                        # We might want to count how many we skipped
                        pass
            
            logger.info(f"从 {len(df)} 行数据中筛选出 {len(valid_companies)} 家符合条件 (资本+经营范围+AI初筛) 的公司。")
            return valid_companies
            
        except Exception as e:
            logger.error(f"Excel 加载失败: {str(e)}")
            return []

if __name__ == "__main__":
    # Test
    loader = ExcelLoader()
    companies = loader.load_companies()
    print(f"Sample companies: {companies[:5]}")
