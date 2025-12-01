# backend/ai_utils.py
import os
import json
import numpy as np
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

# ---------- Create OpenAI client ----------

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    # This print is just for debugging; you can remove it later
    print("ERROR: OPENAI_API_KEY is not set. Check your .env and path.")
client = OpenAI(api_key=api_key)


def embed_text(text: str):
    """
    Returns a numpy vector (float32) embedding for a piece of text.
    """
    if not text:
        text = ""
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return np.array(resp.data[0].embedding, dtype="float32")

def embedding_to_json(vec: np.ndarray) -> str:
    """
    Convert numpy vector to JSON string for storing in MySQL.
    """
    return json.dumps(vec.tolist())

def json_to_embedding(raw: str):
    """
    Convert JSON text from MySQL back to numpy vector.
    """
    if not raw:
        return None
    data = json.loads(raw)
    return np.array(data, dtype="float32")

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
