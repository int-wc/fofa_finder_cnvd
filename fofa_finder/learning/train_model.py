# -*- coding: utf-8 -*-
import pandas as pd
import joblib
import os
import html
import re
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

# Paths
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

def get_augmented_data():
    """
    Manually provide typical samples that might be missing or noisy in the dataset.
    This helps correct the model's bias (e.g., teaching it that 'nginx' is bad, 'VPN entry' is good).
    """
    data = []
    
    # 1. Negative Samples (Trash/Default Pages) - Label 0
    negatives = [
        "Welcome to nginx!",
        "Test Page for the Nginx HTTP Server on Fedora",
        "Apache Tomcat/8.5.55",
        "Apache Tomcat/9.0.0.M1",
        "IIS Windows Server",
        "Microsoft Internet Information Services 8",
        "404 Not Found",
        "403 Forbidden",
        "502 Bad Gateway",
        "Error 500: Internal Server Error",
        "Site under construction",
        "Under Construction",
        "Index of /",
        "phpinfo()",
        "Welcome to CentOS",
        "Test Page for Apache Installation",
        "极光VPN - 免费加速器",
        "快连VPN - 科学上网",
        "老王加速器",
        "VPN梯子推荐",
        "博彩导航",
        "澳门首家线上赌场",
    ]
    for t in negatives:
        data.append({"text": t, "label": 0})
        
    # 2. Positive Samples (Valid Systems) - Label 1
    positives = [
        "XX集团VPN远程接入系统",
        "XX科技内部VPN入口",
        "SSL VPN Login",
        "Pulse Secure",
        "Cisco AnyConnect",
        "Fortinet VPN",
        "XX市综合管理平台后台",
        "协同办公系统(OA)",
        "人力资源管理系统(HR)",
        "GitLab Community Edition",
        "Jenkins Dashboard",
        "Zabbix Monitoring",
        "Grafana",
        "Kibana",
        "RabbitMQ Management",
        "Nacos Console",
        "XX大学教务管理系统",
        "XX医院信息管理系统",
        "泛微e-cology",
        "致远A8+协同管理软件",
        "通达OA网络智能办公系统",
    ]
    for t in positives:
        data.append({"text": t, "label": 1})
        
    return pd.DataFrame(data)

def train():
    if not os.path.exists(DATASET_FILE):
        print("Error: Dataset file not found! Run prepare_data.py first.")
        return
        
    print("Loading dataset...")
    df = pd.read_csv(DATASET_FILE)
    
    # Drop NA
    df.dropna(inplace=True)
    
    print("Cleaning text (decoding HTML entities)...")
    df['text'] = df['text'].apply(clean_text)
    
    # Data Augmentation
    print("Applying data augmentation (adding manual benchmark cases)...")
    aug_df = get_augmented_data()
    # Repeat augmented data to give it more weight (e.g., 5 times)
    aug_df = pd.concat([aug_df] * 5, ignore_index=True)
    
    df = pd.concat([df, aug_df], ignore_index=True)
    
    # Remove duplicates
    df.drop_duplicates(subset=['text'], keep='last', inplace=True)
    
    X = df['text']
    y = df['label']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples...")
    
    # Build Pipeline: TF-IDF + Random Forest
    # TF-IDF: Character level n-grams works well for Chinese short text classification
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='char', ngram_range=(1, 3), max_features=10000)),
        ('clf', RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42))
    ])
    
    # Train
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    y_pred = pipeline.predict(X_test)
    print("\nModel Evaluation:")
    print(classification_report(y_test, y_pred))
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    
    # Save
    joblib.dump(pipeline, MODEL_FILE)
    print(f"\nModel saved to {MODEL_FILE}")
    print("Local engine is ready!")

if __name__ == "__main__":
    train()