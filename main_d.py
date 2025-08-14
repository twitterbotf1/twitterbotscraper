# filename: main_d.py

import os
import sys
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36' }

def init_connection() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("🔴 ERROR: Supabase credentials not set.")
        return None
    return create_client(url, key)

def read_new_links_from_file(filename="new-urls.txt") -> set:
    if not os.path.exists(filename):
        print("🟡 No 'new-urls.txt' file found. Nothing to process.")
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def get_og_title(url: str, session: requests.Session) -> str | None:
    """Fetches the Open Graph title from a URL."""
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        og_title_tag = soup.find('meta', property='og:title')
        if og_title_tag and og_title_tag.get('content'):
            return og_title_tag['content'].strip()
        print(f"🟡 WARNING: No og:title found for {url}")
        return None
    except requests.RequestException as e:
        print(f"🔴 ERROR: Could not fetch {url}. Reason: {e}")
        return None

def process_urls(urls: set) -> list:
    """
    Processes a set of URLs to extract titles and format them.
    Returns a list of dictionaries with valid, processed data.
    """
    processed_data = []
    session = requests.Session()
    session.headers.update(HEADERS)
    
    for url in urls:
        title = get_og_title(url, session)
        if title:
            publication = urlparse(url).netloc.replace('www.', '')
            formatted_title = f'"{title}" -{publication}'
            processed_data.append({'url': url, 'title': formatted_title})
        else:
            # URL is discarded if title can't be extracted
            print(f"Discarding URL due to missing title: {url}")
            
    return processed_data

def assign_timestamps_and_bot(processed_data: list) -> list:
    """Assigns timestamps and bot name to the processed data."""
    if not processed_data:
        return []
    
    utc = pytz.utc
    now = datetime.now(utc)
    
    count = len(processed_data)
    step = timedelta(hours=3) / (count - 1) if count > 1 else timedelta(hours=0)
    
    random.shuffle(processed_data)
    
    final_payload = []
    for i, item in enumerate(processed_data):
        timestamp_dt = now + i * step
        
        # Set time to ISO 8601 format
        item['time'] = timestamp_dt.isoformat()
        item['bot'] = 'formula'
        final_payload.append(item)
        
    return final_payload

def add_links_to_db(supabase: Client, payload: list) -> int:
    """Adds the final payload to the 'to_process' table."""
    if not payload:
        return 0
    try:
        res = supabase.table('to_process').insert(payload).execute()
        return len(res.data)
    except Exception as e:
        print(f"🔴 DATABASE INSERT ERROR: {e}")
        return 0

def main():
    print("--- Starting Processor Script (main_d.py) ---")
    
    new_urls = read_new_links_from_file()
    if not new_urls:
        print("--- Processor Finished: Nothing to do. ---")
        return

    processed_data = process_urls(new_urls)
    
    if not processed_data:
        print("--- Processor Finished: No URLs had valid titles. ---")
        return

    final_payload = assign_timestamps_and_bot(processed_data)
    
    supabase = init_connection()
    if not supabase:
        sys.exit(1)

    added_count = add_links_to_db(supabase, final_payload)
    print(f"✅ Successfully added {added_count} of {len(new_urls)} links to the database.")

    print("--- Processor Finished ---")

if __name__ == "__main__":
    main()
