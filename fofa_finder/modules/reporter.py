# -*- coding: utf-8 -*-
import pandas as pd
import os
import time
from .logger import setup_logger
from ..config import Config

logger = setup_logger("Reporter")

class Reporter:
    def __init__(self):
        # Create session directory based on timestamp
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(Config.OUTPUT_DIR, self.timestamp)
        
        # Ensure directory exists
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
            
        # Create ai_reports subdirectory
        self.reports_dir = os.path.join(self.session_dir, "ai_reports")
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
            
        logger.info(f"Report Session Directory: {self.session_dir}")

    def _sanitize_filename(self, name):
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name

    def save_raw_data(self, company_name, assets):
        """
        保存原始数据 (无 AI 分析)
        路径: output/YYYYMMDD_HHMMSS/Company_raw.xlsx
        """
        safe_name = self._sanitize_filename(company_name)
        filename = f"{safe_name}_raw.xlsx"
        filepath = os.path.join(self.session_dir, filename)
        
        try:
            df_assets = pd.DataFrame(assets)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_assets.to_excel(writer, sheet_name='Raw Assets', index=False)
                
            logger.info(f"原始数据已保存至: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存原始数据失败 ({company_name}): {e}")
            return None

    def save_ai_markdown(self, company_name, analysis_data):
        """
        保存 AI 分析报告为 Markdown 文件 (CNVD 深度分析版)
        路径: output/YYYYMMDD_HHMMSS/ai_reports/Company_analysis.md
        """
        safe_name = self._sanitize_filename(company_name)
        filename = f"{safe_name}_analysis.md"
        filepath = os.path.join(self.reports_dir, filename)
        
        try:
            summary = analysis_data.get('summary', '无')
            strategy = analysis_data.get('cnvd_strategy', '无')
            
            content = f"# {company_name} 资产安全审计报告\n\n"
            content += f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            content += "## 1. 资产梳理总结\n"
            content += f"{summary}\n\n"
            
            content += "## 2. CNVD 挖掘策略建议\n"
            content += f"{strategy}\n\n"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                
            logger.info(f"AI Markdown 报告已保存至: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存 Markdown 报告失败 ({company_name}): {e}")
            return None

    def save_ai_report(self, company_name, clean_assets, cnvd_assets, analysis_data):
        """
        保存 AI 分析报告 (Excel)
        路径: output/YYYYMMDD_HHMMSS/ai_reports/Company_analysis.xlsx
        包含 Sheet:
        1. Clean Assets (AI 清洗后的有效资产)
        2. CNVD Candidates (建议重点测试的资产)
        3. Overview (概览)
        """
        safe_name = self._sanitize_filename(company_name)
        filename = f"{safe_name}_analysis.xlsx"
        filepath = os.path.join(self.reports_dir, filename)
        
        try:
            df_clean = pd.DataFrame(clean_assets)
            df_cnvd = pd.DataFrame(cnvd_assets)
            
            df_overview = pd.DataFrame([{
                'Company': company_name,
                'Total Valid Assets': len(clean_assets),
                'CNVD Candidates': len(cnvd_assets),
                'Summary': analysis_data.get('summary', ''),
                'Strategy': analysis_data.get('cnvd_strategy', '')
            }])
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_overview.to_excel(writer, sheet_name='Overview', index=False)
                df_clean.to_excel(writer, sheet_name='Valid Assets', index=False)
                if not df_cnvd.empty:
                    df_cnvd.to_excel(writer, sheet_name='CNVD Candidates', index=False)
                
            logger.info(f"AI 分析报告(Excel)已保存至: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存 AI 报告失败 ({company_name}): {e}")
            return None
