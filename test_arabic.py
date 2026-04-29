from dotenv import load_dotenv
load_dotenv()
from agent.advisor import ProductAdvisor

advisor = ProductAdvisor()

query = 'هل عربة جوي سبين آمنة لحديثي الولادة؟'
print('=== TC05 TEST ===')

import json, re, os
from google import genai
from agent.prompts import SYSTEM_PROMPT
from rag.retriever import get_retrieval_context, search_products

lang = advisor._detect_language(query)
print('Lang:', lang)

product_context, safety_context, best_score = get_retrieval_context(query)
print('Best Score:', best_score)
threshold = 0.25 if lang == 'ar' else 0.4
print('Threshold:', threshold)

response = advisor.query(query)
print('Recommendation:', response.recommendation)
print('Confidence:', response.confidence)
print('Reasoning trace:', response.reasoning_trace)
