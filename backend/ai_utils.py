# -----------------------------------------------------
# backend/ai_utils.py
# -----------------------------------------------------


import os
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()  # <-- VERY IMPORTANT

# LOAD API KEY (set in environment)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# -----------------------------------------------------
# Create AI Embedding Using OpenAI
# -----------------------------------------------------
def generate_embedding(text: str):

    if not text:
        return None

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding