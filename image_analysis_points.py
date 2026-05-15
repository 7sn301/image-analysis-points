# ═══════════════════════════════════════════════════════════════
# المشهد التنفيذي - Executive Scene Analyzer
# الإصدار: 6.7 | تحليل منشورات X بالذكاء الاصطناعي
# ═══════════════════════════════════════════════════════════════

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
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, urlencode, quote

# ── مكتبات اختيارية ──
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
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
# الإعدادات العامة
# ═══════════════════════════════════════════════════════════════
APP_NAME    = "المشهد التنفيذي"
APP_VERSION = "6.7"
APP_EMOJI   = "🎯"

GEMINI_MODELS = [
    {"name": "gemini-1.5-flash",      "rpm": 15,  "rpd": 1500},
    {"name": "gemini-1.5-flash-8b",   "rpm": 15,  "rpd": 1500},
    {"name": "gemini-2.5-flash",      "rpm": 10,  "rpd": 250},
    {"name": "gemini-2.5-flash-lite", "rpm": 10,  "rpd": 250},
    {"name": "gemini-2.5-pro",        "rpm": 5,   "rpd": 100},
]

OCR_LANG      = "ara+eng"
REQUEST_DELAY = 2
MAX_RETRIES   = 3

TWEET_URL_PATTERN   = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+",
    re.IGNORECASE
)
PROFILE_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/(?!search|hashtag|i/)(\w+)/?$",
    re.IGNORECASE
)

ACCOUNT_CATEGORIES = {
    "معادي":          {"icon": "🔴", "color": "#dc2626", "desc": "يعبّر عن معارضة صريحة أو عدائية"},
    "مشبوه":          {"icon": "🟠", "color": "#ea580c", "desc": "سلوك مثير للريبة أو غير طبيعي"},
    "محايد":          {"icon": "⚪", "color": "#6b7280", "desc": "لا يُظهر انحيازاً واضحاً"},
    "مواطن":          {"icon": "🟢", "color": "#16a34a", "desc": "مواطن عادي يتفاعل بشكل طبيعي"},
    "داعم":           {"icon": "💙", "color": "#2563eb", "desc": "يُبدي دعماً للمواقف الرسمية"},
    "إعلامي":         {"icon": "📰", "color": "#7c3aed", "desc": "صحفي أو وسيلة إعلامية"},
    "مستنجد":         {"icon": "🆘", "color": "#0891b2", "desc": "يطلب المساعدة أو يتقدم بشكاوى"},
    "ساخر":           {"icon": "😏", "color": "#b45309", "desc": "يستخدم السخرية والتهكم"},
    "متدخل خارجي":   {"icon": "🌐", "color": "#be185d", "desc": "حساب خارجي يتدخل في الشأن الداخلي"},
}

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.space",
]

# ═══════════════════════════════════════════════════════════════
# دوال مساعدة للروابط
# ═══════════════════════════════════════════════════════════════
def is_tweet_url(url: str) -> bool:
    return bool(TWEET_URL_PATTERN.match(url.strip()))

def is_profile_url(url: str) -> bool:
    return bool(PROFILE_URL_PATTERN.match(url.strip()))

def extract_tweet_id(url: str) -> Optional[str]:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None

def extract_username_from_url(url: str) -> Optional[str]:
    m = re.search(r"(?:twitter\.com|x\.com)/([^/?\s]+)", url, re.IGNORECASE)
    if m:
        u = m.group(1)
        if u.lower() not in ("search", "hashtag", "i", "intent", "home"):
            return u
    return None

def normalize_tweet_url(url: str) -> str:
    url = re.sub(r"\?.*$", "", url.strip())
    url = re.sub(r"x\.com", "twitter.com", url, flags=re.IGNORECASE)
    url = re.sub(r"^http://", "https://", url)
    return url

# ═══════════════════════════════════════════════════════════════
# إدارة Gemini والـ Retry
# ═══════════════════════════════════════════════════════════════
def exponential_backoff(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    return min(cap, base * (2 ** attempt) + random.uniform(0, 1))

def call_gemini_with_retry(model_obj, prompt: str, max_retries: int = MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            response = model_obj.generate_content(prompt)
            return response.text
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "rate" in err:
                wait = exponential_backoff(attempt)
                time.sleep(wait)
                continue
            elif "404" in err or "not found" in err:
                return None
            else:
                if attempt < max_retries - 1:
                    time.sleep(exponential_backoff(attempt))
                    continue
                return None
    return None

def gemini_generate(api_key: str, prompt: str, status_callback=None) -> Tuple[Optional[str], str]:
    if not GENAI_AVAILABLE:
        return None, "مكتبة google-generativeai غير مثبتة"
    genai.configure(api_key=api_key)
    for model_info in GEMINI_MODELS:
        model_name = model_info["name"]
        try:
            if status_callback:
                status_callback(f"⏳ جاري المحاولة مع نموذج: {model_name}")
            model = genai.GenerativeModel(model_name)
            result = call_gemini_with_retry(model, prompt)
            if result:
                return result, model_name
        except Exception as e:
            if status_callback:
                status_callback(f"⚠️ فشل {model_name}: {str(e)[:60]}")
        time.sleep(REQUEST_DELAY)
    return None, "فشلت جميع النماذج"

# ═══════════════════════════════════════════════════════════════
# كشف VPN
# ═══════════════════════════════════════════════════════════════
def detect_vpn_indicators(account_data: Dict) -> Dict:
    vpn_info = {
        "detected":    False,
        "risk_level":  "منخفض",
        "indicators":  [],
        "score":       0,
    }
    bio      = (account_data.get("bio", "") or "").lower()
    location = (account_data.get("location", "") or "").lower()

    vpn_keywords = ["vpn", "proxy", "tor", "anonymous", "privacy", "nordvpn",
                    "expressvpn", "surfshark", "hide", "tunnel"]
    for kw in vpn_keywords:
        if kw in bio:
            vpn_info["indicators"].append(f"كلمة مفتاحية في البيو: {kw}")
            vpn_info["score"] += 25

    suspicious_locations = ["netherlands", "هولندا", "uk", "المملكة المتحدة",
                            "switzerland", "سويسرا", "iceland", "آيسلندا",
                            "panama", "بنما"]
    for loc in suspicious_locations:
        if loc in location:
            vpn_info["indicators"].append(f"موقع مشبوه: {location}")
            vpn_info["score"] += 15
            break

    country_from_data = account_data.get("country", "")
    if country_from_data and location:
        if country_from_data.lower() not in location and location not in country_from_data.lower():
            vpn_info["indicators"].append("تعارض بين الموقع المُعلن والدولة المرصودة")
            vpn_info["score"] += 20

    if vpn_info["score"] >= 40:
        vpn_info["detected"]   = True
        vpn_info["risk_level"] = "عالٍ"
    elif vpn_info["score"] >= 20:
        vpn_info["detected"]   = True
        vpn_info["risk_level"] = "متوسط"

    return vpn_info

# ═══════════════════════════════════════════════════════════════
# جلب بيانات الحساب من Nitter
# ═══════════════════════════════════════════════════════════════
def fetch_account_details_nitter(username: str, api_key: str = "") -> Dict:
    account_data = {
        "username":       username,
        "display_name":   "",
        "user_id":        "",
        "bio":            "",
        "location":       "",
        "country":        "",
        "joined_date":    "",
        "verified":       False,
        "protected":      False,
        "followers":      0,
        "following":      0,
        "tweets_count":   0,
        "profile_image":  "",
        "pinned_tweet":   "",
        "recent_tweets":  [],
        "connected_via":  "",
        "vpn_info":       {},
        "fetch_status":   "pending",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en;q=0.9",
    }

    for mirror in NITTER_MIRRORS:
        try:
            url = f"{mirror}/{username}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            if not BS4_AVAILABLE:
                account_data["fetch_status"] = "bs4_missing"
                account_data["connected_via"] = mirror
                return account_data

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── الاسم والتوثيق ──
            name_el = soup.find("a", class_="profile-card-fullname")
            if name_el:
                account_data["display_name"] = name_el.get_text(strip=True)
            verified_el = soup.find("span", class_="verified-icon")
            if verified_el:
                account_data["verified"] = True

            # ── البيو ──
            bio_el = soup.find("div", class_="profile-bio")
            if bio_el:
                account_data["bio"] = bio_el.get_text(strip=True)

            # ── الإحصائيات ──
            stats = soup.find_all("li", class_="profile-stat-item")
            for stat in stats:
                num_el  = stat.find("span", class_="profile-stat-num")
                name_el2 = stat.find("span", class_="profile-stat-header")
                if num_el and name_el2:
                    val  = num_el.get_text(strip=True).replace(",", "")
                    kind = name_el2.get_text(strip=True).lower()
                    try:
                        int_val = int(val)
                        if "tweet" in kind or "منشور" in kind:
                            account_data["tweets_count"] = int_val
                        elif "follow" in kind and "ing" in kind:
                            account_data["following"] = int_val
                        elif "follow" in kind:
                            account_data["followers"] = int_val
                    except ValueError:
                        pass

            # ── الموقع ──
            loc_el = soup.find("div", class_="profile-location")
            if loc_el:
                account_data["location"] = loc_el.get_text(strip=True)

            # ── تاريخ الانضمام ──
            joined_el = soup.find("div", class_="profile-joindate")
            if joined_el:
                account_data["joined_date"] = joined_el.get_text(strip=True)

            # ── صورة الحساب ──
            img_el = soup.find("img", class_="profile-card-avatar")
            if img_el and img_el.get("src"):
                src = img_el["src"]
                if src.startswith("/"):
                    src = mirror + src
                account_data["profile_image"] = src

            # ── آخر التغريدات ──
            tweets_els = soup.find_all("div", class_="tweet-content", limit=5)
            for tw in tweets_els:
                account_data["recent_tweets"].append(tw.get_text(strip=True))

            # ── رقم الحساب (User ID) ──
            rss_link = soup.find("a", href=re.compile(r"/\w+/rss"))
            if rss_link:
                account_data["user_id"] = f"@{username}"
            for meta in soup.find_all("meta"):
                content = meta.get("content", "")
                if "twitter:creator:id" in str(meta) or "user_id" in str(meta):
                    account_data["user_id"] = content
                    break

            account_data["connected_via"] = mirror
            account_data["fetch_status"]  = "success"
            account_data["vpn_info"]      = detect_vpn_indicators(account_data)
            return account_data

        except Exception:
            continue

    account_data["fetch_status"] = "failed"
    return account_data

# ═══════════════════════════════════════════════════════════════
# جلب التغريدة
# ═══════════════════════════════════════════════════════════════
def fetch_via_oembed(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "author_url": "",
              "html": "", "media_urls": [], "error": None}
    try:
        api = "https://publish.twitter.com/oembed"
        params = {"url": tweet_url, "lang": "ar", "hide_thread": "false"}
        resp = requests.get(api, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result["author"]     = data.get("author_name", "")
            result["author_url"] = data.get("author_url", "")
            result["html"]       = data.get("html", "")
            html_text = re.sub(r"<[^>]+>", " ", result["html"])
            result["text"] = " ".join(html_text.split())
        else:
            result["error"] = f"oEmbed HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)
    return result

def fetch_via_nitter_tweet(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "images": [], "video": "", "error": None}
    tweet_id = extract_tweet_id(tweet_url)
    username = extract_username_from_url(tweet_url)
    if not tweet_id or not username:
        result["error"] = "تعذّر استخراج معرّف التغريدة أو اسم المستخدم"
        return result

    headers = {"User-Agent": "Mozilla/5.0"}
    for mirror in NITTER_MIRRORS:
        try:
            url  = f"{mirror}/{username}/status/{tweet_id}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            if not BS4_AVAILABLE:
                result["error"] = "bs4 غير متاح"
                return result
            soup = BeautifulSoup(resp.text, "html.parser")
            content_el = soup.find("div", class_="tweet-content")
            if content_el:
                result["text"] = content_el.get_text(strip=True)
            name_el = soup.find("a", class_="fullname")
            if name_el:
                result["author"] = name_el.get_text(strip=True)
            for img in soup.find_all("img", class_="still-image"):
                src = img.get("src", "")
                if src.startswith("/"):
                    src = mirror + src
                result["images"].append(src)
            return result
        except Exception:
            continue

    result["error"] = "فشلت جميع مرايا Nitter"
    return result

def download_media_yt_dlp(tweet_url: str, output_dir: str) -> List[str]:
    files = []
    if not shutil.which("yt-dlp"):
        return files
    try:
        cmd = ["yt-dlp", "--write-thumbnail", "-o",
               os.path.join(output_dir, "%(id)s.%(ext)s"), tweet_url]
        subprocess.run(cmd, capture_output=True, timeout=30)
        for f in Path(output_dir).iterdir():
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mkv"):
                files.append(str(f))
    except Exception:
        pass
    return files

def fetch_tweet_with_media(tweet_url: str) -> Dict:
    result = {
        "text": "", "author": "", "username": "",
        "images": [], "video": "", "source": "", "error": None
    }
    tweet_url = normalize_tweet_url(tweet_url)

    oembed = fetch_via_oembed(tweet_url)
    if not oembed.get("error") and oembed.get("text"):
        result["text"]     = oembed["text"]
        result["author"]   = oembed["author"]
        result["username"] = extract_username_from_url(oembed.get("author_url", "")) or \
                             extract_username_from_url(tweet_url) or ""
        result["source"]   = "oEmbed"

    if not result["text"]:
        nitter = fetch_via_nitter_tweet(tweet_url)
        if not nitter.get("error") and nitter.get("text"):
            result["text"]   = nitter["text"]
            result["author"] = nitter["author"]
            result["images"] = nitter["images"]
            result["source"] = "Nitter"

    if not result["username"]:
        result["username"] = extract_username_from_url(tweet_url) or ""

    return result

# ═══════════════════════════════════════════════════════════════
# OCR والفيديو
# ═══════════════════════════════════════════════════════════════
def ocr_image_tesseract(image_path: str) -> str:
    if not TESSERACT_AVAILABLE or not PIL_AVAILABLE:
        return ""
    try:
        img  = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=OCR_LANG)
        return text.strip()
    except Exception:
        return ""

def ocr_image_gemini(image_path: str, api_key: str) -> str:
    if not GENAI_AVAILABLE or not PIL_AVAILABLE:
        return ""
    try:
        genai.configure(api_key=api_key)
        img   = Image.open(image_path)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp  = model.generate_content(
            ["استخرج كل النصوص الموجودة في هذه الصورة بدقة:", img]
        )
        return resp.text.strip()
    except Exception:
        return ""

def transcribe_video_gemini(video_path: str, api_key: str) -> str:
    if not GENAI_AVAILABLE:
        return ""
    try:
        genai.configure(api_key=api_key)
        with open(video_path, "rb") as f:
            video_data = f.read()
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp  = model.generate_content([
            "فرّغ محتوى هذا الفيديو نصياً بالكامل:",
            {"mime_type": "video/mp4", "data": base64.b64encode(video_data).decode()}
        ])
        return resp.text.strip()
    except Exception:
        return ""

def improve_arabic_text(text: str, api_key: str) -> str:
    if not text or not api_key:
        return text
    prompt = (
        "حسّن النص العربي التالي من حيث التشكيل والإملاء، "
        "مع الحفاظ على المعنى الأصلي:\n\n" + text
    )
    result, _ = gemini_generate(api_key, prompt)
    return result or text

# ═══════════════════════════════════════════════════════════════
# بناء الـ Prompts
# ═══════════════════════════════════════════════════════════════
def build_analysis_prompt(tweet_text: str, mode: str = "executive",
                           ocr_text: str = "", video_transcript: str = "",
                           username: str = "") -> str:
    extra = ""
    if ocr_text:
        extra += f"\n\n📸 نصوص مستخرجة من الصور:\n{ocr_text}"
    if video_transcript:
        extra += f"\n\n🎥 نص الفيديو:\n{video_transcript}"

    mode_instructions = {
        "executive": "أجرِ تحليلاً تنفيذياً استخباراتياً شاملاً",
        "media":     "أجرِ تحليلاً إعلامياً وتحقق من صحة المحتوى",
        "security":  "أجرِ تحليلاً أمنياً مفصلاً للمخاطر والتهديدات",
        "general":   "أجرِ تحليلاً عاماً شاملاً",
    }
    instruction = mode_instructions.get(mode, mode_instructions["executive"])

    return f"""أنت محلل استخباراتي متخصص. {instruction} للمنشور التالي من منصة X.

المستخدم: @{username}
المحتوى: {tweet_text}{extra}

أعد الرد بصيغة JSON فقط (بدون أي نص خارج JSON):
{{
  "executive_summary": "ملخص تنفيذي شامل في 3-5 جمل",
  "key_points": ["نقطة 1", "نقطة 2", "نقطة 3"],
  "risks": ["خطر 1", "خطر 2"],
  "recommendations": ["توصية 1", "توصية 2"],
  "sentiment": "إيجابي/سلبي/محايد",
  "sentiment_score": 75,
  "topics": ["موضوع 1", "موضوع 2"],
  "urgency_level": "عالٍ/متوسط/منخفض",
  "credibility_score": 80,
  "analysis_mode": "{mode}"
}}"""

def build_profile_analysis_prompt(account_data: Dict) -> str:
    recent = "\n".join(account_data.get("recent_tweets", [])[:3])
    return f"""أنت محلل استخباراتي متخصص في تحليل الهوية الرقمية.

بيانات الحساب:
- الاسم: {account_data.get('display_name', '')}
- المعرّف: @{account_data.get('username', '')}
- البيو: {account_data.get('bio', '')}
- الموقع: {account_data.get('location', '')}
- تاريخ الانضمام: {account_data.get('joined_date', '')}
- المتابعون: {account_data.get('followers', 0)}
- التغريدات الأخيرة:
{recent}

بناءً على هذه البيانات، صنّف طبيعة الحساب وأعد الرد بصيغة JSON فقط:
{{
  "primary_category": "معادي/مشبوه/محايد/مواطن/داعم/إعلامي/مستنجد/ساخر/متدخل خارجي",
  "risk_level": "عالٍ/متوسط/منخفض",
  "scores": {{
    "hostility": 0,
    "authenticity": 0,
    "influence": 0,
    "external_interference": 0
  }},
  "summary": "ملخص تحليل الحساب",
  "patterns": ["نمط 1", "نمط 2"],
  "recommendations": ["توصية 1", "توصية 2"],
  "origin_guess": "الدولة المحتملة",
  "influence_level": "عالٍ/متوسط/منخفض"
}}"""

# ═══════════════════════════════════════════════════════════════
# تنفيذ التحليل
# ═══════════════════════════════════════════════════════════════
def run_analysis(tweet_text: str, api_key: str, mode: str = "executive",
                  ocr_text: str = "", video_transcript: str = "",
                  username: str = "", status_callback=None) -> Dict:
    prompt = build_analysis_prompt(tweet_text, mode, ocr_text, video_transcript, username)
    raw, model_used = gemini_generate(api_key, prompt, status_callback)
    if not raw:
        return {"error": "فشل التحليل - تحقق من مفتاح API"}

    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        data["_model_used"] = model_used
        return data
    except json.JSONDecodeError:
        return {"executive_summary": raw, "_model_used": model_used, "_raw": True}

def analyze_account_profile(account_data: Dict, api_key: str,
                              status_callback=None) -> Dict:
    prompt = build_profile_analysis_prompt(account_data)
    raw, model_used = gemini_generate(api_key, prompt, status_callback)
    if not raw:
        return {"error": "فشل تحليل الحساب"}
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        data["_model_used"] = model_used
        return data
    except json.JSONDecodeError:
        return {"summary": raw, "_model_used": model_used}

# ═══════════════════════════════════════════════════════════════
# CSS - تصميم شامل (ليلي/نهاري) + v6.7
# ═══════════════════════════════════════════════════════════════
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');

/* ── متغيرات الألوان ── */
:root {
    --primary:       #1DA1F2;
    --primary-dark:  #0d8bd1;
    --accent:        #F0B429;
    --success:       #16a34a;
    --danger:        #dc2626;
    --warning:       #ea580c;
    --bg-card:       #ffffff;
    --bg-section:    #f8fafc;
    --text-main:     #0f172a;
    --text-sub:      #334155;
    --text-muted:    #64748b;
    --border:        #e2e8f0;
    --shadow:        0 4px 24px rgba(0,0,0,0.10);
    --radius:        16px;
}

/* ── الخط العام ── */
* { font-family: 'Tajawal', sans-serif !important; box-sizing: border-box; }
html, body, .stApp { direction: rtl; text-align: right; }

/* ════════════════════════════════════
   الوضع الليلي (Dark Mode)
════════════════════════════════════ */
@media (prefers-color-scheme: dark) {
    :root {
        --bg-card:    #1e293b;
        --bg-section: #0f172a;
        --text-main:  #f1f5f9;
        --text-sub:   #cbd5e1;
        --text-muted: #94a3b8;
        --border:     #334155;
        --shadow:     0 4px 24px rgba(0,0,0,0.40);
    }
}

/* ── الخلفية العامة ── */
.stApp {
    background: var(--bg-section) !important;
    color: var(--text-main) !important;
}

/* ════════════════════════════════════
   الشريط الجانبي - موسّع ومكبّر
════════════════════════════════════ */
section[data-testid="stSidebar"] {
    width: 360px !important;
    min-width: 360px !important;
    background: linear-gradient(180deg, #0f2b46 0%, #1a3a5c 50%, #0f2b46 100%) !important;
    border-left: 3px solid var(--primary) !important;
    padding: 0 !important;
}
section[data-testid="stSidebar"] > div:first-child {
    padding: 20px 18px !important;
}
section[data-testid="stSidebar"] * {
    color: #ffffff !important;
    font-size: 17px !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F0B429 !important;
    font-size: 20px !important;
    font-weight: 800 !important;
}
section[data-testid="stSidebar"] label {
    color: #e2e8f0 !important;
    font-size: 16px !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select,
section[data-testid="stSidebar"] textarea {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    font-size: 16px !important;
    padding: 10px 14px !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    color: #ffffff !important;
    font-size: 16px !important;
}
section[data-testid="stSidebar"] .stCheckbox label {
    font-size: 16px !important;
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] .sidebar-logo {
    text-align: center;
    padding: 24px 0 16px;
    font-size: 52px;
    line-height: 1;
}
section[data-testid="stSidebar"] .sidebar-title {
    text-align: center;
    font-size: 24px !important;
    font-weight: 900 !important;
    color: #F0B429 !important;
    margin-bottom: 4px;
}
section[data-testid="stSidebar"] .sidebar-version {
    text-align: center;
    font-size: 13px !important;
    color: rgba(255,255,255,0.55) !important;
    margin-bottom: 20px;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.2) !important;
    margin: 16px 0 !important;
}
section[data-testid="stSidebar"] .limit-table {
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 12px;
    font-size: 14px !important;
}
section[data-testid="stSidebar"] .limit-row {
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    font-size: 14px !important;
}

/* ════════════════════════════════════
   عنوان الصفحة الرئيسية
════════════════════════════════════ */
.app-header {
    background: linear-gradient(135deg, #0f2b46 0%, #1DA1F2 50%, #0f2b46 100%);
    padding: 32px 40px;
    border-radius: 20px;
    text-align: center;
    margin-bottom: 28px;
    box-shadow: 0 8px 40px rgba(29,161,242,0.3);
}
.app-header .title {
    font-size: 42px !important;
    font-weight: 900 !important;
    color: #ffffff !important;
    letter-spacing: 1px;
    margin: 0;
}
.app-header .subtitle {
    font-size: 18px !important;
    color: rgba(255,255,255,0.75) !important;
    margin-top: 8px;
}
.app-header .version-badge {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    color: #F0B429 !important;
    font-size: 14px !important;
    font-weight: 700;
    padding: 4px 14px;
    border-radius: 20px;
    margin-top: 10px;
    border: 1px solid rgba(240,180,41,0.5);
}

/* ════════════════════════════════════
   بطاقة بيانات الحساب - v6.7 محدّثة
════════════════════════════════════ */
.account-card {
    background: linear-gradient(135deg, #0f2b46 0%, #1a4a7a 50%, #0d8bd1 100%);
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 8px 40px rgba(29,161,242,0.25);
    direction: rtl;
    position: relative;
    overflow: hidden;
}
.account-card::before {
    content: '';
    position: absolute;
    top: -40px; left: -40px;
    width: 200px; height: 200px;
    background: rgba(255,255,255,0.05);
    border-radius: 50%;
}
.account-card-header {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-bottom: 20px;
}
.account-avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    border: 3px solid rgba(255,255,255,0.5);
    object-fit: cover;
    flex-shrink: 0;
}
.account-avatar-placeholder {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    border: 3px solid rgba(255,255,255,0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 36px;
    flex-shrink: 0;
}
.account-name {
    font-size: 26px !important;
    font-weight: 900 !important;
    color: #ffffff !important;
    margin: 0 0 4px 0;
    line-height: 1.2;
}
.account-username {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #93c5fd !important;
    margin: 0 0 6px 0;
}
/* ── معرّف الحساب ID - v6.7 ── */
.account-id-badge {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.35);
    border-radius: 8px;
    padding: 5px 14px;
    font-size: 16px !important;
    font-weight: 800 !important;
    color: #ffffff !important;
    letter-spacing: 0.5px;
    margin-top: 4px;
}
.account-id-badge .id-label {
    color: #93c5fd !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    margin-left: 6px;
}
/* ── شارة التوثيق ── */
.verified-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(29,161,242,0.3);
    border: 1px solid rgba(29,161,242,0.6);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    margin-top: 6px;
    margin-left: 8px;
}
.unverified-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(107,114,128,0.3);
    border: 1px solid rgba(107,114,128,0.5);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 15px !important;
    font-weight: 600 !important;
    color: #d1d5db !important;
    margin-top: 6px;
    margin-left: 8px;
}
/* ── حاوية الإحصائيات ── */
.account-stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 20px 0;
}
.stat-box {
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 12px;
    padding: 14px 10px;
    text-align: center;
}
.stat-box .stat-num {
    font-size: 26px !important;
    font-weight: 900 !important;
    color: #ffffff !important;
    display: block;
    line-height: 1.1;
}
.stat-box .stat-label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: rgba(255,255,255,0.65) !important;
    margin-top: 4px;
    display: block;
}
/* ── تفاصيل الحساب (صف واحد لكل معلومة) ── */
.account-details-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 16px;
}
.detail-item {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.detail-item .detail-icon {
    font-size: 20px;
    flex-shrink: 0;
}
.detail-item .detail-content {}
.detail-item .detail-label {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: rgba(255,255,255,0.55) !important;
    display: block;
    margin-bottom: 2px;
}
.detail-item .detail-value {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    display: block;
}
/* ── VPN بادج ── */
.vpn-alert {
    margin-top: 16px;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 16px !important;
    font-weight: 700 !important;
}
.vpn-high    { background: rgba(220,38,38,0.25); border: 1px solid rgba(220,38,38,0.5); color: #fca5a5 !important; }
.vpn-medium  { background: rgba(234,88,12,0.25); border: 1px solid rgba(234,88,12,0.5); color: #fdba74 !important; }
.vpn-low     { background: rgba(22,163,74,0.20); border: 1px solid rgba(22,163,74,0.4); color: #86efac !important; }

/* ════════════════════════════════════
   بطاقة الملخص التنفيذي
════════════════════════════════════ */
.summary-card {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a4a7a 100%);
    border-right: 6px solid var(--primary);
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
    direction: rtl;
    box-shadow: var(--shadow);
}
.summary-card .card-title {
    font-size: 22px !important;
    font-weight: 900 !important;
    color: #F0B429 !important;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.summary-card .summary-text {
    font-size: 18px !important;
    font-weight: 500 !important;
    color: #f1f5f9 !important;
    line-height: 1.9 !important;
}

/* ════════════════════════════════════
   نقاط التحليل الرئيسية
════════════════════════════════════ */
.section-card {
    background: var(--bg-card);
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    direction: rtl;
}
.section-title {
    font-size: 20px !important;
    font-weight: 800 !important;
    color: var(--primary) !important;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 2px solid var(--border);
    padding-bottom: 10px;
}
.point-item {
    background: var(--bg-section);
    border-right: 4px solid var(--primary);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
    font-size: 17px !important;
    font-weight: 500 !important;
    color: var(--text-main) !important;
    line-height: 1.7;
    direction: rtl;
}
/* ── المخاطر ── */
.risk-item {
    background: rgba(220,38,38,0.08);
    border-right: 4px solid #dc2626;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
    font-size: 17px !important;
    font-weight: 500 !important;
    color: var(--text-main) !important;
    line-height: 1.7;
    direction: rtl;
}
/* ── التوصيات ── */
.rec-item {
    background: rgba(22,163,74,0.08);
    border-right: 4px solid #16a34a;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
    font-size: 17px !important;
    font-weight: 500 !important;
    color: var(--text-main) !important;
    line-height: 1.7;
    direction: rtl;
}

/* ════════════════════════════════════
   بطاقة المشاعر
════════════════════════════════════ */
.sentiment-card {
    background: var(--bg-card);
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    direction: rtl;
    text-align: center;
}
.sentiment-value {
    font-size: 36px !important;
    font-weight: 900 !important;
    color: var(--primary) !important;
    display: block;
    margin: 12px 0;
}
.sentiment-score {
    font-size: 22px !important;
    font-weight: 800 !important;
    color: var(--text-sub) !important;
}
.sentiment-positive { color: #16a34a !important; }
.sentiment-negative { color: #dc2626 !important; }
.sentiment-neutral  { color: #64748b !important; }

/* ════════════════════════════════════
   الموضوعات
════════════════════════════════════ */
.topic-tag {
    display: inline-block;
    background: rgba(29,161,242,0.12);
    color: var(--primary) !important;
    border: 1px solid rgba(29,161,242,0.35);
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 15px !important;
    font-weight: 700 !important;
    margin: 4px;
}

/* ════════════════════════════════════
   نقاط التحليل للحساب
════════════════════════════════════ */
.profile-score-bar {
    direction: ltr;
    margin-bottom: 14px;
}
.profile-score-label {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: var(--text-main) !important;
    margin-bottom: 5px;
    direction: rtl;
}
.category-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border-radius: 30px;
    font-size: 20px !important;
    font-weight: 900 !important;
    color: #ffffff !important;
    margin-bottom: 12px;
}

/* ════════════════════════════════════
   أزرار وتابات
════════════════════════════════════ */
.stButton > button {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 28px !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    width: 100%;
    box-shadow: 0 4px 16px rgba(29,161,242,0.35);
    transition: all 0.2s ease;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(29,161,242,0.5) !important;
}
.stTabs [role="tab"] {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: var(--text-sub) !important;
    padding: 12px 20px !important;
}
.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom: 3px solid var(--primary) !important;
}
.stTextInput input, .stTextArea textarea {
    font-size: 17px !important;
    font-weight: 500 !important;
    color: var(--text-main) !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
    border: 2px solid var(--border) !important;
    direction: rtl;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(29,161,242,0.15) !important;
}
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--primary), #0d8bd1) !important;
    border-radius: 10px !important;
}
.status-box {
    background: rgba(29,161,242,0.08);
    border: 1px solid rgba(29,161,242,0.25);
    border-radius: 12px;
    padding: 12px 18px;
    font-size: 16px !important;
    color: var(--primary) !important;
    font-weight: 600 !important;
    margin-bottom: 12px;
    direction: rtl;
}

/* ════════════════════════════════════
   وضع إجباري لألوان النصوص
════════════════════════════════════ */
p, span, li, div, h1, h2, h3, h4, h5, h6, label, td, th {
    color: var(--text-main);
}
.stMarkdown p { font-size: 16px !important; line-height: 1.8; }
.stAlert p, .stAlert div { color: var(--text-main) !important; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض بطاقة بيانات الحساب - v6.7 محدّثة
# ═══════════════════════════════════════════════════════════════
def display_account_info_card(account_data: Dict):
    username     = account_data.get("username", "")
    display_name = account_data.get("display_name", username)
    user_id      = account_data.get("user_id", "")
    bio          = account_data.get("bio", "")
    location     = account_data.get("location", "غير محدد")
    country      = account_data.get("country", "")
    joined_date  = account_data.get("joined_date", "غير محدد")
    verified     = account_data.get("verified", False)
    protected    = account_data.get("protected", False)
    followers    = account_data.get("followers", 0)
    following    = account_data.get("following", 0)
    tweets_count = account_data.get("tweets_count", 0)
    profile_img  = account_data.get("profile_image", "")
    connected_via= account_data.get("connected_via", "")
    vpn_info     = account_data.get("vpn_info", {})

    # ── تنسيق الأرقام ──
    def fmt(n):
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)

    # ── Avatar ──
    if profile_img:
        avatar_html = f'<img src="{profile_img}" class="account-avatar" onerror="this.style.display=\'none\'">'
    else:
        avatar_html = '<div class="account-avatar-placeholder">👤</div>'

    # ── شارة التوثيق ──
    if verified:
        verification_html = '<span class="verified-badge">✅ حساب موثَّق</span>'
    else:
        verification_html = '<span class="unverified-badge">⚪ غير موثَّق</span>'

    # ── شارة الحماية ──
    protected_html = ""
    if protected:
        protected_html = '<span class="unverified-badge" style="border-color:rgba(240,180,41,0.5);color:#F0B429!important;">🔒 محمي</span>'

    # ── معرّف الحساب ──
    id_html = ""
    if user_id:
        id_html = f'''
        <div class="account-id-badge">
            <span class="id-label">🪪 معرّف الحساب:</span>
            <span style="color:#ffffff!important;font-size:16px!important;font-weight:800!important;">{user_id}</span>
        </div>'''

    # ── حاوية الإحصائيات الثلاثية ──
    stats_html = f"""
    <div class="account-stats-grid">
        <div class="stat-box">
            <span class="stat-num">{fmt(followers)}</span>
            <span class="stat-label">👥 المتابعون</span>
        </div>
        <div class="stat-box">
            <span class="stat-num">{fmt(following)}</span>
            <span class="stat-label">➡️ يتابع</span>
        </div>
        <div class="stat-box">
            <span class="stat-num">{fmt(tweets_count)}</span>
            <span class="stat-label">📝 المنشورات</span>
        </div>
    </div>"""

    # ── تفاصيل الحساب ──
    display_country = country if country else (location if location != "غير محدد" else "غير محدد")
    details_html = f"""
    <div class="account-details-grid">
        <div class="detail-item">
            <span class="detail-icon">📅</span>
            <div class="detail-content">
                <span class="detail-label">تاريخ الانضمام</span>
                <span class="detail-value">{joined_date}</span>
            </div>
        </div>
        <div class="detail-item">
            <span class="detail-icon">📍</span>
            <div class="detail-content">
                <span class="detail-label">الحساب موجود في</span>
                <span class="detail-value">{display_country}</span>
            </div>
        </div>
        <div class="detail-item">
            <span class="detail-icon">🔗</span>
            <div class="detail-content">
                <span class="detail-label">مصدر البيانات</span>
                <span class="detail-value" style="font-size:13px!important;">{connected_via.replace("https://","") if connected_via else "غير متاح"}</span>
            </div>
        </div>
        <div class="detail-item">
            <span class="detail-icon">📊</span>
            <div class="detail-content">
                <span class="detail-label">نسبة المتابعة</span>
                <span class="detail-value">{round(followers/max(following,1),1)}x</span>
            </div>
        </div>
    </div>"""

    # ── VPN ──
    vpn_html = ""
    if vpn_info:
        risk = vpn_info.get("risk_level", "منخفض")
        detected = vpn_info.get("detected", False)
        indicators = vpn_info.get("indicators", [])
        css_class = {"عالٍ": "vpn-high", "متوسط": "vpn-medium"}.get(risk, "vpn-low")
        vpn_icon  = "🔴" if risk == "عالٍ" else ("🟠" if risk == "متوسط" else "🟢")
        ind_text  = " | ".join(indicators[:2]) if indicators else "لا توجد مؤشرات"
        vpn_html  = f"""
        <div class="vpn-alert {css_class}">
            {vpn_icon} كاشف VPN — خطورة: <strong>{risk}</strong>
            {"✅ لا يُرجَّح استخدام VPN" if not detected else "⚠️ يُرجَّح استخدام VPN"}
            <br><small style="font-size:13px!important;opacity:0.8;">{ind_text}</small>
        </div>"""

    # ── البناء الكامل ──
    card_html = f"""
    <div class="account-card">
        <div class="account-card-header">
            {avatar_html}
            <div style="flex:1;">
                <div class="account-name">{display_name}</div>
                <div class="account-username">@{username}</div>
                {id_html}
                <div style="margin-top:8px;">
                    {verification_html}
                    {protected_html}
                </div>
            </div>
        </div>
        {f'<p style="font-size:16px!important;color:rgba(255,255,255,0.8)!important;margin:0 0 16px;line-height:1.7;">{bio}</p>' if bio else ""}
        {stats_html}
        {details_html}
        {vpn_html}
    </div>"""

    st.markdown(card_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض نتائج التحليل
# ═══════════════════════════════════════════════════════════════
def display_analysis_results(analysis: Dict, username: str = ""):
    if "error" in analysis:
        st.error(f"❌ {analysis['error']}")
        return

    model_used = analysis.get("_model_used", "")
    if model_used and not analysis.get("_raw"):
        st.markdown(
            f'<div class="status-box">🤖 تم التحليل بواسطة: <strong>{model_used}</strong></div>',
            unsafe_allow_html=True
        )

    # ── ملخص تنفيذي ──
    summary = analysis.get("executive_summary", "")
    if summary:
        st.markdown(f"""
        <div class="summary-card">
            <div class="card-title">📋 الملخص التنفيذي</div>
            <p class="summary-text">{summary}</p>
        </div>""", unsafe_allow_html=True)

    # ── نقاط رئيسية + مخاطر + توصيات ──
    col1, col2 = st.columns(2)
    with col1:
        points = analysis.get("key_points", [])
        if points:
            items_html = "".join(f'<div class="point-item">🔹 {p}</div>' for p in points)
            st.markdown(f"""
            <div class="section-card">
                <div class="section-title">🎯 النقاط الرئيسية</div>
                {items_html}
            </div>""", unsafe_allow_html=True)

    with col2:
        risks = analysis.get("risks", [])
        if risks:
            items_html = "".join(f'<div class="risk-item">⚠️ {r}</div>' for r in risks)
            st.markdown(f"""
            <div class="section-card">
                <div class="section-title" style="color:#dc2626!important;">⚠️ المخاطر</div>
                {items_html}
            </div>""", unsafe_allow_html=True)

    recs = analysis.get("recommendations", [])
    if recs:
        items_html = "".join(f'<div class="rec-item">✅ {r}</div>' for r in recs)
        st.markdown(f"""
        <div class="section-card">
            <div class="section-title" style="color:#16a34a!important;">💡 التوصيات</div>
            {items_html}
        </div>""", unsafe_allow_html=True)

    # ── المشاعر ──
    sentiment = analysis.get("sentiment", "")
    score     = analysis.get("sentiment_score", 0)
    urgency   = analysis.get("urgency_level", "")
    credibility = analysis.get("credibility_score", 0)
    if sentiment:
        sent_class = (
            "sentiment-positive" if "إيجابي" in sentiment else
            "sentiment-negative" if "سلبي"   in sentiment else
            "sentiment-neutral"
        )
        sent_icon = "😊" if "إيجابي" in sentiment else ("😟" if "سلبي" in sentiment else "😐")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="sentiment-card">
                <div class="section-title" style="justify-content:center;">🎭 المشاعر العامة</div>
                <span class="sentiment-value {sent_class}">{sent_icon} {sentiment}</span>
                <span class="sentiment-score">نسبة: {score}%</span>
            </div>""", unsafe_allow_html=True)
        with col2:
            urgency_color = "#dc2626" if urgency == "عالٍ" else ("#ea580c" if urgency == "متوسط" else "#16a34a")
            st.markdown(f"""
            <div class="sentiment-card">
                <div class="section-title" style="justify-content:center;">🚨 مستوى الإلحاح</div>
                <span class="sentiment-value" style="color:{urgency_color}!important;">{urgency}</span>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="sentiment-card">
                <div class="section-title" style="justify-content:center;">🔍 المصداقية</div>
                <span class="sentiment-value">{credibility}%</span>
            </div>""", unsafe_allow_html=True)

    # ── الموضوعات ──
    topics = analysis.get("topics", [])
    if topics:
        tags_html = "".join(f'<span class="topic-tag">{t}</span>' for t in topics)
        st.markdown(f"""
        <div class="section-card">
            <div class="section-title">🏷️ الموضوعات</div>
            <div style="direction:rtl;">{tags_html}</div>
        </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض نتائج تحليل الملف الشخصي
# ═══════════════════════════════════════════════════════════════
def display_profile_analysis(profile_analysis: Dict):
    if "error" in profile_analysis:
        st.error(f"❌ {profile_analysis['error']}")
        return

    category = profile_analysis.get("primary_category", "محايد")
    cat_info  = ACCOUNT_CATEGORIES.get(category, {"icon": "⚪", "color": "#6b7280", "desc": ""})
    risk      = profile_analysis.get("risk_level", "")
    summary   = profile_analysis.get("summary", "")
    scores    = profile_analysis.get("scores", {})
    patterns  = profile_analysis.get("patterns", [])
    recs      = profile_analysis.get("recommendations", [])
    origin    = profile_analysis.get("origin_guess", "")
    influence = profile_analysis.get("influence_level", "")
    model     = profile_analysis.get("_model_used", "")

    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">🎯 تحليل طبيعة الحساب</div>
        <div style="text-align:center;margin-bottom:16px;">
            <span class="category-badge" style="background:{cat_info['color']};">
                {cat_info['icon']} {category}
            </span>
            <p style="font-size:16px!important;color:var(--text-sub)!important;margin:8px 0;">{cat_info['desc']}</p>
        </div>
        {f'<div class="summary-card"><p class="summary-text">{summary}</p></div>' if summary else ""}
    </div>""", unsafe_allow_html=True)

    if scores:
        st.markdown('<div class="section-card"><div class="section-title">📊 مؤشرات التقييم</div>', unsafe_allow_html=True)
        score_labels = {
            "hostility":             ("🔴 مستوى العدائية",  "#dc2626"),
            "authenticity":          ("✅ الأصالة",          "#16a34a"),
            "influence":             ("📢 التأثير",          "#2563eb"),
            "external_interference": ("🌐 التدخل الخارجي",  "#be185d"),
        }
        for key, val in scores.items():
            label, color = score_labels.get(key, (key, "#1DA1F2"))
            st.markdown(f'<div class="profile-score-label">{label}: {val}%</div>', unsafe_allow_html=True)
            st.progress(min(int(val), 100) / 100)
        st.markdown('</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if patterns:
            items = "".join(f'<div class="point-item">🔹 {p}</div>' for p in patterns)
            st.markdown(f'<div class="section-card"><div class="section-title">🔍 الأنماط المرصودة</div>{items}</div>', unsafe_allow_html=True)
    with col2:
        if recs:
            items = "".join(f'<div class="rec-item">✅ {r}</div>' for r in recs)
            st.markdown(f'<div class="section-card"><div class="section-title">💡 التوصيات</div>{items}</div>', unsafe_allow_html=True)

    extra_info = []
    if origin:    extra_info.append(f"🌍 الدولة المحتملة: <strong>{origin}</strong>")
    if influence: extra_info.append(f"📢 مستوى التأثير: <strong>{influence}</strong>")
    if risk:      extra_info.append(f"⚡ مستوى الخطورة: <strong>{risk}</strong>")
    if model:     extra_info.append(f"🤖 النموذج: <strong>{model}</strong>")
    if extra_info:
        content = " &nbsp;|&nbsp; ".join(extra_info)
        st.markdown(f'<div class="status-box" style="font-size:15px!important;">{content}</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# الواجهة الرئيسية
# ═══════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_EMOJI}",
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    # ══════════════════════════════
    # الشريط الجانبي
    # ══════════════════════════════
    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-logo">{APP_EMOJI}</div>
        <div class="sidebar-title">{APP_NAME}</div>
        <div class="sidebar-version">الإصدار {APP_VERSION} — تحليل استخباراتي</div>
        <hr>
        """, unsafe_allow_html=True)

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاح مجاني من aistudio.google.com/apikey"
        )

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("**⚙️ إعدادات التحليل**")

        analysis_mode = st.selectbox(
            "🎯 وضع التحليل",
            options=["executive", "media", "security", "general"],
            format_func=lambda x: {
                "executive": "📋 تنفيذي - شامل",
                "media":     "📰 إعلامي - تحقق",
                "security":  "🔒 أمني - مخاطر",
                "general":   "🔍 عام",
            }[x]
        )

        enable_ocr       = st.checkbox("🔤 تفعيل OCR (تحليل الصور)", value=False)
        enable_video     = st.checkbox("🎥 تفعيل تحليل الفيديو",    value=False)
        enable_profile   = st.checkbox("👤 تحليل ملف الحساب",       value=True)
        improve_arabic   = st.checkbox("✍️ تحسين النص العربي",      value=False)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("**📊 حدود الاستخدام المجاني**")
        st.markdown("""
        <div class="limit-table">
            <div class="limit-row"><span>gemini-1.5-flash ⭐</span><span>15 RPM</span></div>
            <div class="limit-row"><span>gemini-1.5-flash-8b</span><span>15 RPM</span></div>
            <div class="limit-row"><span>gemini-2.5-flash</span><span>10 RPM</span></div>
            <div class="limit-row"><span>gemini-2.5-pro</span><span>5 RPM</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;font-size:13px!important;color:rgba(255,255,255,0.4)!important;">
        🔐 بياناتك محمية<br>لا يتم تخزين أي معلومات
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════
    # العنوان الرئيسي
    # ══════════════════════════════
    st.markdown(f"""
    <div class="app-header">
        <div class="title">{APP_EMOJI} {APP_NAME}</div>
        <div class="subtitle">منصة التحليل الاستخباراتي لمنشورات X (تويتر)</div>
        <span class="version-badge">الإصدار {APP_VERSION}</span>
    </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════
    # التابات
    # ══════════════════════════════
    tab_link, tab_profile, tab_img, tab_guide = st.tabs([
        "🔗 تحليل المنشور",
        "👤 تحليل الحساب",
        "🖼️ تحليل الصورة",
        "📖 دليل الاستخدام",
    ])

    # ────────────────────────────────────────────
    # تبويب 1 – تحليل المنشور
    # ────────────────────────────────────────────
    with tab_link:
        st.markdown("### 🔗 تحليل منشور من X")
        tweet_url_input = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            label_visibility="collapsed"
        )

        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            analyze_btn = st.button("🚀 بدء التحليل", key="analyze_tweet")
        with col_btn2:
            clear_btn = st.button("🗑️ مسح", key="clear_tweet")

        if clear_btn:
            st.rerun()

        if analyze_btn:
            if not api_key:
                st.error("❌ يرجى إدخال مفتاح Gemini API في الشريط الجانبي")
            elif not tweet_url_input.strip():
                st.warning("⚠️ يرجى إدخال رابط المنشور")
            elif not is_tweet_url(tweet_url_input.strip()):
                st.error("❌ الرابط غير صحيح. يجب أن يكون رابط منشور X صحيحاً")
            else:
                tweet_url = normalize_tweet_url(tweet_url_input.strip())
                tweet_id  = extract_tweet_id(tweet_url)
                username  = extract_username_from_url(tweet_url) or "unknown"

                progress = st.progress(0)
                status   = st.empty()

                def update_status(msg):
                    status.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)

                # ── جلب البيانات ──
                update_status("📡 جاري جلب بيانات المنشور...")
                progress.progress(15)
                tweet_data = fetch_tweet_with_media(tweet_url)
                full_text  = tweet_data.get("text", "")
                author     = tweet_data.get("author", username)
                images     = tweet_data.get("images", [])

                # ── OCR ──
                ocr_text = ""
                if enable_ocr and images:
                    update_status("🔤 جاري استخراج النصوص من الصور...")
                    progress.progress(35)
                    for img_url in images[:3]:
                        try:
                            resp = requests.get(img_url, timeout=10)
                            if resp.status_code == 200:
                                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                                    tf.write(resp.content)
                                    tmp_path = tf.name
                                t = ocr_image_tesseract(tmp_path)
                                if not t:
                                    t = ocr_image_gemini(tmp_path, api_key)
                                if t:
                                    ocr_text += f"\n{t}"
                                os.unlink(tmp_path)
                        except Exception:
                            pass

                # ── تحسين عربي ──
                if improve_arabic and full_text:
                    update_status("✍️ جاري تحسين النص العربي...")
                    progress.progress(50)
                    full_text = improve_arabic_text(full_text, api_key)

                # ── التحليل الرئيسي ──
                update_status("🧠 جاري التحليل بالذكاء الاصطناعي...")
                progress.progress(65)

                if not full_text:
                    st.warning("⚠️ لم يتم جلب نص المنشور، سيتم التحليل من الرابط فقط")
                    full_text = f"منشور من @{username} – {tweet_url}"

                analysis = run_analysis(
                    full_text, api_key, analysis_mode,
                    ocr_text, "", username, update_status
                )
                progress.progress(85)

                # ── جلب بيانات الحساب ──
                account_data   = {}
                profile_analysis = {}
                if enable_profile:
                    update_status("👤 جاري جلب بيانات الحساب...")
                    account_data = fetch_account_details_nitter(username, api_key)
                    if account_data.get("fetch_status") == "success" and api_key:
                        update_status("📊 جاري تحليل طبيعة الحساب...")
                        profile_analysis = analyze_account_profile(account_data, api_key, update_status)

                progress.progress(100)
                status.empty()
                progress.empty()

                st.success("✅ اكتمل التحليل بنجاح!")
                st.markdown("---")

                # ── عرض بيانات الحساب ──
                if account_data:
                    display_account_info_card(account_data)

                # ── عرض نتائج التحليل ──
                display_analysis_results(analysis, username)

                # ── عرض تحليل الحساب ──
                if profile_analysis:
                    st.markdown("---")
                    display_profile_analysis(profile_analysis)

                # ── تصدير JSON ──
                st.markdown("---")
                full_report = {
                    "tweet_id":   tweet_id,
                    "username":   username,
                    "tweet_url":  tweet_url,
                    "tweet_text": full_text,
                    "ocr_text":   ocr_text,
                    "analysis":   analysis,
                    "account_data":       account_data,
                    "profile_analysis":   profile_analysis,
                    "timestamp":  time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button(
                    label="⬇️ تصدير التقرير (JSON)",
                    data=json.dumps(full_report, ensure_ascii=False, indent=2),
                    file_name=f"report_{tweet_id or 'unknown'}.json",
                    mime="application/json",
                )

    # ────────────────────────────────────────────
    # تبويب 2 – تحليل الحساب
    # ────────────────────────────────────────────
    with tab_profile:
        st.markdown("### 👤 تحليل ملف حساب X")
        profile_url_input = st.text_input(
            "رابط الحساب",
            placeholder="https://x.com/username",
            label_visibility="collapsed",
            key="profile_url_input"
        )
        profile_btn = st.button("🔍 تحليل الحساب", key="analyze_profile")

        if profile_btn:
            if not api_key:
                st.error("❌ يرجى إدخال مفتاح Gemini API")
            elif not profile_url_input.strip():
                st.warning("⚠️ يرجى إدخال رابط الحساب")
            else:
                uname = extract_username_from_url(profile_url_input.strip())
                if not uname:
                    st.error("❌ تعذّر استخراج اسم المستخدم من الرابط")
                else:
                    with st.spinner("⏳ جاري جلب بيانات الحساب..."):
                        acc_data = fetch_account_details_nitter(uname, api_key)
                    display_account_info_card(acc_data)

                    if acc_data.get("fetch_status") == "success" and api_key:
                        with st.spinner("🧠 جاري تحليل طبيعة الحساب..."):
                            prof_analysis = analyze_account_profile(acc_data, api_key)
                        display_profile_analysis(prof_analysis)
                    else:
                        st.warning("⚠️ لم يتم جلب بيانات الحساب من مرايا Nitter")

    # ────────────────────────────────────────────
    # تبويب 3 – تحليل الصورة
    # ────────────────────────────────────────────
    with tab_img:
        st.markdown("### 🖼️ تحليل صورة")
        uploaded = st.file_uploader("ارفع صورة للتحليل", type=["jpg","jpeg","png","webp"])
        if uploaded and api_key:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(uploaded.read())
                img_path = tf.name
            st.image(img_path, caption="الصورة المرفوعة", use_column_width=True)
            with st.spinner("🔍 جاري تحليل الصورة..."):
                ocr_result = ocr_image_gemini(img_path, api_key)
            if ocr_result:
                st.markdown('<div class="section-card"><div class="section-title">📝 النص المستخرج</div>', unsafe_allow_html=True)
                st.text_area("", value=ocr_result, height=200, disabled=True)
                st.markdown('</div>', unsafe_allow_html=True)
                with st.spinner("🧠 جاري التحليل..."):
                    img_analysis = run_analysis(ocr_result, api_key, analysis_mode)
                display_analysis_results(img_analysis)
            os.unlink(img_path)
        elif uploaded and not api_key:
            st.error("❌ يرجى إدخال مفتاح Gemini API أولاً")

    # ────────────────────────────────────────────
    # تبويب 4 – دليل الاستخدام
    # ────────────────────────────────────────────
    with tab_guide:
        st.markdown("### 📖 دليل الاستخدام")

        st.markdown("#### 🚀 البدء السريع")
        st.markdown(
            "1. احصل على مفتاح Gemini مجاني من "
            "[Google AI Studio](https://aistudio.google.com/apikey)\n"
            "2. أدخل المفتاح في الشريط الجانبي الأيمن\n"
            "3. الصق رابط المنشور أو رابط الحساب واضغط **تحليل**"
        )

        st.markdown("#### ✅ الروابط المدعومة")
        st.code(
            "https://x.com/user/status/123456789\n"
            "https://x.com/user/status/123456789?s=20\n"
            "https://twitter.com/user/status/123456789\n"
            "https://x.com/username  (رابط حساب)",
            language=None
        )

        st.markdown("#### 🆕 مستجدات v6.7")
        st.markdown(
            "- **معرّف الحساب** يظهر بخط أبيض كبير\n"
            "- **عدد المتابعين** في بطاقة الإحصائيات\n"
            "- **تاريخ الانضمام** واضح في بيانات الحساب\n"
            "- **الموقع الجغرافي** (الحساب موجود في)\n"
            "- **حالة التوثيق** موثَّق / غير موثَّق / محمي\n"
            "- دعم كامل للوضع الليلي والنهاري\n"
            "- خطوط أكبر للقراءة السريعة"
        )

        st.markdown("#### ⚠️ حل مشكلة 429")
        st.table({
            "الحل":  ["انتظر دقيقة", "مفتاح جديد", "فعّل الفوترة"],
            "الوصف": [
                "الحد المجاني 10-15 طلب/دقيقة",
                "أنشئ مفتاحاً جديداً من aistudio.google.com",
                "يرفع الحد إلى 1000 طلب/دقيقة",
            ]
        })

        st.markdown("#### 🤖 النماذج المتاحة")
        st.table({
            "النموذج":    ["gemini-1.5-flash ⭐", "gemini-1.5-flash-8b", "gemini-2.5-flash", "gemini-2.5-pro"],
            "RPM مجاني": ["15", "15", "10", "5"],
            "RPD مجاني": ["1,500", "1,500", "250", "100"],
        })


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
