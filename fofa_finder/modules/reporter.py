# -*- coding: utf-8 -*-
import pandas as pd
import os
import time
import shutil
from .logger import setup_logger
from ..config import Config

logger = setup_logger("Reporter")

class Reporter:
    def __init__(self):
        # Create session directory based on timestamp in realtime folder
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(Config.OUTPUT_DIR, "realtime", self.timestamp)
        
        # Ensure session directory exists
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
            
        # Create subdirectories for session
        self.raw_dir = os.path.join(self.session_dir, "raw_data")
        self.analysis_dir = os.path.join(self.session_dir, "analysis_data")
        self.report_dir = os.path.join(self.session_dir, "report_data")
        
        for d in [self.raw_dir, self.analysis_dir, self.report_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
            
        logger.info(f"Report Session Directory: {self.session_dir}")

    def _sanitize_filename(self, name):
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name

    def _archive_file(self, filepath, category):
        """
        Archive file to nested date directories:
        - output/YYYY/category/
        - output/YYYY/MM/category/
        - output/YYYY/MM/DD/category/
        """
        if not filepath or not os.path.exists(filepath):
            return

        try:
            filename = os.path.basename(filepath)
            now = time.localtime()
            year = time.strftime("%Y", now)
            month = time.strftime("%m", now)
            day = time.strftime("%d", now)
            
            # Define archive base paths
            archive_bases = [
                os.path.join(Config.OUTPUT_DIR, year),
                os.path.join(Config.OUTPUT_DIR, year, month),
                os.path.join(Config.OUTPUT_DIR, year, month, day)
            ]
            
            for base in archive_bases:
                target_dir = os.path.join(base, category)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                
                target_path = os.path.join(target_dir, filename)
                shutil.copy2(filepath, target_path)
                
        except Exception as e:
            logger.error(f"Archiving failed for {filepath}: {e}")

    def save_raw_data(self, company_name, assets):
        """
        Save raw data to session dir and archive it.
        Category: raw_data
        """
        safe_name = self._sanitize_filename(company_name)
        filename = f"{safe_name}_raw.xlsx"
        filepath = os.path.join(self.raw_dir, filename)
        
        try:
            df_assets = pd.DataFrame(assets)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_assets.to_excel(writer, sheet_name='Raw Assets', index=False)
                
            logger.info(f"原始数据已保存至: {filepath}")
            
            # Archive
            self._archive_file(filepath, "raw_data")
            
            return filepath
        except Exception as e:
            logger.error(f"保存原始数据失败 ({company_name}): {e}")
            return None

    def save_ai_markdown(self, company_name, analysis_data):
        """
        Save markdown report to session dir and archive it.
        Category: report_data
        """
        safe_name = self._sanitize_filename(company_name)
        filename = f"{safe_name}_analysis.md"
        filepath = os.path.join(self.report_dir, filename)
        
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
            
            # Archive
            self._archive_file(filepath, "report_data")
            
            return filepath
        except Exception as e:
            logger.error(f"保存 Markdown 报告失败 ({company_name}): {e}")
            return None

    def save_ai_report(self, company_name, clean_assets, cnvd_assets, analysis_data):
        """
        Save AI analysis excel to session dir and archive it.
        Category: analysis_data
        """
        safe_name = self._sanitize_filename(company_name)
        filename = f"{safe_name}_analysis.xlsx"
        filepath = os.path.join(self.analysis_dir, filename)
        
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
            
            # Archive
            self._archive_file(filepath, "analysis_data")
            
            return filepath
        except Exception as e:
            logger.error(f"保存 AI 报告失败 ({company_name}): {e}")
            return None
