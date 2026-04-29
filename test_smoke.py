from dotenv import load_dotenv
load_dotenv()
from agent.advisor import ProductAdvisor

advisor = ProductAdvisor()
response = advisor.query('Is this stroller safe for my 6 month old baby?')
print('---RESULT---')
print('Recommendation:', response.recommendation.value)
print('Confidence:', response.confidence)
print('Reasoning:', response.reasoning[:200])
print('Trace:', response.reasoning_trace)
