import json
import os
from bs4 import BeautifulSoup
from readability import Document
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "new-urls.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "final_articles.json")

def extract_data(html):
    soup = BeautifulSoup(html, 'lxml')
    
    # 1. Attempt to find og:image
    hero_image = None
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        hero_image = og_img['content']
        
    # 2. Extract main article HTML and title using readability
    try:
        doc = Document(html)
        title = doc.title()
        article_html = doc.summary()
    except Exception:
        return None, None, None
    
    article_soup = BeautifulSoup(article_html, 'lxml')
    
    # 3. Fallback to first image in article body if og:image is missing
    if not hero_image:
        img_tag = article_soup.find('img')
        if img_tag and img_tag.get('src'):
            hero_image = img_tag['src']
            
    # 4. Clean text extraction
    content = article_soup.get_text(separator='\n', strip=True)
    
    return title, hero_image, content

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file not found: {INPUT_FILE}")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    final_data =[]
    success_count = 0
    failure_count = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        for item in data:
            url = item.get("url")
            try:
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000) # Allow JS to load dynamic content
                html = page.content()
                
                title, hero_image, content = extract_data(html)
                
                # Check content length (Updated to 500 as per your request)
                if content and len(content) > 500:
                    final_data.append({
                        "id": item["id"],
                        "domain": item.get("domain"), # Preserving the domain
                        "title": title,
                        "hero_image": hero_image,
                        "content": content
                    })
                    success_count += 1
                    print(f"[SUCCESS] {url}")
                else:
                    failure_count += 1
                    print(f"[FAILED] Content too short or missing: {url}")
                    
            except Exception as e:
                failure_count += 1
                print(f"[FAILED] Error processing {url}: {e}")

        browser.close()
            
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
        
    print(f"\nTotal Success: {success_count}")
    print(f"Total Failure: {failure_count}")

if __name__ == "__main__":
    main()
