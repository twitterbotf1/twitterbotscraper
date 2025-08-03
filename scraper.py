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

SITE_RULES = {
    'formula1.com': {'allowed_paths': ['/latest/article/'], 'disallowed_paths': ['/tags/']},
    'motorsport.com': {'allowed_paths': ['/news/'], 'disallowed_paths': ['/videos/', '/galleries/', '/info/'], 'path_must_end_with_number': True},
    'autosport.com': {'allowed_paths': ['/news/'], 'disallowed_paths': ['/videos/', '/galleries/', '/info/'], 'path_must_end_with_number': True},
    'bbc.co.uk': {'allowed_paths': ['/articles/'], 'disallowed_paths': []},
    'the-race.com': {'allowed_paths': ['/formula-1/'], 'disallowed_paths': ['/category/', '/news/']},
    'planetf1.com': {'allowed_paths': ['/news/', '/features/'], 'disallowed_paths': ['/tag/', '/team/', '/driver/', '/author/']},
    'racefans.net': {'allowed_paths': ['/2024/', '/2025/'], 'disallowed_paths': ['/calendar/']},
    'f1technical.net': {'allowed_paths': ['/news/', '/features/', '/articles/', '/development/'], 'disallowed_paths': ['/forum/', '/gallery/']},
    'grandprix.com': {'allowed_paths': ['/news/', '/races/'], 'disallowed_paths': [], 'path_must_end_with_html': True},
    'racingnews365.com': {'allowed_paths': ['/'], 'disallowed_paths': ['/drivers', '/teams', '/circuits', '/video', '/register', '/interview', '/podcast']},
    'skysports.com': {'allowed_paths': ['/f1/news/'], 'disallowed_paths': ['/f1/video/', '/f1/live-blog/']},
    'it.motorsport.com': {'allowed_paths': ['/news/'], 'disallowed_paths': ['/videos/', '/galleries/', '/info/'], 'path_must_end_with_number': True},
    'gazzetta.it': {'allowed_paths': ['/'], 'disallowed_paths': [], 'path_must_end_with_html': True},
    'autosprint.corrieredellosport.it': {'allowed_paths': ['/news/', '/foto/'], 'disallowed_paths': ['/live/']},
    'f1oversteer.com': {'allowed_paths': ['/news/'], 'disallowed_paths': ['/page/', '/tag/']}
}

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    print("Supabase credentials not set.")
    exit(1)

supabase = create_client(url, key)

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
    if not any(a in parsed_url.path for a in rule.get('allowed_paths', [])): return False
    if any(d in parsed_url.path for d in rule.get('disallowed_paths', [])): return False
    segs = [s for s in parsed_url.path.split('/') if s]
    if rule.get('path_must_end_with_number') and (not segs or not segs[-1].isdigit()): return False
    if rule.get('path_must_end_with_html') and not parsed_url.path.endswith(('.html', '.shtml')): return False
    return True

def scrape_live_links(sources):
    live = set()
    s = requests.Session(); s.headers.update(HEADERS)
    for src in sources:
        dom = urlparse(src).netloc.replace('www.', '')
        rule = SITE_RULES.get(dom)
        try:
            r = s.get(src, timeout=15); r.raise_for_status()
            soup = BeautifulSoup(r.content, 'html.parser')
            base = f"{urlparse(src).scheme}://{urlparse(src).netloc}"
            links = {clean_url(a['href'], base) for a in soup.find_all('a', href=True)}
            for l in links:
                if rule and is_valid_article_link_by_rule(l, dom, rule): live.add(l)
                elif not rule and urlparse(l).path and len(urlparse(l).path) > 15: live.add(l)
        except Exception as e:
            print(f"Failed {src}: {e}")
    return live

def read_links_from_file(f="raw-urls.txt"):
    if not os.path.exists(f):
        open(f, "w").close()
        return set()
    try:
        with open(f, "r", encoding="utf-8") as x:
            return {i.strip() for i in x if i.strip()}
    except Exception as e:
        print(f"Read error {f}: {e}")
        return set()

def add_links_to_db(links):
    if not links: return 0
    try:
        data = [{"url": u, "bot": "formula"} for u in links]
        res = supabase.table('to_process').insert(data).execute()
        return len(res.data)
    except Exception as e:
        print(f"Insert error: {e}")
        return 0

def save_links_to_file(links, f="raw-urls.txt"):
    try:
        with open(f, "w", encoding="utf-8") as x:
            x.write("\\n".join(sorted(list(links))))
    except Exception as e:
        print(f"Save error {f}: {e}")

def main():
    sources = get_sources_from_db()
    if not sources:
        print("No sources.")
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
