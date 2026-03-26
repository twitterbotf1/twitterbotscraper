import os
import json
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "new-urls.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "head.json")
FAIL_JSON = os.path.join(BASE_DIR, "fail.json")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
}

def main():
    if not os.path.exists(INPUT_JSON):
        return
        
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        return

    enriched = []
    failed_items = []
    success_count = 0
    fail_count = 0
    
    for item in data:
        try:
            res = requests.get(item['url'], headers=HEADERS, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.content, 'lxml')
            
            og_title = soup.find('meta', property='og:title')
            og_image = soup.find('meta', property='og:image')
            
            if og_title:
                item['title'] = og_title['content'].strip()
                item['hero_image'] = og_image['content'].strip() if og_image else None
                enriched.append(item)
                success_count += 1
            else:
                item['error'] = "No OG title found"
                failed_items.append(item)
                fail_count += 1
                
        except Exception as e:
            item['error'] = str(e)
            failed_items.append(item)
            fail_count += 1
            continue

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=4)

    with open(FAIL_JSON, "w", encoding="utf-8") as f:
        json.dump(failed_items, f, indent=4)
    
    print(f"Successful: {success_count}")
    print(f"Unsuccessful: {fail_count}")

if __name__ == "__main__":
    main()
