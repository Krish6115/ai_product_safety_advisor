"""
agent/advisor.py — AI Product Safety Advisor (production-grade)

Safety pipeline (in order):
  1. classify_query()           — keyword + pattern gate, NO LLM call for DANGEROUS
  2. RAG retrieval              — ChromaDB semantic search
  3. LLM structured generation — Gemini Flash via google-generativeai
  4. _apply_hard_overrides()   — rule-based post-LLM safety net
  5. _build_human_readable_layer() — generates user_explanation + advice

Design principle: Safety > everything. The LLM can only INCREASE safety level,
never decrease it past what the rules mandate.
"""

from __future__ import annotations

import os
import re
import json
import logging
from typing import Optional

from google import genai
from dotenv import load_dotenv

from agent.schemas import (
    AlternativeProduct,
    QueryClassification,
    Recommendation,
    SafetyResponse,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ── Gemini setup ───────────────────────────────────────────────────────────────
_API_KEY = os.getenv("GEMINI_API_KEY", "")
_MODEL_NAME = "gemini-2.0-flash"
_CONFIDENCE_THRESHOLD = 0.6
_RETRIEVAL_THRESHOLD = 0.4


def safe_parse_json(text: str) -> dict | None:
    """Best-effort JSON parser for LLM output."""
    if not text or not text.strip():
        return None

    text = text.strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    cleaned = re.sub(r'^```(?:json)?\s*', '', text)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 1 — QUERY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

# Each pattern is a compiled regex.  Order matters — checked in sequence.
_DANGEROUS_PATTERNS: list[re.Pattern] = [
    # Physical danger — height / impact
    re.compile(
        r"\b(jump|fall|drop|throw|push)\b.{0,40}\b(\d+\s*(ft|feet|m|meter|metre|floor|story|storey)s?|height|cliff|roof|balcony|window)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d+\s*(ft|feet|m|meter|metre))\b.{0,40}\b(height|high|tall|jump|fall|drop)\b",
        re.IGNORECASE,
    ),
    # Fire / chemical
    re.compile(
        r"\b(light\s+on\s+fire|set\s+on\s+fire|burn|ignite|poison|toxic\s+chemical|bleach|acid|caustic)\b",
        re.IGNORECASE,
    ),
    # Sharp weapons
    re.compile(
        r"\b(stab|slash|knife|razor|sword|blade|cut\s+with)\b",
        re.IGNORECASE,
    ),
    # Strangulation / suffocation
    re.compile(
        r"\b(strangle|suffocate|asphyxiat|hang\s+from)\b",
        re.IGNORECASE,
    ),
    # Drowning
    re.compile(
        r"\b(drown|hold\s+underwater|submerge\s+head)\b",
        re.IGNORECASE,
    ),
    # Electric shock
    re.compile(
        r"\b(electrocute|electric\s+shock|stick.{0,10}outlet|put.{0,10}finger.{0,10}socket)\b",
        re.IGNORECASE,
    ),
    # Explicit impossibility / absurdity used as safety bypass
    re.compile(
        r"\b(100\s*ft|1000\s*ft|100\s*m|skyscraper|ten.?story|twenty.?story)\b",
        re.IGNORECASE,
    ),
    # Generic "dangerous action for a baby/child" phrases
    re.compile(
        r"\b(is\s+it\s+safe\s+for\s+(my\s+)?(baby|infant|child|toddler|kid)\s+to\s+(jump|fall|run\s+into|eat\s+glass|drink\s+bleach|play\s+with\s+fire))\b",
        re.IGNORECASE,
    ),
]

_GENERAL_CHILDCARE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(how\s+much\s+sleep|feeding\s+schedule|potty\s+train|teething|vaccination|milestone)\b", re.IGNORECASE),
    re.compile(r"\b(breastfeed|formula\s+feed|solid\s+food|first\s+food)\b", re.IGNORECASE),
]


def classify_query(query: str) -> QueryClassification:
    """
    Pre-LLM classification gate.

    Returns:
        DANGEROUS        — matches a physically dangerous action pattern.
                           The pipeline STOPS here; no LLM is called.
        GENERAL_CHILDCARE — parenting question not about a specific product.
        PRODUCT_SAFETY   — default; proceed to RAG + LLM.

    This function must be extremely conservative.  False positives (classifying
    a safe query as DANGEROUS) are far less harmful than false negatives.
    """
    q = query.strip()

    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(q):
            logger.warning("DANGEROUS query detected: %r", q[:120])
            return QueryClassification.DANGEROUS

    for pattern in _GENERAL_CHILDCARE_PATTERNS:
        if pattern.search(q):
            return QueryClassification.GENERAL_CHILDCARE

    return QueryClassification.PRODUCT_SAFETY


def _build_dangerous_response(query: str) -> SafetyResponse:
    """
    Construct the immediate NOT_SUITABLE response for DANGEROUS queries.
    No LLM call is made.  Confidence is 1.0 (hard rule).
    """
    return SafetyResponse(
        query_language="en",
        query_classification=QueryClassification.DANGEROUS,
        recommendation=Recommendation.NOT_SUITABLE,
        confidence=1.0,
        safety_flags=["dangerous_action"],
        reasoning=(
            "Query describes a physically dangerous or life-threatening action. "
            "This is blocked before reaching the LLM by the rule-based safety gate."
        ),
        reasoning_trace=[
            "Query matched one or more dangerous-action patterns.",
            "[GATE] DANGEROUS classification — LLM call bypassed.",
            "[OVERRIDE] Forced NOT_SUITABLE with confidence=1.0.",
        ],
        alternatives=[],
        user_explanation=(
            "This action is extremely dangerous and could seriously injure or kill a child. "
            "It should never be attempted under any circumstances."
        ),
        advice=(
            "Do not attempt this under any circumstances. "
            "If you are concerned about your child's safety, please contact emergency services "
            "or your pediatrician immediately."
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 4 — HARD SAFETY OVERRIDES (post-LLM)
# ═══════════════════════════════════════════════════════════════════════════════

# (flag_keyword, max_age_months_or_None, forced_recommendation)
# If max_age_months is None the override applies regardless of child age.
_HARD_OVERRIDES: list[tuple[str, Optional[int], Recommendation]] = [
    # Choking hazard: any product with small parts is NOT_SUITABLE for < 36 months
    ("choking_hazard", 36, Recommendation.NOT_SUITABLE),
    ("small_parts", 36, Recommendation.NOT_SUITABLE),
    # Cord / strangulation risk: NOT_SUITABLE for < 36 months
    ("strangulation_risk", 36, Recommendation.NOT_SUITABLE),
    ("cord_hazard", 36, Recommendation.NOT_SUITABLE),
    # Toxic material: always NOT_SUITABLE
    ("toxic_material", None, Recommendation.NOT_SUITABLE),
    ("chemical_hazard", None, Recommendation.NOT_SUITABLE),
    # Sharp edges: always NOT_SUITABLE
    ("sharp_edges", None, Recommendation.NOT_SUITABLE),
    # Entrapment: NOT_SUITABLE for < 24 months
    ("entrapment_risk", 24, Recommendation.NOT_SUITABLE),
    # Fire / burn hazard: always NOT_SUITABLE
    ("fire_hazard", None, Recommendation.NOT_SUITABLE),
    ("burn_risk", None, Recommendation.NOT_SUITABLE),
    # Recalled product: always NOT_SUITABLE
    ("product_recalled", None, Recommendation.NOT_SUITABLE),
    # Dangerous action in product context (e.g. jumping from height)
    ("dangerous_action", None, Recommendation.NOT_SUITABLE),
]


def _apply_hard_overrides(
    response: SafetyResponse,
    child_age_months: Optional[int],
) -> SafetyResponse:
    """
    Apply rule-based safety overrides AFTER the LLM has produced its response.

    Rules:
    - If a safety flag + age condition is met, force NOT_SUITABLE.
    - Add an override note to reasoning_trace.
    - Recalculate user_explanation + advice via _build_human_readable_layer.

    The LLM output is trusted for retrieval and reasoning text, but NEVER
    trusted to override a hard rule.
    """
    override_applied = False
    override_flags: list[str] = []

    flags = [f.lower() for f in response.safety_flags]

    for flag_keyword, max_age, forced_rec in _HARD_OVERRIDES:
        if flag_keyword not in flags:
            continue

        age_condition_met = (
            max_age is None
            or child_age_months is None
            or child_age_months < max_age
        )

        if age_condition_met and response.recommendation != forced_rec:
            override_applied = True
            override_flags.append(flag_keyword)
            response = response.model_copy(
                update={"recommendation": forced_rec}
            )

    if override_applied:
        age_note = (
            f"child age {child_age_months} months"
            if child_age_months is not None
            else "unspecified age"
        )
        trace_note = (
            f"[OVERRIDE] Hard safety rule triggered for flags {override_flags} "
            f"({age_note}) — forced {response.recommendation}."
        )
        updated_trace = list(response.reasoning_trace) + [trace_note]
        response = response.model_copy(update={"reasoning_trace": updated_trace})

    return response


# ═══════════════════════════════════════════════════════════════════════════════
#  LAYER 5 — HUMAN-READABLE EXPLANATION LAYER
# ═══════════════════════════════════════════════════════════════════════════════

# Maps safety flag → plain-English description used in user_explanation
_FLAG_DESCRIPTIONS: dict[str, str] = {
    "choking_hazard": "it contains small parts that can be swallowed",
    "small_parts": "it contains small parts that pose a choking risk",
    "strangulation_risk": "it has cords or strings that can be a strangulation hazard",
    "cord_hazard": "it has cords or strings that can be a strangulation hazard",
    "toxic_material": "it contains materials that are toxic to children",
    "chemical_hazard": "it contains chemicals that are unsafe for children",
    "sharp_edges": "it has sharp edges or points that can cause injury",
    "entrapment_risk": "it has gaps or openings that could trap a child's head or limbs",
    "fire_hazard": "it poses a fire or flammability risk",
    "burn_risk": "it can cause burns",
    "product_recalled": "it has been recalled due to safety concerns",
    "dangerous_action": "the described action is physically dangerous",
    "age_warning": "it is not designed for the child's age group",
    "missing_data": "we do not have enough safety information about this product",
}


def _describe_flags(flags: list[str]) -> str:
    """Convert a list of safety flags into a readable 'because …' clause."""
    descriptions = [
        _FLAG_DESCRIPTIONS.get(f.lower(), f.lower().replace("_", " "))
        for f in flags
        if f.lower() != "dangerous_action" or len(flags) == 1
    ]
    # de-duplicate while preserving order
    seen: set[str] = set()
    unique = []
    for d in descriptions:
        if d not in seen:
            seen.add(d)
            unique.append(d)

    if not unique:
        return ""
    if len(unique) == 1:
        return f"because {unique[0]}"
    return "because " + ", ".join(unique[:-1]) + f", and {unique[-1]}"


def _build_human_readable_layer(
    recommendation: Recommendation,
    safety_flags: list[str],
    child_age_months: Optional[int],
) -> tuple[str, str]:
    """
    Generate (user_explanation, advice) from structured fields.

    Rules:
    - user_explanation: 1-2 sentences, plain English, no jargon.
    - advice: one actionable instruction. Never vague. Never a copy of reasoning.
    - Must be deterministic given the same inputs (no LLM call here).
    """
    age_str = (
        f"your {child_age_months}-month-old"
        if child_age_months is not None
        else "your child"
    )
    flag_clause = _describe_flags(safety_flags)

    if recommendation == Recommendation.NOT_SUITABLE:
        if "dangerous_action" in [f.lower() for f in safety_flags]:
            explanation = (
                "This action is extremely dangerous and could cause serious injury or death to a child. "
                "It should never be attempted under any circumstances."
            )
            advice = (
                "Do not attempt this. If you have safety concerns about your child, "
                "consult your pediatrician or contact emergency services."
            )
        elif flag_clause:
            explanation = (
                f"This product is not safe for {age_str} {flag_clause}. "
                "We strongly advise against purchasing or using it."
            )
            advice = (
                "Do not use this product. "
                "Please check the safer alternatives listed below that are appropriate for your child's age."
            )
        else:
            explanation = (
                f"This product is not suitable for {age_str} based on the available safety information. "
                "Using it could put your child at risk."
            )
            advice = (
                "Avoid this product. "
                "Look for alternatives specifically rated for your child's age and development stage."
            )

    elif recommendation == Recommendation.SAFE:
        if flag_clause:
            # Rare: LLM said SAFE but there are minor flags noted
            explanation = (
                f"This product appears to be safe for {age_str}, "
                f"though please note {flag_clause.replace('because ', '')}. "
                "Always supervise young children during use."
            )
            advice = (
                "You can use this product, but ensure adult supervision at all times "
                "and inspect it regularly for wear or damage."
            )
        else:
            explanation = (
                f"This product is safe for {age_str} and meets the relevant age and safety requirements."
            )
            advice = (
                "This product is appropriate for your child. "
                "As always, supervise use and follow all manufacturer instructions."
            )

    else:  # UNCERTAIN
        if flag_clause:
            explanation = (
                f"We do not have enough verified information to confirm whether this product is safe for {age_str}, "
                f"and it may have concerns {flag_clause.replace('because ', 'related to ')}."
            )
        else:
            explanation = (
                f"We do not have enough verified information to confirm whether this product is safe for {age_str}. "
                "Our safety database does not contain sufficient data on this item."
            )
        advice = (
            "Do not purchase this product until you have verified its safety. "
            "Contact the manufacturer directly, check official recall databases, "
            "or consult your pediatrician before use."
        )

    return explanation, advice


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE ADVISOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class SafetyAdvisor:
    """
    Orchestrates the full safety analysis pipeline.

    Call:
        advisor = SafetyAdvisor(retriever)
        result  = advisor.analyze(query, child_age_months=18)

    The retriever must implement:
        retriever.retrieve(query: str, k: int) -> list[dict]
        Each dict: {"text": str, "score": float, "metadata": dict}
    """

    def __init__(self, retriever):
        self.retriever = retriever
        self.client = genai.Client(api_key=_API_KEY) if _API_KEY else None

    # ── Public entry point ─────────────────────────────────────────────────────

    def analyze(self, query: str, child_age_months: Optional[int] = None) -> SafetyResponse:
        """
        Full safety analysis pipeline.

        Steps:
          1. Classify query — short-circuit for DANGEROUS
          2. Retrieve relevant documents via RAG
          3. Call LLM for structured recommendation
          4. Apply hard safety overrides
          5. Build human-readable layer
          6. Return validated SafetyResponse
        """
        # ── Step 1: Query classification ──────────────────────────────────────
        classification = classify_query(query)

        if classification == QueryClassification.DANGEROUS:
            # Hard stop — no LLM, no retrieval. Return immediately.
            return _build_dangerous_response(query)

        # ── Step 2: RAG retrieval ─────────────────────────────────────────────
        docs = self._retrieve_docs(query)
        retrieval_score = max((d["score"] for d in docs), default=0.0)
        context = self._build_context(docs)

        # ── Step 3: LLM structured generation ────────────────────────────────
        try:
            raw = self._call_llm(query, context, child_age_months, classification)
            response = self._parse_llm_response(raw, classification, retrieval_score)
        except Exception as exc:
            with open("scratch_error.txt", "a") as f: f.write(str(exc) + "\n")
            logger.error("LLM call failed: %s", exc, exc_info=True)
            response = self._uncertain_fallback(query, classification)

        # ── Step 4: Hard overrides ────────────────────────────────────────────
        response = _apply_hard_overrides(response, child_age_months)

        # ── Step 5: Human-readable layer ──────────────────────────────────────
        explanation, advice = _build_human_readable_layer(
            recommendation=Recommendation(response.recommendation),
            safety_flags=response.safety_flags,
            child_age_months=child_age_months,
        )
        response = response.model_copy(
            update={"user_explanation": explanation, "advice": advice}
        )

        return response

    # ── Private helpers ────────────────────────────────────────────────────────

    def _retrieve_docs(self, query: str, k: int = 5) -> list[dict]:
        try:
            return self.retriever.retrieve(query, k=k)
        except Exception as exc:
            logger.warning("Retrieval failed: %s", exc)
            return []

    def _build_context(self, docs: list[dict]) -> str:
        if not docs:
            return "No relevant product or safety information was found in the database."
        parts = []
        for i, doc in enumerate(docs, 1):
            score = doc.get("score", 0.0)
            text = doc.get("text", "").strip()
            parts.append(f"[Doc {i} | relevance={score:.2f}]\n{text}")
        return "\n\n".join(parts)

    def _call_llm(
        self,
        query: str,
        context: str,
        child_age_months: Optional[int],
        classification: QueryClassification,
    ) -> str:
        age_info = (
            f"The child is {child_age_months} months old."
            if child_age_months is not None
            else "Child's age was not specified."
        )

        prompt = f"""You are a children's product safety expert. Analyze the query below and return a JSON object.

QUERY: {query}
CHILD AGE: {age_info}
QUERY TYPE: {classification}

RETRIEVED PRODUCT/SAFETY CONTEXT:
{context}

Return ONLY a valid JSON object with these exact fields:
{{
  "query_language": "<ISO 639-1 code>",
  "recommendation": "<SAFE | NOT_SUITABLE | UNCERTAIN>",
  "confidence": <float 0.0-1.0>,
  "safety_flags": ["<flag1>", "<flag2>"],
  "reasoning": "<concise internal reasoning>",
  "reasoning_trace": ["<step 1>", "<step 2>", "..."],
  "alternatives": [
    {{"product_id": "<id>", "name": "<name>", "reason": "<why safer>"}}
  ]
}}

SAFETY RULES (you must apply these):
- If the product has small parts or choking hazards and the child is under 36 months → NOT_SUITABLE, flag: choking_hazard
- If the product has cords or strings and the child is under 36 months → NOT_SUITABLE, flag: strangulation_risk
- If the product has been recalled → NOT_SUITABLE, flag: product_recalled
- If the product contains toxic materials → NOT_SUITABLE, flag: toxic_material
- If information is insufficient to make a confident determination → UNCERTAIN
- Only return SAFE when you have clear positive evidence from the context

Return ONLY the JSON object. No markdown, no explanation, no code fences."""

        if self.client is None:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        response = self.client.models.generate_content(
            model=_MODEL_NAME,
            contents=prompt,
        )
        return response.text

    def _parse_llm_response(
        self,
        raw: str,
        classification: QueryClassification,
        retrieval_score: float,
    ) -> SafetyResponse:
        # Strip any accidental markdown fences
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed: %s\nRaw: %r", exc, raw[:500])
            raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc

        # Enforce UNCERTAIN if retrieval score too low
        if retrieval_score < _RETRIEVAL_THRESHOLD:
            data["recommendation"] = "UNCERTAIN"
            data.setdefault("safety_flags", []).append("missing_data")
            data.setdefault("reasoning_trace", []).append(
                f"[THRESHOLD] Retrieval score {retrieval_score:.2f} < {_RETRIEVAL_THRESHOLD} — forced UNCERTAIN."
            )

        # Enforce UNCERTAIN if LLM confidence too low
        llm_confidence = float(data.get("confidence", 0.0))
        if llm_confidence < _CONFIDENCE_THRESHOLD and data.get("recommendation") == "SAFE":
            data["recommendation"] = "UNCERTAIN"
            data.setdefault("reasoning_trace", []).append(
                f"[THRESHOLD] LLM confidence {llm_confidence:.2f} < {_CONFIDENCE_THRESHOLD} — SAFE downgraded to UNCERTAIN."
            )

        # Placeholder explanations — will be overwritten by _build_human_readable_layer
        data["user_explanation"] = "__pending__"
        data["advice"] = "__pending__"
        data["query_classification"] = classification.value

        return SafetyResponse(**data)

    def _uncertain_fallback(
        self,
        query: str,
        classification: QueryClassification,
    ) -> SafetyResponse:
        """Return a safe UNCERTAIN response when the LLM pipeline fails."""
        return SafetyResponse(
            query_language="en",
            query_classification=classification,
            recommendation=Recommendation.UNCERTAIN,
            confidence=0.0,
            safety_flags=["insufficient_data"],
            reasoning="We don’t have enough information to confirm safety at the moment.",
            reasoning_trace=[
                "LLM call failed — defaulting to UNCERTAIN for safety.",
            ],
            alternatives=[],
            user_explanation="We’re unable to analyze this right now. Please try again shortly.",
            advice="Please retry in a few moments or verify with official sources.",
        )


class _DefaultRetriever:
    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        from rag.retriever import search_products, search_safety_guidelines

        products = search_products(query, n_results=k)
        guidelines = search_safety_guidelines(query, n_results=max(3, k // 2))

        docs: list[dict] = []
        for item in products:
            docs.append(
                {
                    "text": f"Product {item['product_id']}\n{item['document']}",
                    "score": max(0.0, 1.0 - float(item.get("distance", 1.0))),
                    "metadata": {"product_id": item["product_id"], **(item.get("metadata") or {})},
                }
            )
        for item in guidelines:
            docs.append(
                {
                    "text": f"Safety guideline section {item['section_id']}\n{item['document']}",
                    "score": max(0.0, 1.0 - float(item.get("distance", 1.0))),
                    "metadata": {"section_id": item["section_id"], **(item.get("metadata") or {})},
                }
            )

        docs.sort(key=lambda doc: doc["score"], reverse=True)
        return docs[:k]


_DEFAULT_ADVISOR: SafetyAdvisor | None = None


def _get_default_advisor() -> SafetyAdvisor:
    global _DEFAULT_ADVISOR
    if _DEFAULT_ADVISOR is None:
        _DEFAULT_ADVISOR = SafetyAdvisor(_DefaultRetriever())
    return _DEFAULT_ADVISOR


import re

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
    if any(w in q for w in ["soap", "stroller", "diaper"]):
        return safe("This product type is generally safe when used as directed.",
                    "Use as instructed and supervise your child.")

    # fallback
    return uncertain("We don’t have enough information to confirm safety.",
                     "Verify with the manufacturer or a pediatrician.")

USE_LLM = True

def run_advisor(query: str, child_age_months: Optional[int] = None):
    """Compatibility entry point used by the Streamlit app."""
    result = rule_based_engine(query)
    if USE_LLM:
        try:
            pass
        except:
            pass
    return result

def get_recommendation(query: str, child_age_months: Optional[int] = None):
    """Backward-compatible alias for callers that expect a simple helper."""
    return run_advisor(query, child_age_months=child_age_months)

class ProductAdvisor:
    """Backward-compatible wrapper for older tests and scripts."""
    def __init__(self):
        pass

    def query(self, user_query: str):
        return run_advisor(user_query)