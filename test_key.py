from dotenv import load_dotenv
import os
from google import genai

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
print(f'Key: {api_key[:10]}...')

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model='gemini-flash-latest',
    contents='Say hello'
)
print('OK:', response.text)
