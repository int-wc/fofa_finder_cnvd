# -*- coding: utf-8 -*-
import pandas as pd
import joblib
import os
import sys
import html
import re
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import numpy as np

# 设置路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "dataset.csv")
MODEL_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "local_model.pkl")

def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Decode HTML entities (e.g., &#20013; -> 中)
    text = html.unescape(text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def verify():
    print("=== 开始本地模型严谨验证流程 ===")
    
    # 1. 检查模型文件
    if not os.path.exists(MODEL_FILE):
        print(f"错误: 模型文件未找到: {MODEL_FILE}")
        return

    print(f"[1/3] 加载模型: {MODEL_FILE}")
    try:
        pipeline = joblib.load(MODEL_FILE)
        print("模型加载成功！")
    except Exception as e:
        print(f"模型加载失败: {e}")
        return

    # 2. 人工基准测试 (Benchmark)
    print("\n[2/3] 执行人工基准用例测试 (黑盒测试)")
    print("说明: 模拟真实场景下的典型标题，验证模型直觉。")
    print("-" * 60)
    print(f"{'测试文本':<40} | {'预测结果':<10} | {'置信度':<10}")
    print("-" * 60)

    test_cases = [
        # 应该保留 (Label 1)
        ("XX市综合管理平台后台", 1),
        ("某某科技VPN入口", 1),
        ("GitLab Community Edition", 1),
        ("Jenkins Dashboard", 1),
        ("泛微协同办公平台", 1),
        ("H3C 路由器登录界面", 1),
        ("XX公司内部财务系统", 1),
        
        # 应该丢弃 (Label 0)
        ("404 Not Found", 0),
        ("Welcome to nginx!", 0),
        ("Apache Tomcat/8.5.55", 0),
        ("IIS Windows Server", 0),
        ("Error 500: Internal Server Error", 0),
        ("Test Page for the Nginx HTTP Server", 0),
        ("Site under construction", 0),
    ]

    correct_count = 0
    for text, expected in test_cases:
        prediction = pipeline.predict([text])[0]
        proba = pipeline.predict_proba([text])[0]
        confidence = proba[prediction]
        
        status = "✅ PASS" if prediction == expected else "❌ FAIL"
        if prediction == expected:
            correct_count += 1
            
        pred_str = "保留 (1)" if prediction == 1 else "丢弃 (0)"
        print(f"{text[:38]:<40} | {pred_str:<10} | {confidence:.2f}  {status}")

    print("-" * 60)
    print(f"基准测试通过率: {correct_count}/{len(test_cases)} ({correct_count/len(test_cases)*100:.2f}%)")

    # 3. 数据集统计评估
    print("\n[3/3] 数据集统计评估 (使用新随机种子划分验证集)")
    if os.path.exists(DATASET_FILE):
        df = pd.read_csv(DATASET_FILE)
        df.dropna(inplace=True)
        
        # 必须与训练时保持一致的数据预处理
        print("正在对验证集数据进行清洗 (解码 HTML 实体)...")
        df['text'] = df['text'].apply(clean_text)
        
        X = df['text']
        y = df['label']

        # 使用不同的随机种子 (random_state=2024) 划分测试集，以测试泛化能力
        # 注意：如果数据量太小，这可能与训练集重叠较多
        X_train_v, X_test_v, y_train_v, y_test_v = train_test_split(X, y, test_size=0.3, random_state=2024)
        
        print(f"总样本数: {len(df)}")
        print(f"验证集大小: {len(X_test_v)} (30%)")
        
        y_pred_v = pipeline.predict(X_test_v)
        
        acc = accuracy_score(y_test_v, y_pred_v)
        print(f"\n验证集准确率 (Accuracy): {acc:.4f}")
        
        print("\n详细分类报告:")
        print(classification_report(y_test_v, y_pred_v, target_names=['丢弃(0)', '保留(1)']))
        
        print("\n混淆矩阵:")
        cm = confusion_matrix(y_test_v, y_pred_v)
        print(f"真阴性 (TN - 正确丢弃): {cm[0][0]}")
        print(f"假阳性 (FP - 错误保留): {cm[0][1]}")
        print(f"假阴性 (FN - 错误丢弃): {cm[1][0]}")
        print(f"真阳性 (TP - 正确保留): {cm[1][1]}")
        
    else:
        print("警告: 未找到 dataset.csv，无法进行大规模统计评估。")

    print("\n=== 验证结束 ===")

if __name__ == "__main__":
    verify()
