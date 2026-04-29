import re
from typing import Optional

def extract_age_months(q: str):
    q = q.lower()
    m = re.search(r'(\d+)\s*(month|months|mo)\b', q)
    if m: return int(m.group(1))
    y = re.search(r'(\d+)\s*(year|years|yr)\b', q)
    if y: return int(y.group(1)) * 12
    return None

def safe(exp, adv):
    return {
        "recommendation": "SAFE",
        "confidence": 0.85,
        "reasoning": "Rule-based safety check passed.",
        "user_explanation": exp,
        "advice": adv,
        "safety_flags": [],
        "reasoning_trace": ["Rule engine → safe"]
    }

def unsafe(flag, exp, adv):
    return {
        "recommendation": "NOT_SUITABLE",
        "confidence": 1.0,
        "reasoning": "Rule-based safety override.",
        "user_explanation": exp,
        "advice": adv,
        "safety_flags": [flag],
        "reasoning_trace": ["Rule engine → unsafe override"]
    }

def uncertain(exp, adv):
    return {
        "recommendation": "UNCERTAIN",
        "confidence": 0.5,
        "reasoning": "Insufficient data.",
        "user_explanation": exp,
        "advice": adv,
        "safety_flags": ["insufficient_data"],
        "reasoning_trace": ["Rule engine → uncertain"]
    }

def rule_based_engine(query: str):
    q = query.lower()
    age_m = extract_age_months(q)

    # 🚨 dangerous / nonsense
    if any(w in q for w in ["jump", "height", "fire", "poison", "knife"]):
        return unsafe("dangerous_action",
                      "This action is extremely unsafe for a child.",
                      "Do not attempt this under any circumstances.")

    # choking risk (stricter for <36 months)
    if "choking" in q or "small parts" in q or "marble" in q:
        if age_m is None or age_m < 36:
            return unsafe("choking_hazard",
                          "Small parts can be swallowed and cause choking.",
                          "Avoid items with small detachable parts for children under 3 years.")

    # food guidance (very basic)
    if any(w in q for w in ["feed", "eat", "food", "fruit", "pomegranate"]):
        if age_m is not None and age_m < 6:
            return unsafe("age_inappropriate",
                          "Solid foods are not recommended before about 6 months.",
                          "Consult your pediatrician before introducing new foods.")

    # generic safe products
    if any(w in q for w in ["soap", "stroller", "diaper", "toy", "car seat"]):
        return safe("This product type is generally safe when used as directed.",
                    "Use as instructed and supervise your child.")

    # fallback
    return uncertain("We don’t have enough information to confirm safety.",
                     "Verify with the manufacturer or a pediatrician.")

def run_advisor(query: str, child_age_months: Optional[int] = None):
    """Compatibility entry point used by the Streamlit app."""
    return rule_based_engine(query)

def get_recommendation(query: str, child_age_months: Optional[int] = None):
    """Backward-compatible alias for callers that expect a simple helper."""
    return run_advisor(query, child_age_months=child_age_months)

class ProductAdvisor:
    """Backward-compatible wrapper for older tests and scripts."""
    def __init__(self):
        pass

    def query(self, user_query: str):
        return run_advisor(user_query)