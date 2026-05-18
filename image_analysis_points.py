# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.9
# يعتمد على twikit (لا يحتاج Twitter Developer API)

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
import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

# ── Gemini (اختياري) ──────────────────────────────────────────
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ── twikit (اختياري) ──────────────────────────────────────────
try:
    from twikit import Client as TwikitClient
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False

# ══════════════════════════════════════════════════════════════
#  CSS — تصميم داكن + عربي
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
  .main-header p  { color: #8b949e; margin: 4px 0 0; }
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
  .profile-card .bio-text { color: #c9d1d9; font-size: 0.95rem; margin: 12px 0; line-height: 1.7; }
  .stat-box {
      background: #0d1117; border: 1px solid #30363d; border-radius: 10px;
      padding: 12px; text-align: center;
  }
  .stat-box .stat-num { font-size: 1.3rem; font-weight: 700; color: #58a6ff; }
  .stat-box .stat-lbl { font-size: 0.78rem; color: #8b949e; }
  .meta-badge {
      display: inline-block; background: #1f2937; border: 1px solid #374151;
      border-radius: 20px; padding: 4px 12px; font-size: 0.82rem; color: #9ca3af;
      margin: 3px;
  }
  .source-tag {
      background: #0d3349; border: 1px solid #1d6896; border-radius: 6px;
      padding: 3px 10px; font-size: 0.78rem; color: #58a6ff;
  }
  .uid-box {
      background: #0d1117; border: 1px dashed #444; border-radius: 8px;
      padding: 8px 14px; font-family: monospace; font-size: 0.9rem;
      color: #f0e68c; direction: ltr; text-align: left;
  }
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
#  ثوابت
# ══════════════════════════════════════════════════════════════
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

NITTER_MIRRORS = [
    "https://nitter.kareem.one",
    "https://nitter.net",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.poast.org",
    "https://nitter.space",
    "https://lightbrd.com",
    "https://nuku.trabun.org",
]

FXTWITTER_API  = "https://api.fxtwitter.com"
COOKIES_FILE   = "/tmp/twikit_cookies.json"

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
#  دوال مساعدة
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
    # استخراج من رابط x.com أو twitter.com
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_.]{1,50})(?:\?|/|$)', text)
    if m:
        return m.group(1).rstrip("/")
    # @ prefix
    if text.startswith("@"):
        return text[1:].split()[0].split("?")[0]
    # اسم مباشر
    if re.match(r'^[A-Za-z0-9_.]{1,50}$', text):
        return text
    # آخر جزء من المسار
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
        for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ",
                    "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
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
            img = Image.open(BytesIO(r.content)).convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    return ""

# ══════════════════════════════════════════════════════════════
#  جلب البيانات — twikit
# ══════════════════════════════════════════════════════════════
def _run_async(coro):
    """تشغيل coroutine بشكل متزامن داخل Streamlit."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def _twikit_fetch(username: str, tw_user: str, tw_email: str, tw_pass: str) -> Optional[Dict]:
    """يسجل دخول twikit ويجلب بيانات المستخدم."""
    if not TWIKIT_AVAILABLE:
        return None
    try:
        client = TwikitClient("en-US")
        # تحميل الكوكيز المحفوظة
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
            "name":          clean_text(user.name or ""),
            "username":      user.screen_name or username,
            "user_id":       str(user.id or ""),
            "bio":           clean_text(user.description or ""),
            "followers":     user.followers_count or 0,
            "following":     user.following_count or 0,
            "posts":         user.statuses_count or 0,
            "location":      clean_text(user.location or ""),
            "join_date":     str(user.created_at or ""),
            "verified":      bool(user.verified or user.is_blue_verified),
            "profile_image": (user.profile_image_url_https or "").replace("_normal", ""),
            "banner":        user.profile_banner_url or "",
            "source":        "twikit",
        }
    except Exception as e:
        err = str(e)
        # الكوكيز منتهية — احذفها وأعد المحاولة
        if "cookies" in err.lower() or "auth" in err.lower() or "login" in err.lower():
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
        return None

def fetch_via_twikit(username: str, tw_user: str, tw_email: str, tw_pass: str) -> Optional[Dict]:
    if not tw_user or not tw_pass:
        return None
    return _run_async(_twikit_fetch(username, tw_user, tw_email, tw_pass))

# ══════════════════════════════════════════════════════════════
#  جلب البيانات — Nitter
# ══════════════════════════════════════════════════════════════
def fetch_via_nitter(username: str, debug: bool = False) -> Optional[Dict]:
    headers = {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept-Language": "ar,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            code = r.status_code
            if debug:
                st.caption(f"  {mirror} → HTTP {code}")
            if code != 200:
                continue
            # كشف Anubis / CAPTCHA / Not Found
            page_lower = r.text.lower()
            if any(k in page_lower for k in ["proof-of-work", "anubis", "challenge", "captcha", "user not found"]):
                if debug:
                    st.caption(f"  ⚠ {mirror} يحظر الوصول (bot protection)")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # استخراج الاسم
            name = ""
            for sel in [".profile-card-fullname", ".fullname", "h1.fullname", ".user-fullname"]:
                el = soup.select_one(sel)
                if el:
                    name = clean_text(el.text)
                    break
            if not name:
                continue

            # استخراج الإحصاءات
            def get_stat(label_text):
                for li in soup.select(".profile-stat"):
                    lbl = li.select_one(".profile-stat-header, .stat-header")
                    num = li.select_one(".profile-stat-num")
                    if lbl and num and label_text.lower() in lbl.text.lower():
                        return clean_text(num.text).replace(",", "")
                return "0"

            followers = get_stat("Followers")
            following = get_stat("Following")
            posts     = get_stat("Tweets")

            # باقي الحقول
            bio_el  = soup.select_one(".profile-bio p, .bio")
            bio     = clean_text(bio_el.text) if bio_el else ""

            loc_el  = soup.select_one(".profile-location span:last-child")
            loc     = clean_text(loc_el.text) if loc_el else ""

            join_el = soup.select_one(".profile-joindate span:last-child")
            join    = clean_text(join_el.text) if join_el else ""

            img_el  = soup.select_one(".profile-card-avatar img, .avatar img")
            img_url = ""
            if img_el:
                src = img_el.get("src", "")
                if src.startswith("/"):
                    src = mirror + src
                img_url = src

            verified = bool(soup.select_one(".verified-icon, .verified"))

            # محاولة جلب user_id من RSS
            user_id = ""
            try:
                rss_url = f"{mirror}/{username}/rss"
                rss_r   = requests.get(rss_url, headers=headers, timeout=8)
                uid_m   = re.search(r'<uri>.*?/(\d{5,})</uri>', rss_r.text)
                if uid_m:
                    user_id = uid_m.group(1)
            except Exception:
                pass

            return {
                "name":          name,
                "username":      username,
                "user_id":       user_id,
                "bio":           bio,
                "followers":     int(followers) if followers.isdigit() else 0,
                "following":     int(following) if following.isdigit() else 0,
                "posts":         int(posts)     if posts.isdigit()     else 0,
                "location":      loc,
                "join_date":     join,
                "verified":      verified,
                "profile_image": img_url,
                "banner":        "",
                "source":        f"Nitter ({mirror})",
            }
        except Exception as e:
            if debug:
                st.caption(f"  ❌ {mirror} خطأ: {str(e)[:60]}")
            continue
    return None

# ══════════════════════════════════════════════════════════════
#  جلب بيانات التغريدة — FxTwitter
# ══════════════════════════════════════════════════════════════
def fetch_tweet_data(tweet_id: str) -> Optional[Dict]:
    try:
        url = f"{FXTWITTER_API}/status/{tweet_id}"
        r   = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=15)
        if r.status_code != 200:
            return None
        tweet = r.json().get("tweet", {})
        if not tweet:
            return None
        author = tweet.get("author", {})
        return {
            "text":       clean_text(tweet.get("text", "")),
            "likes":      tweet.get("likes",    0),
            "retweets":   tweet.get("retweets", 0),
            "replies":    tweet.get("replies",  0),
            "views":      tweet.get("views",    0),
            "date":       tweet.get("created_at", ""),
            "lang":       tweet.get("lang", ""),
            "url":        tweet.get("url", ""),
            "author_name":     clean_text(author.get("name", "")),
            "author_username": author.get("screen_name", ""),
            "author_avatar":   author.get("avatar_url", ""),
            "media":      tweet.get("media", {}).get("all", []),
        }
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية لجلب بيانات المستخدم
# ══════════════════════════════════════════════════════════════
def fetch_user_data(username: str, tw_user: str = "", tw_email: str = "",
                    tw_pass: str = "", debug: bool = False) -> Optional[Dict]:

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
#  رندر بطاقة الملف الشخصي
# ══════════════════════════════════════════════════════════════
def render_profile_card(data: Dict):
    name     = html_module.escape(data.get("name", ""))
    uname    = html_module.escape(data.get("username", ""))
    bio      = html_module.escape(data.get("bio", ""))
    loc      = html_module.escape(data.get("location", ""))
    join     = html_module.escape(format_date(data.get("join_date", "")))
    uid      = html_module.escape(str(data.get("user_id", "")))
    source   = html_module.escape(data.get("source", ""))
    verified = data.get("verified", False)

    followers = format_number(data.get("followers", 0))
    following = format_number(data.get("following", 0))
    posts     = format_number(data.get("posts", 0))

    verified_badge = ' <span style="color:#1d9bf0" title="حساب موثق">✓</span>' if verified else ""

    # صورة البروفايل
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
            '<div style="font-size:0.8rem;color:#8b949e;margin-bottom:4px">🆔 معرّف المستخدم (User ID)</div>'
            '<div class="uid-box">' + uid + '</div>'
            '</div>'
        )

    bio_html = ""
    if bio:
        bio_html = '<div class="bio-text">' + bio + '</div>'

    meta_parts = []
    if loc:
        meta_parts.append("📍 " + loc)
    if join:
        meta_parts.append("📅 انضم في " + join)
    if source:
        meta_parts.append('<span class="source-tag">' + source + '</span>')

    meta_html = "".join('<span class="meta-badge">' + p + '</span>' for p in meta_parts)

    card = (
        '<div class="profile-card" dir="rtl">'
        '<div style="display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap">'
        '<div>' + avatar_html + '</div>'
        '<div style="flex:1;min-width:200px">'
        '<div class="display-name">' + name + verified_badge + '</div>'
        '<div class="username-tag">@' + uname + '</div>'
        + bio_html +
        '<div style="margin-top:8px">' + meta_html + '</div>'
        + uid_html +
        '</div>'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px">'
        '<div class="stat-box"><div class="stat-num">' + followers + '</div><div class="stat-lbl">متابع</div></div>'
        '<div class="stat-box"><div class="stat-num">' + following + '</div><div class="stat-lbl">يتابع</div></div>'
        '<div class="stat-box"><div class="stat-num">' + posts     + '</div><div class="stat-lbl">تغريدة</div></div>'
        '</div>'
        '</div>'
    )
    st.markdown(card, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  معالجة أخطاء Gemini
# ══════════════════════════════════════════════════════════════
def handle_gemini_error(e: Exception):
    err = str(e).lower()
    if "429" in err or "quota" in err:
        st.error("⚠ تجاوزت حصة Gemini — انتظر قليلاً ثم أعد المحاولة.")
    elif "api_key" in err or "api key" in err or "invalid" in err:
        st.error("🔑 مفتاح Gemini غير صالح. تحقق منه في الشريط الجانبي.")
    elif "not found" in err or "404" in err:
        st.error("❌ النموذج غير متاح. جرّب gemini-2.0-flash-lite أو gemini-1.5-pro.")
    else:
        st.error(f"خطأ Gemini: {str(e)[:200]}")

# ══════════════════════════════════════════════════════════════
#  الشريط الجانبي
# ══════════════════════════════════════════════════════════════
def setup_sidebar():
    st.sidebar.markdown("## ⚙️ الإعدادات")

    # Gemini
    st.sidebar.markdown("### 🤖 Gemini AI")
    gemini_key = st.sidebar.text_input(
        "مفتاح Gemini API",
        type="password",
        placeholder="AIza...",
        help="احصل على مفتاحك من https://aistudio.google.com/apikey"
    )
    gemini_model = st.sidebar.selectbox(
        "النموذج",
        ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0
    )

    # بيانات حساب X
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🐦 حساب X (لـ twikit)")
    use_twikit = st.sidebar.checkbox("تفعيل twikit", value=TWIKIT_AVAILABLE)

    tw_user  = ""
    tw_email = ""
    tw_pass  = ""

    if use_twikit and TWIKIT_AVAILABLE:
        tw_user  = st.sidebar.text_input("اسم المستخدم (@)", placeholder="your_account")
        tw_email = st.sidebar.text_input("البريد الإلكتروني", placeholder="your@email.com")
        tw_pass  = st.sidebar.text_input("كلمة المرور", type="password")

        if st.sidebar.button("🗑 حذف الكوكيز المحفوظة"):
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
                st.sidebar.success("تم حذف الكوكيز")
            else:
                st.sidebar.info("لا يوجد كوكيز محفوظة")

        st.sidebar.info(
            "💡 يُنصح باستخدام حساب ثانوي فقط للقراءة.\n"
            "لن يتم نشر أي شيء من حسابك."
        )
    elif use_twikit and not TWIKIT_AVAILABLE:
        st.sidebar.warning("twikit غير مثبت.\nأضف `twikit>=2.0.0` في requirements.txt")

    # وضع التشخيص
    st.sidebar.markdown("---")
    debug = st.sidebar.checkbox("🔬 وضع التشخيص", value=False)

    return gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug

# ══════════════════════════════════════════════════════════════
#  تبويب تحليل الحساب
# ══════════════════════════════════════════════════════════════
def account_tab(gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug):
    st.markdown("### 👤 تحليل حساب X")

    col1, col2 = st.columns([3, 1])
    with col1:
        raw_input = st.text_input(
            "رابط الحساب أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username  أو  username",
            label_visibility="collapsed"
        )
    with col2:
        fetch_btn = st.button("🔍 جلب البيانات", use_container_width=True)

    # إدخال يدوي
    with st.expander("✏️ إدخال البيانات يدوياً (دائماً يعمل)"):
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_name     = st.text_input("الاسم")
            m_username = st.text_input("اسم المستخدم")
            m_user_id  = st.text_input("User ID")
            m_bio      = st.text_area("النبذة", height=80)
        with m_col2:
            m_followers = st.number_input("المتابعون",  min_value=0, step=1)
            m_following = st.number_input("يتابع",      min_value=0, step=1)
            m_posts     = st.number_input("التغريدات",  min_value=0, step=1)
            m_location  = st.text_input("الموقع")
            m_join      = st.text_input("تاريخ الانضمام (dd/mm/yyyy)")
        manual_btn = st.button("💾 استخدام البيانات اليدوية", use_container_width=True)

    data = None

    # جلب تلقائي
    if fetch_btn and raw_input:
        username = extract_username(raw_input)
        if not username:
            st.error("❌ تعذّر استخراج اسم المستخدم. تحقق من الرابط.")
            return

        st.info(f"جاري جلب بيانات **@{username}** ...")
        if debug:
            st.markdown("**📋 سجل التشخيص:**")

        with st.spinner("يتصل بالمصادر..."):
            data = fetch_user_data(username, tw_user, tw_email, tw_pass, debug)

        if not data:
            st.error(f"❌ فشل جلب بيانات **@{username}** من جميع المصادر.")
            st.warning(
                "**الأسباب المحتملة:**\n"
                "- الحساب خاص أو موقوف\n"
                "- اسم المستخدم غير صحيح\n"
                "- Streamlit Cloud محظور من Twitter\n\n"
                "**الحلول:**\n"
                "1. أدخل بيانات حساب X في الشريط الجانبي لاستخدام twikit\n"
                "2. استخدم الإدخال اليدوي أدناه ↓"
            )
            return

    # بيانات يدوية
    if manual_btn and m_name:
        data = {
            "name":          m_name,
            "username":      m_username,
            "user_id":       m_user_id,
            "bio":           m_bio,
            "followers":     int(m_followers),
            "following":     int(m_following),
            "posts":         int(m_posts),
            "location":      m_location,
            "join_date":     m_join,
            "verified":      False,
            "profile_image": "",
            "banner":        "",
            "source":        "إدخال يدوي",
        }

    if not data:
        return

    # عرض البطاقة
    render_profile_card(data)

    # تحليل Gemini
    if gemini_key and GEMINI_AVAILABLE:
        st.markdown("---")
        if st.button("🤖 توليد تقرير استخباراتي بـ Gemini"):
            with st.spinner("يحلل Gemini..."):
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel(gemini_model)
                    prompt = (
                        f"أنت محلل استخباراتي متخصص في شبكات التواصل الاجتماعي.\n"
                        f"حلّل الحساب التالي على منصة X وقدّم تقريراً شاملاً:\n\n"
                        f"الاسم: {data.get('name','')}\n"
                        f"@{data.get('username','')}\n"
                        f"User ID: {data.get('user_id','')}\n"
                        f"النبذة: {data.get('bio','')}\n"
                        f"المتابعون: {format_number(data.get('followers',0))}\n"
                        f"يتابع: {format_number(data.get('following',0))}\n"
                        f"التغريدات: {format_number(data.get('posts',0))}\n"
                        f"الموقع: {data.get('location','')}\n"
                        f"تاريخ الانضمام: {format_date(data.get('join_date',''))}\n"
                        f"موثق: {'نعم' if data.get('verified') else 'لا'}\n\n"
                        f"اكتب تقريراً يشمل: طبيعة الحساب، مؤشرات النشاط، "
                        f"التأثير المحتمل، والملاحظات الاستخباراتية. باللغة العربية."
                    )
                    response = model.generate_content(prompt)
                    st.markdown("#### 📊 التقرير الاستخباراتي")
                    st.markdown(response.text)
                except Exception as e:
                    handle_gemini_error(e)
    elif not GEMINI_AVAILABLE:
        st.info("💡 ثبّت `google-generativeai` وأضف مفتاح Gemini لتفعيل التحليل الذكي.")

# ══════════════════════════════════════════════════════════════
#  تبويب تحليل التغريدة
# ══════════════════════════════════════════════════════════════
def tweet_tab(gemini_key, gemini_model):
    st.markdown("### 🐦 تحليل منشور (تغريدة)")

    col1, col2 = st.columns([3, 1])
    with col1:
        tweet_url = st.text_input(
            "رابط التغريدة",
            placeholder="https://x.com/user/status/123456789",
            label_visibility="collapsed"
        )
    with col2:
        tw_btn = st.button("🔍 جلب التغريدة", use_container_width=True)

    uploaded_img = st.file_uploader(
        "📷 أرفق صورة من التغريدة (اختياري)",
        type=["jpg", "jpeg", "png", "webp"]
    )

    tweet = None
    if tw_btn and tweet_url:
        tweet_id = extract_tweet_id(tweet_url)
        if not tweet_id:
            st.error("❌ لم أتمكن من استخراج ID التغريدة. تحقق من الرابط.")
            return
        with st.spinner("جاري جلب التغريدة..."):
            tweet = fetch_tweet_data(tweet_id)
        if not tweet:
            st.error("❌ فشل جلب التغريدة. تحقق من الرابط أو أن المنشور عام.")
            return

    if tweet:
        # إحصاءات
        st.markdown("#### 📊 إحصاءات المنشور")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("❤️ إعجاب",    format_number(tweet.get("likes",    0)))
        c2.metric("🔁 إعادة نشر", format_number(tweet.get("retweets", 0)))
        c3.metric("💬 رد",        format_number(tweet.get("replies",  0)))
        c4.metric("👁 مشاهدة",    format_number(tweet.get("views",    0)))

        st.markdown("#### 📝 نص المنشور")
        st.text_area("", value=tweet.get("text", ""), height=120, label_visibility="collapsed")

        col_a, col_b = st.columns(2)
        col_a.markdown(f"**الكاتب:** {tweet.get('author_name','')} (@{tweet.get('author_username','')})")
        col_b.markdown(f"**التاريخ:** {format_date(tweet.get('date',''))}")

        # وسائط
        media = tweet.get("media", [])
        if media:
            st.markdown("#### 🖼 وسائط المنشور")
            cols = st.columns(min(len(media), 3))
            for i, item in enumerate(media[:3]):
                url = item.get("url", item.get("thumbnail_url", ""))
                if url:
                    with cols[i]:
                        st.image(url, use_container_width=True)

    # تحليل الصورة
    if uploaded_img and gemini_key and GEMINI_AVAILABLE:
        st.markdown("---")
        st.markdown("#### 🔎 تحليل الصورة")
        img     = Image.open(uploaded_img)
        buf     = BytesIO()
        img.save(buf, format="JPEG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        st.image(img, caption="الصورة المرفوعة", use_container_width=True)

        if st.button("🤖 تحليل الصورة بـ Gemini"):
            with st.spinner("يحلل الصورة..."):
                try:
                    genai.configure(api_key=gemini_key)
                    model   = genai.GenerativeModel(gemini_model)
                    points  = "\n".join(f"- {p}" for p in IMAGE_ANALYSIS_POINTS)
                    prompt  = (
                        f"أنت خبير OSINT متخصص في تحليل الصور من منصات التواصل.\n"
                        f"حلّل هذه الصورة من تغريدة بشكل تفصيلي، وركّز على:\n{points}\n\n"
                        f"قدّم كل نقطة في فقرة مستقلة. اكتب بالعربية."
                    )
                    image_part = {
                        "mime_type": "image/jpeg",
                        "data":      img_b64
                    }
                    response = model.generate_content([prompt, image_part])
                    st.markdown("#### 🔍 نتائج تحليل الصورة")
                    st.markdown(response.text)
                except Exception as e:
                    handle_gemini_error(e)

    elif uploaded_img and not GEMINI_AVAILABLE:
        st.info("💡 ثبّت `google-generativeai` وأضف مفتاح API لتحليل الصورة.")

# ══════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════
def main():
    gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug = setup_sidebar()

    # رأس الصفحة
    st.markdown("""
    <div class="main-header">
      <h1>🔍 محلل حسابات X</h1>
      <p>أداة تحليل استخباراتي لحسابات ومنشورات منصة X (تويتر) • v8.9</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 تحليل حساب", "🐦 تحليل منشور"])

    with tab1:
        account_tab(gemini_key, gemini_model, tw_user, tw_email, tw_pass, debug)

    with tab2:
        tweet_tab(gemini_key, gemini_model)

if __name__ == "__main__":
    main()
