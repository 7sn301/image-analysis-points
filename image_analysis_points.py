# ============================================================
# المشهد التنفيذي - أداة تحليل منشورات X بالذكاء الاصطناعي
# الإصدار: 7.0
# ============================================================

import os
import re
import json
import time
import random
import hashlib
import html
import base64
from io import BytesIO
from urllib.parse import urlparse, quote

import requests
import streamlit as st

# مكتبات اختيارية
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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

# ============================================================
# الإعدادات العامة
# ============================================================
APP_NAME = "المشهد التنفيذي"
APP_VERSION = "7.0"
APP_EMOJI = "🔍"

GEMINI_MODELS = [
    {"name": "gemini-2.0-flash", "rpm": 15, "rpd": 1500},
    {"name": "gemini-1.5-flash", "rpm": 15, "rpd": 1500},
    {"name": "gemini-1.5-flash-8b", "rpm": 15, "rpd": 1500},
    {"name": "gemini-1.0-pro", "rpm": 2, "rpd": 50},
]

# Twitter Bearer Token العام (للواجهة الداخلية)
TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I6xUzrxb%2F5MoHmP1LLMEBPKdpv%2Fw%3D"

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.catsarch.com",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://twiiit.com",
    "https://nitter.moomoo.me",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

REQUEST_DELAY = 1.5
MAX_RETRIES = 3

# Regex patterns
TWEET_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", re.I
)
PROFILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(@?\w+)/?$", re.I
)

# ============================================================
# دوال مساعدة
# ============================================================

def safe_text(text, max_len=500):
    """تنظيف النص من HTML والكود"""
    if not text:
        return ""
    if isinstance(text, (int, float)):
        return str(text)
    text = str(text)
    # إزالة HTML باستخدام BeautifulSoup أو regex
    if BS4_AVAILABLE:
        try:
            text = BeautifulSoup(text, "html.parser").get_text(separator=" ")
        except:
            text = re.sub(r"<[^>]+>", " ", text)
    else:
        text = re.sub(r"<[^>]+>", " ", text)
    # إزالة HTML entities
    text = html.unescape(text)
    # إزالة أحرف خاصة
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # تنظيف المسافات
    text = re.sub(r"\s+", " ", text).strip()
    # تقليم الطول
    if max_len and len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def fmt_number(n):
    """تنسيق الأرقام الكبيرة"""
    if n is None:
        return "—"
    try:
        n = int(n)
        if n == 0:
            return "0"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except (TypeError, ValueError):
        return "—"


def get_random_headers():
    """توليد headers عشوائية واقعية"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }


def is_bot_page(text):
    """الكشف عن صفحات CAPTCHA وحجب الروبوت"""
    if not text:
        return True
    indicators = [
        "making sure you're not a bot",
        "just a moment",
        "captcha",
        "cloudflare",
        "checking your browser",
        "please wait",
        "enable javascript",
        "ddos protection",
        "access denied",
        "403 forbidden",
        "rate limit",
        "too many requests",
    ]
    text_lower = text.lower()
    return any(ind in text_lower for ind in indicators)


def is_tweet_url(url):
    return bool(TWEET_URL_RE.search(url))


def is_profile_url(url):
    return bool(PROFILE_URL_RE.search(url))


def extract_username_from_url(url):
    """استخراج اسم المستخدم من الرابط"""
    m = TWEET_URL_RE.search(url)
    if m:
        return m.group(1)
    m = PROFILE_URL_RE.search(url)
    if m:
        return m.group(1).lstrip("@")
    return None


def extract_tweet_id(url):
    """استخراج معرف التغريدة"""
    m = TWEET_URL_RE.search(url)
    if m:
        return m.group(2)
    return None


def image_to_base64(url):
    """تحويل الصورة إلى base64 للعرض"""
    try:
        headers = get_random_headers()
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "image/jpeg")
            data = base64.b64encode(r.content).decode()
            return f"data:{ct};base64,{data}"
    except Exception:
        pass
    return None


# ============================================================
# Gemini API
# ============================================================

def call_gemini(prompt, api_key, model_name=None, images=None):
    """استدعاء Gemini API مع Retry"""
    if not GEMINI_AVAILABLE or not api_key:
        return None
    
    genai.configure(api_key=api_key)
    models_to_try = [model_name] if model_name else [m["name"] for m in GEMINI_MODELS]
    
    for model in models_to_try:
        for attempt in range(MAX_RETRIES):
            try:
                m = genai.GenerativeModel(model)
                content = [prompt]
                if images:
                    for img in images:
                        if isinstance(img, dict) and "data" in img:
                            content.append({"mime_type": img.get("type", "image/jpeg"), "data": img["data"]})
                result = m.generate_content(content)
                return result.text
            except Exception as e:
                err = str(e).lower()
                if "quota" in err or "rate" in err:
                    time.sleep(2 ** attempt * 3)
                    continue
                elif "invalid" in err and "key" in err:
                    return None
                elif attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
    return None


# ============================================================
# جلب بيانات الحساب - المصدر 1: Twitter Guest API
# ============================================================

def get_guest_token():
    """الحصول على Guest Token من Twitter"""
    try:
        r = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers={
                "Authorization": f"Bearer {TWITTER_BEARER}",
                "User-Agent": random.choice(USER_AGENTS),
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("guest_token", "")
    except Exception:
        pass
    return None


def fetch_via_twitter_guest_api(username):
    """جلب بيانات الحساب عبر Twitter Guest API"""
    try:
        guest_token = get_guest_token()
        if not guest_token:
            return None

        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER}",
            "x-guest-token": guest_token,
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Referer": "https://twitter.com/",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "ar",
        }

        # GraphQL UserByScreenName
        variables = {
            "screen_name": username,
            "withSafetyModeUserFields": True,
        }
        features = {
            "hidden_profile_likes_enabled": True,
            "hidden_profile_subscriptions_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "responsive_web_twitter_article_notes_tab_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        }

        url = "https://api.twitter.com/graphql/qW5u-DAuXpMEG0zA1F7UGQ/UserByScreenName"
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features),
        }

        r = requests.get(url, headers=headers, params=params, timeout=15)
        
        if r.status_code != 200:
            return None

        data = r.json()
        user_data = (
            data.get("data", {})
            .get("user", {})
            .get("result", {})
            .get("legacy", {})
        )

        if not user_data:
            return None

        # استخراج البيانات
        avatar_url = user_data.get("profile_image_url_https", "")
        if avatar_url:
            avatar_url = avatar_url.replace("_normal", "_400x400")

        result = {
            "username": username,
            "display_name": safe_text(user_data.get("name", username)),
            "bio": safe_text(user_data.get("description", ""), 300),
            "followers": user_data.get("followers_count", 0),
            "following": user_data.get("friends_count", 0),
            "tweets_count": user_data.get("statuses_count", 0),
            "location": safe_text(user_data.get("location", "")),
            "join_date": user_data.get("created_at", ""),
            "verified": user_data.get("verified", False),
            "is_blue_verified": (
                data.get("data", {})
                .get("user", {})
                .get("result", {})
                .get("is_blue_verified", False)
            ),
            "protected": user_data.get("protected", False),
            "avatar_url": avatar_url,
            "banner_url": user_data.get("profile_banner_url", ""),
            "source": "twitter_guest_api",
        }

        # تحويل تاريخ الانضمام
        if result["join_date"]:
            try:
                from datetime import datetime
                dt = datetime.strptime(result["join_date"], "%a %b %d %H:%M:%S +0000 %Y")
                result["join_date_formatted"] = dt.strftime("%d/%m/%Y")
            except Exception:
                result["join_date_formatted"] = result["join_date"]
        else:
            result["join_date_formatted"] = "—"

        return result

    except Exception as e:
        return None


# ============================================================
# جلب بيانات الحساب - المصدر 2: FxTwitter API (من تغريدة)
# ============================================================

def fetch_via_fxtwitter(username, tweet_id):
    """جلب بيانات الحساب عبر FxTwitter API من تغريدة"""
    try:
        url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        }
        r = requests.get(url, headers=headers, timeout=15)
        
        if r.status_code != 200:
            return None

        data = r.json()
        tweet = data.get("tweet", {})
        author = tweet.get("author", {})

        if not author:
            return None

        avatar_url = author.get("avatar_url", "")
        if avatar_url and "_normal" in avatar_url:
            avatar_url = avatar_url.replace("_normal", "_400x400")

        result = {
            "username": author.get("screen_name", username),
            "display_name": safe_text(author.get("name", username)),
            "bio": safe_text(author.get("description", ""), 300),
            "followers": author.get("followers", 0),
            "following": author.get("following", 0),
            "tweets_count": author.get("statuses", 0) or author.get("tweets", 0),
            "location": safe_text(author.get("location", "")),
            "join_date": author.get("joined", ""),
            "join_date_formatted": author.get("joined", "—"),
            "verified": author.get("verified", False),
            "is_blue_verified": author.get("is_blue_verified", False),
            "protected": False,
            "avatar_url": avatar_url,
            "banner_url": author.get("banner_url", ""),
            "source": "fxtwitter",
        }
        return result

    except Exception:
        return None


# ============================================================
# جلب بيانات الحساب - المصدر 3: Nitter
# ============================================================

def fetch_via_nitter(username):
    """جلب بيانات الحساب عبر Nitter"""
    if not BS4_AVAILABLE:
        return None

    for mirror in NITTER_MIRRORS:
        try:
            url = f"{mirror}/{username}"
            headers = get_random_headers()
            headers["Referer"] = mirror
            
            r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            
            if r.status_code not in [200, 301, 302]:
                continue

            text = r.text
            if is_bot_page(text):
                continue

            soup = BeautifulSoup(text, "html.parser")
            result = {"username": username, "source": f"nitter:{mirror}"}

            # اسم العرض
            name_el = soup.select_one(".profile-card-fullname") or soup.select_one(".fullname")
            result["display_name"] = safe_text(name_el.get_text()) if name_el else username

            # البايو
            bio_el = soup.select_one(".profile-bio") or soup.select_one(".bio")
            result["bio"] = safe_text(bio_el.get_text()) if bio_el else ""

            # الموقع
            loc_el = soup.select_one(".profile-location") or soup.select_one("[data-label='location']")
            result["location"] = safe_text(loc_el.get_text()) if loc_el else ""

            # تاريخ الانضمام
            join_el = soup.select_one(".profile-joindate") or soup.select_one("[data-label='joined']") or soup.find("span", title=re.compile(r"\d{4}"))
            if join_el:
                result["join_date_formatted"] = safe_text(join_el.get_text())
            else:
                result["join_date_formatted"] = "—"

            # الإحصاءات
            stats = {}
            for item in soup.select(".profile-stat-num"):
                val_text = item.get_text(strip=True).replace(",", "")
                try:
                    val = int(val_text)
                except ValueError:
                    val = 0
                parent = item.find_parent()
                label = parent.get_text(strip=True).lower() if parent else ""
                if "tweet" in label or "post" in label:
                    stats["tweets"] = val
                elif "follow" in label and "er" in label:
                    stats["followers"] = val
                elif "follow" in label:
                    stats["following"] = val

            # طريقة بديلة لاستخراج الإحصاءات
            for item in soup.select(".profile-stat"):
                label_el = item.select_one(".profile-stat-header, .profile-stat-value")
                if not label_el:
                    continue
                header = item.get_text(strip=True).lower()
                num_el = item.select_one(".profile-stat-num")
                if num_el:
                    try:
                        val = int(num_el.get_text(strip=True).replace(",", ""))
                    except ValueError:
                        val = 0
                    if "tweet" in header or "post" in header:
                        stats["tweets"] = val
                    elif "follower" in header:
                        stats["followers"] = val
                    elif "following" in header:
                        stats["following"] = val

            result["followers"] = stats.get("followers", 0)
            result["following"] = stats.get("following", 0)
            result["tweets_count"] = stats.get("tweets", 0)

            # صورة الحساب
            avatar_el = soup.select_one(".profile-card-avatar img") or soup.select_one(".avatar img, .profile-pic")
            if avatar_el:
                avatar_src = avatar_el.get("src", "")
                if avatar_src.startswith("/"):
                    avatar_src = mirror + avatar_src
                # تحويل إلى الصورة الأصلية
                if "pbs.twimg.com" in avatar_src or "twimg.com" in avatar_src:
                    avatar_src = re.sub(r"_\w+\.(jpg|jpeg|png|webp)", r"_400x400.\1", avatar_src)
                elif avatar_src.startswith(mirror):
                    # استخراج URL الأصلي من proxy Nitter
                    m = re.search(r"url=([^&]+)", avatar_src)
                    if m:
                        from urllib.parse import unquote
                        avatar_src = unquote(m.group(1))
                result["avatar_url"] = avatar_src
            else:
                result["avatar_url"] = ""

            # التحقق
            verified_el = soup.select_one(".verified-icon, .profile-verified, .icon-verified")
            result["verified"] = bool(verified_el)
            result["is_blue_verified"] = result["verified"]
            result["protected"] = bool(soup.select_one(".lock-icon, .protected"))

            # إذا حصلنا على بيانات صالحة
            if result.get("followers", 0) > 0 or result.get("display_name", username) != username:
                return result

        except Exception:
            continue

    return None


# ============================================================
# دمج مصادر البيانات
# ============================================================

def fetch_account_details(username, tweet_id=None):
    """جلب بيانات الحساب من مصادر متعددة مع fallback"""
    username = username.lstrip("@").strip()
    
    # المصدر 1: Twitter Guest API (الأفضل - يعيد كل البيانات)
    with st.spinner(f"🔍 جاري جلب بيانات @{username} عبر Twitter API..."):
        result = fetch_via_twitter_guest_api(username)
        if result and (result.get("followers", 0) > 0 or result.get("display_name", username) != username):
            return result

    # المصدر 2: FxTwitter (إذا كان لدينا tweet_id)
    if tweet_id:
        with st.spinner(f"🔍 جاري جلب البيانات عبر FxTwitter..."):
            result = fetch_via_fxtwitter(username, tweet_id)
            if result and result.get("followers", 0) > 0:
                return result

    # المصدر 3: Nitter
    with st.spinner(f"🔍 جاري جلب البيانات عبر Nitter..."):
        result = fetch_via_nitter(username)
        if result:
            return result

    # fallback: بيانات فارغة
    return {
        "username": username,
        "display_name": username,
        "bio": "",
        "followers": None,
        "following": None,
        "tweets_count": None,
        "location": "",
        "join_date_formatted": "—",
        "verified": False,
        "is_blue_verified": False,
        "protected": False,
        "avatar_url": "",
        "source": "unavailable",
    }


# ============================================================
# جلب بيانات التغريدة
# ============================================================

def fetch_tweet_data(url):
    """جلب بيانات التغريدة من مصادر متعددة"""
    username = extract_username_from_url(url)
    tweet_id = extract_tweet_id(url)
    
    tweet_data = {"url": url, "username": username, "tweet_id": tweet_id}
    media_urls = []

    # FxTwitter
    if tweet_id and username:
        try:
            fx_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
            r = requests.get(fx_url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                tweet = data.get("tweet", {})
                if tweet:
                    tweet_data.update({
                        "text": safe_text(tweet.get("text", ""), 2000),
                        "likes": tweet.get("likes", 0),
                        "retweets": tweet.get("retweets", 0),
                        "replies": tweet.get("replies", 0),
                        "views": tweet.get("views", 0),
                        "created_at": tweet.get("created_at", ""),
                        "lang": tweet.get("lang", ""),
                    })
                    # الوسائط
                    media = tweet.get("media", {})
                    if media:
                        for img in media.get("photos", []):
                            media_urls.append(img.get("url", ""))
                        for vid in media.get("videos", []):
                            media_urls.append(vid.get("thumbnail_url", ""))
        except Exception:
            pass

    # Twitter oEmbed كبديل
    if not tweet_data.get("text") and tweet_id:
        try:
            oembed_url = f"https://publish.twitter.com/oembed?url={quote(url)}&omit_script=1"
            r = requests.get(oembed_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                tweet_data["html_embed"] = data.get("html", "")
                # استخراج النص من HTML
                if BS4_AVAILABLE and data.get("html"):
                    soup = BeautifulSoup(data["html"], "html.parser")
                    tweet_data["text"] = safe_text(soup.get_text())
        except Exception:
            pass

    tweet_data["media_urls"] = [u for u in media_urls if u]
    return tweet_data


# ============================================================
# بناء Prompt التحليل
# ============================================================

def build_tweet_analysis_prompt(tweet_data, account_data=None):
    username = tweet_data.get("username", "غير معروف")
    text = tweet_data.get("text", "")
    
    prompt = f"""أنت محلل استخباراتي متخصص في تحليل منشورات منصة X (تويتر).

قم بتحليل المنشور التالي بشكل شامل ومفصل:

**معلومات المنشور:**
- الحساب: @{username}
- النص: {text or 'غير متاح'}
- الإعجابات: {tweet_data.get('likes', '—')}
- إعادة النشر: {tweet_data.get('retweets', '—')}
- الردود: {tweet_data.get('replies', '—')}
- المشاهدات: {tweet_data.get('views', '—')}
"""
    
    if account_data:
        prompt += f"""
**معلومات الحساب:**
- المتابعون: {fmt_number(account_data.get('followers'))}
- يتابع: {fmt_number(account_data.get('following'))}
- المنشورات: {fmt_number(account_data.get('tweets_count'))}
"""

    prompt += """
**التحليل المطلوب (بالعربية):**

```json
{
  "ملخص_المحتوى": "ملخص موجز",
  "الموضوع_الرئيسي": "الموضوع",
  "التوجه_السياسي": "التوجه إن وجد",
  "مؤشرات_التأثير": {
    "مستوى_التفاعل": "مرتفع/متوسط/منخفض",
    "نطاق_الانتشار": "تقدير",
    "درجة_الخطورة": "1-10"
  },
  "الأنماط_الملاحظة": ["نمط1", "نمط2"],
  "التوصيات": ["توصية1", "توصية2"],
  "التقييم_العام": "تقييم شامل"
}
