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
        支持智能表头识别
        返回: list of dicts [{'name': '...', 'matched_keyword': '...'}]
        """
        logger.info(f"正在加载 Excel 文件: {self.file_path}")
        
        try:
            # 1. 尝试智能读取表头
            # 读取前 5 行用于探测
            df_preview = pd.read_excel(self.file_path, nrows=5, header=None)
            
            header_row_idx = -1
            name_col_idx = -1
            capital_col_idx = -1
            scope_col_idx = -1
            
            # 关键词映射
            name_keywords = ['企业名称', '公司名称', '名称', 'Company']
            capital_keywords = ['实缴资本', '注册资本', 'Capital', '资金']
            scope_keywords = ['经营范围', '业务范围', 'Scope', '行业']
            
            # 探测逻辑
            for r_idx, row in df_preview.iterrows():
                row_values = [str(v).strip() for v in row.values]
                
                # 查找列索引
                c_name = next((i for i, v in enumerate(row_values) if any(k in v for k in name_keywords)), -1)
                c_cap = next((i for i, v in enumerate(row_values) if any(k in v for k in capital_keywords)), -1)
                c_scope = next((i for i, v in enumerate(row_values) if any(k in v for k in scope_keywords)), -1)
                
                # 如果找到至少两个关键列，就认为是表头行
                matches = sum([1 for x in [c_name, c_cap, c_scope] if x != -1])
                if matches >= 2:
                    header_row_idx = r_idx
                    name_col_idx = c_name
                    capital_col_idx = c_cap
                    scope_col_idx = c_scope
                    logger.info(f"智能识别表头在第 {r_idx+1} 行: 名称(Col {c_name}), 资本(Col {c_cap}), 范围(Col {c_scope})")
                    break
            
            # 2. 读取完整数据
            if header_row_idx != -1:
                # 使用识别到的表头
                df = pd.read_excel(self.file_path, header=header_row_idx)
                # Pandas header=N means row N is header, data starts from N+1
                # But we need column indices from original raw read
                # Actually, easier to read raw and use indices
                df = pd.read_excel(self.file_path, header=None, skiprows=header_row_idx+1)
            else:
                # Fallback: Hardcoded indices (A, E, AA)
                logger.warning("未识别到明确表头，尝试使用默认列索引 (A=名称, E=资本, AA=范围)...")
                df = pd.read_excel(self.file_path, header=None)
                name_col_idx = 0
                capital_col_idx = 4
                scope_col_idx = 26
            
            # 3. Process Data
            valid_companies = []
            
            for index, row in df.iterrows():
                # Safe access
                if name_col_idx >= len(row): continue
                company_name = row[name_col_idx]
                
                capital_raw = row[capital_col_idx] if capital_col_idx != -1 and capital_col_idx < len(row) else 0
                business_scope = row[scope_col_idx] if scope_col_idx != -1 and scope_col_idx < len(row) else ""
                
                # 跳过空名称
                if pd.isna(company_name) or str(company_name).strip() == "":
                    continue
                    
                company_name = str(company_name).strip()
                
                # 简单的跳过表头逻辑 (if manual read)
                if isinstance(capital_raw, str) and ("实缴" in capital_raw or "资本" in capital_raw):
                    continue
                    
                # 1. 检查实缴资本
                capital_val = self.parse_capital(capital_raw)
                if capital_val <= Config.CAPITAL_THRESHOLD:
                    continue
                    
                # 2. 检查经营范围
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
