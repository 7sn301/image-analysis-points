# ============================================================
# محلل حسابات X  - v9.4
# بدون twikit — Nitter + FxTwitter + Gemini
# ============================================================

import streamlit as st
import requests
import re
import os
import json
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# إعداد الصفحة
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────
# CSS
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

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    border-left: 1px solid #30363d;
}
[data-testid="stSidebar"] * { direction: rtl; text-align: right; }

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
    box-shadow: 0 4px 12px rgba(46,160,67,0.4);
}

.stTextInput input, .stTextArea textarea {
    background: #21262d !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    direction: rtl !important;
}

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
    display: inline-block;
    min-width: 100px;
}

.stat-number { font-size: 1.8rem; font-weight: 700; color: #3fb950; }
.stat-label  { font-size: 0.85rem; color: #8b949e; }

.featured-image-container {
    width: 100%;
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 1.5rem;
    border: 2px solid #30363d;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    max-height: 420px;
}
.featured-image-container img { width:100%; object-fit:cover; display:block; }

.upload-hint {
    border: 2px dashed #30363d;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
    color: #8b949e;
    margin: 0.5rem 0;
    background: rgba(255,255,255,0.02);
}

.info-box    { background:rgba(56,139,253,0.1);  border:1px solid #1f6feb;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; }
.success-box { background:rgba(46,160,67,0.1);   border:1px solid #238636;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; }
.error-box   { background:rgba(248,81,73,0.1);   border:1px solid #da3633;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; }
.warning-box { background:rgba(210,153,34,0.1);  border:1px solid #d29922;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; }

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

.report-section {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    direction: rtl;
    line-height: 1.9;
    white-space: pre-wrap;
}

[data-testid="stMetric"] {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 0.8rem;
}

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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
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
    return re.sub(r'\s+', ' ', text).strip()

def extract_username(s: str) -> str:
    s = s.strip()
    m = re.search(r'(?:twitter|x)\.com/([A-Za-z0-9_]+)', s)
    if m:
        return m.group(1)
    return s.lstrip("@")

def extract_tweet_id(s: str) -> str:
    s = s.strip()
    m = re.search(r'/status/(\d+)', s)
    if m:
        return m.group(1)
    if s.isdigit():
        return s
    return ""

def format_number(n) -> str:
    try:
        n = int(str(n).replace(",", "").replace(".", "").replace("K","000").replace("M","000000"))
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except:
        return str(n) if n else "0"

def format_date(d: str) -> str:
    if not d:
        return ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(d, fmt).strftime("%d/%m/%Y %H:%M")
        except:
            pass
    return d[:16]

def pil_to_base64(img: Image.Image) -> str:
    if img.mode in ("RGBA", "P", "LA", "CMYK"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def url_to_base64(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENTS[0]}, timeout=10)
        if r.status_code == 200:
            return pil_to_base64(Image.open(BytesIO(r.content)))
    except:
        pass
    return ""

# ──────────────────────────────────────────────
# Nitter
# ──────────────────────────────────────────────
def fetch_nitter(username: str, debug: bool = False) -> dict | None:
    headers = {
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ar,en;q=0.9",
    }
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=14)
            if r.status_code != 200:
                if debug:
                    st.caption(f"⚠️ {mirror}: HTTP {r.status_code}")
                continue
            txt = r.text
            if any(x in txt.lower() for x in ["anubis", "checking your browser", "ddos-guard"]):
                if debug:
                    st.caption(f"⚠️ {mirror}: Bot Protection")
                continue

            soup = BeautifulSoup(txt, "html.parser")

            name_el   = soup.select_one(".profile-card-fullname, .fullname, h1.fullname")
            screen_el = soup.select_one(".profile-card-username, .username")
            bio_el    = soup.select_one(".profile-bio p, .bio p, .profile-bio")
            stats     = soup.select(".profile-stat-num, .stats .stat-num, .profile-stat .profile-stat-num")
            img_el    = soup.select_one(".profile-card-avatar img, .avatar img, .profile-avatar img")

            if not name_el:
                if debug:
                    st.caption(f"⚠️ {mirror}: لم يُعثر على اسم")
                continue

            profile_img = ""
            if img_el and img_el.get("src"):
                src = img_el["src"]
                profile_img = (mirror + src) if src.startswith("/") else src

            data = {
                "name":            clean_text(name_el.get_text()),
                "screen_name":     clean_text(screen_el.get_text()).lstrip("@") if screen_el else username,
                "description":     clean_text(bio_el.get_text()) if bio_el else "",
                "followers_count": clean_text(stats[0].get_text()) if len(stats) > 0 else "0",
                "following_count": clean_text(stats[1].get_text()) if len(stats) > 1 else "0",
                "tweet_count":     clean_text(stats[2].get_text()) if len(stats) > 2 else "0",
                "profile_image_url": profile_img,
                "location":        "",
                "verified":        False,
                "created_at":      "",
                "source":          f"Nitter ({mirror})",
            }
            if debug:
                st.caption(f"✅ {mirror}: نجح الجلب")
            return data

        except Exception as e:
            if debug:
                st.caption(f"❌ {mirror}: {e}")
            continue
    return None

# ──────────────────────────────────────────────
# FxTwitter
# ──────────────────────────────────────────────
def fetch_fxtwitter(tweet_id: str) -> dict | None:
    try:
        r = requests.get(f"{FXTWITTER_API}/status/{tweet_id}", timeout=15)
        if r.status_code != 200:
            return None
        tw = r.json().get("tweet", {})
        if not tw:
            return None
        author = tw.get("author", {})
        return {
            "id":                  tweet_id,
            "text":                tw.get("text", ""),
            "created_at":          tw.get("created_at", ""),
            "likes":               tw.get("likes", 0),
            "retweets":            tw.get("retweets", 0),
            "replies":             tw.get("replies", 0),
            "views":               tw.get("views", 0),
            "author_name":         author.get("name", ""),
            "author_screen_name":  author.get("screen_name", ""),
            "author_avatar":       author.get("avatar_url", ""),
            "media_photos":        tw.get("media", {}).get("photos", []),
            "source":              "FxTwitter",
        }
    except:
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
        st.error(f"❌ خطأ Gemini: {e}")
        return None

def gemini_text(model, prompt: str) -> str:
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"❌ خطأ: {e}"

def gemini_with_images(model, prompt: str, images_b64: list) -> str:
    try:
        import google.generativeai as genai
        parts = [prompt]
        for b64 in images_b64:
            parts.append({"mime_type": "image/jpeg", "data": b64})
        return model.generate_content(parts).text
    except Exception as e:
        return f"❌ خطأ: {e}"

# ──────────────────────────────────────────────
# بطاقة الملف الشخصي
# ──────────────────────────────────────────────
def render_profile_card(data: dict, featured_b64: str = None):
    name        = data.get("name", "غير معروف")
    screen_name = data.get("screen_name", "")
    description = data.get("description", "")
    followers   = format_number(data.get("followers_count", 0))
    following   = format_number(data.get("following_count", 0))
    tweets      = format_number(data.get("tweet_count", 0))
    location    = data.get("location", "")
    created     = format_date(data.get("created_at", ""))
    verified    = data.get("verified", False)
    source      = data.get("source", "")
    profile_url = data.get("profile_image_url", "")

    # صورة مرفوعة كبيرة
    if featured_b64:
        st.markdown(f"""
        <div class="featured-image-container">
            <img src="data:image/jpeg;base64,{featured_b64}" alt="صورة الحساب">
        </div>""", unsafe_allow_html=True)

    # صورة بروفايل
    avatar_html = ""
    if profile_url:
        b64 = url_to_base64(profile_url)
        if b64:
            avatar_html = f'<img src="data:image/jpeg;base64,{b64}" style="width:80px;height:80px;border-radius:50%;border:3px solid #238636;margin-left:1rem;flex-shrink:0;">'

    badge = "✅ " if verified else ""
    loc_html   = f'<div style="color:#8b949e;font-size:0.85rem;">📍 {location}</div>' if location else ""
    stats_html = f"""
    <div style="display:flex;gap:0.8rem;flex-wrap:wrap;justify-content:center;margin-top:1rem;">
        <div class="stat-box"><div class="stat-number">{followers}</div><div class="stat-label">متابع</div></div>
        <div class="stat-box"><div class="stat-number">{following}</div><div class="stat-label">يتابع</div></div>
        <div class="stat-box"><div class="stat-number">{tweets}</div><div class="stat-label">تغريدة</div></div>
    </div>"""
    bio_html    = f'<p style="color:#c9d1d9;line-height:1.7;margin-top:0.8rem;">{description}</p>' if description else ""
    date_html   = f'<p style="color:#8b949e;font-size:0.8rem;text-align:center;margin-top:0.8rem;">📅 انضم: {created}</p>' if created else ""
    source_html = f'<p style="color:#30363d;font-size:0.75rem;text-align:center;">المصدر: {source}</p>'

    st.markdown(f"""
    <div class="profile-card">
        <div style="display:flex;align-items:center;margin-bottom:0.5rem;">
            {avatar_html}
            <div style="flex:1;">
                <h2 style="color:#e6edf3;margin:0;font-size:1.4rem;">{badge}{name}</h2>
                <span style="color:#58a6ff;font-size:1rem;">@{screen_name}</span>
                {loc_html}
            </div>
        </div>
        {bio_html}
        <hr style="border-color:#30363d;margin:0.8rem 0;">
        {stats_html}
        {date_html}
        {source_html}
    </div>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# تبويب تحليل الحساب
# ──────────────────────────────────────────────
def account_tab(gemini_key: str, gemini_model_name: str):
    st.markdown("### 👤 تحليل حساب X")

    # رفع صورة
    st.markdown("""
    <div class="upload-hint">
        🖼 أضف صورة الحساب (اختياري)
        <br><small>اسحب وأفلت صورة البروفايل أو البانر — ستظهر فوق بطاقة الملف الشخصي</small>
    </div>""", unsafe_allow_html=True)

    up_img = st.file_uploader(
        "رفع صورة",
        type=["jpg","jpeg","png","webp"],
        key="acc_img",
        label_visibility="collapsed"
    )
    featured_b64 = None
    if up_img:
        try:
            featured_b64 = pil_to_base64(Image.open(up_img))
            st.success("✅ تم تحميل الصورة")
        except Exception as e:
            st.error(f"❌ خطأ في الصورة: {e}")

    # حقل البحث
    col1, col2 = st.columns([3, 1])
    with col1:
        uname_input = st.text_input(
            "🔍 اسم المستخدم أو رابط الحساب",
            placeholder="@username أو https://x.com/username",
            key="acc_uname"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 تحليل", key="btn_fetch_acc", use_container_width=True)

    account_data = st.session_state.get("account_data_cache")

    if fetch_btn and uname_input:
        username = extract_username(uname_input)
        if not username:
            st.error("❌ أدخل اسم مستخدم صحيح")
            return

        account_data = None
        debug = st.session_state.get("debug_mode", False)

        with st.spinner("⏳ جارٍ البحث عبر مرايا Nitter..."):
            account_data = fetch_nitter(username, debug=debug)

        if account_data:
            st.success(f"✅ تم جلب البيانات — المصدر: {account_data['source']}")
            st.session_state["account_data_cache"] = account_data
        else:
            st.markdown('<div class="warning-box">⚠️ تعذّر جلب البيانات تلقائياً — استخدم الإدخال اليدوي أدناه</div>', unsafe_allow_html=True)

    # إدخال يدوي
    with st.expander("✏️ إدخال البيانات يدوياً (دائماً يعمل)", expanded=not account_data):
        c1, c2 = st.columns(2)
        with c1:
            m_name      = st.text_input("الاسم الكامل",     value=account_data.get("name","")            if account_data else "", key="m_name")
            m_screen    = st.text_input("اسم المستخدم",     value=account_data.get("screen_name","")     if account_data else "", key="m_screen")
            m_followers = st.text_input("المتابعون",        value=str(account_data.get("followers_count","0")) if account_data else "0", key="m_followers")
            m_following = st.text_input("يتابع",            value=str(account_data.get("following_count","0")) if account_data else "0", key="m_following")
        with c2:
            m_tweets    = st.text_input("عدد التغريدات",    value=str(account_data.get("tweet_count","0")) if account_data else "0", key="m_tweets")
            m_location  = st.text_input("الموقع",           value=account_data.get("location","")        if account_data else "", key="m_location")
            m_created   = st.text_input("تاريخ الإنشاء",   value=account_data.get("created_at","")      if account_data else "", key="m_created")
            m_verified  = st.checkbox("حساب موثّق ✅",      value=account_data.get("verified",False)     if account_data else False, key="m_verified")
        m_bio = st.text_area("النبذة", value=account_data.get("description","") if account_data else "", height=100, key="m_bio")

        if st.button("💾 تأكيد البيانات", key="btn_manual"):
            account_data = {
                "name": m_name, "screen_name": m_screen,
                "description": m_bio,
                "followers_count": m_followers, "following_count": m_following,
                "tweet_count": m_tweets, "location": m_location,
                "created_at": m_created, "verified": m_verified,
                "profile_image_url": "", "source": "إدخال يدوي",
            }
            st.session_state["account_data_cache"] = account_data
            st.success("✅ تم حفظ البيانات")

    # عرض البطاقة
    if account_data:
        render_profile_card(account_data, featured_b64)

        # تقرير Gemini
        if gemini_key and len(gemini_key) > 10:
            st.markdown("---")
            st.markdown("### 🤖 التقرير الاستخباراتي")

            imgs_for_gemini = [featured_b64] if featured_b64 else []

            prompt = f"""أنت محلل استخباراتي متخصص في تحليل حسابات منصة X (تويتر).

بيانات الحساب:
• الاسم: {account_data.get('name','')}
• المعرّف: @{account_data.get('screen_name','')}
• النبذة: {account_data.get('description','')}
• المتابعون: {account_data.get('followers_count',0)}
• يتابع: {account_data.get('following_count',0)}
• التغريدات: {account_data.get('tweet_count',0)}
• الموقع: {account_data.get('location','')}
• تاريخ الإنشاء: {account_data.get('created_at','')}
• موثّق: {account_data.get('verified',False)}
{"• (مرفق صورة للتحليل البصري)" if imgs_for_gemini else ""}

اكتب تقريراً استخباراتياً شاملاً باللغة العربية يتضمن:
1. 🔍 ملخص الهوية الرقمية
2. 📊 تحليل النشاط والتأثير (نسبة المتابعين/يتابع، معدل التغريدات)
3. 🌍 المؤشرات الجغرافية والانتماءات المحتملة
4. 🎭 تقييم مصداقية الحساب (حقيقي/مشبوه/بوت)
5. ⚠️ نقاط الاهتمام والمخاطر
6. 🔗 التوصيات والخطوات التالية للتحقيق"""

            if st.button("🚀 توليد التقرير الاستخباراتي", key="btn_report"):
                with st.spinner("⏳ Gemini يحلّل البيانات..."):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        if imgs_for_gemini:
                            result = gemini_with_images(model, prompt, imgs_for_gemini)
                        else:
                            result = gemini_text(model, prompt)
                        st.markdown(f'<div class="report-section">{result}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="info-box">💡 أضف مفتاح Gemini في الشريط الجانبي لتوليد تقرير استخباراتي تلقائي</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# تبويب تحليل التغريدة
# ──────────────────────────────────────────────
def tweet_tab(gemini_key: str, gemini_model_name: str):
    st.markdown("### 🐦 تحليل تغريدة")

    col1, col2 = st.columns([3, 1])
    with col1:
        tw_input = st.text_input(
            "🔗 رابط أو معرّف التغريدة",
            placeholder="https://x.com/user/status/123456789",
            key="tw_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 جلب", key="btn_fetch_tw", use_container_width=True)

    tweet_data = st.session_state.get("tweet_data_cache")

    if fetch_btn and tw_input:
        tid = extract_tweet_id(tw_input)
        if not tid:
            st.error("❌ لم أتمكن من استخراج معرّف التغريدة")
            return
        with st.spinner("⏳ جارٍ جلب التغريدة..."):
            tweet_data = fetch_fxtwitter(tid)
        if tweet_data:
            st.success("✅ تم جلب التغريدة")
            st.session_state["tweet_data_cache"] = tweet_data
        else:
            st.error("❌ تعذّر جلب التغريدة — تحقق من الرابط أو أدخل البيانات يدوياً")

    # إدخال يدوي للتغريدة
    with st.expander("✏️ إدخال بيانات التغريدة يدوياً", expanded=not tweet_data):
        m_text    = st.text_area("نص التغريدة", value=tweet_data.get("text","") if tweet_data else "", height=120, key="m_tw_text")
        mc1, mc2  = st.columns(2)
        with mc1:
            m_author  = st.text_input("اسم المؤلف",     value=tweet_data.get("author_name","")        if tweet_data else "", key="m_tw_author")
            m_likes   = st.text_input("الإعجابات",      value=str(tweet_data.get("likes",0))           if tweet_data else "0", key="m_tw_likes")
            m_rts     = st.text_input("إعادة النشر",    value=str(tweet_data.get("retweets",0))        if tweet_data else "0", key="m_tw_rts")
        with mc2:
            m_replies = st.text_input("الردود",         value=str(tweet_data.get("replies",0))         if tweet_data else "0", key="m_tw_replies")
            m_views   = st.text_input("المشاهدات",      value=str(tweet_data.get("views",0))           if tweet_data else "0", key="m_tw_views")
            m_date    = st.text_input("تاريخ النشر",    value=tweet_data.get("created_at","")          if tweet_data else "", key="m_tw_date")

        if st.button("💾 تأكيد بيانات التغريدة", key="btn_tw_manual"):
            tweet_data = {
                "text": m_text, "author_name": m_author,
                "likes": m_likes, "retweets": m_rts,
                "replies": m_replies, "views": m_views,
                "created_at": m_date, "media_photos": [],
                "source": "إدخال يدوي",
            }
            st.session_state["tweet_data_cache"] = tweet_data
            st.success("✅ تم حفظ بيانات التغريدة")

    if tweet_data:
        # معلومات المؤلف
        author_name   = tweet_data.get("author_name","")
        author_screen = tweet_data.get("author_screen_name","")
        created       = format_date(tweet_data.get("created_at",""))

        if author_name or author_screen:
            st.markdown(f"""
            <div class="profile-card" style="padding:1rem;">
                <b style="color:#58a6ff;">@{author_screen}</b>
                <span style="color:#c9d1d9;"> — {author_name}</span>
                {f'<span style="color:#8b949e;font-size:0.85rem;"> · {created}</span>' if created else ''}
            </div>""", unsafe_allow_html=True)

        # نص التغريدة
        st.markdown("#### 📝 نص المنشور")
        st.text_area(
            "tweet_text",
            value=tweet_data.get("text", ""),
            height=130,
            label_visibility="collapsed",
            key="tw_text_view"
        )

        # الإحصاءات
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("❤️ إعجابات",    format_number(tweet_data.get("likes", 0)))
        c2.metric("🔁 إعادة نشر",  format_number(tweet_data.get("retweets", 0)))
        c3.metric("💬 ردود",       format_number(tweet_data.get("replies", 0)))
        c4.metric("👁 مشاهدات",    format_number(tweet_data.get("views", 0)))

        # صور التغريدة
        photos = tweet_data.get("media_photos", [])
        if photos:
            st.markdown("#### 🖼 صور التغريدة")
            img_cols = st.columns(min(len(photos), 3))
            for i, ph in enumerate(photos[:3]):
                url = ph.get("url","") if isinstance(ph, dict) else str(ph)
                if url:
                    img_cols[i].image(url, use_container_width=True)

        # ─── تحليل الصور ───
        st.markdown("---")
        st.markdown("#### 🔬 تحليل الصور بالذكاء الاصطناعي")

        up_imgs = st.file_uploader(
            "ارفع صورة أو أكثر للتحليل",
            type=["jpg","jpeg","png","webp"],
            accept_multiple_files=True,
            key="tw_imgs_upload"
        )

        if up_imgs and gemini_key and len(gemini_key) > 10:
            if st.button("🔬 تحليل الصور", key="btn_analyze_imgs"):
                imgs_b64 = []
                for uf in up_imgs:
                    try:
                        imgs_b64.append(pil_to_base64(Image.open(uf)))
                    except Exception as e:
                        st.warning(f"تخطي صورة: {e}")

                if imgs_b64:
                    pts = "\n".join(f"{i+1}. {p}" for i, p in enumerate(IMAGE_ANALYSIS_POINTS))
                    prompt = f"""أنت محلل استخباراتي وخبير في تحليل الصور. حلّل الصور المرفقة بدقة.

نقاط التحليل المطلوبة:
{pts}

اكتب تقريراً مفصلاً باللغة العربية، تناول كل نقطة على حدة بعمق."""

                    with st.spinner("⏳ Gemini يحلّل الصور..."):
                        model = get_gemini_model(gemini_key, gemini_model_name)
                        if model:
                            result = gemini_with_images(model, prompt, imgs_b64)
                            st.markdown(f'<div class="report-section">{result}</div>', unsafe_allow_html=True)

        elif up_imgs and (not gemini_key or len(gemini_key) <= 10):
            st.markdown('<div class="info-box">💡 أضف مفتاح Gemini في الشريط الجانبي لتحليل الصور</div>', unsafe_allow_html=True)

        # ─── تحليل نص التغريدة بـ Gemini ───
        if gemini_key and len(gemini_key) > 10:
            st.markdown("---")
            if st.button("📝 تحليل نص التغريدة", key="btn_analyze_text"):
                tw_text = tweet_data.get("text","")
                if tw_text:
                    prompt = f"""حلّل هذه التغريدة من منصة X تحليلاً استخباراتياً:

النص: "{tw_text}"
المؤلف: {tweet_data.get('author_name','')} @{tweet_data.get('author_screen_name','')}
الإعجابات: {tweet_data.get('likes',0)} | إعادة النشر: {tweet_data.get('retweets',0)} | الردود: {tweet_data.get('replies',0)}
تاريخ النشر: {tweet_data.get('created_at','')}

التحليل المطلوب:
1. 🎯 الهدف والرسالة الرئيسية
2. 🌍 المؤشرات الجغرافية والسياقية
3. 😤 المشاعر والتوجه الأيديولوجي
4. 📣 مستوى التأثير والانتشار المحتمل
5. ⚠️ المخاطر والمؤشرات التحذيرية
6. 🔍 توصيات التحقيق"""

                    with st.spinner("⏳ Gemini يحلّل التغريدة..."):
                        model = get_gemini_model(gemini_key, gemini_model_name)
                        if model:
                            result = gemini_text(model, prompt)
                            st.markdown(f'<div class="report-section">{result}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# الشريط الجانبي
# ──────────────────────────────────────────────
def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("## ⚙️ الإعدادات")
        st.markdown("---")

        # Gemini
        st.markdown("### 🤖 Gemini AI")
        gemini_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاح مجاني من: https://aistudio.google.com/apikey",
            key="gemini_key"
        )
        if gemini_key and len(gemini_key) > 10:
            st.markdown('<div class="success-box">✅ مفتاح Gemini مُفعَّل</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="info-box">💡 <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#58a6ff;">احصل على مفتاح Gemini مجاني</a></div>', unsafe_allow_html=True)

        gemini_model_name = st.selectbox(
            "🧠 النموذج",
            ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-pro"],
            key="gemini_model"
        )

        st.markdown("---")

        # حالة twikit
        st.markdown("### ℹ️ حالة المصادر")
        st.markdown("""
        <div class="info-box">
            📡 <b>مصادر البيانات النشطة:</b><br>
            • ✅ Nitter Mirrors (بيانات الحسابات)<br>
            • ✅ FxTwitter API (بيانات التغريدات)<br>
            • ✅ إدخال يدوي (دائماً يعمل)<br>
            • ✅ Gemini AI (التحليل والتقارير)<br>
            <br>
            <small style="color:#8b949e;">⚠️ twikit مُعطَّل مؤقتاً — خطأ في المكتبة (KEY_BYTE)</small>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # وضع التشخيص
        st.markdown("### 🔬 التشخيص")
        st.checkbox("تفعيل وضع التشخيص", key="debug_mode")

        return gemini_key, gemini_model_name

# ──────────────────────────────────────────────
# الرئيسية
# ──────────────────────────────────────────────
def main():
    st.markdown("""
    <div style="text-align:center;padding:1.2rem 0 0.5rem;">
        <h1 style="color:#58a6ff;font-size:2.2rem;margin:0;">🔍 محلل حسابات X</h1>
        <p style="color:#8b949e;font-size:0.9rem;margin:0.3rem 0;">
            أداة تحليل لحسابات ومنشورات منصة X • v9.4
        </p>
    </div>
    """, unsafe_allow_html=True)

    gemini_key, gemini_model_name = render_sidebar()

    tab1, tab2 = st.tabs(["👤 تحليل حساب X", "🐦 تحليل تغريدة"])
    with tab1:
        account_tab(gemini_key, gemini_model_name)
    with tab2:
        tweet_tab(gemini_key, gemini_model_name)


if __name__ == "__main__":
    main()
