# -*- coding: utf-8 -*-
import requests
import time
import random
import urllib.parse
from .logger import setup_logger
from ..config import Config

logger = setup_logger("FofaClient")

import base64

class FofaClient:
    def __init__(self):
        self.mode = Config.FOFA_MODE
        self.apis = [] # Always initialize apis list
        self.current_api_index = 0
        
        if self.mode == 'web':
            self.load_apis()
        elif self.mode == 'api':
            self.api_keys = Config.FOFA_API_KEYS
            self.current_key_index = 0
            self.api_url = Config.FOFA_API_URL
            if self.api_keys:
                logger.info(f"Using FOFA Official API Mode (Loaded {len(self.api_keys)} keys)")
            else:
                logger.error("No API Keys configured in Config.FOFA_API_KEYS")

    def load_apis(self):
        """
        解析 http_request.txt 等文件，构建 API 配置池
        """
        for file_path in Config.FOFA_REQUEST_FILES:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                parts = content.split('\n\n', 1)
                if len(parts) < 2:
                    # 尝试 \r\n
                    parts = content.split('\r\n\r\n', 1)
                
                if len(parts) < 2:
                    logger.warning(f"Failed to parse request file: {file_path} (Format error)")
                    continue
                    
                header_part = parts[0]
                body_part = parts[1].strip()
                
                lines = header_part.splitlines()
                if not lines:
                    continue
                    
                # Parse Request Line: POST /path HTTP/1.1
                req_line = lines[0].split()
                if len(req_line) < 2:
                    continue
                method = req_line[0]
                path = req_line[1]
                
                # Parse Headers
                headers = {}
                host = ""
                for line in lines[1:]:
                    if ':' in line:
                        key, val = line.split(':', 1)
                        key = key.strip()
                        val = val.strip()
                        headers[key] = val
                        if key.lower() == 'host':
                            host = val
                
                # Remove Content-Length (requests will calc it)
                if 'Content-Length' in headers:
                    del headers['Content-Length']

                # Remove Accept-Encoding (let requests handle it)
                if 'Accept-Encoding' in headers:
                    del headers['Accept-Encoding']

                
                # Construct URL
                scheme = "https" # Default to https as per origin header usually
                if 'Origin' in headers:
                    if headers['Origin'].startswith('http:'):
                        scheme = 'http'
                
                url = f"{scheme}://{host}{path}"
                
                self.apis.append({
                    'url': url,
                    'method': method,
                    'headers': headers,
                    'body_template': body_part
                })
                logger.info(f"Loaded API endpoint: {url}")
                
            except Exception as e:
                logger.error(f"Error loading request file {file_path}: {e}")

    def build_query(self, company_name, simple=False):
        """
        构建 FOFA 查询语句
        simple=True: 仅查询 body="公司名"，不带排除词 (用于 API 模式避免 820011 错误)
        """
        # 基础查询
        query = f'body="{company_name}"&&body="登录"'
        
        if simple:
            return query
            
        # 排除关键词 (Web 模式使用)
        if Config.EXCLUDED_KEYWORDS:
            exclusions = []
            for kw in Config.EXCLUDED_KEYWORDS:
                exclusions.append(f'body!="{kw}"')
            
            # 使用 && 连接
            exclusion_str = " && ".join(exclusions)
            query = f'{query} && {exclusion_str}'
            
        return query

    def parse_body_and_update(self, body_template, fofa_query):
        """
        解析 body 模板，替换 fofa_yf 参数
        body_template 类似: action=fofa_cx&fofa_yf=title="Beijing"&fofa_ts=100
        """
        # 简单的字符串替换可能不够健壮，解析为字典
        try:
            params = urllib.parse.parse_qs(body_template)
            # parse_qs 返回 {'key': ['val']}
            
            # 更新 fofa_yf
            # 注意：DeepSeek 分析显示用户原来的请求中 fofa_yf 是直接放在 body 里的
            # 我们这里构造一个新的 body 字典供 requests 使用，或者重建字符串
            
            # 为了最大程度模拟原始请求，我们尽量保持顺序（虽然 requests data=dict 不保证顺序）
            # 这里我们直接重建字符串比较安全
            
            # 将 query 进行 URL 编码
            # encoded_query = urllib.parse.quote(fofa_query) # requests 会自动编码 data 字典
            
            # 使用字典方式，让 requests 处理
            data = {}
            for k, v in params.items():
                data[k] = v[0] # 取第一个值
            
            data['fofa_yf'] = fofa_query
            
            # 另外注意 fofa_ts，保留原值或更新
            # User requested fofa_ts=10000
            data['fofa_ts'] = '10000'
                
            return data
        except Exception:
            # Fallback
            return {'action': 'fofa_cx', 'fofa_yf': fofa_query, 'fofa_ts': '10000'}

    def check_token_status(self):
        """
        检查 Token/API Key 是否有效 (自检)
        返回: (bool, message)
        """
        if self.mode == 'api':
            # API Mode Check
            if not self.api_keys:
                return False, "No API Keys configured"
            
            valid_count = 0
            info_url = "https://fofa.info/api/v1/info/my"
            
            for k in self.api_keys:
                try:
                    params = {'email': k['email'], 'key': k['key']}
                    resp = requests.get(info_url, params=params, timeout=10)
                    if resp.status_code == 200 and not resp.json().get('error'):
                        valid_count += 1
                except:
                    pass
            
            if valid_count > 0:
                return True, f"API Mode: {valid_count}/{len(self.api_keys)} keys valid"
            else:
                return False, "API Mode: All keys invalid"

        # Web Mode Check
        if not self.apis:
            return False, "No APIs loaded"
            
        # Try the first API
        api = self.apis[0]
        url = api['url']
        headers = api['headers']
        
        # Simple test query
        query = 'title="baidu"' 
        data = self.parse_body_and_update(api['body_template'], query)
        
        try:
            logger.info(f"正在自检 (Self-checking) 目标: 'Baidu' 接口: {url}...")
            response = requests.post(url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                try:
                    json_resp = response.json()
                    # Check for explicit errors in JSON (e.g. "not logged in")
                    if isinstance(json_resp, dict) and json_resp.get('error'):
                        return False, f"API Error: {json_resp.get('errmsg')}"
                        
                    # Also check specific text that indicates failure (optional, depends on response)
                    if "您未登录网站" in str(json_resp):
                         return False, "Cookie Invalid (Not Logged In)"
                         
                    return True, "Token valid"
                except:
                    return False, "Response not JSON"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Request Exception: {e}"

    def search_official(self, query):
        """
        使用 FOFA 官方 API 搜索 (支持多 Key 故障转移)
        """
        logger.info(f"正在搜索 (API): {query[:50]}... (查看完整日志获取语法)")
        logger.debug(f"完整 FOFA 语法: {query}")
        
        qbase64 = base64.b64encode(query.encode('utf-8')).decode('utf-8')
        
        if not self.api_keys:
            logger.error("No API Keys available.")
            return None, query

        # Loop through keys starting from current index
        attempts = 0
        total_keys = len(self.api_keys)
        
        while attempts < total_keys:
            current_key_info = self.api_keys[self.current_key_index]
            email = current_key_info['email']
            key = current_key_info['key']
            
            params = {
                'email': email,
                'key': key,
                'qbase64': qbase64,
                'size': Config.FOFA_SIZE,
                'fields': 'host,ip,port,title,protocol,country_name,region_name,city_name'
            }
            
            # Rate limiting sleep
            time.sleep(2)
            
            try:
                logger.info(f"正在请求 FOFA API ({email})...")
                response = requests.get(self.api_url, params=params, timeout=60)
                
                # Log full response in debug
                logger.debug(f"[API Request URL] {response.url}")
                logger.debug(f"[API Response] HTTP {response.status_code}\n{response.text}")
                
                if response.status_code == 200:
                    json_resp = response.json()
                    if json_resp.get('error'):
                        errmsg = json_resp.get('errmsg', '')
                        logger.warning(f"Key ({email}) Error: {errmsg}")
                        
                        # 429 Too Many Requests in body (unlikely for 200 OK but possible)
                        
                        # Check for critical query errors that are NOT key-related
                        # [820011] Content restricted
                        # [820000] Syntax error
                        if "820011" in str(errmsg) or "820000" in str(errmsg):
                            logger.error(f"FOFA API Rejected Query: {errmsg}. Skipping this query (No Failover).")
                            return {}, query # Return empty result to avoid Failover
                        
                        # Switch key for other errors (quota, account invalid)
                        self.current_key_index = (self.current_key_index + 1) % total_keys
                        attempts += 1
                        continue
                    else:
                        # Success
                        return json_resp, query
                elif response.status_code == 429:
                    logger.warning(f"FOFA API Rate Limit (429) with Key ({email}). Sleeping 5s...")
                    time.sleep(5)
                    # Retry once with same key? Or switch? Switch is better if one key is exhausted.
                    # But 429 usually means global IP limit or key limit. Let's switch.
                    self.current_key_index = (self.current_key_index + 1) % total_keys
                    attempts += 1
                    continue
                else:
                    logger.warning(f"FOFA API HTTP Error {response.status_code} with Key ({email})")
                    self.current_key_index = (self.current_key_index + 1) % total_keys
                    attempts += 1
                    continue
                    
            except Exception as e:
                logger.error(f"FOFA API Request Exception with Key ({email}): {e}")
                self.current_key_index = (self.current_key_index + 1) % total_keys
                attempts += 1
                continue
        
        logger.error("所有 API Key 均尝试失败。")
        return None, query

    def switch_to_web_mode(self):
        """
        切换到 Web 模式 (当 API Key 耗尽时)
        """
        logger.warning(">>> 正在切换到 Web 模式 (Switching to Web Mode) <<<")
        self.mode = 'web'
        if not self.apis:
            self.load_apis()
            
    def execute_query(self, query):
        """
        执行具体的查询请求
        返回: (json_resp, query_syntax)
        """
        if self.mode == 'api':
            result, q_syntax = self.search_official(query)
            if result is None:
                # API Mode Failed (All keys exhausted or error)
                # Failover to Web Mode
                self.switch_to_web_mode()
                # Retry with new mode
                return self.execute_query(query)
            return result, q_syntax
            
        # Web Mode Logic
        if not self.apis:
            logger.error("Web 模式未加载任何 API 配置")
            return None, query

        # 控制台只显示简短信息，完整语法记录到日志文件 (DEBUG级别)
        logger.info(f"正在搜索: {query[:50]}... (查看完整日志获取语法)")
        logger.debug(f"完整 FOFA 语法: {query}")
        
        # Rate Limiting
        sleep_time = random.uniform(Config.RATE_LIMIT_MIN, Config.RATE_LIMIT_MAX)
        logger.info(f"等待 {sleep_time:.1f} 秒...")
        time.sleep(sleep_time)
        
        # Retry loop for interfaces
        attempts = 0
        max_attempts = len(self.apis) * 2 # Allow some retries
        
        while attempts < max_attempts:
            api = self.apis[self.current_api_index]
            url = api['url']
            headers = api['headers']
            
            # Prepare Data
            data = self.parse_body_and_update(api['body_template'], query)
            
            try:
                logger.info(f"正在请求 {url}...")
                response = requests.post(url, headers=headers, data=data, timeout=60)
                
                # 记录原始响应包到文件日志
                logger.debug(f"[{url}] HTTP {response.status_code} Response: {response.text}")
                
                if response.status_code == 200:
                    try:
                        json_resp = response.json()
                        return json_resp, query
                    except Exception as e:
                        logger.warning(f"响应非 JSON 格式: {response.text[:100]}...")
                        pass
                else:
                    logger.warning(f"HTTP {response.status_code} 来自 {url}")
            
            except requests.RequestException as e:
                logger.error(f"请求失败: {e}")
            
            # Switch API
            self.current_api_index = (self.current_api_index + 1) % len(self.apis)
            attempts += 1
            time.sleep(2) # Short sleep before switching
            
        logger.error(f"所有 API 均请求失败: {query[:30]}...")
        return None, query

    def search(self, company_name):
        """
        执行搜索
        返回: (json_resp, query_syntax)
        """
        # 统一使用简化查询以避免 FOFA 限制 (820011/WAF)
        # 依赖 Analyzer.filter_junk_assets 进行本地清洗
        query = self.build_query(company_name, simple=True)
        return self.execute_query(query)
