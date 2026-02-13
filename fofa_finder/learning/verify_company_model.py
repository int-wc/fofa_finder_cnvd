# -*- coding: utf-8 -*-
import joblib
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_model.pkl")

def verify():
    print("=== 验证本地公司资质模型 ===")
    
    if not os.path.exists(MODEL_FILE):
        print("模型文件未找到！")
        return
        
    try:
        model = joblib.load(MODEL_FILE)
        print("模型加载成功！")
    except Exception as e:
        print(f"模型加载失败: {e}")
        return
        
    # Test Cases
    test_cases = [
        "北京腾讯科技有限公司", # Should be 1
        "深圳市大疆创新科技有限公司", # Should be 1
        "上海xx美容美发有限公司", # Should be 0
        "成都好吃餐饮管理有限公司", # Should be 0
        "杭州阿里巴巴网络技术有限公司", # Should be 1
        "XX市公共交通集团有限公司", # Should be 0 (Traditional)
        "北京百度网讯科技有限公司", # Should be 1
        "XX房地产开发有限公司", # Should be 0
    ]
    
    print("\n基准测试:")
    print("-" * 50)
    print(f"{'公司名称':<30} | {'预测结果':<10}")
    print("-" * 50)
    
    for company in test_cases:
        pred = model.predict([company])[0]
        # proba = model.predict_proba([company])[0]
        label = "通过 (1)" if pred == 1 else "拒绝 (0)"
        print(f"{company:<30} | {label:<10}")
        
    print("-" * 50)

if __name__ == "__main__":
    verify()
