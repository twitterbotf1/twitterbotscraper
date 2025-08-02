import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse, urljoin
from supabase import create_client

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'text/html,application/xhtml+xml',
    'Connection': 'keep-alive'
}

SITE_RULES = { ... }  # keep same rules

# --- DATABASE CONNECTION ---
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    print("Supabase credentials not set.")
    exit(1)

supabase = create_client(url, key)

# --- FUNCTIONS ---
def get_sources_from_db():
    try:
        res = supabase.table('sources').select('url').order('id', desc=True).execute()
        return [item['url'] for item in res.data]
    except Exception as e:
        print(f"Error fetching sources: {e}")
        return []

def clean_url(url, base_url):
    full_url = urljoin(base_url, url)
    parsed = urlparse(full_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

def is_valid_article_link_by_rule(url, domain, rule):
    parsed_url = urlparse(url)
    if domain not in parsed_url.netloc: return False
    allowed = rule.get('allowed_paths', [])
    disallowed = rule.get('disallowed_paths', [])
    if not any(a in parsed_url.path for a in allowed): return False
    if any(d in parsed_url.path for d in disallowed): return False
    segments = [seg for seg in parsed_url.path.split('/') if seg]
    if rule.get('path_must_end_with_number') and (not segments or not segments[-1].isdigit()): return False
    if rule.get('path_must_end_with_html') and not parsed_url.path.endswith(('.html', '.shtml')): return False
    return True

def scrape_live_links(sources):
    live_urls = set()
    session = requests.Session()
    session.headers.update(HEADERS)
    for source_url in sources:
        domain = urlparse(source_url).netloc.replace('www.', '')
        rule = SITE_RULES.get(domain)
        try:
            r = session.get(source_url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, 'html.parser')
            base = f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}"
            links = {clean_url(a['href'], base) for a in soup.find_all('a', href=True)}
            for link in links:
                if rule and is_valid_article_link_by_rule(link, domain, rule):
                    live_urls.add(link)
                elif not rule and urlparse(link).path and len(urlparse(link).path) > 15:
                    live_urls.add(link)
        except Exception as e:
            print(f"Failed to fetch {source_url}: {e}")
    return live_urls

def read_links_from_file(fname="raw-urls.txt"):
    if not os.path.exists(fname):
        open(fname, "w").close()
        return set()
    try:
        with open(fname, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Read error {fname}: {e}")
        return set()

def add_links_to_db(links):
    if not links: return 0
    try:
        data = [{"url": u} for u in links]
        res = supabase.table('to_process').insert(data).execute()
        return len(res.data)
    except Exception as e:
        print(f"Insert error: {e}")
        return 0

def save_links_to_file(links, fname="raw-urls.txt"):
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(list(links))))
    except Exception as e:
        print(f"Save error {fname}: {e}")

# --- MAIN ---
def main():
    sources = get_sources_from_db()
    if not sources:
        print("No sources found.")
        return

    live = scrape_live_links(sources)
    old = read_links_from_file()
    new = live - old
    if not new:
        print("No new links.")
        return

    added = add_links_to_db(new)
    save_links_to_file(live)
    print(f"Added {added} new links.")

if __name__ == "__main__":
    main()
