from dotenv import load_dotenv
load_dotenv()
import time
from agent.advisor import ProductAdvisor, safe_parse_json
from agent.schemas import AdvisorResponse

advisor = ProductAdvisor()

# TC06: Age boundary fail  
query = 'Is the BabyZen YOYO2 safe for my 5 month old?'
print('=== TC06 TEST ===')

import json, re, os
from google import genai
from agent.prompts import SYSTEM_PROMPT
from rag.retriever import get_retrieval_context, search_products

product_context, safety_context, best_score = get_retrieval_context(query)
retrieved = search_products(query, n_results=3)
tool_results = advisor._run_tools(query, retrieved)

system = SYSTEM_PROMPT.format(
    safety_context=safety_context,
    product_context=product_context,
    tool_results=tool_results,
)

response = advisor.client.models.generate_content(
    model=advisor.model_name,
    contents=query,
    config={
        'system_instruction': system,
        'temperature': 0.2,
        'max_output_tokens': 1024,
    },
)

raw = response.text
print('FULL RAW OUTPUT:')
print(repr(raw))
print()
print('LENGTH:', len(raw))
print()

data = safe_parse_json(raw)
print('PARSED DATA:', data is not None)
if data:
    try:
        resp = AdvisorResponse(**data)
        print('SCHEMA OK:', resp.recommendation)
    except Exception as e:
        print('SCHEMA FAIL:', e)
else:
    print('PARSE RETURNED NONE')
