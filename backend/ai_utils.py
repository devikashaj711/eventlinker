import os
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()  # <-- VERY IMPORTANT

# LOAD API KEY (set in environment or hardcode during testing)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_embedding(text: str):
    """
    Converts text into a vector embedding using OpenAI.
    """
    if not text:
        return None

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding