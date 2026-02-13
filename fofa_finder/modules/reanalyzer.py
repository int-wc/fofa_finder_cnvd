# -*- coding: utf-8 -*-
import os
import pandas as pd
import time
from .analyzer import Analyzer
from .reporter import Reporter
from .logger import setup_logger
from ..config import Config

logger = setup_logger("ReAnalyzer")

class ReAnalyzer:
    def __init__(self):
        self.analyzer = Analyzer()
        self.reporter = Reporter() # Creates new session dir automatically for this run
        self.progress_file = os.path.join(Config.OUTPUT_DIR, "reanalysis_progress.txt")

    def find_raw_files(self, root_dir):
        """
        递归查找所有 _raw.xlsx 文件
        """
        raw_files = []
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.endswith("_raw.xlsx"):
                    raw_files.append(os.path.join(root, file))
        return raw_files

    def extract_company_name(self, filename):
        """
        从文件名提取公司名称
        """
        basename = os.path.basename(filename)
        name = basename.replace("_raw.xlsx", "")
        return name

    def run(self):
        """
        执行历史数据重分析
        返回: (prompt_tokens, completion_tokens)
        """
        logger.info("启动历史数据重分析 (Re-analysis Mode)...")
        
        # Load Progress
        processed_files = set()
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                processed_files = set(line.strip() for line in f if line.strip())
            logger.info(f"已加载进度: {len(processed_files)} 个文件已处理")

        # Check Balance (Start)
        initial_balance = self.analyzer.get_account_balance()
        logger.info(f"[DeepSeek] 初始账户余额: {initial_balance}")

        # Find files (Today and Yesterday only)
        all_raw_files = self.find_raw_files(Config.OUTPUT_DIR)
        
        # Filter by time
        target_files = []
        now = time.time()
        one_day = 86400
        # Consider files from last 48 hours to be safe for "Today + Yesterday"
        time_threshold = now - (2 * one_day)
        
        for f in all_raw_files:
            mtime = os.path.getmtime(f)
            if mtime > time_threshold:
                target_files.append(f)
                
        logger.info(f"扫描到 {len(all_raw_files)} 个原始文件，其中 {len(target_files)} 个为近期(48h内)文件")
        
        # Cost Tracking
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost_cny = 0.0
        
        for idx, filepath in enumerate(target_files):
            # Unique ID for progress: filepath
            if filepath in processed_files:
                continue
                
            company_name = self.extract_company_name(filepath)
            logger.info(f"[{idx+1}/{len(target_files)}] 正在重分析: {company_name} (File: {os.path.basename(filepath)})")
            
            try:
                # Pre-check eligibility
                eligible, reason, usage = self.analyzer.check_company_eligibility(company_name)
                
                # Accumulate cost for pre-check
                p_tokens = usage.get('prompt_tokens', 0)
                c_tokens = usage.get('completion_tokens', 0)
                total_prompt_tokens += p_tokens
                total_completion_tokens += c_tokens
                current_cost = (p_tokens / 1_000_000 * 2.0) + (c_tokens / 1_000_000 * 8.0)
                total_cost_cny += current_cost
                
                if not eligible:
                    logger.info(f"[AI Filter] 跳过非目标公司: {company_name} ({reason}) | 累计花费: ¥{total_cost_cny:.4f}")
                    with open(self.progress_file, 'a', encoding='utf-8') as f:
                        f.write(f"{filepath}\n")
                    continue

                # Read Excel
                df = pd.read_excel(filepath)
                assets = df.to_dict('records')
                
                if not assets:
                    logger.warning(f"文件为空或无资产: {filepath}")
                    with open(self.progress_file, 'a', encoding='utf-8') as f:
                        f.write(f"{filepath}\n")
                    continue
                    
                # AI Analysis (New Interface)
                # Returns: clean_assets, cnvd_assets, usage, analysis_data
                clean_assets, cnvd_assets, usage, analysis_data = self.analyzer.analyze_with_ai(company_name, assets)
                
                # Accumulate Cost
                p_tokens = usage.get('prompt_tokens', 0)
                c_tokens = usage.get('completion_tokens', 0)
                total_prompt_tokens += p_tokens
                total_completion_tokens += c_tokens
                
                # Calculate current cost
                current_cost = (p_tokens / 1_000_000 * 2.0) + (c_tokens / 1_000_000 * 8.0)
                total_cost_cny += current_cost
                
                logger.info(f"分析完成: {company_name} | 原始: {len(assets)} -> 有效: {len(clean_assets)} | 本次花费: ¥{current_cost:.4f} | 累计花费: ¥{total_cost_cny:.4f}")
                
                # Save Reports
                self.reporter.save_ai_report(company_name, clean_assets, cnvd_assets, analysis_data)
                self.reporter.save_ai_markdown(company_name, analysis_data)
                
                # Mark as processed
                with open(self.progress_file, 'a', encoding='utf-8') as f:
                    f.write(f"{filepath}\n")
                    
                # Rate Limit
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"处理文件失败 {filepath}: {e}")
        
        # Check Balance (End)
        final_balance = self.analyzer.get_account_balance()
        logger.info(f"[DeepSeek] 结束账户余额: {final_balance}")
                
        return total_prompt_tokens, total_completion_tokens