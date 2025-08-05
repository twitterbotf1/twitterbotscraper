# Save this as main.py
import requests
from bs4 import BeautifulSoup
import os
import time
from urllib.parse import urlparse, urljoin
from supabase import create_client, Client
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, timedelta
import pytz

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
    if "SUPABASE_URL" not in os.environ or "SUPABASE_KEY" not in os.environ:
        print("🔴 ERROR: Supabase credentials not set in environment variables.")
        return None
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    return create_client(url, key)

def get_sources_from_db(supabase: Client) -> list[str]:
    """Fetches the list of source URLs from the 'sources' table in Supabase."""
    try:
        res = supabase.table('sources').select('url').order('id', desc=True).execute()
        sources = [item['url'] for item in res.data]
        print(f"✅ Found {len(sources)} sources in the Supabase 'sources' table.")
        return sources
    except Exception as e:
        print(f"🔴 ERROR: Could not fetch sources from Supabase. Reason: {e}")
        return []

def read_links_from_file(filename="processed-urls.txt") -> set:
    if not os.path.exists(filename):
        print(f"🟡 WARNING: Processed URLs file '{filename}' not found. Creating it.")
        open(filename, "w").close()
        return set()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"🔴 ERROR: Could not read from {filename}. Reason: {e}")
        return set()

def save_links_to_file(links: set, filename="processed-urls.txt"):
    print(f"\n--- Updating {filename} with {len(links)} links for the next run ---")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(list(links))))
        print("✅ Save complete.")
    except Exception as e:
        print(f"🔴 ERROR: Could not save to {filename}. Reason: {e}")

# --- NEW: TIMESTAMP ASSIGNMENT FUNCTION ---
def assign_timestamps(links: set) -> list:
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    count = len(links)
    step = timedelta(hours=3) / (count - 1) if count > 1 else timedelta(hours=0)
    assigned = []
    for i, url in enumerate(sorted(list(links))):
        timestamp = (now + i * step).isoformat()
        assigned.append({"url": url, "bot": "formula", "time": timestamp})
    return assigned

# --- URL VALIDATION & SCRAPING (Unchanged) ---
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

def scrape_live_links(sources_to_scrape: list[str]) -> dict:
    categorized_urls = {urlparse(s).netloc.replace('www.', ''): set() for s in sources_to_scrape}
    session = requests.Session()
    session.headers.update(HEADERS)
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
            if not html_content:
                print(f"🟡 WARNING: No HTML content found for {source_url}.")
                continue
            soup = BeautifulSoup(html_content, 'html.parser')
            base_url = f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}"
            found_links = {clean_url(a['href'], base_url) for a in soup.find_all('a', href=True)}
            categorized_urls[domain].update(found_links)
            print(f"    -> Found {len(found_links)} total links.")
        except requests.RequestException as e:
            print(f"🔴 ERROR: Could not fetch {source_url}. Reason: {e}")
    return categorized_urls

# --- MAIN EXECUTION (UPDATED) ---
def main():
    print("--- Starting Scraper ---")
    supabase = init_connection()
    if not supabase: return

    sources = get_sources_from_db(supabase)
    if not sources: return

    scraped_links_by_domain = scrape_live_links(sources)
    
    print("\n--- Filtering and Validating Links ---")
    all_valid_links = set()
    for domain, links in scraped_links_by_domain.items():
        rule = SITE_RULES.get(domain)
        if not rule:
            print(f"🟡 WARNING: No rule found for '{domain}'. Skipping.")
            continue
        valid_for_domain = {link for link in links if is_valid_article_link_by_rule(link, domain, rule)}
        print(f"✅ Found {len(valid_for_domain)} valid articles for {domain}.")
        all_valid_links.update(valid_for_domain)

    # Use file-based duplicate checking
    processed_links = read_links_from_file()
    new_links_to_add = all_valid_links - processed_links
    
    if not new_links_to_add:
        print("\n✅ No new articles to add. All found links have been processed before.")
    else:
        print(f"\n--- Found {len(new_links_to_add)} New Articles ---")
        # Assign timestamps and write to the 'to_process' table
        data_to_insert = assign_timestamps(new_links_to_add)
        print(f"--- Writing {len(data_to_insert)} new articles with timestamps to Supabase ---")
        try:
            supabase.table('to_process').insert(data_to_insert).execute()
            print("✅ Successfully wrote new articles to the database.")
        except Exception as e:
            print(f"🔴 ERROR: Failed to write to Supabase. Reason: {e}")

    # Update the file with all links found in this run for the next execution
    save_links_to_file(processed_links.union(all_valid_links))
    print("--- Scraper Finished ---")

if __name__ == "__main__":
    main()
