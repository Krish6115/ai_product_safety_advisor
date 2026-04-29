from dotenv import load_dotenv
import os
from agent.advisor import ProductAdvisor

load_dotenv()
advisor = ProductAdvisor()
try:
    response = advisor.query('Is this stroller safe?')
    print('RECOMMENDATION:', response.recommendation)
    print('TRACE:', response.reasoning_trace)
except Exception as e:
    print('UNCAUGHT EXCEPTION:', e)
