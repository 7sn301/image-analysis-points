# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.7
# الجديد: Twitter v1.1 API + sessions محسّنة + HTTP status في Debug

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
from typing import Optional, Dict, List
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
    border: 1px solid #2d2d5e; border-radius: 20px; padding: 32px;
    margin: 20px 0; box-shadow: 0 8px 32px rgba(0,100,255,0.15);
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
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
    "الهوية البصرية والشعارات", "النصوص والكتابات الظاهرة",
    "الأشخاص والوجوه", "المواقع الجغرافية", "التواريخ والأوقات",
    "المركبات وأرقام اللوحات", "الأسلحة والمعدات", "الأعلام والرموز",
    "البنية التحتية والمنشآت", "المستندات والوثائق",
]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r'<[^>]+>', '', str(txt))
    txt = html_module.unescape(txt)
    return txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").strip()

def extract_username(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_.]{1,50})(?:\?|/|$)', text)
    if m:
        uname = m.group(1)
        skip = {"intent","search","home","explore","notifications","messages","i","settings"}
        if uname.lower() not in skip:
            return uname
    if text.startswith("@"):
        return text[1:].split()[0]
    if re.match(r'^[A-Za-z0-9_.]{1,50}$', text):
        return text
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
    return m.group(1) if m else ""

def format_number(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000: return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(n)

def format_date(date_str: str) -> str:
    if not date_str or date_str == "غير متوفر":
        return date_str or "غير متوفر"
    for fmt in ["%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except: pass
    return date_str[:10] if len(date_str) >= 10 else date_str

def image_to_base64(url: str) -> str:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": random.choice(USER_AGENTS)})
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except: pass
    return ""

def make_headers(referer: str = "https://twitter.com/") -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Origin": referer.rstrip("/"),
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }

# ──────────────────────────────────────────────
# DATA FETCHING — 5 SOURCES
# ──────────────────────────────────────────────

def fetch_via_syndication(username: str) -> tuple:
    """Twitter Syndication CDN — بدون مفتاح"""
    try:
        session = requests.Session()
        session.headers.update(make_headers())
        url = "https://cdn.syndication.twimg.com/widgets/followbutton/info.json"
        r = session.get(url, params={"screen_names": username, "lang": "en"}, timeout=15)
        if r.status_code != 200:
            return None, r.status_code
        data_list = r.json()
        if not data_list or not isinstance(data_list, list) or len(data_list) == 0:
            return None, "empty"
        u = data_list[0]
        return {
            "name": u.get("name", ""),
            "username": u.get("screen_name", username),
            "user_id": str(u.get("id", u.get("id_str", ""))),
            "bio": u.get("description", ""),
            "followers": u.get("followers_count", 0),
            "following": u.get("friends_count", 0),
            "posts": u.get("statuses_count", 0),
            "location": u.get("location", ""),
            "join_date": u.get("created_at", ""),
            "verified": u.get("verified", False),
            "profile_image": u.get("profile_image_url_https", "").replace("_normal", ""),
            "banner": u.get("profile_banner_url", ""),
            "source": "Twitter Syndication",
        }, 200
    except Exception as e:
        return None, str(e)[:50]


def fetch_via_twitter_v1(username: str) -> tuple:
    """Twitter API v1.1"""
    try:
        r = requests.get(
            "https://api.twitter.com/1.1/users/show.json",
            params={"screen_name": username, "include_entities": "false"},
            headers={"Authorization": f"Bearer {TWITTER_BEARER}", "User-Agent": random.choice(USER_AGENTS)},
            timeout=15,
        )
        if r.status_code != 200:
            return None, r.status_code
        u = r.json()
        if "errors" in u or "error" in u:
            return None, u.get("errors", [{}])[0].get("code", "err")
        return {
            "name": u.get("name", ""),
            "username": u.get("screen_name", username),
            "user_id": str(u.get("id_str", u.get("id", ""))),
            "bio": u.get("description", ""),
            "followers": u.get("followers_count", 0),
            "following": u.get("friends_count", 0),
            "posts": u.get("statuses_count", 0),
            "location": u.get("location", ""),
            "join_date": u.get("created_at", ""),
            "verified": u.get("verified", False),
            "profile_image": u.get("profile_image_url_https", "").replace("_normal", ""),
            "banner": u.get("profile_banner_url", ""),
            "source": "Twitter v1.1 API",
        }, 200
    except Exception as e:
        return None, str(e)[:50]


def fetch_via_twitter_v2(username: str) -> tuple:
    """Twitter API v2"""
    try:
        r = requests.get(
            f"https://api.twitter.com/2/users/by/username/{username}",
            params={"user.fields": "description,public_metrics,created_at,location,verified,profile_image_url"},
            headers={"Authorization": f"Bearer {TWITTER_BEARER}", "User-Agent": random.choice(USER_AGENTS)},
            timeout=15,
        )
        if r.status_code != 200:
            return None, r.status_code
        data = r.json().get("data", {})
        if not data:
            return None, "no_data"
        m = data.get("public_metrics", {})
        return {
            "name": data.get("name", ""),
            "username": data.get("username", username),
            "user_id": data.get("id", ""),
            "bio": data.get("description", ""),
            "followers": m.get("followers_count", 0),
            "following": m.get("following_count", 0),
            "posts": m.get("tweet_count", 0),
            "location": data.get("location", ""),
            "join_date": data.get("created_at", ""),
            "verified": data.get("verified", False),
            "profile_image": data.get("profile_image_url", "").replace("_normal", ""),
            "banner": "",
            "source": "Twitter v2 API",
        }, 200
    except Exception as e:
        return None, str(e)[:50]


def get_guest_token() -> str:
    try:
        r = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers={"Authorization": f"Bearer {TWITTER_BEARER}"},
            timeout=10,
        )
        return r.json().get("guest_token", "") if r.status_code == 200 else ""
    except: return ""


def fetch_via_guest_api(username: str) -> tuple:
    """Twitter GraphQL Guest API"""
    try:
        token = get_guest_token()
        if not token:
            return None, "no_token"
        r = requests.get(
            "https://api.twitter.com/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
            f"?variables=%7B%22screen_name%22%3A%22{username}%22%7D"
            "&features=%7B%22verified_phone_label_enabled%22%3Afalse%7D",
            headers={
                "Authorization": f"Bearer {TWITTER_BEARER}",
                "x-guest-token": token,
                "User-Agent": random.choice(USER_AGENTS),
            },
            timeout=15,
        )
        if r.status_code != 200:
            return None, r.status_code
        result = r.json().get("data", {}).get("user", {}).get("result", {})
        legacy = result.get("legacy", {})
        if not legacy.get("name"):
            return None, "no_legacy"
        return {
            "name": legacy.get("name", ""),
            "username": legacy.get("screen_name", username),
            "user_id": result.get("rest_id") or legacy.get("id_str", ""),
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
        }, 200
    except Exception as e:
        return None, str(e)[:50]


def fetch_via_nitter(username: str) -> tuple:
    """Nitter mirrors scraping"""
    last_status = "no_mirrors"
    for mirror in NITTER_MIRRORS:
        try:
            r = requests.get(
                f"{mirror}/{username}",
                headers={"User-Agent": random.choice(USER_AGENTS)},
                timeout=12,
            )
            last_status = r.status_code
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            def gs(label):
                for item in soup.select(".profile-stat-header"):
                    if label.lower() in item.get_text(strip=True).lower():
                        v = item.find_next_sibling()
                        return v.get_text(strip=True).replace(",", "") if v else "0"
                return "0"

            name_tag = soup.select_one(".profile-card-fullname")
            if not name_tag:
                continue

            avatar = ""
            at = soup.select_one(".profile-card-avatar img")
            if at:
                src = at.get("src", "")
                avatar = mirror + src if src.startswith("/") else src

            user_id = ""
            try:
                rr = requests.get(f"{mirror}/{username}/rss", headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=8)
                m = re.search(r'user_id=(\d+)', rr.text)
                if m: user_id = m.group(1)
            except: pass

            return {
                "name": name_tag.get_text(strip=True),
                "username": (soup.select_one(".profile-card-username") or type("x", (), {"get_text": lambda *a, **k: username})()).get_text(strip=True).lstrip("@"),
                "user_id": user_id,
                "bio": (soup.select_one(".profile-bio") or type("x", (), {"get_text": lambda *a, **k: ""})()).get_text(separator=" ", strip=True),
                "followers": gs("followers"),
                "following": gs("following"),
                "posts": gs("tweets"),
                "location": (soup.select_one(".profile-location") or type("x", (), {"get_text": lambda *a, **k: ""})()).get_text(strip=True),
                "join_date": (soup.select_one(".profile-joindate") or type("x", (), {"get_text": lambda *a, **k: ""})()).get_text(strip=True),
                "verified": bool(soup.select_one(".verified-icon")),
                "profile_image": avatar,
                "banner": "",
                "source": f"Nitter ({mirror})",
            }, 200
        except Exception as e:
            last_status = str(e)[:30]
            continue
    return None, last_status


def fetch_user_data(username: str, debug: bool = False) -> Optional[Dict]:
    sources = [
        ("🔵 Syndication API", fetch_via_syndication),
        ("🟢 Twitter v1.1",    fetch_via_twitter_v1),
        ("🟡 Twitter v2",      fetch_via_twitter_v2),
        ("🟠 Twitter GraphQL", fetch_via_guest_api),
        ("🔴 Nitter mirrors",  fetch_via_nitter),
    ]

    debug_rows = []
    for label, func in sources:
        try:
            data, status = func(username)
            ok = data is not None and bool(data.get("name"))
            icon = "✅" if ok else "❌"
            debug_rows.append(f"{icon} **{label}** — HTTP: `{status}`")
            if ok:
                if debug:
                    st.caption("\n".join(debug_rows))
                return data
        except Exception as e:
            debug_rows.append(f"❌ **{label}** — Exception: `{str(e)[:40]}`")

    if debug:
        for row in debug_rows:
            st.caption(row)
    return None


def fetch_tweet_data(tweet_id: str) -> Optional[Dict]:
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
    except: return None

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
            '<img class="profile-avatar" src="data:image/jpeg;base64,' + b64 + '" />'
            if b64 else '<div class="avatar-placeholder">👤</div>'
        )
    else:
        avatar_html = '<div class="avatar-placeholder">👤</div>'

    verified_html = ' <span class="verified-badge">✔️</span>' if data.get("verified") else ""
    uid_html = '<div class="user-id-badge">🆔 ' + user_id + '</div>' if user_id else ""

    stats_html = (
        '<div class="stats-row">'
        '<div class="stat-item"><div class="stat-value">' + format_number(data.get("followers", 0)) + '</div><div class="stat-label">متابِع</div></div>'
        '<div class="stat-item"><div class="stat-value">' + format_number(data.get("following", 0)) + '</div><div class="stat-label">يتابع</div></div>'
        '<div class="stat-item"><div class="stat-value">' + format_number(data.get("posts", 0)) + '</div><div class="stat-label">منشور</div></div>'
        '</div>'
    )

    bio_text = clean_text(data.get("bio", ""))
    bio_html = '<div class="bio-section">📄 ' + bio_text + '</div>' if bio_text else ""

    meta_parts = []
    loc = clean_text(data.get("location", ""))
    if loc: meta_parts.append("📍 " + loc)
    jd = format_date(str(data.get("join_date", "")))
    if jd and jd != "غير متوفر": meta_parts.append("📅 انضم في: " + jd)
    meta_html = ""
    if meta_parts:
        meta_html = '<div class="meta-row">' + "".join(['<span class="meta-item">' + p + '</span>' for p in meta_parts]) + '</div>'

    card_html = (
        '<div class="profile-card"><div class="profile-header">'
        + avatar_html +
        '<div><div class="profile-name">' + display_name + verified_html + '</div>'
        '<div class="profile-username">@' + display_username + '</div>'
        + uid_html +
        '<span class="source-badge">📡 ' + display_source + '</span></div>'
        '</div>' + stats_html + bio_html + meta_html + '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)
    if user_id:
        st.text_input("🆔 معرّف الحساب — انقر للنسخ", value=user_id, key="uid_" + display_username)

# ──────────────────────────────────────────────
# GEMINI ERROR HANDLER
# ──────────────────────────────────────────────
def handle_gemini_error(e: Exception):
    err = str(e)
    if "429" in err or "quota" in err.lower():
        st.warning("⚠️ تجاوزت الحد المجاني. مفتاح جديد: https://aistudio.google.com/apikey")
    elif "API_KEY" in err or "invalid" in err.lower():
        st.error("❌ مفتاح API غير صحيح.")
    elif "not found" in err.lower() or "404" in err:
        st.error("❌ النموذج غير متاح. غيّر النموذج في الشريط الجانبي.")
    else:
        st.error("❌ خطأ Gemini: " + err[:200])

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
def setup_sidebar():
    st.sidebar.markdown("## ⚙️ الإعدادات")
    api_key = st.sidebar.text_input("🔑 مفتاح Gemini API", type="password", placeholder="AIzaSy...")
    model_name = st.sidebar.selectbox(
        "🤖 نموذج Gemini",
        ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0,
    )
    debug_mode = st.sidebar.checkbox("🐛 وضع التشخيص (Debug)", value=False,
                                      help="يُظهر HTTP status لكل مصدر بيانات")

    model = None
    if api_key and GEMINI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            st.sidebar.success("✅ متصل بـ Gemini")
        except Exception as e:
            st.sidebar.error("❌ " + str(e)[:80])

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
**📖 كيفية الاستخدام:**
1. أدخل مفتاح Gemini API
2. اختر التبويب المناسب
3. أدخل رابط الحساب أو المنشور
4. اضغط زر الجلب

**💡 نصيحة:**
لو فشل الجلب التلقائي استخدم
**الإدخال اليدوي** وأدخل البيانات يدوياً
""")
    return model, debug_mode

# ──────────────────────────────────────────────
# ACCOUNT TAB
# ──────────────────────────────────────────────
def account_tab(model, debug: bool = False):
    st.markdown("### 👤 تحليل حساب X")
    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input("🔗 رابط أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username  أو  username")
    with col2:
        fetch_btn = st.button("🔍 جلب البيانات", use_container_width=True)

    with st.expander("✏️ إدخال بيانات يدوي (اختياري)"):
        mc1, mc2 = st.columns(2)
        with mc1:
            manual_name = st.text_input("الاسم الكامل")
            manual_followers = st.number_input("المتابعون", min_value=0, value=0)
            manual_posts = st.number_input("المنشورات", min_value=0, value=0)
            manual_user_id = st.text_input("معرّف الحساب (User ID)")
        with mc2:
            manual_bio = st.text_area("النبذة التعريفية", height=100)
            manual_following = st.number_input("يتابع", min_value=0, value=0)
            manual_location = st.text_input("الموقع")
        use_manual = st.checkbox("✅ استخدم البيانات اليدوية")

    if fetch_btn and user_input:
        username = extract_username(user_input)
        if not username:
            st.error("❌ لم يتم التعرف على اسم المستخدم.")
            return

        if debug:
            st.info(f"🔍 اسم المستخدم المستخرج: **`{username}`**")

        with st.spinner(f"⏳ جلب بيانات @{username}..."):
            if use_manual:
                data = {
                    "name": manual_name or username, "username": username,
                    "user_id": manual_user_id, "bio": manual_bio,
                    "followers": manual_followers, "following": manual_following,
                    "posts": manual_posts, "location": manual_location,
                    "join_date": "", "verified": False,
                    "profile_image": "", "banner": "", "source": "يدوي",
                }
            else:
                data = fetch_user_data(username, debug=debug)

        if not data:
            st.error(f"❌ فشل جلب بيانات **@{username}** من جميع المصادر.")
            st.warning(
                "**أسباب محتملة:**\n"
                "- الحساب خاص أو غير موجود\n"
                "- Streamlit Cloud محجوب من Twitter APIs\n"
                "- تقييد مؤقت من Twitter\n\n"
                "**الحلول:**\n"
                "1. تأكد أن الحساب عام وموجود فعلاً على X\n"
                "2. جرّب حساباً معروفاً مثل `elonmusk` للاختبار\n"
                "3. استخدم **الإدخال اليدوي** ↑ لإدخال البيانات يدوياً"
            )
            return

        render_profile_card(data)

        if model:
            st.markdown("---")
            st.markdown("### 🤖 التحليل الاستخباراتي")
            with st.spinner("⏳ Gemini يحلل الحساب..."):
                try:
                    uid_line = f"\n- معرّف الحساب: {data.get('user_id')}" if data.get("user_id") else ""
                    prompt = f"""أعدّ تقريراً استخباراتياً مفصلاً عن حساب X:

**البيانات:**
- الاسم: {data.get('name','')}
- المعرف: @{data.get('username','')}{uid_line}
- النبذة: {clean_text(data.get('bio',''))}
- المتابعون: {format_number(data.get('followers',0))}
- يتابع: {format_number(data.get('following',0))}
- المنشورات: {format_number(data.get('posts',0))}
- الموقع: {clean_text(data.get('location',''))}
- الانضمام: {format_date(str(data.get('join_date','')))}
- موثّق: {'نعم' if data.get('verified') else 'لا'}

**المطلوب:**
1. هوية وطبيعة الحساب
2. مستوى التأثير والانتشار
3. المؤشرات المثيرة للاهتمام
4. التوصيات الاستخباراتية
"""
                    st.markdown(model.generate_content(prompt).text)
                except Exception as e:
                    handle_gemini_error(e)
        else:
            st.info("💡 أضف مفتاح Gemini API في الشريط الجانبي للحصول على تحليل.")

# ──────────────────────────────────────────────
# TWEET TAB
# ──────────────────────────────────────────────
def tweet_tab(model):
    st.markdown("### 📝 تحليل منشور X")
    tweet_url = st.text_input("🔗 رابط المنشور", placeholder="https://x.com/username/status/1234567890")
    uploaded_image = st.file_uploader("🖼️ رفع صورة للتحليل (اختياري)", type=["jpg","jpeg","png","webp"])
    fetch_btn = st.button("🔍 جلب المنشور")

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
        for col, val, label in [
            (c1, format_number(tweet.get("likes",0)), "❤️ إعجاب"),
            (c2, format_number(tweet.get("retweets",0)), "🔁 إعادة نشر"),
            (c3, format_number(tweet.get("replies",0)), "💬 رد"),
            (c4, format_number(tweet.get("views",0)), "👁️ مشاهدة"),
        ]:
            with col:
                st.markdown(
                    '<div class="metric-card"><div class="metric-value">' + val +
                    '</div><div class="metric-label">' + label + '</div></div>',
                    unsafe_allow_html=True
                )

        st.markdown("**📄 نص المنشور:**")
        st.text_area("", value=tweet.get("text",""), height=120, disabled=True, label_visibility="collapsed")
        author_id = tweet.get("author_id","")
        st.markdown(
            f"👤 **{tweet.get('author_name','')}**  (@{tweet.get('author_username','')})"
            + (f"  🆔 `{author_id}`" if author_id else "")
            + f"  📅 {format_date(tweet.get('date',''))}"
        )

        if model:
            st.markdown("---")
            st.markdown("### 🤖 التحليل الاستخباراتي")
            with st.spinner("⏳ Gemini يحلل المنشور..."):
                try:
                    img_text = ""
                    if uploaded_image:
                        img = Image.open(uploaded_image)
                        pts = "\n".join([f"- {p}" for p in IMAGE_ANALYSIS_POINTS])
                        img_r = model.generate_content([f"حلل الصورة استخباراتياً:\n{pts}", img])
                        img_text = "\n\n**تحليل الصورة:**\n" + img_r.text
                    prompt = f"""حلل المنشور التالي استخباراتياً:
- النص: {tweet.get('text','')}
- الإعجابات: {format_number(tweet.get('likes',0))}
- إعادة النشر: {format_number(tweet.get('retweets',0))}
- الردود: {format_number(tweet.get('replies',0))}
- المشاهدات: {format_number(tweet.get('views',0))}
- التاريخ: {format_date(tweet.get('date',''))}
- الكاتب: {tweet.get('author_name','')} (@{tweet.get('author_username','')})
{('- ID: ' + author_id) if author_id else ''}
{img_text}
المطلوب: تحليل المحتوى، التأثير، المؤشرات، التوقيت، التوصيات.
"""
                    st.markdown(model.generate_content(prompt).text)
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
