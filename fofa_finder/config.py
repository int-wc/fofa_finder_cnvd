# -*- coding: utf-8 -*-
import os

class Config:
    # 基础路径
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    
    # 确保输出目录存在
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    # 输入文件 (请根据实际情况修改)
    # 推荐使用绝对路径，或将文件放在项目根目录下
    INPUT_FILE = "company_list.xlsx" 
    
    # FOFA 模式设置
    # 'web': 使用 http_request.txt 模拟网页请求 (已移除，建议使用 api 模式)
    # 'api': 使用 FOFA 官方 API (fofa.info)
    # 默认使用 api 模式
    FOFA_MODE = 'api' 
    
    # FOFA 官方 API 配置 (仅在 FOFA_MODE='api' 时生效)
    # 请在此处填入您的 FOFA 邮箱和 API Key
    FOFA_API_KEYS = [
        {"email": "YOUR_EMAIL_HERE", "key": "YOUR_FOFA_API_KEY_HERE"},
        # 支持多 Key 轮询，格式同上
    ]
    
    FOFA_API_URL = "https://fofa.info/api/v1/search/all"
    FOFA_SIZE = 10000 # 每次搜索数量
    
    # 业务范围筛选关键词 (必须包含其中之一)
    BUSINESS_SCOPE_KEYWORDS = [
        "计算机", "软件", "互联网", "网络", "网站", "系统集成", 
        "数据处理", "云计算", "人工智能", "大数据", "信息技术", "App", "平台"
    ]
    
    # DeepSeek API 配置
    # 请在此处填入您的 DeepSeek API Key
    DEEPSEEK_API_KEY = "YOUR_DEEPSEEK_API_KEY_HERE"
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    
    # 本地 AI 模式 (默认关闭，通过 --local-ai 开启)
    # 开启后将优先使用本地训练的模型进行过滤，节省 API 调用
    USE_LOCAL_AI = False
    
    # 阈值设置
    CAPITAL_THRESHOLD = 5000 * 10000  # 注册资本阈值 (5000万)
    FINGERPRINT_THRESHOLD = 10        # 相同指纹数量阈值
    
    # 速率限制 (秒)
    RATE_LIMIT_MIN = 2
    RATE_LIMIT_MAX = 5
    
    # 排除关键词 (博彩、体育、色情等)
    EXCLUDED_KEYWORDS = [
        "博彩", "赌博", "投注", "彩票", "casino", "betting", "lottery",
        "色情", "成人", "porn", "sex", "xx", "video", 
        "体育", "sports", "足球", "篮球", "球",
        "棋牌", "game", "娱乐城", "澳门", "威尼斯人",
        "小说", "novel", "电影", "movie"
    ]
    
    # 日志格式
    LOG_FORMAT = '[%(asctime)s] %(levelname)-8s | %(name)-12s | %(message)s'
    LOG_FILE = os.path.join(OUTPUT_DIR, "fofa_finder.log")

