from dotenv import load_dotenv
import os
from google import genai

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')

try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents='Hello'
    )
    print(response.text)
except Exception as e:
    print('ERROR:', e)
