# -*- coding: utf-8 -*-
import requests
import json
import time
import pandas as pd
import re
import os
import csv
from collections import Counter
from .logger import setup_logger
from .local_engine import LocalEngine
from ..config import Config

logger = setup_logger("Analyzer")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPANY_DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_dataset.csv")

class Analyzer:
    def __init__(self):
        self.api_key = Config.DEEPSEEK_API_KEY
        self.base_url = Config.DEEPSEEK_BASE_URL
        self.local_engine = LocalEngine() # Init local model
        self.use_local_model_fallback = True # Enable fallback
        self.force_local_model = Config.USE_LOCAL_AI # Force mode from config
        
        if self.force_local_model:
            logger.info("已启用强制本地 AI 模式 (Force Local AI Mode)")

    def get_account_balance(self):
        """
        查询 DeepSeek 账户余额
        """
        if self.force_local_model:
            return "本地模式 (N/A)"
            
        try:
            url = f"{self.base_url.replace('/v1', '')}/user/balance"
            # Adjust URL if base_url includes /v1 or not. 
            # Config.DEEPSEEK_BASE_URL usually is "https://api.deepseek.com" or "https://api.deepseek.com/v1"
            # Official doc says GET https://api.deepseek.com/user/balance
            if "/v1" in self.base_url:
                url = self.base_url.replace("/v1", "/user/balance")
            else:
                url = f"{self.base_url}/user/balance"

            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Expected: {"is_available": true, "balance_infos": [{"currency": "CNY", "total_balance": "0.00", ...}]}
                infos = data.get('balance_infos', [])
                if infos:
                    info = infos[0]
                    currency = info.get('currency', 'CNY')
                    balance = info.get('total_balance', '0.00')
                    return f"{balance} {currency}"
                return "未知 (Unknown Format)"
            else:
                logger.warning(f"查询余额失败: {response.status_code} - {response.text}")
                return "查询失败"
        except Exception as e:
            logger.error(f"查询余额异常: {e}")
            return "异常"

    def check_company_eligibility(self, company_name):
        """
        AI 预判：公司是否具备 CNVD 挖掘价值
        """
        # 如果强制本地模式，使用本地模型
        if self.force_local_model:
            return self.local_engine.predict_company_eligibility(company_name)
            
        logger.info(f"正在进行公司资质预判: {company_name}")
        
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
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                # 使用 deepseek-chat 快速判断，temperature 设低一点保证稳定性
                json={"model": "deepseek-chat", "messages": messages, "temperature": 0.1},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                usage = result.get('usage', {'prompt_tokens': 0, 'completion_tokens': 0})
                
                # 清理 Markdown
                content = content.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(content)
                    eligible = data.get('eligible', False)
                    reason = data.get('reason', 'AI 未提供理由')
                    
                    logger.info(f"资质预判结果: {eligible} - {reason}")
                    self._save_company_training_data(company_name, eligible, reason)
                    return eligible, reason, usage
                except json.JSONDecodeError:
                    logger.warning(f"AI 预判返回格式错误: {content}")
                    # 兜底：如果解析失败，为了不误杀，暂且返回 True? 或者 False?
                    # 考虑到要省钱，返回 False 比较安全，但在日志里记录警告
                    return False, "解析失败 (保守跳过)", usage
            else:
                logger.error(f"预判 API 请求失败: {response.status_code}")
                return False, "API Error", {}
                
        except Exception as e:
            logger.error(f"预判异常: {e}")
            if self.use_local_model_fallback:
                logger.warning("API 预判失败，切换至本地模型...")
                return self.local_engine.predict_company_eligibility(company_name)
            return False, f"Exception: {e}", {}

    def _save_company_training_data(self, company, eligible, reason):
        """
        保存公司资质预判数据到 CSV (Active Learning)
        """
        try:
            file_exists = os.path.exists(COMPANY_DATASET_FILE)
            with open(COMPANY_DATASET_FILE, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['company', 'label', 'reason'])
                writer.writerow([company, 1 if eligible else 0, reason])
        except Exception as e:
            logger.error(f"保存训练数据失败: {e}")

    def extract_assets(self, raw_data):
        """
        从 FOFA 原始响应中提取资产列表
        支持 Web 模式 (dict/list of dicts) 和 API 模式 (list of lists)
        """
        assets = []
        try:
            items = []
            is_api_mode = False
            
            if isinstance(raw_data, dict):
                if 'data' in raw_data:
                    items = raw_data['data'] # Web mode usually
                elif 'results' in raw_data:
                    items = raw_data['results'] # API mode usually
                    # Check if items[0] is list -> API mode
                    if items and isinstance(items[0], list):
                        is_api_mode = True
            elif isinstance(raw_data, list):
                items = raw_data
                
            for item in items:
                asset = {}
                
                if is_api_mode and isinstance(item, list):
                    # API Mode: fields='host,ip,port,title,protocol,country_name,region_name,city_name'
                    # item order matches fields
                    # Ensure index exists
                    try:
                        asset['link'] = item[0] if len(item) > 0 else ''
                        asset['ip'] = item[1] if len(item) > 1 else ''
                        asset['port'] = item[2] if len(item) > 2 else ''
                        asset['title'] = item[3] if len(item) > 3 else ''
                        # Extra fields can be stored if needed
                    except IndexError:
                        pass
                        
                elif isinstance(item, dict):
                    # Web Mode
                    asset['link'] = item.get('link', '') or item.get('host', '')
                    asset['title'] = item.get('title', '')
                    asset['ip'] = item.get('ip', '')
                    asset['port'] = item.get('port', '')
                
                if asset.get('link'):
                    assets.append(asset)
                    
        except Exception as e:
            logger.error(f"提取资产时出错: {e}")
            
        return assets

    def filter_junk_assets(self, assets):
        """
        本地过滤垃圾资产 (博彩、色情等)
        使用 Config.EXCLUDED_KEYWORDS
        """
        if not assets:
            return []
            
        clean_assets = []
        junk_count = 0
        
        excluded_kws = Config.EXCLUDED_KEYWORDS
        if not excluded_kws:
            return assets
            
        for asset in assets:
            title = asset.get('title', '') or ''
            link = asset.get('link', '') or ''
            
            # Check content
            content_to_check = (title + " " + link).lower()
            
            is_junk = False
            for kw in excluded_kws:
                if kw.lower() in content_to_check:
                    is_junk = True
                    break
            
            if is_junk:
                junk_count += 1
            else:
                clean_assets.append(asset)
                
        if junk_count > 0:
            logger.info(f"本地过滤: 移除 {junk_count} 个垃圾资产 (匹配关键词: {', '.join(excluded_kws[:3])}...)")
        
        return clean_assets

    def filter_by_fingerprint(self, assets):
        """
        筛选：是否有 > 10 条相同的网站指纹 (Title)
        返回: (Passed, details)
        """
        if not assets:
            return False, "无资产 (No assets)"
            
        titles = [a.get('title', '').strip() for a in assets if a.get('title')]
        if not titles:
            return False, "未找到标题 (No titles found)"
            
        # Count
        counter = Counter(titles)
        most_common = counter.most_common(1)
        
        if not most_common:
            return False, "无共同标题 (No common title)"
            
        top_title, count = most_common[0]
        
        # Threshold
        if count > Config.FINGERPRINT_THRESHOLD:
            return True, f"发现 {count} 个资产包含标题 '{top_title}'"
        else:
            return False, f"最大指纹数量 {count} <= {Config.FINGERPRINT_THRESHOLD}"

    def split_company_name(self, company_name):
        """
        使用 DeepSeek 将公司全称拆分为查询关键字
        例如: "北京放心科技服务有限公司" -> ["放心科技", "放心科技服务"]
        """
        logger.info(f"正在拆分公司名称: {company_name}")
        
        prompt = f"""
        请提取公司名称 "{company_name}" 的核心关键词，用于搜索引擎检索。
        
        要求:
        1. 去除 "北京"、"有限"、"公司"、"股份" 等通用地域和后缀词。
        2. 保留品牌名和核心业务词的组合。
        3. 输出 2-3 个最可能的简称或品牌词。
        4. 只返回 JSON 数组，不要包含其他文本。
        
        示例:
        输入: "北京放心科技服务有限公司"
        输出: ["放心科技", "放心科技服务"]
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                # 使用 deepseek-chat (无思考) 节省时间
                json={"model": "deepseek-chat", "messages": messages, "temperature": 0.1},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                # 清理 Markdown 代码块标记 (```json ... ```)
                content = content.replace("```json", "").replace("```", "").strip()
                try:
                    keywords = json.loads(content)
                    if isinstance(keywords, list):
                        logger.info(f"生成关键词: {keywords}")
                        return keywords
                except json.JSONDecodeError:
                    logger.warning(f"AI 返回格式错误: {content}")
                    
            else:
                logger.error(f"DeepSeek API 错误 (Split Name): {response.status_code}")
                
        except Exception as e:
            logger.error(f"拆分公司名称异常: {e}")
            
        # Fallback: 简单的规则拆分
        short_name = company_name.replace("北京", "").replace("有限公司", "").replace("股份", "").replace("科技", "")
        return [short_name] if short_name else [company_name]

    def _extract_json_from_text(self, text):
        """
        从文本中尝试暴力提取 JSON 关键字段 (正则兜底)
        """
        data = {}
        try:
            # 1. Try to find valid_ids list
            valid_ids_match = re.search(r'"valid_ids"\s*:\s*\[([\d,\s]*)\]', text)
            if valid_ids_match:
                ids_str = valid_ids_match.group(1)
                data['valid_ids'] = [int(x) for x in ids_str.split(',') if x.strip().isdigit()]
            
            # 2. Try to find cnvd_candidates
            cnvd_match = re.search(r'"cnvd_candidates"\s*:\s*\[([\d,\s]*)\]', text)
            if cnvd_match:
                ids_str = cnvd_match.group(1)
                data['cnvd_candidates'] = [int(x) for x in ids_str.split(',') if x.strip().isdigit()]
            
            # If we found valid_ids, we consider it a success even if summary is missing
            if 'valid_ids' in data:
                # Try to extract summary roughly if possible, or just default
                summary_match = re.search(r'"summary"\s*:\s*"(.*?)"', text, re.DOTALL)
                if summary_match:
                    data['summary'] = summary_match.group(1)
                
                strategy_match = re.search(r'"cnvd_strategy"\s*:\s*"(.*?)"', text, re.DOTALL)
                if strategy_match:
                    data['cnvd_strategy'] = strategy_match.group(1)
                    
                return data
                
        except Exception as e:
            logger.debug(f"正则提取失败: {e}")
            
        return None

    def analyze_with_ai(self, company_name, assets):
        """
        调用 DeepSeek 分析资产 (全量模式 - 仅发送 Title)
        支持分批处理以避免 Token 超限
        返回: (clean_assets, cnvd_candidates, usage_dict, analysis_result)
        """
        # 0. Check Balance / Fallback to Local
        # 如果配置了强制使用本地，或者余额不足(TODO: 实现余额判断逻辑)，则切换
        # 这里简单起见，我们在 API 连续报错后自动切换，或者先尝试 API
        # 用户需求: "如果DeepSeek API没钱了...使用深度学习训练"
        
        # 我们可以先检查余额，如果余额 < 1元 (举例)，则直接用本地
        # 但 get_account_balance 返回的是字符串，解析可能不稳定。
        # 策略: 优先尝试 API，如果 API 返回 402 (Payment Required) 或连续错误，则转本地。
        # 但为了节省时间，也可以加个开关。
        
        # 本次实现：在 API 调用失败的 except 块中，尝试本地兜底。
        
        if self.force_local_model:
            logger.info("强制使用本地模型分析 (Offline Mode)...")
            return self.local_engine.predict_assets(assets)
        
        total_assets = len(assets)
        logger.info(f"正在使用 DeepSeek 分析 {company_name} (全量行数: {total_assets})...")
        
        # 1. 构造精简 Payload (仅 ID 和 Title)
        lean_data = []
        for i, asset in enumerate(assets):
            title = asset.get('title', 'N/A')
            if not title or pd.isna(title):
                title = "N/A"
            lean_data.append({'id': i, 'title': str(title).strip()})
            
        # 2. 分批处理配置
        BATCH_SIZE = 1000 # 保守设置，防止 6000+ 条导致 128k context 溢出
        
        all_valid_ids = []
        all_cnvd_ids = []
        total_usage = {'prompt_tokens': 0, 'completion_tokens': 0}
        combined_summaries = []
        combined_strategies = []
        
        # 3. 循环分批
        for batch_start in range(0, total_assets, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_assets)
            batch_data = lean_data[batch_start:batch_end]
            
            logger.info(f"  > 处理分批: {batch_start+1} - {batch_end} (共 {len(batch_data)} 条)...")
            
            asset_text = json.dumps(batch_data, ensure_ascii=False, indent=0)
            
            prompt = f"""
            你是一个 CNVD 漏洞挖掘专家。请分析以下归属于 "{company_name}" 的资产标题列表 (批次 {batch_start//BATCH_SIZE + 1})。
            
            资产列表 (ID: Title):
            {asset_text}
            
            请执行以下任务:
            1. **数据清洗**: 识别属于该公司的真实业务系统。必须剔除博彩、色情、无关导航页、明显的第三方误报站点。
            2. **CNVD 潜力评估**: 标记哪些系统最容易存在通用漏洞或弱口令（如 OA系统、VPN入口、CRM、ERP、SpringBoot、后台管理系统、老旧框架等），适合作为 CNVD 漏洞挖掘的目标。
            3. **资产梳理**: 总结本批次资产的业务类型。
            
            请以 JSON 格式返回，必须包含以下字段:
            - valid_ids (list[int]): 经清洗后保留的真实业务系统 ID 列表。
            - cnvd_candidates (list[int]): 建议重点测试 CNVD 的资产 ID 列表 (是 valid_ids 的子集)。
            - summary (str): 本批次资产梳理总结。
            - cnvd_strategy (str): 本批次漏洞挖掘策略建议。
            """
            
            messages = [{"role": "user", "content": prompt}]
            
            # Retry mechanism for each batch
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json={"model": "deepseek-chat", "messages": messages}, 
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result['choices'][0]['message']['content']
                        usage = result.get('usage', {'prompt_tokens': 0, 'completion_tokens': 0})
                        
                        # Accumulate Usage (only for successful or last attempt to avoid double counting if we could separate, 
                        # but actually if we retry, we spend tokens again. So we SHOULD count them if the API charged us.
                        # Assuming API charges for failed/bad-json responses too.)
                        total_usage['prompt_tokens'] += usage.get('prompt_tokens', 0)
                        total_usage['completion_tokens'] += usage.get('completion_tokens', 0)
                        
                        # Log (Full content)
                        logger.debug(f"[DeepSeek Response Batch] ({company_name}):\n{content}") 
                        
                        # Parse JSON
                        try:
                            json_str = content
                            if "```json" in content:
                                json_str = content.split("```json")[1].split("```")[0]
                            elif "```" in content:
                                 json_str = content.split("```")[1].split("```")[0]
                            
                            analysis_data = json.loads(json_str.strip())
                            
                            batch_valid_ids = analysis_data.get('valid_ids', [])
                            batch_cnvd_ids = analysis_data.get('cnvd_candidates', [])
                            
                            all_valid_ids.extend(batch_valid_ids)
                            all_cnvd_ids.extend(batch_cnvd_ids)
                            
                            if analysis_data.get('summary'):
                                combined_summaries.append(analysis_data.get('summary'))
                            if analysis_data.get('cnvd_strategy'):
                                combined_strategies.append(analysis_data.get('cnvd_strategy'))
                                
                            # Success! Break retry loop
                            break
                            
                        except json.JSONDecodeError:
                            # 尝试正则兜底提取
                            extracted_data = self._extract_json_from_text(content)
                            if extracted_data:
                                logger.warning(f"批次 {batch_start} JSON 解析失败，但正则提取成功 (尝试 {attempt+1}/{max_retries})")
                                batch_valid_ids = extracted_data.get('valid_ids', [])
                                batch_cnvd_ids = extracted_data.get('cnvd_candidates', [])
                                all_valid_ids.extend(batch_valid_ids)
                                all_cnvd_ids.extend(batch_cnvd_ids)
                                if extracted_data.get('summary'):
                                    combined_summaries.append(extracted_data.get('summary'))
                                if extracted_data.get('cnvd_strategy'):
                                    combined_strategies.append(extracted_data.get('cnvd_strategy'))
                                break # Success via regex extraction
                            
                            logger.warning(f"批次 {batch_start} JSON 解析失败 (尝试 {attempt+1}/{max_retries})")
                            if attempt == max_retries - 1:
                                logger.error(f"批次 {batch_start} 最终解析失败，跳过该批次数据")
                            else:
                                time.sleep(2) # Wait before retry
                                continue
                    else:
                        logger.error(f"DeepSeek API 错误 (Batch {batch_start}): {response.status_code}")
                        
                        # 402 Payment Required or 401 Unauthorized -> Switch to Local Model
                        if response.status_code in [402, 401] and self.use_local_model_fallback:
                            logger.warning("API 余额不足或未授权，切换至本地模型引擎...")
                            return self.local_engine.predict_assets(assets)
                            
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            continue
                        
                except Exception as e:
                    logger.error(f"AI 分析异常 (Batch {batch_start}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        # Final attempt failed -> Try Local Model as last resort
                        if self.use_local_model_fallback:
                            logger.warning("API 多次重试失败，切换至本地模型引擎...")
                            return self.local_engine.predict_assets(assets)
            
            # Rate limit between batches (outside retry loop)
            time.sleep(2)
            
        # 4. 聚合结果
        # Deduplicate IDs just in case
        all_valid_ids = sorted(list(set(all_valid_ids)))
        all_cnvd_ids = sorted(list(set(all_cnvd_ids)))
        
        # Aggregate Summary
        final_summary = "\n\n".join([f"**批次 {i+1}**: {s}" for i, s in enumerate(combined_summaries)])
        final_strategy = "\n\n".join([f"**批次 {i+1}**: {s}" for i, s in enumerate(combined_strategies)])
        
        final_analysis_data = {
            "valid_ids": all_valid_ids,
            "cnvd_candidates": all_cnvd_ids,
            "summary": final_summary,
            "cnvd_strategy": final_strategy
        }
        
        # 5. 提取资产对象
        clean_assets = [assets[i] for i in all_valid_ids if i < len(assets)]
        cnvd_assets = [assets[i] for i in all_cnvd_ids if i < len(assets)]
        
        logger.info(f"AI 清洗完成 (聚合): 原始 {total_assets} -> 有效 {len(clean_assets)} -> CNVD重点 {len(cnvd_assets)}")
        logger.info(f"Total Token Usage: {total_usage}")
        
        return clean_assets, cnvd_assets, total_usage, final_analysis_data

    def check_relevance_with_ai(self, company_name, assets):
        """
        验证资产是否与公司相关 (用于放宽查询后的验证)
        返回: (bool, reason)
        """
        logger.info(f"正在验证资产相关性 ({company_name})...")
        
        # 抽取样本 (最多 5 个)
        sample_assets = assets[:5]
        asset_text = json.dumps(sample_assets, ensure_ascii=False, indent=2)
        
        prompt = f"""
        请判断以下互联网资产是否属于公司 "{company_name}"。
        
        资产列表:
        {asset_text}
        
        背景信息: 我们通过放宽搜索条件找到了这些资产，需要确认它们是否是目标公司的资产，还是误报（例如其他同名公司或包含关键词的无关内容）。
        
        请分析：
        1. 网站标题/内容是否明确提及 "{company_name}" 或其已知品牌？
        2. 是否有明显的无关特征（如完全不同的行业、明显的个人博客、无关的门户网站等）？
        
        请仅返回 JSON 格式结果:
        {{
            "is_relevant": true/false,
            "confidence": 0-100,
            "reason": "简短理由"
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                # 使用 deepseek-chat 快速判断
                json={"model": "deepseek-chat", "messages": messages, "temperature": 0.1},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                content = content.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(content)
                    is_relevant = data.get('is_relevant', False)
                    reason = data.get('reason', 'No reason provided')
                    logger.info(f"AI 验证结果: {is_relevant} - {reason}")
                    return is_relevant, reason
                except json.JSONDecodeError:
                    logger.warning(f"AI 返回格式错误 (Relevance): {content}")
                    # 默认保守策略：如果无法解析，视为不相关，避免误报
                    return False, "AI 响应解析失败"
            else:
                logger.error(f"DeepSeek API 错误 (Relevance): {response.status_code}")
                return False, "API Error"
                
        except Exception as e:
            logger.error(f"AI 验证异常: {e}")
            return False, f"Exception: {e}"
