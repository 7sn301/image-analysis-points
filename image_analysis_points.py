# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.8
# الحل النهائي: Tweepy بمفاتيح Developer الخاصة + إدخال يدوي

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
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False

# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
* { font-family: 'Cairo', sans-serif !important; }
.main, .stApp { background: #0a0a0a; color: #e0e0e0; }
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
.profile-name { font-size: 1.8em; font-weight: 900; color: #fff; margin-bottom: 4px; }
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
.api-setup-box {
    background: linear-gradient(135deg, #0d2137, #0a1628);
    border: 2px solid #1da1f2; border-radius: 16px; padding: 20px; margin: 16px 0;
}
.stTabs [data-baseweb="tab"] { font-size: 1.1em !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
]
FXTWITTER_API = "https://api.fxtwitter.com"
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
        if n >= 1_000: return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(n)

def format_date(date_str: str) -> str:
    if not date_str or date_str == "غير متوفر": return date_str or "غير متوفر"
    for fmt in ["%a %b %d %H:%M:%S %z %Y","%Y-%m-%dT%H:%M:%S.%fZ","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%d"]:
        try: return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except: pass
    return date_str[:10] if len(date_str) >= 10 else date_str

def image_to_base64(url: str) -> str:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": random.choice(USER_AGENTS)})
        if r.status_code == 200:
            return base64.b64encode(r.content).decode()
    except: pass
    return ""

# ──────────────────────────────────────────────
# DATA FETCHING
# ──────────────────────────────────────────────
def fetch_via_tweepy_v1(username: str, api_key: str, api_secret: str,
                         access_token: str, access_secret: str) -> Optional[Dict]:
    """Tweepy v1.1 — الأكثر موثوقية مع مفاتيح Developer الخاصة"""
    if not TWEEPY_AVAILABLE or not all([api_key, api_secret, access_token, access_secret]):
        return None
    try:
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_secret)
        api = tweepy.API(auth, wait_on_rate_limit=False)
        u = api.get_user(screen_name=username)
        return {
            "name": u.name,
            "username": u.screen_name,
            "user_id": str(u.id),
            "bio": u.description or "",
            "followers": u.followers_count,
            "following": u.friends_count,
            "posts": u.statuses_count,
            "location": u.location or "",
            "join_date": str(u.created_at),
            "verified": u.verified,
            "profile_image": u.profile_image_url_https.replace("_normal","") if hasattr(u,"profile_image_url_https") else "",
            "banner": getattr(u, "profile_banner_url", ""),
            "source": "Twitter API (Tweepy)",
        }
    except Exception as e:
        return None


def fetch_via_tweepy_v2(username: str, bearer_token: str) -> Optional[Dict]:
    """Tweepy v2 Bearer Token — يكفي مفتاح Bearer فقط"""
    if not TWEEPY_AVAILABLE or not bearer_token:
        return None
    try:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
        resp = client.get_user(
            username=username,
            user_fields=["description","public_metrics","created_at",
                         "location","verified","profile_image_url","entities"]
        )
        if not resp.data:
            return None
        u = resp.data
        m = u.public_metrics or {}
        return {
            "name": u.name,
            "username": u.username,
            "user_id": str(u.id),
            "bio": u.description or "",
            "followers": m.get("followers_count", 0),
            "following": m.get("following_count", 0),
            "posts": m.get("tweet_count", 0),
            "location": u.location or "",
            "join_date": str(u.created_at) if u.created_at else "",
            "verified": getattr(u, "verified", False) or False,
            "profile_image": (u.profile_image_url or "").replace("_normal",""),
            "banner": "",
            "source": "Twitter API v2 (Tweepy)",
        }
    except Exception:
        return None


def fetch_tweet_data(tweet_id: str) -> Optional[Dict]:
    try:
        r = requests.get(
            f"{FXTWITTER_API}/status/{tweet_id}",
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=15,
        )
        if r.status_code != 200: return None
        data = r.json()
        tweet = data.get("tweet") or data.get("data",{}).get("tweet",{})
        if not tweet: return None
        author = tweet.get("author") or {}
        return {
            "id": tweet_id,
            "text": tweet.get("text",""),
            "likes": tweet.get("likes",0),
            "retweets": tweet.get("retweets",0),
            "replies": tweet.get("replies",0),
            "views": tweet.get("views",0),
            "date": tweet.get("created_at",""),
            "url": tweet.get("url", f"https://x.com/i/status/{tweet_id}"),
            "author_name": author.get("name",""),
            "author_username": author.get("screen_name",""),
            "author_id": str(author.get("id", author.get("id_str",""))),
            "media": tweet.get("media",{}).get("photos",[]),
            "source": "FxTwitter",
        }
    except: return None

# ──────────────────────────────────────────────
# RENDER PROFILE CARD
# ──────────────────────────────────────────────
def render_profile_card(data: Dict):
    display_name     = clean_text(data.get("name",""))
    display_username = clean_text(data.get("username",""))
    user_id          = clean_text(data.get("user_id",""))
    display_source   = clean_text(data.get("source","Unknown"))

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
    uid_html = '<div class="user-id-badge">🆔 ' + user_id + '</div>' if user_id else ""

    stats_html = (
        '<div class="stats-row">'
        '<div class="stat-item"><div class="stat-value">' + format_number(data.get("followers",0)) + '</div><div class="stat-label">متابِع</div></div>'
        '<div class="stat-item"><div class="stat-value">' + format_number(data.get("following",0)) + '</div><div class="stat-label">يتابع</div></div>'
        '<div class="stat-item"><div class="stat-value">' + format_number(data.get("posts",0)) + '</div><div class="stat-label">منشور</div></div>'
        '</div>'
    )

    bio_text = clean_text(data.get("bio",""))
    bio_html = '<div class="bio-section">📄 ' + bio_text + '</div>' if bio_text else ""

    meta_parts = []
    loc = clean_text(data.get("location",""))
    if loc: meta_parts.append("📍 " + loc)
    jd = format_date(str(data.get("join_date","")))
    if jd and jd != "غير متوفر": meta_parts.append("📅 انضم في: " + jd)
    meta_html = ""
    if meta_parts:
        meta_html = '<div class="meta-row">' + "".join(
            ['<span class="meta-item">' + p + '</span>' for p in meta_parts]
        ) + '</div>'

    card_html = (
        '<div class="profile-card"><div class="profile-header">'
        + avatar_html +
        '<div><div class="profile-name">' + display_name + verified_html + '</div>'
        '<div class="profile-username">@' + display_username + '</div>'
        + uid_html +
        '<span class="source-badge">📡 ' + display_source + '</span>'
        '</div></div>'
        + stats_html + bio_html + meta_html + '</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
    if user_id:
        st.text_input("🆔 معرّف الحساب (User ID) — انقر للنسخ",
                       value=user_id, key="uid_" + display_username)

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

    # ── Gemini ──
    st.sidebar.markdown("### 🤖 Gemini AI")
    api_key = st.sidebar.text_input("🔑 مفتاح Gemini API", type="password", placeholder="AIzaSy...")
    model_name = st.sidebar.selectbox(
        "نموذج Gemini",
        ["gemini-2.0-flash-lite","gemini-2.0-flash","gemini-1.5-pro"],
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

    # ── Twitter API ──
    st.sidebar.markdown("### 🐦 Twitter Developer API")
    with st.sidebar.expander("🔑 مفاتيح Twitter API (مطلوبة للجلب)", expanded=True):
        st.markdown("""
<small>
احصل على مفاتيحك من:
<a href="https://developer.twitter.com/en/portal/dashboard" target="_blank">
developer.twitter.com</a>
</small>
""", unsafe_allow_html=True)

        tw_method = st.radio(
            "طريقة الاتصال",
            ["🔐 Bearer Token فقط (v2)", "🔑 مفاتيح كاملة (v1.1)"],
            index=0,
        )

        tw_bearer = ""
        tw_api_key = tw_api_secret = tw_access = tw_access_secret = ""

        if tw_method == "🔐 Bearer Token فقط (v2)":
            tw_bearer = st.text_input("Bearer Token", type="password",
                placeholder="AAAAAAA...", key="tw_bearer")
        else:
            tw_api_key     = st.text_input("API Key (Consumer Key)", type="password", key="tw_akey")
            tw_api_secret  = st.text_input("API Secret", type="password", key="tw_asecret")
            tw_access      = st.text_input("Access Token", type="password", key="tw_at")
            tw_access_secret = st.text_input("Access Token Secret", type="password", key="tw_ats")

    debug_mode = st.sidebar.checkbox("🐛 وضع التشخيص", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
**📖 كيفية الاستخدام:**
1. أضف مفاتيح Twitter Developer
2. أضف مفتاح Gemini AI
3. أدخل رابط الحساب أو المنشور
4. اضغط جلب البيانات

**💡 بدون مفاتيح Twitter:**
استخدم الإدخال اليدوي في التطبيق
""")

    twitter_creds = {
        "method": tw_method,
        "bearer": tw_bearer,
        "api_key": tw_api_key,
        "api_secret": tw_api_secret,
        "access_token": tw_access,
        "access_secret": tw_access_secret,
    }
    return gemini_model, debug_mode, twitter_creds

# ──────────────────────────────────────────────
# ACCOUNT TAB
# ──────────────────────────────────────────────
def account_tab(model, debug: bool, twitter_creds: dict):
    st.markdown("### 👤 تحليل حساب X")

    # إرشادات سريعة
    if not twitter_creds.get("bearer") and not twitter_creds.get("api_key"):
        st.info("⚠️ **لم تُضف مفاتيح Twitter API بعد.** "
                "أضفها في الشريط الجانبي، أو استخدم الإدخال اليدوي أدناه.")

    col1, col2 = st.columns([3,1])
    with col1:
        user_input = st.text_input("🔗 رابط أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username  أو  username")
    with col2:
        fetch_btn = st.button("🔍 جلب البيانات", use_container_width=True)

    with st.expander("✏️ إدخال بيانات يدوي (يعمل دائماً بدون API)"):
        mc1, mc2 = st.columns(2)
        with mc1:
            manual_name      = st.text_input("الاسم الكامل")
            manual_followers = st.number_input("المتابعون", min_value=0, value=0)
            manual_posts     = st.number_input("المنشورات",  min_value=0, value=0)
            manual_user_id   = st.text_input("معرّف الحساب (User ID)")
        with mc2:
            manual_bio       = st.text_area("النبذة التعريفية", height=100)
            manual_following = st.number_input("يتابع", min_value=0, value=0)
            manual_location  = st.text_input("الموقع")
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
                data = None
                method = twitter_creds.get("method","")

                # المحاولة 1: Tweepy v2 (Bearer Token)
                if twitter_creds.get("bearer"):
                    if debug: st.caption("🔵 جاري المحاولة: Tweepy v2 (Bearer Token)...")
                    data = fetch_via_tweepy_v2(username, twitter_creds["bearer"])
                    if data and debug: st.caption("✅ نجح: Tweepy v2")

                # المحاولة 2: Tweepy v1.1 (مفاتيح كاملة)
                if not data and twitter_creds.get("api_key"):
                    if debug: st.caption("🟢 جاري المحاولة: Tweepy v1.1...")
                    data = fetch_via_tweepy_v1(
                        username,
                        twitter_creds["api_key"],
                        twitter_creds["api_secret"],
                        twitter_creds["access_token"],
                        twitter_creds["access_secret"],
                    )
                    if data and debug: st.caption("✅ نجح: Tweepy v1.1")

        if not data:
            st.error(f"❌ فشل جلب بيانات **@{username}**")
            st.warning("""
**السبب:** Streamlit Cloud محجوب من جميع Twitter APIs (كودات 401/403).

**الحلول:**

**الحل 1 (الأفضل): مفاتيح Twitter Developer**
1. سجّل دخولك على [developer.twitter.com](https://developer.twitter.com)
2. أنشئ App جديد → احصل على Bearer Token
3. أضفه في الشريط الجانبي ← "مفاتيح Twitter API"

**الحل 2 (فوري): الإدخال اليدوي**
افتح الـ expander ↑ "إدخال بيانات يدوي" وأدخل البيانات مباشرة
""")
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
    tweet_url = st.text_input("🔗 رابط المنشور",
        placeholder="https://x.com/username/status/1234567890")
    uploaded_image = st.file_uploader(
        "🖼️ رفع صورة للتحليل (اختياري)",
        type=["jpg","jpeg","png","webp"]
    )
    fetch_btn = st.button("🔍 جلب المنشور")

    if fetch_btn and tweet_url:
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
        c1,c2,c3,c4 = st.columns(4)
        for col, val, label in [
            (c1, format_number(tweet.get("likes",0)),    "❤️ إعجاب"),
            (c2, format_number(tweet.get("retweets",0)), "🔁 إعادة نشر"),
            (c3, format_number(tweet.get("replies",0)),  "💬 رد"),
            (c4, format_number(tweet.get("views",0)),    "👁️ مشاهدة"),
        ]:
            with col:
                st.markdown(
                    '<div class="metric-card"><div class="metric-value">' + val +
                    '</div><div class="metric-label">' + label + '</div></div>',
                    unsafe_allow_html=True
                )

        st.markdown("**📄 نص المنشور:**")
        st.text_area("", value=tweet.get("text",""), height=120, disabled=True,
                     label_visibility="collapsed")
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
                        img_r = model.generate_content(
                            [f"حلل الصورة استخباراتياً مع التركيز على:\n{pts}", img]
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

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    gemini_model, debug_mode, twitter_creds = setup_sidebar()
    st.markdown("""
<div class="app-header">
    <div class="app-title">🔍 محلل حسابات X</div>
    <div class="app-subtitle">أداة تحليل استخباراتي لحسابات ومنشورات منصة X (Twitter)</div>
</div>
""", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["👤 تحليل حساب","📝 تحليل منشور"])
    with tab1:
        account_tab(gemini_model, debug_mode, twitter_creds)
    with tab2:
        tweet_tab(gemini_model)

if __name__ == "__main__":
    main()
