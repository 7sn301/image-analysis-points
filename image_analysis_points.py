# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.5
# الجديد: بطاقة مكبّرة + سحب معرّف الحساب (User ID)

import streamlit as st

st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

import requests
import re
import json
import random
import base64
import html as html_module
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    * { font-family: 'Cairo', sans-serif !important; }
    .main { background: #0f1117; color: #e0e0e0; }

    .profile-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border: 1px solid #30363d;
        border-radius: 20px;
        padding: 36px;
        margin: 20px 0;
        box-shadow: 0 12px 40px rgba(0,0,0,0.5);
    }
    .profile-header {
        display: flex;
        align-items: center;
        gap: 24px;
        margin-bottom: 24px;
    }
    .profile-avatar {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 4px solid #1d9bf0;
        object-fit: cover;
        box-shadow: 0 0 20px rgba(29,155,240,0.4);
    }
    .profile-name {
        font-size: 1.9em;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 4px;
    }
    .profile-username {
        color: #8b949e;
        font-size: 1.1em;
        margin-bottom: 6px;
    }
    .verified-badge {
        color: #1d9bf0;
        font-size: 1.2em;
    }
    .user-id-badge {
        display: inline-block;
        background: rgba(29,155,240,0.15);
        border: 1px solid #1d9bf0;
        color: #1d9bf0;
        border-radius: 8px;
        padding: 3px 10px;
        font-size: 0.85em;
        font-family: monospace !important;
        margin-top: 4px;
        letter-spacing: 0.5px;
    }
    .stats-row {
        display: flex;
        gap: 20px;
        margin: 20px 0;
        flex-wrap: wrap;
    }
    .stat-item {
        text-align: center;
        background: rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 16px 28px;
        min-width: 130px;
        border: 1px solid rgba(255,255,255,0.05);
    }
    .stat-value {
        font-size: 1.7em;
        font-weight: 700;
        color: #1d9bf0;
    }
    .stat-label {
        font-size: 0.9em;
        color: #8b949e;
        margin-top: 6px;
    }
    .bio-section {
        background: rgba(255,255,255,0.04);
        border-radius: 10px;
        padding: 14px 18px;
        margin: 14px 0;
        border-left: 4px solid #1d9bf0;
        color: #c9d1d9;
        line-height: 1.8;
        font-size: 1.05em;
    }
    .meta-row {
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
        margin-top: 14px;
    }
    .meta-item {
        color: #8b949e;
        font-size: 1.0em;
    }
    .source-badge {
        display: inline-block;
        background: #1d9bf0;
        color: white;
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .analysis-box {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 24px;
        margin: 16px 0;
        white-space: pre-wrap;
        line-height: 1.8;
        color: #c9d1d9;
        font-size: 1.02em;
    }
    .stButton > button {
        background: linear-gradient(135deg, #1d9bf0, #0d47a1) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 24px !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 16px rgba(29,155,240,0.4) !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── ثوابت ───────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

NITTER_MIRRORS = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.cz",
    "https://nitter.unixfox.eu",
]

FXTWITTER_API = "https://api.fxtwitter.com"

USERNAME_PATTERNS = [
    r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)(?:[/?#].*)?$",
    r"^@?([A-Za-z0-9_]{1,50})$",
]

TWEET_URL_PATTERNS = [
    r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+/status/(\d+)",
    r"(?:https?://)?(?:www\.)?fxtwitter\.com/[A-Za-z0-9_]+/status/(\d+)",
]

IMAGE_ANALYSIS_POINTS = [
    "هوية المرسل/المصدر البصري",
    "المحتوى النصي في الصورة",
    "التواريخ والأوقات المرئية",
    "الأشخاص والوجوه",
    "الموقع الجغرافي المرئي",
    "الأجهزة والتقنيات الظاهرة",
    "الشعارات والعلامات التجارية",
    "الوثائق والأوراق الرسمية",
    "المنشآت والمباني",
    "وسائل النقل",
    "الأسلحة والمعدات",
    "العملات والأموال",
    "الخرائط والمناطق",
    "التجمعات البشرية",
    "الأنشطة والأفعال",
]

# ─── دوال مساعدة ─────────────────────────────────────────────────────────────
def clean_text(txt):
    # type: (Any) -> str
    if not txt:
        return ""
    txt = str(txt)
    txt = re.sub(r'<[^>]+>', '', txt)
    txt = html_module.unescape(txt)
    txt = txt.replace("&", "&amp;")
    txt = txt.replace("<", "&lt;")
    txt = txt.replace(">", "&gt;")
    return txt.strip()


def extract_username(text):
    # type: (str) -> Optional[str]
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'\?.*$', '', text)
    text = re.sub(r'#.*$', '', text)
    for pattern in USERNAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            username = match.group(1)
            reserved = {'home', 'explore', 'notifications', 'messages', 'settings',
                        'search', 'login', 'logout', 'signup', 'i', 'hashtag'}
            if username.lower() not in reserved:
                return username
    return None


def extract_tweet_id(text):
    # type: (str) -> Optional[str]
    if not text:
        return None
    for pattern in TWEET_URL_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def format_number(n):
    # type: (Any) -> str
    try:
        n = int(n)
        if n >= 1_000_000:
            return "{:.1f}M".format(n / 1_000_000)
        elif n >= 1_000:
            return "{:.1f}K".format(n / 1_000)
        return str(n)
    except (ValueError, TypeError):
        return str(n) if n else "0"


def format_date(date_str):
    # type: (str) -> str
    if not date_str:
        return "غير متوفر"
    try:
        dt = datetime.strptime(str(date_str), "%a %b %d %H:%M:%S +0000 %Y")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(date_str)[:10] if len(str(date_str)) >= 10 else str(date_str)


def image_to_base64(url):
    # type: (str) -> Optional[str]
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content))
            img = img.convert("RGB")
            img.thumbnail((300, 300))
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        pass
    return None


# ─── جلب البيانات ────────────────────────────────────────────────────────────
def get_guest_token():
    # type: () -> Optional[str]
    try:
        headers = {
            "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "User-Agent": random.choice(USER_AGENTS),
        }
        resp = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers=headers, timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("guest_token")
    except Exception:
        pass
    return None


def fetch_via_guest_api(username):
    # type: (str) -> Optional[Dict[str, Any]]
    try:
        guest_token = get_guest_token()
        if not guest_token:
            return None
        headers = {
            "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-guest-token": guest_token,
            "User-Agent": random.choice(USER_AGENTS),
            "Content-Type": "application/json",
        }
        params = {
            "variables": json.dumps({
                "screen_name": username,
                "withSafetyModeUserFields": True
            }),
            "features": json.dumps({
                "hidden_profile_likes_enabled": False,
                "hidden_profile_subscriptions_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "subscriptions_verification_info_is_identity_verified_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "highlights_tweets_tab_ui_enabled": True,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
            })
        }
        url = "https://twitter.com/i/api/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            result_obj = (data.get("data", {})
                              .get("user", {})
                              .get("result", {}))
            # ✅ استخراج User ID من rest_id
            user_id = result_obj.get("rest_id", "")
            user = result_obj.get("legacy", {})
            if user and user.get("screen_name"):
                return {
                    "name": user.get("name", ""),
                    "username": user.get("screen_name", username),
                    "user_id": user_id or user.get("id_str", ""),
                    "bio": user.get("description", ""),
                    "followers": user.get("followers_count", 0),
                    "following": user.get("friends_count", 0),
                    "posts": user.get("statuses_count", 0),
                    "location": user.get("location", ""),
                    "join_date": format_date(user.get("created_at", "")),
                    "verified": user.get("verified", False) or user.get("is_blue_verified", False),
                    "profile_image": user.get("profile_image_url_https", "").replace("_normal", "_400x400"),
                    "banner": user.get("profile_banner_url", ""),
                    "source": "Twitter API",
                }
    except Exception:
        pass
    return None


def fetch_via_fxtwitter(username):
    # type: (str) -> Optional[Dict[str, Any]]
    try:
        url = FXTWITTER_API + "/" + username
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            user = data.get("user", {})
            if user:
                return {
                    "name": user.get("name", ""),
                    "username": user.get("screen_name", username),
                    "user_id": str(user.get("id", "")),  # ✅ User ID من FxTwitter
                    "bio": user.get("description", ""),
                    "followers": user.get("followers", 0),
                    "following": user.get("following", 0),
                    "posts": user.get("tweets", 0),
                    "location": user.get("location", ""),
                    "join_date": format_date(user.get("joined", "")),
                    "verified": user.get("verified", False),
                    "profile_image": user.get("avatar_url", ""),
                    "banner": user.get("banner_url", ""),
                    "source": "FxTwitter",
                }
    except Exception:
        pass
    return None


def fetch_via_nitter(username):
    # type: (str) -> Optional[Dict[str, Any]]
    for mirror in NITTER_MIRRORS:
        try:
            url = mirror + "/" + username
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                name_el = soup.select_one(".profile-card-fullname")
                name = name_el.get_text(strip=True) if name_el else ""
                bio_el = soup.select_one(".profile-bio")
                bio = bio_el.get_text(strip=True) if bio_el else ""
                loc_el = soup.select_one(".profile-location")
                location = loc_el.get_text(strip=True) if loc_el else ""
                joined_el = soup.select_one(".profile-joindate")
                join_date = joined_el.get_text(strip=True) if joined_el else "غير متوفر"
                stats = soup.select(".profile-stat-num")
                followers = int(stats[0].get_text(strip=True).replace(",", "")) if len(stats) > 0 else 0
                following = int(stats[1].get_text(strip=True).replace(",", "")) if len(stats) > 1 else 0
                posts = int(stats[2].get_text(strip=True).replace(",", "")) if len(stats) > 2 else 0
                img_el = soup.select_one(".profile-card-avatar img")
                profile_image = ""
                if img_el:
                    src = img_el.get("src", "")
                    profile_image = mirror + src if src.startswith("/") else src

                # ✅ محاولة استخراج User ID من Nitter
                user_id = ""
                try:
                    rss_url = mirror + "/" + username + "/rss"
                    rss_resp = requests.get(rss_url, headers=headers, timeout=8)
                    id_match = re.search(r'twitter\.com/intent/user\?user_id=(\d+)', rss_resp.text)
                    if id_match:
                        user_id = id_match.group(1)
                except Exception:
                    pass

                if name or bio:
                    return {
                        "name": name,
                        "username": username,
                        "user_id": user_id,
                        "bio": bio,
                        "followers": followers,
                        "following": following,
                        "posts": posts,
                        "location": location,
                        "join_date": join_date,
                        "verified": False,
                        "profile_image": profile_image,
                        "banner": "",
                        "source": "Nitter (" + mirror.split("//")[1] + ")",
                    }
        except Exception:
            continue
    return None


def fetch_user_data(username):
    # type: (str) -> Tuple[Optional[Dict[str, Any]], str]
    data = fetch_via_guest_api(username)
    if data:
        return data, "guest_api"
    data = fetch_via_fxtwitter(username)
    if data:
        return data, "fxtwitter"
    data = fetch_via_nitter(username)
    if data:
        return data, "nitter"
    return None, "failed"


def fetch_tweet_data(tweet_id):
    # type: (str) -> Optional[Dict[str, Any]]
    try:
        url = "https://api.fxtwitter.com/status/" + tweet_id
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            tweet = data.get("tweet", {})
            if tweet:
                return {
                    "id": tweet_id,
                    "text": tweet.get("text", ""),
                    "author": tweet.get("author", {}).get("screen_name", ""),
                    "author_name": tweet.get("author", {}).get("name", ""),
                    "author_id": str(tweet.get("author", {}).get("id", "")),
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "replies": tweet.get("replies", 0),
                    "views": tweet.get("views", 0),
                    "created_at": tweet.get("created_at", ""),
                    "lang": tweet.get("lang", ""),
                    "media": tweet.get("media", {}).get("photos", []),
                    "url": "https://x.com/" + tweet.get("author", {}).get("screen_name", "") + "/status/" + tweet_id,
                }
    except Exception:
        pass
    return None


# ─── بطاقة الملف الشخصي المكبّرة ─────────────────────────────────────────────
def render_profile_card(data):
    # type: (Dict[str, Any]) -> None

    # صورة الملف الشخصي
    profile_img_url = data.get("profile_image", "")
    if profile_img_url:
        b64 = image_to_base64(profile_img_url)
        if b64:
            avatar_html = '<img src="data:image/jpeg;base64,' + b64 + '" class="profile-avatar">'
        else:
            avatar_html = '<div style="width:120px;height:120px;border-radius:50%;background:#1d9bf0;display:flex;align-items:center;justify-content:center;font-size:3em;border:4px solid #1d9bf0;">👤</div>'
    else:
        avatar_html = '<div style="width:120px;height:120px;border-radius:50%;background:#1d9bf0;display:flex;align-items:center;justify-content:center;font-size:3em;border:4px solid #1d9bf0;">👤</div>'

    # التوثيق
    verified_html = ' <span class="verified-badge">✓</span>' if data.get("verified") else ""

    # User ID badge
    user_id_html = ""
    uid = clean_text(data.get("user_id", ""))
    if uid:
        user_id_html = '<div><span class="user-id-badge">🆔 ID: ' + uid + '</span></div>'

    # الإحصائيات
    stats_html = (
        '<div class="stats-row">'
        + '<div class="stat-item"><div class="stat-value">'
        + format_number(data.get("followers", 0))
        + '</div><div class="stat-label">👥 متابعون</div></div>'
        + '<div class="stat-item"><div class="stat-value">'
        + format_number(data.get("following", 0))
        + '</div><div class="stat-label">➡️ يتابع</div></div>'
        + '<div class="stat-item"><div class="stat-value">'
        + format_number(data.get("posts", 0))
        + '</div><div class="stat-label">📝 منشورات</div></div>'
        + '</div>'
    )

    # الوصف
    bio_html = ""
    raw_bio = clean_text(data.get("bio", ""))
    if raw_bio:
        bio_html = '<div class="bio-section">📄 ' + raw_bio + '</div>'

    # الموقع وتاريخ الانضمام
    meta_parts = []
    raw_loc = clean_text(data.get("location", ""))
    if raw_loc:
        meta_parts.append('<span class="meta-item">📍 ' + raw_loc + '</span>')

    raw_date = clean_text(data.get("join_date", ""))
    if raw_date and raw_date not in ("غير متوفر", ""):
        try:
            dt = datetime.strptime(raw_date, "%a %b %d %H:%M:%S +0000 %Y")
            raw_date = dt.strftime("%d/%m/%Y")
        except Exception:
            pass
        meta_parts.append('<span class="meta-item">📅 انضم في: ' + raw_date + '</span>')

    meta_html = ""
    if meta_parts:
        meta_html = '<div class="meta-row">' + "".join(meta_parts) + '</div>'

    display_name   = clean_text(data.get("name", data.get("username", "")))
    display_user   = clean_text(data.get("username", ""))
    display_source = clean_text(data.get("source", "Unknown"))

    card_html = (
        '<div class="profile-card">'
          '<div class="profile-header">'
            + avatar_html
            + '<div style="flex:1;">'
                '<div class="profile-name">' + display_name + verified_html + '</div>'
                '<div class="profile-username">@' + display_user + '</div>'
                '<span class="source-badge">📡 ' + display_source + '</span>'
                + user_id_html
              '</div>'
          '</div>'
          + stats_html
          + bio_html
          + meta_html
        + '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)

    # ✅ عرض ID في حقل قابل للنسخ
    if uid:
        st.text_input(
            "🆔 معرّف الحساب (User ID) — انقر للنسخ",
            value=uid,
            disabled=True,
            help="هذا هو المعرّف الرقمي الثابت للحساب"
        )


# ─── الشريط الجانبي ──────────────────────────────────────────────────────────
def setup_sidebar():
    # type: () -> Any
    with st.sidebar:
        st.markdown("## 🔍 محلل حسابات X")
        st.markdown("---")
        model = None
        if GEMINI_AVAILABLE:
            api_key = st.text_input(
                "🔑 مفتاح Gemini API",
                type="password",
                placeholder="AIza...",
                help="احصل على مفتاحك: https://aistudio.google.com/apikey"
            )
            gemini_model = st.selectbox(
                "🤖 نموذج Gemini",
                ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
                index=0
            )
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(gemini_model)
                    st.success("✅ Gemini متصل")
                except Exception as e:
                    st.error("❌ خطأ: " + str(e)[:60])
        else:
            st.warning("⚠️ google-generativeai غير مثبت")
        st.markdown("---")
        st.markdown("""
        **كيفية الاستخدام:**
        1. أدخل مفتاح Gemini API
        2. أدخل رابط أو اسم حساب X
        3. اضغط "تحليل الحساب"
        4. راجع النتائج والتقرير
        """)
        return model


# ─── دالة معالجة أخطاء Gemini ────────────────────────────────────────────────
def handle_gemini_error(e):
    # type: (Exception) -> None
    err = str(e)
    if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
        st.warning(
            "⚠️ **تجاوزت الحد المجاني لـ Gemini API (429)**\n\n"
            "احصل على مفتاح جديد من: https://aistudio.google.com/apikey\n\n"
            "أو انتظر حتى يتجدد الحد غداً."
        )
    elif "API_KEY_INVALID" in err or "invalid" in err.lower():
        st.error("❌ مفتاح API غير صحيح — تحقق من المفتاح في الشريط الجانبي.")
    elif "not found" in err.lower() or "404" in err:
        st.error("❌ النموذج المحدد غير متاح — جرب نموذجاً آخر.")
    else:
        st.error("❌ خطأ في Gemini: " + err[:150])


# ─── تبويب تحليل الحساب ──────────────────────────────────────────────────────
def account_tab(model):
    # type: (Any) -> None
    st.markdown("### 🔍 تحليل حساب X")

    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input(
            "رابط أو اسم الحساب",
            placeholder="مثال: @username أو https://x.com/username",
            label_visibility="collapsed"
        )
    with col2:
        analyze_btn = st.button("🔍 تحليل", use_container_width=True)

    with st.expander("📝 إدخال يدوي (في حال فشل الجلب التلقائي)"):
        m1, m2 = st.columns(2)
        with m1:
            manual_name     = st.text_input("الاسم الكامل")
            manual_username = st.text_input("اسم المستخدم (@)")
            manual_user_id  = st.text_input("معرّف الحساب (User ID)")
            manual_bio      = st.text_area("الوصف (Bio)", height=80)
            manual_location = st.text_input("الموقع")
        with m2:
            manual_followers = st.number_input("المتابعون", min_value=0, value=0)
            manual_following = st.number_input("يتابع",     min_value=0, value=0)
            manual_posts     = st.number_input("المنشورات", min_value=0, value=0)
            manual_join      = st.text_input("تاريخ الانضمام")
        use_manual = st.checkbox("استخدام البيانات اليدوية")

    if analyze_btn and user_input:
        username = extract_username(user_input)
        if not username:
            st.error("❌ تعذر استخراج اسم المستخدم.")
            return

        st.info("🔄 جاري جلب بيانات @" + username + "...")

        if use_manual:
            data = {
                "name":          manual_name or username,
                "username":      manual_username.lstrip("@") or username,
                "user_id":       manual_user_id,
                "bio":           manual_bio,
                "followers":     int(manual_followers),
                "following":     int(manual_following),
                "posts":         int(manual_posts),
                "location":      manual_location,
                "join_date":     manual_join or "غير متوفر",
                "verified":      False,
                "profile_image": "",
                "source":        "إدخال يدوي",
            }
            source = "manual"
        else:
            with st.spinner("جاري المحاولة عبر Twitter API / FxTwitter / Nitter..."):
                data, source = fetch_user_data(username)

        if data:
            st.success("✅ تم جلب البيانات من: " + data.get("source", source))
            render_profile_card(data)

            if model:
                with st.spinner("🤖 جاري التحليل بالذكاء الاصطناعي..."):
                    try:
                        prompt = (
                            "أنت محلل استخباراتي متخصص في تحليل حسابات منصة X.\n\n"
                            "حلل الحساب التالي وقدم تقريرًا شاملًا:\n\n"
                            "معلومات الحساب:\n"
                            "- الاسم: " + str(data.get("name", "")) + "\n"
                            "- اسم المستخدم: @" + str(data.get("username", "")) + "\n"
                            "- معرّف الحساب (ID): " + str(data.get("user_id", "غير متوفر")) + "\n"
                            "- الوصف: " + str(data.get("bio", "لا يوجد")) + "\n"
                            "- المتابعون: " + format_number(data.get("followers", 0)) + "\n"
                            "- يتابع: " + format_number(data.get("following", 0)) + "\n"
                            "- المنشورات: " + format_number(data.get("posts", 0)) + "\n"
                            "- الموقع: " + str(data.get("location", "غير محدد")) + "\n"
                            "- تاريخ الانضمام: " + str(data.get("join_date", "غير متوفر")) + "\n"
                            "- موثق: " + ("نعم" if data.get("verified") else "لا") + "\n\n"
                            "التقرير المطلوب:\n"
                            "1. تصنيف الحساب (شخصي/مؤسسي/إعلامي/بوت/مشبوه)\n"
                            "2. تحليل المصداقية مع التبرير\n"
                            "3. مؤشرات مثيرة للاهتمام\n"
                            "4. تحليل التأثير والانتشار\n"
                            "5. تقييم المخاطر\n"
                            "6. ملاحظات استخباراتية"
                        )
                        response = model.generate_content(prompt)
                        st.markdown("### 🤖 التقرير الاستخباراتي")
                        st.markdown(
                            '<div class="analysis-box">' + response.text + '</div>',
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        handle_gemini_error(e)
            else:
                st.info("💡 أضف مفتاح Gemini API من الشريط الجانبي.")
        else:
            st.error("❌ تعذر جلب بيانات الحساب. جرب الإدخال اليدوي.")


# ─── تبويب تحليل المنشور ─────────────────────────────────────────────────────
def tweet_tab(model):
    # type: (Any) -> None
    st.markdown("### 📝 تحليل منشور X")

    col1, col2 = st.columns([3, 1])
    with col1:
        tweet_input = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            label_visibility="collapsed"
        )
    with col2:
        fetch_btn = st.button("📥 جلب المنشور", use_container_width=True)

    st.markdown("#### 🖼️ تحليل صورة من المنشور")
    uploaded_image = st.file_uploader(
        "ارفع صورة للتحليل",
        type=["jpg", "jpeg", "png", "webp"],
        help="ارفع صورة لتحليلها بالذكاء الاصطناعي"
    )

    if uploaded_image and model:
        if st.button("🔍 تحليل الصورة"):
            with st.spinner("جاري تحليل الصورة..."):
                try:
                    img = Image.open(uploaded_image)
                    points_text = "\n".join(
                        [str(i + 1) + ". " + p for i, p in enumerate(IMAGE_ANALYSIS_POINTS)]
                    )
                    prompt = (
                        "أنت محلل استخباراتي متخصص في تحليل الصور الرقمية.\n\n"
                        "حلل هذه الصورة وفق النقاط التالية:\n\n"
                        + points_text +
                        "\n\nقدم تقريرًا مفصلًا ومنظمًا يغطي كل نقطة ذات صلة.\n"
                        "ركز على المعلومات الاستخباراتية القيمة."
                    )
                    response = model.generate_content([prompt, img])
                    st.markdown("### 🔍 نتائج تحليل الصورة")
                    st.markdown(
                        '<div class="analysis-box">' + response.text + '</div>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    handle_gemini_error(e)
    elif uploaded_image and not model:
        st.info("💡 أضف مفتاح Gemini API لتحليل الصورة.")

    if fetch_btn and tweet_input:
        tweet_id = extract_tweet_id(tweet_input)
        if not tweet_id:
            st.error("❌ تعذر استخراج معرف المنشور.")
            return

        with st.spinner("جاري جلب المنشور..."):
            tweet_data = fetch_tweet_data(tweet_id)

        if tweet_data:
            st.success("✅ تم جلب المنشور")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("❤️ إعجابات",   format_number(tweet_data.get("likes", 0)))
            c2.metric("🔁 إعادة نشر", format_number(tweet_data.get("retweets", 0)))
            c3.metric("💬 ردود",       format_number(tweet_data.get("replies", 0)))
            c4.metric("👁️ مشاهدات",  format_number(tweet_data.get("views", 0)))

            st.markdown("**نص المنشور:**")
            st.info(tweet_data.get("text", ""))

            author_line = "@" + tweet_data.get("author", "") + " (" + tweet_data.get("author_name", "") + ")"
            if tweet_data.get("author_id"):
                author_line += " — ID: `" + tweet_data["author_id"] + "`"
            st.markdown("**المؤلف:** " + author_line)

            if tweet_data.get("created_at"):
                st.markdown("**التاريخ:** " + str(tweet_data["created_at"]))

            if model:
                with st.spinner("🤖 تحليل المنشور..."):
                    try:
                        prompt = (
                            "حلل هذا المنشور من منصة X:\n\n"
                            "المنشور: " + str(tweet_data.get("text", "")) + "\n"
                            "المؤلف: @" + str(tweet_data.get("author", ""))
                            + " (" + str(tweet_data.get("author_name", "")) + ")"
                            + " — ID: " + str(tweet_data.get("author_id", "غير متوفر")) + "\n"
                            "الإحصائيات: إعجابات: " + format_number(tweet_data.get("likes", 0))
                            + " | إعادة نشر: " + format_number(tweet_data.get("retweets", 0))
                            + " | ردود: " + format_number(tweet_data.get("replies", 0))
                            + " | مشاهدات: " + format_number(tweet_data.get("views", 0)) + "\n"
                            "التاريخ: " + str(tweet_data.get("created_at", "")) + "\n\n"
                            "التحليل المطلوب:\n"
                            "1. الموضوع الرئيسي والرسالة\n"
                            "2. الجمهور المستهدف\n"
                            "3. مستوى التفاعل (عادي/عالٍ/غير عادي)\n"
                            "4. أي محتوى مثير للقلق\n"
                            "5. ملاحظات استخباراتية"
                        )
                        response = model.generate_content(prompt)
                        st.markdown("### 🤖 تحليل المنشور")
                        st.markdown(
                            '<div class="analysis-box">' + response.text + '</div>',
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        handle_gemini_error(e)
        else:
            st.error("❌ تعذر جلب المنشور. تأكد من الرابط.")


# ─── الدالة الرئيسية ─────────────────────────────────────────────────────────
def main():
    # type: () -> None
    model = setup_sidebar()
    st.markdown("""
    <div style="text-align:center; padding:20px 0 10px 0;">
        <h1 style="color:#1d9bf0; font-size:2.2em;">🔍 محلل حسابات X</h1>
        <p style="color:#8b949e; font-size:1.1em;">أداة تحليل استخباراتي متقدمة لمنصة X (تويتر)</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 تحليل حساب", "📝 تحليل منشور"])
    with tab1:
        account_tab(model)
    with tab2:
        tweet_tab(model)


main()
