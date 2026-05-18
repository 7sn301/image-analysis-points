# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.6
# الجديد: إصلاح جلب بيانات الحساب + Syndication API + debug mode

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
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
* { font-family: 'Cairo', sans-serif !important; }
.main { background: #0a0a0a; color: #e0e0e0; }
.stApp { background: #0a0a0a; }
.profile-card {
    background: linear-gradient(145deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border: 1px solid #2d2d5e;
    border-radius: 20px;
    padding: 32px;
    margin: 20px 0;
    box-shadow: 0 8px 32px rgba(0,100,255,0.15);
}
.profile-header { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }
.profile-avatar { width: 120px; height: 120px; border-radius: 50%; border: 3px solid #1da1f2; object-fit: cover; }
.avatar-placeholder {
    width: 120px; height: 120px; border-radius: 50%;
    background: linear-gradient(135deg, #1da1f2, #0d47a1);
    display: flex; align-items: center; justify-content: center;
    font-size: 48px; border: 3px solid #1da1f2;
}
.profile-name { font-size: 1.8em; font-weight: 900; color: #ffffff; margin-bottom: 4px; }
.profile-username { font-size: 1.1em; color: #1da1f2; margin-bottom: 8px; }
.user-id-badge {
    background: rgba(29,161,242,0.15); border: 1px solid #1da1f2;
    border-radius: 8px; padding: 3px 10px; font-size: 0.85em;
    color: #7ec8e3; margin-top: 4px; display: inline-block;
}
.source-badge {
    background: rgba(29,161,242,0.2); border: 1px solid rgba(29,161,242,0.5);
    border-radius: 20px; padding: 3px 12px; font-size: 0.8em; color: #7ec8e3;
}
.verified-badge { color: #1da1f2; font-size: 1.1em; margin-right: 6px; }
.stats-row { display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }
.stat-item {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px; padding: 14px 22px; text-align: center; flex: 1; min-width: 90px;
}
.stat-value { font-size: 1.6em; font-weight: 700; color: #1da1f2; }
.stat-label { font-size: 0.8em; color: #888; margin-top: 4px; }
.bio-section {
    background: rgba(255,255,255,0.05); border-right: 3px solid #1da1f2;
    border-radius: 8px; padding: 14px 18px; margin: 14px 0;
    color: #e0e0e0; font-size: 1em; line-height: 1.7;
}
.meta-row { display: flex; flex-wrap: wrap; gap: 14px; color: #aaa; font-size: 0.9em; margin-top: 12px; }
.meta-item { display: flex; align-items: center; gap: 5px; }
.app-header { text-align: center; padding: 30px 0 10px; }
.app-title {
    font-size: 2.8em; font-weight: 900;
    background: linear-gradient(135deg, #1da1f2, #7ec8e3);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.app-subtitle { color: #888; font-size: 1em; margin-top: 6px; }
.metric-card {
    background: linear-gradient(145deg, #1a1a2e, #16213e);
    border: 1px solid #2d2d5e; border-radius: 12px; padding: 18px; text-align: center;
}
.metric-value { font-size: 1.8em; font-weight: 700; color: #1da1f2; }
.metric-label { font-size: 0.85em; color: #888; margin-top: 4px; }
.stTabs [data-baseweb="tab"] { font-size: 1.1em !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
]

NITTER_MIRRORS = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.cz",
    "https://nitter.unixfox.eu",
    "https://nitter.1d4.us",
]

FXTWITTER_API = "https://api.fxtwitter.com"

TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

IMAGE_ANALYSIS_POINTS = [
    "الهوية البصرية والشعارات",
    "النصوص والكتابات الظاهرة",
    "الأشخاص والوجوه",
    "المواقع الجغرافية",
    "التواريخ والأوقات",
    "المركبات وأرقام اللوحات",
    "الأسلحة والمعدات",
    "الأعلام والرموز",
    "البنية التحتية والمنشآت",
    "المستندات والوثائق",
]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r'<[^>]+>', '', str(txt))
    txt = html_module.unescape(txt)
    txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return txt.strip()


def extract_username(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    # من رابط x.com أو twitter.com
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_.-]{1,50})(?:\?|/|$)', text)
    if m:
        uname = m.group(1)
        # تجاهل مسارات مثل "intent", "search", "home"
        skip = {"intent", "search", "home", "explore", "notifications", "messages", "i"}
        if uname.lower() not in skip:
            return uname
    # @ في البداية
    if text.startswith("@"):
        return text[1:].split()[0]
    # نص مباشر
    if re.match(r'^[A-Za-z0-9_.]{1,50}$', text):
        return text
    # آخر جزء من الرابط
    parts = text.rstrip("/").split("/")
    if parts:
        last = parts[-1].split("?")[0]
        if last and re.match(r'^[A-Za-z0-9_.]{1,50}$', last):
            return last
    return text.lstrip("@")


def extract_tweet_id(text: str) -> str:
    if not text:
        return ""
    m = re.search(r'status/(\d+)', text)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{15,20})\b', text)
    if m:
        return m.group(1)
    return ""


def format_number(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return str(n)


def format_date(date_str: str) -> str:
    if not date_str or date_str == "غير متوفر":
        return date_str or "غير متوفر"
    formats = [
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            pass
    return date_str[:10] if len(date_str) >= 10 else date_str


def image_to_base64(url: str) -> str:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": random.choice(USER_AGENTS)})
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except Exception:
        pass
    return ""

# ──────────────────────────────────────────────
# DATA FETCHING
# ──────────────────────────────────────────────

def fetch_via_syndication(username: str) -> Optional[Dict]:
    """
    Twitter Syndication API — لا تحتاج مفتاح، تعمل بشكل موثوق
    https://cdn.syndication.twimg.com/widgets/followbutton/info.json?screen_names=username
    """
    try:
        url = "https://cdn.syndication.twimg.com/widgets/followbutton/info.json"
        params = {"screen_names": username}
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Referer": "https://platform.twitter.com/",
            "Origin": "https://platform.twitter.com",
        }
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data_list = r.json()
        if not data_list or not isinstance(data_list, list):
            return None
        user = data_list[0]
        return {
            "name": user.get("name", ""),
            "username": user.get("screen_name", username),
            "user_id": str(user.get("id", user.get("id_str", ""))),
            "bio": user.get("description", ""),
            "followers": user.get("followers_count", 0),
            "following": user.get("friends_count", 0),
            "posts": user.get("statuses_count", 0),
            "location": user.get("location", ""),
            "join_date": user.get("created_at", ""),
            "verified": user.get("verified", False),
            "profile_image": user.get("profile_image_url_https", "").replace("_normal", ""),
            "banner": user.get("profile_banner_url", ""),
            "source": "Twitter Syndication API",
        }
    except Exception:
        return None


def fetch_via_twitter_v2(username: str) -> Optional[Dict]:
    """Twitter API v2"""
    try:
        url = f"https://api.twitter.com/2/users/by/username/{username}"
        params = {
            "user.fields": "description,public_metrics,created_at,location,verified,profile_image_url"
        }
        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER}",
            "User-Agent": random.choice(USER_AGENTS),
        }
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json().get("data", {})
        if not data:
            return None
        metrics = data.get("public_metrics", {})
        return {
            "name": data.get("name", ""),
            "username": data.get("username", username),
            "user_id": data.get("id", ""),
            "bio": data.get("description", ""),
            "followers": metrics.get("followers_count", 0),
            "following": metrics.get("following_count", 0),
            "posts": metrics.get("tweet_count", 0),
            "location": data.get("location", ""),
            "join_date": data.get("created_at", ""),
            "verified": data.get("verified", False),
            "profile_image": data.get("profile_image_url", "").replace("_normal", ""),
            "banner": "",
            "source": "Twitter v2 API",
        }
    except Exception:
        return None


def get_guest_token() -> str:
    try:
        r = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers={"Authorization": f"Bearer {TWITTER_BEARER}"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("guest_token", "")
    except Exception:
        pass
    return ""


def fetch_via_guest_api(username: str) -> Optional[Dict]:
    """Twitter GraphQL Guest API"""
    try:
        token = get_guest_token()
        if not token:
            return None
        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER}",
            "x-guest-token": token,
            "User-Agent": random.choice(USER_AGENTS),
        }
        url = (
            "https://api.twitter.com/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
            f"?variables=%7B%22screen_name%22%3A%22{username}%22%7D"
            "&features=%7B%22verified_phone_label_enabled%22%3Afalse%7D"
        )
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        result = d.get("data", {}).get("user", {}).get("result", {})
        legacy = result.get("legacy", {})
        user_id = result.get("rest_id") or legacy.get("id_str", "")
        return {
            "name": legacy.get("name", ""),
            "username": legacy.get("screen_name", username),
            "user_id": user_id,
            "bio": legacy.get("description", ""),
            "followers": legacy.get("followers_count", 0),
            "following": legacy.get("friends_count", 0),
            "posts": legacy.get("statuses_count", 0),
            "location": legacy.get("location", ""),
            "join_date": legacy.get("created_at", ""),
            "verified": legacy.get("verified", False) or result.get("is_blue_verified", False),
            "profile_image": legacy.get("profile_image_url_https", "").replace("_normal", ""),
            "banner": legacy.get("profile_banner_url", ""),
            "source": "Twitter GraphQL",
        }
    except Exception:
        return None


def fetch_via_nitter(username: str) -> Optional[Dict]:
    """Nitter mirrors scraping"""
    for mirror in NITTER_MIRRORS:
        try:
            r = requests.get(
                f"{mirror}/{username}",
                headers={"User-Agent": random.choice(USER_AGENTS)},
                timeout=12,
            )
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            def get_stat(label):
                for item in soup.select(".profile-stat-header"):
                    if label.lower() in item.get_text(strip=True).lower():
                        val = item.find_next_sibling()
                        if val:
                            return val.get_text(strip=True).replace(",", "")
                return "0"

            name_tag = soup.select_one(".profile-card-fullname")
            uname_tag = soup.select_one(".profile-card-username")
            bio_tag = soup.select_one(".profile-bio")
            loc_tag = soup.select_one(".profile-location")
            joined_tag = soup.select_one(".profile-joindate")
            avatar_tag = soup.select_one(".profile-card-avatar img")

            name = name_tag.get_text(strip=True) if name_tag else username
            uname = uname_tag.get_text(strip=True).lstrip("@") if uname_tag else username
            bio = bio_tag.get_text(separator=" ", strip=True) if bio_tag else ""
            loc = loc_tag.get_text(strip=True) if loc_tag else ""
            joined = joined_tag.get_text(strip=True) if joined_tag else ""
            avatar = ""
            if avatar_tag:
                src = avatar_tag.get("src", "")
                if src.startswith("/"):
                    src = mirror + src
                avatar = src

            # user_id من RSS
            user_id = ""
            try:
                rss_r = requests.get(
                    f"{mirror}/{username}/rss",
                    headers={"User-Agent": random.choice(USER_AGENTS)},
                    timeout=8,
                )
                m = re.search(r'twitter\.com/intent/user\?user_id=(\d+)', rss_r.text)
                if m:
                    user_id = m.group(1)
            except Exception:
                pass

            return {
                "name": name,
                "username": uname,
                "user_id": user_id,
                "bio": bio,
                "followers": get_stat("followers"),
                "following": get_stat("following"),
                "posts": get_stat("tweets"),
                "location": loc,
                "join_date": joined,
                "verified": bool(soup.select_one(".verified-icon")),
                "profile_image": avatar,
                "banner": "",
                "source": f"Nitter ({mirror})",
            }
        except Exception:
            continue
    return None


def fetch_user_data(username: str, debug: bool = False) -> Optional[Dict]:
    """
    يجرب 4 مصادر بالترتيب:
    1. Syndication API (بدون مفتاح - الأكثر موثوقية)
    2. Twitter v2 API
    3. Twitter GraphQL (Guest)
    4. Nitter mirrors
    """
    sources = [
        ("🔵 Syndication API", fetch_via_syndication),
        ("🟢 Twitter v2 API",  fetch_via_twitter_v2),
        ("🟡 Twitter GraphQL", fetch_via_guest_api),
        ("🟠 Nitter mirrors",  fetch_via_nitter),
    ]

    for label, func in sources:
        if debug:
            st.caption(f"جاري المحاولة: {label}...")
        try:
            data = func(username)
            if data and data.get("name"):
                if debug:
                    st.caption(f"✅ نجح: {label}")
                return data
        except Exception:
            pass

    return None


def fetch_tweet_data(tweet_id: str) -> Optional[Dict]:
    """جلب بيانات تغريدة عبر FxTwitter"""
    try:
        r = requests.get(
            f"{FXTWITTER_API}/status/{tweet_id}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        tweet = data.get("tweet") or data.get("data", {}).get("tweet", {})
        if not tweet:
            return None
        author = tweet.get("author") or {}
        return {
            "id": tweet_id,
            "text": tweet.get("text", ""),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "views": tweet.get("views", 0),
            "date": tweet.get("created_at", ""),
            "url": tweet.get("url", f"https://x.com/i/status/{tweet_id}"),
            "author_name": author.get("name", ""),
            "author_username": author.get("screen_name", ""),
            "author_id": str(author.get("id", author.get("id_str", ""))),
            "media": tweet.get("media", {}).get("photos", []),
            "source": "FxTwitter",
        }
    except Exception:
        return None

# ──────────────────────────────────────────────
# RENDER PROFILE CARD
# ──────────────────────────────────────────────
def render_profile_card(data: Dict):
    display_name = clean_text(data.get("name", ""))
    display_username = clean_text(data.get("username", ""))
    user_id = clean_text(data.get("user_id", ""))
    display_source = clean_text(data.get("source", "Unknown"))

    avatar_url = data.get("profile_image", "")
    if avatar_url:
        b64 = image_to_base64(avatar_url)
        avatar_html = (
            '<img class="profile-avatar" src="data:image/jpeg;base64,' + b64 + '" alt="avatar"/>'
            if b64 else '<div class="avatar-placeholder">👤</div>'
        )
    else:
        avatar_html = '<div class="avatar-placeholder">👤</div>'

    verified_html = ' <span class="verified-badge">✔️</span>' if data.get("verified") else ""
    uid_html = '<div class="user-id-badge">🆔 ' + user_id + '</div>' if user_id else ""

    followers = format_number(data.get("followers", 0))
    following = format_number(data.get("following", 0))
    posts = format_number(data.get("posts", 0))

    stats_html = (
        '<div class="stats-row">'
        '<div class="stat-item"><div class="stat-value">' + followers + '</div><div class="stat-label">متابِع</div></div>'
        '<div class="stat-item"><div class="stat-value">' + following + '</div><div class="stat-label">يتابع</div></div>'
        '<div class="stat-item"><div class="stat-value">' + posts + '</div><div class="stat-label">منشور</div></div>'
        '</div>'
    )

    bio_text = clean_text(data.get("bio", ""))
    bio_html = '<div class="bio-section">📄 ' + bio_text + '</div>' if bio_text else ""

    meta_parts = []
    loc = clean_text(data.get("location", ""))
    if loc:
        meta_parts.append("📍 " + loc)
    join_raw = data.get("join_date", "")
    join_fmt = format_date(str(join_raw)) if join_raw else ""
    if join_fmt and join_fmt != "غير متوفر":
        meta_parts.append("📅 انضم في: " + join_fmt)

    meta_html = ""
    if meta_parts:
        items = "".join(['<span class="meta-item">' + p + '</span>' for p in meta_parts])
        meta_html = '<div class="meta-row">' + items + '</div>'

    card_html = (
        '<div class="profile-card">'
        '<div class="profile-header">'
        + avatar_html +
        '<div>'
        '<div class="profile-name">' + display_name + verified_html + '</div>'
        '<div class="profile-username">@' + display_username + '</div>'
        + uid_html +
        '<span class="source-badge">📡 ' + display_source + '</span>'
        '</div>'
        '</div>'
        + stats_html + bio_html + meta_html +
        '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)

    if user_id:
        st.text_input(
            "🆔 معرّف الحساب (User ID) — انقر للنسخ",
            value=user_id,
            key="uid_" + display_username
        )

# ──────────────────────────────────────────────
# GEMINI ERROR HANDLER
# ──────────────────────────────────────────────
def handle_gemini_error(e: Exception):
    err = str(e)
    if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
        st.warning(
            "⚠️ تجاوزت الحد المجاني لـ Gemini API. "
            "احصل على مفتاح جديد من: https://aistudio.google.com/apikey"
        )
    elif "API_KEY" in err or "api key" in err.lower() or "invalid" in err.lower():
        st.error("❌ مفتاح API غير صحيح. تحقق من المفتاح في الشريط الجانبي.")
    elif "not found" in err.lower() or "404" in err:
        st.error("❌ النموذج غير متاح. غيّر النموذج في الشريط الجانبي.")
    else:
        st.error("❌ خطأ في Gemini: " + err[:200])

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
def setup_sidebar():
    st.sidebar.markdown("## ⚙️ الإعدادات")

    api_key = st.sidebar.text_input(
        "🔑 مفتاح Gemini API",
        type="password",
        placeholder="AIzaSy...",
        help="احصل على مفتاح مجاني من https://aistudio.google.com/apikey",
    )

    model_name = st.sidebar.selectbox(
        "🤖 نموذج Gemini",
        ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0,
    )

    debug_mode = st.sidebar.checkbox("🐛 وضع التشخيص (Debug)", value=False)

    model = None
    if api_key and GEMINI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            st.sidebar.success("✅ متصل بـ Gemini")
        except Exception as e:
            st.sidebar.error("❌ خطأ: " + str(e)[:100])

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
**📖 كيفية الاستخدام:**
1. أدخل مفتاح Gemini API
2. اختر تحليل الحساب أو المنشور
3. أدخل الرابط أو اسم المستخدم
4. اضغط جلب البيانات
""")

    return model, debug_mode

# ──────────────────────────────────────────────
# ACCOUNT TAB
# ──────────────────────────────────────────────
def account_tab(model, debug: bool = False):
    st.markdown("### 👤 تحليل حساب X")

    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input(
            "🔗 رابط أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username  أو  username",
        )
    with col2:
        fetch_btn = st.button("🔍 جلب البيانات", use_container_width=True)

    with st.expander("✏️ إدخال بيانات يدوي (اختياري)"):
        manual_name = st.text_input("الاسم الكامل")
        manual_bio = st.text_area("النبذة التعريفية")
        manual_followers = st.number_input("المتابعون", min_value=0, value=0)
        manual_following = st.number_input("يتابع", min_value=0, value=0)
        manual_posts = st.number_input("المنشورات", min_value=0, value=0)
        manual_location = st.text_input("الموقع")
        manual_user_id = st.text_input("معرّف الحساب (User ID)")
        use_manual = st.checkbox("استخدم البيانات اليدوية")

    if fetch_btn and user_input:
        username = extract_username(user_input)
        if not username:
            st.error("❌ لم يتم التعرف على اسم المستخدم.")
            return

        if debug:
            st.info(f"🔍 اسم المستخدم المستخرج: `{username}`")

        with st.spinner(f"⏳ جلب بيانات @{username}..."):
            if use_manual:
                data = {
                    "name": manual_name or username,
                    "username": username,
                    "user_id": manual_user_id,
                    "bio": manual_bio,
                    "followers": manual_followers,
                    "following": manual_following,
                    "posts": manual_posts,
                    "location": manual_location,
                    "join_date": "",
                    "verified": False,
                    "profile_image": "",
                    "banner": "",
                    "source": "يدوي",
                }
            else:
                data = fetch_user_data(username, debug=debug)

        if not data:
            st.error(f"❌ فشل جلب بيانات @{username} من جميع المصادر.")
            st.warning(
                "**أسباب محتملة:**\n"
                "- الحساب خاص أو غير موجود\n"
                "- تقييد مؤقت من Twitter API\n"
                "- اسم المستخدم غير صحيح\n\n"
                "**الحل:** فعّل **وضع التشخيص** في الشريط الجانبي لمعرفة سبب الفشل، "
                "أو استخدم **الإدخال اليدوي** ↑"
            )
            return

        render_profile_card(data)

        if model:
            st.markdown("---")
            st.markdown("### 🤖 التحليل الاستخباراتي")
            with st.spinner("⏳ Gemini يحلل الحساب..."):
                try:
                    uid_line = (
                        f"\n- معرّف الحساب (User ID): {data.get('user_id')}"
                        if data.get("user_id") else ""
                    )
                    prompt = f"""قم بإعداد تقرير استخباراتي مفصل عن حساب X التالي:

**بيانات الحساب:**
- الاسم: {data.get('name', '')}
- المعرف: @{data.get('username', '')}{uid_line}
- النبذة: {clean_text(data.get('bio', ''))}
- المتابعون: {format_number(data.get('followers', 0))}
- يتابع: {format_number(data.get('following', 0))}
- المنشورات: {format_number(data.get('posts', 0))}
- الموقع: {clean_text(data.get('location', ''))}
- تاريخ الانضمام: {format_date(str(data.get('join_date', '')))}
- موثّق: {'نعم' if data.get('verified') else 'لا'}

**المطلوب:**
1. تحديد هوية وطبيعة الحساب
2. تحليل مستوى التأثير والانتشار
3. المؤشرات المثيرة للاهتمام
4. التوصيات الاستخباراتية
"""
                    response = model.generate_content(prompt)
                    st.markdown(response.text)
                except Exception as e:
                    handle_gemini_error(e)
        else:
            st.info("💡 أضف مفتاح Gemini API في الشريط الجانبي للحصول على تحليل.")

# ──────────────────────────────────────────────
# TWEET TAB
# ──────────────────────────────────────────────
def tweet_tab(model):
    st.markdown("### 📝 تحليل منشور X")

    tweet_url = st.text_input(
        "🔗 رابط المنشور",
        placeholder="https://x.com/username/status/1234567890",
    )

    uploaded_image = st.file_uploader(
        "🖼️ رفع صورة للتحليل (اختياري)",
        type=["jpg", "jpeg", "png", "webp"],
    )

    fetch_btn = st.button("🔍 جلب المنشور", use_container_width=False)

    if fetch_btn and tweet_url:
        tweet_id = extract_tweet_id(tweet_url)
        if not tweet_id:
            st.error("❌ لم يتم التعرف على رابط المنشور.")
            return

        with st.spinner("⏳ جلب بيانات المنشور..."):
            tweet = fetch_tweet_data(tweet_id)

        if not tweet:
            st.error("❌ فشل جلب المنشور. تحقق من الرابط.")
            return

        st.success("✅ تم جلب المنشور بنجاح")
        c1, c2, c3, c4 = st.columns(4)
        metrics = [
            (c1, format_number(tweet.get("likes", 0)), "❤️ إعجاب"),
            (c2, format_number(tweet.get("retweets", 0)), "🔁 إعادة نشر"),
            (c3, format_number(tweet.get("replies", 0)), "💬 رد"),
            (c4, format_number(tweet.get("views", 0)), "👁️ مشاهدة"),
        ]
        for col, val, label in metrics:
            with col:
                st.markdown(
                    '<div class="metric-card">'
                    '<div class="metric-value">' + val + '</div>'
                    '<div class="metric-label">' + label + '</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("**📄 نص المنشور:**")
        st.text_area("", value=tweet.get("text", ""), height=120, disabled=True, label_visibility="collapsed")

        author_id = tweet.get("author_id", "")
        st.markdown(
            f"👤 **الكاتب:** {tweet.get('author_name', '')}  "
            f"(@{tweet.get('author_username', '')})"
            + (f"  |  🆔 **ID:** `{author_id}`" if author_id else "") +
            f"  |  📅 {format_date(tweet.get('date', ''))}"
        )

        if model:
            st.markdown("---")
            st.markdown("### 🤖 التحليل الاستخباراتي")
            with st.spinner("⏳ Gemini يحلل المنشور..."):
                try:
                    image_analysis_text = ""
                    if uploaded_image:
                        img = Image.open(uploaded_image)
                        points_str = "\n".join([f"- {p}" for p in IMAGE_ANALYSIS_POINTS])
                        img_prompt = f"""حلل هذه الصورة من منظور استخباراتي، مع التركيز على:\n{points_str}"""
                        img_response = model.generate_content([img_prompt, img])
                        image_analysis_text = "\n\n**تحليل الصورة:**\n" + img_response.text

                    tweet_prompt = f"""قم بتحليل المنشور التالي من منظور استخباراتي:

**بيانات المنشور:**
- النص: {tweet.get('text', '')}
- الإعجابات: {format_number(tweet.get('likes', 0))}
- إعادة النشر: {format_number(tweet.get('retweets', 0))}
- الردود: {format_number(tweet.get('replies', 0))}
- المشاهدات: {format_number(tweet.get('views', 0))}
- التاريخ: {format_date(tweet.get('date', ''))}
- الكاتب: {tweet.get('author_name', '')} (@{tweet.get('author_username', '')})
{('- معرّف الكاتب: ' + author_id) if author_id else ''}
{image_analysis_text}

**المطلوب:**
1. تحليل محتوى المنشور
2. تقييم التأثير والانتشار
3. المؤشرات المثيرة للاهتمام
4. السياق والتوقيت
5. التوصيات
"""
                    response = model.generate_content(tweet_prompt)
                    st.markdown(response.text)
                except Exception as e:
                    handle_gemini_error(e)
        else:
            st.info("💡 أضف مفتاح Gemini API للحصول على التحليل.")

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    model, debug_mode = setup_sidebar()

    st.markdown("""
<div class="app-header">
    <div class="app-title">🔍 محلل حسابات X</div>
    <div class="app-subtitle">أداة تحليل استخباراتي لحسابات ومنشورات منصة X (Twitter)</div>
</div>
""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 تحليل حساب", "📝 تحليل منشور"])
    with tab1:
        account_tab(model, debug=debug_mode)
    with tab2:
        tweet_tab(model)


if __name__ == "__main__":
    main()
