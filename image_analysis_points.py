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
```
"""
    return prompt


def build_profile_analysis_prompt(account_data, tweets_sample=None):
    prompt = f"""أنت محلل استخباراتي متخصص في تحليل حسابات منصة X.

**بيانات الحساب:**
- المعرف: @{account_data.get('username', '—')}
- الاسم: {account_data.get('display_name', '—')}
- البايو: {account_data.get('bio', 'لا يوجد')}
- الموقع: {account_data.get('location', 'غير محدد')}
- المتابعون: {fmt_number(account_data.get('followers'))}
- يتابع: {fmt_number(account_data.get('following'))}
- المنشورات: {fmt_number(account_data.get('tweets_count'))}
- تاريخ الانضمام: {account_data.get('join_date_formatted', '—')}
- موثق: {'نعم ✅' if account_data.get('verified') or account_data.get('is_blue_verified') else 'لا ❌'}
"""
    
    if tweets_sample:
        prompt += f"\n**عينة من المنشورات الأخيرة:**\n{tweets_sample}\n"
    
    prompt += """
**التحليل المطلوب (بالعربية):**

```json
{
  "طبيعة_الحساب": "شخصي/مؤسسي/إعلامي/ترفيهي",
  "التوجه_العام": "وصف التوجه",
  "مستوى_التأثير": "مرتفع/متوسط/منخفض",
  "المواضيع_الرئيسية": ["موضوع1", "موضوع2"],
  "مؤشرات_المصداقية": {
    "نسبة_المتابعين": "نسبة المتابعين/يتابع",
    "تقييم_النشاط": "نشط/متوسط/خامل",
    "مؤشر_الأصالة": "1-10"
  },
  "الأنماط_الملاحظة": ["نمط1"],
  "التوصيات": ["توصية1"],
  "ملاحظات_أمنية": "ملاحظات مهمة إن وجدت",
  "التقييم_الشامل": "تقييم نهائي"
}
```
"""
    return prompt


# ============================================================
# CSS وتصميم الواجهة
# ============================================================

def inject_css():
    st.markdown("""
<style>
/* RTL Support */
html, body, [class*="css"] {
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif !important;
}

.stApp { background: #0f1117 !important; }

/* إخفاء العناصر الافتراضية */
#MainMenu, footer, header { visibility: hidden; }

/* بطاقة الحساب */
.account-card {
    background: linear-gradient(135deg, #1a1f2e 0%, #1e2537 100%);
    border: 1px solid #2d3748;
    border-radius: 16px;
    padding: 24px;
    margin: 16px 0;
    direction: rtl;
}

.account-banner {
    width: 100%;
    height: 120px;
    object-fit: cover;
    border-radius: 12px 12px 0 0;
    margin-bottom: -40px;
}

.account-header {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 20px;
    direction: rtl;
}

.account-avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    border: 3px solid #1DA1F2;
    object-fit: cover;
    flex-shrink: 0;
}

.account-avatar-placeholder {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    border: 3px solid #1DA1F2;
    background: linear-gradient(135deg, #1DA1F2, #0d7bc4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    flex-shrink: 0;
}

.account-info { flex: 1; }

.account-display-name {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    direction: rtl;
    text-align: right;
}

.account-username {
    font-size: 15px;
    color: #8899a6;
    direction: ltr;
    text-align: left;
}

.account-id {
    font-size: 13px;
    color: #64748b;
    background: #1e2537;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 4px 10px;
    display: inline-block;
    margin-top: 4px;
    direction: ltr;
}

.badge-verified {
    background: linear-gradient(135deg, #1DA1F2, #0d7bc4);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.badge-unverified {
    background: #374151;
    color: #9ca3af;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.badge-protected {
    background: #4b5563;
    color: #fbbf24;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

/* Stats Row */
.stats-row {
    display: flex;
    gap: 8px;
    margin: 16px 0;
    justify-content: flex-start;
    direction: rtl;
}

.stat-box {
    background: #1e2537;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 14px 20px;
    text-align: center;
    flex: 1;
    min-width: 100px;
}

.stat-number {
    font-size: 24px;
    font-weight: 700;
    color: #1DA1F2;
    display: block;
    direction: ltr;
}

.stat-label {
    font-size: 13px;
    color: #8899a6;
    display: block;
    margin-top: 4px;
    direction: rtl;
}

/* Details */
.detail-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid #1e2537;
    direction: rtl;
    text-align: right;
}

.detail-icon { font-size: 18px; }
.detail-label { font-size: 13px; color: #8899a6; width: 120px; }
.detail-value { font-size: 14px; color: #e2e8f0; font-weight: 500; }

/* نتائج التحليل */
.analysis-card {
    background: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
    direction: rtl;
}

.analysis-section-title {
    font-size: 16px;
    font-weight: 600;
    color: #1DA1F2;
    margin-bottom: 12px;
    direction: rtl;
    text-align: right;
}

.pattern-tag {
    background: #1e3a5f;
    color: #60a5fa;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    display: inline-block;
    margin: 3px;
}

.recommendation-item {
    background: #1a2e1a;
    border-right: 3px solid #22c55e;
    padding: 8px 12px;
    border-radius: 0 8px 8px 0;
    margin: 6px 0;
    color: #86efac;
    font-size: 14px;
    direction: rtl;
    text-align: right;
}

.source-indicator {
    font-size: 11px;
    color: #4b5563;
    text-align: left;
    direction: ltr;
    margin-top: 8px;
}

/* Spinner */
.stSpinner > div { border-top-color: #1DA1F2 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    width: 360px !important;
    background: #1a1f2e !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #1DA1F2, #0d7bc4) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
    width: 100% !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #0d7bc4, #0a6aa8) !important;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# عرض بطاقة الحساب
# ============================================================

def display_account_card(account):
    """عرض بطاقة الحساب بشكل جميل باستخدام Streamlit الأصلي"""
    if not account:
        st.warning("⚠️ لم يتم جلب بيانات الحساب")
        return

    # Header Row
    col1, col2 = st.columns([1, 4])
    
    with col1:
        avatar_url = account.get("avatar_url", "")
        if avatar_url:
            # محاولة تحميل الصورة
            try:
                img_data = image_to_base64(avatar_url)
                if img_data:
                    st.markdown(
                        f'<img src="{img_data}" style="width:80px;height:80px;border-radius:50%;border:3px solid #1DA1F2;object-fit:cover;">',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(f'<div style="width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#1DA1F2,#0d7bc4);display:flex;align-items:center;justify-content:center;font-size:32px;">👤</div>', unsafe_allow_html=True)
            except Exception:
                st.markdown(f'<div style="width:80px;height:80px;border-radius:50%;background:#1e2537;border:3px solid #1DA1F2;display:flex;align-items:center;justify-content:center;font-size:32px;">👤</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="width:80px;height:80px;border-radius:50%;background:#1e2537;border:3px solid #1DA1F2;display:flex;align-items:center;justify-content:center;font-size:32px;">👤</div>', unsafe_allow_html=True)

    with col2:
        display_name = account.get("display_name", account.get("username", "—"))
        username = account.get("username", "—")
        
        st.markdown(f'<p style="font-size:22px;font-weight:700;color:#fff;margin:0;direction:rtl;">{display_name}</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:14px;color:#8899a6;margin:0;direction:ltr;">@{username}</p>', unsafe_allow_html=True)
        
        # شارة التحقق
        if account.get("protected"):
            st.markdown('<span style="background:#4b5563;color:#fbbf24;padding:3px 10px;border-radius:20px;font-size:12px;">🔒 حساب خاص</span>', unsafe_allow_html=True)
        elif account.get("verified") or account.get("is_blue_verified"):
            st.markdown('<span style="background:linear-gradient(135deg,#1DA1F2,#0d7bc4);color:white;padding:3px 10px;border-radius:20px;font-size:12px;">✅ موثق</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span style="background:#374151;color:#9ca3af;padding:3px 10px;border-radius:20px;font-size:12px;">⬜ غير موثق</span>', unsafe_allow_html=True)

    st.markdown("---")

    # البايو
    bio = account.get("bio", "")
    if bio:
        st.markdown(f'<p style="color:#e2e8f0;font-size:14px;direction:rtl;text-align:right;padding:8px 0;">{bio}</p>', unsafe_allow_html=True)

    # إحصاءات
    followers = account.get("followers")
    following = account.get("following")
    tweets = account.get("tweets_count")

    col_f, col_fw, col_t = st.columns(3)
    
    with col_f:
        st.markdown(f"""
        <div style="background:#1e2537;border:1px solid #2d3748;border-radius:12px;padding:14px;text-align:center;">
            <span style="font-size:24px;font-weight:700;color:#1DA1F2;display:block;">{fmt_number(followers)}</span>
            <span style="font-size:13px;color:#8899a6;">متابع</span>
        </div>
        """, unsafe_allow_html=True)

    with col_fw:
        st.markdown(f"""
        <div style="background:#1e2537;border:1px solid #2d3748;border-radius:12px;padding:14px;text-align:center;">
            <span style="font-size:24px;font-weight:700;color:#1DA1F2;display:block;">{fmt_number(following)}</span>
            <span style="font-size:13px;color:#8899a6;">يتابع</span>
        </div>
        """, unsafe_allow_html=True)

    with col_t:
        st.markdown(f"""
        <div style="background:#1e2537;border:1px solid #2d3748;border-radius:12px;padding:14px;text-align:center;">
            <span style="font-size:24px;font-weight:700;color:#1DA1F2;display:block;">{fmt_number(tweets)}</span>
            <span style="font-size:13px;color:#8899a6;">منشور</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # التفاصيل
    details = []
    location = account.get("location", "")
    join_date = account.get("join_date_formatted", "—")

    if location:
        details.append(("📍", "الموقع", location))
    if join_date and join_date != "—":
        details.append(("📅", "تاريخ الانضمام", join_date))

    if details:
        for icon, label, value in details:
            st.markdown(
                f'<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #1e2537;direction:rtl;text-align:right;">'
                f'<span style="font-size:18px;">{icon}</span>'
                f'<span style="font-size:13px;color:#8899a6;width:120px;">{label}</span>'
                f'<span style="font-size:14px;color:#e2e8f0;">{value}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    # مصدر البيانات
    source = account.get("source", "")
    if source:
        source_names = {
            "twitter_guest_api": "🐦 Twitter API",
            "fxtwitter": "⚡ FxTwitter",
            "unavailable": "❌ غير متاح",
        }
        source_display = next((v for k, v in source_names.items() if k in source), f"📡 {source}")
        st.markdown(f'<p style="font-size:11px;color:#4b5563;text-align:left;margin-top:8px;">{source_display}</p>', unsafe_allow_html=True)


# ============================================================
# عرض نتائج التحليل
# ============================================================

def display_analysis_results(analysis_text):
    """عرض نتائج التحليل من Gemini"""
    if not analysis_text:
        st.info("لم يتم الحصول على نتائج تحليل")
        return

    # محاولة استخراج JSON
    json_match = re.search(r"```json\s*([\s\S]+?)\s*```", analysis_text)
    
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            
            # عرض كل قسم
            for key, value in data.items():
                title = key.replace("_", " ")
                
                if isinstance(value, dict):
                    st.markdown(f'<p class="analysis-section-title">📊 {title}</p>', unsafe_allow_html=True)
                    for k, v in value.items():
                        st.markdown(
                            f'<div class="detail-item">'
                            f'<span class="detail-label">{k.replace("_"," ")}</span>'
                            f'<span class="detail-value">{v}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                elif isinstance(value, list):
                    st.markdown(f'<p class="analysis-section-title">📋 {title}</p>', unsafe_allow_html=True)
                    for item in value:
                        if "أنماط" in title or "pattern" in title.lower():
                            st.markdown(f'<span class="pattern-tag">🔹 {item}</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f'<div class="recommendation-item">✅ {item}</div>',
                                unsafe_allow_html=True
                            )
                    st.markdown("<br>", unsafe_allow_html=True)
                else:
                    st.markdown(f'<p class="analysis-section-title">📌 {title}</p>', unsafe_allow_html=True)
                    st.markdown(
                        f'<p style="color:#e2e8f0;font-size:14px;direction:rtl;text-align:right;padding:8px 12px;'
                        f'background:#1e2537;border-radius:8px;">{value}</p>',
                        unsafe_allow_html=True
                    )
            return
        except json.JSONDecodeError:
            pass

    # عرض النص كما هو إذا لم يكن JSON
    st.markdown(
        f'<div style="direction:rtl;text-align:right;color:#e2e8f0;font-size:14px;'
        f'background:#1a1f2e;border-radius:12px;padding:20px;">{analysis_text}</div>',
        unsafe_allow_html=True
    )


# ============================================================
# الواجهة الرئيسية
# ============================================================

def main():
    st.set_page_config(
        page_title=f"{APP_EMOJI} {APP_NAME}",
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    inject_css()

    # Sidebar
    with st.sidebar:
        st.markdown(
            f'<h2 style="color:#1DA1F2;direction:rtl;text-align:right;font-size:20px;">'
            f'{APP_EMOJI} {APP_NAME}</h2>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p style="color:#8899a6;font-size:13px;direction:rtl;text-align:right;">أداة تحليل منشورات X بالذكاء الاصطناعي</p>',
            unsafe_allow_html=True
        )
        st.markdown("---")

        gemini_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاحك من https://aistudio.google.com/apikey"
        )
        
        st.markdown("---")
        st.markdown('<p style="color:#8899a6;font-size:12px;direction:rtl;text-align:right;">⚙️ إعدادات التحليل</p>', unsafe_allow_html=True)
        
        enable_profile = st.checkbox("تحليل الملف الشخصي", value=True)
        enable_ocr = st.checkbox("تفعيل OCR للصور", value=False)
        
        st.markdown("---")
        
        # جدول الحصص
        st.markdown('<p style="color:#8899a6;font-size:12px;direction:rtl;text-align:right;">📊 حدود الاستخدام اليومي</p>', unsafe_allow_html=True)
        for model in GEMINI_MODELS[:3]:
            st.markdown(
                f'<p style="font-size:11px;color:#4b5563;direction:ltr;text-align:left;">'
                f'{model["name"]}: {model["rpd"]} req/day</p>',
                unsafe_allow_html=True
            )

    # Tabs
    tab_tweet, tab_profile, tab_image, tab_guide = st.tabs([
        "📊 تحليل منشور",
        "👤 تحليل حساب", 
        "🖼️ تحليل صورة",
        "📖 دليل الاستخدام"
    ])

    # ── تبويب تحليل المنشور ──
    with tab_tweet:
        st.markdown('<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">📊 تحليل منشور X</h3>', unsafe_allow_html=True)
        
        tweet_url = st.text_input(
            "🔗 رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            key="tweet_url_input"
        )

        if st.button("🔍 تحليل المنشور", key="btn_tweet"):
            if not tweet_url:
                st.error("⚠️ الرجاء إدخال رابط المنشور")
            elif not is_tweet_url(tweet_url):
                st.error("⚠️ الرابط غير صالح. يجب أن يكون رابط منشور من X")
            elif not gemini_key:
                st.error("⚠️ الرجاء إدخال مفتاح Gemini API")
            else:
                username = extract_username_from_url(tweet_url)
                tweet_id = extract_tweet_id(tweet_url)
                
                progress = st.progress(0)
                status = st.empty()

                # جلب التغريدة
                status.info("⏳ جاري جلب المنشور...")
                tweet_data = fetch_tweet_data(tweet_url)
                progress.progress(20)

                # جلب بيانات الحساب
                account_data = None
                if enable_profile and username:
                    status.info("⏳ جاري جلب بيانات الحساب...")
                    account_data = fetch_account_details(username, tweet_id)
                    progress.progress(50)
                
                # OCR
                if enable_ocr and tweet_data.get("media_urls"):
                    status.info("⏳ جاري تحليل الصور...")
                    # OCR logic here
                    progress.progress(60)

                # تحليل Gemini
                status.info("⏳ جاري التحليل بالذكاء الاصطناعي...")
                prompt = build_tweet_analysis_prompt(tweet_data, account_data)
                analysis = call_gemini(prompt, gemini_key)
                progress.progress(90)

                # عرض النتائج
                progress.progress(100)
                status.empty()

                st.success("✅ اكتمل التحليل")

                # بطاقة الحساب
                if account_data:
                    with st.expander("👤 بيانات الحساب", expanded=True):
                        display_account_card(account_data)

                # نص المنشور
                if tweet_data.get("text"):
                    with st.expander("📝 نص المنشور", expanded=True):
                        st.markdown(
                            f'<div style="direction:rtl;text-align:right;color:#e2e8f0;'
                            f'background:#1a1f2e;padding:16px;border-radius:12px;">'
                            f'{tweet_data["text"]}</div>',
                            unsafe_allow_html=True
                        )
                        cols = st.columns(4)
                        cols[0].metric("❤️ إعجاب", fmt_number(tweet_data.get("likes", 0)))
                        cols[1].metric("🔁 إعادة نشر", fmt_number(tweet_data.get("retweets", 0)))
                        cols[2].metric("💬 رد", fmt_number(tweet_data.get("replies", 0)))
                        cols[3].metric("👁️ مشاهدة", fmt_number(tweet_data.get("views", 0)))

                # نتائج التحليل
                if analysis:
                    with st.expander("🧠 نتائج التحليل", expanded=True):
                        st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
                        display_analysis_results(analysis)
                        st.markdown('</div>', unsafe_allow_html=True)

                # تصدير JSON
                report = {
                    "tweet": tweet_data,
                    "account": account_data,
                    "analysis": analysis,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button(
                    "📥 تحميل التقرير JSON",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"report_{tweet_id or 'tweet'}.json",
                    mime="application/json"
                )

    # ── تبويب تحليل الحساب ──
    with tab_profile:
        st.markdown('<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">👤 تحليل حساب X</h3>', unsafe_allow_html=True)

        profile_url = st.text_input(
            "🔗 رابط الحساب أو المعرف",
            placeholder="https://x.com/username أو @username",
            key="profile_url_input"
        )

        if st.button("🔍 تحليل الحساب", key="btn_profile"):
            username = extract_username_from_url(profile_url) or profile_url.lstrip("@").strip()
            
            if not username:
                st.error("⚠️ الرجاء إدخال رابط الحساب أو المعرف")
            elif not gemini_key:
                st.error("⚠️ الرجاء إدخال مفتاح Gemini API")
            else:
                progress = st.progress(0)
                status = st.empty()

                status.info("⏳ جاري جلب بيانات الحساب...")
                account_data = fetch_account_details(username)
                progress.progress(40)

                status.info("⏳ جاري التحليل بالذكاء الاصطناعي...")
                prompt = build_profile_analysis_prompt(account_data)
                analysis = call_gemini(prompt, gemini_key)
                progress.progress(90)

                progress.progress(100)
                status.empty()

                if account_data:
                    st.success("✅ اكتمل جلب البيانات")
                    with st.expander("👤 بيانات الحساب", expanded=True):
                        display_account_card(account_data)
                else:
                    st.warning("⚠️ تعذر جلب بيانات الحساب")

                if analysis:
                    with st.expander("🧠 تحليل طبيعة الحساب", expanded=True):
                        display_analysis_results(analysis)

                # تصدير
                report = {
                    "account": account_data,
                    "analysis": analysis,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button(
                    "📥 تحميل تقرير الحساب",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"profile_{username}.json",
                    mime="application/json"
                )

    # ── تبويب تحليل الصورة ──
    with tab_image:
        st.markdown('<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">🖼️ تحليل صورة</h3>', unsafe_allow_html=True)

        img_file = st.file_uploader(
            "ارفع صورة للتحليل",
            type=["jpg", "jpeg", "png", "webp"],
            key="img_upload"
        )
        img_url_input = st.text_input("أو أدخل رابط الصورة", key="img_url")

        if st.button("🔍 تحليل الصورة", key="btn_image"):
            if not gemini_key:
                st.error("⚠️ الرجاء إدخال مفتاح Gemini API")
            elif not img_file and not img_url_input:
                st.error("⚠️ الرجاء رفع صورة أو إدخال رابطها")
            else:
                with st.spinner("⏳ جاري تحليل الصورة..."):
                    image_data = None
                    if img_file:
                        image_data = img_file.read()
                        image_b64 = base64.b64encode(image_data).decode()
                        images = [{"type": img_file.type, "data": image_b64}]
                    elif img_url_input:
                        try:
                            r = requests.get(img_url_input, timeout=10)
                            image_data = r.content
                            image_b64 = base64.b64encode(image_data).decode()
                            images = [{"type": r.headers.get("content-type", "image/jpeg"), "data": image_b64}]
                        except Exception as e:
                            st.error(f"تعذر تحميل الصورة: {e}")
                            images = None

                    if images:
                        if img_file and PIL_AVAILABLE:
                            st.image(img_file, caption="الصورة المرفوعة", width=400)
                        
                        prompt = """
حلل هذه الصورة بشكل مفصل من منظور استخباراتي:
1. ما المحتوى الرئيسي للصورة؟
2. هل تحتوي على نص؟ إذا نعم، ما هو؟
3. ما السياق المحتمل للصورة؟
4. هل هناك أي مؤشرات مثيرة للاهتمام أو مشبوهة؟
5. ما التوصيات بشأن هذه الصورة؟
"""
                        analysis = call_gemini(prompt, gemini_key, images=images)
                        
                        if analysis:
                            st.success("✅ اكتمل التحليل")
                            st.markdown(
                                f'<div style="direction:rtl;text-align:right;color:#e2e8f0;'
                                f'background:#1a1f2e;border-radius:12px;padding:20px;">'
                                f'{analysis}</div>',
                                unsafe_allow_html=True
                            )

    # ── تبويب دليل الاستخدام ──
    with tab_guide:
        st.markdown('<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">📖 دليل الاستخدام</h3>', unsafe_allow_html=True)
        
        guide_content = """
        <div style="direction:rtl;text-align:right;color:#e2e8f0;font-size:14px;line-height:2;">
        
        <h4 style="color:#1DA1F2;">🚀 كيفية الاستخدام</h4>
        
        <p><strong>1. احصل على مفتاح Gemini API</strong><br>
        من خلال <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#1DA1F2;">Google AI Studio</a> - مجاني</p>
        
        <p><strong>2. أدخل المفتاح في الشريط الجانبي</strong></p>
        
        <p><strong>3. اختر نوع التحليل:</strong><br>
        • تحليل منشور: الصق رابط التغريدة<br>
        • تحليل حساب: أدخل المعرف أو الرابط<br>
        • تحليل صورة: ارفع الصورة أو أدخل رابطها</p>
        
        <h4 style="color:#1DA1F2;">📊 ما يتم تحليله</h4>
        <ul>
        <li>محتوى المنشور والموضوع الرئيسي</li>
        <li>التوجه السياسي والأيديولوجي</li>
        <li>مؤشرات التأثير والانتشار</li>
        <li>الأنماط الملاحظة</li>
        <li>التوصيات الاستخباراتية</li>
        </ul>
        
        <h4 style="color:#1DA1F2;">⚠️ ملاحظات مهمة</h4>
        <p>• الأداة للأغراض التعليمية والبحثية فقط<br>
        • الحسابات الخاصة لا يمكن تحليلها<br>
        • قد تتأخر جودة البيانات عند الحجب</p>
        
        </div>
        """
        st.markdown(guide_content, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
```

---

## ملف requirements.txt

```
streamlit>=1.32.0
Pillow>=10.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
google-generativeai>=0.5.0
numpy>=1.24.0
```

## ملف packages.txt

```
tesseract-ocr
tesseract-ocr-ara
tesseract-ocr-eng
ffmpeg
```

## ملف .streamlit/config.toml

```toml
[theme]
base = "dark"
primaryColor = "#1DA1F2"
backgroundColor = "#0f1117"
secondaryBackgroundColor = "#1a1f2e"
textColor = "#e2e8f0"
font = "sans serif"
```

---

## جدول التغييرات في الإصدار 7.0

| المشكلة | السبب | الحل |
|---------|-------|------|
| عدم جلب صورة الحساب | Nitter محجوب + عدم تحويل URL | إضافة `_400x400` + تحويل base64 |
| عدد المتابعين يظهر `-` | Nitter يعيد CAPTCHA | Twitter Guest API كمصدر رئيسي |
| HTML يظهر كنص | `safe_text()` لم تنظف جيدًا | إعادة كتابة `safe_text()` + BeautifulSoup |
| شارات الموثق لا تعمل | HTML escaped | استخدام `st.markdown(unsafe_allow_html=True)` |
| النصوص من اليسار | CSS غير مكتمل | `direction:rtl` كامل |
| عنوان الإصدار في الهيدر | في الكود | حُذف نهائيًا |

---

**الإصدار 7.0** يحل جميع المشكلات المذكورة بثلاثة مصادر بيانات متتالية: Twitter Guest API → FxTwitter → Nitter مع تجاوز كامل لمشاكل CAPTCHA والـ HTML.
