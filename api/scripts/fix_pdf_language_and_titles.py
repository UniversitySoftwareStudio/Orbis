import json
import os
import re
from urllib.parse import urlparse, unquote

# === PATH SETUP ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "api", "data")

FILES = [
    "bilgi_pdfs_important.jsonl",
    "bilgi_pdfs_irrelevant.jsonl",
    "bilgi_pdfs_resumes.jsonl",
]

def detect_language_v3(text, title=""):
    if not text: return 'en'
    
    combined_text = (text.lower() + " ") + (title.lower() + " ") * 3
    words = combined_text.split()
    
    en_stops = {'the', 'and', 'to', 'of', 'in', 'is', 'for', 'that', 'with', 'as', 'are', 'this', 'students', 'university', 'department', 'faculty', 'code', 'grade'}
    en_score = sum(1 for w in words if w in en_stops)
    
    tr_stops = {'ve', 'bir', 'bu', 'ile', 'için', 'olarak', 'daha', 'gibi', 'kadar', 'sonra', 'veya', 'olan', 'fakülte', 'bölüm', 'ders', 'kredi', 'not'}
    tr_chars = ['ı', 'ğ', 'ş', 'ü', 'ö', 'ç'] 
    
    tr_word_score = sum(1 for w in words if w in tr_stops)
    tr_char_score = sum(combined_text.count(c) for c in tr_chars)
    
    total_tr_score = tr_word_score + (tr_char_score * 0.8)

    if total_tr_score > (en_score * 1.2) and total_tr_score > 2:
        return 'tr'
    return 'en'

def generate_filename_title(url):
    """
    Extracts a clean title from the URL safely (OS Agnostic).
    """
    try:
        if not url: return ""
        
        # 1. Decode URL and strip trailing slashes
        url_clean = unquote(url).strip().rstrip('/')
        
        # 2. Get the last part of the URL (The filename)
        filename = url_clean.split('/')[-1]
        
        # 3. Remove extension manually (Case insensitive)
        if filename.lower().endswith(".pdf"):
            filename = filename[:-4]
            
        # 4. Clean formatting
        clean_name = filename.replace("-", " ").replace("_", " ").strip().title()
        
        # 5. Fallback check
        if not clean_name or len(clean_name) < 2:
            return ""
            
        return clean_name
    except:
        return ""

def clean_title(row):
    original_title = row.get('title', '')
    if original_title is None: original_title = ""
    title = original_title.strip()
    
    url = row.get('url', '')
    filename_clean = generate_filename_title(url)

    # --- RULE 0: Fix Empty Titles ---
    if not title:
        return filename_clean

    # --- RULE 1: Ban Generic Titles ---
    bad_titles = [
        "powerpoint presentation", "microsoft word", "adsız", "untitled", 
        "presentation", "sunu", "belge", "document"
    ]
    
    if any(bt == title.lower() for bt in bad_titles) or "microsoft word" in title.lower() or "powerpoint presentation" in title.lower():
        return filename_clean

    # --- RULE 2: Ban Excessive Length ---
    if len(title) > 200 or len(title.split()) > 25:
        return filename_clean

    # --- RULE 3: Remove Hash Codes (THE FIX) ---
    words = title.split()
    if len(words) > 1:  # <--- ONLY if there are multiple words
        last_word = words[-1]
        # Example: "Report 5V3Vrrc" -> "Report"
        # But "Binder2" -> "Binder2" (Safe)
        if len(last_word) > 4 and re.search(r'\d', last_word) and re.search(r'[a-zA-Z]', last_word):
            title = " ".join(words[:-1]) 
    
    # --- SAFETY NET ---
    # If we accidentally deleted everything (e.g. title was "1234ABCD"), fallback!
    if not title.strip():
        return filename_clean

    return title

def clean_text(text):
    if not text: return text
    return text.replace('\x00', '')

def run_fix():
    print(f"📂 Scanning files in: {DATA_DIR}")
    
    for filename in FILES:
        filepath = os.path.join(DATA_DIR, filename)
        temp_filepath = os.path.join(DATA_DIR, f"{filename}.tmp")
        
        if not os.path.exists(filepath):
            print(f"⚠️  File not found: {filename}")
            continue

        print(f"🔧 Repairing Metadata for: {filename}...")
        
        stats = {"tr": 0, "en": 0, "titles_fixed": 0}
        
        with open(filepath, 'r', encoding='utf-8') as infile, \
             open(temp_filepath, 'w', encoding='utf-8') as outfile:
            
            for line in infile:
                if not line.strip(): continue
                try:
                    row = json.loads(line)
                    
                    # 1. Sanitize Content
                    row['content'] = clean_text(row.get('content', ''))
                    original_title = clean_text(row.get('title', ''))
                    
                    # 2. Fix Main Title
                    new_title = clean_title(row)
                    row['title'] = new_title

                    # 3. SYNC METADATA TITLE
                    if 'metadata' in row and isinstance(row['metadata'], dict):
                        row['metadata']['title'] = new_title
                    
                    if new_title != original_title:
                        stats["titles_fixed"] += 1
                    
                    # 4. Language Detect
                    sample_text = row['content'][:3000] 
                    lang = detect_language_v3(sample_text, new_title)
                    row['language'] = lang
                    
                    stats[lang] += 1
                    
                    outfile.write(json.dumps(row, ensure_ascii=False) + "\n")
                    
                except json.JSONDecodeError: continue
        
        os.replace(temp_filepath, filepath)
        
        print(f"   ✅ Complete.")
        print(f"      - EN Docs: {stats['en']}")
        print(f"      - TR Docs: {stats['tr']}")
        print(f"      - Titles Repaired: {stats['titles_fixed']}")

    print("\n🎉 Metadata repair finished.")

if __name__ == "__main__":
    run_fix()