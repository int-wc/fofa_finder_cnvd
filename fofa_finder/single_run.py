# -*- coding: utf-8 -*-
import argparse
from fofa_finder.modules.fofa_client import FofaClient
from fofa_finder.modules.analyzer import Analyzer
from fofa_finder.modules.reporter import Reporter
from fofa_finder.modules.logger import setup_logger
from fofa_finder.config import Config

logger = setup_logger("SingleRun")

def run_single(company_name):
    logger.info(f"Test running for company: {company_name}")
    
    fofa = FofaClient()
    analyzer = Analyzer()
    reporter = Reporter()
    
    # Search
    raw, query_syntax = fofa.search(company_name)
    
    # Extract
    assets = analyzer.extract_assets(raw)
    
    # Local Filtering (Junk)
    assets = analyzer.filter_junk_assets(assets)
    
    if not assets:
        logger.error("Search failed or no assets found (after filtering).")
        return
    
    # Add Query Syntax
    for asset in assets:
        asset['fofa_query'] = query_syntax
        
    logger.info(f"Found {len(assets)} assets.")
    
    # Filter
    passed, reason = analyzer.filter_by_fingerprint(assets)
    logger.info(f"Filter result: {passed} - {reason}")
    
    if passed:
        # Save Raw Data
        reporter.save_raw_data(company_name, assets)
        
        # Analyze
        analysis = analyzer.analyze_with_ai(company_name, assets)
        print(f"AI Analysis:\n{analysis}")
        
        # Save AI Report
        path = reporter.save_ai_report(company_name, assets, analysis)
        logger.info(f"AI Report saved to {path}")
        
        # Save AI Markdown
        md_path = reporter.save_ai_markdown(company_name, analysis)
        if md_path:
            logger.info(f"AI Markdown Report saved to {md_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run single company search")
    parser.add_argument("company", nargs="?", default="百度", help="Company name to search")
    parser.add_argument("--api-mode", action="store_true", help="Use FOFA Official API")
    args = parser.parse_args()

    if args.api_mode:
        Config.FOFA_MODE = 'api'
        logger.info("Switching to FOFA Official API Mode via command line argument.")

    run_single(args.company)
