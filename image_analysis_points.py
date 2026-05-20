# ============================================================
# محلل حسابات X  - v9.3
# الإصلاح: twikit import داخل الدوال فقط (يمنع crash عند البدء)
# ============================================================

import streamlit as st
import requests
import re
import os
import json
import asyncio
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# إعداد الصفحة — أول شيء يُستدعى
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────
# CSS — ثيم داكن عربي
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

* { font-family: 'Cairo', sans-serif !important; }

.stApp {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    color: #e6edf3;
    direction: rtl;
}

.main .block-container {
    padding: 1.5rem 2rem;
    max-width: 1200px;
    background: transparent;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    border-left: 1px solid #30363d;
}
[data-testid="stSidebar"] * { direction: rtl; text-align: right; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #238636, #2ea043);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1.2rem;
    transition: all 0.2s;
    width: 100%;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2ea043, #3fb950);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(46, 160, 67, 0.4);
}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background: #21262d !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    direction: rtl !important;
}

/* Cards */
.profile-card {
    background: linear-gradient(135deg, #161b22, #21262d);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}

.stat-box {
    background: #0d1117;
    border: 1px solid #238636;
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
    margin: 0.3rem;
}

.stat-number {
    font-size: 1.8rem;
    font-weight: 700;
    color: #3fb950;
}

.stat-label {
    font-size: 0.85rem;
    color: #8b949e;
}

/* Featured image */
.featured-image-container {
    width: 100%;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 1.5rem;
    border: 2px solid #30363d;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    max-height: 400px;
}
.featured-image-container img {
    width: 100%;
    object-fit: cover;
    display: block;
}

/* Upload hint */
.upload-hint {
    border: 2px dashed #30363d;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    color: #8b949e;
    margin: 0.5rem 0;
    background: rgba(255,255,255,0.02);
    transition: border-color 0.2s;
}
.upload-hint:hover { border-color: #58a6ff; }

/* Info/Success/Error boxes */
.info-box {
    background: rgba(56,139,253,0.1);
    border: 1px solid #1f6feb;
    border-radius: 10px;
    padding: 1rem;
    margin: 0.5rem 0;
    direction: rtl;
}
.success-box {
    background: rgba(46,160,67,0.1);
    border: 1px solid #238636;
    border-radius: 10px;
    padding: 1rem;
    margin: 0.5rem 0;
    direction: rtl;
}
.error-box {
    background: rgba(248,81,73,0.1);
    border: 1px solid #da3633;
    border-radius: 10px;
    padding: 1rem;
    margin: 0.5rem 0;
    direction: rtl;
}
.warning-box {
    background: rgba(210,153,34,0.1);
    border: 1px solid #d29922;
    border-radius: 10px;
    padding: 1rem;
    margin: 0.5rem 0;
    direction: rtl;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #161b22;
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    border: 1px solid #30363d;
}
.stTabs [data-baseweb="tab"] {
    color: #8b949e;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: #238636 !important;
    color: white !important;
}

/* Report */
.report-section {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    direction: rtl;
    line-height: 1.8;
}

/* Metrics */
[data-testid="stMetric"] {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 0.8rem;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #58a6ff; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# الثوابت
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
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
COOKIES_PATH = "/tmp/twikit_cookies.json"

IMAGE_ANALYSIS_POINTS = [
    "الموقع الجغرافي أو المؤشرات المكانية",
    "الأشخاص والهويات المرئية",
    "المعدات والتجهيزات الظاهرة",
    "المركبات وأرقام اللوحات",
    "العلامات والشعارات والنصوص",
    "الزمن والمناخ والإضاءة",
    "البنية التحتية والمنشآت",
    "الأنشطة والتجمعات البشرية",
    "الدلالات الأمنية والاستخباراتية",
    "التناقضات والعناصر غير العادية",
]

# ──────────────────────────────────────────────
# دوال مساعدة
# ──────────────────────────────────────────────
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_username(input_str: str) -> str:
    input_str = input_str.strip()
    if "twitter.com/" in input_str or "x.com/" in input_str:
        match = re.search(r'(?:twitter|x)\.com/([A-Za-z0-9_]+)', input_str)
        if match:
            return match.group(1)
    return input_str.lstrip("@")

def extract_tweet_id(input_str: str) -> str:
    input_str = input_str.strip()
    match = re.search(r'/status/(\d+)', input_str)
    if match:
        return match.group(1)
    if input_str.isdigit():
        return input_str
    return ""

def format_number(n) -> str:
    try:
        n = int(str(n).replace(",", "").replace(".", ""))
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except:
        return str(n) if n else "0"

def format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        patterns = [
            "%a %b %d %H:%M:%S %z %Y",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
        ]
        for p in patterns:
            try:
                dt = datetime.strptime(date_str, p)
                return dt.strftime("%d/%m/%Y %H:%M")
            except:
                continue
        return date_str[:16]
    except:
        return date_str

def pil_to_base64(img: Image.Image, fmt="JPEG") -> str:
    if img.mode in ("RGBA", "P", "LA", "CMYK"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format=fmt, quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def img_url_to_base64(url: str) -> str:
    try:
        headers = {"User-Agent": USER_AGENTS[0]}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content))
            return pil_to_base64(img)
    except:
        pass
    return ""

# ──────────────────────────────────────────────
# twikit — مستورد داخل الدوال فقط (يمنع crash)
# ──────────────────────────────────────────────
def _check_twikit_available() -> tuple[bool, str]:
    """تحقق من توفر twikit"""
    try:
        import twikit
        return True, twikit.__version__
    except ImportError:
        return False, "غير مثبت"
    except Exception as e:
        return False, str(e)

async def _twikit_login(username: str, email: str, password: str):
    """تسجيل الدخول عبر twikit"""
    try:
        from twikit import Client
    except ImportError:
        return None, "❌ مكتبة twikit غير مثبتة"

    try:
        client = Client('ar')
        if os.path.exists(COOKIES_PATH):
            try:
                client.load_cookies(COOKIES_PATH)
                return client, "✅ تم تحميل الجلسة"
            except Exception:
                os.remove(COOKIES_PATH)

        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password
        )
        client.save_cookies(COOKIES_PATH)
        return client, f"✅ تم الدخول كـ @{username}"
    except Exception as e:
        err = str(e)
        if "KEY_BYTE" in err:
            return None, (
                "❌ خطأ twikit (KEY_BYTE) — تويتر غيّر بنيته الداخلية.\n"
                "الحل: عدّل requirements.txt إلى:\n"
                "twikit @ git+https://github.com/d60/twikit.git"
            )
        return None, f"❌ فشل الدخول: {err}"

async def _twikit_login_test(username: str, email: str, password: str) -> tuple[bool, str]:
    """اختبار بيانات twikit"""
    client, msg = await _twikit_login(username, email, password)
    return client is not None, msg

async def _fetch_twikit_user(client, username: str) -> dict | None:
    """جلب بيانات مستخدم عبر twikit"""
    try:
        user = await client.get_user_by_screen_name(username)
        if not user:
            return None
        return {
            "name": user.name or "",
            "screen_name": user.screen_name or username,
            "description": user.description or "",
            "followers_count": user.followers_count or 0,
            "following_count": user.following_count or 0,
            "tweet_count": user.tweet_count or 0,
            "created_at": str(user.created_at or ""),
            "verified": getattr(user, "verified", False),
            "profile_image_url": getattr(user, "profile_image_url_https",
                                         getattr(user, "profile_image_url", "")),
            "location": getattr(user, "location", ""),
            "url": getattr(user, "url", ""),
            "source": "twikit",
        }
    except Exception as e:
        st.session_state.get("debug") and st.warning(f"twikit error: {e}")
        return None

# ──────────────────────────────────────────────
# Nitter scraping
# ──────────────────────────────────────────────
def fetch_nitter_data(username: str, debug: bool = False) -> dict | None:
    headers = {
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html",
        "Accept-Language": "ar,en;q=0.9",
    }
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                debug and st.warning(f"Nitter {mirror}: HTTP {r.status_code}")
                continue
            if "anubis" in r.text.lower() or "bot" in r.text.lower()[:500]:
                debug and st.warning(f"Nitter {mirror}: Bot Protection")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            name_el = soup.select_one(".profile-card-fullname, .fullname")
            screen_el = soup.select_one(".profile-card-username, .username")
            bio_el = soup.select_one(".profile-bio p, .bio p")
            stats = soup.select(".profile-stat-num, .stats .stat-num")
            img_el = soup.select_one(".profile-card-avatar img, .avatar img")

            if not name_el:
                debug and st.warning(f"Nitter {mirror}: لم يُعثر على بيانات")
                continue

            data = {
                "name": clean_text(name_el.get_text()),
                "screen_name": clean_text(screen_el.get_text()).lstrip("@") if screen_el else username,
                "description": clean_text(bio_el.get_text()) if bio_el else "",
                "followers_count": clean_text(stats[0].get_text()) if len(stats) > 0 else "0",
                "following_count": clean_text(stats[1].get_text()) if len(stats) > 1 else "0",
                "tweet_count": clean_text(stats[2].get_text()) if len(stats) > 2 else "0",
                "profile_image_url": (mirror + img_el["src"]) if img_el and img_el.get("src") else "",
                "location": "",
                "verified": False,
                "created_at": "",
                "source": f"nitter ({mirror})",
            }
            return data
        except Exception as e:
            debug and st.warning(f"Nitter {mirror}: {e}")
            continue
    return None

# ──────────────────────────────────────────────
# FxTwitter
# ──────────────────────────────────────────────
def fetch_fxtwitter_tweet(tweet_id: str) -> dict | None:
    try:
        url = f"{FXTWITTER_API}/status/{tweet_id}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        tweet = data.get("tweet", {})
        if not tweet:
            return None
        author = tweet.get("author", {})
        return {
            "id": tweet_id,
            "text": tweet.get("text", ""),
            "created_at": tweet.get("created_at", ""),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "views": tweet.get("views", 0),
            "author_name": author.get("name", ""),
            "author_screen_name": author.get("screen_name", ""),
            "author_avatar": author.get("avatar_url", ""),
            "media": tweet.get("media", {}).get("photos", []),
            "source": "fxtwitter",
        }
    except Exception as e:
        return None

# ──────────────────────────────────────────────
# Gemini
# ──────────────────────────────────────────────
def get_gemini_model(api_key: str, model_name: str):
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"خطأ في Gemini: {e}")
        return None

def gemini_generate(model, prompt: str, images: list = None) -> str:
    try:
        import google.generativeai as genai
        content = [prompt]
        if images:
            for img_data in images:
                content.append({
                    "mime_type": "image/jpeg",
                    "data": img_data,
                })
        response = model.generate_content(content)
        return response.text
    except Exception as e:
        return f"❌ خطأ Gemini: {e}"

# ──────────────────────────────────────────────
# رسم بطاقة الملف الشخصي
# ──────────────────────────────────────────────
def render_profile_card(data: dict, featured_img_b64: str = None):
    name = data.get("name", "غير معروف")
    screen_name = data.get("screen_name", "")
    description = data.get("description", "")
    followers = format_number(data.get("followers_count", 0))
    following = format_number(data.get("following_count", 0))
    tweets = format_number(data.get("tweet_count", 0))
    location = data.get("location", "")
    created = format_date(data.get("created_at", ""))
    verified = data.get("verified", False)
    source = data.get("source", "")
    profile_img_url = data.get("profile_image_url", "")

    # صورة المستخدم المرفوعة
    if featured_img_b64:
        st.markdown(f"""
        <div class="featured-image-container">
            <img src="data:image/jpeg;base64,{featured_img_b64}" alt="صورة الحساب">
        </div>
        """, unsafe_allow_html=True)

    # صورة البروفايل + الاسم
    avatar_html = ""
    if profile_img_url:
        profile_b64 = img_url_to_base64(profile_img_url)
        if profile_b64:
            avatar_html = f'<img src="data:image/jpeg;base64,{profile_b64}" style="width:80px;height:80px;border-radius:50%;border:3px solid #238636;margin-left:1rem;">'

    verified_badge = "✅ " if verified else ""
    st.markdown(f"""
    <div class="profile-card">
        <div style="display:flex;align-items:center;margin-bottom:1rem;">
            {avatar_html}
            <div>
                <h2 style="color:#e6edf3;margin:0;">{verified_badge}{name}</h2>
                <span style="color:#58a6ff;font-size:1rem;">@{screen_name}</span>
                {f'<span style="color:#8b949e;font-size:0.85rem;margin-right:0.5rem;">📍 {location}</span>' if location else ''}
            </div>
        </div>
        {f'<p style="color:#c9d1d9;line-height:1.7;direction:rtl;">{description}</p>' if description else ''}
        <hr style="border-color:#30363d;margin:1rem 0;">
        <div style="display:flex;gap:1rem;flex-wrap:wrap;justify-content:center;">
            <div class="stat-box"><div class="stat-number">{followers}</div><div class="stat-label">متابع</div></div>
            <div class="stat-box"><div class="stat-number">{following}</div><div class="stat-label">يتابع</div></div>
            <div class="stat-box"><div class="stat-number">{tweets}</div><div class="stat-label">تغريدة</div></div>
        </div>
        {f'<p style="color:#8b949e;font-size:0.8rem;margin-top:1rem;text-align:center;">📅 انضم: {created}</p>' if created else ''}
        <p style="color:#30363d;font-size:0.75rem;text-align:center;margin-top:0.5rem;">المصدر: {source}</p>
    </div>
    """, unsafe_allow_html=True)

# ──────────────────────────────────────────────
# تبويب تحليل الحساب
# ──────────────────────────────────────────────
def account_tab(gemini_key: str, gemini_model: str, tw_user: str, tw_email: str, tw_pass: str):
    st.markdown("### 👤 تحليل حساب X")
    st.markdown('<div class="upload-hint">🖼 أضف صورة الحساب (اختياري)<br><small>اسحب وأفلت صورة البروفايل أو البانر — ستظهر فوق بطاقة الملف الشخصي</small></div>', unsafe_allow_html=True)

    uploaded_img = st.file_uploader(
        "",
        type=["jpg", "jpeg", "png", "webp"],
        key="account_img_upload",
        label_visibility="collapsed"
    )

    featured_img_b64 = None
    if uploaded_img:
        try:
            img = Image.open(uploaded_img)
            featured_img_b64 = pil_to_base64(img)
            st.success("✅ تم تحميل الصورة بنجاح")
        except Exception as e:
            st.error(f"❌ خطأ في الصورة: {e}")

    col1, col2 = st.columns([3, 1])
    with col1:
        username_input = st.text_input(
            "🔍 اسم المستخدم أو رابط الحساب",
            placeholder="@username أو https://x.com/username",
            key="account_username"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 تحليل", key="fetch_account", use_container_width=True)

    if fetch_btn and username_input:
        username = extract_username(username_input)
        if not username:
            st.error("❌ أدخل اسم مستخدم صحيح")
            return

        account_data = None

        # محاولة 1: twikit
        if tw_user and tw_pass and tw_email:
            with st.spinner("⏳ جارٍ الاتصال عبر twikit..."):
                try:
                    client, msg = asyncio.run(_twikit_login(tw_user, tw_email, tw_pass))
                    if client:
                        account_data = asyncio.run(_fetch_twikit_user(client, username))
                        if account_data:
                            st.success(f"✅ تم الجلب عبر twikit")
                    else:
                        st.warning(f"⚠️ {msg}")
                except Exception as e:
                    st.warning(f"⚠️ twikit: {e}")

        # محاولة 2: Nitter
        if not account_data:
            with st.spinner("⏳ جارٍ البحث عبر مرايا Nitter..."):
                account_data = fetch_nitter_data(username, debug=st.session_state.get("debug_mode", False))
                if account_data:
                    st.info("ℹ️ تم الجلب عبر Nitter")

        # إدخال يدوي إن فشل الجلب
        if not account_data:
            st.markdown('<div class="warning-box">⚠️ تعذّر جلب البيانات تلقائياً — استخدم الإدخال اليدوي أدناه</div>', unsafe_allow_html=True)

        with st.expander("✏️ إدخال البيانات يدوياً (دائماً يعمل)", expanded=not account_data):
            mcol1, mcol2 = st.columns(2)
            with mcol1:
                m_name = st.text_input("الاسم الكامل", value=account_data.get("name","") if account_data else "", key="m_name")
                m_screen = st.text_input("اسم المستخدم", value=account_data.get("screen_name", username) if account_data else username, key="m_screen")
                m_followers = st.text_input("المتابعون", value=str(account_data.get("followers_count","0")) if account_data else "0", key="m_followers")
                m_following = st.text_input("يتابع", value=str(account_data.get("following_count","0")) if account_data else "0", key="m_following")
            with mcol2:
                m_tweets = st.text_input("عدد التغريدات", value=str(account_data.get("tweet_count","0")) if account_data else "0", key="m_tweets")
                m_location = st.text_input("الموقع", value=account_data.get("location","") if account_data else "", key="m_location")
                m_created = st.text_input("تاريخ الإنشاء", value=account_data.get("created_at","") if account_data else "", key="m_created")
                m_verified = st.checkbox("حساب موثّق ✅", value=account_data.get("verified", False) if account_data else False, key="m_verified")
            m_bio = st.text_area("النبذة", value=account_data.get("description","") if account_data else "", height=100, key="m_bio")

            if st.button("💾 تأكيد البيانات اليدوية", key="confirm_manual"):
                account_data = {
                    "name": m_name, "screen_name": m_screen,
                    "description": m_bio, "followers_count": m_followers,
                    "following_count": m_following, "tweet_count": m_tweets,
                    "location": m_location, "created_at": m_created,
                    "verified": m_verified, "profile_image_url": "",
                    "source": "إدخال يدوي",
                }
                st.session_state["manual_account_data"] = account_data
                st.success("✅ تم حفظ البيانات")

        # استخدام البيانات المحفوظة
        if not account_data and "manual_account_data" in st.session_state:
            account_data = st.session_state["manual_account_data"]

        if account_data:
            render_profile_card(account_data, featured_img_b64)

            # تقرير Gemini
            if gemini_key and gemini_key not in ("", "AIza..."):
                st.markdown("---")
                st.markdown("### 🤖 تقرير استخباراتي بالذكاء الاصطناعي")

                images_for_gemini = []
                if featured_img_b64:
                    images_for_gemini.append(featured_img_b64)

                prompt = f"""أنت محلل استخباراتي متخصص. حلّل هذا الحساب على منصة X:

الاسم: {account_data.get('name','')}
المعرّف: @{account_data.get('screen_name','')}
النبذة: {account_data.get('description','')}
المتابعون: {account_data.get('followers_count',0)}
يتابع: {account_data.get('following_count',0)}
التغريدات: {account_data.get('tweet_count',0)}
الموقع: {account_data.get('location','')}
تاريخ الإنشاء: {account_data.get('created_at','')}
موثّق: {account_data.get('verified',False)}
{"(مرفق صورة للحساب)" if images_for_gemini else ""}

اكتب تقريراً استخباراتياً باللغة العربية يشمل:
1. 🔍 ملخص الهوية الرقمية
2. 📊 تحليل النشاط والتأثير
3. 🌍 المؤشرات الجغرافية
4. ⚠️ نقاط الاهتمام والمخاطر
5. 🔗 التوصيات والخطوات التالية"""

                if st.button("🚀 توليد التقرير الاستخباراتي", key="gen_report"):
                    with st.spinner("⏳ Gemini يُحلّل البيانات..."):
                        model = get_gemini_model(gemini_key, gemini_model)
                        if model:
                            report = gemini_generate(model, prompt, images_for_gemini if images_for_gemini else None)
                            st.markdown(f'<div class="report-section">{report}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# تبويب تحليل التغريدة
# ──────────────────────────────────────────────
def tweet_tab(gemini_key: str, gemini_model: str):
    st.markdown("### 🐦 تحليل تغريدة")

    col1, col2 = st.columns([3, 1])
    with col1:
        tweet_input = st.text_input(
            "🔗 رابط أو معرّف التغريدة",
            placeholder="https://x.com/user/status/123456789 أو معرّف رقمي",
            key="tweet_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 جلب", key="fetch_tweet", use_container_width=True)

    if fetch_btn and tweet_input:
        tweet_id = extract_tweet_id(tweet_input)
        if not tweet_id:
            st.error("❌ لم أتمكن من استخراج معرّف التغريدة")
            return

        with st.spinner("⏳ جارٍ جلب التغريدة..."):
            tweet = fetch_fxtwitter_tweet(tweet_id)

        if not tweet:
            st.error("❌ تعذّر جلب التغريدة — تحقق من الرابط")
            return

        st.success("✅ تم جلب التغريدة")

        # معلومات المؤلف
        st.markdown(f"""
        <div class="profile-card">
            <b style="color:#58a6ff;">@{tweet.get('author_screen_name','')}</b>
            <span style="color:#8b949e;"> — {tweet.get('author_name','')}</span>
        </div>
        """, unsafe_allow_html=True)

        # نص التغريدة
        st.markdown("#### 📝 نص المنشور")
        st.text_area(
            "",
            value=tweet.get("text", ""),
            height=120,
            label_visibility="collapsed",
            key="tweet_text_display"
        )

        # الإحصاءات
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("❤️ إعجابات", format_number(tweet.get("likes", 0)))
        c2.metric("🔁 إعادة نشر", format_number(tweet.get("retweets", 0)))
        c3.metric("💬 ردود", format_number(tweet.get("replies", 0)))
        c4.metric("👁 مشاهدات", format_number(tweet.get("views", 0)))

        # صور التغريدة
        media_photos = tweet.get("media", [])
        if media_photos:
            st.markdown("#### 🖼 الصور")

        # رفع صورة للتحليل
        st.markdown("---")
        st.markdown("#### 🔬 تحليل الصور بالذكاء الاصطناعي")
        uploaded_imgs = st.file_uploader(
            "ارفع صورة أو أكثر للتحليل",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="tweet_img_upload"
        )

        if uploaded_imgs and gemini_key and gemini_key not in ("", "AIza..."):
            if st.button("🔬 تحليل الصور", key="analyze_images"):
                images_b64 = []
                for uf in uploaded_imgs:
                    try:
                        img = Image.open(uf)
                        images_b64.append(pil_to_base64(img))
                    except Exception as e:
                        st.warning(f"تخطي صورة: {e}")

                if images_b64:
                    points_text = "\n".join([f"{i+1}. {p}" for i, p in enumerate(IMAGE_ANALYSIS_POINTS)])
                    prompt = f"""حلّل الصور المرفقة من منظور استخباراتي وأمني دقيق.

ركّز على النقاط التالية:
{points_text}

اكتب تقريراً مفصلاً باللغة العربية لكل نقطة."""

                    with st.spinner("⏳ Gemini يُحلّل الصور..."):
                        model = get_gemini_model(gemini_key, gemini_model)
                        if model:
                            result = gemini_generate(model, prompt, images_b64)
                            st.markdown(f'<div class="report-section">{result}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# الشريط الجانبي
# ──────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ الإعدادات")
        st.markdown("---")

        # Gemini
        st.markdown("### 🤖 Gemini AI")
        gemini_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاح من: https://aistudio.google.com/apikey",
            key="gemini_api_key"
        )
        gemini_model = st.selectbox(
            "🧠 النموذج",
            ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
            key="gemini_model_select"
        )

        st.markdown("---")

        # twikit
        st.markdown("### 🐦 حساب X (لـ twikit)")

        # تحقق من توفر twikit
        twikit_ok, twikit_ver = _check_twikit_available()
        if twikit_ok:
            st.caption(f"✅ twikit v{twikit_ver}")
        else:
            st.markdown(f'<div class="error-box">❌ twikit غير متوفر: {twikit_ver}</div>', unsafe_allow_html=True)

        tw_user = st.text_input("👤 اسم المستخدم", placeholder="your_username (بدون @)", key="tw_username")
        tw_email = st.text_input("📧 البريد الإلكتروني", placeholder="your@email.com", key="tw_email")
        tw_pass = st.text_input("🔒 كلمة المرور", type="password", placeholder="••••••••", key="tw_password")

        # زر تأكيد الدخول
        if st.button("🔐 تأكيد الدخول", key="test_login", use_container_width=True):
            if tw_user and tw_email and tw_pass:
                with st.spinner("⏳ جارٍ التحقق..."):
                    try:
                        ok, msg = asyncio.run(_twikit_login_test(tw_user, tw_email, tw_pass))
                        if ok:
                            st.success(msg)
                            st.session_state["twikit_session"] = True
                        else:
                            st.error(msg)
                            st.session_state["twikit_session"] = False
                    except Exception as e:
                        st.error(f"❌ خطأ: {e}")
            else:
                st.warning("⚠️ أدخل جميع البيانات")

        # حالة الجلسة
        if os.path.exists(COOKIES_PATH):
            st.markdown('<div class="success-box">🟢 جلسة محفوظة — سيُعاد استخدامها تلقائياً</div>', unsafe_allow_html=True)
            if st.button("🗑 حذف الجلسة", key="del_session", use_container_width=True):
                os.remove(COOKIES_PATH)
                st.session_state.pop("twikit_session", None)
                st.success("✅ تم حذف الجلسة")
                st.rerun()
        else:
            st.caption("⚪ لا توجد جلسة — سيتم تسجيل الدخول عند الطلب")
            st.caption("يُنصح باستخدام حساب ثانوي. لن يتم نشر أي شيء.")

        st.markdown("---")

        # وضع التشخيص
        st.markdown("### 🔬 وضع التشخيص")
        debug = st.checkbox("تفعيل وضع التشخيص", key="debug_mode")
        if debug:
            st.markdown('<div class="warning-box">⚠️ وضع التشخيص مفعّل — ستظهر معلومات تقنية إضافية</div>', unsafe_allow_html=True)

        return gemini_key, gemini_model, tw_user, tw_email, tw_pass

# ──────────────────────────────────────────────
# الدالة الرئيسية
# ──────────────────────────────────────────────
def main():
    # العنوان الرئيسي
    st.markdown("""
    <div style="text-align:center;padding:1rem 0 0.5rem;">
        <h1 style="color:#58a6ff;font-size:2.2rem;margin:0;">🔍 محلل حسابات X</h1>
        <p style="color:#8b949e;font-size:0.9rem;">أداة تحليل استخباراتي لحسابات ومنشورات منصة X • v9.3</p>
    </div>
    """, unsafe_allow_html=True)

    # الشريط الجانبي
    gemini_key, gemini_model, tw_user, tw_email, tw_pass = render_sidebar()

    # التبويبات
    tab1, tab2 = st.tabs(["👤 تحليل حساب X", "🐦 تحليل تغريدة"])

    with tab1:
        account_tab(gemini_key, gemini_model, tw_user, tw_email, tw_pass)

    with tab2:
        tweet_tab(gemini_key, gemini_model)

# ──────────────────────────────────────────────
if __name__ == "__main__":
    main()
