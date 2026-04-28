"""Pytest-based evaluation suite for the Product Advisor."""

import json
import sys
import pytest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.advisor import ProductAdvisor
from agent.schemas import AdvisorResponse
from eval.metrics import (
    check_schema_compliance,
    check_recommendation_match,
    check_safety_flags,
    check_language_match,
    check_confidence_bounds,
    compute_aggregate_metrics,
)

# Load test cases
TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
    TEST_CASES = json.load(f)


@pytest.fixture(scope="session")
def advisor():
    """Create a single advisor instance for the entire test session."""
    return ProductAdvisor()


@pytest.fixture(scope="session")
def all_results():
    """Accumulate results for aggregate reporting."""
    return []


def case_id(case):
    """Generate test ID from case."""
    return case["id"]


@pytest.mark.parametrize("case", TEST_CASES, ids=case_id)
def test_advisor_response(advisor, case, all_results):
    """Test the advisor's response against expected values."""
    result = {"id": case["id"], "category": case.get("category", "unknown")}

    # Query the advisor
    response = advisor.query(case["query"])

    # 1. Schema compliance — MUST pass
    assert check_schema_compliance(response), f"[{case['id']}] Response is not a valid AdvisorResponse"
    result["schema_valid"] = True

    # 2. Reasoning trace — MUST have at least 1 step
    has_trace = len(response.reasoning_trace) >= 1
    result["has_reasoning_trace"] = has_trace
    assert has_trace, (
        f"[{case['id']}] reasoning_trace is empty — expected at least 1 reasoning step"
    )

    # 3. Recommendation correctness
    if "expected_recommendation" in case:
        match = check_recommendation_match(response, case["expected_recommendation"])
        result["recommendation_correct"] = match
        assert match, (
            f"[{case['id']}] Expected recommendation '{case['expected_recommendation']}', "
            f"got '{response.recommendation.value}'"
        )

    # 4. Safety flags
    if "expected_flags" in case:
        flag_metrics = check_safety_flags(response, case["expected_flags"])
        result["flag_metrics"] = flag_metrics
        # Check recall — all expected flags should be present
        assert flag_metrics["recall"] >= 0.5, (
            f"[{case['id']}] Expected flags {case['expected_flags']}, "
            f"got {[f.value for f in response.safety_flags]}. Recall: {flag_metrics['recall']:.2f}"
        )

    # 5. Language match
    if "expected_language" in case:
        lang_match = check_language_match(response, case["expected_language"])
        result["language_correct"] = lang_match
        assert lang_match, (
            f"[{case['id']}] Expected language '{case['expected_language']}', "
            f"got '{response.query_language}'"
        )

    # 6. Confidence bounds
    min_conf = case.get("min_confidence")
    max_conf = case.get("max_confidence")
    if min_conf is not None or max_conf is not None:
        in_bounds = check_confidence_bounds(response, min_conf, max_conf)
        result["confidence_in_bounds"] = in_bounds
        assert in_bounds, (
            f"[{case['id']}] Confidence {response.confidence:.2f} out of bounds "
            f"(min={min_conf}, max={max_conf})"
        )

    all_results.append(result)


def test_aggregate_metrics(all_results):
    """Print aggregate metrics after all tests complete.

    Note: This test runs last due to dependency on accumulated results.
    """
    if not all_results:
        pytest.skip("No results accumulated yet")

    metrics = compute_aggregate_metrics(all_results)
    print("\n" + "=" * 60)
    print("AGGREGATE EVALUATION METRICS")
    print("=" * 60)
    for key, value in metrics.items():
        print(f"  {key:.<40} {value}")
    print("=" * 60)

    # Print reasoning trace coverage
    trace_count = sum(1 for r in all_results if r.get("has_reasoning_trace", False))
    print(f"  reasoning_trace_coverage............... {trace_count}/{len(all_results)} ({trace_count/len(all_results):.0%})")
    print("=" * 60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])

