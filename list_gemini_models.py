import os
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))

print("Available Gemini models that support generateContent:")
for m in genai.list_models():
    if 'generateContent' in [method.name for method in m.supported_generation_methods]:
        print(f"  {m.name}")
