# -*- coding: utf-8 -*-
# X Account & Post Analyzer v9.2

import streamlit as st

st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

import requests
import re
import base64
import random
import html as html_module
import asyncio
import os
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

try:
    from twikit import Client as TwikitClient
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False

# ══════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* { font-family: 'Cairo', sans-serif !important; }
body, .stApp { background-color: #0d1117; color: #e6edf3; }
.main-header {
    background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
    border: 1px solid #30363d; border-radius: 12px;
    padding: 24px; text-align: center; margin-bottom: 24px;
}
.main-header h1 { color: #58a6ff; font-size: 2rem; margin: 0; }
.main-header p { color: #8b949e; margin: 4px 0 0; }
.profile-card {
    background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
    border: 1px solid #30363d; border-radius: 16px;
    padding: 24px; margin: 16px 0; direction: rtl;
}
.profile-card .avatar-img {
    width: 120px; height: 120px; border-radius: 50%;
    border: 3px solid #58a6ff; object-fit: cover;
}
.profile-card .display-name { font-size: 1.4rem; font-weight: 700; color: #e6edf3; }
.profile-card .username-tag { color: #58a6ff; font-size: 1rem; }
.profile-card .bio-text {
    color: #c9d1d9; font-size: 0.95rem; margin: 12px 0; line-height: 1.7;
}
.stat-box {
    background: #0d1117; border: 1px solid #30363d;
    border-radius: 10px; padding: 12px; text-align: center;
}
.stat-box .stat-num { font-size: 1.3rem; font-weight: 700; color: #58a6ff; }
.stat-box .stat-lbl { font-size: 0.78rem; color: #8b949e; }
.meta-badge {
    display: inline-block; background: #1f2937;
    border: 1px solid #374151; border-radius: 20px;
    padding: 4px 12px; font-size: 0.82rem; color: #9ca3af; margin: 3px;
}
.source-tag {
    background: #0d3349; border: 1px solid #1d6896;
    border-radius: 6px; padding: 3px 10px; font-size: 0.78rem; color: #58a6ff;
}
.uid-box {
    background: #0d1117; border: 1px dashed #444;
    border-radius: 8px; padding: 8px 14px;
    font-family: monospace; font-size: 0.9rem;
    color: #f0e68c; direction: ltr; text-align: left;
}
.featured-image-container {
    position: relative; width: 100%; margin: 0;
    border-radius: 16px 16px 0 0; overflow: hidden;
    border: 2px solid #30363d; border-bottom: none;
    box-shadow: 0 8px 32px rgba(0,0,0,0.6); background: #0d1117;
}
.featured-image-container img {
    width: 100%; max-height: 520px;
    object-fit: contain; background: #0d1117; display: block;
}
.featured-image-label {
    position: absolute; top: 12px; right: 14px;
    background: rgba(13,17,23,0.88); border: 1px solid #30363d;
    border-radius: 20px; padding: 5px 16px;
    font-size: 0.82rem; color: #58a6ff; backdrop-filter: blur(8px);
}
.upload-hint {
    background: linear-gradient(135deg, #0d1117, #161b22);
    border: 2px dashed #30363d; border-radius: 12px;
    padding: 18px 24px; text-align: center;
    margin: 12px 0 4px 0; direction: rtl;
}
.upload-hint-title { font-size: 0.95rem; color: #8b949e; margin-bottom: 4px; }
.upload-hint-sub { font-size: 0.78rem; color: #484f58; }
.login-status-ok {
    background: #0d2818; border: 1px solid #238636;
    border-radius: 10px; padding: 12px 16px;
    margin: 8px 0; direction: rtl;
}
.login-status-ok .ls-icon { font-size: 1.3rem; }
.login-status-ok .ls-name { color: #3fb950; font-weight: 700; font-size: 1rem; }
.login-status-ok .ls-user { color: #8b949e; font-size: 0.85rem; }
.login-status-fail {
    background: #2d0f0f; border: 1px solid #da3633;
    border-radius: 10px; padding: 12px 16px; margin: 8px 0; direction: rtl;
}
.login-status-fail .ls-icon { font-size: 1.3rem; }
.login-status-fail .ls-msg { color: #f85149; font-size: 0.9rem; }
.stTextInput>div>div>input,
.stTextArea>div>div>textarea {
    background-color: #161b22 !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
}
.stButton>button {
    background: linear-gradient(135deg, #238636, #2ea043);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 10px 28px;
}
.stButton>button:hover { opacity: 0.88; }
div[data-testid="stTabs"] button { color: #c9d1d9 !important; }
.stSidebar { background-color: #161b22 !important; }
.stAlert { direction: rtl; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ثوابت
# ══════════════════════════════════════════════════════════════
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

NITTER_MIRRORS = [
    "https://nitter.privacyredirect.com",
    "https://xcancel.com",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.space",
    "https://nuku.trabun.org",
    "https://lightbrd.com",
    "https://nitter.kareem.one",
    "https://nitter.net",
]

FXTWITTER_API = "https://api.fxtwitter.com"
COOKIES_FILE = "/tmp/twikit_cookies.json"

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

# ══════════════════════════════════════════════════════════════
# دوال مساعدة
# ══════════════════════════════════════════════════════════════
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    text = html_module.unescape(text)
    return text.strip()


def extract_username(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_.]{1,50})(?:\?|/|$)', text)
    if m:
        return m.group(1).rstrip("/")
    if text.startswith("@"):
        return text[1:].split()[0].split("?")[0]
    if re.match(r'^[A-Za-z0-9_.]{1,50}$', text):
        return text
    parts = text.rstrip("/").split("/")
    last = parts[-1].split("?")[0] if parts else ""
    if last and re.match(r'^[A-Za-z0-9_.]{1,50}$', last):
        return last
    return text.lstrip("@")


def extract_tweet_id(text: str) -> str:
    if not text:
        return ""
    m = re.search(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)', text)
    if m:
        return m.group(1)
    if re.match(r'^\d{10,}$', text.strip()):
        return text.strip()
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
        return str(n) if n else "0"


def format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        for fmt in (
            "%a %b %d %H:%M:%S %z %Y",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(date_str[:25], fmt[:len(date_str[:25])])
                return dt.strftime("%d/%m/%Y")
            except Exception:
                continue
    except Exception:
        pass
    return date_str[:10]


def image_to_base64(url: str) -> str:
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=10, stream=True)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content))
            if img.mode in ("RGBA", "P", "LA", "CMYK"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return ""


def pil_to_base64(img: Image.Image, quality: int = 92) -> str:
    try:
        if img.mode in ("RGBA", "P", "LA", "CMYK"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
# twikit — دوال أساسية
# ══════════════════════════════════════════════════════════════
def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _twikit_login(tw_user: str, tw_email: str, tw_pass: str):
    """تسجيل الدخول وإرجاع الـ client أو None."""
    if not TWIKIT_AVAILABLE:
        return None, "twikit غير مثبت"
    try:
        client = TwikitClient("en-US")
        if os.path.exists(COOKIES_FILE):
            client.load_cookies(COOKIES_FILE)
            return client, "cookies"
        await client.login(
            auth_info_1=tw_user,
            auth_info_2=tw_email,
            password=tw_pass,
        )
        client.save_cookies(COOKIES_FILE)
        return client, "login"
    except Exception as e:
        if os.path.exists(COOKIES_FILE):
            os.remove(COOKIES_FILE)
        return None, str(e)


async def _twikit_test_login(tw_user: str, tw_email: str, tw_pass: str) -> Dict:
    """اختبار تسجيل الدخول وإرجاع نتيجة مفصّلة."""
    if not TWIKIT_AVAILABLE:
        return {"ok": False, "msg": "twikit غير مثبت في requirements.txt"}
    if not tw_user or not tw_pass:
        return {"ok": False, "msg": "يرجى إدخال اسم المستخدم وكلمة المرور"}
    try:
        client = TwikitClient("en-US")
        # حذف الكوكيز القديمة لإجبار تسجيل دخول جديد
        if os.path.exists(COOKIES_FILE):
            os.remove(COOKIES_FILE)
        await client.login(
            auth_info_1=tw_user,
            auth_info_2=tw_email,
            password=tw_pass,
        )
        client.save_cookies(COOKIES_FILE)
        # جلب بيانات الحساب للتأكيد
        me = await client.get_user_by_screen_name(tw_user.lstrip("@"))
        name = clean_text(me.name) if me else tw_user
        screen = me.screen_name if me else tw_user
        return {
            "ok": True,
            "name": name,
            "screen_name": screen,
            "msg": "تم تسجيل الدخول بنجاح وحفظ الجلسة",
        }
    except Exception as e:
        return {"ok": False, "msg": str(e)[:200]}


def test_twikit_login(tw_user: str, tw_email: str, tw_pass: str) -> Dict:
    return _run_async(_twikit_test_login(tw_user, tw_email, tw_pass))


async def _twikit_fetch(username: str, tw_user: str, tw_email: str, tw_pass: str) -> Optional[Dict]:
    if not TWIKIT_AVAILABLE:
        return None
    try:
        client = TwikitClient("en-US")
        if os.path.exists(COOKIES_FILE):
            client.load_cookies(COOKIES_FILE)
        else:
            await client.login(
                auth_info_1=tw_user,
                auth_info_2=tw_email,
                password=tw_pass,
            )
            client.save_cookies(COOKIES_FILE)

        user = await client.get_user_by_screen_name(username)
        if not user:
            return None

        return {
            "name": clean_text(user.name or ""),
            "username": user.screen_name or username,
            "user_id": str(user.id or ""),
            "bio": clean_text(user.description or ""),
            "followers": user.followers_count or 0,
            "following": user.following_count or 0,
            "posts": user.statuses_count or 0,
            "location": clean_text(user.location or ""),
            "join_date": str(user.created_at or ""),
            "verified": bool(user.verified or user.is_blue_verified),
            "profile_image": (user.profile_image_url_https or "").replace("_normal", ""),
            "banner": user.profile_banner_url or "",
            "source": "twikit",
        }
    except Exception as e:
        err = str(e)
        if any(k in err.lower() for k in ["cookies", "auth", "login"]):
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
        return None


def fetch_via_twikit(username: str, tw_user: str, tw_email: str, tw_pass: str) -> Optional[Dict]:
    if not tw_user or not tw_pass:
        return None
    return _run_async(_twikit_fetch(username, tw_user, tw_email, tw_pass))


# ══════════════════════════════════════════════════════════════
# Nitter
# ══════════════════════════════════════════════════════════════
def fetch_via_nitter(username: str, debug: bool = False) -> Optional[Dict]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "ar,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            code = r.status_code
            if debug:
                st.caption(f"  {mirror} — HTTP {code}")
            if code != 200:
                continue

            page_lower = r.text.lower()
            if any(k in page_lower for k in ["proof-of-work", "anubis", "challenge", "captcha", "user not found"]):
                if debug:
                    st.caption(f"  {mirror} محمي (bot protection)")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            name = ""
            for sel in [".profile-card-fullname", ".fullname", "h1.fullname", ".user-fullname"]:
                el = soup.select_one(sel)
                if el:
                    name = clean_text(el.text)
                    break
            if not name:
                continue

            def get_stat(label_text):
                for li in soup.select(".profile-stat"):
                    lbl = li.select_one(".profile-stat-header, .stat-header")
                    num = li.select_one(".profile-stat-num")
                    if lbl and num and label_text.lower() in lbl.text.lower():
                        return clean_text(num.text).replace(",", "")
                return "0"

            followers = get_stat("Followers")
            following = get_stat("Following")
            posts = get_stat("Tweets")

            bio_el = soup.select_one(".profile-bio p, .bio")
            bio = clean_text(bio_el.text) if bio_el else ""

            loc_el = soup.select_one(".profile-location span:last-child")
            loc = clean_text(loc_el.text) if loc_el else ""

            join_el = soup.select_one(".profile-joindate span:last-child")
            join = clean_text(join_el.text) if join_el else ""

            img_el = soup.select_one(".profile-card-avatar img, .avatar img")
            img_url = ""
            if img_el:
                src = img_el.get("src", "")
                if src.startswith("/"):
                    src = mirror + src
                img_url = src

            verified = bool(soup.select_one(".verified-icon, .verified"))

            user_id = ""
            try:
                rss_r = requests.get(f"{mirror}/{username}/rss", headers=headers, timeout=8)
                uid_m = re.search(r'<uri>.*?/(\d{5,})</uri>', rss_r.text)
                if uid_m:
                    user_id = uid_m.group(1)
            except Exception:
                pass

            return {
                "name": name,
                "username": username,
                "user_id": user_id,
                "bio": bio,
                "followers": int(followers) if followers.isdigit() else 0,
                "following": int(following) if following.isdigit() else 0,
                "posts": int(posts) if posts.isdigit() else 0,
                "location": loc,
                "join_date": join,
                "verified": verified,
                "profile_image": img_url,
                "banner": "",
                "source": f"Nitter ({mirror})",
            }
        except Exception as e:
            if debug:
                st.caption(f"  {mirror} خطأ: {str(e)[:60]}")
            continue
    return None


# ══════════════════════════════════════════════════════════════
# FxTwitter
# ══════════════════════════════════════════════════════════════
def fetch_tweet_data(tweet_id: str) -> Optional[Dict]:
    try:
        url = f"{FXTWITTER_API}/status/{tweet_id}"
        r = requests.get(
            url,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=15
        )
        if r.status_code != 200:
            return None
        tweet = r.json().get("tweet", {})
        if not tweet:
            return None
        author = tweet.get("author", {})
        return {
            "text": clean_text(tweet.get("text", "")),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "views": tweet.get("views", 0),
            "date": tweet.get("created_at", ""),
            "lang": tweet.get("lang", ""),
            "url": tweet.get("url", ""),
            "author_name": clean_text(author.get("name", "")),
            "author_username": author.get("screen_name", ""),
            "author_avatar": author.get("avatar_url", ""),
            "media": tweet.get("media", {}).get("all", []),
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# fetch_user_data
# ══════════════════════════════════════════════════════════════
def fetch_user_data(
    username: str,
    tw_user: str = "",
    tw_email: str = "",
    tw_pass: str = "",
    debug: bool = False
) -> Optional[Dict]:
    sources = []
    if tw_user and tw_pass:
        sources.append(("🔵 twikit", lambda: fetch_via_twikit(username, tw_user, tw_email, tw_pass)))
    sources.append(("🟠 Nitter mirrors", lambda: fetch_via_nitter(username, debug)))

    for label, func in sources:
        if debug:
            st.caption(f"جاري المحاولة: {label}...")
        data = func()
        if data and data.get("name"):
            if debug:
                st.success(f"✅ نجح: {label}")
            return data
        elif debug:
            st.caption(f"فشل: {label}")
    return None


# ══════════════════════════════════════════════════════════════
# render_profile_card
# ══════════════════════════════════════════════════════════════
def render_profile_card(data: Dict, featured_image_b64: str = ""):
    name = html_module.escape(data.get("name", ""))
    uname = html_module.escape(data.get("username", ""))
    bio = html_module.escape(data.get("bio", ""))
    loc = html_module.escape(data.get("location", ""))
    join = html_module.escape(format_date(data.get("join_date", "")))
    uid = html_module.escape(str(data.get("user_id", "")))
    source = html_module.escape(data.get("source", ""))
    verified = data.get("verified", False)

    followers = format_number(data.get("followers", 0))
    following = format_number(data.get("following", 0))
    posts = format_number(data.get("posts", 0))

    verified_badge = ' <span style="color:#1d9bf0" title="موثق">✓</span>' if verified else ""

    img_url = data.get("profile_image", "")
    if img_url and img_url.startswith("http"):
        b64 = image_to_base64(img_url)
        img_src = f"data:image/jpeg;base64,{b64}" if b64 else img_url
    else:
        img_src = "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"

    avatar_html = (
        '<img class="avatar-img" src="' + img_src + '" '
        'onerror="this.src=\'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png\'">'
    )

    uid_html = ""
    if uid:
        uid_html = (
            '<div style="margin-top:12px">'
            '<div style="font-size:0.8rem;color:#8b949e;margin-bottom:4px">🆔 User ID</div>'
            '<div class="uid-box">' + uid + '</div>'
            '</div>'
        )

    bio_html = '<div class="bio-text">' + bio + '</div>' if bio else ""

    meta_parts = []
    if loc:
        meta_parts.append("📍 " + loc)
    if join:
        meta_parts.append("📅 انضم في " + join)
    if source:
        meta_parts.append('<span class="source-tag">' + source + '</span>')
    meta_html = "".join('<span class="meta-badge">' + p + '</span>' for p in meta_parts)

    featured_html = ""
    if featured_image_b64:
        featured_html = (
            '<div class="featured-image-container">'
            '<div class="featured-image-label">📷 صورة الحساب</div>'
            '<img src="data:image/jpeg;base64,' + featured_image_b64 + '" alt="صورة الحساب">'
            '</div>'
        )

    card_style = ' style="border-radius:0 0 16px 16px;border-top:none;margin-top:0"' if featured_image_b64 else ""

    card = (
        featured_html
        + '<div class="profile-card" dir="rtl"' + card_style + '>'
        + '<div style="display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap">'
        + '<div>' + avatar_html + '</div>'
        + '<div style="flex:1;min-width:200px">'
        + '<div class="display-name">' + name + verified_badge + '</div>'
        + '<div class="username-tag">@' + uname + '</div>'
        + bio_html
        + '<div style="margin-top:8px">' + meta_html + '</div>'
        + uid_html
        + '</div>'
        + '</div>'
        + '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px">'
        + '<div class="stat-box"><div class="stat-num">' + followers + '</div><div class="stat-lbl">متابع</div></div>'
        + '<div class="stat-box"><div class="stat-num">' + following + '</div><div class="stat-lbl">يتابع</div></div>'
        + '<div class="stat-box"><div class="stat-num">' + posts + '</div><div class="stat-lbl">تغريدة</div></div>'
        + '</div>'
        + '</div>'
    )
    st.markdown(card, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# handle_gemini_error
# ══════════════════════════════════════════════════════════════
def handle_gemini_error(e: Exception):
    err = str(e).lower()
    if "429" in err or "quota" in err:
        st.error("تجاوزت حصة Gemini — انتظر قليلاً ثم أعد المحاولة.")
    elif "api_key" in err or "api key" in err or "invalid" in err:
        st.error("مفتاح Gemini غير صالح. تحقق منه في الشريط الجانبي.")
    elif "not found" in err or "404" in err:
        st.error("النموذج غير متاح. جرّب gemini-2.0-flash-lite.")
    else:
        st.error(f"خطأ Gemini: {str(e)[:200]}")


# ══════════════════════════════════════════════════════════════
# setup_sidebar — مع زر تأكيد الدخول ✅
# ══════════════════════════════════════════════════════════════
def setup_sidebar():
    st.sidebar.markdown("## ⚙️ الإعدادات")
    st.sidebar.markdown("### 🤖 Gemini AI")

    gemini_key = st.sidebar.text_input(
        "مفتاح Gemini API",
        type="password",
        placeholder="AIza...",
    )
    gemini_model = st.sidebar.selectbox(
        "النموذج",
        ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🐦 حساب X (لـ twikit)")
    use_twikit = st.sidebar.checkbox("تفعيل twikit", value=TWIKIT_AVAILABLE)

    tw_user = ""
    tw_email = ""
    tw_pass = ""

    if use_twikit and TWIKIT_AVAILABLE:
        tw_user = st.sidebar.text_input(
            "اسم المستخدم (@)",
            placeholder="your_account",
            key="tw_user_input"
        )
        tw_email = st.sidebar.text_input(
            "البريد الإلكتروني",
            placeholder="your@email.com",
            key="tw_email_input"
        )
        tw_pass = st.sidebar.text_input(
            "كلمة المرور",
            type="password",
            key="tw_pass_input"
        )

        st.sidebar.markdown("---")

        # ── زر تأكيد الدخول ───────────────────────────────
        col_login, col_del = st.sidebar.columns(2)

        with col_login:
            login_btn = st.button(
                "🔐 تأكيد الدخول",
                use_container_width=True,
                key="login_test_btn"
            )
        with col_del:
            del_btn = st.button(
                "🗑 حذف الجلسة",
                use_container_width=True,
                key="del_cookies_btn"
            )

        # معالجة حذف الجلسة
        if del_btn:
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
                st.sidebar.success("✅ تم حذف الجلسة المحفوظة")
            else:
                st.sidebar.info("لا توجد جلسة محفوظة")

        # معالجة تأكيد الدخول
        if login_btn:
            if not tw_user or not tw_pass:
                st.sidebar.error("❌ أدخل اسم المستخدم وكلمة المرور أولاً")
            else:
                with st.sidebar:
                    with st.spinner("جاري تسجيل الدخول..."):
                        result = test_twikit_login(tw_user, tw_email, tw_pass)

                if result["ok"]:
                    disp_name = html_module.escape(result.get("name", tw_user))
                    disp_user = html_module.escape(result.get("screen_name", tw_user))
                    st.sidebar.markdown(
                        '<div class="login-status-ok">'
                        '<div class="ls-icon">✅</div>'
                        '<div class="ls-name">' + disp_name + '</div>'
                        '<div class="ls-user">@' + disp_user + '</div>'
                        '<div style="font-size:0.78rem;color:#3fb950;margin-top:4px">'
                        'تم تسجيل الدخول بنجاح — الجلسة محفوظة</div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    err_msg = html_module.escape(result.get("msg", "خطأ غير معروف"))
                    st.sidebar.markdown(
                        '<div class="login-status-fail">'
                        '<div class="ls-icon">❌</div>'
                        '<div class="ls-msg">' + err_msg + '</div>'
                        '<div style="font-size:0.75rem;color:#8b949e;margin-top:6px">'
                        'تحقق من البيانات وأعد المحاولة</div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )

        # حالة الجلسة الحالية
        if os.path.exists(COOKIES_FILE):
            st.sidebar.markdown(
                '<div style="background:#0d2818;border:1px solid #238636;'
                'border-radius:8px;padding:8px 12px;margin-top:6px;'
                'font-size:0.82rem;color:#3fb950;direction:rtl">'
                '🟢 جلسة نشطة محفوظة</div>',
                unsafe_allow_html=True,
            )
        else:
            st.sidebar.markdown(
                '<div style="background:#1c1c1c;border:1px solid #444;'
                'border-radius:8px;padding:8px 12px;margin-top:6px;'
                'font-size:0.82rem;color:#8b949e;direction:rtl">'
                '⚪ لا توجد جلسة — سيتم تسجيل الدخول عند الطلب</div>',
                unsafe_allow_html=True,
            )

        st.sidebar.info("💡 يُنصح باستخدام حساب ثانوي. لن يتم نشر أي شيء.")

    elif use_twikit and not TWIKIT_AVAILABLE:
        st.sidebar.warning("twikit غير مثبت. أضف twikit>=2.0.0 في requirements.txt")

    st.sidebar.markdown("---")
    debug = st.sidebar.checkbox("🔬 وضع التشخيص", value=False)

    return gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug


# ══════════════════════════════════════════════════════════════
# account_tab
# ══════════════════════════════════════════════════════════════
def account_tab(gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug):
    st.markdown("### 👤 تحليل حساب X")

    col1, col2 = st.columns([3, 1])
    with col1:
        raw_input = st.text_input(
            "رابط الحساب أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username",
            label_visibility="collapsed",
        )
    with col2:
        fetch_btn = st.button("🔍 جلب البيانات", use_container_width=True)

    st.markdown("""
    <div class="upload-hint">
      <div class="upload-hint-title">🖼 أضف صورة الحساب (اختياري)</div>
      <div class="upload-hint-sub">اسحب وأفلت صورة البروفايل أو البانر — ستظهر فوق بطاقة الملف الشخصي</div>
    </div>
    """, unsafe_allow_html=True)

    uploaded_account_img = st.file_uploader(
        "اسحب الصورة هنا أو انقر للاختيار",
        type=["jpg", "jpeg", "png", "webp"],
        key="account_img_uploader",
        label_visibility="collapsed",
    )

    featured_b64 = ""
    if uploaded_account_img:
        try:
            pil_img = Image.open(uploaded_account_img)
            featured_b64 = pil_to_base64(pil_img, quality=92)
            if featured_b64:
                st.success("✅ تم تحميل الصورة — ستظهر فوق بطاقة الحساب")
            else:
                st.warning("لم يتم معالجة الصورة بشكل صحيح.")
        except Exception as e:
            st.error(f"خطأ في معالجة الصورة: {e}")

    with st.expander("✏️ إدخال البيانات يدوياً (دائماً يعمل)"):
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_name = st.text_input("الاسم")
            m_username = st.text_input("اسم المستخدم")
            m_user_id = st.text_input("User ID")
            m_bio = st.text_area("النبذة", height=80)
        with m_col2:
            m_followers = st.number_input("المتابعون", min_value=0, step=1)
            m_following = st.number_input("يتابع", min_value=0, step=1)
            m_posts = st.number_input("التغريدات", min_value=0, step=1)
            m_location = st.text_input("الموقع")
            m_join = st.text_input("تاريخ الانضمام (dd/mm/yyyy)")
        manual_btn = st.button("💾 استخدام البيانات اليدوية", use_container_width=True)

    data = None

    if fetch_btn and raw_input:
        username = extract_username(raw_input)
        if not username:
            st.error("تعذّر استخراج اسم المستخدم. تحقق من الرابط.")
            return

        st.info(f"جاري جلب بيانات @{username} ...")
        if debug:
            st.markdown("**سجل التشخيص:**")

        with st.spinner("يتصل بالمصادر..."):
            data = fetch_user_data(username, tw_user, tw_email, tw_pass, debug)

        if not data:
            st.error(f"فشل جلب بيانات @{username} من جميع المصادر.")
            st.warning(
                "الأسباب المحتملة:\n"
                "- الحساب خاص أو موقوف\n"
                "- اسم المستخدم غير صحيح\n"
                "- Streamlit Cloud محظور من Twitter\n\n"
                "الحلول:\n"
                "1. أدخل بيانات حساب X واضغط (تأكيد الدخول) في الشريط الجانبي\n"
                "2. استخدم الإدخال اليدوي أدناه"
            )
            if featured_b64:
                st.markdown("---")
                st.markdown(
                    '<div class="featured-image-container">'
                    '<div class="featured-image-label">📷 صورة الحساب</div>'
                    '<img src="data:image/jpeg;base64,' + featured_b64 + '" alt="صورة">'
                    '</div>',
                    unsafe_allow_html=True,
                )
            return

    if manual_btn and m_name:
        data = {
            "name": m_name,
            "username": m_username,
            "user_id": m_user_id,
            "bio": m_bio,
            "followers": int(m_followers),
            "following": int(m_following),
            "posts": int(m_posts),
            "location": m_location,
            "join_date": m_join,
            "verified": False,
            "profile_image": "",
            "banner": "",
            "source": "إدخال يدوي",
        }

    if not data:
        return

    render_profile_card(data, featured_image_b64=featured_b64)

    if gemini_key and GEMINI_AVAILABLE:
        st.markdown("---")
        btn_label = "🤖 تقرير استخباراتي مع تحليل الصورة" if featured_b64 else "🤖 توليد تقرير استخباراتي"
        if st.button(btn_label):
            with st.spinner("يحلل Gemini..."):
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel(gemini_model)

                    base_info = (
                        "الاسم: " + data.get("name", "") + "\n"
                        "@" + data.get("username", "") + "\n"
                        "User ID: " + data.get("user_id", "") + "\n"
                        "النبذة: " + data.get("bio", "") + "\n"
                        "المتابعون: " + format_number(data.get("followers", 0)) + "\n"
                        "يتابع: " + format_number(data.get("following", 0)) + "\n"
                        "التغريدات: " + format_number(data.get("posts", 0)) + "\n"
                        "الموقع: " + data.get("location", "") + "\n"
                        "تاريخ الانضمام: " + format_date(data.get("join_date", "")) + "\n"
                        "موثق: " + ("نعم" if data.get("verified") else "لا") + "\n"
                    )

                    if featured_b64:
                        prompt = (
                            "أنت محلل استخباراتي متخصص في شبكات التواصل.\n"
                            "حلّل الحساب التالي والصورة المرفقة:\n\n"
                            + base_info
                            + "\nاكتب تقريراً يشمل:\n"
                            "1. طبيعة الحساب وتوجهاته\n"
                            "2. مؤشرات النشاط والتأثير\n"
                            "3. تحليل الصورة المرفقة بالتفصيل\n"
                            "4. الملاحظات الاستخباراتية العامة\n"
                            "باللغة العربية."
                        )
                        image_part = {"mime_type": "image/jpeg", "data": featured_b64}
                        response = model.generate_content([prompt, image_part])
                    else:
                        prompt = (
                            "أنت محلل استخباراتي متخصص في شبكات التواصل.\n"
                            "حلّل الحساب التالي وقدّم تقريراً شاملاً:\n\n"
                            + base_info
                            + "\nاكتب تقريراً يشمل: طبيعة الحساب، مؤشرات النشاط، "
                            "التأثير المحتمل، والملاحظات الاستخباراتية. باللغة العربية."
                        )
                        response = model.generate_content(prompt)

                    st.markdown("#### 📊 التقرير الاستخباراتي")
                    st.markdown(response.text)
                except Exception as e:
                    handle_gemini_error(e)
    elif not GEMINI_AVAILABLE:
        st.info("ثبّت google-generativeai وأضف مفتاح Gemini لتفعيل التحليل الذكي.")


# ══════════════════════════════════════════════════════════════
# tweet_tab
# ══════════════════════════════════════════════════════════════
def tweet_tab(gemini_key, gemini_model):
    st.markdown("### 🐦 تحليل منشور (تغريدة)")

    col1, col2 = st.columns([3, 1])
    with col1:
        tweet_url = st.text_input(
            "رابط التغريدة",
            placeholder="https://x.com/user/status/123456789",
            label_visibility="collapsed",
        )
    with col2:
        tw_btn = st.button("🔍 جلب التغريدة", use_container_width=True)

    uploaded_img = st.file_uploader(
        "📷 أرفق صورة من التغريدة (اختياري)",
        type=["jpg", "jpeg", "png", "webp"],
        key="tweet_img_uploader",
    )

    tweet = None

    if tw_btn and tweet_url:
        tweet_id = extract_tweet_id(tweet_url)
        if not tweet_id:
            st.error("لم أتمكن من استخراج ID التغريدة. تحقق من الرابط.")
            return
        with st.spinner("جاري جلب التغريدة..."):
            tweet = fetch_tweet_data(tweet_id)
        if not tweet:
            st.error("فشل جلب التغريدة. تحقق من الرابط أو أن المنشور عام.")
            return

    if tweet:
        st.markdown("#### 📊 إحصاءات المنشور")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("❤️ إعجاب", format_number(tweet.get("likes", 0)))
        c2.metric("🔁 إعادة نشر", format_number(tweet.get("retweets", 0)))
        c3.metric("💬 رد", format_number(tweet.get("replies", 0)))
        c4.metric("👁 مشاهدة", format_number(tweet.get("views", 0)))

        st.markdown("#### 📝 نص المنشور")
        tweet_text = tweet.get("text", "")
        st.text_area(
            "نص المنشور",
            value=tweet_text,
            height=120,
            label_visibility="collapsed",
        )

        col_a, col_b = st.columns(2)
        author_name = tweet.get("author_name", "")
        author_user = tweet.get("author_username", "")
        tweet_date = format_date(tweet.get("date", ""))
        col_a.markdown(f"**الكاتب:** {author_name} (@{author_user})")
        col_b.markdown(f"**التاريخ:** {tweet_date}")

        media = tweet.get("media", [])
        if media:
            st.markdown("#### 🖼 وسائط المنشور")
            cols = st.columns(min(len(media), 3))
            for i, item in enumerate(media[:3]):
                media_url = item.get("url", item.get("thumbnail_url", ""))
                if media_url:
                    with cols[i]:
                        st.image(media_url, use_container_width=True)

    if uploaded_img and gemini_key and GEMINI_AVAILABLE:
        st.markdown("---")
        st.markdown("#### 🔎 تحليل الصورة")
        try:
            pil_img = Image.open(uploaded_img)
            img_b64 = pil_to_base64(pil_img, quality=92)

            if not img_b64:
                st.error("فشل تحويل الصورة.")
                return

            st.image(pil_img, caption="الصورة المرفوعة", use_container_width=True)

            if st.button("🤖 تحليل الصورة بـ Gemini"):
                with st.spinner("يحلل الصورة..."):
                    try:
                        genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel(gemini_model)
                        points = "\n".join(f"- {p}" for p in IMAGE_ANALYSIS_POINTS)
                        prompt = (
                            "أنت خبير OSINT متخصص في تحليل الصور من منصات التواصل.\n"
                            "حلّل هذه الصورة بشكل تفصيلي وركّز على:\n"
                            + points
                            + "\nقدّم كل نقطة في فقرة مستقلة. اكتب بالعربية."
                        )
                        image_part = {"mime_type": "image/jpeg", "data": img_b64}
                        response = model.generate_content([prompt, image_part])
                        st.markdown("#### 🔍 نتائج تحليل الصورة")
                        st.markdown(response.text)
                    except Exception as e:
                        handle_gemini_error(e)
        except Exception as e:
            st.error(f"خطأ في معالجة الصورة: {e}")

    elif uploaded_img and not GEMINI_AVAILABLE:
        st.info("ثبّت google-generativeai وأضف مفتاح API لتحليل الصورة.")


# ══════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════
def main():
    gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug = setup_sidebar()

    st.markdown("""
    <div class="main-header">
      <h1>🔍 محلل حسابات X</h1>
      <p>أداة تحليل استخباراتي لحسابات ومنشورات منصة X • v9.2</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 تحليل حساب", "🐦 تحليل منشور"])

    with tab1:
        account_tab(gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug)

    with tab2:
        tweet_tab(gemini_key, gemini_model)


if __name__ == "__main__":
    main()
