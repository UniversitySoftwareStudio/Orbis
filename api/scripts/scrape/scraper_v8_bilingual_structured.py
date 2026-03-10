import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import concurrent.futures
import os
from datetime import datetime

# --- CONFIGURATION ---
BASE_URL = "https://ects.bilgi.edu.tr"
OUTPUT_FILE = "scraped_courses_2025-2026.jsonl"
SEARCH_QUERY = "" 
TARGET_TOTAL = None 

# --- SYSTEM SETTINGS ---
MAX_WORKERS = 10 
PAGE_BATCH_SIZE = 10 
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

# Globals
CURRENT_COOKIES = {}
CURRENT_LANG = "EN"
SEARCH_URL_TEMPLATE = "https://ects.bilgi.edu.tr/Course?Page={}&ContextId=95&q=" + SEARCH_QUERY + "&CycleNo=-1&FacultyId=-1&DepartmentId=-1&OfferStyleId=-1&IsDetailSearch=True&OpenToUndergraduate=False"

def setup_language_session(lang_code):
    culture_param = "tr" if lang_code == "TR" else "en-US"
    url = f"{BASE_URL}/Home/SetCulture?culture={culture_param}&returnurl={BASE_URL}"
    print(f"   [Setup] Switching Context to {lang_code} ({culture_param})...")
    try:
        with requests.Session() as s:
            s.headers.update(HEADERS)
            r = s.get(url, timeout=10)
            if r.status_code == 200:
                return s.cookies.get_dict()
    except Exception as e:
        print(f"   [!] Error setting language: {e}")
    return {}

def get_soup(session, url):
    try:
        response = session.get(url, timeout=20)
        if response.status_code in [403, 429]: return None 
        return BeautifulSoup(response.content, 'html.parser')
    except: return None

def clean_text(text):
    return " ".join(text.split()) if text else ""

def slugify(text):
    if not text: return "unknown_field"
    text = clean_text(text).lower()
    text = re.sub(r'[^a-z0-9\s_]', '', text) 
    return re.sub(r'\s+', '_', text)

def get_existing_count_for_lang(target_lang):
    if not os.path.exists(OUTPUT_FILE): return 0
    count = 0
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get('language') == target_lang.lower():
                    count += 1
            except: pass
    return count

def fetch_page_items(page_num):
    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.cookies.update(CURRENT_COOKIES)
        soup = get_soup(session, SEARCH_URL_TEMPLATE.format(page_num))
        if not soup: return []
        items = []
        for p in soup.find_all('div', class_='panel-default'):
            try:
                header = p.find('div', class_='panel-heading')
                if not header: continue
                title_link = header.find('a', href=True)
                if not title_link: continue
                relative_url = title_link['href']
                full_text = clean_text(header.text)
                course_code = "UNKNOWN"
                course_title = "UNKNOWN"
                if "|" in full_text:
                    parts = full_text.split("|", 1)
                    course_code = clean_text(parts[0])
                    course_title = clean_text(parts[1])
                body = p.find('div', class_='panel-body')
                department = None
                if body:
                    body_text = clean_text(body.get_text())
                    dept_match = re.search(r'(Department|Bölüm)\s*:\s*([^:]+?)(Ders|Course|$)', body_text)
                    if dept_match:
                        department = dept_match.group(2).split("Course")[0].split("Ders")[0].strip()
                items.append({
                    "url": BASE_URL + relative_url,
                    "code": course_code,
                    "title": course_title,
                    "department": department
                })
            except: continue
        return items

def parse_course_detail(context_data):
    url = context_data['url']
    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.cookies.update(CURRENT_COOKIES)
        soup = get_soup(session, url)
        if not soup: return None

        # --- UPDATED SCHEMA ---
        # Removed 'faculty' and 'prerequisites_raw'
        record = {
            "url": url,
            "language": CURRENT_LANG.lower(),
            "title": context_data['title'],
            "content": "",
            "detected_date": None,
            "scraped_at": datetime.now().isoformat(),
            "type": "course",
            "metadata": {
                "course_code": context_data['code'],
                "department": context_data['department'],
                "weekly_topics": []
            }
        }

        # 1. Dynamic Table
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) == 2:
                key = clean_text(cols[0].text)
                val = clean_text(cols[1].text)
                if key and val:
                    slug = slugify(key)
                    
                    # Logic: Description -> 'content'
                    if slug in ['course_description', 'dersin_tanimi']:
                        record['content'] = val
                    # Logic: Academic Year -> 'detected_date'
                    elif slug in ['academic_year', 'akademik_yil', 'academicyear']:
                        record['detected_date'] = val
                        # Also keep it in metadata
                        record['metadata'][slug] = val
                    # Logic: Everything else -> metadata
                    # This now includes 'prerequisites_and_corequisites' naturally
                    else:
                        record['metadata'][slug] = val

        # 2. Header Table
        for tbl in soup.find_all('table', class_='table-responsive'):
            headers = [clean_text(h.text) for h in tbl.find_all('th')]
            tbody = tbl.find('tbody')
            if tbody and tbody.find('tr'):
                values = [clean_text(d.text) for d in tbody.find('tr').find_all('td')]
                for k, v in zip(headers, values):
                    if k and v:
                        slug = slugify(k)
                        if slug in ['academic_year', 'akademik_yil', 'academicyear']:
                            record['detected_date'] = v
                        record['metadata'][slug] = v

        # 3. Weekly Content
        header = soup.find('h3', string=re.compile("Ders İçeriği|Course Content", re.IGNORECASE))
        if header and header.find_next('table'):
            for row in header.find_next('table').find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 2:
                    topic = clean_text(cols[1].text)
                    if topic: record['metadata']['weekly_topics'].append(topic)

        # Fallback for Content
        if not record['content']:
            desc_label = soup.find('label', string=re.compile("Dersin Tanımı|Course Description", re.IGNORECASE))
            if desc_label:
                parent = desc_label.find_parent('td')
                if parent and parent.find_next_sibling('td'):
                    record['content'] = clean_text(parent.find_next_sibling('td').text)

        return record

def main():
    print(f"┌{'─'*60}┐")
    print(f"│  BILINGUAL RAG SCRAPER v17 (Clean Schema) {'│':>20}")
    print(f"└{'─'*60}┘")

    global CURRENT_COOKIES, CURRENT_LANG

    for lang in ["EN", "TR"]:
        CURRENT_LANG = lang
        CURRENT_COOKIES = setup_language_session(lang)
        
        print(f"\n{'='*65}")
        print(f" STARTING BATCH: {lang}")
        print(f"{'='*65}")

        existing_count = get_existing_count_for_lang(lang)
        print(f"   [Resume] Found {existing_count} {lang} records in file.")

        if TARGET_TOTAL and existing_count >= TARGET_TOTAL:
            print(f"   [Skip] Target for {lang} reached.")
            continue

        print(f"   [Phase 1] Searching for {lang} courses...")
        
        all_items = []
        page = 1
        stop = False
        last_page_items = [] # Infinite loop fix

        while not stop:
            batch = list(range(page, page + PAGE_BATCH_SIZE))
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=PAGE_BATCH_SIZE) as exc:
                future_to_page = {exc.submit(fetch_page_items, p): p for p in batch}
                for f in concurrent.futures.as_completed(future_to_page):
                    try: results[future_to_page[f]] = f.result()
                    except: results[future_to_page[f]] = []
            
            for p in batch:
                items = results.get(p, [])
                
                # Check 1: Empty Page
                if not items: 
                    stop = True
                    break
                
                # Check 2: Duplicate Content (Website returns last page infinitely)
                # We check if the first course code of this page matches the last page's first course
                if last_page_items and items[0]['code'] == last_page_items[0]['code']:
                    stop = True
                    break
                
                last_page_items = items
                all_items.extend(items)
            
            sys.stdout.write(f"\r   Found {len(all_items)} items... (Scanned up to Page {page + PAGE_BATCH_SIZE - 1})")
            sys.stdout.flush()
            page += PAGE_BATCH_SIZE

        print(f"\n   Total {lang} items found: {len(all_items)}")

        # Slice
        items_to_scrape = all_items[existing_count:]
        if TARGET_TOTAL:
            needed = TARGET_TOTAL - existing_count
            if needed < len(items_to_scrape): items_to_scrape = items_to_scrape[:needed]
        
        if not items_to_scrape:
            print(f"   No new {lang} items to scrape.")
            continue

        print(f"   [Phase 2] Scraping {len(items_to_scrape)} new items...")
        saved = existing_count
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exc:
            results = exc.map(parse_course_detail, items_to_scrape)
            for data in results:
                if data:
                    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    saved += 1
                    code_display = (data['metadata']['course_code'] + " " * 10)[:10]
                    sys.stdout.write(f"\r│ {lang} │ Total: {saved:<5} │ {code_display} ... ")
                    sys.stdout.flush()
        
        print(f"\n   [Done] Finished {lang} batch.")

    print(f"\n\n[ALL DONE] All languages processed.")

if __name__ == "__main__":
    main()