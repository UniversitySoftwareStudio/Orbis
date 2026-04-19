import requests
from bs4 import BeautifulSoup
import json
import time
import random
import concurrent.futures
import threading
import logging
import re
import os
import signal
import sys
from urllib.parse import urljoin, urlparse
from datetime import datetime

# --- CONFIGURATION ---
START_URLS = ["https://www.bilgi.edu.tr/tr/", "https://www.bilgi.edu.tr/en/"]
ALLOWED_DOMAIN = "www.bilgi.edu.tr"
DATA_FILE = "bilgi_university_data.jsonl"
STATE_FILE = "mainscraper_v4_visited_urls.txt"
LOG_FILE = "mainscraper_v4.log"

MAX_THREADS = 10
REQUEST_DELAY = (0.2, 0.5)

# --- LOGGING SETUP (Force Flush) ---
# We create a handler that flushes to disk immediately
file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
file_handler.flush = lambda: file_handler.stream.flush() # Monkey-patch to ensure flush works
console_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

# --- GLOBAL STATE ---
visited_urls = set()
url_lock = threading.Lock()
file_lock = threading.Lock()
shutdown_event = threading.Event() # For graceful exit

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- GRACEFUL EXIT HANDLER ---
def signal_handler(sig, frame):
    print("\n[!] Ctrl+C Detected! Stopping threads safely... (Please wait)")
    shutdown_event.set()
    # logging.shutdown() # Close logs cleanly
    # sys.exit(0) # We let the main loop break instead of forcing exit

signal.signal(signal.SIGINT, signal_handler)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                visited_urls.add(line.strip())
        logging.info(f"Resumed: {len(visited_urls)} URLs loaded.")

def mark_visited(url):
    with url_lock:
        visited_urls.add(url)
        with open(STATE_FILE, 'a', encoding='utf-8') as f:
            f.write(url + '\n')

def is_valid_url(url):
    parsed = urlparse(url)
    if parsed.netloc != ALLOWED_DOMAIN: return False
    
    path = parsed.path.lower()
    if any(x in path for x in ['/media/', '/static/', '/uploads/', '/files/', '/images/', 'wp-content', 'search', 'filtre']):
        return False
    if any(path.endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip', '.pptx', '.docx', '.css', '.js', '.xml', '.mp4']):
        return False
    return True

def find_years_in_text(text):
    matches = re.findall(r'\b(201[5-9]|202[0-9])\b', text)
    return sorted(list(set(matches)), reverse=True)

def find_date_in_text(text):
    patterns = [
        r"(\d{1,2}\s+[A-Za-zçğıöşüÇĞİÖŞÜ]{3,}\s+20\d{2})", 
        r"(\d{1,2}[./-]\d{1,2}[./-]20\d{2})"                
    ]
    header_text = text[:1000] 
    for p in patterns:
        match = re.search(p, header_text)
        if match: return match.group(0)
    return None

def parse_page(url, session):
    if shutdown_event.is_set(): return [] # Stop if Ctrl+C was pressed

    try:
        # 1. HEAD REQUEST
        try:
            head_resp = session.head(url, headers=HEADERS, timeout=5, allow_redirects=True)
            if 'text/html' not in head_resp.headers.get('Content-Type', ''):
                return []
        except:
            pass

        # 2. GET REQUEST
        time.sleep(random.uniform(*REQUEST_DELAY))
        response = session.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200: return []

        soup = BeautifulSoup(response.content, 'html.parser')
        new_links = []

        # 3. HARVEST LINKS
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].split('#')[0].split('?')[0]
            full_link = urljoin(url, href)
            if is_valid_url(full_link):
                new_links.append(full_link)

        # 4. SAVE CONTENT
        is_homepage = "is-homepage" in soup.body.get('class', [])
        if not is_homepage:
            data = extract_page_data(soup, url)
            if data:
                save_data(data)
                # Force flush log entry to disk immediately
                logging.info(f"[SAVED] {url}")
                for handler in logging.getLogger().handlers:
                    handler.flush()

        return new_links

    except Exception as e:
        logging.error(f"Error {url}: {e}")
        return []

def extract_page_data(soup, url):
    title = soup.find('h1')
    title_text = title.get_text(strip=True) if title else (soup.title.get_text(strip=True) if soup.title else "No Title")

    content_area = soup.find('body')
    if not content_area: return None
    
    for tag in content_area.select('nav, footer, .site-header, .sidebar, .widget, script, style, .cookie-warning, .modal'):
        tag.decompose()
        
    main_text = content_area.get_text(separator='\n', strip=True)
    if len(main_text) < 100: return None 

    breadcrumbs = []
    bc_div = soup.find(class_='breadcrumb')
    if bc_div:
        breadcrumbs = [li.get_text(strip=True) for li in bc_div.find_all('li')]

    detected_date = find_date_in_text(main_text)
    mentioned_years = find_years_in_text(main_text)
    scraped_at = datetime.now().isoformat()

    meta_str = f"Source: {title_text}. "
    if detected_date: meta_str += f"Date: {detected_date}. "
    if mentioned_years: meta_str += f"Years Mentioned: {', '.join(mentioned_years)}. "
    
    enriched_content = f"{meta_str}\n\n{main_text}"

    return {
        "url": url,
        "language": "tr" if "/tr/" in url else "en",
        "title": title_text,
        "content": enriched_content, 
        "scraped_at": scraped_at,
        "detected_date": detected_date, 
        "mentioned_years": mentioned_years, 
        "type": "web_page",
        "metadata": {
            "breadcrumbs": breadcrumbs,
            "source_domain": "bilgi.edu.tr"
        }
    }

def save_data(data):
    with file_lock:
        with open(DATA_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

def crawl_bfs():
    load_state()
    queue = []
    for start_url in START_URLS:
        if start_url not in visited_urls:
            queue.append(start_url)
    
    if not queue: queue = START_URLS.copy()

    with requests.Session() as session:
        while queue and not shutdown_event.is_set():
            current_batch = []
            with url_lock:
                while queue and len(current_batch) < MAX_THREADS:
                    url = queue.pop(0)
                    if url not in visited_urls:
                        visited_urls.add(url) 
                        with open(STATE_FILE, 'a', encoding='utf-8') as f:
                            f.write(url + '\n')
                        current_batch.append(url)
            
            if not current_batch: break

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                future_to_url = {executor.submit(parse_page, url, session): url for url in current_batch}
                for future in concurrent.futures.as_completed(future_to_url):
                    links = future.result()
                    if links:
                        for link in links:
                            if link not in visited_urls:
                                queue.append(link)
            
            print(f"Queue: {len(queue)} | Processed: {len(visited_urls)}")

    print("Scraper stopped.")

if __name__ == "__main__":
    crawl_bfs()