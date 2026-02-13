# -*- coding: utf-8 -*-
import sys
import os
import time
import argparse
from fofa_finder.modules.logger import setup_logger
from fofa_finder.config import Config
from fofa_finder.modules.excel_loader import ExcelLoader
from fofa_finder.modules.fofa_client import FofaClient
from fofa_finder.modules.analyzer import Analyzer
from fofa_finder.modules.reporter import Reporter
from fofa_finder.modules.reanalyzer import ReAnalyzer
from fofa_finder.learning.augment_data import augment
from fofa_finder.learning.train_company_model import train as train_company_model

logger = setup_logger("Main")

def main():
    parser = argparse.ArgumentParser(description="FOFA Finder - Corporate Asset Discovery Tool")
    parser.add_argument("--api-mode", action="store_true", help="Use FOFA Official API instead of Web Simulation")
    parser.add_argument("--local-ai", action="store_true", help="Force use Local AI Model instead of DeepSeek API")
    args = parser.parse_args()

    if args.api_mode:
        Config.FOFA_MODE = 'api'
        logger.info("Switching to FOFA Official API Mode via command line argument.")
        
    if args.local_ai:
        Config.USE_LOCAL_AI = True
        logger.info("Switching to Local AI Mode (Offline) via command line argument.")

    logger.info("正在启动 FOFA Finder...")
    
    # Auto-Learning Phase
    # logger.info("="*50)
    # logger.info(">>> 阶段 0: 自动学习与模型增强 (Auto Learning) <<<")
    # logger.info("="*50)
    # try:
    #     # Augment with small batch (e.g., 10) to keep startup fast but continuous
    #     added_count = augment(batch_size=10)
    #     if added_count > 0:
    #         logger.info(f"成功获取 {added_count} 条新样本，正在重新训练本地模型...")
    #         train_company_model()
    #         logger.info("本地模型已更新！")
    #     else:
    #         logger.info("本次未发现新样本或未进行增强。")
    # except Exception as e:
    #     logger.warning(f"自动学习过程中出现异常 (非阻断性): {e}")
    
    # 默认关闭自动学习，以免新手用户运行时卡住或报错
    # 建议在文档中说明如何开启
    pass

    # 1. Load Companies
    loader = ExcelLoader()
    companies = loader.load_companies()
    
    if not companies:
        logger.error("未找到公司或 Excel 加载失败。")
        return

    logger.info(f"即将处理 {len(companies)} 家公司...")
    
    # 0. Historical Data Audit (Before Scan)
    # logger.info("="*50)
    # logger.info(">>> 阶段 1: 历史数据全量补漏分析 (Historical Audit) <<<")
    # logger.info("="*50)
    
    # reanalyzer = ReAnalyzer()
    # re_p_tokens, re_c_tokens = reanalyzer.run()
    re_p_tokens, re_c_tokens = 0, 0
    
    logger.info("\n")
    logger.info("="*50)
    logger.info(">>> 阶段 2: 新一轮资产扫描任务 (New Scan Task) <<<")
    logger.info("="*50)

    # Initialize Modules
    fofa_client = FofaClient()
    analyzer = Analyzer()
    reporter = Reporter()
    
    # Check Balance (Start)
    initial_balance_str = analyzer.get_account_balance()
    logger.info(f"[DeepSeek] 初始账户余额: {initial_balance_str}")
    
    # Try to parse initial balance to float for estimation
    try:
        # Assuming format "¥ 50.00" or similar, extract number
        import re
        balance_match = re.search(r'([\d\.]+)', str(initial_balance_str))
        initial_balance = float(balance_match.group(1)) if balance_match else 0.0
    except:
        initial_balance = 0.0
        
    # 0. Self-Check Token
    logger.info("正在执行自检 (Self-check)，目标: Baidu...")
    token_valid, msg = fofa_client.check_token_status()
    if not token_valid:
        logger.critical(f"自检失败 (FAILED): {msg}")
        logger.critical("请更新 d:\\cnvd_new\\http_request.txt (以及 http2/3.txt) 中的 FOFA Token/Cookie！")
        logger.critical("程序即将退出。")
        return
    else:
        logger.info(f"自检通过 (PASSED): {msg}")

    # Cost Tracking (Initialize with re-analysis usage)
    total_prompt_tokens = re_p_tokens
    total_completion_tokens = re_c_tokens
    
    # Calculate initial cost from re-analysis
    re_cost = (re_p_tokens / 1_000_000 * 2.0) + (re_c_tokens / 1_000_000 * 8.0)
    total_cost_cny = re_cost # Global cumulative cost
    
    # Progress Tracking
    progress_file = os.path.join(Config.OUTPUT_DIR, "progress.txt")
    processed_companies = set()
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            processed_companies = set(line.strip() for line in f if line.strip())
        logger.info(f"已加载进度: {len(processed_companies)} 家公司已处理 (Skipping them)")

    # Balance Calibration Settings
    BALANCE_CHECK_INTERVAL = 20 # Check real balance every 20 companies
    
    for idx, company_data in enumerate(companies):
        company_name = company_data['name']
        
        # Periodic Balance Calibration
        if idx > 0 and idx % BALANCE_CHECK_INTERVAL == 0:
            try:
                # logger.info("正在校准账户余额...")
                real_balance_str = analyzer.get_account_balance()
                import re
                balance_match = re.search(r'([\d\.]+)', str(real_balance_str))
                if balance_match:
                    new_balance = float(balance_match.group(1))
                    # Reset estimation base
                    initial_balance = new_balance
                    total_cost_cny = 0.0 # Reset cumulative cost relative to this new checkpoint
                    # logger.info(f"余额校准完成: {new_balance}")
            except Exception as e:
                logger.warning(f"余额校准失败: {e}")

        # Resume Check
        if company_name in processed_companies:
            # logger.info(f"跳过已处理公司: {company_name}") # Silence skip logs to reduce noise
            continue
            
        # Estimate current balance
        est_balance = initial_balance - total_cost_cny
        balance_info = f" | 余额≈¥{est_balance:.2f}" if initial_balance > 0 else ""
        
        logger.info(f"[{idx+1}/{len(companies)}] 正在处理: {company_name} (匹配业务: {company_data['matched_keyword']}){balance_info}")
        
        # 1. Analyze Name
        keywords = analyzer.split_company_name(company_name)
        
        found_assets = False
        all_company_assets = []
        
        for kw in keywords:
            # 2. Search
            raw_result, query_syntax = fofa_client.search(kw)
            if not raw_result:
                logger.warning(f"关键词 '{kw}' 无查询结果")
                continue
                
            # 3. Extract Assets
            kw_assets = analyzer.extract_assets(raw_result)
            
            # Local Filtering (Junk)
            kw_assets = analyzer.filter_junk_assets(kw_assets)
            
            if not kw_assets:
                logger.warning(f"关键词 '{kw}' 无查询结果 (或全部被过滤)")
                continue
                
            # Add metadata
            for asset in kw_assets:
                asset['fofa_query'] = query_syntax
                asset['search_keyword'] = kw
                
            all_company_assets.extend(kw_assets)
            found_assets = True
            
            # Rate Limit (per keyword)
            time.sleep(2) 

        if not found_assets:
            logger.warning(f"公司 {company_name} (所有关键词) 未发现任何资产")
            # Mark as processed even if no assets found
            with open(progress_file, 'a', encoding='utf-8') as f:
                f.write(f"{company_name}\n")
            continue
            
        # 4. Filter Fingerprint (Consolidate assets first)
        # Deduplicate assets by link
        unique_assets = {a['link']: a for a in all_company_assets}.values()
        all_company_assets = list(unique_assets)
        
        logger.info(f"公司 {company_name} 共发现 {len(all_company_assets)} 个唯一资产")
        
        # 5. Save Raw Data (Always save if assets found)
        reporter.save_raw_data(company_name, all_company_assets)
        
        # 6. AI Analysis (New Full Audit Mode)
        if all_company_assets: # Always analyze if we have assets
            clean_assets, cnvd_assets, usage, analysis_data = analyzer.analyze_with_ai(company_name, all_company_assets)
            
            # Accumulate Cost
            p_tokens = usage.get('prompt_tokens', 0)
            c_tokens = usage.get('completion_tokens', 0)
            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            
            # Calculate current cost
            current_cost = (p_tokens / 1_000_000 * 2.0) + (c_tokens / 1_000_000 * 8.0)
            total_cost_cny += current_cost
            
            # Re-estimate balance after cost update
            est_balance = initial_balance - total_cost_cny
            
            logger.info(f"AI 分析完成: {company_name} | 本次花费: ¥{current_cost:.4f} | 累计花费: ¥{total_cost_cny:.4f} | 余额≈¥{est_balance:.2f}")
            
            # 7. Save Reports
            reporter.save_ai_report(company_name, clean_assets, cnvd_assets, analysis_data)
            reporter.save_ai_markdown(company_name, analysis_data) 
        else:
            logger.warning(f"无资产可分析: {company_name}")
            
        # Mark as processed
        with open(progress_file, 'a', encoding='utf-8') as f:
            f.write(f"{company_name}\n")
            
        # Rate Limit (per company)
        time.sleep(Config.RATE_LIMIT_MIN)
        
    # Cost Summary
    # Pricing (Approx DeepSeek V3): Input 2元/1M, Output 8元/1M
    input_cost = (total_prompt_tokens / 1_000_000) * 2.0
    output_cost = (total_completion_tokens / 1_000_000) * 8.0
    total_cost = input_cost + output_cost
    
    logger.info("="*50)
    logger.info("任务统计 (Task Statistics)")
    logger.info(f"Total Prompt Tokens: {total_prompt_tokens}")
    logger.info(f"Total Completion Tokens: {total_completion_tokens}")
    logger.info(f"Estimated Cost (CNY): ¥{total_cost:.4f}")
    
    # Check Balance (End)
    final_balance = analyzer.get_account_balance()
    logger.info(f"[DeepSeek] 结束账户余额: {final_balance}")
    
    logger.info("="*50)

    logger.info("所有任务已完成。")

if __name__ == "__main__":
    main()
