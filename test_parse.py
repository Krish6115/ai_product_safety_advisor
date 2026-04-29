import json, re
from agent.advisor import safe_parse_json

# Test with the exact kind of output we're seeing
test1 = '{\n  "query_language": "en",\n  "product_id": "MW-004",\n  "product_name": "Marble Run Deluxe Set - 100 Pieces",\n  "recommendation": "NOT_SUITABLE",\n  "confidence": 1.0,\n  "reasoning": "This is not safe.",\n  "reasoning_trace": ["step1", "step2"],\n  "safety_flags": ["choking_hazard", "age_inappropriate"],\n  "age_range_months": "36-144",\n  "alternatives": [{"product_id": "MW-005", "name": "LEGO Duplo", "reason": "Safe for younger"}],\n  "disclaimer": "Always verify."\n}'

result = safe_parse_json(test1)
print("Direct parse test:", result is not None)

# Try the schema
from agent.schemas import AdvisorResponse
try:
    resp = AdvisorResponse(**result)
    print("Schema OK:", resp.recommendation)
except Exception as e:
    print("Schema FAIL:", e)
