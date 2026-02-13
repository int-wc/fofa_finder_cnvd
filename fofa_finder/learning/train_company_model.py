# -*- coding: utf-8 -*-
import pandas as pd
import joblib
import os
import re
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import logging
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

DATASET_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_dataset.csv")
MODEL_FILE = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_model.pkl")

from fofa_finder.modules.logger import setup_logger

logger = setup_logger("TrainModel")

def clean_company_name(name):
    if not isinstance(name, str):
        return ""
    # Remove common legal suffixes to focus on the core name/industry
    # e.g. "北京XX科技有限公司" -> "北京XX科技"
    # Actually, "科技" is a strong feature, we should keep it.
    # We might just remove specific noise if needed, but for now raw name is fine.
    return name.strip()

from sklearn.utils import resample

def train():
    if not os.path.exists(DATASET_FILE):
        logger.error("Error: Dataset file not found! Run extract_company_data.py first.")
        return
        
    logger.info("Loading dataset...")
    df = pd.read_csv(DATASET_FILE)
    
    # Drop NA
    df.dropna(subset=['company', 'label'], inplace=True)
    
    # Handle Imbalance via Upsampling
    df_majority = df[df.label==0]
    df_minority = df[df.label==1]
    
    logger.info(f"Original counts: 0 (Neg): {len(df_majority)}, 1 (Pos): {len(df_minority)}")
    
    # Upsample minority class
    df_minority_upsampled = resample(df_minority, 
                                     replace=True,     # sample with replacement
                                     n_samples=len(df_majority),    # to match majority class
                                     random_state=42) # reproducible results
                                     
    # Combine majority class with upsampled minority class
    df_upsampled = pd.concat([df_majority, df_minority_upsampled])
    
    logger.info(f"Upsampled counts: 0: {len(df_upsampled[df_upsampled.label==0])}, 1: {len(df_upsampled[df_upsampled.label==1])}")
    
    X = df_upsampled['company']
    y = df_upsampled['label']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples...")
    
    # Build Pipeline: TF-IDF + Random Forest
    # Analyzer='char' is good for Chinese names.
    # ngram_range=(2, 4) captures "科技", "网络", "信息技术", "房地产" etc.
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='char', ngram_range=(2, 4), max_features=5000)),
        ('clf', RandomForestClassifier(n_estimators=100, random_state=42))
    ])
    
    # Train
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    if len(X_test) > 0:
        y_pred = pipeline.predict(X_test)
        logger.info("\nModel Evaluation:")
        logger.info(classification_report(y_test, y_pred))
        logger.info(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    
    # Save
    joblib.dump(pipeline, MODEL_FILE)
    logger.info(f"\nModel saved to {MODEL_FILE}")
    logger.info("Company eligibility engine is ready!")

if __name__ == "__main__":
    train()
