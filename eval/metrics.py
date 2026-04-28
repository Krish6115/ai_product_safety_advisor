"""Evaluation metrics for the Product Advisor."""

from agent.schemas import AdvisorResponse, Recommendation, SafetyFlag


def check_schema_compliance(response: AdvisorResponse | None) -> bool:
    """Check if a response is a valid AdvisorResponse."""
    return response is not None and isinstance(response, AdvisorResponse)


def check_recommendation_match(response: AdvisorResponse, expected: str) -> bool:
    """Check if the recommendation matches the expected value."""
    return response.recommendation.value == expected


def check_safety_flags(response: AdvisorResponse, expected_flags: list[str]) -> dict:
    """Check if expected safety flags are present.

    Returns:
        Dict with precision, recall, f1 for flag matching.
    """
    actual = {f.value for f in response.safety_flags}
    expected = set(expected_flags)

    if not expected and not actual:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    if not expected:
        return {"precision": 0.0 if actual else 1.0, "recall": 1.0, "f1": 0.0 if actual else 1.0}

    if not actual:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0}

    true_positives = len(actual & expected)
    precision = true_positives / len(actual) if actual else 0.0
    recall = true_positives / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def check_language_match(response: AdvisorResponse, expected: str) -> bool:
    """Check if the response language matches expected."""
    return response.query_language == expected


def check_confidence_bounds(response: AdvisorResponse, min_conf: float | None, max_conf: float | None) -> bool:
    """Check if confidence is within expected bounds."""
    if min_conf is not None and response.confidence < min_conf:
        return False
    if max_conf is not None and response.confidence > max_conf:
        return False
    return True


def compute_aggregate_metrics(results: list[dict]) -> dict:
    """Compute aggregate metrics across all test case results.

    Args:
        results: List of per-test result dicts.

    Returns:
        Dict with aggregate metrics including accuracy and refusal_accuracy.
    """
    total = len(results)
    if total == 0:
        return {}

    schema_pass = sum(1 for r in results if r.get("schema_valid", False))
    rec_correct = sum(1 for r in results if r.get("recommendation_correct", False))
    lang_correct = sum(1 for r in results if r.get("language_correct", False))
    conf_correct = sum(1 for r in results if r.get("confidence_in_bounds", False))

    rec_tested = sum(1 for r in results if "recommendation_correct" in r)
    lang_tested = sum(1 for r in results if "language_correct" in r)
    conf_tested = sum(1 for r in results if "confidence_in_bounds" in r)

    flag_f1_scores = [r["flag_metrics"]["f1"] for r in results if "flag_metrics" in r]

    # Overall accuracy: correct predictions / total cases with expected recommendation
    accuracy = rec_correct / rec_tested if rec_tested else 0.0

    # Refusal accuracy: correct refusals / total refusal cases
    refusal_results = [r for r in results if r.get("category") == "refusal"]
    refusal_correct = sum(1 for r in refusal_results if r.get("recommendation_correct", False))
    refusal_tested = sum(1 for r in refusal_results if "recommendation_correct" in r)
    refusal_accuracy = refusal_correct / refusal_tested if refusal_tested else 0.0

    # Per-category breakdown
    categories = set(r.get("category", "unknown") for r in results)
    category_breakdown = {}
    for cat in sorted(categories):
        cat_results = [r for r in results if r.get("category") == cat]
        cat_rec_correct = sum(1 for r in cat_results if r.get("recommendation_correct", False))
        cat_rec_tested = sum(1 for r in cat_results if "recommendation_correct" in r)
        if cat_rec_tested > 0:
            category_breakdown[f"  {cat}"] = f"{cat_rec_correct}/{cat_rec_tested} ({cat_rec_correct/cat_rec_tested:.0%})"

    metrics = {
        "total_tests": total,
        "schema_compliance": f"{schema_pass}/{total} ({schema_pass/total:.0%})",
        "overall_accuracy": f"{rec_correct}/{rec_tested} ({accuracy:.0%})" if rec_tested else "N/A",
        "refusal_accuracy": f"{refusal_correct}/{refusal_tested} ({refusal_accuracy:.0%})" if refusal_tested else "N/A",
        "language_match_rate": f"{lang_correct}/{lang_tested} ({lang_correct/lang_tested:.0%})" if lang_tested else "N/A",
        "confidence_calibration": f"{conf_correct}/{conf_tested} ({conf_correct/conf_tested:.0%})" if conf_tested else "N/A",
        "safety_flag_avg_f1": f"{sum(flag_f1_scores)/len(flag_f1_scores):.2f}" if flag_f1_scores else "N/A",
    }

    if category_breakdown:
        metrics["--- per category ---"] = ""
        metrics.update(category_breakdown)

    return metrics
