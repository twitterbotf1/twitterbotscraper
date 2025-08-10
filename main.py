# filename: main.py

import requests
from bs4 import BeautifulSoup
import os
import time
from urllib.parse import urlparse, urljoin
from supabase import create_client, Client
from playwright.sync_api import sync_playwright

# --- HEADERS, SITE RULES & PLAYWRIGHT SITES (Unchanged) ---
HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'keep-alive' }
SITE_RULES = {
    'formula1.com': { 'allowed_paths': ['/latest/article/'], 'disallowed_paths': ['/tags/'] },
    'motorsport.com': { 'allowed_paths': ['/f1/news/'], 'disallowed_paths': ['/videos/', '/galleries/', '/info/'] },
    'it.motorsport.com': { 'allowed_paths': ['/f1/news/'], 'disallowed_paths': ['/videos/', '/galleries/', '/info/', '/live-text/'] },
    'autosport.com': { 'allowed_paths': ['/f1/news/'], 'disallowed_paths': ['/videos/', '/galleries/', '/info/'] },
    'bbc.co.uk': { 'allowed_paths': ['/sport/formula1/'], 'disallowed_paths': ['/calendar', '/latest', '/results', '/standings', '/videos'] },
    'the-race.com': { 'allowed_paths': ['/formula-1/'], 'disallowed_paths': ['/category/'] },
    'planetf1.com': { 'allowed_paths': ['/news/', '/features/'], 'disallowed_paths': ['/tag/', '/team/', '/driver/', '/author/'] },
    'racefans.net': { 'allowed_paths': ['/2024/', '/2025/'], 'disallowed_paths': ['/calendar/'] },
    'f1technical.net': { 'allowed_paths': ['/news/', '/features/'], 'disallowed_paths': ['/forum/'] },
    'grandprix.com': { 'allowed_paths': ['/news/'], 'disallowed_paths': [] },
    'racingnews365.com': { 'allowed_paths': ['-'], 'disallowed_paths': ['/video', '/podcast', 'grand-prix', '/formula-1-', '/f1-news', 'live-timing', 'editorial-team-and-staff', 'privacy-policy', 'terms-and-conditions', 'service-and-contact', 'disclaimer'], 'min_hyphens': 3 },
    'skysports.com': { 'allowed_paths': ['/f1/news/'], 'disallowed_paths': ['/f1/video/'] },
    'f1oversteer.com': { 'allowed_paths': ['/news/'], 'disallowed_paths': ['/page/', '/tag/'] },
    'gazzetta.it': { 'allowed_paths': ['/Formula-1/', '/motori/ferrari/'], 'disallowed_paths': ['/pagina-', '/classifiche', '/calendario-risultati', '/piloti', '/scuderie'] },
    'autosprint.it': { 'allowed_paths': ['/news/formula1/'], 'disallowed_paths': ['/foto/', '/video/', '/widget/', '/live/', '/in-diretta/'] }
}
PLAYWRIGHT_SITES = ['f1oversteer.com', 'racefans.net', 'bbc.co.uk', 'formula1.com']

# --- DATABASE & FILE HANDLING ---
def init_connection() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    return create_client(url, key)

def get_sources_from_db(supabase: Client) -> list[str]:
    try:
        res = supabase.table('sources').select('url').order('id', desc=True).execute()
        sources = [item['url'] for item in res.data]
        print(f"✅ Found {len(sources)} sources in the Supabase 'sources' table.")
        return sources
    except Exception as e:
        print(f"🔴 ERROR: Could not fetch sources from Supabase. Reason: {e}")
        return []

def read_links_from_file(filename="raw-urls.txt") -> set:
    if not os.path.exists(filename):
        open(filename, "w").close()
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def save_links_to_file(links: set, filename="raw-urls.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(links))))

def save_new_links(links: set, filename="new-urls.txt"):
    print(f"Writing {len(links)} new links to '{filename}'...")
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(links))))

# --- URL VALIDATION & SCRAPING ---
def clean_url(url: str, base_url: str) -> str:
    full_url = urljoin(base_url, url)
    parsed = urlparse(full_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

def is_valid_article_link_by_rule(url: str, domain: str, rule: dict) -> bool:
    parsed_url = urlparse(url)
    if domain not in parsed_url.netloc: return False
    allowed, disallowed = rule.get('allowed_paths', []), rule.get('disallowed_paths', [])
    min_hyphens = rule.get('min_hyphens')
    if not any(a in parsed_url.path for a in allowed): return False
    if any(d in parsed_url.path for d in disallowed): return False
    if min_hyphens is not None and parsed_url.path.count('-') < min_hyphens: return False
    return True

def get_html_with_playwright(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS['User-Agent'])
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_selector("body", timeout=15000)
            time.sleep(3)
            html_content = page.content()
            browser.close()
            return html_content
    except Exception as e:
        print(f"🔴 ERROR: Playwright failed for {url}. Reason: {e}")
        return ""

def scrape_and_filter_links(sources_to_scrape: list[str]) -> set:
    session = requests.Session()
    session.headers.update(HEADERS)
    live_links = set()
    
    for i, source_url in enumerate(sources_to_scrape):
        domain = urlparse(source_url).netloc.replace('www.', '')
        print(f"\n[{i+1}/{len(sources_to_scrape)}] Scraping: {domain}...")
        html_content = None
        try:
            if any(site in domain for site in PLAYWRIGHT_SITES):
                print("...using Playwright (dynamic content)")
                html_content = get_html_with_playwright(source_url)
            else:
                print("...using Requests (static content)")
                response = session.get(source_url, timeout=15)
                response.raise_for_status()
                html_content = response.content
            
            if not html_content: continue

            soup = BeautifulSoup(html_content, 'lxml')
            base_url = f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}"
            found_links = {clean_url(a['href'], base_url) for a in soup.find_all('a', href=True)}
            
            rule = SITE_RULES.get(domain)
            if not rule: continue
                
            valid_for_domain = {link for link in found_links if is_valid_article_link_by_rule(link, domain, rule)}
            print(f"    -> Found {len(valid_for_domain)} valid articles for {domain}.")
            live_links.update(valid_for_domain)

        except requests.RequestException as e:
            print(f"🔴 ERROR: Could not fetch {source_url}. Reason: {e}")
            
    return live_links

# --- MAIN EXECUTION ---
def main():
    print("--- Starting Scraper Script (main.py) ---")
    supabase = init_connection()
    if not supabase: sys.exit(1)

    sources = get_sources_from_db(supabase)
    if not sources:
        print("No sources found. Exiting.")
        return

    live_links = scrape_and_filter_links(sources)
    old_links = read_links_from_file()
    new_links = live_links - old_links

    if not new_links:
        print("\n✅ No new links found.")
    else:
        print(f"\n✅ Found {len(new_links)} new links.")
        save_new_links(new_links)

    save_links_to_file(live_links)
    print(f"Updated 'raw-urls.txt' with {len(live_links)} total links.")
    print("--- Scraper Finished ---")

if __name__ == "__main__":
    main()
