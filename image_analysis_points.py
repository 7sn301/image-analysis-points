# ═══════════════════════════════════════════════════════════════
# المشهد التنفيذي - Executive Scene Analyzer
# الإصدار: 6.9 | إصلاح CAPTCHA + Syndication API
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
from urllib.parse import urlparse, quote, urlencode
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
# الإعدادات
# ═══════════════════════════════════════════════════════════════
APP_NAME    = "المشهد التنفيذي"
APP_VERSION = "6.9"
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
MAX_PAGES     = 10

TWEET_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/\w+/status/\d+", re.IGNORECASE
)
PROFILE_URL_PATTERN = re.compile(
    r"https?://(www\.)?(twitter\.com|x\.com)/(?!search|hashtag|i/)(\w+)/?(\?.*)?$",
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

# قائمة User Agents واقعية
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.space",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.net",
    "https://n.0x0.st",
]

# ═══════════════════════════════════════════════════════════════
# دوال مساعدة - إصلاح v6.9
# ═══════════════════════════════════════════════════════════════

def is_bot_detection_page(html_text: str) -> bool:
    """كشف صفحات CAPTCHA و Bot-Detection"""
    indicators = [
        "making sure you're not a bot",
        "making sure you",
        "cloudflare",
        "captcha",
        "just a moment",
        "challenge",
        "are you human",
        "verify you are human",
        "ddos protection",
        "security check",
        "bot check",
        "turnstile",
        "cf-browser-verification",
    ]
    text_lower = (html_text or "").lower()
    return any(ind in text_lower for ind in indicators)

def safe_text(text: str) -> str:
    """
    تنظيف النص بثلاث مراحل:
    1. استخراج النص النقي من HTML
    2. حذف أي نمط يبدو كـ HTML tag حتى بعد الـ decode
    3. تشفير HTML للعرض الآمن
    """
    if not text:
        return ""

    # المرحلة 1: استخراج النص من HTML
    raw = str(text)
    if BS4_AVAILABLE:
        clean = BeautifulSoup(raw, "html.parser").get_text(separator=" ")
    else:
        clean = re.sub(r"<[^>]+>", " ", raw)

    # المرحلة 2: حذف أي أنماط تبدو كـ HTML tags (قد تكون entities مُفككة)
    # هذا يحذف أشياء مثل: <div style="...">, <span class="...">, </div>
    clean = re.sub(r'<[a-zA-Z/][^>]{0,300}>', ' ', clean)
    # حذف attributes منفردة مثل style="..." class="..."
    clean = re.sub(r'\b(style|class|href|src|id)\s*=\s*["\'][^"\']*["\']', ' ', clean)

    clean = re.sub(r"\s+", " ", clean).strip()

    # المرحلة 3: فقط إذا بدا النص طبيعياً (ليس كوداً برمجياً)
    if len(clean) < 3 or looks_like_code(clean):
        return ""

    return html_module.escape(clean)

def looks_like_code(text: str) -> bool:
    """هل يبدو النص كـ HTML/CSS code؟"""
    code_patterns = [
        r'<\w+',           # HTML tags
        r'>\s*<',          # nested tags
        r'div|span|class=', # HTML elements
        r'\{[^}]{5,}\}',   # CSS blocks
        r'margin|padding|border-radius',  # CSS properties
    ]
    score = sum(1 for p in code_patterns if re.search(p, text, re.IGNORECASE))
    return score >= 2  # إذا وجدنا 2+ مؤشرات، فهو كود

def fmt_number(n: int) -> str:
    if n and n > 0:
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    return "—"

def get_headers(referer: str = "") -> Dict:
    return {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":  "document",
        "Sec-Fetch-Mode":  "navigate",
        "Cache-Control":   "no-cache",
        **({"Referer": referer} if referer else {}),
    }

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
        if u.lower() not in ("search","hashtag","i","intent","home","explore","notifications"):
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
    vpn = {"detected": False, "risk_level": "منخفض", "indicators": [], "score": 0}
    bio = str(account_data.get("bio", "") or "").lower()
    loc = str(account_data.get("location", "") or "").lower()
    for kw in ["vpn","proxy","tor","anonymous","nordvpn","expressvpn","surfshark","hide.me"]:
        if kw in bio:
            vpn["indicators"].append(f"مؤشر في البيو: {kw}")
            vpn["score"] += 25
    for suspect in ["netherlands","هولندا","switzerland","سويسرا","iceland","panama"]:
        if suspect in loc:
            vpn["indicators"].append(f"موقع مشبوه: {loc}")
            vpn["score"] += 15
            break
    if vpn["score"] >= 40:
        vpn["detected"] = True; vpn["risk_level"] = "عالٍ"
    elif vpn["score"] >= 15:
        vpn["detected"] = True; vpn["risk_level"] = "متوسط"
    return vpn

# ═══════════════════════════════════════════════════════════════
# جلب بيانات الحساب - المصادر المتعددة
# ═══════════════════════════════════════════════════════════════

def _parse_count(text: str) -> int:
    if not text:
        return 0
    text = str(text).strip().replace(",", "").replace("٬", "").replace(" ", "")
    try:
        if text.upper().endswith("K"):
            return int(float(text[:-1]) * 1_000)
        if text.upper().endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        return int(float(text))
    except Exception:
        return 0

def _empty_account(username: str) -> Dict:
    return {
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
        "fetch_method":  "",
    }

# ── المصدر 1: Twitter Syndication API ──
def fetch_via_syndication(username: str) -> Dict:
    """
    يستخدم API التضمين الخاص بتويتر لجلب بيانات الحساب.
    لا يحتاج مفتاح API.
    """
    result = _empty_account(username)
    try:
        # Token الذي يستخدمه تويتر للـ widget
        token = str(random.randint(10000000, 99999999))
        url = f"https://cdn.syndication.twimg.com/timeline/profile"
        params = {
            "screen_name": username,
            "count":       "20",
            "dnt":         "true",
            "lang":        "ar",
            "token":       token,
        }
        headers = {
            "User-Agent":  random.choice(USER_AGENTS),
            "Accept":      "application/json, text/javascript, */*",
            "Origin":      "https://platform.twitter.com",
            "Referer":     "https://platform.twitter.com/",
            "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            # استخراج بيانات المستخدم
            user = None
            if "globalObjects" in data and "users" in data["globalObjects"]:
                users = data["globalObjects"]["users"]
                if users:
                    user = list(users.values())[0]
            elif "data" in data and "user" in data["data"]:
                u = data["data"]["user"]
                user = u.get("result", {}).get("legacy", u)
            elif "timeline" in data:
                tl = data["timeline"]
                if isinstance(tl, dict):
                    user = tl.get("user", {})

            if user:
                result["display_name"]  = safe_text(user.get("name", ""))
                result["bio"]           = safe_text(user.get("description", ""))
                result["location"]      = safe_text(user.get("location", ""))
                result["verified"]      = bool(user.get("verified", False) or user.get("is_blue_verified", False))
                result["protected"]     = bool(user.get("protected", False))
                result["followers"]     = int(user.get("followers_count", 0) or 0)
                result["following"]     = int(user.get("friends_count", 0) or 0)
                result["tweets_count"]  = int(user.get("statuses_count", 0) or 0)
                result["user_id"]       = str(user.get("id_str", "") or user.get("id", ""))
                img = (user.get("profile_image_url_https", "") or
                       user.get("profile_image_url", ""))
                # الحصول على الصورة بأعلى دقة
                result["profile_image"] = img.replace("_normal", "_400x400") if img else ""

                created = user.get("created_at", "")
                if created:
                    result["joined_date"] = created

                result["connected_via"] = "Twitter Syndication API"
                result["fetch_status"]  = "success"
                result["fetch_method"]  = "syndication"

            # استخراج التغريدات الأخيرة
            tweets_raw = []
            if "globalObjects" in data and "tweets" in data["globalObjects"]:
                for tw_id, tw in data["globalObjects"]["tweets"].items():
                    text = tw.get("full_text", tw.get("text", ""))
                    if text:
                        tweets_raw.append(safe_text(text))
            elif "timeline" in data and isinstance(data["timeline"], dict):
                entries = data["timeline"].get("entries", [])
                for e in entries:
                    content = e.get("content", {})
                    tweet_data = (content.get("tweet", {}) or
                                  content.get("item", {}).get("content", {}).get("tweet", {}))
                    text = tweet_data.get("text", "")
                    if text:
                        tweets_raw.append(safe_text(text))

            result["recent_tweets"] = [t for t in tweets_raw if t][:20]

    except Exception as e:
        result["fetch_status"] = "failed"
        result["_error"] = str(e)

    return result

# ── المصدر 2: Nitter مع كشف CAPTCHA ──
def fetch_via_nitter_profile(username: str) -> Dict:
    result = _empty_account(username)

    for mirror in NITTER_MIRRORS:
        try:
            url  = f"{mirror}/{username}"
            resp = requests.get(url, headers=get_headers(mirror), timeout=12)

            if resp.status_code != 200:
                continue

            # ✅ كشف CAPTCHA - الإصلاح الرئيسي v6.9
            if is_bot_detection_page(resp.text):
                continue  # تخطّ هذه المرآة

            if not BS4_AVAILABLE:
                result["fetch_status"] = "bs4_missing"
                return result

            soup = BeautifulSoup(resp.text, "html.parser")

            # تحقق: هل هذه صفحة ملف شخصي فعلاً؟
            profile_section = (
                soup.find("div", class_=re.compile(r"profile-card|profile", re.I)) or
                soup.find("a",   class_=re.compile(r"profile-card", re.I))
            )
            if not profile_section:
                continue

            # ── الاسم ──
            for cls in ["profile-card-fullname", "profile-card-name", "fullname"]:
                el = soup.find(attrs={"class": re.compile(cls, re.I)})
                if el:
                    name = el.get_text(strip=True)
                    if name and not looks_like_code(name):
                        result["display_name"] = name
                        break

            # ── التوثيق ──
            result["verified"] = bool(
                soup.find(class_=re.compile(r"verified|checkmark|blue", re.I))
            )
            result["protected"] = bool(
                soup.find(class_=re.compile(r"protect|lock|private", re.I))
            )

            # ── البيو ──
            bio_el = soup.find(class_=re.compile(r"profile-bio|bio-description|bio", re.I))
            if bio_el:
                bio_raw = bio_el.get_text(separator=" ", strip=True)
                bio_clean = safe_text(bio_raw)
                if bio_clean and not looks_like_code(bio_clean):
                    result["bio"] = bio_clean

            # ── الإحصاء ──
            # طريقة 1: عناصر stat
            for stat in soup.find_all(class_=re.compile(r"profile-stat|stat-item", re.I)):
                num_el  = stat.find(class_=re.compile(r"stat-num|number|count", re.I))
                kind_el = stat.find(class_=re.compile(r"stat-header|label|title", re.I))
                if num_el:
                    val  = _parse_count(num_el.get_text(strip=True))
                    kind = (kind_el.get_text(strip=True).lower() if kind_el else "")
                    if   "tweet"  in kind or "post" in kind: result["tweets_count"] = val
                    elif "follow" in kind and "ing" not in kind: result["followers"] = val
                    elif "following" in kind: result["following"] = val

            # طريقة 2: روابط مباشرة
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                text = a_tag.get_text(strip=True)
                if f"/{username}/followers" in href.lower():
                    result["followers"] = _parse_count(text)
                elif f"/{username}/following" in href.lower():
                    result["following"] = _parse_count(text)

            # ── الموقع ──
            loc_el = soup.find(class_=re.compile(r"profile-location|location", re.I))
            if loc_el:
                loc = loc_el.get_text(strip=True)
                if not looks_like_code(loc):
                    result["location"] = loc

            # ── تاريخ الانضمام ──
            join_el = soup.find(class_=re.compile(r"profile-join|joindate|join-date", re.I))
            if join_el:
                join = join_el.get_text(strip=True)
                if not looks_like_code(join):
                    result["joined_date"] = join
            if not result["joined_date"]:
                for el in soup.find_all(title=re.compile(r"\d{4}")):
                    t = el.get("title", "")
                    if re.search(r"\d{4}", t):
                        result["joined_date"] = t
                        break

            # ── صورة الحساب ──
            for cls in ["profile-card-avatar", "profile-image", "avatar"]:
                img_el = soup.find("img", class_=re.compile(cls, re.I))
                if img_el:
                    src = img_el.get("src", "")
                    if src:
                        if src.startswith("/"): src = mirror + src
                        result["profile_image"] = src.replace("_normal","_400x400")
                        break

            # ── التغريدات الأخيرة ──
            for tw in soup.find_all(class_=re.compile(r"tweet-content|tweet-text", re.I), limit=20):
                text = tw.get_text(separator=" ", strip=True)
                clean = safe_text(text)
                if clean and not looks_like_code(clean) and len(clean) > 10:
                    result["recent_tweets"].append(clean)

            result["connected_via"] = mirror
            result["fetch_method"]  = "nitter"
            result["fetch_status"]  = "success" if (
                result["display_name"] or result["bio"] or result["recent_tweets"]
            ) else "partial"
            result["vpn_info"] = detect_vpn_indicators(result)
            return result

        except Exception:
            continue

    result["fetch_status"] = "failed"
    return result

# ── المصدر 3: oEmbed للتغريدة ──
def fetch_via_tweet_syndication(tweet_id: str) -> Dict:
    """جلب بيانات تغريدة محددة عبر Syndication API"""
    try:
        token = str(random.randint(10, 99))
        url   = f"https://cdn.syndication.twimg.com/tweet-result"
        params = {"id": tweet_id, "token": token, "lang": "ar"}
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept":     "application/json",
            "Origin":     "https://platform.twitter.com",
            "Referer":    "https://platform.twitter.com/",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}

def fetch_account_details(username: str, api_key: str = "") -> Dict:
    """
    يجرب المصادر بالترتيب:
    1. Twitter Syndication API (الأفضل - لا يحتاج auth)
    2. Nitter mirrors (مع كشف CAPTCHA)
    3. إرجاع بيانات فارغة مع رسالة خطأ واضحة
    """
    # المحاولة 1: Syndication API
    result = fetch_via_syndication(username)
    if result.get("fetch_status") == "success":
        result["vpn_info"] = detect_vpn_indicators(result)
        return result

    # المحاولة 2: Nitter
    nitter_result = fetch_via_nitter_profile(username)
    if nitter_result.get("fetch_status") in ("success", "partial"):
        # دمج البيانات: خذ من Syndication ما هو متاح، وأكمل من Nitter
        for field in ["display_name","bio","location","joined_date","verified",
                      "protected","followers","following","tweets_count","profile_image"]:
            if not result.get(field) and nitter_result.get(field):
                result[field] = nitter_result[field]
        if not result.get("recent_tweets"):
            result["recent_tweets"] = nitter_result.get("recent_tweets", [])
        result["connected_via"] = nitter_result.get("connected_via", "")
        result["fetch_status"]  = "partial"
        result["vpn_info"]      = detect_vpn_indicators(result)
        return result

    # لا شيء يعمل
    result["fetch_status"] = "failed"
    result["vpn_info"]     = {}
    return result

# دالة التوافق (استخدمها v6.8 كـ fetch_account_details_nitter)
fetch_account_details_nitter = fetch_account_details

# ═══════════════════════════════════════════════════════════════
# جلب التغريدة
# ═══════════════════════════════════════════════════════════════
def fetch_via_oembed(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "author_url": "", "html": "", "media_urls": [], "error": None}
    try:
        params = {"url": tweet_url, "lang": "ar"}
        resp   = requests.get("https://publish.twitter.com/oembed", params=params, timeout=10)
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

def fetch_via_syndication_tweet(tweet_id: str, tweet_url: str) -> Dict:
    """استخدام Syndication API لجلب نص التغريدة"""
    result = {"text": "", "author": "", "images": [], "error": None}
    try:
        token  = str(random.randint(10, 99))
        url    = "https://cdn.syndication.twimg.com/tweet-result"
        params = {"id": tweet_id, "token": token, "lang": "ar"}
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept":     "application/json",
            "Origin":     "https://platform.twitter.com",
            "Referer":    "https://platform.twitter.com/",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result["text"]   = safe_text(
                data.get("text", "") or data.get("full_text", "")
            )
            user = data.get("user", {})
            result["author"] = safe_text(user.get("name", ""))
            # الصور
            media = data.get("mediaDetails", []) or data.get("entities", {}).get("media", [])
            for m in media:
                url_m = m.get("media_url_https", m.get("media_url", ""))
                if url_m:
                    result["images"].append(url_m)
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
    for mirror in NITTER_MIRRORS:
        try:
            url  = f"{mirror}/{username}/status/{tweet_id}"
            resp = requests.get(url, headers=get_headers(mirror), timeout=10)
            if resp.status_code != 200:
                continue
            if is_bot_detection_page(resp.text):
                continue
            if not BS4_AVAILABLE:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            content = soup.find(class_=re.compile(r"tweet-content|tweet-text", re.I))
            if content:
                result["text"] = safe_text(content.get_text(separator=" ", strip=True))
            name_el = soup.find(class_=re.compile(r"fullname", re.I))
            if name_el:
                result["author"] = safe_text(name_el.get_text(strip=True))
            for img in soup.find_all("img", class_=re.compile(r"still-image|tweet-image", re.I)):
                src = img.get("src", "")
                if src:
                    if src.startswith("/"): src = mirror + src
                    result["images"].append(src)
            if result["text"]:
                return result
        except Exception:
            continue
    result["error"] = "فشل جلب التغريدة"
    return result

def fetch_tweet_with_media(tweet_url: str) -> Dict:
    result = {"text": "", "author": "", "username": "", "images": [], "source": "", "error": None}
    tweet_url = normalize_tweet_url(tweet_url)
    tweet_id  = extract_tweet_id(tweet_url)

    # المحاولة 1: Syndication API
    if tweet_id:
        syn = fetch_via_syndication_tweet(tweet_id, tweet_url)
        if syn.get("text"):
            result["text"]   = syn["text"]
            result["author"] = syn["author"]
            result["images"] = syn["images"]
            result["source"] = "Syndication API"

    # المحاولة 2: oEmbed
    if not result["text"]:
        oembed = fetch_via_oembed(tweet_url)
        if not oembed.get("error") and oembed.get("text"):
            result["text"]   = oembed["text"]
            result["author"] = oembed["author"]
            result["source"] = "oEmbed"

    # المحاولة 3: Nitter
    if not result["text"]:
        nit = fetch_via_nitter_tweet(tweet_url)
        if not nit.get("error") and nit.get("text"):
            result["text"]   = nit["text"]
            result["author"] = nit["author"]
            result["images"] = nit["images"]
            result["source"] = "Nitter"

    result["username"] = extract_username_from_url(tweet_url) or ""
    return result

# ═══════════════════════════════════════════════════════════════
# جلب صفحات متعددة
# ═══════════════════════════════════════════════════════════════
def fetch_multiple_pages_nitter(username: str, max_pages: int = 10) -> List[str]:
    all_tweets = []
    for mirror in NITTER_MIRRORS:
        cursor = ""
        page   = 0
        try:
            while page < max_pages:
                url = f"{mirror}/{username}"
                if cursor:
                    url += f"?cursor={quote(cursor)}"
                resp = requests.get(url, headers=get_headers(mirror), timeout=12)
                if resp.status_code != 200:
                    break
                if is_bot_detection_page(resp.text):
                    break
                if not BS4_AVAILABLE:
                    break
                soup  = BeautifulSoup(resp.text, "html.parser")
                found = False
                for tw in soup.find_all(class_=re.compile(r"tweet-content|tweet-text", re.I)):
                    text = safe_text(tw.get_text(separator=" ", strip=True))
                    if text and not looks_like_code(text) and len(text) > 10:
                        all_tweets.append(text)
                        found = True
                if not found:
                    break
                next_el = soup.find("a", class_=re.compile(r"show-more|next|load-more", re.I))
                if next_el and next_el.get("href"):
                    m = re.search(r"cursor=([^&]+)", next_el["href"])
                    cursor = m.group(1) if m else ""
                    if not cursor:
                        break
                else:
                    break
                page += 1
                time.sleep(0.8)
            if all_tweets:
                return all_tweets
        except Exception:
            continue
    return all_tweets

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
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp  = model.generate_content(["استخرج كل النصوص:", Image.open(image_path)])
        return resp.text.strip()
    except Exception:
        return ""

def transcribe_video_gemini(video_path: str, api_key: str) -> str:
    if not GENAI_AVAILABLE:
        return ""
    try:
        genai.configure(api_key=api_key)
        with open(video_path, "rb") as f:
            vd = f.read()
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp  = model.generate_content([
            "فرّغ الفيديو نصياً:",
            {"mime_type": "video/mp4", "data": base64.b64encode(vd).decode()}
        ])
        return resp.text.strip()
    except Exception:
        return ""

def improve_arabic_text(text: str, api_key: str) -> str:
    if not text or not api_key:
        return text
    result, _ = gemini_generate(api_key, f"حسّن النص العربي:\n\n{text}")
    return result or text

# ═══════════════════════════════════════════════════════════════
# بناء الـ Prompts
# ═══════════════════════════════════════════════════════════════
def build_analysis_prompt(tweet_text, mode="executive", ocr_text="", video_transcript="", username=""):
    extra = ""
    if ocr_text:        extra += f"\n\n📸 نصوص الصور:\n{ocr_text}"
    if video_transcript: extra += f"\n\n🎥 نص الفيديو:\n{video_transcript}"
    instructions = {
        "executive": "تحليل تنفيذي استخباراتي شامل",
        "media":     "تحليل إعلامي وتحقق من المحتوى",
        "security":  "تحليل أمني مفصّل للمخاطر",
        "general":   "تحليل عام شامل",
    }
    return f"""أنت محلل استخباراتي. أجرِ {instructions.get(mode,'تحليلاً شاملاً')} للمنشور التالي.

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
    all_tweets = list(account_data.get("recent_tweets", []))
    if extended_tweets:
        all_tweets = list(dict.fromkeys(all_tweets + extended_tweets))
    tweets_text  = "\n".join([f"- {t}" for t in all_tweets[:50]])
    tweets_count = len(all_tweets)
    return f"""أنت محلل استخباراتي متخصص. حلّل هذا الحساب بناءً على بياناته وتغريداته.

بيانات الحساب:
- الاسم: {account_data.get('display_name','')}
- المعرّف: @{account_data.get('username','')}
- البيو: {account_data.get('bio','')}
- الموقع: {account_data.get('location','')}
- تاريخ الانضمام: {account_data.get('joined_date','')}
- المتابعون: {account_data.get('followers',0):,}
- يتابع: {account_data.get('following',0):,}
- إجمالي المنشورات: {account_data.get('tweets_count',0):,}
- عينة منشورات ({tweets_count}):
{tweets_text}

أعد JSON فقط:
{{
  "primary_category": "معادي/مشبوه/محايد/مواطن/داعم/إعلامي/مستنجد/ساخر/متدخل خارجي",
  "risk_level": "عالٍ/متوسط/منخفض",
  "scores": {{
    "hostility": 0,
    "authenticity": 0,
    "influence": 0,
    "external_interference": 0
  }},
  "summary": "تحليل شامل للحساب",
  "patterns": ["نمط 1","نمط 2","نمط 3"],
  "recommendations": ["توصية 1","توصية 2"],
  "origin_guess": "الدولة المحتملة",
  "influence_level": "عالٍ/متوسط/منخفض",
  "content_themes": ["موضوع 1","موضوع 2"],
  "activity_pattern": "وصف نمط النشاط"
}}"""

# ═══════════════════════════════════════════════════════════════
# تنفيذ التحليل
# ═══════════════════════════════════════════════════════════════
def run_analysis(tweet_text, api_key, mode="executive", ocr_text="",
                  video_transcript="", username="", status_cb=None) -> Dict:
    prompt = build_analysis_prompt(tweet_text, mode, ocr_text, video_transcript, username)
    raw, model_used = gemini_generate(api_key, prompt, status_cb)
    if not raw:
        return {"error": "فشل التحليل"}
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        data["_model_used"] = model_used
        return data
    except Exception:
        return {"executive_summary": raw, "_model_used": model_used, "_raw": True}

def analyze_account_profile(account_data, api_key, extended_tweets=None, status_cb=None) -> Dict:
    prompt = build_profile_analysis_prompt(account_data, extended_tweets)
    raw, model_used = gemini_generate(api_key, prompt, status_cb)
    if not raw:
        return {"error": "فشل تحليل الحساب"}
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        data["_model_used"] = model_used
        return data
    except Exception:
        return {"summary": raw, "_model_used": model_used}

# ═══════════════════════════════════════════════════════════════
# CSS الشامل
# ═══════════════════════════════════════════════════════════════
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');
:root{
    --p:#1DA1F2;--pd:#0d8bd1;--gold:#F0B429;--ok:#16a34a;--err:#dc2626;
    --card:#fff;--bg:#f0f4f8;--txt:#0f172a;--sub:#334155;--muted:#64748b;
    --bdr:#e2e8f0;--shd:0 4px 20px rgba(0,0,0,.10);--r:16px;
}
@media(prefers-color-scheme:dark){
    :root{--card:#1e293b;--bg:#0f172a;--txt:#f1f5f9;--sub:#cbd5e1;
          --muted:#94a3b8;--bdr:#334155;--shd:0 4px 20px rgba(0,0,0,.40);}
}
*{font-family:'Tajawal',sans-serif!important;box-sizing:border-box;}
html,body,.stApp{direction:rtl!important;text-align:right!important;}
.stApp{background:var(--bg)!important;color:var(--txt)!important;}
p,li,span,td,th,div,label{color:var(--txt);}
.stMarkdown p{font-size:17px!important;line-height:1.9!important;color:var(--txt)!important;}

/* ── شريط جانبي ── */
section[data-testid="stSidebar"]{
    width:360px!important;min-width:360px!important;
    background:linear-gradient(180deg,#071e33 0%,#0f2b46 60%,#071e33 100%)!important;
    border-left:3px solid var(--p)!important;
}
section[data-testid="stSidebar"]>div:first-child{padding:20px 18px!important;}
section[data-testid="stSidebar"] *{color:#fff!important;font-size:17px!important;}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{color:var(--gold)!important;font-size:20px!important;}
section[data-testid="stSidebar"] label{color:#e2e8f0!important;font-size:16px!important;font-weight:600!important;}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] select{
    background:rgba(255,255,255,.12)!important;border:1px solid rgba(255,255,255,.3)!important;
    border-radius:10px!important;color:#fff!important;font-size:16px!important;padding:10px 14px!important;
}
section[data-testid="stSidebar"] .stSelectbox>div>div{
    background:rgba(255,255,255,.12)!important;border:1px solid rgba(255,255,255,.3)!important;color:#fff!important;
}
.sidebar-logo{text-align:center;font-size:54px;padding:20px 0 12px;}
.sidebar-title{text-align:center;font-size:26px!important;font-weight:900!important;color:var(--gold)!important;margin-bottom:4px;}
.sidebar-version{text-align:center;font-size:13px!important;color:rgba(255,255,255,.5)!important;margin-bottom:20px;}
.limit-table{background:rgba(255,255,255,.08);border-radius:10px;padding:12px;}
.limit-row{display:flex;justify-content:space-between;padding:6px 0;
    border-bottom:1px solid rgba(255,255,255,.1);font-size:14px!important;color:#e2e8f0!important;}

/* ── رأس الصفحة ── */
.app-header{
    background:linear-gradient(135deg,#071e33 0%,#1a4a7a 50%,#071e33 100%);
    padding:30px 40px;border-radius:20px;text-align:center;
    margin-bottom:28px;box-shadow:0 8px 40px rgba(29,161,242,.25);
}
.app-header .title{font-size:44px!important;font-weight:900!important;color:#fff!important;margin:0;}
.app-header .subtitle{font-size:18px!important;color:rgba(255,255,255,.7)!important;margin-top:6px;}

/* ── بطاقة الحساب ── */
.acc-card{
    background:linear-gradient(135deg,#071e33 0%,#1a4a7a 60%,#0d8bd1 100%);
    border-radius:20px;padding:28px 32px;margin-bottom:24px;
    box-shadow:0 8px 40px rgba(29,161,242,.25);direction:rtl;
}
.acc-card-hdr{display:flex;align-items:center;gap:18px;margin-bottom:20px;}
.acc-avatar{width:84px;height:84px;border-radius:50%;border:3px solid rgba(255,255,255,.55);object-fit:cover;flex-shrink:0;}
.acc-avatar-ph{width:84px;height:84px;border-radius:50%;background:rgba(255,255,255,.15);border:3px solid rgba(255,255,255,.4);display:flex;align-items:center;justify-content:center;font-size:38px;flex-shrink:0;}
.acc-name{font-size:28px!important;font-weight:900!important;color:#fff!important;margin:0 0 4px;}
.acc-uname{font-size:19px!important;font-weight:700!important;color:#93c5fd!important;margin:0 0 8px;}
.acc-id-box{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.35);border-radius:8px;padding:6px 14px;margin-bottom:10px;}
.acc-id-lbl{font-size:13px!important;color:#93c5fd!important;font-weight:600!important;}
.acc-id-val{font-size:17px!important;color:#fff!important;font-weight:900!important;}
.badge{display:inline-flex;align-items:center;gap:6px;border-radius:20px;padding:5px 14px;font-size:15px!important;font-weight:700!important;margin-left:6px;margin-top:4px;}
.badge-v{background:rgba(29,161,242,.3);border:1px solid rgba(29,161,242,.6);color:#fff!important;}
.badge-u{background:rgba(107,114,128,.3);border:1px solid rgba(107,114,128,.5);color:#d1d5db!important;}
.badge-p{background:rgba(240,180,41,.2);border:1px solid rgba(240,180,41,.5);color:#fcd34d!important;}
.stats-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0;}
.stat-box{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);border-radius:12px;padding:14px 8px;text-align:center;}
.stat-num{font-size:28px!important;font-weight:900!important;color:#fff!important;display:block;line-height:1.1;}
.stat-lbl{font-size:14px!important;font-weight:600!important;color:rgba(255,255,255,.65)!important;margin-top:4px;display:block;}
.details-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px;}
.detail-row{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:10px;padding:10px 14px;display:flex;align-items:center;gap:10px;direction:rtl;}
.detail-icon{font-size:20px;flex-shrink:0;}
.detail-lbl{font-size:12px!important;color:rgba(255,255,255,.55)!important;font-weight:600!important;display:block;}
.detail-val{font-size:16px!important;color:#fff!important;font-weight:700!important;display:block;}
.vpn-box{margin-top:14px;padding:12px 16px;border-radius:10px;direction:rtl;}
.vpn-h{background:rgba(220,38,38,.25);border:1px solid rgba(220,38,38,.5);color:#fca5a5!important;}
.vpn-m{background:rgba(234,88,12,.25);border:1px solid rgba(234,88,12,.5);color:#fdba74!important;}
.vpn-l{background:rgba(22,163,74,.20);border:1px solid rgba(22,163,74,.4);color:#86efac!important;}
.vpn-box *{font-size:15px!important;font-weight:700!important;}
.fetch-method{display:inline-block;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);border-radius:6px;padding:3px 10px;font-size:12px!important;color:rgba(255,255,255,.7)!important;margin-top:8px;}

/* ── بطاقات التحليل ── */
.sum-card{background:linear-gradient(135deg,#1e3a5f 0%,#1a4a7a 100%);border-right:6px solid var(--p);border-radius:16px;padding:24px 28px;margin-bottom:20px;direction:rtl;}
.sum-title{font-size:22px!important;font-weight:900!important;color:var(--gold)!important;margin-bottom:14px;display:flex;align-items:center;gap:8px;}
.sum-text{font-size:19px!important;font-weight:500!important;color:#f1f5f9!important;line-height:2!important;direction:rtl;text-align:right;}
.sec-card{background:var(--card);border-radius:16px;padding:22px 26px;margin-bottom:18px;box-shadow:var(--shd);border:1px solid var(--bdr);direction:rtl;}
.sec-title{font-size:20px!important;font-weight:800!important;color:var(--p)!important;margin-bottom:14px;display:flex;align-items:center;gap:8px;border-bottom:2px solid var(--bdr);padding-bottom:10px;direction:rtl;}
.pt-item{background:var(--bg);border-right:4px solid var(--p);border-radius:10px;padding:13px 16px;margin-bottom:10px;font-size:17px!important;font-weight:500!important;color:var(--txt)!important;line-height:1.8;direction:rtl;text-align:right;}
.risk-item{background:rgba(220,38,38,.07);border-right:4px solid #dc2626;border-radius:10px;padding:13px 16px;margin-bottom:10px;font-size:17px!important;font-weight:500!important;color:var(--txt)!important;line-height:1.8;direction:rtl;text-align:right;}
.rec-item{background:rgba(22,163,74,.07);border-right:4px solid #16a34a;border-radius:10px;padding:13px 16px;margin-bottom:10px;font-size:17px!important;font-weight:500!important;color:var(--txt)!important;line-height:1.8;direction:rtl;text-align:right;}
.sent-card{background:var(--card);border-radius:16px;padding:22px 18px;margin-bottom:18px;box-shadow:var(--shd);border:1px solid var(--bdr);text-align:center;direction:rtl;}
.sent-val{font-size:34px!important;font-weight:900!important;color:var(--p)!important;display:block;margin:10px 0;}
.sent-score{font-size:20px!important;font-weight:800!important;color:var(--sub)!important;}
.sent-pos{color:var(--ok)!important;}.sent-neg{color:var(--err)!important;}.sent-neu{color:var(--muted)!important;}
.topic-tag{display:inline-block;background:rgba(29,161,242,.12);color:var(--p)!important;border:1px solid rgba(29,161,242,.35);border-radius:20px;padding:6px 16px;font-size:15px!important;font-weight:700!important;margin:4px;}
.cat-badge{display:inline-flex;align-items:center;gap:10px;padding:12px 24px;border-radius:30px;font-size:22px!important;font-weight:900!important;color:#fff!important;margin-bottom:12px;}
.score-lbl{font-size:17px!important;font-weight:700!important;color:var(--txt)!important;margin-bottom:6px;direction:rtl;text-align:right;}
.status-box{background:rgba(29,161,242,.08);border:1px solid rgba(29,161,242,.25);border-radius:12px;padding:12px 18px;font-size:16px!important;color:var(--p)!important;font-weight:600!important;margin-bottom:12px;direction:rtl;}
.warn-box{background:rgba(234,88,12,.08);border:1px solid rgba(234,88,12,.3);border-radius:12px;padding:12px 18px;font-size:15px!important;color:#ea580c!important;font-weight:600!important;margin-bottom:12px;direction:rtl;}
.stButton>button{background:linear-gradient(135deg,var(--p) 0%,var(--pd) 100%)!important;color:#fff!important;border:none!important;border-radius:12px!important;padding:14px 28px!important;font-size:18px!important;font-weight:700!important;width:100%!important;}
.stTabs [role="tab"]{font-size:17px!important;font-weight:700!important;padding:12px 18px!important;}
.stTabs [aria-selected="true"]{color:var(--p)!important;border-bottom:3px solid var(--p)!important;}
.stTextInput input,.stTextArea textarea{font-size:17px!important;color:var(--txt)!important;border-radius:12px!important;padding:12px 16px!important;border:2px solid var(--bdr)!important;direction:rtl!important;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض بطاقة الحساب - v6.9 مُصلَحة بالكامل
# ═══════════════════════════════════════════════════════════════
def display_account_info_card(account_data: Dict):
    # استخراج البيانات بأمان
    username      = str(account_data.get("username", "") or "")
    display_name  = str(account_data.get("display_name", "") or username)
    user_id       = str(account_data.get("user_id", "") or "")
    bio_raw       = str(account_data.get("bio", "") or "")
    location      = str(account_data.get("location", "") or "")
    joined_date   = str(account_data.get("joined_date", "") or "")
    verified      = bool(account_data.get("verified", False))
    protected     = bool(account_data.get("protected", False))
    followers     = int(account_data.get("followers", 0) or 0)
    following     = int(account_data.get("following", 0) or 0)
    tweets_count  = int(account_data.get("tweets_count", 0) or 0)
    profile_img   = str(account_data.get("profile_image", "") or "")
    connected_via = str(account_data.get("connected_via", "") or "")
    vpn_info      = account_data.get("vpn_info", {}) or {}
    fetch_status  = str(account_data.get("fetch_status", ""))
    fetch_method  = str(account_data.get("fetch_method", ""))

    # ── تأكيد النصوص آمنة (لا HTML code) ──
    if looks_like_code(display_name): display_name = username
    if looks_like_code(bio_raw):      bio_raw = ""
    if looks_like_code(location):     location = ""
    if looks_like_code(joined_date):  joined_date = ""

    # تشفير للعرض الآمن
    display_name_e = html_module.escape(display_name)
    bio_e          = html_module.escape(bio_raw)
    location_e     = html_module.escape(location) if location else "غير محدد"
    joined_e       = html_module.escape(joined_date) if joined_date else "غير محدد"
    via_short      = connected_via.replace("https://","") if connected_via else "—"

    # ── Avatar ──
    if profile_img and profile_img.startswith("http"):
        avatar_html = (
            f'<img src="{profile_img}" class="acc-avatar" alt="avatar" '
            f'onerror="this.style.display=\'none\';document.getElementById(\'ph_{username}\').style.display=\'flex\'">'
            f'<div class="acc-avatar-ph" id="ph_{username}" style="display:none">👤</div>'
        )
    else:
        avatar_html = f'<div class="acc-avatar-ph" id="ph_{username}">👤</div>'

    # ── شارات ──
    v_badge = '<span class="badge badge-v">✅ موثَّق</span>' if verified else '<span class="badge badge-u">⚪ غير موثَّق</span>'
    p_badge = '<span class="badge badge-p">🔒 محمي</span>' if protected else ""

    # ── معرّف ──
    id_html = (
        f'<div class="acc-id-box">'
        f'<span class="acc-id-lbl">🪪 معرّف:</span>'
        f'<span class="acc-id-val">{html_module.escape(user_id)}</span>'
        f'</div>'
    ) if user_id else ""

    # ── Bio ──
    bio_html = (
        f'<p style="font-size:16px!important;color:rgba(255,255,255,.82)!important;'
        f'margin:0 0 16px;line-height:1.8;direction:rtl;text-align:right">{bio_e}</p>'
    ) if bio_e else ""

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

    # ── التفاصيل ──
    ratio = f"{round(followers/max(following,1),1)}x" if following > 0 else "—"
    details_html = f"""
<div class="details-grid">
  <div class="detail-row">
    <span class="detail-icon">📅</span>
    <div>
      <span class="detail-lbl">تاريخ الانضمام</span>
      <span class="detail-val">{joined_e}</span>
    </div>
  </div>
  <div class="detail-row">
    <span class="detail-icon">📍</span>
    <div>
      <span class="detail-lbl">الحساب موجود في</span>
      <span class="detail-val">{location_e}</span>
    </div>
  </div>
  <div class="detail-row">
    <span class="detail-icon">🔗</span>
    <div>
      <span class="detail-lbl">مصدر البيانات</span>
      <span class="detail-val" style="font-size:13px!important">{html_module.escape(via_short)}</span>
    </div>
  </div>
  <div class="detail-row">
    <span class="detail-icon">📊</span>
    <div>
      <span class="detail-lbl">نسبة المتابعة</span>
      <span class="detail-val">{ratio}</span>
    </div>
  </div>
</div>"""

    # ── VPN ──
    vpn_html = ""
    if vpn_info:
        risk      = str(vpn_info.get("risk_level","منخفض"))
        detected  = bool(vpn_info.get("detected",False))
        inds      = vpn_info.get("indicators",[]) or []
        css       = {"عالٍ":"vpn-h","متوسط":"vpn-m"}.get(risk,"vpn-l")
        icon      = "🔴" if risk=="عالٍ" else ("🟠" if risk=="متوسط" else "🟢")
        ind_txt   = " | ".join(inds[:2]) if inds else "لا توجد مؤشرات"
        status_t  = "⚠️ يُرجَّح استخدام VPN" if detected else "✅ لا يُرجَّح استخدام VPN"
        vpn_html  = f"""
<div class="vpn-box {css}">
  {icon} كاشف VPN — خطورة: <strong>{risk}</strong> — {status_t}
  <br><small style="font-size:13px!important;opacity:.8">{html_module.escape(ind_txt)}</small>
</div>"""

    # ── مصدر البيانات Badge ──
    method_labels = {
        "syndication": "🐦 Twitter Syndication API",
        "nitter":      "🪞 Nitter Mirror",
    }
    method_badge = f'<div class="fetch-method">{method_labels.get(fetch_method, "🔍 " + fetch_method)}</div>' if fetch_method else ""

    # ── التجميع النهائي ──
    card = f"""
<div class="acc-card">
  <div class="acc-card-hdr">
    {avatar_html}
    <div style="flex:1;direction:rtl;text-align:right">
      <div class="acc-name">{display_name_e}</div>
      <div class="acc-uname">@{html_module.escape(username)}</div>
      {id_html}
      <div style="margin-top:6px">{v_badge}{p_badge}</div>
      {method_badge}
    </div>
  </div>
  {bio_html}
  {stats_html}
  {details_html}
  {vpn_html}
</div>"""
    st.markdown(card, unsafe_allow_html=True)

    # رسائل الحالة
    if fetch_status == "failed":
        st.markdown(
            '<div class="warn-box">⚠️ تعذّر جلب بيانات الحساب — '
            'تحقق من صحة الرابط أو حاول مجدداً لاحقاً</div>',
            unsafe_allow_html=True
        )
    elif fetch_status == "partial":
        st.markdown(
            '<div class="status-box">ℹ️ بيانات جزئية — بعض المعلومات قد تكون غير مكتملة</div>',
            unsafe_allow_html=True
        )

# ═══════════════════════════════════════════════════════════════
# عرض نتائج التحليل
# ═══════════════════════════════════════════════════════════════
def display_analysis_results(analysis: Dict, username: str = ""):
    if "error" in analysis:
        st.error(f"❌ {analysis['error']}")
        return
    model_used = analysis.get("_model_used","")
    if model_used and not analysis.get("_raw"):
        st.markdown(
            f'<div class="status-box">🤖 تم التحليل بواسطة: <strong>{model_used}</strong></div>',
            unsafe_allow_html=True
        )

    summary = str(analysis.get("executive_summary","") or "")
    if summary:
        st.markdown(f"""
<div class="sum-card">
  <div class="sum-title">📋 الملخص التنفيذي</div>
  <p class="sum-text">{html_module.escape(summary)}</p>
</div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        pts = analysis.get("key_points",[]) or []
        if pts:
            items = "".join(f'<div class="pt-item">🔹 {html_module.escape(str(p))}</div>' for p in pts)
            st.markdown(f'<div class="sec-card"><div class="sec-title">🎯 النقاط الرئيسية</div>{items}</div>', unsafe_allow_html=True)
    with c2:
        risks = analysis.get("risks",[]) or []
        if risks:
            items = "".join(f'<div class="risk-item">⚠️ {html_module.escape(str(r))}</div>' for r in risks)
            st.markdown(f'<div class="sec-card"><div class="sec-title" style="color:#dc2626!important">⚠️ المخاطر</div>{items}</div>', unsafe_allow_html=True)

    recs = analysis.get("recommendations",[]) or []
    if recs:
        items = "".join(f'<div class="rec-item">✅ {html_module.escape(str(r))}</div>' for r in recs)
        st.markdown(f'<div class="sec-card" style="direction:rtl"><div class="sec-title" style="color:#16a34a!important;direction:rtl">💡 التوصيات</div>{items}</div>', unsafe_allow_html=True)

    sentiment = str(analysis.get("sentiment","") or "")
    score     = analysis.get("sentiment_score",0) or 0
    urgency   = str(analysis.get("urgency_level","") or "")
    cred      = analysis.get("credibility_score",0) or 0

    if sentiment:
        sc = "sent-pos" if "إيجابي" in sentiment else ("sent-neg" if "سلبي" in sentiment else "sent-neu")
        si = "😊" if "إيجابي" in sentiment else ("😟" if "سلبي" in sentiment else "😐")
        uc = "#dc2626" if urgency=="عالٍ" else ("#ea580c" if urgency=="متوسط" else "#16a34a")
        c1,c2,c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="sent-card"><div class="sec-title" style="justify-content:center;border:none;padding-bottom:0">🎭 المشاعر العامة</div><span class="sent-val {sc}">{si} {html_module.escape(sentiment)}</span><span class="sent-score">النسبة: {score}%</span></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="sent-card"><div class="sec-title" style="justify-content:center;border:none;padding-bottom:0">🚨 مستوى الإلحاح</div><span class="sent-val" style="color:{uc}!important">{html_module.escape(urgency)}</span></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="sent-card"><div class="sec-title" style="justify-content:center;border:none;padding-bottom:0">🔍 المصداقية</div><span class="sent-val">{cred}%</span></div>', unsafe_allow_html=True)

    topics = analysis.get("topics",[]) or []
    if topics:
        tags = "".join(f'<span class="topic-tag">{html_module.escape(str(t))}</span>' for t in topics)
        st.markdown(f'<div class="sec-card"><div class="sec-title">🏷️ الموضوعات</div><div style="direction:rtl">{tags}</div></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# عرض تحليل الملف الشخصي
# ═══════════════════════════════════════════════════════════════
def display_profile_analysis(pa: Dict):
    if "error" in pa:
        st.error(f"❌ {pa['error']}")
        return
    cat     = str(pa.get("primary_category","محايد") or "محايد")
    cat_i   = ACCOUNT_CATEGORIES.get(cat, {"icon":"⚪","color":"#6b7280","desc":""})
    summary = str(pa.get("summary","") or "")
    scores  = pa.get("scores",{}) or {}
    patterns= pa.get("patterns",[]) or []
    recs    = pa.get("recommendations",[]) or []
    themes  = pa.get("content_themes",[]) or []
    activity= str(pa.get("activity_pattern","") or "")
    origin  = str(pa.get("origin_guess","") or "")
    influence=str(pa.get("influence_level","") or "")
    risk    = str(pa.get("risk_level","") or "")
    model   = str(pa.get("_model_used","") or "")

    st.markdown(f"""
<div class="sec-card">
  <div class="sec-title">🎯 تحليل طبيعة الحساب</div>
  <div style="text-align:center;margin-bottom:16px">
    <span class="cat-badge" style="background:{cat_i['color']}">{cat_i['icon']} {html_module.escape(cat)}</span>
    <p style="font-size:17px!important;color:var(--sub)!important;margin:8px 0">{cat_i['desc']}</p>
  </div>
  {f'<div class="sum-card"><p class="sum-text">{html_module.escape(summary)}</p></div>' if summary else ''}
</div>""", unsafe_allow_html=True)

    # ── مؤشرات التقييم ──
    if scores:
        labels = {
            "hostility":             ("🔴 مستوى العدائية",   "#dc2626"),
            "authenticity":          ("✅ الأصالة",           "#16a34a"),
            "influence":             ("📢 التأثير",           "#2563eb"),
            "external_interference": ("🌐 التدخل الخارجي",   "#be185d"),
        }
        st.markdown('<div class="sec-card"><div class="sec-title">📊 مؤشرات التقييم</div>', unsafe_allow_html=True)
        for key, val in scores.items():
            lbl, _ = labels.get(key, (key, "#1DA1F2"))
            try:    pct = min(int(float(val)), 100)
            except: pct = 0
            st.markdown(f'<div class="score-lbl">{lbl}: <strong>{pct}%</strong></div>', unsafe_allow_html=True)
            st.progress(pct / 100)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── الأنماط + التوصيات ──
    c1, c2 = st.columns(2)
    with c1:
        if patterns:
            items = "".join(f'<div class="pt-item" style="direction:rtl;text-align:right">🔹 {html_module.escape(str(p))}</div>' for p in patterns)
            st.markdown(f'<div class="sec-card" style="direction:rtl;text-align:right"><div class="sec-title" style="direction:rtl">🔍 الأنماط المرصودة</div>{items}</div>', unsafe_allow_html=True)
    with c2:
        if recs:
            items = "".join(f'<div class="rec-item" style="direction:rtl;text-align:right">✅ {html_module.escape(str(r))}</div>' for r in recs)
            st.markdown(f'<div class="sec-card" style="direction:rtl;text-align:right"><div class="sec-title" style="direction:rtl;color:#16a34a!important">💡 التوصيات</div>{items}</div>', unsafe_allow_html=True)

    # ── محاور المحتوى ──
    if themes:
        tags = "".join(f'<span class="topic-tag">{html_module.escape(str(t))}</span>' for t in themes)
        act_html = f'<p style="font-size:16px!important;color:var(--sub)!important;margin-top:12px;direction:rtl;text-align:right">{html_module.escape(activity)}</p>' if activity else ""
        st.markdown(f'<div class="sec-card" style="direction:rtl"><div class="sec-title">🏷️ محاور المحتوى</div><div style="direction:rtl">{tags}</div>{act_html}</div>', unsafe_allow_html=True)

    extra = []
    if origin:    extra.append(f"🌍 الدولة: <strong>{html_module.escape(origin)}</strong>")
    if influence: extra.append(f"📢 التأثير: <strong>{html_module.escape(influence)}</strong>")
    if risk:      extra.append(f"⚡ الخطورة: <strong>{html_module.escape(risk)}</strong>")
    if model:     extra.append(f"🤖 النموذج: <strong>{html_module.escape(model)}</strong>")
    if extra:
        st.markdown(f'<div class="status-box" style="font-size:15px!important">{" &nbsp;|&nbsp; ".join(extra)}</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# الواجهة الرئيسية
# ═══════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_EMOJI}",
        page_icon=APP_EMOJI, layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    with st.sidebar:
        st.markdown(f"""
<div class="sidebar-logo">{APP_EMOJI}</div>
<div class="sidebar-title">{APP_NAME}</div>
<div class="sidebar-version">v{APP_VERSION}</div>
<hr style="border-color:rgba(255,255,255,.2);margin:16px 0">
""", unsafe_allow_html=True)

        api_key = st.text_input("🔑 مفتاح Gemini API", type="password", placeholder="AIza...")
        st.markdown("<hr style='border-color:rgba(255,255,255,.2);margin:16px 0'>", unsafe_allow_html=True)
        st.markdown("**⚙️ إعدادات التحليل**")

        analysis_mode = st.selectbox("🎯 وضع التحليل",
            options=["executive","media","security","general"],
            format_func=lambda x: {"executive":"📋 تنفيذي","media":"📰 إعلامي",
                                    "security":"🔒 أمني","general":"🔍 عام"}[x])

        enable_ocr    = st.checkbox("🔤 تفعيل OCR",               value=False)
        enable_video  = st.checkbox("🎥 تحليل الفيديو",           value=False)
        enable_profile= st.checkbox("👤 تحليل ملف الحساب",        value=True)
        deep_profile  = st.checkbox("🔬 تحليل عميق (200 منشور)",  value=False)
        improve_ar    = st.checkbox("✍️ تحسين النص العربي",       value=False)

        st.markdown("<hr style='border-color:rgba(255,255,255,.2);margin:16px 0'>", unsafe_allow_html=True)
        st.markdown("**📊 حدود الاستخدام المجاني**")
        st.markdown("""
<div class="limit-table">
  <div class="limit-row"><span>gemini-1.5-flash ⭐</span><span>15 RPM</span></div>
  <div class="limit-row"><span>gemini-1.5-flash-8b</span><span>15 RPM</span></div>
  <div class="limit-row"><span>gemini-2.5-flash</span><span>10 RPM</span></div>
  <div class="limit-row"><span>gemini-2.5-pro</span><span>5 RPM</span></div>
</div>
<hr style="border-color:rgba(255,255,255,.2);margin:16px 0">
<div style="text-align:center;font-size:13px!important;color:rgba(255,255,255,.4)!important">🔐 بياناتك محمية</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div class="app-header">
  <div class="title">{APP_EMOJI} {APP_NAME}</div>
  <div class="subtitle">منصة التحليل الاستخباراتي لمنشورات X (تويتر)</div>
</div>""", unsafe_allow_html=True)

    tab_link, tab_profile, tab_img, tab_guide = st.tabs([
        "🔗 تحليل المنشور", "👤 تحليل الحساب",
        "🖼️ تحليل الصورة",  "📖 دليل الاستخدام"
    ])

    # ────── تبويب 1: تحليل المنشور ──────
    with tab_link:
        st.markdown("### 🔗 تحليل منشور من X")
        tweet_url_input = st.text_input("رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            label_visibility="collapsed")
        c1,c2 = st.columns([3,1])
        with c1: analyze_btn = st.button("🚀 بدء التحليل", key="btn_t")
        with c2:
            if st.button("🗑️ مسح", key="btn_c"): st.rerun()

        if analyze_btn:
            if not api_key:
                st.error("❌ يرجى إدخال مفتاح Gemini API")
            elif not tweet_url_input.strip():
                st.warning("⚠️ يرجى إدخال رابط المنشور")
            elif not is_tweet_url(tweet_url_input.strip()):
                st.error("❌ الرابط غير صحيح")
            else:
                tweet_url = normalize_tweet_url(tweet_url_input.strip())
                tweet_id  = extract_tweet_id(tweet_url)
                username  = extract_username_from_url(tweet_url) or "unknown"
                prog = st.progress(0)
                stat = st.empty()
                def upd(msg): stat.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)

                upd("📡 جلب بيانات المنشور...")
                prog.progress(10)
                tweet_data = fetch_tweet_with_media(tweet_url)
                full_text  = tweet_data.get("text","")
                images     = tweet_data.get("images",[])

                ocr_text = ""
                if enable_ocr and images:
                    upd("🔤 OCR...")
                    prog.progress(30)
                    for img_url in images[:3]:
                        try:
                            r2 = requests.get(img_url, timeout=10)
                            if r2.status_code==200:
                                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                                    tf.write(r2.content); tmp=tf.name
                                t = ocr_image_tesseract(tmp) or ocr_image_gemini(tmp, api_key)
                                if t: ocr_text += f"\n{t}"
                                os.unlink(tmp)
                        except: pass

                if improve_ar and full_text:
                    upd("✍️ تحسين النص...")
                    prog.progress(45)
                    full_text = improve_arabic_text(full_text, api_key)

                upd("🧠 التحليل بالذكاء الاصطناعي...")
                prog.progress(60)
                if not full_text:
                    full_text = f"منشور من @{username} — {tweet_url}"
                analysis = run_analysis(full_text, api_key, analysis_mode, ocr_text, "", username, upd)

                acc_data, prof_analysis, ext_tweets = {}, {}, []
                if enable_profile:
                    upd("👤 جلب بيانات الحساب...")
                    prog.progress(75)
                    acc_data = fetch_account_details(username, api_key)
                    if deep_profile:
                        upd("🔬 جلب منشورات موسّعة...")
                        ext_tweets = fetch_multiple_pages_nitter(username, MAX_PAGES)
                    if api_key:
                        upd("📊 تحليل طبيعة الحساب...")
                        prof_analysis = analyze_account_profile(acc_data, api_key, ext_tweets, upd)

                prog.progress(100); stat.empty(); prog.empty()
                st.success("✅ اكتمل التحليل بنجاح!")
                st.markdown("---")
                if acc_data: display_account_info_card(acc_data)
                display_analysis_results(analysis, username)
                if prof_analysis:
                    st.markdown("---")
                    display_profile_analysis(prof_analysis)
                st.markdown("---")
                report = {
                    "tweet_id":tweet_id,"username":username,"tweet_url":tweet_url,
                    "tweet_text":full_text,"ocr_text":ocr_text,"analysis":analysis,
                    "account_data":acc_data,"profile_analysis":prof_analysis,
                    "extended_tweets_count":len(ext_tweets),
                    "timestamp":time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button("⬇️ تصدير التقرير (JSON)",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"report_{tweet_id or 'unknown'}.json", mime="application/json")

    # ────── تبويب 2: تحليل الحساب ──────
    with tab_profile:
        st.markdown("### 👤 تحليل ملف حساب X")
        prof_url = st.text_input("رابط الحساب",
            placeholder="https://x.com/username", label_visibility="collapsed", key="pu")
        deep_p = st.checkbox("🔬 جلب منشورات موسّع", value=False, key="dp")
        if st.button("🔍 تحليل الحساب", key="btn_p"):
            if not api_key:
                st.error("❌ يرجى إدخال مفتاح Gemini API")
            elif not prof_url.strip():
                st.warning("⚠️ يرجى إدخال رابط الحساب")
            else:
                uname = extract_username_from_url(prof_url.strip())
                if not uname:
                    st.error("❌ تعذّر استخراج اسم المستخدم")
                else:
                    ext = []
                    with st.spinner("⏳ جلب بيانات الحساب..."):
                        acc = fetch_account_details(uname, api_key)
                    if deep_p:
                        with st.spinner("🔬 جلب المنشورات..."):
                            ext = fetch_multiple_pages_nitter(uname, MAX_PAGES)
                    display_account_info_card(acc)
                    if api_key:
                        with st.spinner("🧠 تحليل طبيعة الحساب..."):
                            pa = analyze_account_profile(acc, api_key, ext)
                        display_profile_analysis(pa)
                    else:
                        st.warning("⚠️ أدخل مفتاح API لتفعيل التحليل الذكي")

    # ────── تبويب 3: تحليل الصورة ──────
    with tab_img:
        st.markdown("### 🖼️ تحليل صورة")
        uploaded = st.file_uploader("ارفع صورة", type=["jpg","jpeg","png","webp"])
        if uploaded and api_key:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(uploaded.read()); ip=tf.name
            st.image(ip, use_column_width=True)
            with st.spinner("🔍 تحليل..."):
                ocr_r = ocr_image_gemini(ip, api_key)
            if ocr_r:
                st.markdown('<div class="sec-card"><div class="sec-title">📝 النص المستخرج</div>', unsafe_allow_html=True)
                st.text_area("", value=ocr_r, height=200, disabled=True)
                st.markdown("</div>", unsafe_allow_html=True)
                with st.spinner("🧠 تحليل المحتوى..."):
                    ia = run_analysis(ocr_r, api_key, analysis_mode)
                display_analysis_results(ia)
            os.unlink(ip)
        elif uploaded and not api_key:
            st.error("❌ يرجى إدخال مفتاح Gemini API")

    # ────── تبويب 4: الدليل ──────
    with tab_guide:
        st.markdown("### 📖 دليل الاستخدام")
        st.markdown("#### 🚀 البدء السريع")
        st.markdown(
            "1. احصل على مفتاح Gemini من [Google AI Studio](https://aistudio.google.com/apikey)\n"
            "2. أدخله في الشريط الجانبي\n"
            "3. الصق الرابط واضغط **تحليل**"
        )
        st.markdown("#### 🆕 مستجدات v6.9 — الإصلاحات الجوهرية")
        st.markdown(
            "- ✅ **إصلاح CAPTCHA**: كشف صفحات Bot-Detection وتخطّيها تلقائياً\n"
            "- ✅ **Twitter Syndication API**: مصدر جديد لجلب بيانات الحساب مباشرة\n"
            "- ✅ **safe_text() محسّنة**: 3 مراحل تنظيف لمنع ظهور HTML كنص\n"
            "- ✅ **looks_like_code()**: كشف أي نص يشبه كوداً برمجياً\n"
            "- ✅ **User Agents** متناوبة لتجاوز الحجب\n"
            "- ✅ **مصادر متعددة**: Syndication → oEmbed → Nitter"
        )
        st.code(
            "https://x.com/user/status/123456789\n"
            "https://x.com/username  ← رابط حساب",
            language=None
        )
        st.markdown("#### ⚠️ حل مشكلة 429")
        st.table({
            "الحل":  ["انتظر دقيقة","مفتاح جديد","فعّل الفوترة"],
            "الوصف": ["الحد المجاني 10-15 طلب/دقيقة",
                      "من aistudio.google.com/apikey",
                      "يرفع الحد إلى 1000 طلب/دقيقة"]
        })
        st.markdown("#### 🤖 النماذج المتاحة")
        st.table({
            "النموذج":    ["gemini-1.5-flash ⭐","gemini-1.5-flash-8b","gemini-2.5-flash","gemini-2.5-pro"],
            "RPM مجاني": ["15","15","10","5"],
            "RPD مجاني": ["1,500","1,500","250","100"],
        })


if __name__ == "__main__":
    main()
