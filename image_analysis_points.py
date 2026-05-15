# ============================================================
# المشهد التنفيذي - Executive Scene Analyzer
# النسخة: v6.3 | تاريخ التحديث: 2026-05
# الإصلاحات: نماذج Gemini 2025-2026 + Retry Backoff + RTL UI
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
from urllib.parse import urlparse, urlencode, quote_plus

# ── مكتبات اختيارية ──────────────────────────────────────────
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
# ⚙️  الإعدادات العامة
# ════════════════════════════════════════════════════════════
APP_NAME    = "المشهد التنفيذي"
APP_VERSION = "6.3"
APP_EMOJI   = "🎯"

# ── نماذج Gemini المتاحة 2025-2026 (مرتبة حسب الأولوية) ─────
# gemini-1.5-flash أفضل للـ Free Tier: 15 RPM, 1500 RPD
GEMINI_MODELS = [
    "gemini-1.5-flash",        # ✅ 15 RPM | 1,500 RPD  ← الأفضل مجاناً
    "gemini-1.5-flash-8b",     # ✅ 15 RPM | 1,500 RPD
    "gemini-2.5-flash",        # ✅ 10 RPM | 250 RPD
    "gemini-2.5-flash-lite",   # ✅ احتياطي
    "gemini-2.5-pro",          # ✅  5 RPM | 100 RPD  ← الأثقل
]

OCR_LANG      = "ara+eng"
REQUEST_DELAY = 2      # ثوانٍ بين كل طلب API
MAX_RETRIES   = 3      # عدد المحاولات لكل نموذج عند 429

# ── Regex لروابط X / Twitter ─────────────────────────────────
TWEET_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/[^/]+/status/\d+",
    re.IGNORECASE
)

# ════════════════════════════════════════════════════════════
# 🔗  دوال التحقق من الروابط
# ════════════════════════════════════════════════════════════
def is_tweet_url(url: str) -> bool:
    return bool(TWEET_URL_PATTERN.match(url.strip()))

def extract_tweet_id(url: str) -> Optional[str]:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None

def extract_username_from_url(url: str) -> str:
    """يستخرج @username من رابط المنشور."""
    m = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/", url, re.IGNORECASE)
    return f"@{m.group(1)}" if m else ""

def normalize_tweet_url(url: str) -> str:
    """يحوّل x.com → twitter.com ويحذف query params."""
    url = re.sub(r"\?.*$", "", url.strip())
    url = re.sub(r"https?://(www\.)?x\.com/", "https://twitter.com/", url)
    return url

# ════════════════════════════════════════════════════════════
# 🔄  Exponential Backoff للتعامل مع 429
# ════════════════════════════════════════════════════════════
def exponential_backoff(attempt: int, base: float = 2.0, cap: float = 60.0) -> float:
    """يحسب وقت الانتظار: 2^attempt ثانية + jitter عشوائي."""
    wait = min(base ** attempt + random.uniform(0, 1), cap)
    return wait

def call_gemini_with_retry(model_name: str, prompt, status_fn=None) -> Optional[str]:
    """
    يستدعي Gemini مع إعادة المحاولة عند 429.
    يعيد النص أو None عند الفشل.
    """
    if not GEMINI_AVAILABLE:
        return None

    for attempt in range(MAX_RETRIES):
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            err_str = str(e).lower()

            # ── 429: تجاوز الحصة ─────────────────────────────
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                wait_time = exponential_backoff(attempt)
                if status_fn:
                    status_fn(f"⏳ {model_name}: حد الطلبات – انتظر {wait_time:.0f}ث (محاولة {attempt+1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                continue   # أعد المحاولة

            # ── 404: النموذج غير موجود ───────────────────────
            elif "404" in err_str or "not found" in err_str or "deprecated" in err_str:
                if status_fn:
                    status_fn(f"⚠️ {model_name}: النموذج غير متاح – جربّ التالي")
                return None   # انتقل للنموذج التالي فوراً

            # ── خطأ آخر ──────────────────────────────────────
            else:
                if status_fn:
                    status_fn(f"❌ {model_name}: خطأ غير متوقع: {str(e)[:80]}")
                return None

    # فشلت كل المحاولات لهذا النموذج
    if status_fn:
        status_fn(f"🚫 {model_name}: استُنفدت {MAX_RETRIES} محاولات")
    return None

def gemini_generate(prompt, api_key: str, status_fn=None) -> Tuple[Optional[str], Optional[str]]:
    """
    يجرّب كل نماذج Gemini بالترتيب حتى ينجح أحدها.
    يعيد (النص, اسم_النموذج) أو (None, None).
    """
    if not GEMINI_AVAILABLE or not api_key:
        return None, None

    genai.configure(api_key=api_key)

    for model_name in GEMINI_MODELS:
        if status_fn:
            status_fn(f"🤖 جارٍ المحاولة: {model_name}")

        result = call_gemini_with_retry(model_name, prompt, status_fn)
        if result:
            return result, model_name

        # تأخير بين النماذج لتجنب 429
        time.sleep(REQUEST_DELAY)

    return None, None

# ════════════════════════════════════════════════════════════
# 🐦  جلب بيانات المنشور
# ════════════════════════════════════════════════════════════
def fetch_via_oembed(tweet_url: str) -> Dict:
    """يجلب بيانات المنشور عبر Twitter oEmbed API (مجاني، بدون مفتاح)."""
    result = {"text": "", "author": "", "username": "", "images": [], "video_url": None, "is_retweet": False}
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={quote_plus(tweet_url)}&lang=ar&omit_script=true"
        resp = requests.get(oembed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            data = resp.json()
            result["author"] = data.get("author_name", "")
            html_content = data.get("html", "")

            if BS4_AVAILABLE and html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                # استخراج النص
                p_tags = soup.find_all("p")
                texts = [p.get_text(separator=" ", strip=True) for p in p_tags if p.get_text(strip=True)]
                result["text"] = " ".join(texts)
                # استخراج الصور
                imgs = soup.find_all("img")
                result["images"] = [img["src"] for img in imgs if img.get("src")]

            # استخراج username من رابط المؤلف
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
    """يجلب بيانات المنشور عبر مرايا Nitter كبديل احتياطي."""
    result = {"text": "", "author": "", "username": "", "images": [], "video_url": None, "is_retweet": False, "error": ""}
    tweet_id = extract_tweet_id(tweet_url)
    username_from_url = extract_username_from_url(tweet_url).lstrip("@")

    for mirror in NITTER_MIRRORS:
        try:
            nitter_url = f"{mirror}/{username_from_url}/status/{tweet_id}"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"}
            resp = requests.get(nitter_url, timeout=8, headers=headers)
            if resp.status_code != 200:
                continue

            if not BS4_AVAILABLE:
                result["error"] = "BeautifulSoup غير متوفر"
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── النص ─────────────────────────────────────────
            content_div = soup.find("div", class_="tweet-content")
            if content_div:
                result["text"] = content_div.get_text(separator=" ", strip=True)

            # ── المؤلف ───────────────────────────────────────
            name_el  = soup.find("a", class_="fullname")
            uname_el = soup.find("a", class_="username")
            if name_el:
                result["author"] = name_el.get_text(strip=True)
            if uname_el:
                result["username"] = uname_el.get_text(strip=True)

            # ── إعادة نشر؟ ──────────────────────────────────
            rt_label = soup.find("span", class_="retweet-header")
            if rt_label:
                result["is_retweet"] = True

            # ── الصور ────────────────────────────────────────
            for img in soup.find_all("img", class_="media-image"):
                src = img.get("src", "")
                if src:
                    full_src = f"{mirror}{src}" if src.startswith("/") else src
                    result["images"].append(full_src)

            # ── الفيديو ──────────────────────────────────────
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
    """يحاول تحميل الوسائط عبر yt-dlp."""
    result = {"images": [], "video_path": None, "error": ""}
    yt_dlp_path = shutil.which("yt-dlp")
    if not yt_dlp_path:
        result["error"] = "yt-dlp غير مثبّت"
        return result
    try:
        cmd = [
            yt_dlp_path,
            tweet_url,
            "--no-playlist",
            "--write-thumbnail",
            "--skip-download",
            "-o", os.path.join(output_dir, "%(id)s.%(ext)s"),
            "--quiet",
        ]
        subprocess.run(cmd, timeout=30, capture_output=True, check=False)

        # جمع الملفات المحملة
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
    """
    الدالة الرئيسية: تجلب المنشور عبر 3 طبقات احتياطية.
    الطبقة 1: oEmbed API
    الطبقة 2: Nitter mirrors
    الطبقة 3: yt-dlp
    """
    if status_fn:
        status_fn("🔍 يتحقق من الرابط...")

    tweet_data = {
        "text": "", "author": "", "username": "", "url_username": "",
        "images": [], "video_path": None, "video_url": None,
        "is_retweet": False, "tweet_id": "", "original_url": url,
    }

    tweet_data["url_username"] = extract_username_from_url(url)
    tweet_data["tweet_id"] = extract_tweet_id(url) or ""
    normalized = normalize_tweet_url(url)

    # ── الطبقة 1: oEmbed ─────────────────────────────────────
    if status_fn:
        status_fn("📡 الطبقة 1: Twitter oEmbed API...")
    oembed = fetch_via_oembed(normalized)
    if oembed.get("text"):
        tweet_data.update(oembed)
        if status_fn:
            status_fn("✅ oEmbed: تم جلب النص بنجاح")
    else:
        # ── الطبقة 2: Nitter ─────────────────────────────────
        if status_fn:
            status_fn("📡 الطبقة 2: Nitter mirrors...")
        nitter = fetch_via_nitter(normalized)
        if nitter.get("text") or nitter.get("images"):
            tweet_data.update(nitter)
            if status_fn:
                status_fn("✅ Nitter: تم جلب البيانات")
        else:
            if status_fn:
                status_fn("⚠️ Nitter فشل – جميع المرايا غير متاحة")

    # ── الطبقة 3: yt-dlp للوسائط ─────────────────────────────
    if not tweet_data["images"] and not tweet_data.get("video_path"):
        if status_fn:
            status_fn("📡 الطبقة 3: yt-dlp للوسائط...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            media = download_media_yt_dlp(normalized, tmp_dir)
            if media["images"]:
                tweet_data["images"].extend(media["images"])
            if media["video_path"]:
                tweet_data["video_path"] = media["video_path"]

    return tweet_data

# ════════════════════════════════════════════════════════════
# 🖼️  OCR واستخراج النص من الصور
# ════════════════════════════════════════════════════════════
def ocr_image_tesseract(image_path_or_url: str) -> str:
    """استخراج النص بـ Tesseract OCR."""
    if not PIL_AVAILABLE or not TESSERACT_AVAILABLE:
        return ""
    try:
        if image_path_or_url.startswith("http"):
            resp = requests.get(image_path_or_url, timeout=10)
            img = Image.open(io.BytesIO(resp.content))
        else:
            img = Image.open(image_path_or_url)
        return pytesseract.image_to_string(img, lang=OCR_LANG)
    except Exception as e:
        return f"[OCR Error: {e}]"

def ocr_image_gemini(image_path_or_url: str, api_key: str, status_fn=None) -> str:
    """استخراج النص من الصورة باستخدام Gemini Vision."""
    if not GEMINI_AVAILABLE or not api_key:
        return ""
    try:
        if image_path_or_url.startswith("http"):
            resp = requests.get(image_path_or_url, timeout=10)
            img_data = resp.content
        else:
            with open(image_path_or_url, "rb") as f:
                img_data = f.read()

        img_b64 = base64.b64encode(img_data).decode()
        prompt = [
            "استخرج كل النصوص الموجودة في هذه الصورة بدقة. حافظ على الترتيب الأصلي وأعد النص كما هو.",
            {"mime_type": "image/jpeg", "data": img_b64}
        ]
        text, model = gemini_generate(prompt, api_key, status_fn)
        return text or ""
    except Exception as e:
        return f"[Gemini OCR Error: {e}]"

# ════════════════════════════════════════════════════════════
# 🎬  استخراج النص من الفيديو
# ════════════════════════════════════════════════════════════
def transcribe_video_gemini(video_path: str, api_key: str, status_fn=None) -> str:
    """يحوّل الفيديو إلى نص باستخدام Gemini."""
    if not GEMINI_AVAILABLE or not api_key or not os.path.exists(video_path):
        return ""
    try:
        with open(video_path, "rb") as f:
            video_data = f.read()
        video_b64 = base64.b64encode(video_data).decode()

        # تحديد نوع الملف
        ext = Path(video_path).suffix.lower()
        mime_map = {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska"}
        mime_type = mime_map.get(ext, "video/mp4")

        prompt = [
            "استخرج وفرّغ كل الكلام والنصوص الظاهرة في هذا الفيديو. قدّم النص كاملاً بالعربية.",
            {"mime_type": mime_type, "data": video_b64}
        ]
        text, model = gemini_generate(prompt, api_key, status_fn)
        return text or ""
    except Exception as e:
        return f"[Video Transcription Error: {e}]"

# ════════════════════════════════════════════════════════════
# ✨  تحسين النص العربي
# ════════════════════════════════════════════════════════════
def improve_arabic_text(text: str, api_key: str, status_fn=None) -> str:
    """يحسّن النص العربي بتصحيح الأخطاء الإملائية والنحوية."""
    if not text.strip() or not api_key:
        return text
    prompt = f"""صحّح هذا النص العربي: أصلح الأخطاء الإملائية، وأضف علامات التشكيل حيث يلزم، وحسّن الصياغة مع الحفاظ على المعنى الأصلي. أعد النص المحسّن فقط بدون شرح.

النص:
{text}"""
    result, _ = gemini_generate(prompt, api_key, status_fn)
    return result or text

# ════════════════════════════════════════════════════════════
# 📊  التحليل التنفيذي بـ Gemini
# ════════════════════════════════════════════════════════════
def build_analysis_prompt(tweet_data: Dict, mode: str) -> str:
    """يبني prompt التحليل بحسب الوضع المحدد."""

    author_info = tweet_data.get("author", "")
    username    = tweet_data.get("username", "") or tweet_data.get("url_username", "")
    is_retweet  = tweet_data.get("is_retweet", False)
    text        = tweet_data.get("text", "")
    tweet_id    = tweet_data.get("tweet_id", "")

    author_block = f"صاحب الحساب: {author_info} ({username})" if username else f"صاحب الحساب: {author_info}"
    if is_retweet:
        author_block += "\n⚠️ ملاحظة: هذا المنشور إعادة نشر (Retweet)"

    mode_instructions = {
        "executive": "ركّز على الجوانب الاستراتيجية والقرارات والمخاطر.",
        "media":     "ركّز على الأسلوب الإعلامي والرسائل التسويقية والجمهور المستهدف.",
        "security":  "ركّز على المخاطر الأمنية والتحريض والمعلومات المضللة.",
        "general":   "قدّم تحليلاً شاملاً ومتوازناً.",
    }
    focus = mode_instructions.get(mode, mode_instructions["general"])

    prompt = f"""أنت محلل ذكاء اصطناعي متخصص. حلّل المنشور التالي من منصة X وقدّم ملخصاً تنفيذياً احترافياً.

📌 بيانات المنشور:
{author_block}
معرّف المنشور: {tweet_id}

📝 محتوى المنشور:
{text if text else "(لا يوجد نص – قد يكون المحتوى صورة أو فيديو فقط)"}

🎯 تعليمات التحليل: {focus}

أعد النتيجة بصيغة JSON صحيحة تماماً بهذا الهيكل:
{{
  "executive_summary": "ملخص تنفيذي في 3-4 جمل",
  "key_points": ["النقطة الأولى", "النقطة الثانية", "النقطة الثالثة"],
  "risks": ["الخطر الأول", "الخطر الثاني"],
  "recommendations": ["التوصية الأولى", "التوصية الثانية"],
  "sentiment": "إيجابي | سلبي | محايد",
  "topics": ["الموضوع الأول", "الموضوع الثاني"],
  "is_retweet_note": "{('هذا إعادة نشر' if is_retweet else '')}"
}}

مهم: أعد JSON فقط بدون أي نص خارجه."""
    return prompt

def run_analysis(tweet_data: Dict, api_key: str, mode: str, status_fn=None) -> Dict:
    """يشغّل التحليل التنفيذي ويعيد النتيجة كـ dict."""
    default_error = {
        "executive_summary": "❌ فشل التحليل",
        "key_points": [], "risks": [], "recommendations": [],
        "sentiment": "غير محدد", "topics": [], "is_retweet_note": ""
    }

    if not api_key:
        default_error["executive_summary"] = "❌ أدخل مفتاح Gemini API من الشريط الجانبي"
        return default_error

    prompt = build_analysis_prompt(tweet_data, mode)

    if status_fn:
        status_fn("🧠 جارٍ التحليل بـ Gemini...")

    raw_text, used_model = gemini_generate(prompt, api_key, status_fn)

    if not raw_text:
        default_error["executive_summary"] = (
            "❌ فشل التحليل – أسباب محتملة:\n"
            "• تجاوز حصة الاستخدام المجانية (429) – انتظر دقيقة وأعد المحاولة\n"
            "• تحقق من صلاحية مفتاح API على https://aistudio.google.com/apikey"
        )
        return default_error

    # ── تحليل JSON ───────────────────────────────────────────
    try:
        # تنظيف الـ response
        clean = raw_text.strip()
        clean = re.sub(r"^```json\s*", "", clean)
        clean = re.sub(r"^```\s*",    "", clean)
        clean = re.sub(r"\s*```$",    "", clean)
        result = json.loads(clean)
        result["_model_used"] = used_model
        return result
    except json.JSONDecodeError:
        # استخرج JSON من النص إذا كان مدمجاً
        json_match = re.search(r"\{[\s\S]+\}", raw_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
                result["_model_used"] = used_model
                return result
            except Exception:
                pass
        default_error["executive_summary"] = f"⚠️ الاستجابة غير منظمة:\n{raw_text[:300]}"
        default_error["_model_used"] = used_model
        return default_error

# ════════════════════════════════════════════════════════════
# 🎨  CSS – واجهة RTL عربية
# ════════════════════════════════════════════════════════════
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');

* { font-family: 'Tajawal', 'Arial', sans-serif !important; }

/* ── اتجاه عام RTL ─────────────────────────────────────── */
html, body, .stApp { direction: rtl; text-align: right; }

/* ── عنوان التطبيق – مُوسَّط ────────────────────────────── */
.app-title {
    text-align: center !important;
    font-size: 2.5rem;
    font-weight: 900;
    background: linear-gradient(135deg, #1DA1F2, #0d47a1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding: 0.5rem 0;
    margin-bottom: 0.2rem;
}
.app-subtitle {
    text-align: center !important;
    color: #666;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

/* ── الشريط الجانبي ─────────────────────────────────────── */
[data-testid="stSidebar"] {
    direction: rtl !important;
    text-align: right !important;
}
[data-testid="stSidebar"] * {
    text-align: right !important;
    direction: rtl !important;
}

/* ── حقول الإدخال ───────────────────────────────────────── */
input, textarea, .stTextInput input, .stTextArea textarea {
    direction: rtl !important;
    text-align: right !important;
}

/* ── التبويبات ──────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { justify-content: flex-end; }
.stTabs [data-baseweb="tab"]      { direction: rtl; }

/* ── بطاقات النتائج ─────────────────────────────────────── */
.result-card {
    background: #f8f9fa;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin: 0.8rem 0;
    border-right: 4px solid #1DA1F2;
    direction: rtl;
    text-align: right;
}
.author-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, #1DA1F2, #0d47a1);
    color: white;
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 0.5rem;
}
.retweet-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #17bf63;
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    margin-right: 8px;
}
.model-badge {
    font-size: 0.75rem;
    color: #888;
    background: #eee;
    padding: 2px 8px;
    border-radius: 10px;
    float: left;
}
.sentiment-positive { color: #17bf63; font-weight: 700; }
.sentiment-negative { color: #e0245e; font-weight: 700; }
.sentiment-neutral  { color: #657786; font-weight: 700; }

/* ── قوائم النقاط ───────────────────────────────────────── */
.point-item {
    background: white;
    border-radius: 8px;
    padding: 8px 14px;
    margin: 4px 0;
    border: 1px solid #e1e8ed;
    direction: rtl;
}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# 🖥️  الواجهة الرئيسية
# ════════════════════════════════════════════════════════════
def display_analysis_results(analysis: Dict, tweet_data: Dict):
    """يعرض نتائج التحليل بشكل منسّق."""

    author   = tweet_data.get("author", "")
    username = tweet_data.get("username", "") or tweet_data.get("url_username", "")
    is_rt    = tweet_data.get("is_retweet", False)
    model    = analysis.get("_model_used", "")

    # ── شارة المؤلف ───────────────────────────────────────
    st.markdown("#### 👤 صاحب الحساب")
    author_html = f'<span class="author-badge">🐦 {author}'
    if username:
        author_html += f' &nbsp;|&nbsp; <span style="opacity:.8">{username}</span>'
    author_html += "</span>"
    if is_rt:
        author_html += ' <span class="retweet-badge">🔁 إعادة نشر</span>'
    if model:
        author_html += f' <span class="model-badge">🤖 {model}</span>'
    st.markdown(author_html, unsafe_allow_html=True)

    st.markdown("---")

    # ── الملخص التنفيذي ───────────────────────────────────
    st.markdown("#### 📋 الملخص التنفيذي")
    st.markdown(
        f'<div class="result-card">{analysis.get("executive_summary", "—")}</div>',
        unsafe_allow_html=True
    )

    # ── النقاط الرئيسية + المخاطر + التوصيات ──────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🎯 النقاط الرئيسية")
        for pt in analysis.get("key_points", []):
            st.markdown(f'<div class="point-item">• {pt}</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("#### ⚠️ المخاطر والتوصيات")
        for r in analysis.get("risks", []):
            st.markdown(f'<div class="point-item" style="border-color:#e0245e;">🔴 {r}</div>', unsafe_allow_html=True)
        for rec in analysis.get("recommendations", []):
            st.markdown(f'<div class="point-item" style="border-color:#17bf63;">✅ {rec}</div>', unsafe_allow_html=True)

    # ── المشاعر + الموضوعات ───────────────────────────────
    col3, col4 = st.columns(2)
    sentiment = analysis.get("sentiment", "محايد")
    sent_class = "sentiment-positive" if "إيجاب" in sentiment else \
                 "sentiment-negative" if "سلب"  in sentiment else "sentiment-neutral"
    with col3:
        st.markdown("#### 💡 المشاعر العامة")
        st.markdown(f'<p class="{sent_class}" style="font-size:1.4rem">{sentiment}</p>', unsafe_allow_html=True)
    with col4:
        st.markdown("#### 🏷️ الموضوعات")
        for topic in analysis.get("topics", []):
            st.markdown(f'<span style="background:#e8f5fd;padding:3px 10px;border-radius:12px;margin:3px;display:inline-block">{topic}</span>', unsafe_allow_html=True)

def main():
    st.set_page_config(
        page_title=f"{APP_EMOJI} {APP_NAME}",
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()

    # ── عنوان مُوسَّط ──────────────────────────────────────
    st.markdown(f'<h1 class="app-title">{APP_EMOJI} {APP_NAME}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="app-subtitle">تحليل منشورات X وتويتر بالذكاء الاصطناعي | v{APP_VERSION}</p>', unsafe_allow_html=True)

    # ════════════════════════════════════════════
    # الشريط الجانبي
    # ════════════════════════════════════════════
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
        st.info("""
**gemini-1.5-flash** ← الأفضل
• 15 طلب/دقيقة
• 1,500 طلب/يوم

**gemini-2.5-flash**
• 10 طلبات/دقيقة
• 250 طلب/يوم
        """)

        st.markdown("---")
        st.caption(f"v{APP_VERSION} | يستخدم: oEmbed + Nitter + yt-dlp")

    # ════════════════════════════════════════════
    # التبويبات الرئيسية
    # ════════════════════════════════════════════
    tab_link, tab_img, tab_guide = st.tabs(["🔗 تحليل رابط", "🖼️ تحليل صورة", "📖 دليل الاستخدام"])

    # ──────────────────────────────────────────
    # تبويب 1: تحليل رابط X
    # ──────────────────────────────────────────
    with tab_link:
        st.markdown("### 🔗 أدخل رابط منشور X")
        tweet_url_input = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/123456789",
            help="يقبل روابط x.com و twitter.com بجميع أشكالها"
        )

        if tweet_url_input:
            if is_tweet_url(tweet_url_input):
                tid = extract_tweet_id(tweet_url_input)
                uname = extract_username_from_url(tweet_url_input)
                st.success(f"✅ رابط صالح | الحساب: **{uname}** | معرّف المنشور: `{tid}`")
            else:
                st.error("❌ الرابط غير مدعوم – أدخل رابط x.com أو twitter.com")

        analyze_btn = st.button("🔍 تحليل المنشور", type="primary", use_container_width=True)

        if analyze_btn:
            if not tweet_url_input or not is_tweet_url(tweet_url_input):
                st.error("❌ أدخل رابطاً صالحاً أولاً")
            elif not api_key:
                st.error("❌ أدخل مفتاح Gemini API من الشريط الجانبي")
            else:
                status_container = st.empty()
                progress_bar     = st.progress(0)
                log_container    = st.expander("📋 سجل التنفيذ", expanded=False)
                log_lines        = []

                def update_status(msg):
                    status_container.info(f"⏳ {msg}")
                    log_lines.append(msg)
                    with log_container:
                        st.text("\n".join(log_lines[-10:]))

                # ── جلب البيانات ──────────────────────────
                progress_bar.progress(10)
                update_status("جارٍ جلب بيانات المنشور...")
                tweet_data = fetch_tweet_with_media(tweet_url_input, api_key, update_status)
                progress_bar.progress(40)

                # ── تحسين النص ────────────────────────────
                if improve_text and tweet_data.get("text"):
                    update_status("✨ تحسين النص العربي...")
                    tweet_data["text"] = improve_arabic_text(tweet_data["text"], api_key, update_status)
                progress_bar.progress(55)

                # ── OCR ───────────────────────────────────
                ocr_texts = []
                if enable_ocr and tweet_data.get("images"):
                    update_status(f"🖼️ تحليل {len(tweet_data['images'])} صورة...")
                    for img in tweet_data["images"][:3]:
                        t = ocr_image_tesseract(img) or ocr_image_gemini(img, api_key, update_status)
                        if t.strip():
                            ocr_texts.append(t)
                progress_bar.progress(70)

                # ── فيديو ─────────────────────────────────
                video_transcript = ""
                if enable_video and tweet_data.get("video_path"):
                    update_status("🎬 تحليل الفيديو...")
                    video_transcript = transcribe_video_gemini(tweet_data["video_path"], api_key, update_status)
                progress_bar.progress(80)

                # ── دمج المحتوى ───────────────────────────
                full_text = tweet_data.get("text", "")
                if ocr_texts:
                    full_text += "\n\n[نص من الصور]\n" + "\n".join(ocr_texts)
                if video_transcript:
                    full_text += "\n\n[تفريغ الفيديو]\n" + video_transcript
                tweet_data["text"] = full_text

                # ── التحليل ───────────────────────────────
                update_status("🧠 جارٍ التحليل التنفيذي...")
                analysis = run_analysis(tweet_data, api_key, analysis_mode, update_status)
                progress_bar.progress(100)
                status_container.success("✅ اكتمل التحليل!")

                st.markdown("---")
                display_analysis_results(analysis, tweet_data)

                # ── عرض النص الخام ────────────────────────
                with st.expander("📝 النص الكامل للمنشور", expanded=False):
                    st.text_area("", value=tweet_data.get("text", "(فارغ)"), height=150, disabled=True)

                # ── OCR texts ─────────────────────────────
                if ocr_texts:
                    with st.expander("🖼️ النصوص المستخرجة من الصور"):
                        for i, t in enumerate(ocr_texts, 1):
                            st.text_area(f"صورة {i}", value=t, height=80, disabled=True)

                # ── تفريغ الفيديو ─────────────────────────
                if video_transcript:
                    with st.expander("🎬 تفريغ الفيديو"):
                        st.text_area("", value=video_transcript, height=100, disabled=True)

                # ── تحميل النتائج ─────────────────────────
                export_data = {
                    "tweet_url":   tweet_url_input,
                    "tweet_data":  {k: v for k, v in tweet_data.items() if k != "video_path"},
                    "analysis":    analysis,
                    "ocr_texts":   ocr_texts,
                    "transcript":  video_transcript,
                }
                st.download_button(
                    label="💾 تحميل النتائج (JSON)",
                    data=json.dumps(export_data, ensure_ascii=False, indent=2),
                    file_name=f"analysis_{tweet_data.get('tweet_id','')}.json",
                    mime="application/json"
                )

    # ──────────────────────────────────────────
    # تبويب 2: تحليل صورة مباشر
    # ──────────────────────────────────────────
    with tab_img:
        st.markdown("### 🖼️ رفع صورة للتحليل المباشر")
        uploaded = st.file_uploader("ارفع صورة", type=["jpg", "jpeg", "png", "webp", "gif"])

        if uploaded and st.button("🔍 تحليل الصورة", type="primary"):
            if not api_key:
                st.error("❌ أدخل مفتاح Gemini API")
            else:
                with st.spinner("جارٍ التحليل..."):
                    # حفظ مؤقت
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                        tmp.write(uploaded.read())
                        tmp_path = tmp.name

                    # OCR + Gemini
                    ocr_text = ocr_image_tesseract(tmp_path)
                    prompt = f"""حلّل هذه الصورة وقدّم:
1. وصف المحتوى
2. النصوص المرئية
3. المعلومات الرئيسية
4. التوصيات

النص المستخرج تلقائياً: {ocr_text or '(لا يوجد)'}"""

                    img_data = open(tmp_path, "rb").read()
                    img_b64  = base64.b64encode(img_data).decode()
                    full_prompt = [prompt, {"mime_type": "image/jpeg", "data": img_b64}]

                    status_box = st.empty()
                    result, model = gemini_generate(full_prompt, api_key, lambda m: status_box.info(m))
                    os.unlink(tmp_path)

                    if result:
                        st.success(f"✅ التحليل مكتمل – النموذج: {model}")
                        st.markdown("---")
                        st.markdown(result)
                    else:
                        st.error("❌ فشل التحليل – راجع الإعدادات أو انتظر دقيقة وأعد المحاولة")

    # ──────────────────────────────────────────
    # تبويب 3: دليل الاستخدام
    # ──────────────────────────────────────────
    with tab_guide:
        st.markdown("""
### 📖 دليل الاستخدام

#### 🚀 البدء السريع
1. احصل على مفتاح Gemini مجاني من [Google AI Studio](https://aistudio.google.com/apikey)
2. أدخل المفتاح في الشريط الجانبي
3. الصق رابط المنشور وانقر **تحليل**

#### ✅ الروابط المدعومة
- `https://x.com/user/status/123456789`
- `https://x.com/user/status/123456789?s=20`
- `https://twitter.com/user/status/123456789`
- `https://www.twitter.com/user/status/123456789?ref=...`

#### ⚠️ حل مشكلة 429 (تجاوز الحصة)
| الحل | الوصف |
|---|---|
| انتظر دقيقة | الحد المجاني: 10-15 طلب/دقيقة |
| استخدم مفتاحاً جديداً | [أنشئ مفتاحاً جديداً](https://aistudio.google.com/apikey) |
| فعّل الفوترة | يرفع الحد إلى 1000 طلب/دقيقة |

#### 🤖 النماذج المتاحة (2025-2026)
| النموذج | RPM مجاني | RPD مجاني |
|---|---|---|
| gemini-1.5-flash ⭐ | 15 | 1,500 |
| gemini-1.5-flash-8b | 15 | 1,500 |
| gemini-2.5-flash | 10 | 250 |
| gemini-2.5-pro | 5 | 100 |
        """)

if __name__ == "__main__":
    main()
