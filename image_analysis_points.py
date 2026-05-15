# ============================================================
# المشهد التنفيذي - Executive Scene Analyzer
# النسخة: v6.3 | تاريخ التحديث: 2026-05
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
APP_VERSION = "6.3"
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
            if status_fn: status_fn("⚠️ Nitter فشل – جميع المرايا غير متاحة")

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

# ════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════
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
    focus   = focus_map.get(mode, focus_map["general"])
    rt_note = "هذا اعادة نشر" if is_retweet else ""
    text_content = text if text else "(لا يوجد نص)"

    lines = [
        "انت محلل ذكاء اصطناعي متخصص. حلل المنشور التالي من منصة X وقدم ملخصا تنفيذيا احترافيا.",
        "",
        "بيانات المنشور:",
        author_block,
        "معرف المنشور: " + tweet_id,
        "",
        "محتوى المنشور:",
        text_content,
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
            "فشل التحليل - اسباب محتملة:\n"
            "تجاوز الحصة المجانية (429) - انتظر دقيقة واعد المحاولة\n"
            "تحقق من مفتاح API على https://aistudio.google.com/apikey"
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
def inject_css():
    css = (
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');"
        "* { font-family: 'Tajawal', Arial, sans-serif !important; }"
        "html, body, .stApp { direction: rtl; text-align: right; }"
        ".stApp, .stApp * { color: #1a1a1a !important; }"
        ".app-title {"
        "  text-align: center !important;"
        "  font-size: 2.4rem;"
        "  font-weight: 900;"
        "  background: linear-gradient(135deg,#1DA1F2,#0d47a1);"
        "  -webkit-background-clip: text;"
        "  -webkit-text-fill-color: transparent;"
        "  padding: 0.5rem 0;"
        "}"
        ".app-subtitle { text-align:center !important; color:#555 !important; font-size:1rem; margin-bottom:1.5rem; }"
        "[data-testid='stSidebar'], [data-testid='stSidebar'] * {"
        "  direction:rtl !important; text-align:right !important; color:#1a1a1a !important;"
        "}"
        "input, textarea, .stTextInput input, .stTextArea textarea {"
        "  direction:rtl !important; text-align:right !important;"
        "  color:#1a1a1a !important; background-color:#ffffff !important;"
        "  -webkit-text-fill-color:#1a1a1a !important;"
        "}"
        "textarea[disabled], textarea:disabled {"
        "  color:#1a1a1a !important; -webkit-text-fill-color:#1a1a1a !important;"
        "  background-color:#f8f9fa !important; opacity:1 !important;"
        "}"
        ".stTabs [data-baseweb='tab-list'] { justify-content:flex-end; }"
        ".stTabs [data-baseweb='tab'] { direction:rtl; color:#1a1a1a !important; }"
        ".result-card {"
        "  background:#ffffff !important; border-radius:12px;"
        "  padding:1.2rem 1.5rem; margin:0.8rem 0;"
        "  border-right:4px solid #1DA1F2; direction:rtl; text-align:right;"
        "  color:#1a1a1a !important; box-shadow:0 2px 8px rgba(0,0,0,0.08);"
        "}"
        ".result-card, .result-card * { color:#1a1a1a !important; }"
        ".author-badge {"
        "  display:inline-flex; align-items:center; gap:6px;"
        "  background:linear-gradient(135deg,#1DA1F2,#0d47a1);"
        "  padding:6px 14px; border-radius:20px; font-weight:700; font-size:1rem; margin-bottom:0.5rem;"
        "}"
        ".author-badge, .author-badge * { color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; }"
        ".retweet-badge {"
        "  display:inline-flex; align-items:center; gap:6px;"
        "  background:#17bf63; padding:4px 12px; border-radius:20px; font-size:0.85rem; margin-right:8px;"
        "}"
        ".retweet-badge, .retweet-badge * { color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; }"
        ".model-badge { font-size:0.75rem; color:#555 !important; background:#eee !important; padding:2px 8px; border-radius:10px; float:left; }"
        ".point-item {"
        "  background:#ffffff !important; border-radius:8px; padding:10px 16px; margin:5px 0;"
        "  border:1px solid #dde3ea; direction:rtl; text-align:right;"
        "  color:#1a1a1a !important; font-size:0.95rem; line-height:1.6;"
        "  box-shadow:0 1px 4px rgba(0,0,0,0.05);"
        "}"
        ".point-item, .point-item * { color:#1a1a1a !important; -webkit-text-fill-color:#1a1a1a !important; }"
        ".sentiment-positive { color:#0a8a42 !important; font-weight:700; }"
        ".sentiment-negative { color:#c0142a !important; font-weight:700; }"
        ".sentiment-neutral  { color:#4a5568 !important; font-weight:700; }"
        ".topic-tag {"
        "  background:#e8f5fd !important; color:#0d47a1 !important;"
        "  -webkit-text-fill-color:#0d47a1 !important;"
        "  padding:3px 12px; border-radius:14px; margin:3px; display:inline-block;"
        "  font-size:0.88rem; font-weight:500; border:1px solid #b3d9f5;"
        "}"
        "[data-testid='stAppViewContainer'] *, [data-testid='block-container'] *,"
        ".element-container *, .stMarkdown *,"
        "p, span, div, li, label, h1, h2, h3, h4, h5, h6 { color:#1a1a1a !important; }"
        ".author-badge span, .author-badge *, .retweet-badge span, .retweet-badge * {"
        "  color:#ffffff !important; -webkit-text-fill-color:#ffffff !important;"
        "}"
        ".stProgress > div > div { background:linear-gradient(90deg,#1DA1F2,#0d47a1) !important; }"
        ".streamlit-expanderHeader, .streamlit-expanderHeader *,"
        ".streamlit-expanderContent, .streamlit-expanderContent * {"
        "  color:#1a1a1a !important; direction:rtl !important; text-align:right !important;"
        "}"
        ".stAlert p, .stAlert div, .stInfo p, .stSuccess p, .stError p, .stWarning p { color:#1a1a1a !important; }"
        ".stSelectbox label, .stRadio label, .stCheckbox label, .stCheckbox span {"
        "  color:#1a1a1a !important; direction:rtl !important;"
        "}"
        ".stButton > button { direction:rtl; font-weight:700; border-radius:10px; }"
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
def display_analysis_results(analysis: Dict, tweet_data: Dict):
    author   = tweet_data.get("author", "")
    username = tweet_data.get("username", "") or tweet_data.get("url_username", "")
    is_rt    = tweet_data.get("is_retweet", False)
    model    = analysis.get("_model_used", "")

    st.markdown("#### 👤 صاحب الحساب")
    author_html = '<span class="author-badge">🐦 ' + author
    if username:
        author_html += " | " + username
    author_html += "</span>"
    if is_rt:
        author_html += ' <span class="retweet-badge">🔁 إعادة نشر</span>'
    if model:
        author_html += ' <span class="model-badge">🤖 ' + model + "</span>"
    st.markdown(author_html, unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("#### 📋 الملخص التنفيذي")
    st.markdown(
        '<div class="result-card">' + analysis.get("executive_summary", "—") + "</div>",
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🎯 النقاط الرئيسية")
        for pt in analysis.get("key_points", []):
            st.markdown('<div class="point-item">• ' + pt + "</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("#### ⚠️ المخاطر والتوصيات")
        for r in analysis.get("risks", []):
            st.markdown(
                '<div class="point-item" style="border-right:4px solid #e0245e;">🔴 ' + r + "</div>",
                unsafe_allow_html=True
            )
        for rec in analysis.get("recommendations", []):
            st.markdown(
                '<div class="point-item" style="border-right:4px solid #17bf63;">✅ ' + rec + "</div>",
                unsafe_allow_html=True
            )

    col3, col4 = st.columns(2)
    sentiment = analysis.get("sentiment", "محايد")
    sent_cls  = (
        "sentiment-positive" if "ايجاب" in sentiment or "إيجاب" in sentiment
        else "sentiment-negative" if "سلب" in sentiment
        else "sentiment-neutral"
    )
    with col3:
        st.markdown("#### 💡 المشاعر العامة")
        st.markdown('<p class="' + sent_cls + '" style="font-size:1.4rem">' + sentiment + "</p>", unsafe_allow_html=True)
    with col4:
        st.markdown("#### 🏷️ الموضوعات")
        for topic in analysis.get("topics", []):
            st.markdown('<span class="topic-tag">' + topic + "</span>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title=APP_EMOJI + " " + APP_NAME,
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()

    st.markdown('<h1 class="app-title">' + APP_EMOJI + " " + APP_NAME + "</h1>", unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">تحليل منشورات X وتويتر بالذكاء الاصطناعي | v' + APP_VERSION + "</p>", unsafe_allow_html=True)

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
        enable_ocr   = st.checkbox("🖼️ تحليل الصور (OCR)", value=True)
        enable_video = st.checkbox("🎬 تحليل الفيديو",     value=False)
        improve_text = st.checkbox("✨ تحسين النص العربي", value=False)
        st.markdown("---")
        st.markdown("#### 📊 حدود الاستخدام المجاني")
        st.info(
            "gemini-1.5-flash (الافضل)\n"
            "15 طلب/دقيقة | 1,500 طلب/يوم\n\n"
            "gemini-2.5-flash\n"
            "10 طلبات/دقيقة | 250 طلب/يوم"
        )
        st.markdown("---")
        st.caption("v" + APP_VERSION + " | oEmbed + Nitter + yt-dlp")

    # ════ التبويبات ════
    tab_link, tab_img, tab_guide = st.tabs(["🔗 تحليل رابط", "🖼️ تحليل صورة", "📖 دليل الاستخدام"])

    # ── تبويب 1: تحليل رابط ──
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
                st.success("✅ رابط صالح | الحساب: " + uname + " | معرّف المنشور: " + str(tid))
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
                log_lines  = []

                def upd(msg):
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

                ocr_texts = []
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
                    st.text_area("", value=tweet_data.get("text", "(فارغ)"), height=150, disabled=True)

                if ocr_texts:
                    with st.expander("🖼️ النصوص المستخرجة من الصور"):
                        for i, t in enumerate(ocr_texts, 1):
                            st.text_area("صورة " + str(i), value=t, height=80, disabled=True)

                if video_transcript:
                    with st.expander("🎬 تفريغ الفيديو"):
                        st.text_area("", value=video_transcript, height=100, disabled=True)

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

    # ── تبويب 2: تحليل صورة ──
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

    # ── تبويب 3: دليل الاستخدام ──
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
            "https://twitter.com/user/status/123456789\n"
            "https://www.twitter.com/user/status/123456789",
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
