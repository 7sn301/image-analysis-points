# -*- coding: utf-8 -*-
# X Account & Post Analyzer v8.2 - Standalone, Python 3.8+ Compatible
# ملف وحيد كامل - لا يستورد من app.py

import streamlit as st

# يجب أن يكون أول أمر Streamlit
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
import time
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

# ─── CSS مخصص ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * { font-family: 'Cairo', sans-serif !important; }
    
    .main { background: #0f1117; color: #e0e0e0; }
    
    .profile-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    
    .profile-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 20px;
    }
    
    .profile-avatar {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 3px solid #1d9bf0;
        object-fit: cover;
    }
    
    .profile-name {
        font-size: 1.4em;
        font-weight: 700;
        color: #ffffff;
    }
    
    .profile-username {
        color: #8b949e;
        font-size: 0.95em;
    }
    
    .verified-badge {
        color: #1d9bf0;
        font-size: 1.1em;
    }
    
    .stats-row {
        display: flex;
        gap: 24px;
        margin: 16px 0;
        flex-wrap: wrap;
    }
    
    .stat-item {
        text-align: center;
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 12px 20px;
        min-width: 100px;
    }
    
    .stat-value {
        font-size: 1.3em;
        font-weight: 700;
        color: #1d9bf0;
    }
    
    .stat-label {
        font-size: 0.8em;
        color: #8b949e;
        margin-top: 4px;
    }
    
    .bio-section {
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 12px 0;
        border-left: 3px solid #1d9bf0;
        color: #c9d1d9;
        line-height: 1.6;
    }
    
    .meta-row {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-top: 12px;
    }
    
    .meta-item {
        color: #8b949e;
        font-size: 0.9em;
    }
    
    .source-badge {
        display: inline-block;
        background: #1d9bf0;
        color: white;
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.8em;
        font-weight: 600;
    }
    
    .analysis-box {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin: 16px 0;
        white-space: pre-wrap;
        line-height: 1.7;
        color: #c9d1d9;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #1d9bf0, #0d47a1) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 24px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 16px rgba(29,155,240,0.4) !important;
    }
    
    .error-box {
        background: rgba(218,54,51,0.1);
        border: 1px solid #da3633;
        border-radius: 8px;
        padding: 12px 16px;
        color: #ff7b72;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ─── ثوابت ────────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

NITTER_MIRRORS = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.cz",
    "https://nitter.unixfox.eu",
]

FXTWITTER_API = "https://api.fxtwitter.com"

# ─── Regex لاستخراج اليوزرنيم ──────────────────────────────────────────────
USERNAME_PATTERNS = [
    r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)(?:[/?#].*)?$",
    r"^@?([A-Za-z0-9_]{1,50})$",
]

TWEET_URL_PATTERNS = [
    r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+/status/(\d+)",
    r"(?:https?://)?(?:www\.)?fxtwitter\.com/[A-Za-z0-9_]+/status/(\d+)",
]

# ─── نقاط تحليل الصور ──────────────────────────────────────────────────────
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

# ─── دوال مساعدة ───────────────────────────────────────────────────────────
def extract_username(text):
    # type: (str) -> Optional[str]
    """استخراج اسم المستخدم من URL أو نص مباشر"""
    if not text:
        return None
    text = text.strip()
    # إزالة query parameters
    text = re.sub(r'\?.*$', '', text)
    text = re.sub(r'#.*$', '', text)
    
    for pattern in USERNAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            username = match.group(1)
            # تجاهل الكلمات المحجوزة
            reserved = {'home', 'explore', 'notifications', 'messages', 'settings', 
                       'search', 'login', 'logout', 'signup', 'i', 'hashtag'}
            if username.lower() not in reserved:
                return username
    return None


def extract_tweet_id(text):
    # type: (str) -> Optional[str]
    """استخراج معرف التغريدة من URL"""
    if not text:
        return None
    for pattern in TWEET_URL_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def format_number(n):
    # type: (Any) -> str
    """تنسيق الأرقام بشكل مقروء"""
    try:
        n = int(n)
        if n >= 1_000_000:
            return "{:.1f}M".format(n / 1_000_000)
        elif n >= 1_000:
            return "{:.1f}K".format(n / 1_000)
        return str(n)
    except (ValueError, TypeError):
        return str(n) if n else "0"


def image_to_base64(url):
    # type: (str) -> Optional[str]
    """تحميل صورة وتحويلها إلى base64"""
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content))
            img = img.convert("RGB")
            img.thumbnail((200, 200))
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        pass
    return None


def format_date(date_str):
    # type: (str) -> str
    """تحويل تاريخ Twitter إلى صيغة عربية مقروءة"""
    if not date_str:
        return "غير متوفر"
    try:
        # صيغة Twitter: "Mon Jan 01 00:00:00 +0000 2020"
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S +0000 %Y")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(date_str)[:10] if len(str(date_str)) >= 10 else str(date_str)


# ─── جلب البيانات: Guest API ────────────────────────────────────────────────
def get_guest_token():
    # type: () -> Optional[str]
    """الحصول على Guest Token من Twitter"""
    try:
        headers = {
            "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "User-Agent": random.choice(USER_AGENTS),
        }
        resp = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("guest_token")
    except Exception:
        pass
    return None


def fetch_via_guest_api(username):
    # type: (str) -> Optional[Dict[str, Any]]
    """جلب بيانات الحساب عبر Twitter Guest API"""
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
            user = (data.get("data", {})
                       .get("user", {})
                       .get("result", {})
                       .get("legacy", {}))
            if user and user.get("screen_name"):
                return {
                    "name": user.get("name", ""),
                    "username": user.get("screen_name", username),
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
    """جلب بيانات الحساب عبر FxTwitter API"""
    try:
        url = "{}/{}".format(FXTWITTER_API, username)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            user = data.get("user", {})
            if user:
                return {
                    "name": user.get("name", ""),
                    "username": user.get("screen_name", username),
                    "bio": user.get("description", ""),
                    "followers": user.get("followers", 0),
                    "following": user.get("following", 0),
                    "posts": user.get("tweets", 0),
                    "location": user.get("location", ""),
                    "join_date": user.get("joined", "غير متوفر"),
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
    """جلب بيانات الحساب عبر Nitter"""
    for mirror in NITTER_MIRRORS:
        try:
            url = "{}/{}".format(mirror, username)
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # اسم الحساب
                name_el = soup.select_one(".profile-card-fullname")
                name = name_el.get_text(strip=True) if name_el else ""
                
                # الوصف
                bio_el = soup.select_one(".profile-bio")
                bio = bio_el.get_text(strip=True) if bio_el else ""
                
                # الموقع
                loc_el = soup.select_one(".profile-location")
                location = loc_el.get_text(strip=True) if loc_el else ""
                
                # تاريخ الانضمام
                joined_el = soup.select_one(".profile-joindate")
                join_date = joined_el.get_text(strip=True) if joined_el else "غير متوفر"
                
                # الإحصائيات
                stats = soup.select(".profile-stat-num")
                followers = int(stats[0].get_text(strip=True).replace(",", "")) if len(stats) > 0 else 0
                following = int(stats[1].get_text(strip=True).replace(",", "")) if len(stats) > 1 else 0
                posts = int(stats[2].get_text(strip=True).replace(",", "")) if len(stats) > 2 else 0
                
                # صورة الملف الشخصي
                img_el = soup.select_one(".profile-card-avatar img")
                profile_image = ""
                if img_el:
                    src = img_el.get("src", "")
                    if src.startswith("/"):
                        profile_image = mirror + src
                    else:
                        profile_image = src
                
                if name or bio:
                    return {
                        "name": name,
                        "username": username,
                        "bio": bio,
                        "followers": followers,
                        "following": following,
                        "posts": posts,
                        "location": location,
                        "join_date": join_date,
                        "verified": False,
                        "profile_image": profile_image,
                        "banner": "",
                        "source": "Nitter ({})".format(mirror.split("//")[1]),
                    }
        except Exception:
            continue
    return None


def fetch_user_data(username):
    # type: (str) -> Tuple[Optional[Dict[str, Any]], str]
    """جلب بيانات المستخدم مع fallback ثلاثي"""
    # المحاولة الأولى: Guest API
    data = fetch_via_guest_api(username)
    if data:
        return data, "guest_api"
    
    # المحاولة الثانية: FxTwitter
    data = fetch_via_fxtwitter(username)
    if data:
        return data, "fxtwitter"
    
    # المحاولة الثالثة: Nitter
    data = fetch_via_nitter(username)
    if data:
        return data, "nitter"
    
    return None, "failed"


# ─── جلب بيانات التغريدة ────────────────────────────────────────────────────
def fetch_tweet_data(tweet_id):
    # type: (str) -> Optional[Dict[str, Any]]
    """جلب بيانات التغريدة عبر FxTwitter"""
    try:
        url = "https://api.fxtwitter.com/status/{}".format(tweet_id)
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
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "replies": tweet.get("replies", 0),
                    "views": tweet.get("views", 0),
                    "created_at": tweet.get("created_at", ""),
                    "lang": tweet.get("lang", ""),
                    "media": tweet.get("media", {}).get("photos", []),
                    "url": "https://x.com/{}/status/{}".format(
                        tweet.get("author", {}).get("screen_name", ""), tweet_id
                    ),
                }
    except Exception:
        pass
    return None


# ─── عرض بطاقة الملف الشخصي ─────────────────────────────────────────────────
def render_profile_card(data):
    # type: (Dict[str, Any]) -> None
    """عرض بطاقة جميلة لبيانات الحساب"""
    
    # تحويل الصورة إلى base64
    avatar_html = ""
    profile_img_url = data.get("profile_image", "")
    if profile_img_url:
        b64 = image_to_base64(profile_img_url)
        if b64:
            avatar_html = '<img src="data:image/jpeg;base64,{}" class="profile-avatar">'.format(b64)
        else:
            avatar_html = '<div style="width:80px;height:80px;border-radius:50%;background:#1d9bf0;display:flex;align-items:center;justify-content:center;font-size:2em;">👤</div>'
    else:
        avatar_html = '<div style="width:80px;height:80px;border-radius:50%;background:#1d9bf0;display:flex;align-items:center;justify-content:center;font-size:2em;">👤</div>'
    
    # علامة التوثيق
    verified_html = ' <span class="verified-badge">✓</span>' if data.get("verified") else ""
    
    # الإحصائيات
    stats_html = """
    <div class="stats-row">
        <div class="stat-item">
            <div class="stat-value">{followers}</div>
            <div class="stat-label">👥 متابعون</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{following}</div>
            <div class="stat-label">➡️ يتابع</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{posts}</div>
            <div class="stat-label">📝 منشورات</div>
        </div>
    </div>
    """.format(
        followers=format_number(data.get("followers", 0)),
        following=format_number(data.get("following", 0)),
        posts=format_number(data.get("posts", 0)),
    )
    
    # الوصف
    bio_html = ""
    if data.get("bio"):
        bio_html = '<div class="bio-section">📄 {}</div>'.format(data["bio"])
    
    # المعلومات الإضافية
    meta_items = []
    if data.get("location"):
        meta_items.append("📍 {}".format(data["location"]))
    if data.get("join_date") and data["join_date"] != "غير متوفر":
        meta_items.append("📅 انضم في: {}".format(data["join_date"]))
    meta_html = ""
    if meta_items:
        meta_html = '<div class="meta-row">' + "".join(
            ['<span class="meta-item">{}</span>'.format(item) for item in meta_items]
        ) + '</div>'
    
    card_html = """
    <div class="profile-card">
        <div class="profile-header">
            {avatar}
            <div>
                <div class="profile-name">{name}{verified}</div>
                <div class="profile-username">@{username}</div>
                <span class="source-badge">📡 {source}</span>
            </div>
        </div>
        {stats}
        {bio}
        {meta}
    </div>
    """.format(
        avatar=avatar_html,
        name=data.get("name", username),
        verified=verified_html,
        username=data.get("username", ""),
        source=data.get("source", "Unknown"),
        stats=stats_html,
        bio=bio_html,
        meta=meta_html,
    )
    
    st.markdown(card_html, unsafe_allow_html=True)


# ─── الشريط الجانبي ─────────────────────────────────────────────────────────
def setup_sidebar():
    # type: () -> Any
    """إعداد الشريط الجانبي وتحميل نموذج Gemini"""
    with st.sidebar:
        st.markdown("## 🔍 محلل حسابات X")
        st.markdown("---")
        
        model = None
        if GEMINI_AVAILABLE:
            api_key = st.text_input(
                "🔑 مفتاح Gemini API",
                type="password",
                placeholder="AIza...",
                help="احصل على مفتاحك من: https://aistudio.google.com/apikey"
            )
            
            gemini_model = st.selectbox(
                "🤖 نموذج Gemini",
                ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"],
                index=0
            )
            
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(gemini_model)
                    st.success("✅ Gemini متصل")
                except Exception as e:
                    st.error("❌ خطأ في الاتصال: {}".format(str(e)[:50]))
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


# ─── تبويب تحليل الحساب ─────────────────────────────────────────────────────
def account_tab(model):
    # type: (Any) -> None
    """تبويب تحليل الحسابات"""
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
    
    # إدخال يدوي
    with st.expander("📝 إدخال يدوي (في حال فشل الجلب التلقائي)"):
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            manual_name = st.text_input("الاسم الكامل")
            manual_username = st.text_input("اسم المستخدم (@)")
            manual_bio = st.text_area("الوصف (Bio)", height=80)
            manual_location = st.text_input("الموقع")
        with m_col2:
            manual_followers = st.number_input("المتابعون", min_value=0, value=0)
            manual_following = st.number_input("يتابع", min_value=0, value=0)
            manual_posts = st.number_input("المنشورات", min_value=0, value=0)
            manual_join = st.text_input("تاريخ الانضمام")
        
        use_manual = st.checkbox("استخدام البيانات اليدوية")
    
    if analyze_btn and user_input:
        username = extract_username(user_input)
        
        if not username:
            st.error("❌ تعذر استخراج اسم المستخدم. تأكد من صحة الرابط.")
            return
        
        st.info("🔄 جاري جلب بيانات @{}...".format(username))
        
        if use_manual:
            data = {
                "name": manual_name or username,
                "username": manual_username.lstrip("@") or username,
                "bio": manual_bio,
                "followers": int(manual_followers),
                "following": int(manual_following),
                "posts": int(manual_posts),
                "location": manual_location,
                "join_date": manual_join or "غير متوفر",
                "verified": False,
                "profile_image": "",
                "source": "إدخال يدوي",
            }
            source = "manual"
        else:
            with st.spinner("جاري المحاولة..."):
                data, source = fetch_user_data(username)
        
        if data:
            st.success("✅ تم جلب البيانات من: {}".format(data.get("source", source)))
            render_profile_card(data)
            
            # تحليل Gemini
            if model:
                with st.spinner("🤖 جاري التحليل بالذكاء الاصطناعي..."):
                    try:
                        prompt = """أنت محلل استخباراتي متخصص في تحليل حسابات منصة X (تويتر).
                        
حلل الحساب التالي وقدم تقريرًا شاملًا:

**معلومات الحساب:**
- الاسم: {}
- اسم المستخدم: @{}
- الوصف: {}
- المتابعون: {}
- يتابع: {}
- المنشورات: {}
- الموقع: {}
- تاريخ الانضمام: {}
- موثق: {}

**التقرير المطلوب:**
1. 🎯 **تصنيف الحساب**: (شخصي/مؤسسي/إعلامي/بوت/مشبوه)
2. 📊 **تحليل المصداقية**: نسبة المصداقية مع التبرير
3. 🔍 **مؤشرات مثيرة للاهتمام**: أي أنماط غير عادية
4. 📈 **تحليل التأثير**: مدى التأثير والانتشار
5. ⚠️ **تقييم المخاطر**: هل يوجد محتوى مثير للقلق
6. 📝 **ملاحظات استخباراتية**: معلومات قيمة للتحليل""".format(
                            data.get("name", ""),
                            data.get("username", ""),
                            data.get("bio", "لا يوجد"),
                            format_number(data.get("followers", 0)),
                            format_number(data.get("following", 0)),
                            format_number(data.get("posts", 0)),
                            data.get("location", "غير محدد"),
                            data.get("join_date", "غير متوفر"),
                            "نعم" if data.get("verified") else "لا",
                        )
                        
                        response = model.generate_content(prompt)
                        st.markdown("### 🤖 التقرير الاستخباراتي")
                        st.markdown(
                            '<div class="analysis-box">{}</div>'.format(response.text),
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        st.error("❌ خطأ في Gemini: {}".format(str(e)[:100]))
            else:
                st.info("💡 أضف مفتاح Gemini API من الشريط الجانبي للحصول على تحليل AI.")
        else:
            st.error("❌ تعذر جلب بيانات الحساب. جرب الإدخال اليدوي.")


# ─── تبويب تحليل المنشور ────────────────────────────────────────────────────
def tweet_tab(model):
    # type: (Any) -> None
    """تبويب تحليل المنشورات"""
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
    
    # رفع صورة للتحليل
    st.markdown("#### 🖼️ تحليل صورة من المنشور")
    uploaded_image = st.file_uploader(
        "ارفع صورة للتحليل",
        type=["jpg", "jpeg", "png", "webp"],
        help="ارفع صورة من المنشور لتحليلها بالذكاء الاصطناعي"
    )
    
    if uploaded_image and model:
        if st.button("🔍 تحليل الصورة"):
            with st.spinner("جاري تحليل الصورة..."):
                try:
                    img = Image.open(uploaded_image)
                    
                    points_text = "\n".join(
                        ["{}. {}".format(i+1, p) for i, p in enumerate(IMAGE_ANALYSIS_POINTS)]
                    )
                    
                    prompt = """أنت محلل استخباراتي متخصص في تحليل الصور الرقمية.
                    
حلل هذه الصورة وفق النقاط التالية:

{}

قدم تقريرًا مفصلًا ومنظمًا يغطي كل نقطة ذات صلة بالصورة.
ركز على المعلومات الاستخباراتية القيمة.""".format(points_text)
                    
                    response = model.generate_content([prompt, img])
                    st.markdown("### 🔍 نتائج تحليل الصورة")
                    st.markdown(
                        '<div class="analysis-box">{}</div>'.format(response.text),
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error("❌ خطأ في تحليل الصورة: {}".format(str(e)[:100]))
    elif uploaded_image and not model:
        st.info("💡 أضف مفتاح Gemini API لتحليل الصورة.")
    
    # جلب المنشور
    if fetch_btn and tweet_input:
        tweet_id = extract_tweet_id(tweet_input)
        
        if not tweet_id:
            st.error("❌ تعذر استخراج معرف المنشور.")
            return
        
        with st.spinner("جاري جلب المنشور..."):
            tweet_data = fetch_tweet_data(tweet_id)
        
        if tweet_data:
            st.success("✅ تم جلب المنشور")
            
            # عرض بيانات المنشور
            with st.container():
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("❤️ إعجابات", format_number(tweet_data.get("likes", 0)))
                col2.metric("🔁 إعادة نشر", format_number(tweet_data.get("retweets", 0)))
                col3.metric("💬 ردود", format_number(tweet_data.get("replies", 0)))
                col4.metric("👁️ مشاهدات", format_number(tweet_data.get("views", 0)))
                
                st.markdown("**نص المنشور:**")
                st.info(tweet_data.get("text", ""))
                
                st.markdown("**المؤلف:** @{} ({})".format(
                    tweet_data.get("author", ""),
                    tweet_data.get("author_name", "")
                ))
                
                if tweet_data.get("created_at"):
                    st.markdown("**التاريخ:** {}".format(tweet_data["created_at"]))
            
            # تحليل Gemini
            if model:
                with st.spinner("🤖 تحليل المنشور بالذكاء الاصطناعي..."):
                    try:
                        prompt = """حلل هذا المنشور من منصة X:

**المنشور:** {}
**المؤلف:** @{} ({})
**الإحصائيات:** إعجابات: {} | إعادة نشر: {} | ردود: {} | مشاهدات: {}
**التاريخ:** {}

**التحليل المطلوب:**
1. 📌 الموضوع الرئيسي والرسالة
2. 🎯 الجمهور المستهدف
3. 📊 مستوى التفاعل (عادي/عالٍ/غير عادي)
4. ⚠️ أي محتوى مثير للقلق
5. 🔍 ملاحظات استخباراتية""".format(
                            tweet_data.get("text", ""),
                            tweet_data.get("author", ""),
                            tweet_data.get("author_name", ""),
                            format_number(tweet_data.get("likes", 0)),
                            format_number(tweet_data.get("retweets", 0)),
                            format_number(tweet_data.get("replies", 0)),
                            format_number(tweet_data.get("views", 0)),
                            tweet_data.get("created_at", ""),
                        )
                        
                        response = model.generate_content(prompt)
                        st.markdown("### 🤖 تحليل المنشور")
                        st.markdown(
                            '<div class="analysis-box">{}</div>'.format(response.text),
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        st.error("❌ خطأ في Gemini: {}".format(str(e)[:100]))
        else:
            st.error("❌ تعذر جلب المنشور. تأكد من الرابط.")


# ─── الدالة الرئيسية ─────────────────────────────────────────────────────────
def main():
    # type: () -> None
    """نقطة الدخول الرئيسية للتطبيق"""
    model = setup_sidebar()
    
    st.markdown("""
    <div style="text-align:center; padding: 20px 0 10px 0;">
        <h1 style="color:#1d9bf0; font-size:2em;">🔍 محلل حسابات X</h1>
        <p style="color:#8b949e;">أداة تحليل استخباراتي متقدمة لمنصة X (تويتر)</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["👤 تحليل حساب", "📝 تحليل منشور"])
    
    with tab1:
        account_tab(model)
    
    with tab2:
        tweet_tab(model)


# تشغيل التطبيق
main()
