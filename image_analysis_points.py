# ============================================================
# المشهد التنفيذي - Executive Scene Analyzer
# النسخة: v6.6 | استخراج بيانات الحساب التفصيلية
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
APP_VERSION = "6.6"
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
PROFILE_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/([^/?\s]+)/?$",
    re.IGNORECASE
)

ACCOUNT_CATEGORIES = {
    "معادي":        {"icon": "🔴", "color": "#dc2626", "desc": "محتوى معادٍ أو مثير للفتنة"},
    "مشبوه":        {"icon": "🟠", "color": "#d97706", "desc": "أنماط مشبوهة تستوجب المراقبة"},
    "محايد":        {"icon": "🟡", "color": "#ca8a04", "desc": "محتوى عام بدون توجه واضح"},
    "مواطن":        {"icon": "🟢", "color": "#059669", "desc": "مواطن عادي يتفاعل بشكل طبيعي"},
    "داعم":         {"icon": "💙", "color": "#1DA1F2", "desc": "داعم للقيادة والتوجهات الوطنية"},
    "إعلامي":       {"icon": "📰", "color": "#7c3aed", "desc": "حساب إعلامي أو صحفي"},
    "مستنجد":       {"icon": "🆘", "color": "#0891b2", "desc": "يطلب المساعدة أو يشكو"},
    "ساخر":         {"icon": "😏", "color": "#be185d", "desc": "أسلوب تهكمي على المسؤولين"},
    "متدخل خارجي": {"icon": "⚠️", "color": "#7f1d1d", "desc": "تدخل في الشأن الداخلي السعودي"},
}

# ════════════════════════════════════════════════════════════
def is_tweet_url(url: str) -> bool:
    return bool(TWEET_URL_PATTERN.match(url.strip()))

def is_profile_url(url: str) -> bool:
    u = url.strip().rstrip("/")
    if TWEET_URL_PATTERN.match(u):
        return False
    return bool(PROFILE_URL_PATTERN.match(u))

def extract_tweet_id(url: str) -> Optional[str]:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None

def extract_username_from_url(url: str) -> str:
    m = re.search(r"(?:twitter\.com|x\.com)/([^/?\s]+?)(?:/|$|\?)", url, re.IGNORECASE)
    if m:
        uname = m.group(1)
        if uname.lower() not in ("status", "i", "home", "explore", "notifications"):
            return f"@{uname}"
    return ""

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
# 🔍  استخراج بيانات الحساب التفصيلية — الجديد v6.6
# ════════════════════════════════════════════════════════════

def detect_vpn_indicators(profile_data: Dict) -> Dict:
    """
    يكشف مؤشرات استخدام VPN أو البروكسي بناءً على:
    - التناقض بين الموقع المُعلن والدولة المتصل منها
    - استخدام متصفحات/تطبيقات مرتبطة بـ VPN
    - تغيير مستمر في موقع النشر
    """
    indicators = []
    risk_level = "منخفض"
    score = 0

    location  = (profile_data.get("location") or "").lower()
    connected = (profile_data.get("connected_via") or "").lower()
    country   = (profile_data.get("country") or "").lower()

    # مؤشر 1: التطبيق المتصل به
    vpn_apps = ["vpn", "proxy", "tor", "onion", "nord", "express", "proton"]
    for app in vpn_apps:
        if app in connected:
            indicators.append("يستخدم تطبيقاً مرتبطاً بـ VPN: " + connected)
            score += 4
            break

    # مؤشر 2: تناقض الموقع والدولة
    arabic_countries = ["saudi", "uae", "egypt", "jordan", "iraq", "syria", "kuwait", "qatar",
                        "السعودية", "الامارات", "مصر", "الاردن", "العراق", "سوريا", "الكويت"]
    non_arabic_countries = ["united kingdom", "uk", "usa", "united states", "germany",
                            "france", "netherlands", "sweden", "canada", "australia"]

    location_is_arabic = any(c in location for c in arabic_countries)
    country_is_non_arabic = any(c in country for c in non_arabic_countries)
    connected_is_non_arabic = any(c in connected for c in non_arabic_countries)

    if location_is_arabic and (country_is_non_arabic or connected_is_non_arabic):
        indicators.append("تناقض: الموقع المُعلن عربي لكن الاتصال من دولة غربية")
        score += 5

    # مؤشر 3: دولة الاتصال (UK/US شائعة للـ VPN)
    if "united kingdom" in connected or "uk" in connected:
        indicators.append("الاتصال من المملكة المتحدة (شائع في VPN)")
        score += 2

    if "netherlands" in connected or "هولندا" in connected:
        indicators.append("الاتصال من هولندا (مركز خوادم VPN)")
        score += 3

    # تحديد مستوى الخطر
    if score >= 6:
        risk_level = "عالي"
    elif score >= 3:
        risk_level = "متوسط"
    else:
        risk_level = "منخفض"

    return {
        "vpn_indicators": indicators,
        "vpn_risk_level": risk_level,
        "vpn_score": score,
        "likely_using_vpn": score >= 3,
    }

def fetch_account_details_nitter(username: str) -> Dict:
    """
    استخراج بيانات الحساب التفصيلية:
    - الاسم المعروض
    - المعرف (@handle)
    - الـ User ID الرقمي
    - الدولة / الموقع
    - تاريخ الانضمام
    - التحقق (verified)
    - التطبيق المتصل به (connected via)
    - موثّق منذ
    - عدد المتابعين / المتابَعين
    - عدد المنشورات
    - مؤشرات VPN
    """
    result = {
        "display_name":   "",
        "username":       username,
        "user_id":        "",
        "bio":            "",
        "location":       "",
        "country":        "",
        "joined_date":    "",
        "verified":       False,
        "verified_since": "",
        "connected_via":  "",
        "followers":      "",
        "following":      "",
        "tweets_count":   "",
        "website":        "",
        "profile_image":  "",
        "recent_tweets":  [],
        "pinned_tweet":   "",
        "is_private":     False,
        "error":          "",
        # مؤشرات VPN
        "vpn_info":       {},
    }

    clean_username = username.lstrip("@")

    for mirror in NITTER_MIRRORS:
        try:
            url  = f"{mirror}/{clean_username}"
            resp = requests.get(url, timeout=12,
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 404:
                result["error"] = "الحساب غير موجود"
                return result
            if resp.status_code != 200:
                continue

            if not BS4_AVAILABLE:
                result["error"] = "BeautifulSoup غير متوفر"
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── الاسم المعروض ──────────────────────────────
            name_el = soup.find("a", class_="profile-card-fullname")
            if not name_el:
                name_el = soup.find("div", class_="profile-card-fullname")
            if name_el:
                result["display_name"] = name_el.get_text(strip=True)

            # ── السيرة الذاتية ─────────────────────────────
            bio_el = soup.find("div", class_="profile-bio")
            if bio_el:
                result["bio"] = bio_el.get_text(separator=" ", strip=True)

            # ── الموقع / الدولة ────────────────────────────
            loc_el = soup.find("div", class_="profile-location")
            if loc_el:
                loc_text = loc_el.get_text(strip=True)
                result["location"] = loc_text
                # محاولة استخراج الدولة
                country_patterns = [
                    "Saudi Arabia", "السعودية", "United Kingdom", "UK", "USA",
                    "United States", "Egypt", "مصر", "UAE", "الامارات",
                    "Jordan", "الاردن", "Iraq", "العراق", "Qatar", "قطر",
                    "Kuwait", "الكويت", "Germany", "France", "Netherlands",
                    "Sweden", "Canada", "Australia", "Turkey", "تركيا",
                ]
                for cp in country_patterns:
                    if cp.lower() in loc_text.lower():
                        result["country"] = cp
                        break

            # ── تاريخ الانضمام ────────────────────────────
            joined_el = soup.find("div", class_="profile-joindate")
            if not joined_el:
                # بحث بديل
                for span in soup.find_all("span"):
                    txt = span.get_text(strip=True)
                    if "انضم" in txt or "joined" in txt.lower() or "تاريخ" in txt:
                        result["joined_date"] = txt
                        break
            else:
                span_el = joined_el.find("span", title=True)
                result["joined_date"] = span_el["title"] if span_el and span_el.get("title") else joined_el.get_text(strip=True)

            # ── التحقق ────────────────────────────────────
            verified_el = soup.find("span", class_="verified-icon")
            if not verified_el:
                verified_el = soup.find("i", class_=lambda c: c and "verified" in c)
            result["verified"] = verified_el is not None

            # ── الإحصائيات ────────────────────────────────
            stats_container = soup.find("ul", class_="profile-stats")
            if stats_container:
                stat_items = stats_container.find_all("li")
                for item in stat_items:
                    header = item.find("span", class_="profile-stat-header")
                    num    = item.find("span", class_="profile-stat-num")
                    if header and num:
                        lbl = header.get_text(strip=True).lower()
                        val = num.get_text(strip=True)
                        if "tweet" in lbl or "منشور" in lbl or "post" in lbl:
                            result["tweets_count"] = val
                        elif "following" in lbl or "يتابع" in lbl:
                            result["following"] = val
                        elif "follower" in lbl or "متابع" in lbl:
                            result["followers"] = val

            # ── الموقع الإلكتروني ─────────────────────────
            website_el = soup.find("div", class_="profile-website")
            if website_el:
                a_el = website_el.find("a")
                result["website"] = a_el["href"] if a_el else website_el.get_text(strip=True)

            # ── صورة الملف الشخصي ─────────────────────────
            img_el = soup.find("img", class_="profile-card-avatar")
            if not img_el:
                av_wrap = soup.find("a", class_="profile-card-avatar")
                if av_wrap:
                    img_el = av_wrap.find("img")
            if img_el and img_el.get("src"):
                src = img_el["src"]
                result["profile_image"] = f"{mirror}{src}" if src.startswith("/") else src

            # ── التغريدة المثبّتة ─────────────────────────
            pinned = soup.find("div", class_="pinned")
            if pinned:
                pinned_content = pinned.find("div", class_="tweet-content")
                if pinned_content:
                    result["pinned_tweet"] = pinned_content.get_text(separator=" ", strip=True)

            # ── أحدث المنشورات ────────────────────────────
            tweet_divs = soup.find_all("div", class_="tweet-content", limit=10)
            result["recent_tweets"] = [
                t.get_text(separator=" ", strip=True)
                for t in tweet_divs
                if t.get_text(strip=True)
            ]

            # ── محاولة استخراج User ID من الصفحة ─────────
            # Nitter يضع الـ ID في بعض الروابط
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                # /intent/user?user_id=XXXXX
                uid_match = re.search(r"user_id=(\d+)", href)
                if uid_match:
                    result["user_id"] = uid_match.group(1)
                    break

            # بحث بديل عن الـ ID في meta tags
            if not result["user_id"]:
                for meta in soup.find_all("meta"):
                    content = meta.get("content", "")
                    uid_m   = re.search(r"user_id[=:](\d+)", content)
                    if uid_m:
                        result["user_id"] = uid_m.group(1)
                        break

            # ── معلومات "متصل عبر" من آخر المنشورات ──────
            # يظهر في بعض نسخ Nitter كـ "Twitter for iPhone" أو "United Kingdom App Store"
            source_els = soup.find_all("span", class_="tweet-source")
            if not source_els:
                source_els = soup.find_all("a", class_="tweet-source")
            if source_els:
                sources = list(set([s.get_text(strip=True) for s in source_els if s.get_text(strip=True)]))
                result["connected_via"] = " | ".join(sources[:3])

            # ── حساب خاص؟ ────────────────────────────────
            private_el = soup.find("div", class_="protected")
            if not private_el:
                private_el = soup.find("span", string=lambda t: t and "protected" in t.lower())
            result["is_private"] = private_el is not None

            # ── تحليل VPN ────────────────────────────────
            result["vpn_info"] = detect_vpn_indicators(result)

            if result["display_name"] or result["recent_tweets"]:
                return result

        except Exception as e:
            result["error"] = str(e)
            continue

    # إذا فشلت Nitter، حاول Twitter oEmbed للحصول على الاسم الأساسي
    if not result["display_name"]:
        try:
            test_url  = f"https://twitter.com/{clean_username}"
            oembed_u  = f"https://publish.twitter.com/oembed?url={quote_plus(test_url)}&omit_script=true"
            r         = requests.get(oembed_u, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                result["display_name"] = data.get("author_name", "")
                # استخراج username من author_url
                au = data.get("author_url", "")
                if au:
                    m2 = re.search(r"twitter\.com/([^/?]+)", au)
                    if m2:
                        result["username"] = "@" + m2.group(1)
        except Exception:
            pass

    return result

# ════════════════════════════════════════════════════════════
NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.space",
]

def fetch_via_oembed(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "username": "", "images": [],
              "video_url": None, "is_retweet": False}
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={quote_plus(tweet_url)}&lang=ar&omit_script=true"
        resp = requests.get(oembed_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            data = resp.json()
            result["author"] = data.get("author_name", "")
            html_content = data.get("html", "")
            if BS4_AVAILABLE and html_content:
                soup  = BeautifulSoup(html_content, "html.parser")
                texts = [p.get_text(separator=" ", strip=True)
                         for p in soup.find_all("p") if p.get_text(strip=True)]
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

def fetch_via_nitter_tweet(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "username": "", "images": [],
              "video_url": None, "is_retweet": False, "error": ""}
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
        cmd = [yt_dlp_path, tweet_url, "--no-playlist", "--write-thumbnail",
               "--skip-download", "-o", os.path.join(output_dir, "%(id)s.%(ext)s"), "--quiet"]
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
        nitter = fetch_via_nitter_tweet(normalized)
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
        prompt  = ["استخرج كل النصوص الموجودة في هذه الصورة بدقة.",
                   {"mime_type": "image/jpeg", "data": img_b64}]
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
        video_b64 = base64.b64encode(video_data).decode()
        ext       = Path(video_path).suffix.lower()
        mime_map  = {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska"}
        mime_type = mime_map.get(ext, "video/mp4")
        prompt    = ["استخرج وفرّغ كل الكلام في هذا الفيديو بالعربية.",
                     {"mime_type": mime_type, "data": video_b64}]
        text, _ = gemini_generate(prompt, api_key, status_fn)
        return text or ""
    except Exception as e:
        return f"[Video Error: {e}]"

def improve_arabic_text(text: str, api_key: str, status_fn=None) -> str:
    if not text.strip() or not api_key:
        return text
    prompt = "صحّح هذا النص العربي إملائياً ونحوياً. أعد النص المحسّن فقط:\n\n" + text
    result, _ = gemini_generate(prompt, api_key, status_fn)
    return result or text

# ════════════════════════════════════════════════════════════
def build_profile_analysis_prompt(profile_data: Dict, tweet_text: str = "") -> str:
    username     = profile_data.get("username", "")
    display_name = profile_data.get("display_name", "")
    bio          = profile_data.get("bio", "")
    location     = profile_data.get("location", "")
    country      = profile_data.get("country", "")
    joined       = profile_data.get("joined_date", "")
    followers    = profile_data.get("followers", "")
    connected    = profile_data.get("connected_via", "")
    verified     = profile_data.get("verified", False)
    vpn_info     = profile_data.get("vpn_info", {})
    recent       = profile_data.get("recent_tweets", [])
    tweets_sample = "\n".join(f"- {t}" for t in recent[:8]) if recent else "(لا توجد منشورات)"
    cats_list     = " | ".join(ACCOUNT_CATEGORIES.keys())

    lines = [
        "انت محلل استخباراتي متخصص في تحليل الحسابات على منصة X في السياق السعودي.",
        "",
        "بيانات الحساب:",
        "الاسم: " + display_name,
        "المعرف: " + username,
        "السيرة الذاتية: " + (bio or "فارغة"),
        "الموقع المُعلن: " + (location or "غير محدد"),
        "الدولة: " + (country or "غير محددة"),
        "تاريخ الانضمام: " + (joined or "غير معروف"),
        "متحقق منه: " + ("نعم" if verified else "لا"),
        "متصل عبر: " + (connected or "غير معروف"),
        "المتابعون: " + (followers or "غير معروف"),
        "مؤشر VPN: " + str(vpn_info.get("vpn_risk_level", "منخفض")),
        "",
        "عينة من المنشورات الأخيرة:",
        tweets_sample,
    ]
    if tweet_text:
        lines += ["", "المنشور المحدد:", tweet_text]

    lines += [
        "",
        "التصنيفات: " + cats_list,
        "",
        "اعد JSON صحيحا فقط:",
        "{",
        '  "primary_category": "احد التصنيفات",',
        '  "secondary_category": "تصنيف ثانوي او فارغ",',
        '  "risk_level": "عالي او متوسط او منخفض",',
        '  "risk_score": 7,',
        '  "scores": {"عدائية":3,"تهكم":5,"استنجاد":2,"تدخل_خارجي":1,"دعم_وطني":8,"اعلامي":4},',
        '  "profile_summary": "وصف موجز في 2-3 جمل",',
        '  "behavioral_patterns": ["نمط 1", "نمط 2"],',
        '  "key_topics": ["موضوع 1", "موضوع 2"],',
        '  "recommendations": ["توصية 1", "توصية 2"],',
        '  "account_origin_guess": "سعودي او خليجي او عربي او اجنبي",',
        '  "influence_level": "عالي او متوسط او منخفض",',
        '  "vpn_assessment": "تقييم استخدام VPN في جملة واحدة"',
        "}",
    ]
    return "\n".join(lines)

def analyze_account_profile(profile_data: Dict, tweet_text: str, api_key: str, status_fn=None) -> Dict:
    default = {
        "primary_category": "محايد", "secondary_category": "",
        "risk_level": "منخفض", "risk_score": 0, "scores": {},
        "profile_summary": "تعذّر التحليل", "behavioral_patterns": [],
        "key_topics": [], "recommendations": [],
        "account_origin_guess": "غير محدد", "influence_level": "منخفض",
        "vpn_assessment": "",
    }
    if not api_key:
        default["profile_summary"] = "أدخل مفتاح Gemini API"
        return default

    prompt = build_profile_analysis_prompt(profile_data, tweet_text)
    if status_fn:
        status_fn("🧠 تحليل طبيعة الحساب...")

    raw_text, used_model = gemini_generate(prompt, api_key, status_fn)
    if not raw_text:
        default["profile_summary"] = "فشل التحليل"
        return default

    try:
        clean = raw_text.strip()
        clean = re.sub(r"^```json\s*", "", clean)
        clean = re.sub(r"^```\s*",     "", clean)
        clean = re.sub(r"\s*```$",     "", clean)
        result = json.loads(clean)
        result["_model_used"] = used_model
        return result
    except Exception:
        m = re.search(r"\{[\s\S]+\}", raw_text)
        if m:
            try:
                result = json.loads(m.group())
                result["_model_used"] = used_model
                return result
            except Exception:
                pass
        default["profile_summary"] = "استجابة غير منظمة"
        return default

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
        "media":     "ركز على الاسلوب الاعلامي والرسائل والجمهور.",
        "security":  "ركز على المخاطر الامنية والتحريض والمعلومات المضللة.",
        "general":   "قدم تحليلا شاملا ومتوازنا.",
    }
    focus   = focus_map.get(mode, focus_map["general"])
    rt_note = "هذا اعادة نشر" if is_retweet else ""

    lines = [
        "انت محلل ذكاء اصطناعي. حلل هذا المنشور من X.",
        "", "بيانات المنشور:", author_block, "معرف المنشور: " + tweet_id,
        "", "المحتوى:", (text if text else "(لا يوجد نص)"),
        "", "تعليمات: " + focus,
        "", "اعد JSON صحيحا فقط:",
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
        default_error["executive_summary"] = "ادخل مفتاح Gemini API"
        return default_error

    raw_text, used_model = gemini_generate(
        build_analysis_prompt(tweet_data, mode), api_key, status_fn
    )
    if not raw_text:
        default_error["executive_summary"] = "فشل التحليل – انتظر دقيقة وأعد المحاولة"
        return default_error

    try:
        clean = raw_text.strip()
        clean = re.sub(r"^```json\s*", "", clean)
        clean = re.sub(r"^```\s*",     "", clean)
        clean = re.sub(r"\s*```$",     "", clean)
        result = json.loads(clean)
        result["_model_used"] = used_model
        return result
    except Exception:
        m = re.search(r"\{[\s\S]+\}", raw_text)
        if m:
            try:
                result = json.loads(m.group())
                result["_model_used"] = used_model
                return result
            except Exception:
                pass
        default_error["executive_summary"] = "استجابة غير منظمة"
        return default_error

# ════════════════════════════════════════════════════════════
# 🎨  CSS
# ════════════════════════════════════════════════════════════
def inject_css():
    css = (
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');"
        ":root {"
        "  --bg-main:#f0f4f8;--bg-card:#ffffff;--bg-card2:#f8fafc;"
        "  --text-primary:#0f172a;--text-secondary:#334155;--text-muted:#64748b;"
        "  --border-color:#cbd5e1;"
        "  --accent-blue:#1DA1F2;--accent-dark:#0d47a1;"
        "  --accent-green:#059669;--accent-red:#dc2626;--accent-orange:#d97706;"
        "  --shadow:0 4px 16px rgba(0,0,0,0.10);--shadow-sm:0 2px 8px rgba(0,0,0,0.07);"
        "  --sidebar-bg:#1e293b;--sidebar-text:#f1f5f9;--sidebar-muted:#94a3b8;"
        "  --sidebar-border:#334155;--sidebar-card:#0f172a;"
        "}"
        "@media (prefers-color-scheme:dark){:root{"
        "  --bg-main:#0f172a;--bg-card:#1e293b;--bg-card2:#0f172a;"
        "  --text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-muted:#94a3b8;"
        "  --border-color:#334155;"
        "  --shadow:0 4px 16px rgba(0,0,0,0.40);--shadow-sm:0 2px 8px rgba(0,0,0,0.30);"
        "}}"
        "*,*::before,*::after{font-family:'Tajawal',Arial,sans-serif !important;box-sizing:border-box;}"
        "html,body{direction:rtl !important;text-align:right !important;}"
        ".stApp{background-color:var(--bg-main) !important;direction:rtl !important;}"
        ".stApp p,.stApp span,.stApp div,.stApp label,.stApp li,"
        ".stApp h1,.stApp h2,.stApp h3,.stApp h4{"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;}"
        "textarea,textarea[disabled],textarea:disabled{"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;"
        "  background-color:var(--bg-card2) !important;opacity:1 !important;"
        "  font-size:1.1rem !important;line-height:1.8 !important;}"
        "input,.stTextInput input{"
        "  direction:rtl !important;text-align:right !important;"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;"
        "  background-color:var(--bg-card) !important;"
        "  font-size:1.1rem !important;padding:10px 16px !important;"
        "  border-radius:10px !important;border:2px solid var(--border-color) !important;}"
        "[data-testid='stSidebar']{"
        "  background-color:var(--sidebar-bg) !important;direction:rtl !important;"
        "  min-width:320px !important;width:320px !important;}"
        "[data-testid='stSidebar']>div{padding:1.5rem 1.2rem !important;}"
        "[data-testid='stSidebar']*{"
        "  direction:rtl !important;text-align:right !important;"
        "  color:var(--sidebar-text) !important;-webkit-text-fill-color:var(--sidebar-text) !important;}"
        "[data-testid='stSidebar'] h1,[data-testid='stSidebar'] h2,"
        "[data-testid='stSidebar'] h3,[data-testid='stSidebar'] h4{"
        "  font-size:1.3rem !important;font-weight:800 !important;"
        "  color:#ffffff !important;-webkit-text-fill-color:#ffffff !important;"
        "  border-bottom:2px solid var(--sidebar-border);padding-bottom:8px;margin-bottom:12px;}"
        "[data-testid='stSidebar'] label,[data-testid='stSidebar'] .stCheckbox span{"
        "  font-size:1.1rem !important;font-weight:600 !important;"
        "  color:var(--sidebar-text) !important;-webkit-text-fill-color:var(--sidebar-text) !important;}"
        "[data-testid='stSidebar'] input,[data-testid='stSidebar'] .stTextInput input{"
        "  background-color:var(--sidebar-card) !important;color:#ffffff !important;"
        "  -webkit-text-fill-color:#ffffff !important;"
        "  border:2px solid var(--sidebar-border) !important;"
        "  font-size:1.05rem !important;padding:10px 14px !important;border-radius:10px !important;}"
        ".app-title{"
        "  text-align:center !important;font-size:3rem !important;font-weight:900 !important;"
        "  background:linear-gradient(135deg,#1DA1F2,#0d47a1) !important;"
        "  -webkit-background-clip:text !important;-webkit-text-fill-color:transparent !important;"
        "  padding:0.8rem 0 0.3rem 0;}"
        ".app-subtitle{"
        "  text-align:center !important;color:var(--text-muted) !important;"
        "  -webkit-text-fill-color:var(--text-muted) !important;"
        "  font-size:1.15rem !important;margin-bottom:2rem;}"
        ".stTabs [data-baseweb='tab-list']{justify-content:flex-end !important;gap:8px;}"
        ".stTabs [data-baseweb='tab']{"
        "  direction:rtl !important;font-size:1.1rem !important;font-weight:700 !important;"
        "  padding:10px 20px !important;border-radius:10px 10px 0 0 !important;}"
        # بطاقة معلومات الحساب التفصيلية
        ".account-info-card{"
        "  background:var(--bg-card) !important;border-radius:16px !important;"
        "  padding:0 !important;margin-bottom:1.5rem !important;"
        "  box-shadow:var(--shadow) !important;overflow:hidden;}"
        ".account-info-header{"
        "  background:linear-gradient(135deg,#1DA1F2,#0d47a1);"
        "  padding:1.5rem 2rem;direction:rtl;text-align:right;}"
        ".account-info-header *{color:#ffffff !important;-webkit-text-fill-color:#ffffff !important;}"
        ".account-info-name{font-size:1.8rem !important;font-weight:900 !important;margin-bottom:4px;}"
        ".account-info-handle{font-size:1.1rem !important;opacity:0.85;margin-bottom:4px;}"
        ".account-info-id{font-size:0.9rem !important;opacity:0.7;}"
        ".verified-badge{"
        "  display:inline-block;background:rgba(255,255,255,0.2);"
        "  padding:2px 10px;border-radius:12px;font-size:0.9rem;margin-right:8px;}"
        ".account-info-body{padding:1.5rem 2rem;direction:rtl;}"
        ".info-grid{"
        "  display:grid;grid-template-columns:repeat(2,1fr);gap:16px;"
        "  direction:rtl;}"
        ".info-item{"
        "  background:var(--bg-card2);border-radius:12px;"
        "  padding:12px 16px;border-right:4px solid var(--accent-blue);}"
        ".info-item-label{"
        "  font-size:0.85rem !important;color:var(--text-muted) !important;"
        "  -webkit-text-fill-color:var(--text-muted) !important;"
        "  font-weight:600;margin-bottom:4px;}"
        ".info-item-value{"
        "  font-size:1.1rem !important;color:var(--text-primary) !important;"
        "  -webkit-text-fill-color:var(--text-primary) !important;"
        "  font-weight:700;}"
        # بطاقة VPN
        ".vpn-card{"
        "  border-radius:16px !important;padding:1.5rem 2rem !important;"
        "  margin-bottom:1.5rem !important;direction:rtl !important;"
        "  text-align:right !important;}"
        ".vpn-card *{color:#ffffff !important;-webkit-text-fill-color:#ffffff !important;}"
        ".vpn-title{font-size:1.4rem !important;font-weight:900 !important;margin-bottom:12px;}"
        ".vpn-indicator{"
        "  background:rgba(255,255,255,0.15);border-radius:10px;"
        "  padding:8px 14px;margin:6px 0;font-size:1rem !important;}"
        # بطاقات عامة
        ".account-card{"
        "  background:linear-gradient(135deg,#1DA1F2,#0d47a1) !important;"
        "  border-radius:16px !important;padding:1.5rem 2rem !important;"
        "  margin-bottom:1.5rem !important;direction:rtl !important;"
        "  text-align:right !important;box-shadow:var(--shadow) !important;}"
        ".account-card *{color:#ffffff !important;-webkit-text-fill-color:#ffffff !important;}"
        ".account-name{font-size:1.6rem !important;font-weight:900 !important;margin-bottom:4px;}"
        ".account-username{font-size:1.1rem !important;opacity:0.85;}"
        ".account-model{font-size:0.9rem !important;opacity:0.7;margin-top:6px;}"
        ".retweet-tag{"
        "  display:inline-block;background:rgba(255,255,255,0.25);"
        "  padding:3px 14px;border-radius:20px;font-size:1rem !important;font-weight:700;margin-top:8px;}"
        ".profile-risk-card{"
        "  border-radius:16px !important;padding:1.5rem 2rem !important;"
        "  margin-bottom:1.2rem !important;direction:rtl !important;"
        "  text-align:right !important;box-shadow:var(--shadow) !important;}"
        ".profile-risk-card *{color:#ffffff !important;-webkit-text-fill-color:#ffffff !important;}"
        ".risk-category-name{font-size:2rem !important;font-weight:900 !important;}"
        ".risk-level-badge{"
        "  display:inline-block;padding:4px 16px;border-radius:20px;"
        "  background:rgba(255,255,255,0.2);font-size:1rem !important;font-weight:700;}"
        ".score-bar-wrap{margin:6px 0;direction:rtl;}"
        ".score-label{font-size:1rem !important;font-weight:600 !important;margin-bottom:3px;}"
        ".score-bar-bg{background:var(--border-color);border-radius:8px;height:14px;width:100%;overflow:hidden;}"
        ".score-bar-fill{height:14px;border-radius:8px;}"
        ".summary-card{"
        "  background:var(--bg-card) !important;border-radius:16px !important;"
        "  padding:1.8rem 2rem !important;margin-bottom:1.5rem !important;"
        "  border-right:6px solid var(--accent-blue) !important;"
        "  direction:rtl !important;text-align:right !important;box-shadow:var(--shadow) !important;}"
        ".summary-card .section-title{"
        "  font-size:1.4rem !important;font-weight:900 !important;"
        "  color:var(--accent-blue) !important;-webkit-text-fill-color:var(--accent-blue) !important;"
        "  margin-bottom:12px;display:block;}"
        ".summary-card .summary-text{"
        "  font-size:1.25rem !important;font-weight:500 !important;"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;"
        "  line-height:2.0 !important;}"
        ".points-card{"
        "  background:var(--bg-card) !important;border-radius:16px !important;"
        "  padding:1.5rem 1.8rem !important;margin-bottom:1.2rem !important;"
        "  direction:rtl !important;text-align:right !important;"
        "  box-shadow:var(--shadow-sm) !important;border-top:4px solid var(--accent-blue);}"
        ".risks-card{"
        "  background:var(--bg-card) !important;border-radius:16px !important;"
        "  padding:1.5rem 1.8rem !important;margin-bottom:1.2rem !important;"
        "  direction:rtl !important;text-align:right !important;"
        "  box-shadow:var(--shadow-sm) !important;border-top:4px solid var(--accent-red);}"
        ".reco-card{"
        "  background:var(--bg-card) !important;border-radius:16px !important;"
        "  padding:1.5rem 1.8rem !important;margin-bottom:1.2rem !important;"
        "  direction:rtl !important;text-align:right !important;"
        "  box-shadow:var(--shadow-sm) !important;border-top:4px solid var(--accent-green);}"
        ".meta-card{"
        "  background:var(--bg-card) !important;border-radius:16px !important;"
        "  padding:1.5rem 1.8rem !important;margin-bottom:1.2rem !important;"
        "  direction:rtl !important;text-align:right !important;box-shadow:var(--shadow-sm) !important;}"
        ".section-title-lg{"
        "  font-size:1.35rem !important;font-weight:900 !important;"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;"
        "  margin-bottom:14px;display:block;"
        "  padding-bottom:8px;border-bottom:2px solid var(--border-color);}"
        ".point-row{"
        "  display:flex;align-items:flex-start;gap:12px;"
        "  padding:12px 0;border-bottom:1px solid var(--border-color);direction:rtl;}"
        ".point-row:last-child{border-bottom:none;}"
        ".point-icon{font-size:1.3rem;flex-shrink:0;margin-top:2px;}"
        ".point-text{"
        "  font-size:1.15rem !important;font-weight:500 !important;"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;"
        "  line-height:1.8 !important;}"
        ".sentiment-value{font-size:1.8rem !important;font-weight:900 !important;margin-top:8px;}"
        ".sentiment-pos{color:#059669 !important;-webkit-text-fill-color:#059669 !important;}"
        ".sentiment-neg{color:#dc2626 !important;-webkit-text-fill-color:#dc2626 !important;}"
        ".sentiment-neu{color:#64748b !important;-webkit-text-fill-color:#64748b !important;}"
        ".topic-pill{"
        "  display:inline-block;background:rgba(29,161,242,0.12) !important;"
        "  color:var(--accent-dark) !important;-webkit-text-fill-color:var(--accent-dark) !important;"
        "  border:1.5px solid rgba(29,161,242,0.35);"
        "  padding:6px 16px;border-radius:20px;"
        "  font-size:1.05rem !important;font-weight:600 !important;margin:4px 3px;}"
        ".stProgress>div>div{background:linear-gradient(90deg,#1DA1F2,#0d47a1) !important;}"
        ".streamlit-expanderHeader,.streamlit-expanderHeader *{"
        "  font-size:1.1rem !important;font-weight:700 !important;"
        "  color:var(--text-primary) !important;-webkit-text-fill-color:var(--text-primary) !important;"
        "  direction:rtl !important;text-align:right !important;}"
        ".stButton>button{"
        "  direction:rtl !important;font-size:1.1rem !important;font-weight:700 !important;"
        "  border-radius:12px !important;padding:12px 24px !important;}"
        ".stAlert p,.stAlert div{color:var(--text-primary) !important;}"
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# 🖥️  عرض بطاقة معلومات الحساب التفصيلية — جديد v6.6
# ════════════════════════════════════════════════════════════
def display_account_info_card(account_data: Dict):
    display_name = account_data.get("display_name", "غير معروف")
    username     = account_data.get("username", "")
    user_id      = account_data.get("user_id", "")
    verified     = account_data.get("verified", False)
    joined       = account_data.get("joined_date", "")
    location     = account_data.get("location", "")
    country      = account_data.get("country", "")
    connected    = account_data.get("connected_via", "")
    followers    = account_data.get("followers", "")
    following    = account_data.get("following", "")
    tweets_count = account_data.get("tweets_count", "")
    bio          = account_data.get("bio", "")
    is_private   = account_data.get("is_private", False)
    vpn_info     = account_data.get("vpn_info", {})
    pinned       = account_data.get("pinned_tweet", "")

    verified_html = '<span class="verified-badge">✅ موثّق</span>' if verified else ""
    private_html  = '<span class="verified-badge">🔒 خاص</span>' if is_private else ""

    # ── رأس البطاقة ──────────────────────────────────────
    header_html = (
        '<div class="account-info-card">'
        '<div class="account-info-header">'
        '<div class="account-info-name">' + display_name + verified_html + private_html + "</div>"
        '<div class="account-info-handle">' + username + "</div>"
        + ('<div class="account-info-id">🔢 User ID: <code style="background:rgba(255,255,255,0.2);'
           'padding:2px 8px;border-radius:6px;color:#fff;">' + user_id + "</code></div>" if user_id else "")
        + "</div>"
    )

    # ── شبكة المعلومات ──────────────────────────────────
    def info_item(icon, label, value, border_color="#1DA1F2"):
        if not value:
            return ""
        return (
            '<div class="info-item" style="border-right-color:' + border_color + ';">'
            '<div class="info-item-label">' + icon + " " + label + "</div>"
            '<div class="info-item-value">' + str(value) + "</div>"
            "</div>"
        )

    grid_items = (
        info_item("📅", "تاريخ الانضمام",     joined,       "#1DA1F2") +
        info_item("📍", "الموقع المُعلن",      location,     "#059669") +
        info_item("🌍", "الدولة المرصودة",     country,      "#7c3aed") +
        info_item("📱", "متصل عبر",           connected,    "#d97706") +
        info_item("👥", "المتابعون",           followers,    "#0891b2") +
        info_item("➡️", "يتابع",              following,    "#0891b2") +
        info_item("📝", "عدد المنشورات",       tweets_count, "#be185d") +
        info_item("💬", "السيرة الذاتية",      bio,          "#64748b")
    )

    body_html = (
        '<div class="account-info-body">'
        '<div class="info-grid">' + grid_items + "</div>"
        + (
            '<div style="margin-top:16px;padding:12px 16px;background:var(--bg-card2);'
            'border-radius:12px;border-right:4px solid #d97706;">'
            '<div class="info-item-label">📌 المنشور المثبّت</div>'
            '<div class="point-text">' + pinned + "</div></div>"
            if pinned else ""
        )
        + "</div></div>"
    )

    st.markdown(header_html + body_html, unsafe_allow_html=True)

    # ── بطاقة VPN ────────────────────────────────────────
    vpn_risk  = vpn_info.get("vpn_risk_level", "منخفض")
    vpn_score = vpn_info.get("vpn_score", 0)
    vpn_inds  = vpn_info.get("vpn_indicators", [])
    likely    = vpn_info.get("likely_using_vpn", False)

    vpn_colors = {"عالي": "#7f1d1d", "متوسط": "#92400e", "منخفض": "#064e3b"}
    vpn_color  = vpn_colors.get(vpn_risk, "#334155")
    vpn_icon   = "🔴" if vpn_risk == "عالي" else "🟡" if vpn_risk == "متوسط" else "🟢"

    indicators_html = "".join(
        '<div class="vpn-indicator">⚠️ ' + ind + "</div>"
        for ind in vpn_inds
    ) if vpn_inds else '<div class="vpn-indicator">✅ لم يتم رصد مؤشرات VPN واضحة</div>'

    st.markdown(
        '<div class="vpn-card" style="background:linear-gradient(135deg,' + vpn_color + ',#1e293b);">'
        '<div class="vpn-title">' + vpn_icon + " كاشف VPN / البروكسي</div>"
        '<div style="font-size:1.2rem;font-weight:700;margin-bottom:10px;">'
        "مستوى الاحتمال: " + vpn_risk + " | نقاط: " + str(vpn_score) + "/10 | "
        + ("🚨 يُرجَّح استخدام VPN" if likely else "✅ لا يُرجَّح استخدام VPN")
        + "</div>"
        + indicators_html
        + "</div>",
        unsafe_allow_html=True
    )

def display_analysis_results(analysis: Dict, tweet_data: Dict):
    author   = tweet_data.get("author", "")
    username = tweet_data.get("username", "") or tweet_data.get("url_username", "")
    is_rt    = tweet_data.get("is_retweet", False)
    model    = analysis.get("_model_used", "")

    rt_tag   = '<span class="retweet-tag">🔁 إعادة نشر</span>' if is_rt else ""
    mdl_line = '<div class="account-model">🤖 نموذج: ' + model + "</div>" if model else ""
    st.markdown(
        '<div class="account-card">'
        '<div class="account-name">🐦 ' + author + "</div>"
        + ('<div class="account-username">' + username + "</div>" if username else "")
        + rt_tag + mdl_line + "</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="summary-card">'
        '<span class="section-title">📋 الملخص التنفيذي</span>'
        '<div class="summary-text">' + analysis.get("executive_summary", "—") + "</div></div>",
        unsafe_allow_html=True
    )
    kp_rows = "".join(
        '<div class="point-row"><span class="point-icon">🔹</span>'
        '<span class="point-text">' + pt + "</span></div>"
        for pt in analysis.get("key_points", [])
    )
    st.markdown(
        '<div class="points-card"><span class="section-title-lg">🎯 النقاط الرئيسية</span>'
        + kp_rows + "</div>",
        unsafe_allow_html=True
    )
    col1, col2 = st.columns(2)
    with col1:
        risk_rows = "".join(
            '<div class="point-row"><span class="point-icon">🔴</span>'
            '<span class="point-text">' + r + "</span></div>"
            for r in analysis.get("risks", [])
        )
        st.markdown(
            '<div class="risks-card"><span class="section-title-lg">⚠️ المخاطر</span>'
            + risk_rows + "</div>",
            unsafe_allow_html=True
        )
    with col2:
        rec_rows = "".join(
            '<div class="point-row"><span class="point-icon">✅</span>'
            '<span class="point-text">' + rec + "</span></div>"
            for rec in analysis.get("recommendations", [])
        )
        st.markdown(
            '<div class="reco-card"><span class="section-title-lg">💡 التوصيات</span>'
            + rec_rows + "</div>",
            unsafe_allow_html=True
        )
    col3, col4 = st.columns(2)
    sentiment = analysis.get("sentiment", "محايد")
    sent_cls  = (
        "sentiment-pos" if "ايجاب" in sentiment or "إيجاب" in sentiment
        else "sentiment-neg" if "سلب" in sentiment
        else "sentiment-neu"
    )
    with col3:
        st.markdown(
            '<div class="meta-card"><span class="section-title-lg">💬 المشاعر العامة</span>'
            '<div class="sentiment-value ' + sent_cls + '">' + sentiment + "</div></div>",
            unsafe_allow_html=True
        )
    with col4:
        topics_html = "".join(
            '<span class="topic-pill">' + t + "</span>"
            for t in analysis.get("topics", [])
        )
        st.markdown(
            '<div class="meta-card"><span class="section-title-lg">🏷️ الموضوعات</span>'
            '<div style="margin-top:10px;">' + topics_html + "</div></div>",
            unsafe_allow_html=True
        )

def display_profile_analysis(profile_analysis: Dict, profile_data: Dict):
    cat_key   = profile_analysis.get("primary_category", "محايد")
    cat_info  = ACCOUNT_CATEGORIES.get(cat_key, {"icon": "⬜", "color": "#64748b", "desc": ""})
    risk_lvl  = profile_analysis.get("risk_level", "منخفض")
    risk_score = profile_analysis.get("risk_score", 0)
    sec_cat   = profile_analysis.get("secondary_category", "")
    risk_colors = {"عالي": "#dc2626", "متوسط": "#d97706", "منخفض": "#059669"}
    risk_color  = risk_colors.get(risk_lvl, "#64748b")

    sec_html = (
        '<div style="margin-top:8px;opacity:0.85;font-size:1rem;">تصنيف ثانوي: ' + sec_cat + "</div>"
        if sec_cat else ""
    )
    st.markdown(
        '<div class="profile-risk-card" style="background:linear-gradient(135deg,'
        + cat_info["color"] + "," + risk_color + ');">'
        '<div style="font-size:3rem;">' + cat_info["icon"] + "</div>"
        '<div class="risk-category-name">' + cat_key + "</div>"
        '<div style="font-size:1rem;opacity:0.85;margin-top:4px;">' + cat_info["desc"] + "</div>"
        + sec_html
        + '<div style="margin-top:12px;">'
        '<span class="risk-level-badge">مستوى الخطر: ' + risk_lvl
        + " | نقاط: " + str(risk_score) + "/10</span></div></div>",
        unsafe_allow_html=True
    )

    scores = profile_analysis.get("scores", {})
    if scores:
        score_colors = {
            "عدائية": "#dc2626", "تهكم": "#be185d", "استنجاد": "#0891b2",
            "تدخل_خارجي": "#7f1d1d", "دعم_وطني": "#059669", "اعلامي": "#7c3aed",
        }
        score_labels = {
            "عدائية": "عدائية تجاه القيادة", "تهكم": "تهكم وسخرية",
            "استنجاد": "استنجاد وشكاوى", "تدخل_خارجي": "تدخل خارجي",
            "دعم_وطني": "دعم وطني", "اعلامي": "نشاط إعلامي",
        }
        bars_html = "".join(
            '<div class="score-bar-wrap">'
            '<div class="score-label">' + score_labels.get(k, k) + ": " + str(v) + "/10</div>"
            '<div class="score-bar-bg"><div class="score-bar-fill" style="width:'
            + str(min(int(v) * 10, 100)) + "%;background:" + score_colors.get(k, "#1DA1F2") + ';"></div></div>'
            "</div>"
            for k, v in scores.items()
        )
        st.markdown(
            '<div class="points-card"><span class="section-title-lg">📊 مقاييس التقييم</span>'
            + bars_html + "</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        '<div class="summary-card">'
        '<span class="section-title">🧠 ملخص طبيعة الحساب</span>'
        '<div class="summary-text">' + profile_analysis.get("profile_summary", "—") + "</div></div>",
        unsafe_allow_html=True
    )

    vpn_assess = profile_analysis.get("vpn_assessment", "")
    if vpn_assess:
        st.markdown(
            '<div class="meta-card"><span class="section-title-lg">🔐 تقييم VPN</span>'
            '<div class="point-text">' + vpn_assess + "</div></div>",
            unsafe_allow_html=True
        )

    col1, col2 = st.columns(2)
    with col1:
        pattern_rows = "".join(
            '<div class="point-row"><span class="point-icon">🔍</span>'
            '<span class="point-text">' + p + "</span></div>"
            for p in profile_analysis.get("behavioral_patterns", [])
        )
        st.markdown(
            '<div class="points-card"><span class="section-title-lg">🔄 الأنماط السلوكية</span>'
            + pattern_rows + "</div>",
            unsafe_allow_html=True
        )
    with col2:
        rec_rows = "".join(
            '<div class="point-row"><span class="point-icon">📌</span>'
            '<span class="point-text">' + r + "</span></div>"
            for r in profile_analysis.get("recommendations", [])
        )
        st.markdown(
            '<div class="reco-card"><span class="section-title-lg">📋 توصيات للمحلل</span>'
            + rec_rows + "</div>",
            unsafe_allow_html=True
        )

    col3, col4 = st.columns(2)
    with col3:
        topics_html = "".join(
            '<span class="topic-pill">' + t + "</span>"
            for t in profile_analysis.get("key_topics", [])
        )
        st.markdown(
            '<div class="meta-card"><span class="section-title-lg">🏷️ الموضوعات الرئيسية</span>'
            '<div style="margin-top:10px;">' + topics_html + "</div></div>",
            unsafe_allow_html=True
        )
    with col4:
        origin  = profile_analysis.get("account_origin_guess", "غير محدد")
        influ   = profile_analysis.get("influence_level", "منخفض")
        influ_c = {"عالي": "#dc2626", "متوسط": "#d97706", "منخفض": "#059669"}.get(influ, "#64748b")
        st.markdown(
            '<div class="meta-card"><span class="section-title-lg">🌍 معلومات إضافية</span>'
            '<div class="point-row"><span class="point-icon">🗺️</span>'
            '<span class="point-text">المنشأ المرجّح: <b>' + origin + "</b></span></div>"
            '<div class="point-row"><span class="point-icon">📡</span>'
            '<span class="point-text">مستوى التأثير: <b style="color:'
            + influ_c + '">' + influ + "</b></span></div></div>",
            unsafe_allow_html=True
        )

    recent = profile_data.get("recent_tweets", [])
    if recent:
        with st.expander("📜 أحدث منشورات الحساب (" + str(len(recent)) + ")", expanded=False):
            for i, tw in enumerate(recent, 1):
                st.markdown(
                    '<div class="point-row"><span class="point-icon">' + str(i) + ".</span>"
                    '<span class="point-text">' + tw + "</span></div>",
                    unsafe_allow_html=True
                )

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
    st.markdown(
        '<p class="app-subtitle">تحليل منشورات X + استخراج بيانات الحسابات | v' + APP_VERSION + "</p>",
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")
        api_key = st.text_input(
            "🔑 مفتاح Gemini API", type="password",
            help="من: https://aistudio.google.com/apikey",
            placeholder="AIzaSy..."
        )
        st.markdown("---")
        analysis_mode = st.selectbox(
            "🎯 وضع التحليل",
            ["executive", "media", "security", "general"],
            format_func=lambda x: {
                "executive": "📊 تنفيذي", "media": "📣 إعلامي",
                "security": "🔒 أمني",    "general": "🌐 عام"
            }.get(x, x)
        )
        st.markdown("---")
        enable_ocr     = st.checkbox("🖼️ تحليل الصور (OCR)",    value=True)
        enable_video   = st.checkbox("🎬 تحليل الفيديو",         value=False)
        improve_text   = st.checkbox("✨ تحسين النص العربي",     value=False)
        enable_profile = st.checkbox("🕵️ تحليل ملف الحساب",     value=True)
        enable_vpn     = st.checkbox("🔐 كاشف VPN",              value=True)
        st.markdown("---")
        st.markdown("#### 📊 حدود الاستخدام المجاني")
        st.info(
            "🥇 gemini-1.5-flash\n15 طلب/دقيقة | 1,500 طلب/يوم\n\n"
            "⚡ gemini-2.5-flash\n10 طلبات/دقيقة | 250 طلب/يوم"
        )
        st.caption("v" + APP_VERSION + " | oEmbed + Nitter + Gemini")

    tab_link, tab_profile, tab_img, tab_guide = st.tabs([
        "🔗 تحليل منشور", "🕵️ تحليل حساب", "🖼️ تحليل صورة", "📖 دليل"
    ])

    # ══════════════════════════════════════════════════════
    with tab_link:
        st.markdown("### 🔗 تحليل منشور X")
        col_a, col_b = st.columns([3, 2])
        with col_a:
            tweet_url_input = st.text_input(
                "🔗 رابط المنشور",
                placeholder="https://x.com/username/status/123456789"
            )
        with col_b:
            profile_url_input = st.text_input(
                "👤 رابط الحساب (اختياري)",
                placeholder="https://x.com/username"
            )

        if tweet_url_input:
            if is_tweet_url(tweet_url_input):
                tid   = extract_tweet_id(tweet_url_input)
                uname = extract_username_from_url(tweet_url_input)
                st.success("✅ رابط صالح | الحساب: " + uname + " | المعرّف: " + str(tid))
            else:
                st.error("❌ الرابط غير مدعوم")

        if st.button("🔍 تحليل المنشور + الحساب", type="primary", use_container_width=True):
            if not tweet_url_input or not is_tweet_url(tweet_url_input):
                st.error("❌ أدخل رابط منشور صالح")
            elif not api_key:
                st.error("❌ أدخل مفتاح Gemini API")
            else:
                status_box = st.empty()
                progress   = st.progress(0)
                log_exp    = st.expander("📋 سجل التنفيذ", expanded=False)
                log_lines: List[str] = []

                def upd(msg):
                    status_box.info("⏳ " + msg)
                    log_lines.append(msg)
                    with log_exp:
                        st.text("\n".join(log_lines[-10:]))

                progress.progress(10)
                upd("جارٍ جلب بيانات المنشور...")
                tweet_data = fetch_tweet_with_media(tweet_url_input, api_key, upd)
                progress.progress(30)

                if improve_text and tweet_data.get("text"):
                    upd("تحسين النص...")
                    tweet_data["text"] = improve_arabic_text(tweet_data["text"], api_key, upd)

                ocr_texts: List[str] = []
                if enable_ocr and tweet_data.get("images"):
                    upd("تحليل الصور...")
                    for img in tweet_data["images"][:3]:
                        t = ocr_image_tesseract(img) or ocr_image_gemini(img, api_key, upd)
                        if t.strip():
                            ocr_texts.append(t)
                progress.progress(50)

                video_transcript = ""
                if enable_video and tweet_data.get("video_path"):
                    upd("تحليل الفيديو...")
                    video_transcript = transcribe_video_gemini(tweet_data["video_path"], api_key, upd)

                full_text = tweet_data.get("text", "")
                if ocr_texts:        full_text += "\n[صور]\n"   + "\n".join(ocr_texts)
                if video_transcript: full_text += "\n[فيديو]\n" + video_transcript
                tweet_data["text"] = full_text

                upd("جارٍ التحليل التنفيذي...")
                analysis = run_analysis(tweet_data, api_key, analysis_mode, upd)
                progress.progress(70)

                account_data     = {}
                profile_analysis = {}
                if enable_profile or enable_vpn:
                    username_for = (
                        extract_username_from_url(profile_url_input)
                        if profile_url_input
                        else tweet_data.get("username", "") or tweet_data.get("url_username", "")
                    )
                    if username_for:
                        upd("جارٍ جلب بيانات الحساب...")
                        account_data = fetch_account_details_nitter(username_for)
                        if enable_profile:
                            upd("جارٍ تحليل طبيعة الحساب...")
                            profile_analysis = analyze_account_profile(
                                account_data, tweet_data.get("text", ""), api_key, upd
                            )
                progress.progress(100)
                status_box.success("✅ اكتمل التحليل!")

                st.markdown("---")
                if account_data:
                    st.markdown("## 👤 بيانات الحساب")
                    display_account_info_card(account_data)

                st.markdown("## 📰 تحليل المنشور")
                display_analysis_results(analysis, tweet_data)

                if profile_analysis:
                    st.markdown("---")
                    st.markdown("## 🕵️ تحليل طبيعة الحساب")
                    display_profile_analysis(profile_analysis, account_data)

                with st.expander("📝 النص الكامل", expanded=False):
                    st.text_area("", value=tweet_data.get("text", "(فارغ)"), height=200, disabled=True)

                export = {
                    "tweet_url": tweet_url_input,
                    "tweet_data": {k: v for k, v in tweet_data.items() if k != "video_path"},
                    "analysis": analysis,
                    "account_data": account_data,
                    "profile_analysis": profile_analysis,
                }
                st.download_button(
                    "💾 تحميل التقرير الكامل (JSON)",
                    data=json.dumps(export, ensure_ascii=False, indent=2),
                    file_name="report_" + tweet_data.get("tweet_id", "") + ".json",
                    mime="application/json"
                )

    # ══════════════════════════════════════════════════════
    with tab_profile:
        st.markdown("### 🕵️ تحليل حساب X")
        profile_only = st.text_input(
            "رابط الحساب أو المعرف",
            placeholder="https://x.com/username  أو  @username"
        )
        if st.button("🔍 استخراج بيانات الحساب + تحليله", type="primary", use_container_width=True):
            if not profile_only.strip():
                st.error("❌ أدخل رابط الحساب أو المعرف")
            elif not api_key:
                st.error("❌ أدخل مفتاح Gemini API")
            else:
                uname_in = profile_only.strip()
                if uname_in.startswith("http"):
                    uname_in = extract_username_from_url(uname_in)
                if not uname_in:
                    st.error("❌ تعذّر استخراج المعرف")
                else:
                    s2 = st.empty()
                    p2 = st.progress(0)

                    def upd2(msg):
                        s2.info("⏳ " + msg)

                    upd2("جارٍ جلب بيانات الحساب...")
                    account_data2 = fetch_account_details_nitter(uname_in)
                    p2.progress(50)

                    if not account_data2.get("display_name") and not account_data2.get("recent_tweets"):
                        st.warning("⚠️ تعذّر جلب البيانات من Nitter – سيتم التحليل بناءً على المعرف فقط")
                        account_data2["username"] = uname_in

                    upd2("جارٍ التحليل...")
                    profile_analysis2 = analyze_account_profile(account_data2, "", api_key, upd2)
                    p2.progress(100)
                    s2.success("✅ اكتمل!")

                    st.markdown("---")
                    st.markdown("## 👤 بيانات الحساب")
                    display_account_info_card(account_data2)

                    st.markdown("## 🕵️ تحليل طبيعة الحساب")
                    display_profile_analysis(profile_analysis2, account_data2)

                    st.download_button(
                        "💾 تحميل التقرير (JSON)",
                        data=json.dumps(
                            {"username": uname_in, "account_data": account_data2,
                             "profile_analysis": profile_analysis2},
                            ensure_ascii=False, indent=2
                        ),
                        file_name="profile_" + uname_in.lstrip("@") + ".json",
                        mime="application/json"
                    )

    # ══════════════════════════════════════════════════════
    with tab_img:
        st.markdown("### 🖼️ تحليل صورة مباشر")
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
                        "حلل هذه الصورة: وصف المحتوى، النصوص، المعلومات الرئيسية، التوصيات. النص المستخرج: " + (ocr_text or "لا يوجد"),
                        {"mime_type": "image/jpeg", "data": img_b64}
                    ]
                    sb3 = st.empty()
                    res3, mdl3 = gemini_generate(prompt, api_key, lambda m: sb3.info(m))
                    os.unlink(tmp_path)
                    if res3:
                        st.success("✅ النموذج: " + str(mdl3))
                        st.markdown(res3)
                    else:
                        st.error("❌ فشل التحليل")

    # ══════════════════════════════════════════════════════
    with tab_guide:
        st.markdown("### 📖 دليل الاستخدام v6.6")
        st.markdown("#### 🆕 الجديد في v6.6 — استخراج بيانات الحساب")
        st.markdown(
            "- **الاسم المعروض** + **المعرف** + **User ID الرقمي**  \n"
            "- **الدولة / الموقع** المُعلن والمرصود  \n"
            "- **تاريخ الانضمام** + التحقق + الحساب الخاص  \n"
            "- **متصل عبر** (iPhone / Android / Web / تطبيق معين)  \n"
            "- **كاشف VPN**: يكشف التناقض بين الموقع المُعلن ودولة الاتصال  \n"
            "- **إحصائيات**: متابعون، يتابع، عدد المنشورات  \n"
            "- **المنشور المثبّت**  \n"
            "- **10 منشورات أخيرة** للتحليل"
        )
        st.markdown("#### 🔐 كيف يعمل كاشف VPN؟")
        st.markdown(
            "يرصد الكاشف المؤشرات التالية:  \n"
            "1. تطبيقات مرتبطة بـ VPN في حقل 'متصل عبر'  \n"
            "2. تناقض: الموقع المُعلن عربي لكن الاتصال من دولة غربية  \n"
            "3. الاتصال من هولندا (مركز خوادم VPN)  \n"
            "4. الاتصال من المملكة المتحدة مع موقع عربي مُعلن"
        )
        st.markdown("#### ✅ الروابط المدعومة")
        st.code(
            "https://x.com/username/status/123456789\n"
            "https://x.com/username\n"
            "@username",
            language=None
        )
        st.markdown("#### 🏷️ التصنيفات")
        st.table({
            "التصنيف": list(ACCOUNT_CATEGORIES.keys()),
            "الأيقونة": [v["icon"] for v in ACCOUNT_CATEGORIES.values()],
            "الوصف":    [v["desc"] for v in ACCOUNT_CATEGORIES.values()],
        })


if __name__ == "__main__":
    main()
