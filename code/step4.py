import os
import json
import time
import re
from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "spicy_news.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "final_posts.json")
KEY_PATH = os.path.join(BASE_DIR, "key.txt")

SYSTEM_PROMPT = """
You are a Teenage F1 content Creator. You use the given content to derive a summary and a spicy rage bait type post for your social media account. You like to use appropriate emoji's and always keep both summary and the spicy post under 230 characters to allow for manual additions. 

You have a dual persona that only applies to the spicy post:

1. IF the article is about Charles Leclerc:
   - Persona: You are his fiercest soldier, ready to go to war for him. He is absolutely perfect and incapable of error. You never try to make the post about him but you always defend him according to the claims made in the article. Any negatives are always the teams fault and nothing Charles do is bad.  
   - Tone: Extremely defensive, aggressive, and obsessed.
   - Team and teammate Stance: If Ferrari fails Charles, mock the team relentlessly. If Charles isn't mentioned, be indifferent to the team and the teammate Lewis Hamilton.

2. IF the article is about ANYONE ELSE (Red Bull, Max, McLaren, etc.) or specifically the FIA/FOM:
   - Persona: A hateful, cynical contrarian. Who mocks the FIA/FOM without a second though and not in a good way, its like a personal grudge kind of thing, Nothing they do is good. If it is about other teams or drivers you still mock them but not as hard as you mock the FIA/FOM. But still sarcasm and mockery is what they get. 
   - Tone: Pure mockery, sarcasm, and vitriol. 
   - Stance: Reject all positive results, find flaws in everything, and treat the FIA/FOM as pure evil. You are here to drag everyone down and trigger their fanbases.

STRICT RULES:
- NO CROSS-OVERS: If the article is not about Charles, do not mention him.
- NO COMPARISONS: Stick strictly to the content of the current article. 
- LENGTH: Maximum 230 characters per string (Summary and Tweet).
- LANGUAGE: English.
- OUTPUT: Return ONLY a raw JSON object mapping IDs to a list of 2 strings: {"id_xyz": ["summary", "tweet1"]}
"""

def get_api_key():
    if not os.path.exists(KEY_PATH): return None
    with open(KEY_PATH, "r") as f: return f.read().strip()

def process_batch(client, batch_data):
    input_payload = [{"id": item["id"], "title": item["title"], "content": item["content"]} for item in batch_data]
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=json.dumps(input_payload),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        text = response.text.strip()
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

    if not os.path.exists(INPUT_JSON): return
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        valid_data = json.load(f)

    if not valid_data: return

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
    # We remove domain from the final JSON but use it for the suffix
    keys_to_remove = {"id", "title", "content", "domain"}

    for item in valid_data:
        item_id = item["id"]
        if item_id in all_tweets:
            generated = all_tweets[item_id] # [summary, tweet]
            
            # 1. Clean Domain Name
            raw_domain = item.get("domain", "news")
            clean_domain = raw_domain.replace("www.", "").replace(".com", "")
            
            # 2. Append required suffix to the Summary (generated[0])
            suffix = f" #formula1 #f1 #f1twt #{clean_domain}"
            generated[0] = f"{generated[0]}{suffix}"
            
            # 3. Build final item
            cleaned_item = {k: v for k, v in item.items() if k not in keys_to_remove}
            cleaned_item["generated_tweets"] = [item["title"]] + generated
            final_output.append(cleaned_item)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

    print(f"✅ Finished. Appended domain tags to {len(final_output)} summaries.")

if __name__ == "__main__":
    main()
