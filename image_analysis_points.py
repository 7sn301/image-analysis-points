# ============================================================
# المشهد التنفيذي - Executive Scene Analyzer
# النسخة: v6.4 | تحسينات الواجهة + دعم الوضع الليلي/النهاري
# ============================================================

import os
import re
import io
import json
import time
import random
import base64
import tempfile
import subprocess
import shutil
import requests
import streamlit as st
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from urllib.parse import urlparse, quote_plus

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ════════════════════════════════════════════════════════════
APP_NAME    = "المشهد التنفيذي"
APP_VERSION = "6.4"
APP_EMOJI   = "🎯"

GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]

OCR_LANG      = "ara+eng"
REQUEST_DELAY = 2
MAX_RETRIES   = 3

TWEET_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/[^/]+/status/\d+",
    re.IGNORECASE
)

# ════════════════════════════════════════════════════════════
def is_tweet_url(url: str) -> bool:
    return bool(TWEET_URL_PATTERN.match(url.strip()))

def extract_tweet_id(url: str) -> Optional[str]:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None

def extract_username_from_url(url: str) -> str:
    m = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/", url, re.IGNORECASE)
    return f"@{m.group(1)}" if m else ""

def normalize_tweet_url(url: str) -> str:
    url = re.sub(r"\?.*$", "", url.strip())
    url = re.sub(r"https?://(www\.)?x\.com/", "https://twitter.com/", url)
    return url

# ════════════════════════════════════════════════════════════
def exponential_backoff(attempt: int, base: float = 2.0, cap: float = 60.0) -> float:
    return min(base ** attempt + random.uniform(0, 1), cap)

def call_gemini_with_retry(model_name: str, prompt, status_fn=None) -> Optional[str]:
    if not GEMINI_AVAILABLE:
        return None
    for attempt in range(MAX_RETRIES):
        try:
            model  = genai.GenerativeModel(model_name)
            result = model.generate_content(prompt)
            return result.text
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "resource_exhausted" in err:
                wait = exponential_backoff(attempt)
                if status_fn:
                    status_fn(f"⏳ {model_name}: حد الطلبات – انتظر {wait:.0f}ث (محاولة {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            elif "404" in err or "not found" in err or "deprecated" in err:
                if status_fn:
                    status_fn(f"⚠️ {model_name}: غير متاح – جرّب التالي")
                return None
            else:
                if status_fn:
                    status_fn(f"❌ {model_name}: {str(e)[:80]}")
                return None
    if status_fn:
        status_fn(f"🚫 {model_name}: استُنفدت {MAX_RETRIES} محاولات")
    return None

def gemini_generate(prompt, api_key: str, status_fn=None) -> Tuple[Optional[str], Optional[str]]:
    if not GEMINI_AVAILABLE or not api_key:
        return None, None
    genai.configure(api_key=api_key)
    for model_name in GEMINI_MODELS:
        if status_fn:
            status_fn(f"🤖 جارٍ المحاولة: {model_name}")
        result = call_gemini_with_retry(model_name, prompt, status_fn)
        if result:
            return result, model_name
        time.sleep(REQUEST_DELAY)
    return None, None

# ════════════════════════════════════════════════════════════
def fetch_via_oembed(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "username": "", "images": [], "video_url": None, "is_retweet": False}
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={quote_plus(tweet_url)}&lang=ar&omit_script=true"
        resp = requests.get(oembed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            data = resp.json()
            result["author"] = data.get("author_name", "")
            html_content = data.get("html", "")
            if BS4_AVAILABLE and html_content:
                soup  = BeautifulSoup(html_content, "html.parser")
                texts = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
                result["text"]   = " ".join(texts)
                result["images"] = [img["src"] for img in soup.find_all("img") if img.get("src")]
            author_url = data.get("author_url", "")
            if author_url:
                m = re.search(r"twitter\.com/([^/?]+)", author_url, re.IGNORECASE)
                if m:
                    result["username"] = f"@{m.group(1)}"
    except Exception as e:
        result["error"] = str(e)
    return result

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.space",
]

def fetch_via_nitter(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "username": "", "images": [], "video_url": None, "is_retweet": False, "error": ""}
    tweet_id     = extract_tweet_id(tweet_url)
    username_raw = extract_username_from_url(tweet_url).lstrip("@")
    for mirror in NITTER_MIRRORS:
        try:
            nitter_url = f"{mirror}/{username_raw}/status/{tweet_id}"
            resp = requests.get(nitter_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                continue
            if not BS4_AVAILABLE:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            content_div = soup.find("div", class_="tweet-content")
            if content_div:
                result["text"] = content_div.get_text(separator=" ", strip=True)
            name_el  = soup.find("a", class_="fullname")
            uname_el = soup.find("a", class_="username")
            if name_el:  result["author"]   = name_el.get_text(strip=True)
            if uname_el: result["username"] = uname_el.get_text(strip=True)
            if soup.find("span", class_="retweet-header"):
                result["is_retweet"] = True
            for img in soup.find_all("img", class_="media-image"):
                src = img.get("src", "")
                if src:
                    result["images"].append(f"{mirror}{src}" if src.startswith("/") else src)
            video_el = soup.find("video")
            if video_el:
                result["video_url"] = video_el.get("src", "")
            if result["text"] or result["images"]:
                return result
        except Exception as e:
            result["error"] = str(e)
            continue
    return result

def download_media_yt_dlp(tweet_url: str, output_dir: str) -> Dict:
    result = {"images": [], "video_path": None, "error": ""}
    yt_dlp_path = shutil.which("yt-dlp")
    if not yt_dlp_path:
        result["error"] = "yt-dlp غير مثبّت"
        return result
    try:
        cmd = [
            yt_dlp_path, tweet_url,
            "--no-playlist", "--write-thumbnail", "--skip-download",
            "-o", os.path.join(output_dir, "%(id)s.%(ext)s"), "--quiet",
        ]
        subprocess.run(cmd, timeout=30, capture_output=True, check=False)
        for f in Path(output_dir).glob("*"):
            ext = f.suffix.lower()
            if ext in (".jpg", ".jpeg", ".png", ".webp"):
                result["images"].append(str(f))
            elif ext in (".mp4", ".webm", ".mkv"):
                result["video_path"] = str(f)
    except Exception as e:
        result["error"] = str(e)
    return result

def fetch_tweet_with_media(url: str, api_key: str, status_fn=None) -> Dict:
    tweet_data = {
        "text": "", "author": "", "username": "", "url_username": "",
        "images": [], "video_path": None, "video_url": None,
        "is_retweet": False, "tweet_id": "", "original_url": url,
    }
    tweet_data["url_username"] = extract_username_from_url(url)
    tweet_data["tweet_id"]     = extract_tweet_id(url) or ""
    normalized = normalize_tweet_url(url)

    if status_fn: status_fn("📡 الطبقة 1: oEmbed API...")
    oembed = fetch_via_oembed(normalized)
    if oembed.get("text"):
        tweet_data.update(oembed)
        if status_fn: status_fn("✅ oEmbed: تم جلب النص")
    else:
        if status_fn: status_fn("📡 الطبقة 2: Nitter mirrors...")
        nitter = fetch_via_nitter(normalized)
        if nitter.get("text") or nitter.get("images"):
            tweet_data.update(nitter)
            if status_fn: status_fn("✅ Nitter: تم جلب البيانات")
        else:
            if status_fn: status_fn("⚠️ Nitter فشل")

    if not tweet_data["images"] and not tweet_data.get("video_path"):
        if status_fn: status_fn("📡 الطبقة 3: yt-dlp للوسائط...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            media = download_media_yt_dlp(normalized, tmp_dir)
            if media["images"]:     tweet_data["images"].extend(media["images"])
            if media["video_path"]: tweet_data["video_path"] = media["video_path"]

    return tweet_data

# ════════════════════════════════════════════════════════════
def ocr_image_tesseract(image_path_or_url: str) -> str:
    if not PIL_AVAILABLE or not TESSERACT_AVAILABLE:
        return ""
    try:
        if image_path_or_url.startswith("http"):
            resp = requests.get(image_path_or_url, timeout=10)
            img  = Image.open(io.BytesIO(resp.content))
        else:
            img = Image.open(image_path_or_url)
        return pytesseract.image_to_string(img, lang=OCR_LANG)
    except Exception as e:
        return f"[OCR Error: {e}]"

def ocr_image_gemini(image_path_or_url: str, api_key: str, status_fn=None) -> str:
    if not GEMINI_AVAILABLE or not api_key:
        return ""
    try:
        if image_path_or_url.startswith("http"):
            resp     = requests.get(image_path_or_url, timeout=10)
            img_data = resp.content
        else:
            with open(image_path_or_url, "rb") as f:
                img_data = f.read()
        img_b64 = base64.b64encode(img_data).decode()
        prompt  = [
            "استخرج كل النصوص الموجودة في هذه الصورة بدقة.",
            {"mime_type": "image/jpeg", "data": img_b64}
        ]
        text, _ = gemini_generate(prompt, api_key, status_fn)
        return text or ""
    except Exception as e:
        return f"[Gemini OCR Error: {e}]"

def transcribe_video_gemini(video_path: str, api_key: str, status_fn=None) -> str:
    if not GEMINI_AVAILABLE or not api_key or not os.path.exists(video_path):
        return ""
    try:
        with open(video_path, "rb") as f:
            video_data = f.read()
        video_b64  = base64.b64encode(video_data).decode()
        ext        = Path(video_path).suffix.lower()
        mime_map   = {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska"}
        mime_type  = mime_map.get(ext, "video/mp4")
        prompt     = [
            "استخرج وفرّغ كل الكلام والنصوص الظاهرة في هذا الفيديو بالعربية.",
            {"mime_type": mime_type, "data": video_b64}
        ]
        text, _ = gemini_generate(prompt, api_key, status_fn)
        return text or ""
    except Exception as e:
        return f"[Video Error: {e}]"

def improve_arabic_text(text: str, api_key: str, status_fn=None) -> str:
    if not text.strip() or not api_key:
        return text
    prompt = "صحّح هذا النص العربي إملائياً ونحوياً مع الحفاظ على المعنى. أعد النص المحسّن فقط:\n\n" + text
    result, _ = gemini_generate(prompt, api_key, status_fn)
    return result or text

# ════════════════════════════════════════════════════════════
def build_analysis_prompt(tweet_data: Dict, mode: str) -> str:
    author     = tweet_data.get("author", "")
    username   = tweet_data.get("username", "") or tweet_data.get("url_username", "")
    is_retweet = tweet_data.get("is_retweet", False)
    text       = tweet_data.get("text", "")
    tweet_id   = tweet_data.get("tweet_id", "")

    author_block = "صاحب الحساب: " + author + (" (" + username + ")" if username else "")
    if is_retweet:
        author_block += "\nهذا المنشور اعادة نشر (Retweet)"

    focus_map = {
        "executive": "ركز على الجوانب الاستراتيجية والقرارات والمخاطر.",
        "media":     "ركز على الاسلوب الاعلامي والرسائل والجمهور المستهدف.",
        "security":  "ركز على المخاطر الامنية والتحريض والمعلومات المضللة.",
        "general":   "قدم تحليلا شاملا ومتوازنا.",
    }
    focus    = focus_map.get(mode, focus_map["general"])
    rt_note  = "هذا اعادة نشر" if is_retweet else ""
    txt_body = text if text else "(لا يوجد نص)"

    lines = [
        "انت محلل ذكاء اصطناعي متخصص. حلل المنشور التالي من منصة X وقدم ملخصا تنفيذيا احترافيا.",
        "",
        "بيانات المنشور:",
        author_block,
        "معرف المنشور: " + tweet_id,
        "",
        "محتوى المنشور:",
        txt_body,
        "",
        "تعليمات: " + focus,
        "",
        "اعد JSON صحيحا فقط بهذا الهيكل بدون اي نص خارجه:",
        "{",
        '  "executive_summary": "ملخص في 3-4 جمل",',
        '  "key_points": ["نقطة 1", "نقطة 2", "نقطة 3"],',
        '  "risks": ["خطر 1", "خطر 2"],',
        '  "recommendations": ["توصية 1", "توصية 2"],',
        '  "sentiment": "ايجابي او سلبي او محايد",',
        '  "topics": ["موضوع 1", "موضوع 2"],',
        '  "is_retweet_note": "' + rt_note + '"',
        "}",
    ]
    return "\n".join(lines)

def run_analysis(tweet_data: Dict, api_key: str, mode: str, status_fn=None) -> Dict:
    default_error = {
        "executive_summary": "فشل التحليل",
        "key_points": [], "risks": [], "recommendations": [],
        "sentiment": "غير محدد", "topics": [], "is_retweet_note": ""
    }
    if not api_key:
        default_error["executive_summary"] = "ادخل مفتاح Gemini API من الشريط الجانبي"
        return default_error

    prompt = build_analysis_prompt(tweet_data, mode)
    if status_fn:
        status_fn("جاري التحليل التنفيذي...")

    raw_text, used_model = gemini_generate(prompt, api_key, status_fn)

    if not raw_text:
        default_error["executive_summary"] = (
            "فشل التحليل - تجاوز الحصة المجانية (429)\n"
            "انتظر دقيقة واعد المحاولة\n"
            "او تحقق من مفتاح API على aistudio.google.com/apikey"
        )
        return default_error

    try:
        clean = raw_text.strip()
        clean = re.sub(r"^```json\s*", "", clean)
        clean = re.sub(r"^```\s*",     "", clean)
        clean = re.sub(r"\s*```$",     "", clean)
        result = json.loads(clean)
        result["_model_used"] = used_model
        return result
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]+\}", raw_text)
        if m:
            try:
                result = json.loads(m.group())
                result["_model_used"] = used_model
                return result
            except Exception:
                pass
        default_error["executive_summary"] = "استجابة غير منظمة:\n" + raw_text[:300]
        default_error["_model_used"] = used_model
        return default_error

# ════════════════════════════════════════════════════════════
# 🎨  CSS محسّن — دعم الوضع الليلي والنهاري + خط كبير + RTL
# ════════════════════════════════════════════════════════════
def inject_css():
    css_parts = [
        "<style>",

        # ── خط Tajawal ──
        "@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');",

        # ── متغيرات الألوان: وضع نهاري ──
        ":root {",
        "  --bg-main: #f0f4f8;",
        "  --bg-card: #ffffff;",
        "  --bg-card2: #f8fafc;",
        "  --text-primary: #0f172a;",
        "  --text-secondary: #334155;",
        "  --text-muted: #64748b;",
        "  --border-color: #cbd5e1;",
        "  --accent-blue: #1DA1F2;",
        "  --accent-dark: #0d47a1;",
        "  --accent-green: #059669;",
        "  --accent-red: #dc2626;",
        "  --accent-orange: #d97706;",
        "  --shadow: 0 4px 16px rgba(0,0,0,0.10);",
        "  --shadow-sm: 0 2px 8px rgba(0,0,0,0.07);",
        "  --sidebar-bg: #1e293b;",
        "  --sidebar-text: #f1f5f9;",
        "  --sidebar-muted: #94a3b8;",
        "  --sidebar-border: #334155;",
        "  --sidebar-card: #0f172a;",
        "}",

        # ── متغيرات الألوان: وضع ليلي ──
        "@media (prefers-color-scheme: dark) { :root {",
        "  --bg-main: #0f172a;",
        "  --bg-card: #1e293b;",
        "  --bg-card2: #0f172a;",
        "  --text-primary: #f1f5f9;",
        "  --text-secondary: #cbd5e1;",
        "  --text-muted: #94a3b8;",
        "  --border-color: #334155;",
        "  --shadow: 0 4px 16px rgba(0,0,0,0.40);",
        "  --shadow-sm: 0 2px 8px rgba(0,0,0,0.30);",
        "} }",

        # ── أساس ──
        "*, *::before, *::after { font-family: 'Tajawal', Arial, sans-serif !important; box-sizing: border-box; }",
        "html, body { direction: rtl !important; text-align: right !important; }",

        # ── تطبيق Streamlit ──
        ".stApp {",
        "  background-color: var(--bg-main) !important;",
        "  direction: rtl !important;",
        "}",

        # ── ضمان لون النص في كل مكان ──
        ".stApp p, .stApp span, .stApp div, .stApp label,",
        ".stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "}",

        # ── textarea معطّل ──
        "textarea, textarea[disabled], textarea:disabled {",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "  background-color: var(--bg-card2) !important;",
        "  opacity: 1 !important;",
        "  font-size: 1.1rem !important;",
        "  line-height: 1.8 !important;",
        "}",

        # ── حقول الإدخال ──
        "input, .stTextInput input {",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "  background-color: var(--bg-card) !important;",
        "  font-size: 1.1rem !important;",
        "  padding: 10px 16px !important;",
        "  border-radius: 10px !important;",
        "  border: 2px solid var(--border-color) !important;",
        "}",

        # ══ الشريط الجانبي ══════════════════════════════
        "[data-testid='stSidebar'] {",
        "  background-color: var(--sidebar-bg) !important;",
        "  direction: rtl !important;",
        "  min-width: 320px !important;",
        "  width: 320px !important;",
        "}",
        "[data-testid='stSidebar'] > div { padding: 1.5rem 1.2rem !important; }",
        "[data-testid='stSidebar'] * {",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  color: var(--sidebar-text) !important;",
        "  -webkit-text-fill-color: var(--sidebar-text) !important;",
        "}",
        "[data-testid='stSidebar'] h1, [data-testid='stSidebar'] h2,",
        "[data-testid='stSidebar'] h3, [data-testid='stSidebar'] h4 {",
        "  font-size: 1.3rem !important;",
        "  font-weight: 800 !important;",
        "  color: #ffffff !important;",
        "  -webkit-text-fill-color: #ffffff !important;",
        "  border-bottom: 2px solid var(--sidebar-border);",
        "  padding-bottom: 8px;",
        "  margin-bottom: 12px;",
        "}",
        "[data-testid='stSidebar'] label, [data-testid='stSidebar'] .stCheckbox span {",
        "  font-size: 1.1rem !important;",
        "  font-weight: 600 !important;",
        "  color: var(--sidebar-text) !important;",
        "  -webkit-text-fill-color: var(--sidebar-text) !important;",
        "}",
        "[data-testid='stSidebar'] input, [data-testid='stSidebar'] .stTextInput input {",
        "  background-color: var(--sidebar-card) !important;",
        "  color: #ffffff !important;",
        "  -webkit-text-fill-color: #ffffff !important;",
        "  border: 2px solid var(--sidebar-border) !important;",
        "  font-size: 1.05rem !important;",
        "  padding: 10px 14px !important;",
        "  border-radius: 10px !important;",
        "}",
        "[data-testid='stSidebar'] .stSelectbox > div > div {",
        "  background-color: var(--sidebar-card) !important;",
        "  color: #ffffff !important;",
        "  font-size: 1.05rem !important;",
        "  border: 2px solid var(--sidebar-border) !important;",
        "  border-radius: 10px !important;",
        "}",
        "[data-testid='stSidebar'] .stInfo {",
        "  background-color: rgba(29,161,242,0.15) !important;",
        "  border-right: 4px solid var(--accent-blue) !important;",
        "  border-radius: 10px;",
        "  padding: 12px 16px;",
        "  font-size: 1.05rem !important;",
        "}",
        "[data-testid='stSidebar'] caption {",
        "  color: var(--sidebar-muted) !important;",
        "  -webkit-text-fill-color: var(--sidebar-muted) !important;",
        "  font-size: 0.9rem !important;",
        "}",

        # ══ عنوان التطبيق ═══════════════════════════════
        ".app-title {",
        "  text-align: center !important;",
        "  font-size: 3rem !important;",
        "  font-weight: 900 !important;",
        "  background: linear-gradient(135deg, #1DA1F2, #0d47a1) !important;",
        "  -webkit-background-clip: text !important;",
        "  -webkit-text-fill-color: transparent !important;",
        "  padding: 0.8rem 0 0.3rem 0;",
        "  letter-spacing: -1px;",
        "}",
        ".app-subtitle {",
        "  text-align: center !important;",
        "  color: var(--text-muted) !important;",
        "  -webkit-text-fill-color: var(--text-muted) !important;",
        "  font-size: 1.15rem !important;",
        "  margin-bottom: 2rem;",
        "}",

        # ══ التبويبات ════════════════════════════════════
        ".stTabs [data-baseweb='tab-list'] { justify-content: flex-end !important; gap: 8px; }",
        ".stTabs [data-baseweb='tab'] {",
        "  direction: rtl !important;",
        "  font-size: 1.1rem !important;",
        "  font-weight: 700 !important;",
        "  padding: 10px 20px !important;",
        "  border-radius: 10px 10px 0 0 !important;",
        "}",

        # ══ بطاقة صاحب الحساب ════════════════════════════
        ".account-card {",
        "  background: linear-gradient(135deg, #1DA1F2 0%, #0d47a1 100%) !important;",
        "  border-radius: 16px !important;",
        "  padding: 1.5rem 2rem !important;",
        "  margin-bottom: 1.5rem !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  box-shadow: var(--shadow) !important;",
        "}",
        ".account-card * {",
        "  color: #ffffff !important;",
        "  -webkit-text-fill-color: #ffffff !important;",
        "}",
        ".account-name {",
        "  font-size: 1.6rem !important;",
        "  font-weight: 900 !important;",
        "  margin-bottom: 4px;",
        "}",
        ".account-username {",
        "  font-size: 1.1rem !important;",
        "  opacity: 0.85;",
        "}",
        ".account-model {",
        "  font-size: 0.9rem !important;",
        "  opacity: 0.7;",
        "  margin-top: 6px;",
        "}",
        ".retweet-tag {",
        "  display: inline-block;",
        "  background: rgba(255,255,255,0.25);",
        "  padding: 3px 14px;",
        "  border-radius: 20px;",
        "  font-size: 1rem !important;",
        "  font-weight: 700;",
        "  margin-top: 8px;",
        "}",

        # ══ بطاقة الملخص التنفيذي ════════════════════════
        ".summary-card {",
        "  background: var(--bg-card) !important;",
        "  border-radius: 16px !important;",
        "  padding: 1.8rem 2rem !important;",
        "  margin-bottom: 1.5rem !important;",
        "  border-right: 6px solid var(--accent-blue) !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  box-shadow: var(--shadow) !important;",
        "}",
        ".summary-card .section-title {",
        "  font-size: 1.4rem !important;",
        "  font-weight: 900 !important;",
        "  color: var(--accent-blue) !important;",
        "  -webkit-text-fill-color: var(--accent-blue) !important;",
        "  margin-bottom: 12px;",
        "  display: block;",
        "}",
        ".summary-card .summary-text {",
        "  font-size: 1.25rem !important;",
        "  font-weight: 500 !important;",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "  line-height: 2.0 !important;",
        "}",

        # ══ بطاقة النقاط ══════════════════════════════════
        ".points-card {",
        "  background: var(--bg-card) !important;",
        "  border-radius: 16px !important;",
        "  padding: 1.5rem 1.8rem !important;",
        "  margin-bottom: 1.2rem !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  box-shadow: var(--shadow-sm) !important;",
        "  border-top: 4px solid var(--accent-blue);",
        "}",
        ".section-title-lg {",
        "  font-size: 1.35rem !important;",
        "  font-weight: 900 !important;",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "  margin-bottom: 14px;",
        "  display: block;",
        "  padding-bottom: 8px;",
        "  border-bottom: 2px solid var(--border-color);",
        "}",
        ".point-row {",
        "  display: flex;",
        "  align-items: flex-start;",
        "  gap: 12px;",
        "  padding: 12px 0;",
        "  border-bottom: 1px solid var(--border-color);",
        "  direction: rtl;",
        "}",
        ".point-row:last-child { border-bottom: none; }",
        ".point-icon { font-size: 1.3rem; flex-shrink: 0; margin-top: 2px; }",
        ".point-text {",
        "  font-size: 1.15rem !important;",
        "  font-weight: 500 !important;",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "  line-height: 1.8 !important;",
        "}",

        # ══ بطاقة المخاطر ══════════════════════════════════
        ".risks-card {",
        "  background: var(--bg-card) !important;",
        "  border-radius: 16px !important;",
        "  padding: 1.5rem 1.8rem !important;",
        "  margin-bottom: 1.2rem !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  box-shadow: var(--shadow-sm) !important;",
        "  border-top: 4px solid var(--accent-red);",
        "}",

        # ══ بطاقة التوصيات ════════════════════════════════
        ".reco-card {",
        "  background: var(--bg-card) !important;",
        "  border-radius: 16px !important;",
        "  padding: 1.5rem 1.8rem !important;",
        "  margin-bottom: 1.2rem !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  box-shadow: var(--shadow-sm) !important;",
        "  border-top: 4px solid var(--accent-green);",
        "}",

        # ══ بطاقة المشاعر والموضوعات ══════════════════════
        ".meta-card {",
        "  background: var(--bg-card) !important;",
        "  border-radius: 16px !important;",
        "  padding: 1.5rem 1.8rem !important;",
        "  margin-bottom: 1.2rem !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "  box-shadow: var(--shadow-sm) !important;",
        "}",
        ".sentiment-value {",
        "  font-size: 1.8rem !important;",
        "  font-weight: 900 !important;",
        "  margin-top: 8px;",
        "}",
        ".sentiment-pos { color: #059669 !important; -webkit-text-fill-color: #059669 !important; }",
        ".sentiment-neg { color: #dc2626 !important; -webkit-text-fill-color: #dc2626 !important; }",
        ".sentiment-neu { color: #64748b !important; -webkit-text-fill-color: #64748b !important; }",
        ".topic-pill {",
        "  display: inline-block;",
        "  background: rgba(29,161,242,0.12) !important;",
        "  color: var(--accent-dark) !important;",
        "  -webkit-text-fill-color: var(--accent-dark) !important;",
        "  border: 1.5px solid rgba(29,161,242,0.35);",
        "  padding: 6px 16px;",
        "  border-radius: 20px;",
        "  font-size: 1.05rem !important;",
        "  font-weight: 600 !important;",
        "  margin: 4px 3px;",
        "}",

        # ══ شريط التقدم ═══════════════════════════════════
        ".stProgress > div > div { background: linear-gradient(90deg, #1DA1F2, #0d47a1) !important; }",

        # ══ Expander ══════════════════════════════════════
        ".streamlit-expanderHeader, .streamlit-expanderHeader * {",
        "  font-size: 1.1rem !important;",
        "  font-weight: 700 !important;",
        "  color: var(--text-primary) !important;",
        "  -webkit-text-fill-color: var(--text-primary) !important;",
        "  direction: rtl !important;",
        "  text-align: right !important;",
        "}",

        # ══ الأزرار ════════════════════════════════════════
        ".stButton > button {",
        "  direction: rtl !important;",
        "  font-size: 1.1rem !important;",
        "  font-weight: 700 !important;",
        "  border-radius: 12px !important;",
        "  padding: 12px 24px !important;",
        "}",

        # ══ تصحيح Alerts ══════════════════════════════════
        ".stAlert p, .stAlert div { color: var(--text-primary) !important; }",

        "</style>",
    ]
    st.markdown("".join(css_parts), unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# 🖥️  عرض نتائج التحليل — واجهة محسّنة
# ════════════════════════════════════════════════════════════
def display_analysis_results(analysis: Dict, tweet_data: Dict):
    author   = tweet_data.get("author", "")
    username = tweet_data.get("username", "") or tweet_data.get("url_username", "")
    is_rt    = tweet_data.get("is_retweet", False)
    model    = analysis.get("_model_used", "")

    # ══ 1. بطاقة صاحب الحساب ════════════════════════════
    rt_tag   = '<span class="retweet-tag">🔁 إعادة نشر</span>' if is_rt else ""
    mdl_line = '<div class="account-model">🤖 نموذج: ' + model + "</div>" if model else ""

    st.markdown(
        '<div class="account-card">'
        '  <div style="font-size:2rem;margin-bottom:6px;">👤</div>'
        '  <div class="account-name">🐦 ' + author + "</div>"
        + ('<div class="account-username">' + username + "</div>" if username else "")
        + rt_tag
        + mdl_line
        + "</div>",
        unsafe_allow_html=True
    )

    # ══ 2. الملخص التنفيذي ══════════════════════════════
    st.markdown(
        '<div class="summary-card">'
        '<span class="section-title">📋 الملخص التنفيذي</span>'
        '<div class="summary-text">' + analysis.get("executive_summary", "—") + "</div>"
        "</div>",
        unsafe_allow_html=True
    )

    # ══ 3. النقاط الرئيسية ═══════════════════════════════
    kp_rows = "".join(
        '<div class="point-row">'
        '<span class="point-icon">🔹</span>'
        '<span class="point-text">' + pt + "</span>"
        "</div>"
        for pt in analysis.get("key_points", [])
    )
    st.markdown(
        '<div class="points-card">'
        '<span class="section-title-lg">🎯 النقاط الرئيسية</span>'
        + kp_rows +
        "</div>",
        unsafe_allow_html=True
    )

    # ══ 4. المخاطر + التوصيات ════════════════════════════
    col1, col2 = st.columns(2)

    with col1:
        risk_rows = "".join(
            '<div class="point-row">'
            '<span class="point-icon">🔴</span>'
            '<span class="point-text">' + r + "</span>"
            "</div>"
            for r in analysis.get("risks", [])
        )
        st.markdown(
            '<div class="risks-card">'
            '<span class="section-title-lg">⚠️ المخاطر</span>'
            + risk_rows +
            "</div>",
            unsafe_allow_html=True
        )

    with col2:
        rec_rows = "".join(
            '<div class="point-row">'
            '<span class="point-icon">✅</span>'
            '<span class="point-text">' + rec + "</span>"
            "</div>"
            for rec in analysis.get("recommendations", [])
        )
        st.markdown(
            '<div class="reco-card">'
            '<span class="section-title-lg">💡 التوصيات</span>'
            + rec_rows +
            "</div>",
            unsafe_allow_html=True
        )

    # ══ 5. المشاعر + الموضوعات ════════════════════════════
    col3, col4 = st.columns(2)

    sentiment = analysis.get("sentiment", "محايد")
    sent_cls  = (
        "sentiment-pos" if "ايجاب" in sentiment or "إيجاب" in sentiment
        else "sentiment-neg" if "سلب" in sentiment
        else "sentiment-neu"
    )

    with col3:
        st.markdown(
            '<div class="meta-card">'
            '<span class="section-title-lg">💬 المشاعر العامة</span>'
            '<div class="sentiment-value ' + sent_cls + '">' + sentiment + "</div>"
            "</div>",
            unsafe_allow_html=True
        )

    with col4:
        topics_html = "".join(
            '<span class="topic-pill">' + t + "</span>"
            for t in analysis.get("topics", [])
        )
        st.markdown(
            '<div class="meta-card">'
            '<span class="section-title-lg">🏷️ الموضوعات</span>'
            '<div style="margin-top:10px;">' + topics_html + "</div>"
            "</div>",
            unsafe_allow_html=True
        )

# ════════════════════════════════════════════════════════════
# 🚀  الدالة الرئيسية
# ════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title=APP_EMOJI + " " + APP_NAME,
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()

    st.markdown(
        '<h1 class="app-title">' + APP_EMOJI + " " + APP_NAME + "</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        '<p class="app-subtitle">تحليل منشورات X وتويتر بالذكاء الاصطناعي | v' + APP_VERSION + "</p>",
        unsafe_allow_html=True
    )

    # ════ الشريط الجانبي ════
    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")
        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            help="احصل على مفتاحك من: https://aistudio.google.com/apikey",
            placeholder="AIzaSy..."
        )
        st.markdown("---")
        analysis_mode = st.selectbox(
            "🎯 وضع التحليل",
            ["executive", "media", "security", "general"],
            format_func=lambda x: {
                "executive": "📊 تنفيذي",
                "media":     "📣 إعلامي",
                "security":  "🔒 أمني",
                "general":   "🌐 عام"
            }.get(x, x)
        )
        st.markdown("---")
        enable_ocr   = st.checkbox("🖼️ تحليل الصور (OCR)",  value=True)
        enable_video = st.checkbox("🎬 تحليل الفيديو",       value=False)
        improve_text = st.checkbox("✨ تحسين النص العربي",   value=False)
        st.markdown("---")
        st.markdown("#### 📊 حدود الاستخدام المجاني")
        st.info(
            "🥇 gemini-1.5-flash\n"
            "15 طلب/دقيقة | 1,500 طلب/يوم\n\n"
            "⚡ gemini-2.5-flash\n"
            "10 طلبات/دقيقة | 250 طلب/يوم"
        )
        st.markdown("---")
        st.caption("v" + APP_VERSION + " | oEmbed + Nitter + yt-dlp")

    # ════ التبويبات ════
    tab_link, tab_img, tab_guide = st.tabs([
        "🔗 تحليل رابط",
        "🖼️ تحليل صورة",
        "📖 دليل الاستخدام"
    ])

    # ── تبويب 1 ──
    with tab_link:
        st.markdown("### 🔗 أدخل رابط منشور X")
        tweet_url_input = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/123456789",
            help="يقبل روابط x.com و twitter.com بجميع أشكالها"
        )
        if tweet_url_input:
            if is_tweet_url(tweet_url_input):
                tid   = extract_tweet_id(tweet_url_input)
                uname = extract_username_from_url(tweet_url_input)
                st.success("✅ رابط صالح | الحساب: " + uname + " | المعرّف: " + str(tid))
            else:
                st.error("❌ الرابط غير مدعوم – أدخل رابط x.com أو twitter.com")

        analyze_btn = st.button("🔍 تحليل المنشور", type="primary", use_container_width=True)

        if analyze_btn:
            if not tweet_url_input or not is_tweet_url(tweet_url_input):
                st.error("❌ أدخل رابطاً صالحاً أولاً")
            elif not api_key:
                st.error("❌ أدخل مفتاح Gemini API من الشريط الجانبي")
            else:
                status_box = st.empty()
                progress   = st.progress(0)
                log_exp    = st.expander("📋 سجل التنفيذ", expanded=False)
                log_lines: List[str] = []

                def upd(msg: str):
                    status_box.info("⏳ " + msg)
                    log_lines.append(msg)
                    with log_exp:
                        st.text("\n".join(log_lines[-10:]))

                progress.progress(10)
                upd("جارٍ جلب بيانات المنشور...")
                tweet_data = fetch_tweet_with_media(tweet_url_input, api_key, upd)
                progress.progress(40)

                if improve_text and tweet_data.get("text"):
                    upd("تحسين النص العربي...")
                    tweet_data["text"] = improve_arabic_text(tweet_data["text"], api_key, upd)
                progress.progress(55)

                ocr_texts: List[str] = []
                if enable_ocr and tweet_data.get("images"):
                    upd("تحليل " + str(len(tweet_data["images"])) + " صورة...")
                    for img in tweet_data["images"][:3]:
                        t = ocr_image_tesseract(img) or ocr_image_gemini(img, api_key, upd)
                        if t.strip():
                            ocr_texts.append(t)
                progress.progress(70)

                video_transcript = ""
                if enable_video and tweet_data.get("video_path"):
                    upd("تحليل الفيديو...")
                    video_transcript = transcribe_video_gemini(tweet_data["video_path"], api_key, upd)
                progress.progress(80)

                full_text = tweet_data.get("text", "")
                if ocr_texts:
                    full_text += "\n\n[نص من الصور]\n" + "\n".join(ocr_texts)
                if video_transcript:
                    full_text += "\n\n[تفريغ الفيديو]\n" + video_transcript
                tweet_data["text"] = full_text

                analysis = run_analysis(tweet_data, api_key, analysis_mode, upd)
                progress.progress(100)
                status_box.success("✅ اكتمل التحليل!")

                st.markdown("---")
                display_analysis_results(analysis, tweet_data)

                with st.expander("📝 النص الكامل للمنشور", expanded=False):
                    st.text_area("", value=tweet_data.get("text", "(فارغ)"), height=200, disabled=True)

                if ocr_texts:
                    with st.expander("🖼️ النصوص المستخرجة من الصور"):
                        for i, t in enumerate(ocr_texts, 1):
                            st.text_area("صورة " + str(i), value=t, height=100, disabled=True)

                if video_transcript:
                    with st.expander("🎬 تفريغ الفيديو"):
                        st.text_area("", value=video_transcript, height=120, disabled=True)

                export = {
                    "tweet_url":  tweet_url_input,
                    "tweet_data": {k: v for k, v in tweet_data.items() if k != "video_path"},
                    "analysis":   analysis,
                    "ocr_texts":  ocr_texts,
                    "transcript": video_transcript,
                }
                st.download_button(
                    "💾 تحميل النتائج (JSON)",
                    data=json.dumps(export, ensure_ascii=False, indent=2),
                    file_name="analysis_" + tweet_data.get("tweet_id", "") + ".json",
                    mime="application/json"
                )

    # ── تبويب 2 ──
    with tab_img:
        st.markdown("### 🖼️ رفع صورة للتحليل المباشر")
        uploaded = st.file_uploader("ارفع صورة", type=["jpg", "jpeg", "png", "webp", "gif"])
        if uploaded and st.button("🔍 تحليل الصورة", type="primary"):
            if not api_key:
                st.error("❌ أدخل مفتاح Gemini API")
            else:
                with st.spinner("جارٍ التحليل..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                        tmp.write(uploaded.read())
                        tmp_path = tmp.name
                    ocr_text = ocr_image_tesseract(tmp_path)
                    img_data = open(tmp_path, "rb").read()
                    img_b64  = base64.b64encode(img_data).decode()
                    prompt   = [
                        "حلل هذه الصورة وقدم: وصف المحتوى، النصوص المرئية، المعلومات الرئيسية، التوصيات. النص المستخرج: " + (ocr_text or "لا يوجد"),
                        {"mime_type": "image/jpeg", "data": img_b64}
                    ]
                    stat_box = st.empty()
                    result, model = gemini_generate(prompt, api_key, lambda m: stat_box.info(m))
                    os.unlink(tmp_path)
                    if result:
                        st.success("✅ التحليل مكتمل – النموذج: " + str(model))
                        st.markdown("---")
                        st.markdown(result)
                    else:
                        st.error("❌ فشل التحليل – انتظر دقيقة وأعد المحاولة")

    # ── تبويب 3 ──
    with tab_guide:
        st.markdown("### 📖 دليل الاستخدام")
        st.markdown("#### 🚀 البدء السريع")
        st.markdown(
            "1. احصل على مفتاح Gemini مجاني من [Google AI Studio](https://aistudio.google.com/apikey)  \n"
            "2. أدخل المفتاح في الشريط الجانبي  \n"
            "3. الصق رابط المنشور واضغط **تحليل**"
        )
        st.markdown("#### ✅ الروابط المدعومة")
        st.code(
            "https://x.com/user/status/123456789\n"
            "https://x.com/user/status/123456789?s=20\n"
            "https://twitter.com/user/status/123456789",
            language=None
        )
        st.markdown("#### ⚠️ حل مشكلة 429")
        st.table({
            "الحل":  ["انتظر دقيقة", "مفتاح جديد", "فعّل الفوترة"],
            "الوصف": [
                "الحد المجاني 10-15 طلب/دقيقة",
                "أنشئ مفتاحاً من aistudio.google.com/apikey",
                "يرفع الحد إلى 1000 طلب/دقيقة"
            ]
        })
        st.markdown("#### 🤖 النماذج المتاحة 2025-2026")
        st.table({
            "النموذج":    ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.5-flash", "gemini-2.5-pro"],
            "RPM مجاني": ["15", "15", "10", "5"],
            "RPD مجاني": ["1,500", "1,500", "250", "100"]
        })


if __name__ == "__main__":
    main()
