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


class ProductAdvisor:
    """Mumzworld Product Safety & Suitability Advisor."""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set. Copy .env.example to .env and add your key.")
        self.client = genai.Client(api_key=api_key)
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

    def _parse_llm_response(self, raw_text: str) -> AdvisorResponse | None:
        """Parse LLM response into validated AdvisorResponse."""
        # Strip markdown code fences if present
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            response = AdvisorResponse(**data)

            # Apply uncertainty threshold logic
            response = self._apply_uncertainty_threshold(response)

            return response
        except (json.JSONDecodeError, Exception):
            return None

    def _apply_uncertainty_threshold(self, response: AdvisorResponse) -> AdvisorResponse:
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

        # Rule 3: insufficient_data flag → ensure UNCERTAIN if confidence is moderate
        if SafetyFlag.INSUFFICIENT_DATA in response.safety_flags:
            if response.recommendation == Recommendation.SUITABLE:
                response.recommendation = Recommendation.UNCERTAIN
                response.reasoning_trace.append(
                    "[OVERRIDE] Insufficient data flag present — cannot confirm SUITABLE"
                )

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
            return AdvisorResponse(
                query_language=lang,
                recommendation=Recommendation.UNCERTAIN,
                confidence=0.1,
                reasoning="Unable to retrieve product information. Please try again."
                if lang == "en"
                else "غير قادر على استرداد معلومات المنتج. يرجى المحاولة مرة أخرى.",
                reasoning_trace=["RAG retrieval failed", "Returning UNCERTAIN due to system error"],
                safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
            )

        # Step 2b: Check retrieval quality — if score is too low, data is insufficient
        if best_score < RETRIEVAL_THRESHOLD:
            return AdvisorResponse(
                query_language=lang,
                recommendation=Recommendation.UNCERTAIN,
                confidence=max(0.1, best_score),
                reasoning="I don't have enough product information to make a safe recommendation."
                if lang == "en"
                else "لا أملك معلومات كافية عن المنتج لتقديم توصية آمنة.",
                reasoning_trace=[
                    f"RAG retrieval score: {best_score:.2f}",
                    f"Below retrieval threshold: {RETRIEVAL_THRESHOLD}",
                    "Insufficient product data to assess safety",
                    "Returning UNCERTAIN — refusing to guess",
                ],
                safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
            )

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
                    "temperature": 0.1,
                    "max_output_tokens": 1024,
                },
            )
            raw_text = response.text
        except Exception as e:
            return AdvisorResponse(
                query_language=lang,
                recommendation=Recommendation.UNCERTAIN,
                confidence=0.0,
                reasoning=f"LLM call failed: {str(e)}",
                reasoning_trace=["LLM API call failed", f"Error: {str(e)}", "Returning UNCERTAIN"],
                safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
            )

        # Step 6: Parse and validate
        parsed = self._parse_llm_response(raw_text)
        if parsed:
            return parsed

        # Step 7: Retry once with error feedback
        try:
            retry_prompt = RETRY_PROMPT.format(
                error="Could not parse as valid JSON/schema",
                previous_response=raw_text[:500],
            )
            retry_response = self.client.models.generate_content(
                model=self.model_name,
                contents=retry_prompt,
                config={
                    "system_instruction": system,
                    "temperature": 0.0,
                    "max_output_tokens": 1024,
                },
            )
            parsed = self._parse_llm_response(retry_response.text)
            if parsed:
                return parsed
        except Exception:
            pass

        # Final fallback
        return AdvisorResponse(
            query_language=lang,
            recommendation=Recommendation.UNCERTAIN,
            confidence=0.1,
            reasoning="Unable to generate a valid assessment. Please rephrase your question."
            if lang == "en"
            else "غير قادر على إنشاء تقييم صالح. يرجى إعادة صياغة سؤالك.",
            reasoning_trace=["LLM response failed schema validation", "Retry also failed", "Returning UNCERTAIN fallback"],
            safety_flags=[SafetyFlag.INSUFFICIENT_DATA],
        )
