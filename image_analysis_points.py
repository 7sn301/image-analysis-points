# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.9 — النسخة النهائية
# المصادر: twikit (حساب Twitter عادي) + Nitter مع كشف Anubis

import streamlit as st

st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

import requests
import re
import random
import base64
import html as html_module
import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
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

# ══════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
* { font-family: 'Cairo', sans-serif !important; }
.main, .stApp { background: #0a0a0a; color: #e0e0e0; }

.profile-card {
    background: linear-gradient(145deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
    border: 1px solid #2d2d5e; border-radius: 20px; padding: 32px;
    margin: 20px 0; box-shadow: 0 8px 32px rgba(0,100,255,0.15);
}
.profile-header { display:flex; align-items:center; gap:20px; margin-bottom:20px; }
.profile-avatar {
    width:120px; height:120px; border-radius:50%;
    border:3px solid #1da1f2; object-fit:cover;
}
.avatar-placeholder {
    width:120px; height:120px; border-radius:50%;
    background:linear-gradient(135deg,#1da1f2,#0d47a1);
    display:flex; align-items:center; justify-content:center;
    font-size:48px; border:3px solid #1da1f2;
}
.profile-name  { font-size:1.8em; font-weight:900; color:#fff; margin-bottom:4px; }
.profile-username { font-size:1.1em; color:#1da1f2; margin-bottom:8px; }
.user-id-badge {
    background:rgba(29,161,242,0.15); border:1px solid #1da1f2;
    border-radius:8px; padding:3px 10px; font-size:.85em;
    color:#7ec8e3; margin-top:4px; display:inline-block;
}
.source-badge {
    background:rgba(29,161,242,0.2); border:1px solid rgba(29,161,242,0.5);
    border-radius:20px; padding:3px 12px; font-size:.8em; color:#7ec8e3;
}
.verified-badge { color:#1da1f2; font-size:1.1em; margin-right:6px; }
.stats-row { display:flex; gap:16px; margin:20px 0; flex-wrap:wrap; }
.stat-item {
    background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1);
    border-radius:12px; padding:14px 22px; text-align:center; flex:1; min-width:90px;
}
.stat-value { font-size:1.6em; font-weight:700; color:#1da1f2; }
.stat-label  { font-size:.8em; color:#888; margin-top:4px; }
.bio-section {
    background:rgba(255,255,255,.05); border-right:3px solid #1da1f2;
    border-radius:8px; padding:14px 18px; margin:14px 0;
    color:#e0e0e0; font-size:1em; line-height:1.7;
}
.meta-row  { display:flex; flex-wrap:wrap; gap:14px; color:#aaa; font-size:.9em; margin-top:12px; }
.meta-item { display:flex; align-items:center; gap:5px; }

.app-header   { text-align:center; padding:30px 0 10px; }
.app-title {
    font-size:2.8em; font-weight:900;
    background:linear-gradient(135deg,#1da1f2,#7ec8e3);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.app-subtitle { color:#888; font-size:1em; margin-top:6px; }

.metric-card {
    background:linear-gradient(145deg,#1a1a2e,#16213e);
    border:1px solid #2d2d5e; border-radius:12px; padding:18px; text-align:center;
}
.metric-value { font-size:1.8em; font-weight:700; color:#1da1f2; }
.metric-label { font-size:.85em; color:#888; margin-top:4px; }

.stTabs [data-baseweb="tab"] { font-size:1.1em !important; font-weight:600 !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
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

# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════
def clean_text(txt: str) -> str:
    if not txt: return ""
    txt = re.sub(r'<[^>]+>', '', str(txt))
    txt = html_module.unescape(txt)
    return txt.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").strip()


def extract_username(text: str) -> str:
    if not text: return ""
    text = text.strip()
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_.]{1,50})(?:\?|/|$)', text)
    if m:
        skip = {"intent","search","home","explore","notifications","messages","i","settings"}
        if m.group(1).lower() not in skip:
            return m.group(1)
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
    if not text: return ""
    m = re.search(r'status/(\d+)', text)
    if m: return m.group(1)
    m = re.search(r'\b(\d{15,20})\b', text)
    return m.group(1) if m else ""


def format_number(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(n)


def format_date(date_str: str) -> str:
    if not date_str or date_str == "غير متوفر":
        return date_str or "غير متوفر"
    for fmt in ["%a %b %d %H:%M:%S %z %Y",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d"]:
        try: return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except: pass
    return date_str[:10] if len(date_str) >= 10 else date_str


def image_to_base64(url: str) -> str:
    try:
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": random.choice(USER_AGENTS)})
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except: pass
    return ""

# ══════════════════════════════════════════════
# TWIKIT  —  حساب Twitter عادي (بدون Developer API)
# ══════════════════════════════════════════════
def run_async(coro):
    """تشغيل coroutine داخل Streamlit بأمان"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=45)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _twikit_fetch(username_target: str,
                        tw_user: str, tw_email: str, tw_password: str) -> Optional[Dict]:
    client = TwikitClient("en-US")

    # استخدام الكوكيز المحفوظة إن وُجدت
    if os.path.exists(COOKIES_FILE):
        try:
            client.load_cookies(COOKIES_FILE)
        except Exception:
            os.remove(COOKIES_FILE)

    if not os.path.exists(COOKIES_FILE):
        await client.login(
            auth_info_1=tw_user,
            auth_info_2=tw_email,
            password=tw_password,
        )
        client.save_cookies(COOKIES_FILE)

    user = await client.get_user_by_screen_name(username_target)
    if not user:
        return None

    return {
        "name":          getattr(user, "name",                   ""),
        "username":      getattr(user, "screen_name",            username_target),
        "user_id":       str(getattr(user, "id",                 "")),
        "bio":           getattr(user, "description",            "") or "",
        "followers":     getattr(user, "followers_count",        0),
        "following":     getattr(user, "friends_count",          0),
        "posts":         getattr(user, "statuses_count",         0),
        "location":      getattr(user, "location",               "") or "",
        "join_date":     str(getattr(user, "created_at",         "")),
        "verified":      getattr(user, "verified",               False)
                      or getattr(user, "is_blue_verified",       False),
        "profile_image": (getattr(user, "profile_image_url_https","") or "").replace("_normal",""),
        "banner":        getattr(user, "profile_banner_url",     "") or "",
        "source":        "twikit (حساب Twitter)",
    }


def fetch_via_twikit(username: str,
                     tw_user: str, tw_email: str, tw_password: str) -> Optional[Dict]:
    if not TWIKIT_AVAILABLE or not all([tw_user, tw_email, tw_password]):
        return None
    try:
        return run_async(_twikit_fetch(username, tw_user, tw_email, tw_password))
    except Exception as e:
        # حذف الكوكيز إذا انتهت صلاحيتها
        if os.path.exists(COOKIES_FILE):
            try: os.remove(COOKIES_FILE)
            except: pass
        return None

# ══════════════════════════════════════════════
# NITTER  —  مع كشف Anubis + selectors محسّنة
# ══════════════════════════════════════════════
def fetch_via_nitter(username: str, debug: bool = False) -> Optional[Dict]:
    browser_headers = {
        "User-Agent":               random.choice(USER_AGENTS),
        "Accept":                   "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":          "en-US,en;q=0.5",
        "Accept-Encoding":          "gzip, deflate, br",
        "DNT":                      "1",
        "Connection":               "keep-alive",
        "Upgrade-Insecure-Requests":"1",
    }

    for mirror in NITTER_MIRRORS:
        try:
            r = requests.get(f"{mirror}/{username}",
                             headers=browser_headers,
                             timeout=12,
                             allow_redirects=True)

            if debug:
                st.caption(f"  ↳ {mirror} → HTTP {r.status_code}")

            if r.status_code != 200:
                continue

            # ── كشف Anubis (PoW) ──
            if ("Anubis" in r.text
                    or "proof-of-work" in r.text.lower()
                    or r.text.strip().startswith("Loading...")):
                if debug:
                    st.caption(f"  ↳ {mirror} → 🛡️ Anubis PoW — محمي ضد السكريبينغ")
                continue

            # ── صفحة فارغة / bot detection ──
            if len(r.text) < 500:
                if debug:
                    st.caption(f"  ↳ {mirror} → ⚠️ صفحة فارغة")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # ── كشف "user not found" ──
            if (soup.select_one(".error-panel")
                    or "User not found"      in r.text
                    or "user-not-found"      in r.text
                    or "No user found"       in r.text):
                if debug:
                    st.caption(f"  ↳ {mirror} → ❌ الحساب غير موجود")
                return None   # لا فائدة من تجربة مرايا أخرى

            # ── الاسم الكامل ──
            name = ""
            for sel in [".profile-card-fullname",
                        "a.profile-card-fullname",
                        ".fullname",
                        "[class*='fullname']"]:
                tag = soup.select_one(sel)
                if tag:
                    name = tag.get_text(strip=True)
                    break

            if not name:
                if debug:
                    st.caption(f"  ↳ {mirror} → ⚠️ HTTP 200 لكن لا profile-card")
                continue

            # ── الإحصائيات بثلاث طرق fallback ──
            def get_stat(stat_class: str) -> str:
                # طريقة 1: li.followers .profile-stat-num
                el = soup.select_one(f"li.{stat_class} .profile-stat-num")
                if el:
                    return el.get_text(strip=True).replace(",","").replace(".","")
                # طريقة 2: header ثم sibling نصي
                for h in soup.select(".profile-stat-header"):
                    if stat_class.rstrip("s").lower() in h.get_text(strip=True).lower():
                        sib = h.find_next_sibling()
                        if sib:
                            return sib.get_text(strip=True).replace(",","")
                # طريقة 3: data-stat attribute
                el2 = soup.select_one(f"[data-stat='{stat_class}']")
                if el2:
                    return el2.get_text(strip=True).replace(",","")
                return "0"

            # ── صورة البروفايل ──
            avatar = ""
            for sel in [".profile-card-avatar img", ".avatar img", "img.avatar"]:
                at = soup.select_one(sel)
                if at:
                    src = at.get("src","")
                    avatar = mirror + src if src.startswith("/") else src
                    break

            # ── User ID من RSS ──
            user_id = ""
            try:
                rr = requests.get(f"{mirror}/{username}/rss",
                                  headers={"User-Agent": random.choice(USER_AGENTS)},
                                  timeout=8)
                m = re.search(r'user_id=(\d+)', rr.text)
                if m:
                    user_id = m.group(1)
            except Exception:
                pass

            # ── حقول أخرى ──
            uname_tag = soup.select_one(".profile-card-username, a.username")
            bio_tag   = soup.select_one(".profile-bio, .bio")
            loc_tag   = soup.select_one(".profile-location, .location")
            join_tag  = soup.select_one(".profile-joindate, .joindate, [title*='Joined']")

            return {
                "name":          name,
                "username":      uname_tag.get_text(strip=True).lstrip("@")
                                 if uname_tag else username,
                "user_id":       user_id,
                "bio":           bio_tag.get_text(separator=" ",strip=True) if bio_tag else "",
                "followers":     get_stat("followers"),
                "following":     get_stat("following"),
                "posts":         get_stat("posts") or get_stat("tweets"),
                "location":      loc_tag.get_text(strip=True)  if loc_tag  else "",
                "join_date":     join_tag.get_text(strip=True) if join_tag else "",
                "verified":      bool(soup.select_one(".verified-icon, .icon-ok-circled")),
                "profile_image": avatar,
                "banner":        "",
                "source":        f"Nitter ({mirror})",
            }

        except requests.exceptions.ConnectionError:
            if debug:
                st.caption(f"  ↳ {mirror} → 🔌 Connection aborted")
            continue
        except Exception as e:
            if debug:
                st.caption(f"  ↳ {mirror} → ❌ {str(e)[:50]}")
            continue

    return None

# ══════════════════════════════════════════════
# FETCH TWEET  —  FxTwitter
# ══════════════════════════════════════════════
def fetch_tweet_data(tweet_id: str) -> Optional[Dict]:
    try:
        r = requests.get(
            f"{FXTWITTER_API}/status/{tweet_id}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=15,
        )
        if r.status_code != 200: return None
        data  = r.json()
        tweet = data.get("tweet") or data.get("data",{}).get("tweet",{})
        if not tweet: return None
        author = tweet.get("author") or {}
        return {
            "id":               tweet_id,
            "text":             tweet.get("text",""),
            "likes":            tweet.get("likes",0),
            "retweets":         tweet.get("retweets",0),
            "replies":          tweet.get("replies",0),
            "views":            tweet.get("views",0),
            "date":             tweet.get("created_at",""),
            "url":              tweet.get("url", f"https://x.com/i/status/{tweet_id}"),
            "author_name":      author.get("name",""),
            "author_username":  author.get("screen_name",""),
            "author_id":        str(author.get("id", author.get("id_str",""))),
            "media":            tweet.get("media",{}).get("photos",[]),
            "source":           "FxTwitter",
        }
    except: return None

# ══════════════════════════════════════════════
# RENDER PROFILE CARD
# ══════════════════════════════════════════════
def render_profile_card(data: Dict):
    display_name     = clean_text(data.get("name",""))
    display_username = clean_text(data.get("username",""))
    user_id          = clean_text(data.get("user_id",""))
    display_source   = clean_text(data.get("source","Unknown"))

    # صورة البروفايل
    avatar_url = data.get("profile_image","")
    if avatar_url:
        b64 = image_to_base64(avatar_url)
        avatar_html = (
            '<img class="profile-avatar" src="data:image/jpeg;base64,' + b64 + '" />'
            if b64 else '<div class="avatar-placeholder">👤</div>'
        )
    else:
        avatar_html = '<div class="avatar-placeholder">👤</div>'

    verified_html = ' <span class="verified-badge">✔️</span>' if data.get("verified") else ""
    uid_html      = '<div class="user-id-badge">🆔 ' + user_id + '</div>' if user_id else ""

    # إحصائيات
    stats_html = (
        '<div class="stats-row">'
        '<div class="stat-item"><div class="stat-value">'
            + format_number(data.get("followers",0)) +
        '</div><div class="stat-label">متابِع</div></div>'
        '<div class="stat-item"><div class="stat-value">'
            + format_number(data.get("following",0)) +
        '</div><div class="stat-label">يتابع</div></div>'
        '<div class="stat-item"><div class="stat-value">'
            + format_number(data.get("posts",0)) +
        '</div><div class="stat-label">منشور</div></div>'
        '</div>'
    )

    # Bio
    bio_text = clean_text(data.get("bio",""))
    bio_html = '<div class="bio-section">📄 ' + bio_text + '</div>' if bio_text else ""

    # Meta
    meta_parts = []
    loc = clean_text(data.get("location",""))
    if loc: meta_parts.append("📍 " + loc)
    jd = format_date(str(data.get("join_date","")))
    if jd and jd != "غير متوفر": meta_parts.append("📅 انضم في: " + jd)
    meta_html = ""
    if meta_parts:
        meta_html = (
            '<div class="meta-row">'
            + "".join(['<span class="meta-item">' + p + '</span>' for p in meta_parts])
            + '</div>'
        )

    card_html = (
        '<div class="profile-card"><div class="profile-header">'
        + avatar_html
        + '<div>'
          '<div class="profile-name">'  + display_name     + verified_html + '</div>'
          '<div class="profile-username">@' + display_username + '</div>'
        + uid_html
        + '<span class="source-badge">📡 ' + display_source + '</span>'
          '</div></div>'
        + stats_html + bio_html + meta_html
        + '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)
    if user_id:
        st.text_input("🆔 معرّف الحساب — انقر للنسخ",
                      value=user_id, key="uid_" + display_username)

# ══════════════════════════════════════════════
# GEMINI ERROR HANDLER
# ══════════════════════════════════════════════
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

# ══════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════
def setup_sidebar():
    st.sidebar.markdown("## ⚙️ الإعدادات")

    # ── Gemini ──────────────────────────────
    st.sidebar.markdown("### 🤖 Gemini AI")
    api_key = st.sidebar.text_input(
        "🔑 مفتاح Gemini API", type="password", placeholder="AIzaSy...",
        help="احصل على مفتاح مجاني من https://aistudio.google.com/apikey"
    )
    model_name = st.sidebar.selectbox(
        "نموذج Gemini",
        ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
        index=0,
    )
    gemini_model = None
    if api_key and GEMINI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            gemini_model = genai.GenerativeModel(model_name)
            st.sidebar.success("✅ متصل بـ Gemini")
        except Exception as e:
            st.sidebar.error("❌ " + str(e)[:80])

    st.sidebar.markdown("---")

    # ── twikit — حساب Twitter عادي ──────────
    st.sidebar.markdown("### 🐦 حساب Twitter (للجلب التلقائي)")
    with st.sidebar.expander("🔐 بيانات حساب X العادي", expanded=True):
        st.markdown("""<small>
أدخل بيانات حسابك الشخصي على X.<br>
<b>لا تحتاج Developer API.</b><br>
تُحفظ الجلسة مؤقتاً فقط.
</small>""", unsafe_allow_html=True)

        tw_user     = st.text_input("اسم المستخدم",    placeholder="your_username",  key="tw_u")
        tw_email    = st.text_input("البريد الإلكتروني", placeholder="you@email.com", key="tw_e")
        tw_password = st.text_input("كلمة المرور",      type="password",              key="tw_p")

        if all([tw_user, tw_email, tw_password]):
            st.success("✅ سيُستخدَم twikit للجلب")
            # زر لمسح الكوكيز
            if st.button("🗑️ مسح الجلسة المحفوظة"):
                if os.path.exists(COOKIES_FILE):
                    os.remove(COOKIES_FILE)
                    st.info("تم مسح الجلسة.")
        else:
            st.info("💡 بدون بيانات: سيُجرَّب Nitter")

    debug_mode = st.sidebar.checkbox("🐛 وضع التشخيص", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
**📖 كيفية الاستخدام:**
1. أدخل بيانات حساب X
2. أضف مفتاح Gemini
3. أدخل رابط الحساب أو المنشور
4. اضغط جلب البيانات

**💡 بدون حساب Twitter:**
استخدم الإدخال اليدوي
""")

    return gemini_model, debug_mode, {
        "tw_user": tw_user, "tw_email": tw_email, "tw_password": tw_password
    }

# ══════════════════════════════════════════════
# ACCOUNT TAB
# ══════════════════════════════════════════════
def account_tab(model, debug: bool, creds: dict):
    st.markdown("### 👤 تحليل حساب X")

    has_creds = all([creds.get("tw_user"), creds.get("tw_email"), creds.get("tw_password")])

    if not has_creds:
        st.info("⚠️ لم تُدخل بيانات Twitter بعد. أدخلها في الشريط الجانبي، أو استخدم الإدخال اليدوي.")

    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input(
            "🔗 رابط أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username  أو  username"
        )
    with col2:
        fetch_btn = st.button("🔍 جلب البيانات", use_container_width=True)

    # ── الإدخال اليدوي ──────────────────────
    with st.expander("✏️ إدخال بيانات يدوي (يعمل دائماً بدون API)"):
        mc1, mc2 = st.columns(2)
        with mc1:
            manual_name      = st.text_input("الاسم الكامل")
            manual_followers = st.number_input("المتابعون",  min_value=0, value=0)
            manual_posts     = st.number_input("المنشورات",  min_value=0, value=0)
            manual_user_id   = st.text_input("معرّف الحساب (User ID)")
        with mc2:
            manual_bio       = st.text_area("النبذة التعريفية", height=100)
            manual_following = st.number_input("يتابع",      min_value=0, value=0)
            manual_location  = st.text_input("الموقع")
        use_manual = st.checkbox("✅ استخدم البيانات اليدوية")

    if not (fetch_btn and user_input):
        return

    username = extract_username(user_input)
    if not username:
        st.error("❌ لم يتم التعرف على اسم المستخدم.")
        return

    if debug:
        st.info(f"🔍 اسم المستخدم المستخرج: **`{username}`**")

    # ── جلب البيانات ─────────────────────────
    with st.spinner(f"⏳ جلب بيانات @{username}..."):

        if use_manual:
            data = {
                "name": manual_name or username, "username": username,
                "user_id": manual_user_id,       "bio": manual_bio,
                "followers": manual_followers,    "following": manual_following,
                "posts": manual_posts,            "location": manual_location,
                "join_date": "",                  "verified": False,
                "profile_image": "",              "banner": "",
                "source": "يدوي",
            }

        else:
            data = None

            # المصدر 1: twikit
            if has_creds and TWIKIT_AVAILABLE:
                if debug: st.caption("🔵 جاري المحاولة: twikit...")
                try:
                    data = fetch_via_twikit(username,
                                            creds["tw_user"],
                                            creds["tw_email"],
                                            creds["tw_password"])
                    if data  and debug: st.caption("✅ نجح: twikit")
                    if not data and debug: st.caption("❌ فشل: twikit")
                except Exception as e:
                    if debug: st.caption(f"❌ twikit خطأ: {str(e)[:70]}")

            # المصدر 2: Nitter
            if not data:
                if debug: st.caption("🟠 جاري المحاولة: Nitter mirrors...")
                data = fetch_via_nitter(username, debug=debug)
                if data  and debug: st.caption("✅ نجح: Nitter")
                if not data and debug: st.caption("❌ فشل: جميع مرايا Nitter")

    # ── النتيجة ──────────────────────────────
    if not data:
        st.error(f"❌ فشل جلب بيانات **@{username}**")
        st.warning("""
**أسباب محتملة:**
- الحساب خاص أو غير موجود
- Streamlit Cloud محجوب من Twitter APIs
- مرايا Nitter محمية بـ Anubis (PoW)

**الحلول:**
1. ✅ **أدخل بيانات حسابك** في الشريط الجانبي (twikit يعمل)
2. ✅ **استخدم الإدخال اليدوي** ↑ وأدخل البيانات يدوياً
3. 🔍 **جرّب حساباً معروفاً** مثل `elonmusk` للتأكد
""")
        return

    render_profile_card(data)

    # ── Gemini تحليل ─────────────────────────
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

# ══════════════════════════════════════════════
# TWEET TAB
# ══════════════════════════════════════════════
def tweet_tab(model):
    st.markdown("### 📝 تحليل منشور X")

    tweet_url = st.text_input(
        "🔗 رابط المنشور",
        placeholder="https://x.com/username/status/1234567890"
    )
    uploaded_image = st.file_uploader(
        "🖼️ رفع صورة للتحليل (اختياري)",
        type=["jpg","jpeg","png","webp"]
    )
    fetch_btn = st.button("🔍 جلب المنشور")

    if not (fetch_btn and tweet_url):
        return

    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        st.error("❌ لم يتم التعرف على رابط المنشور.")
        return

    with st.spinner("⏳ جلب المنشور..."):
        tweet = fetch_tweet_data(tweet_id)

    if not tweet:
        st.error("❌ فشل جلب المنشور. تحقق من الرابط.")
        return

    st.success("✅ تم جلب المنشور بنجاح")

    # ── مقاييس ───────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    for col, val, label in [
        (c1, format_number(tweet.get("likes",0)),    "❤️ إعجاب"),
        (c2, format_number(tweet.get("retweets",0)), "🔁 إعادة نشر"),
        (c3, format_number(tweet.get("replies",0)),  "💬 رد"),
        (c4, format_number(tweet.get("views",0)),    "👁️ مشاهدة"),
    ]:
        with col:
            st.markdown(
                '<div class="metric-card">'
                '<div class="metric-value">' + val   + '</div>'
                '<div class="metric-label">' + label + '</div>'
                '</div>',
                unsafe_allow_html=True
            )

    st.markdown("**📄 نص المنشور:**")
    st.text_area("", value=tweet.get("text",""), height=120,
                 disabled=True, label_visibility="collapsed")

    author_id = tweet.get("author_id","")
    st.markdown(
        f"👤 **{tweet.get('author_name','')}**"
        f"  (@{tweet.get('author_username','')})"
        + (f"  🆔 `{author_id}`" if author_id else "")
        + f"  📅 {format_date(tweet.get('date',''))}"
    )

    # ── Gemini ────────────────────────────────
    if model:
        st.markdown("---")
        st.markdown("### 🤖 التحليل الاستخباراتي")
        with st.spinner("⏳ Gemini يحلل المنشور..."):
            try:
                img_text = ""
                if uploaded_image:
                    img  = Image.open(uploaded_image)
                    pts  = "\n".join([f"- {p}" for p in IMAGE_ANALYSIS_POINTS])
                    img_r = model.generate_content(
                        [f"حلل الصورة استخباراتياً:\n{pts}", img]
                    )
                    img_text = "\n\n**تحليل الصورة:**\n" + img_r.text

                prompt = f"""حلل المنشور التالي استخباراتياً:
- النص: {tweet.get('text','')}
- الإعجابات: {format_number(tweet.get('likes',0))}
- إعادة النشر: {format_number(tweet.get('retweets',0))}
- الردود: {format_number(tweet.get('replies',0))}
- المشاهدات: {format_number(tweet.get('views',0))}
- التاريخ: {format_date(tweet.get('date',''))}
- الكاتب: {tweet.get('author_name','')} (@{tweet.get('author_username','')})
{('- ID الكاتب: ' + author_id) if author_id else ''}
{img_text}
المطلوب: تحليل المحتوى، التأثير، المؤشرات، التوقيت، التوصيات.
"""
                st.markdown(model.generate_content(prompt).text)
            except Exception as e:
                handle_gemini_error(e)
    else:
        st.info("💡 أضف مفتاح Gemini API للحصول على التحليل.")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
def main():
    gemini_model, debug_mode, twitter_creds = setup_sidebar()

    st.markdown("""
<div class="app-header">
    <div class="app-title">🔍 محلل حسابات X</div>
    <div class="app-subtitle">أداة تحليل استخباراتي لحسابات ومنشورات منصة X (Twitter)</div>
</div>
""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["👤 تحليل حساب", "📝 تحليل منشور"])
    with tab1:
        account_tab(gemini_model, debug_mode, twitter_creds)
    with tab2:
        tweet_tab(gemini_model)


if __name__ == "__main__":
    main()
