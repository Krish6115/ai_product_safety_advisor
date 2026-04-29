"""Core Product Advisor agent — orchestrates RAG, tools, and LLM."""

import json
import re
import os
from dotenv import load_dotenv
from google import genai
from langdetect import detect

from agent.schemas import AdvisorResponse, Recommendation, SafetyFlag
from agent.prompts import SYSTEM_PROMPT, RETRY_PROMPT
from agent.tools import age_check, product_lookup, weight_check
from rag.retriever import get_retrieval_context

load_dotenv()


# Confidence threshold — below this, force UNCERTAIN recommendation
UNCERTAINTY_THRESHOLD = 0.6

# RAG retrieval score threshold — below this, data is considered insufficient
RETRIEVAL_THRESHOLD = 0.4


def safe_parse_json(text: str) -> dict | None:
    """FIX 2: Safe JSON parser with regex fallback.

    Tries multiple strategies to extract valid JSON from messy LLM output:
    1. Direct json.loads
    2. Regex extraction of {...} block
    3. Strip markdown fences then parse
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: Regex extract the JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', text)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    return None


class ProductAdvisor:
    """Mumzworld Product Safety & Suitability Advisor."""

    def __init__(self, model_name: str = "gemini-flash-latest"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set. Copy .env.example to .env and add your key.")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def _detect_language(self, text: str) -> str:
        """Detect if the query is English or Arabic."""
        try:
            lang = detect(text)
            return "ar" if lang == "ar" else "en"
        except Exception:
            return "en"

    def _extract_child_age(self, query: str) -> int | None:
        """Extract child age in months from the query text."""
        # Patterns: "X month", "X months", "X-month", "Xm"
        month_patterns = [
            r"(\d+)\s*(?:month|months|month-old|months-old|m\b|أشهر|شهر)",
        ]
        for pattern in month_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Patterns: "X year", "X years", "X-year-old", "سنة", "سنوات"
        year_patterns = [
            r"(\d+)\s*(?:year|years|year-old|years-old|yr|yrs|سنة|سنوات|سنه)",
        ]
        for pattern in year_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return int(match.group(1)) * 12

        return None

    def _extract_child_weight(self, query: str) -> float | None:
        """Extract child weight in kg from the query."""
        patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram|كجم|كيلو)",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _run_tools(self, query: str, retrieved_products: list[dict]) -> str:
        """Run relevant tools based on query context."""
        results = []
        child_age = self._extract_child_age(query)
        child_weight = self._extract_child_weight(query)

        if not retrieved_products:
            return "No tools executed — no products retrieved."

        # Run tools on the top retrieved product
        top_product_id = retrieved_products[0].get("product_id") if retrieved_products else None

        if top_product_id:
            # Always do product lookup
            lookup_result = product_lookup(top_product_id)
            results.append(f"product_lookup({top_product_id}): {json.dumps(lookup_result, ensure_ascii=False)}")

            # Age check if age is mentioned
            if child_age is not None:
                age_result = age_check(top_product_id, child_age)
                results.append(f"age_check({top_product_id}, {child_age}mo): {json.dumps(age_result, ensure_ascii=False)}")

            # Weight check if weight is mentioned
            if child_weight is not None:
                weight_result = weight_check(top_product_id, child_weight)
                results.append(f"weight_check({top_product_id}, {child_weight}kg): {json.dumps(weight_result, ensure_ascii=False)}")

        return "\n".join(results) if results else "No specific tools triggered."

    # Map of common LLM-invented flag names to valid SafetyFlag values
    FLAG_ALIASES = {
        "age_limit": "age_inappropriate",
        "age_restriction": "age_inappropriate",
        "small_parts": "choking_hazard",
        "small_pieces": "choking_hazard",
        "battery_risk": "battery_hazard",
        "needs_supervision": "supervision_required",
        "material_safety": "material_concern",
        "recall": "recall_alert",
        "no_data": "insufficient_data",
    }

    VALID_FLAGS = {f.value for f in SafetyFlag}

    def _normalize_safety_flags(self, flags: list) -> list[str]:
        """Normalize LLM-invented flag names to valid SafetyFlag enum values."""
        normalized = []
        for flag in flags:
            flag_str = str(flag).strip().lower()
            if flag_str in self.VALID_FLAGS:
                normalized.append(flag_str)
            elif flag_str in self.FLAG_ALIASES:
                normalized.append(self.FLAG_ALIASES[flag_str])
            # else: silently drop unknown flags
        return normalized

    def _parse_llm_response(self, raw_text: str) -> AdvisorResponse | None:
        """Parse LLM response using safe parser + schema construction."""
        data = safe_parse_json(raw_text)
        if data is None:
            return None

        # Fill in defaults for missing optional fields
        data.setdefault("query_language", "en")
        data.setdefault("confidence", 0.0)
        data.setdefault("reasoning", "")
        data.setdefault("reasoning_trace", [])
        data.setdefault("rule_applied", [])
        data.setdefault("safety_flags", [])
        data.setdefault("alternatives", [])
        data.setdefault("disclaimer", "Always verify product safety with manufacturer guidelines. | تحقق دائماً من سلامة المنتج مع إرشادات الشركة المصنعة.")

        # Normalize safety flags to valid enum values
        data["safety_flags"] = self._normalize_safety_flags(data.get("safety_flags", []))

        try:
            return AdvisorResponse(**data)
        except Exception:
            return None

    def _apply_uncertainty_threshold(self, response: AdvisorResponse, child_age: int | None = None) -> AdvisorResponse:
        """Apply explicit threshold-based uncertainty and safety overrides.

        Engineering logic (not just prompting):
        - If confidence < UNCERTAINTY_THRESHOLD → force UNCERTAIN
        - If critical safety flags present + SUITABLE → force NOT_SUITABLE
        - Append override reasoning to trace
        """
        # Rule 1: Low confidence → UNCERTAIN
        if response.confidence < UNCERTAINTY_THRESHOLD and response.recommendation != Recommendation.UNCERTAIN:
            original = response.recommendation.value
            response.recommendation = Recommendation.UNCERTAIN
            response.reasoning_trace.append(
                f"[OVERRIDE] Confidence {response.confidence:.2f} < threshold {UNCERTAINTY_THRESHOLD} — forced UNCERTAIN (was {original})"
            )

        # Rule 2: Critical safety flags + SUITABLE → NOT_SUITABLE
        critical_flags = {SafetyFlag.CHOKING_HAZARD, SafetyFlag.AGE_INAPPROPRIATE, SafetyFlag.WEIGHT_LIMIT}
        if response.safety_flags and any(f in critical_flags for f in response.safety_flags):
            if response.recommendation == Recommendation.SUITABLE:
                response.recommendation = Recommendation.NOT_SUITABLE
                triggered = [f.value for f in response.safety_flags if f in critical_flags]
                response.reasoning_trace.append(
                    f"[OVERRIDE] Critical safety flags {triggered} detected — forced NOT_SUITABLE"
                )
                if SafetyFlag.AGE_INAPPROPRIATE in response.safety_flags:
                    response.rule_applied.append("min_age_violation")
                if SafetyFlag.WEIGHT_LIMIT in response.safety_flags:
                    response.rule_applied.append("max_weight_violation")

        # Rule 3: insufficient_data flag → ensure UNCERTAIN if confidence is moderate
        if SafetyFlag.INSUFFICIENT_DATA in response.safety_flags:
            if response.recommendation == Recommendation.SUITABLE:
                response.recommendation = Recommendation.UNCERTAIN
                response.reasoning_trace.append(
                    "[OVERRIDE] Insufficient data flag present — cannot confirm SUITABLE"
                )

        # Rule 4: Hardcoded safety rule for Lego and toddlers
        if response.product_name and "lego" in response.product_name.lower():
            if child_age is not None and child_age < 36:
                if response.recommendation != Recommendation.NOT_SUITABLE:
                    response.recommendation = Recommendation.NOT_SUITABLE
                    if SafetyFlag.CHOKING_HAZARD not in response.safety_flags:
                        response.safety_flags.append(SafetyFlag.CHOKING_HAZARD)
                    response.reasoning_trace.append(
                        "[OVERRIDE] Hardcoded safety rule: LEGO products contain small parts and are NOT_SUITABLE for children under 36 months"
                    )
                    response.rule_applied.append("choking_hazard_under_36m")

        return response

    def _build_human_readable_layer(self, response: AdvisorResponse) -> AdvisorResponse:
        """Populate user-facing explanation and advice from the final decision."""
        lang = "ar" if response.query_language == "ar" else "en"

        def join_terms(terms: list[str]) -> str:
            if not terms:
                return ""
            if len(terms) == 1:
                return terms[0]
            if len(terms) == 2:
                return f"{terms[0]} and {terms[1]}" if lang == "en" else f"{terms[0]} و {terms[1]}"
            separator = ", " if lang == "en" else "، "
            tail_joiner = ", and " if lang == "en" else "، و "
            return separator.join(terms[:-1]) + tail_joiner + terms[-1]

        flag_values = {flag.value for flag in response.safety_flags}
        age_flag = SafetyFlag.AGE_INAPPROPRIATE.value in flag_values
        weight_flag = SafetyFlag.WEIGHT_LIMIT.value in flag_values
        choking_flag = SafetyFlag.CHOKING_HAZARD.value in flag_values
        supervision_flag = SafetyFlag.SUPERVISION_REQUIRED.value in flag_values
        battery_flag = SafetyFlag.BATTERY_HAZARD.value in flag_values

        if response.recommendation == Recommendation.SUITABLE:
            if lang == "ar":
                response.user_explanation = (
                    "هذا المنتج مناسب لطفلك وفقًا للمعلومات المتاحة."
                    if not (supervision_flag or battery_flag)
                    else "هذا المنتج مناسب بشكل عام، لكن يجب استخدامه تحت إشراف شخص بالغ."
                )
                response.advice = (
                    "يمكنك استخدامه بأمان. راقب طفلك دائمًا واتبع تعليمات الشركة المصنعة."
                    if not (supervision_flag or battery_flag)
                    else "استخدمه تحت إشراف شخص بالغ واتبع تعليمات السلامة بدقة."
                )
            else:
                response.user_explanation = (
                    "This product appears safe and suitable for your child based on the information available."
                    if not (supervision_flag or battery_flag)
                    else "This product is generally suitable, but it should be used with adult supervision."
                )
                response.advice = (
                    "You can use it, but always supervise your child and follow the manufacturer instructions."
                    if not (supervision_flag or battery_flag)
                    else "Use it with adult supervision and follow the safety instructions closely."
                )

        elif response.recommendation == Recommendation.NOT_SUITABLE:
            if lang == "ar":
                causes = []
                if age_flag:
                    causes.append("هو مخصص لأطفال أكبر سنًا")
                if weight_flag:
                    causes.append("وزن طفلك يتجاوز الحد المسموح")
                if choking_flag:
                    causes.append("قد يحتوي على أجزاء صغيرة غير مناسبة للأطفال الصغار")

                response.user_explanation = (
                    f"هذا المنتج غير مناسب لأن {join_terms(causes)}." if causes else "هذا المنتج غير مناسب وفقًا لمعلومات السلامة المتاحة."
                )

                advice_parts = []
                if age_flag:
                    advice_parts.append("اختر منتجًا مناسبًا لعمر طفلك")
                if weight_flag:
                    advice_parts.append("اختر منتجًا بحد وزن أعلى")
                if choking_flag:
                    advice_parts.append("اختر ألعابًا بدون أجزاء صغيرة قابلة للفصل")

                if not advice_parts:
                    response.advice = "تجنب هذا المنتج واختر بديلاً أكثر أمانًا."
                elif len(advice_parts) == 1:
                    response.advice = f"تجنب هذا المنتج و{advice_parts[0]}."
                else:
                    response.advice = "تجنب هذا المنتج واختر بديلاً أكثر أمانًا يناسب عمر طفلك واحتياجات السلامة."
            else:
                causes = []
                if age_flag:
                    causes.append("it is meant for older children")
                if weight_flag:
                    causes.append("your child exceeds the weight limit")
                if choking_flag:
                    causes.append("it may contain small parts")

                response.user_explanation = (
                    f"This product is not suitable because {join_terms(causes)}." if causes else "This product is not suitable based on the safety information available."
                )

                advice_parts = []
                if age_flag:
                    advice_parts.append("choose a product rated for your child's age")
                if weight_flag:
                    advice_parts.append("choose a product with a higher weight limit")
                if choking_flag:
                    advice_parts.append("choose toys without small detachable parts")

                if not advice_parts:
                    response.advice = "Avoid this product and choose a safer alternative."
                elif len(advice_parts) == 1:
                    response.advice = f"Avoid this product and {advice_parts[0]}."
                else:
                    response.advice = "Avoid this product and choose a safer alternative that matches your child's age and safety needs."

        else:
            if lang == "ar":
                response.user_explanation = "لا نملك معلومات كافية لتأكيد سلامة هذا المنتج."
                response.advice = "يرجى مشاركة اسم المنتج وعمر الطفل أو وزنه حتى نتمكن من التحقق مرة أخرى."
            else:
                response.user_explanation = "We don't have enough information to confirm safety."
                response.advice = "Please share the product name and your child's age or weight so we can check again."

        return response

    def query(self, user_query: str) -> AdvisorResponse:
        """Process a user query and return a structured safety assessment.

        Args:
            user_query: The user's question about a product (EN or AR).

        Returns:
            AdvisorResponse with recommendation, safety flags, and confidence.
        """
        # Step 1: Detect language
        lang = self._detect_language(user_query)

        # Step 2: RAG retrieval
        try:
            product_context, safety_context, best_score = get_retrieval_context(user_query)
        except Exception:
            # If RAG fails, return uncertain response
            return self._build_human_readable_layer(AdvisorResponse(
                query_language=lang,
                recommendation=Recommendation.UNCERTAIN,
                confidence=0.1,
                reasoning="Unable to retrieve product information. Please try again."
                if lang == "en"
                else "غير قادر على استرداد معلومات المنتج. يرجى المحاولة مرة أخرى.",
                reasoning_trace=["RAG retrieval failed", "Returning UNCERTAIN due to system error"],
                safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
            ))

        # Step 2b: Check retrieval quality — if score is too low, data is insufficient
        threshold = 0.25 if lang == "ar" else RETRIEVAL_THRESHOLD
        if best_score < threshold:
            return self._build_human_readable_layer(AdvisorResponse(
                query_language=lang,
                recommendation=Recommendation.UNCERTAIN,
                confidence=max(0.1, best_score),
                reasoning="I don't have enough product information to make a safe recommendation."
                if lang == "en"
                else "لا أملك معلومات كافية عن المنتج لتقديم توصية آمنة.",
                reasoning_trace=[
                    f"RAG retrieval score: {best_score:.2f}",
                    f"Below retrieval threshold: {threshold}",
                    "Insufficient product data to assess safety",
                    "Returning UNCERTAIN — refusing to guess",
                ],
                safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
            ))

        # Step 3: Run tools on retrieved products
        from rag.retriever import search_products
        retrieved = search_products(user_query, n_results=3)
        tool_results = self._run_tools(user_query, retrieved)

        # Step 4: Build prompt
        system = SYSTEM_PROMPT.format(
            safety_context=safety_context,
            product_context=product_context,
            tool_results=tool_results,
        )

        # Step 5: Call LLM
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_query,
                config={
                    "system_instruction": system,
                    "temperature": 0.2,
                    "max_output_tokens": 2048,
                },
            )
            raw_text = response.text

            # FIX 1: Print raw LLM output for debugging
            print("\n===== RAW LLM OUTPUT =====")
            print(raw_text[:500] if raw_text else "EMPTY")
            print("==========================\n")

            # Step 6: Parse with safe parser
            parsed = self._parse_llm_response(raw_text)

            # FIX 4: Retry with stricter instruction if first parse fails
            if not parsed:
                print("[RETRY] First parse failed, retrying with stricter prompt...")
                retry_response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_query,
                    config={
                        "system_instruction": system + "\n\nYour previous response was invalid JSON. Return ONLY valid JSON. No explanation.",
                        "temperature": 0.1,
                        "max_output_tokens": 2048,
                    },
                )
                raw_text = retry_response.text
                print("\n===== RETRY RAW OUTPUT =====")
                print(raw_text[:500] if raw_text else "EMPTY")
                print("============================\n")
                parsed = self._parse_llm_response(raw_text)

            if parsed:
                parsed.query_language = lang
                child_age = self._extract_child_age(user_query)
                parsed = self._apply_uncertainty_threshold(parsed, child_age)
                return self._build_human_readable_layer(parsed)

            raise ValueError("Failed to parse LLM response after retry")

        except Exception as e:
            return self._build_human_readable_layer(AdvisorResponse(
                query_language=lang,
                recommendation=Recommendation.UNCERTAIN,
                confidence=0.0,
                reasoning=f"LLM call failed: {str(e)}",
                reasoning_trace=["LLM API call failed", f"Error: {str(e)}", "Returning UNCERTAIN"],
                safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
            ))
