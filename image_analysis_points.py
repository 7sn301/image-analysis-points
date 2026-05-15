# ═══════════════════════════════════════════════════════════════
# المشهد التنفيذي - Executive Scene Analyzer
# الإصدار: 6.8 | تحليل منشورات X بالذكاء الاصطناعي
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
from urllib.parse import urlparse, quote
import html as html_module

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
APP_VERSION = "6.8"
APP_EMOJI   = "🎯"

GEMINI_MODELS = [
    {"name": "gemini-1.5-flash",      "rpm": 15,  "rpd": 1500},
    {"name": "gemini-1.5-flash-8b",   "rpm": 15,  "rpd": 1500},
    {"name": "gemini-2.5-flash",      "rpm": 10,  "rpd": 250},
    {"name": "gemini-2.5-flash-lite", "rpm": 10,  "rpd": 250},
    {"name": "gemini-2.5-pro",        "rpm": 5,   "rpd": 100},
]

OCR_LANG        = "ara+eng"
REQUEST_DELAY   = 2
MAX_RETRIES     = 3
MAX_POSTS_FETCH = 10   # عدد صفحات Nitter (كل صفحة ~20 تغريدة → 200 تغريدة)

TWEET_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+",
    re.IGNORECASE
)
PROFILE_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/(?!search|hashtag|i/)(\w+)/?$",
    re.IGNORECASE
)

ACCOUNT_CATEGORIES = {
    "معادي":         {"icon": "🔴", "color": "#dc2626", "desc": "يعبّر عن معارضة صريحة أو عدائية"},
    "مشبوه":         {"icon": "🟠", "color": "#ea580c", "desc": "سلوك مثير للريبة أو غير طبيعي"},
    "محايد":         {"icon": "⚪", "color": "#6b7280", "desc": "لا يُظهر انحيازاً واضحاً"},
    "مواطن":         {"icon": "🟢", "color": "#16a34a", "desc": "مواطن عادي يتفاعل بشكل طبيعي"},
    "داعم":          {"icon": "💙", "color": "#2563eb", "desc": "يُبدي دعماً للمواقف الرسمية"},
    "إعلامي":        {"icon": "📰", "color": "#7c3aed", "desc": "صحفي أو وسيلة إعلامية"},
    "مستنجد":        {"icon": "🆘", "color": "#0891b2", "desc": "يطلب المساعدة أو يتقدم بشكاوى"},
    "ساخر":          {"icon": "😏", "color": "#b45309", "desc": "يستخدم السخرية والتهكم"},
    "متدخل خارجي":  {"icon": "🌐", "color": "#be185d", "desc": "حساب خارجي يتدخل في الشأن الداخلي"},
}

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.space",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]

# ═══════════════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════════════
def safe_text(text: str) -> str:
    """تنظيف النص من HTML وإرجاع نص آمن"""
    if not text:
        return ""
    if BS4_AVAILABLE:
        clean = BeautifulSoup(str(text), "html.parser").get_text(separator=" ")
    else:
        clean = re.sub(r"<[^>]+>", " ", str(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    return html_module.escape(clean)

def fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n) if n > 0 else "—"

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
# Gemini API
# ═══════════════════════════════════════════════════════════════
def exponential_backoff(attempt: int) -> float:
    return min(60.0, 1.0 * (2 ** attempt) + random.uniform(0, 1))

def call_gemini_with_retry(model_obj, prompt: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            response = model_obj.generate_content(prompt)
            return response.text
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "rate" in err:
                time.sleep(exponential_backoff(attempt))
                continue
            elif "404" in err or "not found" in err:
                return None
            else:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(exponential_backoff(attempt))
                    continue
                return None
    return None

def gemini_generate(api_key: str, prompt: str, status_cb=None) -> Tuple[Optional[str], str]:
    if not GENAI_AVAILABLE:
        return None, "مكتبة google-generativeai غير مثبتة"
    genai.configure(api_key=api_key)
    for m in GEMINI_MODELS:
        try:
            if status_cb:
                status_cb(f"⏳ جاري المحاولة مع: {m['name']}")
            model  = genai.GenerativeModel(m["name"])
            result = call_gemini_with_retry(model, prompt)
            if result:
                return result, m["name"]
        except Exception as e:
            if status_cb:
                status_cb(f"⚠️ فشل {m['name']}: {str(e)[:50]}")
        time.sleep(REQUEST_DELAY)
    return None, "فشلت جميع النماذج"

# ═══════════════════════════════════════════════════════════════
# كشف VPN
# ═══════════════════════════════════════════════════════════════
def detect_vpn_indicators(account_data: Dict) -> Dict:
    vpn_info = {"detected": False, "risk_level": "منخفض", "indicators": [], "score": 0}
    bio      = str(account_data.get("bio", "") or "").lower()
    location = str(account_data.get("location", "") or "").lower()

    for kw in ["vpn", "proxy", "tor", "anonymous", "nordvpn", "expressvpn", "surfshark", "hide.me"]:
        if kw in bio:
            vpn_info["indicators"].append(f"مؤشر في البيو: {kw}")
            vpn_info["score"] += 25

    for loc in ["netherlands", "هولندا", "switzerland", "سويسرا", "iceland", "panama"]:
        if loc in location:
            vpn_info["indicators"].append(f"موقع مشبوه: {location}")
            vpn_info["score"] += 15
            break

    if vpn_info["score"] >= 40:
        vpn_info["detected"]   = True
        vpn_info["risk_level"] = "عالٍ"
    elif vpn_info["score"] >= 15:
        vpn_info["detected"]   = True
        vpn_info["risk_level"] = "متوسط"

    return vpn_info

# ═══════════════════════════════════════════════════════════════
# جلب بيانات الحساب - Nitter مُحسَّن
# ═══════════════════════════════════════════════════════════════
def _parse_nitter_count(text: str) -> int:
    """تحويل نص مثل '1.2K' أو '15,000' إلى رقم صحيح"""
    if not text:
        return 0
    text = text.strip().replace(",", "").replace("٬", "")
    try:
        if text.endswith("K") or text.endswith("k"):
            return int(float(text[:-1]) * 1000)
        if text.endswith("M") or text.endswith("m"):
            return int(float(text[:-1]) * 1_000_000)
        return int(float(text))
    except Exception:
        return 0

def fetch_account_details_nitter(username: str, api_key: str = "") -> Dict:
    account_data = {
        "username":      username,
        "display_name":  "",
        "user_id":       "",
        "bio":           "",
        "location":      "",
        "country":       "",
        "joined_date":   "",
        "verified":      False,
        "protected":     False,
        "followers":     0,
        "following":     0,
        "tweets_count":  0,
        "profile_image": "",
        "recent_tweets": [],
        "connected_via": "",
        "vpn_info":      {},
        "fetch_status":  "pending",
    }

    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ar,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml",
    }

    for mirror in NITTER_MIRRORS:
        try:
            url  = f"{mirror}/{username}"
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                continue

            if not BS4_AVAILABLE:
                account_data["fetch_status"] = "bs4_missing"
                account_data["connected_via"] = mirror
                return account_data

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── الاسم الكامل ──
            for selector in [
                ("a",    {"class": "profile-card-fullname"}),
                ("div",  {"class": "profile-card-fullname"}),
                ("h1",   {}),
            ]:
                el = soup.find(selector[0], selector[1]) if selector[1] else soup.find(selector[0])
                if el:
                    account_data["display_name"] = el.get_text(strip=True)
                    break

            # ── التوثيق ──
            if soup.find("span", class_=re.compile(r"verified|checkmark", re.I)):
                account_data["verified"] = True
            if soup.find("span", class_=re.compile(r"protect|lock", re.I)):
                account_data["protected"] = True

            # ── البيو (نظيف بدون HTML) ──
            bio_el = soup.find("div", class_=re.compile(r"profile-bio|bio", re.I))
            if bio_el:
                account_data["bio"] = bio_el.get_text(separator=" ", strip=True)

            # ── الإحصائيات ──
            # طريقة 1: profile-stat-item
            stats = soup.find_all("li", class_=re.compile(r"profile-stat", re.I))
            for stat in stats:
                num_el  = stat.find("span", class_=re.compile(r"stat-num|number", re.I))
                name_el = stat.find("span", class_=re.compile(r"stat-header|label", re.I))
                if num_el:
                    val  = _parse_nitter_count(num_el.get_text(strip=True))
                    kind = name_el.get_text(strip=True).lower() if name_el else ""
                    if "tweet" in kind or "post" in kind or "منشور" in kind:
                        account_data["tweets_count"] = val
                    elif "follower" in kind and "following" not in kind:
                        account_data["followers"] = val
                    elif "following" in kind or "يتابع" in kind:
                        account_data["following"] = val

            # طريقة 2: البحث في نصوص الصفحة بشكل مباشر
            if account_data["followers"] == 0:
                for a in soup.find_all("a", href=re.compile(rf"/{username}/followers", re.I)):
                    num = _parse_nitter_count(a.get_text(strip=True))
                    if num > 0:
                        account_data["followers"] = num
                        break
            if account_data["following"] == 0:
                for a in soup.find_all("a", href=re.compile(rf"/{username}/following", re.I)):
                    num = _parse_nitter_count(a.get_text(strip=True))
                    if num > 0:
                        account_data["following"] = num
                        break

            # ── الموقع ──
            loc_el = soup.find("div", class_=re.compile(r"profile-location|location", re.I))
            if loc_el:
                account_data["location"] = loc_el.get_text(strip=True)
            else:
                # بحث بديل
                for span in soup.find_all("span"):
                    if span.find("span", class_=re.compile(r"icon-location", re.I)):
                        account_data["location"] = span.get_text(strip=True)
                        break

            # ── تاريخ الانضمام ──
            joined_el = soup.find("div", class_=re.compile(r"profile-joindate|joindate|join", re.I))
            if joined_el:
                account_data["joined_date"] = joined_el.get_text(strip=True)
            else:
                for span in soup.find_all("span", title=re.compile(r"\d{4}")):
                    t = span.get("title", "")
                    if re.search(r"\d{4}", t):
                        account_data["joined_date"] = t
                        break

            # ── صورة الحساب ──
            for img_class in ["profile-card-avatar", "profile-image", "avatar"]:
                img_el = soup.find("img", class_=re.compile(img_class, re.I))
                if img_el:
                    src = img_el.get("src", "")
                    if src:
                        if src.startswith("/"):
                            src = mirror + src
                        account_data["profile_image"] = src
                        break
            if not account_data["profile_image"]:
                # بحث مباشر عن أي صورة تبدو صورة ملف شخصي
                for img in soup.find_all("img"):
                    src = img.get("src", "")
                    if "profile" in src.lower() or "avatar" in src.lower() or "pbs.twimg" in src:
                        if src.startswith("/"):
                            src = mirror + src
                        account_data["profile_image"] = src
                        break

            # ── التغريدات الأخيرة (نظيفة) ──
            tweet_els = soup.find_all(
                "div",
                class_=re.compile(r"tweet-content|tweet-text|content", re.I),
                limit=20
            )
            for tw in tweet_els:
                text = tw.get_text(separator=" ", strip=True)
                if text and len(text) > 10:
                    account_data["recent_tweets"].append(text)

            account_data["connected_via"] = mirror
            account_data["fetch_status"]  = "success" if (
                account_data["display_name"] or account_data["bio"] or account_data["recent_tweets"]
            ) else "partial"
            account_data["vpn_info"] = detect_vpn_indicators(account_data)
            return account_data

        except Exception:
            continue

    account_data["fetch_status"] = "failed"
    return account_data

def fetch_multiple_pages_nitter(username: str, max_pages: int = 10) -> List[str]:
    """جلب أكثر من صفحة من تغريدات المستخدم لتحليل أعمق"""
    all_tweets = []
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ar,en;q=0.9"}

    for mirror in NITTER_MIRRORS:
        cursor = ""
        fetched_pages = 0
        try:
            while fetched_pages < max_pages:
                url = f"{mirror}/{username}"
                if cursor:
                    url += f"?cursor={cursor}"
                resp = requests.get(url, headers=headers, timeout=12)
                if resp.status_code != 200:
                    break
                if not BS4_AVAILABLE:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                tweet_els = soup.find_all(
                    "div",
                    class_=re.compile(r"tweet-content|tweet-text", re.I)
                )
                if not tweet_els:
                    break
                for tw in tweet_els:
                    text = tw.get_text(separator=" ", strip=True)
                    if text and len(text) > 10:
                        all_tweets.append(text)

                # البحث عن رابط الصفحة التالية
                next_link = soup.find("a", class_=re.compile(r"show-more|next", re.I))
                if next_link and next_link.get("href"):
                    href = next_link["href"]
                    m = re.search(r"cursor=([^&]+)", href)
                    if m:
                        cursor = m.group(1)
                    else:
                        break
                else:
                    break

                fetched_pages += 1
                time.sleep(0.5)

            if all_tweets:
                return all_tweets
        except Exception:
            continue

    return all_tweets

# ═══════════════════════════════════════════════════════════════
# جلب التغريدة
# ═══════════════════════════════════════════════════════════════
def fetch_via_oembed(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "author_url": "", "html": "", "media_urls": [], "error": None}
    try:
        api    = "https://publish.twitter.com/oembed"
        params = {"url": tweet_url, "lang": "ar"}
        resp   = requests.get(api, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result["author"]     = data.get("author_name", "")
            result["author_url"] = data.get("author_url", "")
            result["html"]       = data.get("html", "")
            html_text = re.sub(r"<[^>]+>", " ", result["html"])
            result["text"] = " ".join(html_text.split())
        else:
            result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)
    return result

def fetch_via_nitter_tweet(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "images": [], "error": None}
    tweet_id = extract_tweet_id(tweet_url)
    username = extract_username_from_url(tweet_url)
    if not tweet_id or not username:
        result["error"] = "تعذّر استخراج البيانات"
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
            content_el = soup.find("div", class_=re.compile(r"tweet-content|tweet-text", re.I))
            if content_el:
                result["text"] = content_el.get_text(separator=" ", strip=True)
            name_el = soup.find("a", class_=re.compile(r"fullname", re.I))
            if name_el:
                result["author"] = name_el.get_text(strip=True)
            for img in soup.find_all("img", class_=re.compile(r"still-image|tweet-image", re.I)):
                src = img.get("src", "")
                if src:
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
    result = {"text": "", "author": "", "username": "", "images": [], "video": "", "source": "", "error": None}
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
        return pytesseract.image_to_string(Image.open(image_path), lang=OCR_LANG).strip()
    except Exception:
        return ""

def ocr_image_gemini(image_path: str, api_key: str) -> str:
    if not GENAI_AVAILABLE or not PIL_AVAILABLE:
        return ""
    try:
        genai.configure(api_key=api_key)
        img   = Image.open(image_path)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp  = model.generate_content(["استخرج كل النصوص من هذه الصورة:", img])
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
            "فرّغ محتوى هذا الفيديو نصياً:",
            {"mime_type": "video/mp4", "data": base64.b64encode(video_data).decode()}
        ])
        return resp.text.strip()
    except Exception:
        return ""

def improve_arabic_text(text: str, api_key: str) -> str:
    if not text or not api_key:
        return text
    result, _ = gemini_generate(api_key, f"حسّن النص العربي التالي:\n\n{text}")
    return result or text

# ═══════════════════════════════════════════════════════════════
# بناء الـ Prompts
# ═══════════════════════════════════════════════════════════════
def build_analysis_prompt(tweet_text: str, mode: str = "executive",
                           ocr_text: str = "", video_transcript: str = "",
                           username: str = "") -> str:
    extra = ""
    if ocr_text:
        extra += f"\n\n📸 نصوص الصور:\n{ocr_text}"
    if video_transcript:
        extra += f"\n\n🎥 نص الفيديو:\n{video_transcript}"

    mode_instructions = {
        "executive": "أجرِ تحليلاً تنفيذياً استخباراتياً شاملاً",
        "media":     "أجرِ تحليلاً إعلامياً وتحقق من صحة المحتوى",
        "security":  "أجرِ تحليلاً أمنياً مفصلاً للمخاطر",
        "general":   "أجرِ تحليلاً عاماً شاملاً",
    }
    instruction = mode_instructions.get(mode, mode_instructions["executive"])

    return f"""أنت محلل استخباراتي. {instruction} للمنشور التالي.

المستخدم: @{username}
المحتوى: {tweet_text}{extra}

أعد JSON فقط:
{{
  "executive_summary": "ملخص 3-5 جمل",
  "key_points": ["نقطة 1","نقطة 2","نقطة 3"],
  "risks": ["خطر 1","خطر 2"],
  "recommendations": ["توصية 1","توصية 2"],
  "sentiment": "إيجابي/سلبي/محايد",
  "sentiment_score": 75,
  "topics": ["موضوع 1","موضوع 2"],
  "urgency_level": "عالٍ/متوسط/منخفض",
  "credibility_score": 80,
  "analysis_mode": "{mode}"
}}"""

def build_profile_analysis_prompt(account_data: Dict, extended_tweets: List[str] = None) -> str:
    # دمج التغريدات الأخيرة مع الممتدة
    all_tweets = list(account_data.get("recent_tweets", []))
    if extended_tweets:
        all_tweets = list(set(all_tweets + extended_tweets))

    # استخدام أول 500 تغريدة كحد أقصى للتحليل
    tweets_sample = all_tweets[:500]
    tweets_text   = "\n".join([f"- {t}" for t in tweets_sample[:50]])  # إرسال 50 للنموذج
    tweets_count  = len(tweets_sample)

    return f"""أنت محلل استخباراتي متخصص في الهوية الرقمية وتحليل سلوك حسابات منصة X.

بيانات الحساب:
- الاسم: {account_data.get('display_name', '')}
- المعرّف: @{account_data.get('username', '')}
- البيو: {account_data.get('bio', '')}
- الموقع: {account_data.get('location', '')}
- تاريخ الانضمام: {account_data.get('joined_date', '')}
- المتابعون: {account_data.get('followers', 0):,}
- يتابع: {account_data.get('following', 0):,}
- إجمالي المنشورات: {account_data.get('tweets_count', 0):,}
- عينة تغريدات ({tweets_count} تغريدة):
{tweets_text}

بناءً على التحليل الشامل لمحتوى الحساب وأنماط سلوكه، أعد JSON فقط:
{{
  "primary_category": "معادي/مشبوه/محايد/مواطن/داعم/إعلامي/مستنجد/ساخر/متدخل خارجي",
  "risk_level": "عالٍ/متوسط/منخفض",
  "scores": {{
    "hostility": 0,
    "authenticity": 0,
    "influence": 0,
    "external_interference": 0
  }},
  "summary": "تحليل شامل لطبيعة الحساب وتوجهاته",
  "patterns": ["نمط 1","نمط 2","نمط 3"],
  "recommendations": ["توصية 1","توصية 2"],
  "origin_guess": "الدولة أو المنطقة المحتملة",
  "influence_level": "عالٍ/متوسط/منخفض",
  "content_themes": ["موضوع 1","موضوع 2"],
  "activity_pattern": "وصف نمط النشاط والتوقيت"
}}"""

# ═══════════════════════════════════════════════════════════════
# تنفيذ التحليل
# ═══════════════════════════════════════════════════════════════
def run_analysis(tweet_text: str, api_key: str, mode: str = "executive",
                  ocr_text: str = "", video_transcript: str = "",
                  username: str = "", status_cb=None) -> Dict:
    prompt = build_analysis_prompt(tweet_text, mode, ocr_text, video_transcript, username)
    raw, model_used = gemini_generate(api_key, prompt, status_cb)
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
                              extended_tweets: List[str] = None,
                              status_cb=None) -> Dict:
    prompt = build_profile_analysis_prompt(account_data, extended_tweets)
    raw, model_used = gemini_generate(api_key, prompt, status_cb)
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
# CSS الشامل v6.8
# ═══════════════════════════════════════════════════════════════
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');

/* ── متغيرات ── */
:root {
    --p:    #1DA1F2;
    --pd:   #0d8bd1;
    --gold: #F0B429;
    --ok:   #16a34a;
    --err:  #dc2626;
    --warn: #ea580c;
    --card: #ffffff;
    --bg:   #f0f4f8;
    --txt:  #0f172a;
    --sub:  #334155;
    --muted:#64748b;
    --bdr:  #e2e8f0;
    --shd:  0 4px 20px rgba(0,0,0,.10);
    --r:    16px;
}
[data-theme="dark"] {
    --card:#1e293b; --bg:#0f172a;
    --txt:#f1f5f9; --sub:#cbd5e1; --muted:#94a3b8; --bdr:#334155;
}
@media (prefers-color-scheme:dark){
    :root{ --card:#1e293b; --bg:#0f172a; --txt:#f1f5f9;
           --sub:#cbd5e1; --muted:#94a3b8; --bdr:#334155;
           --shd:0 4px 20px rgba(0,0,0,.40); }
}

/* ── عام ── */
*{ font-family:'Tajawal',sans-serif!important; box-sizing:border-box; }
html,body,.stApp{ direction:rtl!important; text-align:right!important; }
.stApp{ background:var(--bg)!important; color:var(--txt)!important; }
p,li,span,td,th,div,label{ color:var(--txt); }
.stMarkdown p{ font-size:17px!important; line-height:1.9!important; color:var(--txt)!important; }
h1,h2,h3{ color:var(--txt)!important; font-weight:800!important; }

/* ── شريط جانبي ── */
section[data-testid="stSidebar"]{
    width:360px!important; min-width:360px!important;
    background:linear-gradient(180deg,#071e33 0%,#0f2b46 60%,#071e33 100%)!important;
    border-left:3px solid var(--p)!important;
}
section[data-testid="stSidebar"]>div:first-child{ padding:20px 18px!important; }
section[data-testid="stSidebar"] *{ color:#fff!important; font-size:17px!important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{ color:var(--gold)!important; font-size:20px!important; }
section[data-testid="stSidebar"] label{ color:#e2e8f0!important; font-size:16px!important; font-weight:600!important; }
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select{
    background:rgba(255,255,255,.12)!important; border:1px solid rgba(255,255,255,.3)!important;
    border-radius:10px!important; color:#fff!important; font-size:16px!important; padding:10px 14px!important;
}
section[data-testid="stSidebar"] .stSelectbox>div>div{
    background:rgba(255,255,255,.12)!important; border:1px solid rgba(255,255,255,.3)!important; color:#fff!important;
}
.sidebar-logo{ text-align:center; font-size:54px; padding:20px 0 12px; }
.sidebar-title{ text-align:center; font-size:26px!important; font-weight:900!important; color:var(--gold)!important; margin-bottom:4px; }
.sidebar-version{ text-align:center; font-size:13px!important; color:rgba(255,255,255,.5)!important; margin-bottom:20px; }
.limit-table{ background:rgba(255,255,255,.08); border-radius:10px; padding:12px; }
.limit-row{ display:flex; justify-content:space-between; padding:6px 0;
            border-bottom:1px solid rgba(255,255,255,.1); font-size:14px!important; color:#e2e8f0!important; }

/* ── رأس الصفحة ── */
.app-header{
    background:linear-gradient(135deg,#071e33 0%,#1a4a7a 50%,#071e33 100%);
    padding:30px 40px; border-radius:20px; text-align:center;
    margin-bottom:28px; box-shadow:0 8px 40px rgba(29,161,242,.25);
}
.app-header .title{ font-size:44px!important; font-weight:900!important; color:#fff!important; margin:0; }
.app-header .subtitle{ font-size:18px!important; color:rgba(255,255,255,.7)!important; margin-top:6px; }

/* ════════════════════════════════
   بطاقة الحساب
════════════════════════════════ */
.acc-card{
    background:linear-gradient(135deg,#071e33 0%,#1a4a7a 60%,#0d8bd1 100%);
    border-radius:20px; padding:28px 32px; margin-bottom:24px;
    box-shadow:0 8px 40px rgba(29,161,242,.25); direction:rtl;
}
.acc-card-hdr{ display:flex; align-items:center; gap:18px; margin-bottom:20px; }
.acc-avatar{
    width:84px; height:84px; border-radius:50%;
    border:3px solid rgba(255,255,255,.55); object-fit:cover; flex-shrink:0;
}
.acc-avatar-ph{
    width:84px; height:84px; border-radius:50%;
    background:rgba(255,255,255,.15); border:3px solid rgba(255,255,255,.4);
    display:flex; align-items:center; justify-content:center;
    font-size:38px; flex-shrink:0;
}
.acc-name{ font-size:28px!important; font-weight:900!important; color:#fff!important; margin:0 0 4px; }
.acc-uname{ font-size:19px!important; font-weight:700!important; color:#93c5fd!important; margin:0 0 8px; }

/* معرّف الحساب */
.acc-id-box{
    display:inline-flex; align-items:center; gap:8px;
    background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.35);
    border-radius:8px; padding:6px 14px; margin-bottom:10px;
}
.acc-id-lbl{ font-size:13px!important; color:#93c5fd!important; font-weight:600!important; }
.acc-id-val{ font-size:17px!important; color:#fff!important; font-weight:900!important; letter-spacing:.5px; }

/* شارات */
.badge{
    display:inline-flex; align-items:center; gap:6px;
    border-radius:20px; padding:5px 14px; font-size:15px!important;
    font-weight:700!important; margin-left:6px; margin-top:4px;
}
.badge-verified{ background:rgba(29,161,242,.3); border:1px solid rgba(29,161,242,.6); color:#fff!important; }
.badge-unverified{ background:rgba(107,114,128,.3); border:1px solid rgba(107,114,128,.5); color:#d1d5db!important; }
.badge-protected{ background:rgba(240,180,41,.2); border:1px solid rgba(240,180,41,.5); color:#fcd34d!important; }

/* إحصاء */
.stats-grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:20px 0; }
.stat-box{
    background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.18);
    border-radius:12px; padding:14px 8px; text-align:center;
}
.stat-num{ font-size:28px!important; font-weight:900!important; color:#fff!important; display:block; line-height:1.1; }
.stat-lbl{ font-size:14px!important; font-weight:600!important; color:rgba(255,255,255,.65)!important; margin-top:4px; display:block; }

/* تفاصيل */
.details-grid{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:16px; }
.detail-row{
    background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15);
    border-radius:10px; padding:10px 14px;
    display:flex; align-items:center; gap:10px; direction:rtl;
}
.detail-icon{ font-size:20px; flex-shrink:0; }
.detail-lbl{ font-size:12px!important; color:rgba(255,255,255,.55)!important; font-weight:600!important; display:block; }
.detail-val{ font-size:16px!important; color:#fff!important; font-weight:700!important; display:block; }

/* VPN */
.vpn-box{ margin-top:14px; padding:12px 16px; border-radius:10px; direction:rtl; }
.vpn-high{   background:rgba(220,38,38,.25); border:1px solid rgba(220,38,38,.5);   color:#fca5a5!important; }
.vpn-medium{ background:rgba(234,88,12,.25);  border:1px solid rgba(234,88,12,.5);   color:#fdba74!important; }
.vpn-low{    background:rgba(22,163,74,.20);   border:1px solid rgba(22,163,74,.4);   color:#86efac!important; }
.vpn-box *{ font-size:15px!important; font-weight:700!important; }

/* ════════════════════════════════
   بطاقات التحليل
════════════════════════════════ */
.sum-card{
    background:linear-gradient(135deg,#1e3a5f 0%,#1a4a7a 100%);
    border-right:6px solid var(--p); border-radius:16px;
    padding:24px 28px; margin-bottom:20px; direction:rtl;
}
.sum-title{ font-size:22px!important; font-weight:900!important; color:var(--gold)!important; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.sum-text{ font-size:19px!important; font-weight:500!important; color:#f1f5f9!important; line-height:2!important; direction:rtl; text-align:right; }

.sec-card{
    background:var(--card); border-radius:16px; padding:22px 26px;
    margin-bottom:18px; box-shadow:var(--shd); border:1px solid var(--bdr); direction:rtl;
}
.sec-title{ font-size:20px!important; font-weight:800!important; color:var(--p)!important; margin-bottom:14px;
    display:flex; align-items:center; gap:8px; border-bottom:2px solid var(--bdr); padding-bottom:10px; direction:rtl; }

.pt-item{
    background:var(--bg); border-right:4px solid var(--p);
    border-radius:10px; padding:13px 16px; margin-bottom:10px;
    font-size:17px!important; font-weight:500!important; color:var(--txt)!important;
    line-height:1.8; direction:rtl; text-align:right;
}
.risk-item{
    background:rgba(220,38,38,.07); border-right:4px solid #dc2626;
    border-radius:10px; padding:13px 16px; margin-bottom:10px;
    font-size:17px!important; font-weight:500!important; color:var(--txt)!important;
    line-height:1.8; direction:rtl; text-align:right;
}
.rec-item{
    background:rgba(22,163,74,.07); border-right:4px solid #16a34a;
    border-radius:10px; padding:13px 16px; margin-bottom:10px;
    font-size:17px!important; font-weight:500!important; color:var(--txt)!important;
    line-height:1.8; direction:rtl; text-align:right;
}

/* مشاعر */
.sent-card{
    background:var(--card); border-radius:16px; padding:22px 18px;
    margin-bottom:18px; box-shadow:var(--shd); border:1px solid var(--bdr);
    text-align:center; direction:rtl;
}
.sent-val{ font-size:34px!important; font-weight:900!important; color:var(--p)!important; display:block; margin:10px 0; }
.sent-score{ font-size:20px!important; font-weight:800!important; color:var(--sub)!important; }
.sent-pos{ color:var(--ok)!important; }
.sent-neg{ color:var(--err)!important; }
.sent-neu{ color:var(--muted)!important; }

/* موضوعات */
.topic-tag{
    display:inline-block; background:rgba(29,161,242,.12); color:var(--p)!important;
    border:1px solid rgba(29,161,242,.35); border-radius:20px;
    padding:6px 16px; font-size:15px!important; font-weight:700!important; margin:4px;
}

/* بروفايل */
.cat-badge{
    display:inline-flex; align-items:center; gap:10px;
    padding:12px 24px; border-radius:30px;
    font-size:22px!important; font-weight:900!important; color:#fff!important; margin-bottom:12px;
}
.score-lbl{ font-size:17px!important; font-weight:700!important; color:var(--txt)!important; margin-bottom:6px; direction:rtl; text-align:right; }

/* حالة */
.status-box{
    background:rgba(29,161,242,.08); border:1px solid rgba(29,161,242,.25);
    border-radius:12px; padding:12px 18px; font-size:16px!important;
    color:var(--p)!important; font-weight:600!important; margin-bottom:12px; direction:rtl;
}

/* أزرار */
.stButton>button{
    background:linear-gradient(135deg,var(--p) 0%,var(--pd) 100%)!important;
    color:#fff!important; border:none!important; border-radius:12px!important;
    padding:14px 28px!important; font-size:18px!important; font-weight:700!important;
    width:100%!important; box-shadow:0 4px 16px rgba(29,161,242,.35)!important;
    transition:all .2s ease!important;
}
.stButton>button:hover{ transform:translateY(-2px)!important; }

/* تابات */
.stTabs [role="tab"]{ font-size:17px!important; font-weight:700!important; padding:12px 18px!important; }
.stTabs [aria-selected="true"]{ color:var(--p)!important; border-bottom:3px solid var(--p)!important; }

/* مدخلات */
.stTextInput input,.stTextArea textarea{
    font-size:17px!important; font-weight:500!important; color:var(--txt)!important;
    border-radius:12px!important; padding:12px 16px!important; border:2px solid var(--bdr)!important;
    direction:rtl!important;
}
.stTextInput input:focus,.stTextArea textarea:focus{
    border-color:var(--p)!important; box-shadow:0 0 0 3px rgba(29,161,242,.15)!important;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض بطاقة الحساب - v6.8 مُعاد كتابتها بالكامل
# ═══════════════════════════════════════════════════════════════
def display_account_info_card(account_data: Dict):
    username      = str(account_data.get("username", "") or "")
    display_name  = safe_text(account_data.get("display_name", "") or username)
    user_id       = safe_text(account_data.get("user_id", "") or "")
    bio           = safe_text(account_data.get("bio", "") or "")
    location      = safe_text(account_data.get("location", "") or "غير محدد")
    country       = safe_text(account_data.get("country", "") or "")
    joined_date   = safe_text(account_data.get("joined_date", "") or "غير محدد")
    verified      = bool(account_data.get("verified", False))
    protected     = bool(account_data.get("protected", False))
    followers     = int(account_data.get("followers", 0) or 0)
    following     = int(account_data.get("following", 0) or 0)
    tweets_count  = int(account_data.get("tweets_count", 0) or 0)
    profile_img   = str(account_data.get("profile_image", "") or "")
    connected_via = str(account_data.get("connected_via", "") or "")
    vpn_info      = account_data.get("vpn_info", {}) or {}
    fetch_status  = str(account_data.get("fetch_status", ""))

    # ── Avatar HTML ──
    if profile_img:
        avatar_html = f'<img src="{profile_img}" class="acc-avatar" alt="avatar" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'"><div class="acc-avatar-ph" style="display:none">👤</div>'
    else:
        avatar_html = '<div class="acc-avatar-ph">👤</div>'

    # ── شارات ──
    badges_html = ""
    if verified:
        badges_html += '<span class="badge badge-verified">✅ موثَّق</span>'
    else:
        badges_html += '<span class="badge badge-unverified">⚪ غير موثَّق</span>'
    if protected:
        badges_html += '<span class="badge badge-protected">🔒 محمي</span>'

    # ── معرّف ──
    id_html = ""
    if user_id:
        id_html = f'<div class="acc-id-box"><span class="acc-id-lbl">🪪 معرّف:</span><span class="acc-id-val">{user_id}</span></div>'

    # ── Bio ──
    bio_html = f'<p style="font-size:16px!important;color:rgba(255,255,255,.82)!important;margin:0 0 16px;line-height:1.8;direction:rtl">{bio}</p>' if bio else ""

    # ── إحصاء ──
    stats_html = f"""
<div class="stats-grid">
  <div class="stat-box">
    <span class="stat-num">{fmt_number(followers)}</span>
    <span class="stat-lbl">👥 المتابعون</span>
  </div>
  <div class="stat-box">
    <span class="stat-num">{fmt_number(following)}</span>
    <span class="stat-lbl">➡️ يتابع</span>
  </div>
  <div class="stat-box">
    <span class="stat-num">{fmt_number(tweets_count)}</span>
    <span class="stat-lbl">📝 المنشورات</span>
  </div>
</div>"""

    # ── تفاصيل ──
    display_country = country if country else (location if location != "غير محدد" else "غير محدد")
    ratio_val = f"{round(followers / max(following, 1), 1)}x" if following > 0 else "—"
    mirror_short = connected_via.replace("https://", "") if connected_via else "غير متاح"

    details_html = f"""
<div class="details-grid">
  <div class="detail-row">
    <span class="detail-icon">📅</span>
    <div>
      <span class="detail-lbl">تاريخ الانضمام</span>
      <span class="detail-val">{joined_date}</span>
    </div>
  </div>
  <div class="detail-row">
    <span class="detail-icon">📍</span>
    <div>
      <span class="detail-lbl">الحساب موجود في</span>
      <span class="detail-val">{display_country}</span>
    </div>
  </div>
  <div class="detail-row">
    <span class="detail-icon">🔗</span>
    <div>
      <span class="detail-lbl">مصدر البيانات</span>
      <span class="detail-val" style="font-size:13px!important">{mirror_short}</span>
    </div>
  </div>
  <div class="detail-row">
    <span class="detail-icon">📊</span>
    <div>
      <span class="detail-lbl">نسبة المتابعة</span>
      <span class="detail-val">{ratio_val}</span>
    </div>
  </div>
</div>"""

    # ── VPN ──
    vpn_html = ""
    if vpn_info:
        risk      = str(vpn_info.get("risk_level", "منخفض"))
        detected  = bool(vpn_info.get("detected", False))
        indicators= vpn_info.get("indicators", []) or []
        css_cls   = "vpn-high" if risk == "عالٍ" else ("vpn-medium" if risk == "متوسط" else "vpn-low")
        icon      = "🔴" if risk == "عالٍ" else ("🟠" if risk == "متوسط" else "🟢")
        ind_text  = " | ".join(indicators[:2]) if indicators else "لا توجد مؤشرات"
        status_txt= "⚠️ يُرجَّح استخدام VPN" if detected else "✅ لا يُرجَّح استخدام VPN"
        vpn_html  = f"""
<div class="vpn-box {css_cls}">
  {icon} كاشف VPN — خطورة: <strong>{risk}</strong> — {status_txt}
  <br><small style="font-size:13px!important;opacity:.8">{ind_text}</small>
</div>"""

    # ── تجميع ──
    card_html = f"""
<div class="acc-card">
  <div class="acc-card-hdr">
    {avatar_html}
    <div style="flex:1;direction:rtl">
      <div class="acc-name">{display_name}</div>
      <div class="acc-uname">@{username}</div>
      {id_html}
      <div style="margin-top:6px">{badges_html}</div>
    </div>
  </div>
  {bio_html}
  {stats_html}
  {details_html}
  {vpn_html}
</div>"""

    st.markdown(card_html, unsafe_allow_html=True)

    # ── رسالة حالة الجلب ──
    if fetch_status == "failed":
        st.warning("⚠️ لم يتم جلب بيانات الحساب من Nitter — قد يكون الحساب خاصاً أو المرايا معطلة")
    elif fetch_status == "partial":
        st.info("ℹ️ بيانات جزئية — بعض المعلومات قد تكون غير مكتملة")

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
    summary = str(analysis.get("executive_summary", "") or "")
    if summary:
        st.markdown(f"""
<div class="sum-card">
  <div class="sum-title">📋 الملخص التنفيذي</div>
  <p class="sum-text">{html_module.escape(summary)}</p>
</div>""", unsafe_allow_html=True)

    # ── نقاط + مخاطر ──
    col1, col2 = st.columns(2)
    with col1:
        points = analysis.get("key_points", []) or []
        if points:
            items = "".join(
                f'<div class="pt-item">🔹 {html_module.escape(str(p))}</div>' for p in points
            )
            st.markdown(f"""
<div class="sec-card">
  <div class="sec-title">🎯 النقاط الرئيسية</div>
  {items}
</div>""", unsafe_allow_html=True)

    with col2:
        risks = analysis.get("risks", []) or []
        if risks:
            items = "".join(
                f'<div class="risk-item">⚠️ {html_module.escape(str(r))}</div>' for r in risks
            )
            st.markdown(f"""
<div class="sec-card">
  <div class="sec-title" style="color:#dc2626!important">⚠️ المخاطر</div>
  {items}
</div>""", unsafe_allow_html=True)

    # ── توصيات ──
    recs = analysis.get("recommendations", []) or []
    if recs:
        items = "".join(
            f'<div class="rec-item">✅ {html_module.escape(str(r))}</div>' for r in recs
        )
        st.markdown(f"""
<div class="sec-card" style="direction:rtl;text-align:right">
  <div class="sec-title" style="color:#16a34a!important;direction:rtl">💡 التوصيات</div>
  {items}
</div>""", unsafe_allow_html=True)

    # ── مشاعر ──
    sentiment   = str(analysis.get("sentiment", "") or "")
    score       = analysis.get("sentiment_score", 0) or 0
    urgency     = str(analysis.get("urgency_level", "") or "")
    credibility = analysis.get("credibility_score", 0) or 0

    if sentiment:
        sent_cls  = "sent-pos" if "إيجابي" in sentiment else ("sent-neg" if "سلبي" in sentiment else "sent-neu")
        sent_icon = "😊" if "إيجابي" in sentiment else ("😟" if "سلبي" in sentiment else "😐")
        urg_color = "#dc2626" if urgency == "عالٍ" else ("#ea580c" if urgency == "متوسط" else "#16a34a")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
<div class="sent-card">
  <div class="sec-title" style="justify-content:center;border:none;padding-bottom:0">🎭 المشاعر العامة</div>
  <span class="sent-val {sent_cls}">{sent_icon} {sentiment}</span>
  <span class="sent-score">النسبة: {score}%</span>
</div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
<div class="sent-card">
  <div class="sec-title" style="justify-content:center;border:none;padding-bottom:0">🚨 مستوى الإلحاح</div>
  <span class="sent-val" style="color:{urg_color}!important">{urgency}</span>
</div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
<div class="sent-card">
  <div class="sec-title" style="justify-content:center;border:none;padding-bottom:0">🔍 المصداقية</div>
  <span class="sent-val">{credibility}%</span>
</div>""", unsafe_allow_html=True)

    # ── موضوعات ──
    topics = analysis.get("topics", []) or []
    if topics:
        tags = "".join(
            f'<span class="topic-tag">{html_module.escape(str(t))}</span>' for t in topics
        )
        st.markdown(f"""
<div class="sec-card">
  <div class="sec-title">🏷️ الموضوعات</div>
  <div style="direction:rtl">{tags}</div>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض تحليل الملف الشخصي
# ═══════════════════════════════════════════════════════════════
def display_profile_analysis(profile_analysis: Dict):
    if "error" in profile_analysis:
        st.error(f"❌ {profile_analysis['error']}")
        return

    category = str(profile_analysis.get("primary_category", "محايد") or "محايد")
    cat_info  = ACCOUNT_CATEGORIES.get(category, {"icon": "⚪", "color": "#6b7280", "desc": ""})
    risk      = str(profile_analysis.get("risk_level", "") or "")
    summary   = str(profile_analysis.get("summary", "") or "")
    scores    = profile_analysis.get("scores", {}) or {}
    patterns  = profile_analysis.get("patterns", []) or []
    recs      = profile_analysis.get("recommendations", []) or []
    origin    = str(profile_analysis.get("origin_guess", "") or "")
    influence = str(profile_analysis.get("influence_level", "") or "")
    themes    = profile_analysis.get("content_themes", []) or []
    activity  = str(profile_analysis.get("activity_pattern", "") or "")
    model     = str(profile_analysis.get("_model_used", "") or "")

    # ── تصنيف الحساب ──
    st.markdown(f"""
<div class="sec-card">
  <div class="sec-title">🎯 تحليل طبيعة الحساب</div>
  <div style="text-align:center;margin-bottom:16px">
    <span class="cat-badge" style="background:{cat_info['color']}">
      {cat_info['icon']} {category}
    </span>
    <p style="font-size:17px!important;color:var(--sub)!important;margin:8px 0">{cat_info['desc']}</p>
  </div>
  {f'<div class="sum-card"><p class="sum-text">{html_module.escape(summary)}</p></div>' if summary else ""}
</div>""", unsafe_allow_html=True)

    # ── مؤشرات التقييم ──
    if scores:
        score_labels = {
            "hostility":             ("🔴 مستوى العدائية",   "#dc2626"),
            "authenticity":          ("✅ الأصالة",           "#16a34a"),
            "influence":             ("📢 التأثير",           "#2563eb"),
            "external_interference": ("🌐 التدخل الخارجي",   "#be185d"),
        }
        st.markdown('<div class="sec-card"><div class="sec-title">📊 مؤشرات التقييم</div>', unsafe_allow_html=True)
        for key, val in scores.items():
            label, color = score_labels.get(key, (key, "#1DA1F2"))
            try:
                pct = min(int(float(val)), 100)
            except Exception:
                pct = 0
            st.markdown(
                f'<div class="score-lbl">{label}: <strong>{pct}%</strong></div>',
                unsafe_allow_html=True
            )
            st.progress(pct / 100)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── الأنماط + التوصيات ──
    col1, col2 = st.columns(2)
    with col1:
        if patterns:
            items = "".join(
                f'<div class="pt-item" style="direction:rtl;text-align:right">🔹 {html_module.escape(str(p))}</div>'
                for p in patterns
            )
            st.markdown(f"""
<div class="sec-card" style="direction:rtl;text-align:right">
  <div class="sec-title" style="direction:rtl">🔍 الأنماط المرصودة</div>
  {items}
</div>""", unsafe_allow_html=True)

    with col2:
        if recs:
            items = "".join(
                f'<div class="rec-item" style="direction:rtl;text-align:right">✅ {html_module.escape(str(r))}</div>'
                for r in recs
            )
            st.markdown(f"""
<div class="sec-card" style="direction:rtl;text-align:right">
  <div class="sec-title" style="direction:rtl;color:#16a34a!important">💡 التوصيات</div>
  {items}
</div>""", unsafe_allow_html=True)

    # ── الموضوعات + نمط النشاط ──
    if themes:
        tags = "".join(
            f'<span class="topic-tag">{html_module.escape(str(t))}</span>' for t in themes
        )
        st.markdown(f"""
<div class="sec-card" style="direction:rtl">
  <div class="sec-title">🏷️ محاور المحتوى</div>
  <div style="direction:rtl">{tags}</div>
  {f'<p style="font-size:16px!important;color:var(--sub)!important;margin-top:12px;direction:rtl">{html_module.escape(activity)}</p>' if activity else ""}
</div>""", unsafe_allow_html=True)

    # ── معلومات إضافية ──
    extra = []
    if origin:    extra.append(f"🌍 الدولة المحتملة: <strong>{html_module.escape(origin)}</strong>")
    if influence: extra.append(f"📢 مستوى التأثير: <strong>{html_module.escape(influence)}</strong>")
    if risk:      extra.append(f"⚡ مستوى الخطورة: <strong>{html_module.escape(risk)}</strong>")
    if model:     extra.append(f"🤖 النموذج: <strong>{html_module.escape(model)}</strong>")
    if extra:
        st.markdown(
            f'<div class="status-box" style="font-size:15px!important">{" &nbsp;|&nbsp; ".join(extra)}</div>',
            unsafe_allow_html=True
        )

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

    # ══════ الشريط الجانبي ══════
    with st.sidebar:
        st.markdown(f"""
<div class="sidebar-logo">{APP_EMOJI}</div>
<div class="sidebar-title">{APP_NAME}</div>
<div class="sidebar-version">v{APP_VERSION}</div>
<hr style="border-color:rgba(255,255,255,.2);margin:16px 0">
""", unsafe_allow_html=True)

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاح مجاني من aistudio.google.com/apikey"
        )

        st.markdown("<hr style='border-color:rgba(255,255,255,.2);margin:16px 0'>", unsafe_allow_html=True)
        st.markdown("**⚙️ إعدادات التحليل**")

        analysis_mode = st.selectbox(
            "🎯 وضع التحليل",
            options=["executive", "media", "security", "general"],
            format_func=lambda x: {
                "executive": "📋 تنفيذي — شامل",
                "media":     "📰 إعلامي — تحقق",
                "security":  "🔒 أمني — مخاطر",
                "general":   "🔍 عام",
            }[x]
        )

        enable_ocr    = st.checkbox("🔤 تفعيل OCR", value=False)
        enable_video  = st.checkbox("🎥 تحليل الفيديو", value=False)
        enable_profile= st.checkbox("👤 تحليل ملف الحساب", value=True)
        deep_profile  = st.checkbox("🔬 تحليل عميق (500 منشور)", value=False)
        improve_ar    = st.checkbox("✍️ تحسين النص العربي", value=False)

        st.markdown("<hr style='border-color:rgba(255,255,255,.2);margin:16px 0'>", unsafe_allow_html=True)
        st.markdown("**📊 حدود الاستخدام المجاني**")
        st.markdown("""
<div class="limit-table">
  <div class="limit-row"><span>gemini-1.5-flash ⭐</span><span>15 RPM / 1500 RPD</span></div>
  <div class="limit-row"><span>gemini-1.5-flash-8b</span><span>15 RPM / 1500 RPD</span></div>
  <div class="limit-row"><span>gemini-2.5-flash</span><span>10 RPM / 250 RPD</span></div>
  <div class="limit-row"><span>gemini-2.5-pro</span><span>5 RPM / 100 RPD</span></div>
</div>""", unsafe_allow_html=True)

        st.markdown("""
<hr style="border-color:rgba(255,255,255,.2);margin:16px 0">
<div style="text-align:center;font-size:13px!important;color:rgba(255,255,255,.4)!important">
  🔐 بياناتك محمية — لا يتم تخزينها
</div>""", unsafe_allow_html=True)

    # ══════ رأس الصفحة ══════
    st.markdown(f"""
<div class="app-header">
  <div class="title">{APP_EMOJI} {APP_NAME}</div>
  <div class="subtitle">منصة التحليل الاستخباراتي لمنشورات X (تويتر)</div>
</div>
""", unsafe_allow_html=True)

    # ══════ التابات ══════
    tab_link, tab_profile, tab_img, tab_guide = st.tabs([
        "🔗 تحليل المنشور",
        "👤 تحليل الحساب",
        "🖼️ تحليل الصورة",
        "📖 دليل الاستخدام",
    ])

    # ────── تبويب 1: تحليل المنشور ──────
    with tab_link:
        st.markdown("### 🔗 تحليل منشور من X")
        tweet_url_input = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            label_visibility="collapsed"
        )
        col_b1, col_b2 = st.columns([3, 1])
        with col_b1:
            analyze_btn = st.button("🚀 بدء التحليل", key="btn_tweet")
        with col_b2:
            if st.button("🗑️ مسح", key="btn_clear"):
                st.rerun()

        if analyze_btn:
            if not api_key:
                st.error("❌ يرجى إدخال مفتاح Gemini API في الشريط الجانبي")
            elif not tweet_url_input.strip():
                st.warning("⚠️ يرجى إدخال رابط المنشور")
            elif not is_tweet_url(tweet_url_input.strip()):
                st.error("❌ الرابط غير صحيح")
            else:
                tweet_url = normalize_tweet_url(tweet_url_input.strip())
                tweet_id  = extract_tweet_id(tweet_url)
                username  = extract_username_from_url(tweet_url) or "unknown"

                progress = st.progress(0)
                status   = st.empty()
                def upd(msg): status.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)

                upd("📡 جاري جلب بيانات المنشور...")
                progress.progress(10)
                tweet_data = fetch_tweet_with_media(tweet_url)
                full_text  = tweet_data.get("text", "")
                author     = tweet_data.get("author", username)
                images     = tweet_data.get("images", [])

                ocr_text = ""
                if enable_ocr and images:
                    upd("🔤 استخراج النصوص من الصور...")
                    progress.progress(30)
                    for img_url in images[:3]:
                        try:
                            r2 = requests.get(img_url, timeout=10)
                            if r2.status_code == 200:
                                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                                    tf.write(r2.content)
                                    tmp = tf.name
                                t = ocr_image_tesseract(tmp) or ocr_image_gemini(tmp, api_key)
                                if t: ocr_text += f"\n{t}"
                                os.unlink(tmp)
                        except Exception:
                            pass

                if improve_ar and full_text:
                    upd("✍️ تحسين النص العربي...")
                    progress.progress(45)
                    full_text = improve_arabic_text(full_text, api_key)

                upd("🧠 التحليل بالذكاء الاصطناعي...")
                progress.progress(60)
                if not full_text:
                    full_text = f"منشور من @{username} — {tweet_url}"
                analysis = run_analysis(full_text, api_key, analysis_mode, ocr_text, "", username, upd)

                acc_data, prof_analysis = {}, {}
                extended_tweets = []
                if enable_profile:
                    upd("👤 جلب بيانات الحساب...")
                    progress.progress(75)
                    acc_data = fetch_account_details_nitter(username, api_key)

                    if deep_profile:
                        upd("🔬 جلب آخر المنشورات (قد يستغرق دقيقة)...")
                        extended_tweets = fetch_multiple_pages_nitter(username, max_pages=MAX_POSTS_FETCH)

                    if api_key:
                        upd("📊 تحليل طبيعة الحساب...")
                        prof_analysis = analyze_account_profile(acc_data, api_key, extended_tweets, upd)

                progress.progress(100)
                status.empty()
                progress.empty()
                st.success("✅ اكتمل التحليل بنجاح!")
                st.markdown("---")

                if acc_data:
                    display_account_info_card(acc_data)
                display_analysis_results(analysis, username)
                if prof_analysis:
                    st.markdown("---")
                    display_profile_analysis(prof_analysis)

                st.markdown("---")
                full_report = {
                    "tweet_id": tweet_id, "username": username,
                    "tweet_url": tweet_url, "tweet_text": full_text,
                    "ocr_text": ocr_text, "analysis": analysis,
                    "account_data": acc_data, "profile_analysis": prof_analysis,
                    "extended_tweets_count": len(extended_tweets),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button(
                    "⬇️ تصدير التقرير (JSON)",
                    data=json.dumps(full_report, ensure_ascii=False, indent=2),
                    file_name=f"report_{tweet_id or 'unknown'}.json",
                    mime="application/json"
                )

    # ────── تبويب 2: تحليل الحساب ──────
    with tab_profile:
        st.markdown("### 👤 تحليل ملف حساب X")
        prof_url = st.text_input(
            "رابط الحساب",
            placeholder="https://x.com/username",
            label_visibility="collapsed",
            key="p_url"
        )
        deep_p = st.checkbox("🔬 تحليل عميق (جلب أكثر منشورات)", value=False, key="deep_p")
        if st.button("🔍 تحليل الحساب", key="btn_profile"):
            if not api_key:
                st.error("❌ يرجى إدخال مفتاح Gemini API")
            elif not prof_url.strip():
                st.warning("⚠️ يرجى إدخال رابط الحساب")
            else:
                uname = extract_username_from_url(prof_url.strip())
                if not uname:
                    st.error("❌ تعذّر استخراج اسم المستخدم")
                else:
                    ext_tweets = []
                    with st.spinner("⏳ جلب بيانات الحساب..."):
                        acc = fetch_account_details_nitter(uname, api_key)
                    if deep_p:
                        with st.spinner("🔬 جلب المنشورات الموسّع..."):
                            ext_tweets = fetch_multiple_pages_nitter(uname, max_pages=MAX_POSTS_FETCH)
                    display_account_info_card(acc)
                    if api_key:
                        with st.spinner("🧠 تحليل طبيعة الحساب..."):
                            pa = analyze_account_profile(acc, api_key, ext_tweets)
                        display_profile_analysis(pa)
                    else:
                        st.warning("⚠️ أدخل مفتاح API لتفعيل التحليل الذكي")

    # ────── تبويب 3: تحليل الصورة ──────
    with tab_img:
        st.markdown("### 🖼️ تحليل صورة")
        uploaded = st.file_uploader("ارفع صورة للتحليل", type=["jpg","jpeg","png","webp"])
        if uploaded and api_key:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(uploaded.read())
                img_path = tf.name
            st.image(img_path, caption="الصورة المرفوعة", use_column_width=True)
            with st.spinner("🔍 تحليل الصورة..."):
                ocr_r = ocr_image_gemini(img_path, api_key)
            if ocr_r:
                st.markdown('<div class="sec-card"><div class="sec-title">📝 النص المستخرج</div>', unsafe_allow_html=True)
                st.text_area("", value=ocr_r, height=200, disabled=True)
                st.markdown("</div>", unsafe_allow_html=True)
                with st.spinner("🧠 تحليل المحتوى..."):
                    ia = run_analysis(ocr_r, api_key, analysis_mode)
                display_analysis_results(ia)
            os.unlink(img_path)
        elif uploaded and not api_key:
            st.error("❌ يرجى إدخال مفتاح Gemini API أولاً")

    # ────── تبويب 4: دليل الاستخدام ──────
    with tab_guide:
        st.markdown("### 📖 دليل الاستخدام")
        st.markdown("#### 🚀 البدء السريع")
        st.markdown(
            "1. احصل على مفتاح Gemini من [Google AI Studio](https://aistudio.google.com/apikey)\n"
            "2. أدخله في الشريط الجانبي\n"
            "3. الصق الرابط واضغط **تحليل**"
        )
        st.markdown("#### ✅ روابط مدعومة")
        st.code(
            "https://x.com/user/status/123456789\n"
            "https://x.com/user/status/123456789?s=20\n"
            "https://twitter.com/user/status/123456789\n"
            "https://x.com/username  ← رابط حساب",
            language=None
        )
        st.markdown("#### 🆕 مستجدات v6.8")
        st.markdown(
            "- ✅ إصلاح ظهور HTML كنص — تنظيف كامل للبيانات\n"
            "- ✅ تحسين جلب إحصاء الحساب (متابعون/يتابع/منشورات)\n"
            "- ✅ تحليل عميق: جلب حتى 200 منشور للتحليل\n"
            "- ✅ مؤشرات التقييم تعمل بالكامل مع شريط التقدم\n"
            "- ✅ الأنماط والتوصيات: محاذاة RTL كاملة\n"
            "- ✅ حذف شارة الإصدار من الصفحة الرئيسية\n"
            "- ✅ دعم كامل الوضع الليلي والنهاري"
        )
        st.markdown("#### ⚠️ حل مشكلة 429")
        st.table({
            "الحل":  ["انتظر دقيقة", "مفتاح جديد", "فعّل الفوترة"],
            "الوصف": [
                "الحد المجاني 10-15 طلب/دقيقة",
                "أنشئ مفتاحاً من aistudio.google.com/apikey",
                "يرفع الحد إلى 1000 طلب/دقيقة",
            ]
        })
        st.markdown("#### 🤖 النماذج المتاحة 2025-2026")
        st.table({
            "النموذج":    ["gemini-1.5-flash ⭐","gemini-1.5-flash-8b","gemini-2.5-flash","gemini-2.5-pro"],
            "RPM مجاني": ["15","15","10","5"],
            "RPD مجاني": ["1,500","1,500","250","100"],
        })


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
