# -*- coding: utf-8 -*-
import pandas as pd
import joblib
import os
import sys
import logging
import re
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score
from sklearn.utils import resample
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

# Configure Logger
logger = logging.getLogger("TrainCNVD")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('│  %(asctime)s  │  INFO      │  TrainCNVD     │ %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "cnvd_dataset.csv")
MODEL_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "cnvd_model.pkl")

def clean_title(title):
    if not isinstance(title, str):
        return ""
    # Basic cleanup
    return title.strip()

def train():
    logger.info("=== 开始训练 CNVD 重点资产识别模型 ===")
    
    if not os.path.exists(DATASET_FILE):
        logger.error(f"Dataset not found: {DATASET_FILE}")
        return
        
    df = pd.read_csv(DATASET_FILE)
    df.dropna(subset=['title', 'label'], inplace=True)
    
    # Check data distribution
    df_neg = df[df.label==0]
    df_pos = df[df.label==1]
    
    logger.info(f"Dataset Size: {len(df)}")
    logger.info(f"Negatives (0): {len(df_neg)}")
    logger.info(f"Positives (1): {len(df_pos)}")
    
    if len(df_pos) < 5:
        logger.warning("正样本太少 (<5)，无法训练有效模型。建议使用规则匹配代替。")
        return

    # Upsample minority (Positives)
    if len(df_pos) < len(df_neg):
        logger.info("Upsampling positive class...")
        df_pos_upsampled = resample(df_pos, 
                                    replace=True,
                                    n_samples=len(df_neg),
                                    random_state=42)
        df_upsampled = pd.concat([df_neg, df_pos_upsampled])
    else:
        df_upsampled = df
        
    X = df_upsampled['title']
    y = df_upsampled['label']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples...")
    
    # Pipeline
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='char', ngram_range=(2, 5), max_features=5000)),
        ('clf', RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced'))
    ])
    
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    if len(X_test) > 0:
        y_pred = pipeline.predict(X_test)
        logger.info("\nModel Evaluation:")
        logger.info(classification_report(y_test, y_pred))
        logger.info(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        
    # Save
    joblib.dump(pipeline, MODEL_FILE)
    logger.info(f"Model saved to {MODEL_FILE}")

if __name__ == "__main__":
    train()
