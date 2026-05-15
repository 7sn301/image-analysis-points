# ============================================================
# image_analysis_points.py
# المشهد التنفيذي - تحليل منشورات X بالذكاء الاصطناعي
# الإصدار: 7.0
# ============================================================

import os
import re
import json
import time
import random
import base64
import html
from urllib.parse import quote

import requests
import streamlit as st

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
# الاعدادات العامة
# ============================================================
APP_NAME = "المشهد التنفيذي"
APP_VERSION = "7.0"
APP_EMOJI = "🔍"

GEMINI_MODELS = [
    {"name": "gemini-2.0-flash", "rpm": 15, "rpd": 1500},
    {"name": "gemini-1.5-flash", "rpm": 15, "rpd": 1500},
    {"name": "gemini-1.5-flash-8b", "rpm": 15, "rpd": 1500},
]

TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I6xUzrxb%2F5MoHmP1LLMEBPKdpv%2Fw%3D"

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.catsarch.com",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://twiiit.com",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

REQUEST_DELAY = 1.5
MAX_RETRIES = 3

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
    if not text:
        return ""
    if isinstance(text, (int, float)):
        return str(text)
    text = str(text)
    if BS4_AVAILABLE:
        try:
            text = BeautifulSoup(text, "html.parser").get_text(separator=" ")
        except Exception:
            text = re.sub(r"<[^>]+>", " ", text)
    else:
        text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_len and len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def fmt_number(n):
    if n is None:
        return "-"
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
        return "-"


def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
    }


def is_bot_page(text):
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
        "access denied",
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
    m = TWEET_URL_RE.search(url)
    if m:
        return m.group(1)
    m = PROFILE_URL_RE.search(url)
    if m:
        return m.group(1).lstrip("@")
    return None


def extract_tweet_id(url):
    m = TWEET_URL_RE.search(url)
    if m:
        return m.group(2)
    return None


def image_to_base64(url):
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
                            content.append({
                                "mime_type": img.get("type", "image/jpeg"),
                                "data": img["data"]
                            })
                result = m.generate_content(content)
                return result.text
            except Exception as e:
                err = str(e).lower()
                if "quota" in err or "rate" in err:
                    time.sleep(2 ** attempt * 3)
                    continue
                elif attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
    return None


# ============================================================
# جلب بيانات الحساب - Twitter Guest API
# ============================================================

def get_guest_token():
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

        variables = {
            "screen_name": username,
            "withSafetyModeUserFields": True,
        }
        features = {
            "hidden_profile_likes_enabled": True,
            "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "highlights_tweets_tab_ui_enabled": True,
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
        user_result = (
            data.get("data", {})
            .get("user", {})
            .get("result", {})
        )
        user_data = user_result.get("legacy", {})

        if not user_data:
            return None

        avatar_url = user_data.get("profile_image_url_https", "")
        if avatar_url:
            avatar_url = avatar_url.replace("_normal", "_400x400")

        join_date_raw = user_data.get("created_at", "")
        join_date_formatted = "غير محدد"
        if join_date_raw:
            try:
                from datetime import datetime
                dt = datetime.strptime(join_date_raw, "%a %b %d %H:%M:%S +0000 %Y")
                join_date_formatted = dt.strftime("%d/%m/%Y")
            except Exception:
                join_date_formatted = join_date_raw

        return {
            "username": username,
            "display_name": safe_text(user_data.get("name", username)),
            "bio": safe_text(user_data.get("description", ""), 300),
            "followers": user_data.get("followers_count", 0),
            "following": user_data.get("friends_count", 0),
            "tweets_count": user_data.get("statuses_count", 0),
            "location": safe_text(user_data.get("location", "")),
            "join_date_formatted": join_date_formatted,
            "verified": user_data.get("verified", False),
            "is_blue_verified": user_result.get("is_blue_verified", False),
            "protected": user_data.get("protected", False),
            "avatar_url": avatar_url,
            "banner_url": user_data.get("profile_banner_url", ""),
            "source": "twitter_guest_api",
        }

    except Exception:
        return None


# ============================================================
# جلب بيانات الحساب - FxTwitter
# ============================================================

def fetch_via_fxtwitter(username, tweet_id):
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

        return {
            "username": author.get("screen_name", username),
            "display_name": safe_text(author.get("name", username)),
            "bio": safe_text(author.get("description", ""), 300),
            "followers": author.get("followers", 0),
            "following": author.get("following", 0),
            "tweets_count": author.get("statuses", 0),
            "location": safe_text(author.get("location", "")),
            "join_date_formatted": author.get("joined", "غير محدد"),
            "verified": author.get("verified", False),
            "is_blue_verified": author.get("is_blue_verified", False),
            "protected": False,
            "avatar_url": avatar_url,
            "banner_url": author.get("banner_url", ""),
            "source": "fxtwitter",
        }
    except Exception:
        return None


# ============================================================
# جلب بيانات الحساب - Nitter
# ============================================================

def fetch_via_nitter(username):
    if not BS4_AVAILABLE:
        return None

    for mirror in NITTER_MIRRORS:
        try:
            url = f"{mirror}/{username}"
            headers = get_random_headers()
            r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            if r.status_code not in [200, 301, 302]:
                continue
            if is_bot_page(r.text):
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            result = {"username": username, "source": f"nitter"}

            name_el = soup.select_one(".profile-card-fullname, .fullname")
            result["display_name"] = safe_text(name_el.get_text()) if name_el else username

            bio_el = soup.select_one(".profile-bio, .bio")
            result["bio"] = safe_text(bio_el.get_text()) if bio_el else ""

            loc_el = soup.select_one(".profile-location")
            result["location"] = safe_text(loc_el.get_text()) if loc_el else ""

            join_el = soup.select_one(".profile-joindate")
            result["join_date_formatted"] = safe_text(join_el.get_text()) if join_el else "غير محدد"

            followers = 0
            following = 0
            tweets_count = 0
            for item in soup.select(".profile-stat"):
                header = item.get_text(strip=True).lower()
                num_el = item.select_one(".profile-stat-num")
                if num_el:
                    try:
                        val = int(num_el.get_text(strip=True).replace(",", ""))
                    except ValueError:
                        val = 0
                    if "tweet" in header or "post" in header:
                        tweets_count = val
                    elif "follower" in header:
                        followers = val
                    elif "following" in header:
                        following = val

            result["followers"] = followers
            result["following"] = following
            result["tweets_count"] = tweets_count

            avatar_el = soup.select_one(".profile-card-avatar img, .avatar img")
            if avatar_el:
                avatar_src = avatar_el.get("src", "")
                if avatar_src.startswith("/"):
                    avatar_src = mirror + avatar_src
                result["avatar_url"] = avatar_src
            else:
                result["avatar_url"] = ""

            verified_el = soup.select_one(".verified-icon, .icon-verified")
            result["verified"] = bool(verified_el)
            result["is_blue_verified"] = result["verified"]
            result["protected"] = bool(soup.select_one(".lock-icon, .protected"))

            if result.get("display_name", username) != username or followers > 0:
                return result

        except Exception:
            continue

    return None


# ============================================================
# الدالة الرئيسية لجلب بيانات الحساب
# ============================================================

def fetch_account_details(username, tweet_id=None):
    username = username.lstrip("@").strip()

    result = fetch_via_twitter_guest_api(username)
    if result and (result.get("followers", 0) > 0 or result.get("display_name", username) != username):
        return result

    if tweet_id:
        result = fetch_via_fxtwitter(username, tweet_id)
        if result and result.get("followers", 0) > 0:
            return result

    result = fetch_via_nitter(username)
    if result:
        return result

    return {
        "username": username,
        "display_name": username,
        "bio": "",
        "followers": None,
        "following": None,
        "tweets_count": None,
        "location": "",
        "join_date_formatted": "غير محدد",
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
    username = extract_username_from_url(url)
    tweet_id = extract_tweet_id(url)
    tweet_data = {"url": url, "username": username, "tweet_id": tweet_id}
    media_urls = []

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
                    media = tweet.get("media", {})
                    if media:
                        for img in media.get("photos", []):
                            media_urls.append(img.get("url", ""))
                        for vid in media.get("videos", []):
                            media_urls.append(vid.get("thumbnail_url", ""))
        except Exception:
            pass

    tweet_data["media_urls"] = [u for u in media_urls if u]
    return tweet_data


# ============================================================
# بناء Prompt للتحليل
# ============================================================

def build_tweet_prompt(tweet_data, account_data=None):
    username = tweet_data.get("username", "غير معروف")
    text = tweet_data.get("text", "")

    lines = [
        "انت محلل استخباراتي متخصص في تحليل منشورات منصة X.",
        "",
        "معلومات المنشور:",
        f"- الحساب: @{username}",
        f"- النص: {text or 'غير متاح'}",
        f"- الاعجابات: {tweet_data.get('likes', 0)}",
        f"- اعادة النشر: {tweet_data.get('retweets', 0)}",
        f"- الردود: {tweet_data.get('replies', 0)}",
        f"- المشاهدات: {tweet_data.get('views', 0)}",
    ]

    if account_data:
        lines += [
            "",
            "معلومات الحساب:",
            f"- المتابعون: {fmt_number(account_data.get('followers'))}",
            f"- يتابع: {fmt_number(account_data.get('following'))}",
            f"- المنشورات: {fmt_number(account_data.get('tweets_count'))}",
        ]

    lines += [
        "",
        "التحليل المطلوب بالعربية بصيغة JSON:",
        '```json',
        '{',
        '  "ملخص_المحتوى": "ملخص موجز",',
        '  "الموضوع_الرئيسي": "الموضوع",',
        '  "التوجه": "التوجه ان وجد",',
        '  "مؤشرات_التأثير": {',
        '    "مستوى_التفاعل": "مرتفع/متوسط/منخفض",',
        '    "درجة_الخطورة": "1-10"',
        '  },',
        '  "الانماط_الملاحظة": ["نمط1", "نمط2"],',
        '  "التوصيات": ["توصية1", "توصية2"],',
        '  "التقييم_العام": "تقييم شامل"',
        '}',
        '```',
    ]

    return "\n".join(lines)


def build_profile_prompt(account_data):
    lines = [
        "انت محلل استخباراتي متخصص في تحليل حسابات منصة X.",
        "",
        "بيانات الحساب:",
        f"- المعرف: @{account_data.get('username', 'غير معروف')}",
        f"- الاسم: {account_data.get('display_name', 'غير محدد')}",
        f"- البايو: {account_data.get('bio', 'لا يوجد')}",
        f"- الموقع: {account_data.get('location', 'غير محدد')}",
        f"- المتابعون: {fmt_number(account_data.get('followers'))}",
        f"- يتابع: {fmt_number(account_data.get('following'))}",
        f"- المنشورات: {fmt_number(account_data.get('tweets_count'))}",
        f"- تاريخ الانضمام: {account_data.get('join_date_formatted', 'غير محدد')}",
        f"- موثق: {'نعم' if account_data.get('verified') or account_data.get('is_blue_verified') else 'لا'}",
        "",
        "التحليل المطلوب بالعربية بصيغة JSON:",
        '```json',
        '{',
        '  "طبيعة_الحساب": "شخصي/مؤسسي/اعلامي/ترفيهي",',
        '  "التوجه_العام": "وصف التوجه",',
        '  "مستوى_التأثير": "مرتفع/متوسط/منخفض",',
        '  "المواضيع_الرئيسية": ["موضوع1", "موضوع2"],',
        '  "مؤشرات_المصداقية": {',
        '    "تقييم_النشاط": "نشط/متوسط/خامل",',
        '    "مؤشر_الأصالة": "1-10"',
        '  },',
        '  "الانماط_الملاحظة": ["نمط1"],',
        '  "التوصيات": ["توصية1"],',
        '  "التقييم_الشامل": "تقييم نهائي"',
        '}',
        '```',
    ]
    return "\n".join(lines)


# ============================================================
# CSS
# ============================================================

def inject_css():
    st.markdown("""
<style>
html, body, [class*="css"] {
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif !important;
}
.stApp { background: #0f1117 !important; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebar"] {
    width: 360px !important;
    background: #1a1f2e !important;
}
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
    if not account:
        st.warning("لم يتم جلب بيانات الحساب")
        return

    col1, col2 = st.columns([1, 4])

    with col1:
        avatar_url = account.get("avatar_url", "")
        if avatar_url:
            img_data = image_to_base64(avatar_url)
            if img_data:
                st.markdown(
                    f'<img src="{img_data}" style="width:80px;height:80px;'
                    f'border-radius:50%;border:3px solid #1DA1F2;object-fit:cover;">',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<div style="width:80px;height:80px;border-radius:50%;'
                    'background:#1e2537;border:3px solid #1DA1F2;display:flex;'
                    'align-items:center;justify-content:center;font-size:32px;">👤</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                '<div style="width:80px;height:80px;border-radius:50%;'
                'background:#1e2537;border:3px solid #1DA1F2;display:flex;'
                'align-items:center;justify-content:center;font-size:32px;">👤</div>',
                unsafe_allow_html=True
            )

    with col2:
        display_name = account.get("display_name", account.get("username", "غير معروف"))
        username = account.get("username", "غير معروف")

        st.markdown(
            f'<p style="font-size:22px;font-weight:700;color:#fff;margin:0;direction:rtl;">'
            f'{display_name}</p>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<p style="font-size:14px;color:#8899a6;margin:0;direction:ltr;">@{username}</p>',
            unsafe_allow_html=True
        )

        if account.get("protected"):
            st.markdown(
                '<span style="background:#4b5563;color:#fbbf24;padding:3px 10px;'
                'border-radius:20px;font-size:12px;">🔒 حساب خاص</span>',
                unsafe_allow_html=True
            )
        elif account.get("verified") or account.get("is_blue_verified"):
            st.markdown(
                '<span style="background:linear-gradient(135deg,#1DA1F2,#0d7bc4);'
                'color:white;padding:3px 10px;border-radius:20px;font-size:12px;">✅ موثق</span>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<span style="background:#374151;color:#9ca3af;padding:3px 10px;'
                'border-radius:20px;font-size:12px;">⬜ غير موثق</span>',
                unsafe_allow_html=True
            )

    st.markdown("---")

    bio = account.get("bio", "")
    if bio:
        st.markdown(
            f'<p style="color:#e2e8f0;font-size:14px;direction:rtl;text-align:right;'
            f'padding:8px 0;">{bio}</p>',
            unsafe_allow_html=True
        )

    col_f, col_fw, col_t = st.columns(3)

    with col_f:
        st.markdown(
            '<div style="background:#1e2537;border:1px solid #2d3748;border-radius:12px;'
            'padding:14px;text-align:center;">'
            f'<span style="font-size:24px;font-weight:700;color:#1DA1F2;display:block;">'
            f'{fmt_number(account.get("followers"))}</span>'
            '<span style="font-size:13px;color:#8899a6;">متابع</span>'
            '</div>',
            unsafe_allow_html=True
        )

    with col_fw:
        st.markdown(
            '<div style="background:#1e2537;border:1px solid #2d3748;border-radius:12px;'
            'padding:14px;text-align:center;">'
            f'<span style="font-size:24px;font-weight:700;color:#1DA1F2;display:block;">'
            f'{fmt_number(account.get("following"))}</span>'
            '<span style="font-size:13px;color:#8899a6;">يتابع</span>'
            '</div>',
            unsafe_allow_html=True
        )

    with col_t:
        st.markdown(
            '<div style="background:#1e2537;border:1px solid #2d3748;border-radius:12px;'
            'padding:14px;text-align:center;">'
            f'<span style="font-size:24px;font-weight:700;color:#1DA1F2;display:block;">'
            f'{fmt_number(account.get("tweets_count"))}</span>'
            '<span style="font-size:13px;color:#8899a6;">منشور</span>'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    location = account.get("location", "")
    join_date = account.get("join_date_formatted", "غير محدد")

    if location:
        st.markdown(
            f'<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #1e2537;'
            f'direction:rtl;">'
            f'<span style="font-size:18px;">📍</span>'
            f'<span style="font-size:13px;color:#8899a6;width:120px;">الموقع</span>'
            f'<span style="font-size:14px;color:#e2e8f0;">{location}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    if join_date and join_date != "غير محدد":
        st.markdown(
            f'<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #1e2537;'
            f'direction:rtl;">'
            f'<span style="font-size:18px;">📅</span>'
            f'<span style="font-size:13px;color:#8899a6;width:120px;">تاريخ الانضمام</span>'
            f'<span style="font-size:14px;color:#e2e8f0;">{join_date}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    source = account.get("source", "")
    if source:
        source_map = {
            "twitter_guest_api": "Twitter API",
            "fxtwitter": "FxTwitter",
            "unavailable": "غير متاح",
        }
        source_display = source_map.get(source, source)
        st.markdown(
            f'<p style="font-size:11px;color:#4b5563;text-align:left;margin-top:8px;">'
            f'المصدر: {source_display}</p>',
            unsafe_allow_html=True
        )


# ============================================================
# عرض نتائج التحليل
# ============================================================

def display_analysis_results(analysis_text):
    if not analysis_text:
        st.info("لم يتم الحصول على نتائج تحليل")
        return

    json_match = re.search(r"```json\s*([\s\S]+?)\s*```", analysis_text)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            for key, value in data.items():
                title = key.replace("_", " ")
                if isinstance(value, dict):
                    st.markdown(
                        f'<p style="font-size:16px;font-weight:600;color:#1DA1F2;'
                        f'direction:rtl;text-align:right;">📊 {title}</p>',
                        unsafe_allow_html=True
                    )
                    for k, v in value.items():
                        st.markdown(
                            f'<div style="display:flex;gap:10px;padding:6px 0;'
                            f'border-bottom:1px solid #1e2537;direction:rtl;">'
                            f'<span style="color:#8899a6;width:150px;">{k.replace("_"," ")}</span>'
                            f'<span style="color:#e2e8f0;">{v}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                elif isinstance(value, list):
                    st.markdown(
                        f'<p style="font-size:16px;font-weight:600;color:#1DA1F2;'
                        f'direction:rtl;text-align:right;">📋 {title}</p>',
                        unsafe_allow_html=True
                    )
                    for item in value:
                        if "انماط" in title or "pattern" in title.lower():
                            st.markdown(
                                f'<span style="background:#1e3a5f;color:#60a5fa;'
                                f'padding:4px 12px;border-radius:20px;font-size:13px;'
                                f'display:inline-block;margin:3px;">🔹 {item}</span>',
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                f'<div style="background:#1a2e1a;border-right:3px solid #22c55e;'
                                f'padding:8px 12px;border-radius:0 8px 8px 0;margin:6px 0;'
                                f'color:#86efac;font-size:14px;direction:rtl;text-align:right;">'
                                f'✅ {item}</div>',
                                unsafe_allow_html=True
                            )
                    st.markdown("<br>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<p style="font-size:16px;font-weight:600;color:#1DA1F2;'
                        f'direction:rtl;text-align:right;">📌 {title}</p>',
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f'<p style="color:#e2e8f0;font-size:14px;direction:rtl;'
                        f'text-align:right;padding:8px 12px;background:#1e2537;'
                        f'border-radius:8px;">{value}</p>',
                        unsafe_allow_html=True
                    )
            return
        except json.JSONDecodeError:
            pass

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

    with st.sidebar:
        st.markdown(
            f'<h2 style="color:#1DA1F2;direction:rtl;text-align:right;font-size:20px;">'
            f'{APP_EMOJI} {APP_NAME}</h2>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p style="color:#8899a6;font-size:13px;direction:rtl;text-align:right;">'
            'اداة تحليل منشورات X بالذكاء الاصطناعي</p>',
            unsafe_allow_html=True
        )
        st.markdown("---")

        gemini_key = st.text_input(
            "مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
        )

        st.markdown("---")
        enable_profile = st.checkbox("تحليل الملف الشخصي", value=True)
        enable_ocr = st.checkbox("تفعيل OCR للصور", value=False)

        st.markdown("---")
        st.markdown(
            '<p style="color:#8899a6;font-size:12px;direction:rtl;text-align:right;">'
            'حدود الاستخدام اليومي:</p>',
            unsafe_allow_html=True
        )
        for model in GEMINI_MODELS:
            st.markdown(
                f'<p style="font-size:11px;color:#4b5563;direction:ltr;text-align:left;">'
                f'{model["name"]}: {model["rpd"]} req/day</p>',
                unsafe_allow_html=True
            )

    tab_tweet, tab_profile, tab_image, tab_guide = st.tabs([
        "تحليل منشور",
        "تحليل حساب",
        "تحليل صورة",
        "دليل الاستخدام",
    ])

    # تحليل المنشور
    with tab_tweet:
        st.markdown(
            '<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">تحليل منشور X</h3>',
            unsafe_allow_html=True
        )

        tweet_url = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            key="tweet_url_input"
        )

        if st.button("تحليل المنشور", key="btn_tweet"):
            if not tweet_url:
                st.error("الرجاء ادخال رابط المنشور")
            elif not is_tweet_url(tweet_url):
                st.error("الرابط غير صالح")
            elif not gemini_key:
                st.error("الرجاء ادخال مفتاح Gemini API")
            else:
                username = extract_username_from_url(tweet_url)
                tweet_id = extract_tweet_id(tweet_url)
                progress = st.progress(0)
                status = st.empty()

                status.info("جاري جلب المنشور...")
                tweet_data = fetch_tweet_data(tweet_url)
                progress.progress(20)

                account_data = None
                if enable_profile and username:
                    status.info("جاري جلب بيانات الحساب...")
                    account_data = fetch_account_details(username, tweet_id)
                    progress.progress(50)

                status.info("جاري التحليل بالذكاء الاصطناعي...")
                prompt = build_tweet_prompt(tweet_data, account_data)
                analysis = call_gemini(prompt, gemini_key)
                progress.progress(90)

                progress.progress(100)
                status.empty()
                st.success("اكتمل التحليل")

                if account_data:
                    with st.expander("بيانات الحساب", expanded=True):
                        display_account_card(account_data)

                if tweet_data.get("text"):
                    with st.expander("نص المنشور", expanded=True):
                        st.markdown(
                            f'<div style="direction:rtl;text-align:right;color:#e2e8f0;'
                            f'background:#1a1f2e;padding:16px;border-radius:12px;">'
                            f'{tweet_data["text"]}</div>',
                            unsafe_allow_html=True
                        )
                        cols = st.columns(4)
                        cols[0].metric("اعجاب", fmt_number(tweet_data.get("likes", 0)))
                        cols[1].metric("اعادة نشر", fmt_number(tweet_data.get("retweets", 0)))
                        cols[2].metric("رد", fmt_number(tweet_data.get("replies", 0)))
                        cols[3].metric("مشاهدة", fmt_number(tweet_data.get("views", 0)))

                if analysis:
                    with st.expander("نتائج التحليل", expanded=True):
                        display_analysis_results(analysis)

                report = {
                    "tweet": tweet_data,
                    "account": account_data,
                    "analysis": analysis,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button(
                    "تحميل التقرير JSON",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"report_{tweet_id or 'tweet'}.json",
                    mime="application/json"
                )

    # تحليل الحساب
    with tab_profile:
        st.markdown(
            '<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">تحليل حساب X</h3>',
            unsafe_allow_html=True
        )

        profile_input = st.text_input(
            "رابط الحساب او المعرف",
            placeholder="https://x.com/username او @username",
            key="profile_url_input"
        )

        if st.button("تحليل الحساب", key="btn_profile"):
            username = extract_username_from_url(profile_input) or profile_input.lstrip("@").strip()

            if not username:
                st.error("الرجاء ادخال رابط الحساب او المعرف")
            elif not gemini_key:
                st.error("الرجاء ادخال مفتاح Gemini API")
            else:
                progress = st.progress(0)
                status = st.empty()

                status.info("جاري جلب بيانات الحساب...")
                account_data = fetch_account_details(username)
                progress.progress(40)

                status.info("جاري التحليل بالذكاء الاصطناعي...")
                prompt = build_profile_prompt(account_data)
                analysis = call_gemini(prompt, gemini_key)
                progress.progress(90)

                progress.progress(100)
                status.empty()

                if account_data:
                    st.success("اكتمل جلب البيانات")
                    with st.expander("بيانات الحساب", expanded=True):
                        display_account_card(account_data)
                else:
                    st.warning("تعذر جلب بيانات الحساب")

                if analysis:
                    with st.expander("تحليل طبيعة الحساب", expanded=True):
                        display_analysis_results(analysis)

                report = {
                    "account": account_data,
                    "analysis": analysis,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                st.download_button(
                    "تحميل تقرير الحساب",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name=f"profile_{username}.json",
                    mime="application/json"
                )

    # تحليل الصورة
    with tab_image:
        st.markdown(
            '<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">تحليل صورة</h3>',
            unsafe_allow_html=True
        )

        img_file = st.file_uploader(
            "ارفع صورة للتحليل",
            type=["jpg", "jpeg", "png", "webp"],
            key="img_upload"
        )
        img_url_input = st.text_input("او ادخل رابط الصورة", key="img_url")

        if st.button("تحليل الصورة", key="btn_image"):
            if not gemini_key:
                st.error("الرجاء ادخال مفتاح Gemini API")
            elif not img_file and not img_url_input:
                st.error("الرجاء رفع صورة او ادخال رابطها")
            else:
                with st.spinner("جاري تحليل الصورة..."):
                    images = None
                    if img_file:
                        image_data = img_file.read()
                        image_b64 = base64.b64encode(image_data).decode()
                        images = [{"type": img_file.type, "data": image_b64}]
                    elif img_url_input:
                        try:
                            r = requests.get(img_url_input, timeout=10)
                            image_b64 = base64.b64encode(r.content).decode()
                            ct = r.headers.get("content-type", "image/jpeg")
                            images = [{"type": ct, "data": image_b64}]
                        except Exception as e:
                            st.error(f"تعذر تحميل الصورة: {e}")

                    if images:
                        if img_file and PIL_AVAILABLE:
                            st.image(img_file, caption="الصورة المرفوعة", width=400)

                        prompt_lines = [
                            "حلل هذه الصورة بشكل مفصل:",
                            "1. ما المحتوى الرئيسي للصورة؟",
                            "2. هل تحتوي على نص؟ اذكره.",
                            "3. ما السياق المحتمل للصورة؟",
                            "4. هل هناك مؤشرات مثيرة للاهتمام؟",
                            "5. ما التوصيات؟",
                        ]
                        analysis = call_gemini("\n".join(prompt_lines), gemini_key, images=images)

                        if analysis:
                            st.success("اكتمل التحليل")
                            st.markdown(
                                f'<div style="direction:rtl;text-align:right;color:#e2e8f0;'
                                f'background:#1a1f2e;border-radius:12px;padding:20px;">'
                                f'{analysis}</div>',
                                unsafe_allow_html=True
                            )

    # دليل الاستخدام
    with tab_guide:
        st.markdown(
            '<h3 style="color:#1DA1F2;direction:rtl;text-align:right;">دليل الاستخدام</h3>',
            unsafe_allow_html=True
        )
        st.markdown("""
<div style="direction:rtl;text-align:right;color:#e2e8f0;font-size:14px;line-height:2;">

<h4 style="color:#1DA1F2;">كيفية الاستخدام</h4>

<p>1. احصل على مفتاح Gemini API من Google AI Studio (مجاني)</p>
<p>2. ادخل المفتاح في الشريط الجانبي</p>
<p>3. اختر نوع التحليل:</p>
<ul>
<li>تحليل منشور: الصق رابط التغريدة</li>
<li>تحليل حساب: ادخل المعرف او الرابط</li>
<li>تحليل صورة: ارفع الصورة او ادخل رابطها</li>
</ul>

<h4 style="color:#1DA1F2;">ما يتم تحليله</h4>
<ul>
<li>محتوى المنشور والموضوع الرئيسي</li>
<li>التوجه السياسي والايديولوجي</li>
<li>مؤشرات التأثير والانتشار</li>
<li>الانماط الملاحظة</li>
<li>التوصيات الاستخباراتية</li>
</ul>

<h4 style="color:#1DA1F2;">ملاحظات مهمة</h4>
<p>الاداة للاغراض التعليمية والبحثية فقط</p>
<p>الحسابات الخاصة لا يمكن تحليلها</p>

</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
```
