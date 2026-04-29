from dotenv import load_dotenv
import os
from agent.advisor import ProductAdvisor

load_dotenv()
advisor = ProductAdvisor()
response = advisor.query('Is the BabyZen YOYO2 safe for my 5 month old baby?')
print(response.recommendation)
print(response.reasoning)
print(response.reasoning_trace)
