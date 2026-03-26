# filename: /workspaces/twitterbotscraper/code/step1.py
import os, time, json, hashlib, requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright

# --- PORTABLE CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(BASE_DIR, "sources.txt")
RAW_URLS_PATH = os.path.join(BASE_DIR, "raw-urls.txt")
NEW_URLS_JSON = os.path.join(BASE_DIR, "new-urls.json")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}

# --- RESTORED RULES ---
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
    'racingnews365.com': { 'allowed_paths': ['-'], 'disallowed_paths': ['/video', '/podcast', 'grand-prix'], 'min_hyphens': 3 },
    'skysports.com': { 'allowed_paths': ['/f1/news/'], 'disallowed_paths': ['/f1/video/'] },
    'f1oversteer.com': { 'allowed_paths': ['/news/'], 'disallowed_paths': ['/page/', '/tag/'] },
    'gazzetta.it': { 'allowed_paths': ['/Formula-1/', '/motori/ferrari/'], 'disallowed_paths': ['/pagina-', '/classifiche'] },
    'autosprint.it': { 'allowed_paths': ['/news/formula1/'], 'disallowed_paths': ['/foto/', '/video/'] }
}
PLAYWRIGHT_SITES = ['f1oversteer.com', 'racefans.net', 'bbc.co.uk', 'formula1.com']

def generate_id(url): return hashlib.md5(url.encode()).hexdigest()[:8]

def is_valid(url, domain, rule):
    parsed = urlparse(url)
    if domain not in parsed.netloc: return False
    allowed, disallowed = rule.get('allowed_paths', []), rule.get('disallowed_paths', [])
    if not any(a in parsed.path for a in allowed): return False
    if any(d in parsed.path for d in disallowed): return False
    if rule.get('min_hyphens') and parsed.path.count('-') < rule['min_hyphens']: return False
    return True

def get_html(url, domain):
    if any(s in domain for s in PLAYWRIGHT_SITES):
        try:
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                pg = b.new_page(user_agent=HEADERS['User-Agent'])
                pg.goto(url, timeout=30000, wait_until='domcontentloaded')
                time.sleep(2)
                h = pg.content()
                b.close()
                return h
        except: return None
    try: return requests.get(url, headers=HEADERS, timeout=15).content
    except: return None

def main():
    if not os.path.exists(SOURCES_PATH): return
    with open(SOURCES_PATH, "r") as f: sources = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    
    history = set()
    if os.path.exists(RAW_URLS_PATH):
        with open(RAW_URLS_PATH, "r") as f: history = {l.strip() for l in f if l.strip()}

    new_items, all_urls = [], set(history)
    for src in sources:
        dom = urlparse(src).netloc.replace('www.', '')
        html = get_html(src, dom)
        if not html: continue
        
        soup = BeautifulSoup(html, 'lxml')
        base = f"{urlparse(src).scheme}://{urlparse(src).netloc}"
        
        # Extract all links
        raw_links = []
        for a in soup.find_all('a', href=True):
            full = urljoin(base, a['href']).split('?')[0].rstrip('/')
            if full not in raw_links: raw_links.append(full)
        
        rule = SITE_RULES.get(dom)
        if rule:
            # Filter and take top 5
            valid_links = [l for l in raw_links if is_valid(l, dom, rule)][:5]
            for l in valid_links:
                all_urls.add(l)
                if l not in history:
                    new_items.append({"id": generate_id(l), "url": l, "domain": dom})

    with open(NEW_URLS_JSON, "w") as f: json.dump(new_items, f, indent=4)
    with open(RAW_URLS_PATH, "w") as f: f.write("\n".join(sorted(list(all_urls))))
    print(f"✅ Found {len(new_items)} new articles.")

if __name__ == "__main__": main()