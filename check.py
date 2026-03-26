# filename: /workspaces/twitterbotscraper/code/check_models.py
import os
from google import genai

with open("/workspaces/twitterbotscraper/code/key.txt", "r") as f:
    api_key = f.read().strip()

client = genai.Client(api_key=api_key)

print("--- Your Available Models ---")
for model in client.models.list():
    print(model.name)