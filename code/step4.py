import json
import os
import time
import cloudscraper
import trafilatura
from playwright.sync_api import sync_playwright

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "spicy_news.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "spicy_news_enriched.json")

def extract_with_fast_method(url):
    """Stage 1: Attempt to get content using cloudscraper and trafilatura."""
    try:
        scraper = cloudscraper.create_scraper()
        # Get HTML content bypassing simple Cloudflare/bot checks
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            # Extract clean text from HTML
            content = trafilatura.extract(response.text)
            return content
    except Exception as e:
        print(f"   - Fast method failed for {url}: {e}")
    return None

def extract_with_browser(url):
    """Stage 2: Fallback to Playwright for JS-heavy or protected sites."""
    try:
        with sync_playwright() as p:
            # Launch a headless browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Navigate and wait for the page to load
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            # Give JS a small moment to run
            time.sleep(2) 
            
            html = page.content()
            browser.close()
            
            # Extract clean text from rendered HTML
            return trafilatura.extract(html)
    except Exception as e:
        print(f"   - Browser method failed for {url}: {e}")
    return None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Starting processing for {len(data)} links...")
    
    enriched_data = []

    for index, item in enumerate(data):
        url = item.get("url")
        print(f"[{index+1}/{len(data)}] Processing: {url}")
        
        # Step 1: Try Fast Scraper
        content = extract_with_fast_method(url)
        
        # Step 2: If Stage 1 failed or returned empty, try Browser rendering
        if not content or len(content.strip()) < 100:
            print(f"   - Content empty or too short. Trying browser fallback...")
            content = extract_with_browser(url)
        
        # Add content to our item (if found)
        item["content"] = content if content else "COULD_NOT_EXTRACT"
        
        enriched_data.append(item)
        
        # Small delay to avoid aggressive rate-limiting
        time.sleep(1)

    # Save the updated data
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(enriched_data, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Processing complete. Results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
