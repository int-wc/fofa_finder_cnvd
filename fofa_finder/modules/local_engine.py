# -*- coding: utf-8 -*-
import joblib
import os
import pandas as pd
from .logger import setup_logger

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

logger = setup_logger("LocalEngine")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BASE_DIR, "fofa_finder", "learning", "local_model.pkl")
COMPANY_MODEL_PATH = os.path.join(BASE_DIR, "fofa_finder", "learning", "company_model.pkl")
CNVD_MODEL_PATH = os.path.join(BASE_DIR, "fofa_finder", "learning", "cnvd_model.pkl")

class LocalEngine:
    def __init__(self):
        self.model = None
        self.company_model = None
        self.cnvd_model = None
        self.load_model()
        self.load_company_model()
        self.load_cnvd_model()

    def load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                logger.info(f"本地 AI 模型 (资产) 已加载: {MODEL_PATH}")
            except Exception as e:
                logger.error(f"加载本地资产模型失败: {e}")
        else:
            logger.warning("未找到本地资产模型文件，请先运行 learning/train_model.py")

    def load_company_model(self):
        if os.path.exists(COMPANY_MODEL_PATH):
            try:
                self.company_model = joblib.load(COMPANY_MODEL_PATH)
                logger.info(f"本地 AI 模型 (公司资质) 已加载: {COMPANY_MODEL_PATH}")
            except Exception as e:
                logger.error(f"加载本地公司模型失败: {e}")
        else:
            logger.warning("未找到本地公司模型文件，请先运行 learning/train_company_model.py")

    def load_cnvd_model(self):
        if os.path.exists(CNVD_MODEL_PATH):
            try:
                self.cnvd_model = joblib.load(CNVD_MODEL_PATH)
                logger.info(f"本地 AI 模型 (CNVD) 已加载: {CNVD_MODEL_PATH}")
            except Exception as e:
                logger.error(f"加载本地 CNVD 模型失败: {e}")
        else:
            logger.warning("未找到本地 CNVD 模型文件，请先运行 learning/train_cnvd_model.py")

    def predict_company_eligibility(self, company_name):
        """
        使用本地模型预测公司资质
        返回: (eligible: bool, reason: str, usage: dict)
        """
        if not self.company_model:
            # 如果没有模型，默认通过（Fail-open），以免误杀
            logger.warning("本地公司模型未加载，默认判定为通过")
            return True, "本地模型未加载 (Default Pass)", {}
            
        try:
            # Predict
            # 1 = Eligible, 0 = Ineligible
            # Input needs to be iterable
            prediction = self.company_model.predict([company_name])[0]
            
            # Try to get probability if possible
            confidence = "N/A"
            if hasattr(self.company_model, "predict_proba"):
                probs = self.company_model.predict_proba([company_name])[0]
                confidence = f"{probs[prediction]:.2f}"
            
            is_eligible = bool(prediction == 1)
            reason = f"[本地模型] 判定{'通过' if is_eligible else '拒绝'} (置信度: {confidence})"
            
            logger.info(f"本地公司资质推理: {company_name} -> {is_eligible}")
            return is_eligible, reason, {'local_mode': True}
            
        except Exception as e:
            logger.error(f"本地公司推理异常: {e}")
            return True, f"推理出错: {e} (Default Pass)", {}

    def predict_assets(self, assets):
        """
        使用本地模型预测资产有效性
        返回: (clean_assets, cnvd_assets, usage_dict, analysis_data)
        """
        if not self.model:
            logger.error("本地模型未加载，无法执行预测")
            return [], [], {}, {"summary": "本地模型未加载", "cnvd_strategy": "无"}
            
        logger.info("正在使用本地 AI 引擎进行推理...")
        
        # Prepare Data
        titles = [str(a.get('title', '')) for a in assets]
        
        try:
            # Predict
            # 1 = Valid, 0 = Invalid
            predictions = self.model.predict(titles)
            # probabilities = self.model.predict_proba(titles) # If we want confidence score
            
            clean_assets = []
            cnvd_assets = [] # Local model currently only does binary classification (Valid/Invalid)
            
            valid_count = 0
            cnvd_count = 0
            
            for i, pred in enumerate(predictions):
                if pred == 1:
                    asset = assets[i]
                    clean_assets.append(asset)
                    
                    # Stage 2: CNVD Importance Check
                    is_cnvd_candidate = False
                    if self.cnvd_model:
                        try:
                            # Use CNVD model
                            title = str(asset.get('title', '')).strip()
                            cnvd_pred = self.cnvd_model.predict([title])[0]
                            if cnvd_pred == 1:
                                is_cnvd_candidate = True
                        except Exception:
                            # Fallback to rule-based if model fails on specific input
                            pass
                    
                    # If model not available or failed, could use rule-based fallback
                    # For now, if model exists, we trust it.
                    
                    if is_cnvd_candidate:
                        cnvd_assets.append(asset)
                        cnvd_count += 1
                        
                    valid_count += 1
            
            usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'local_mode': True}
            
            analysis_data = {
                "valid_ids": [i for i, p in enumerate(predictions) if p == 1],
                "cnvd_candidates": [i for i, asset in enumerate(assets) if asset in cnvd_assets],
                "summary": f"[本地模型分析] 共扫描 {len(assets)} 个资产，识别出 {valid_count} 个有效业务系统，其中 {cnvd_count} 个为 CNVD 重点资产。",
                "cnvd_strategy": "当前处于离线/省钱模式，仅提供基础清洗，建议人工复核。"
            }
            
            logger.info(f"本地推理完成: 原始 {len(assets)} -> 有效 {len(clean_assets)} -> CNVD重点 {len(cnvd_assets)}")
            return clean_assets, cnvd_assets, usage, analysis_data
            
        except Exception as e:
            logger.error(f"本地推理异常: {e}")
            return [], [], {}, {}