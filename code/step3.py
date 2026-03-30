# filename: /workspaces/twitterbotscraper/code/step3.py
import os
import json
from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "head.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "spicy_news.json")
KEY_PATH = os.path.join(BASE_DIR, "key.txt")

SYSTEM_PROMPT = """
You are a cynical F1 social media strategist aiming for maximum viral engagement.
Analyze the provided IDs and Titles.

1. CRITERIA: Select the 20 most "spicy" items. Focus on:
   - Driver/Team drama or "war of words".
   - Controversial steward decisions or FIA bias.
   - Shocking rumors or major technical failures.

2. DEDUPLICATION:
   - Headlines may be in English, Italian, or Spanish. 
   - You must recognize when multiple titles refer to the SAME news event across different languages.
   - For any given news event, pick only ONE ID (the one with the most provocative title).

3. UNIQUENESS: Ensure each of the 20 selected IDs represents a different, unique news topic.

4. EXCLUSIONS: Skip standard race results, practice times, weather updates, or generic PR quotes.

5. OUTPUT: Return ONLY a JSON list of the 20 chosen IDs: ["id1", "id2", ...]
"""

def get_api_key():
    if not os.path.exists(KEY_PATH): return None
    with open(KEY_PATH, "r") as f: return f.read().strip()

def main():
    if not os.path.exists(INPUT_JSON): return
    with open(INPUT_JSON, "r") as f:
        full_data = json.load(f)

    if not full_data: return

    # Check if we should skip Gemini
    if len(full_data) <= 20:
        with open(OUTPUT_JSON, "w") as f:
            json.dump(full_data, f, indent=4)
        print(f"✅ Items count ({len(full_data)}) <= 20. Saved directly to {OUTPUT_JSON}.")
        return

    api_key = get_api_key()
    if not api_key: return
    client = genai.Client(api_key=api_key)

    input_to_gemini = [{"id": item["id"], "title": item["title"]} for item in full_data]

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=json.dumps(input_to_gemini),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        
        spicy_ids = json.loads(response.text)
        final_list = [item for item in full_data if item["id"] in spicy_ids]

        with open(OUTPUT_JSON, "w") as f:
            json.dump(final_list, f, indent=4)
            
        print(f"✅ Successfully filtered {len(final_list)} spicy items using gemini-2.5-flash-lite.")

    except Exception as e:
        print(f"🔴 Error: {e}")

if __name__ == "__main__":
    main()
