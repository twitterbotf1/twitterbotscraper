import os
import json
import time
import re
from google import genai
from google.genai import types

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "spicy_news_enriched.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "final_posts.json")
KEY_PATH = os.path.join(BASE_DIR, "key.txt")

def get_api_key():
    if not os.path.exists(KEY_PATH):
        print(f"🔴 Error: {KEY_PATH} not found.")
        return None
    with open(KEY_PATH, "r") as f:
        return f.read().strip()

SYSTEM_PROMPT = """
You are a specialized F1 commentator with a conditional 'Bias Switch'. 
Your task is to write 3 distinct tweet variations for each provided article based STRICTLY on its content.

LOGIC SWITCH:
1. IF the article is about Ferrari, Charles Leclerc, or Lewis Hamilton:
   - Tone: Loyal, supportive, and defensive. 
   - Persona: You are their biggest fan.

2. IF the article is about ANYONE ELSE (Red Bull, Max, Mercedes, Toto, McLaren, FIA, etc.):
   - Tone: Biting sarcasm, satire, and mockery.
   - Persona: You are a harsh critic.

STRICT RULES:
- NO CROSS-OVERS: If an article is NOT about Ferrari/Leclerc/Hamilton, DO NOT mention them. Stay focused only on the subjects in the text.
- LENGTH: Maximum 250 characters per tweet.
- LANGUAGE: Always English.
- OUTPUT: Return ONLY a raw JSON object mapping IDs to a list of 3 strings.

Example Output:
{"id_xyz": ["tweet1", "tweet2", "tweet3"]}
"""

def process_batch(client, batch_data):
    """Sends a batch of 5 articles to Gemini."""
    input_payload = [
        {
            "id": item["id"],
            "title": item["title"],
            "content": item["content"]
        } for item in batch_data
    ]
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=json.dumps(input_payload),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        
        # Clean the response text to ensure it is valid JSON
        text = response.text.strip()
        # Remove markdown code blocks if the AI accidentally adds them
        if text.startswith("```"):
            text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)
        
        return json.loads(text)
    except Exception as e:
        print(f"🔴 AI Batch Error: {e}")
        return {}

def main():
    api_key = get_api_key()
    if not api_key: return
    client = genai.Client(api_key=api_key)

    if not os.path.exists(INPUT_JSON):
        print("🔴 Input file not found.")
        return

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        full_data = json.load(f)

    # Filter out items where extraction failed
    valid_data = [item for item in full_data if item.get("content") != "COULD_NOT_EXTRACT"]
    
    if not valid_data:
        print("🟡 No valid content to process.")
        return

    all_tweets = {}
    batch_size = 5
    for i in range(0, len(valid_data), batch_size):
        batch = valid_data[i : i + batch_size]
        print(f"Processing batch {i//batch_size + 1} ({len(batch)} items)...")
        
        batch_results = process_batch(client, batch)
        all_tweets.update(batch_results)
        
        if i + batch_size < len(valid_data):
            time.sleep(5)

    final_output = []
    for item in valid_data:
        item_id = item["id"]
        if item_id in all_tweets:
            item["generated_tweets"] = all_tweets[item_id]
            final_output.append(item)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

    print(f"✅ Finished. Generated tweets for {len(final_output)} articles in {OUTPUT_JSON}")

if __name__ == "__main__":
    main()