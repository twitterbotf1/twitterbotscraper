import os
import json
import requests
from bs4 import BeautifulSoup

# Setup file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_JSON = os.path.join(BASE_DIR, "new-urls.json")
OUTPUT_JSON = os.path.join(BASE_DIR, "head.json")

# Standard headers to prevent being blocked by websites
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
}

def main():
    # 1. Check if the input file exists
    if not os.path.exists(INPUT_JSON):
        print(f"File {INPUT_JSON} not found.")
        return
        
    # 2. Load the list of URLs
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        return

    enriched = []
    
    # 3. Process each URL
    for item in data:
        try:
            # Download the page
            res = requests.get(item['url'], headers=HEADERS, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.content, 'lxml')
            
            # --- FETCH TITLE ---
            og_title = soup.find('meta', property='og:title')
            
            # --- FETCH HERO IMAGE ---
            og_image = soup.find('meta', property='og:image')
            
            # Only add to list if a title was found
            if og_title:
                item['title'] = og_title['content'].strip()
                
                # Add the hero image URL if it exists, otherwise set as None
                item['hero_image'] = og_image['content'].strip() if og_image else None
                
                enriched.append(item)
                print(f"Successfully processed: {item['url']}")
            else:
                print(f"Skipped (no title found): {item['url']}")
                
        except Exception as e:
            print(f"Error processing {item['url']}: {e}")
            continue

    # 4. Save the results to the output file
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=4)
    
    print(f"Done. Saved results to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()