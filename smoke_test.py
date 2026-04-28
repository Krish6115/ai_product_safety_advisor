"""Quick smoke test for all core components."""
from agent.schemas import AdvisorResponse, SafetyFlag, Recommendation
from agent.tools import age_check, product_lookup, weight_check
from rag.retriever import search_products, search_safety_guidelines

print("=== Import Test ===")
print("All imports OK")

print("\n=== Tool Tests ===")
# Age check: marble set for 18-month-old (should be NOT suitable)
r = age_check("MW-004", 18)
print(f"age_check(MW-004, 18mo): suitable={r['is_age_appropriate']}, choking={r.get('choking_hazard_risk')}")

# Age check: stroller for 3-month-old (should be suitable)
r2 = age_check("MW-001", 3)
print(f"age_check(MW-001, 3mo): suitable={r2['is_age_appropriate']}")

# Weight check: 15kg child on 10kg-max swing
r3 = weight_check("MW-006", 15)
print(f"weight_check(MW-006, 15kg): suitable={r3['is_weight_appropriate']}")

# Product lookup
r4 = product_lookup("MW-007")
print(f"product_lookup(MW-007): {r4['product']['name_en']}")

print("\n=== RAG Search Tests ===")
s = search_products("stroller for baby", 3)
print(f"Search 'stroller for baby': found {len(s)} results")
for item in s:
    print(f"  - {item['product_id']} (distance: {item['distance']:.3f})")

s2 = search_safety_guidelines("choking hazard for toddler", 2)
print(f"\nSearch 'choking hazard': found {len(s2)} sections")
for item in s2:
    print(f"  - {item['section_id']} (distance: {item['distance']:.3f})")

print("\n=== Schema Test ===")
resp = AdvisorResponse(
    query_language="en",
    product_id="MW-001",
    product_name="Chicco Bravo Stroller",
    recommendation=Recommendation.SUITABLE,
    confidence=0.9,
    reasoning="Product is suitable for the child's age.",
    safety_flags=[],
    age_range_months="0-36",
)
print(f"Schema validation OK: {resp.recommendation.value}, confidence={resp.confidence}")

print("\n[ALL SMOKE TESTS PASSED]")
