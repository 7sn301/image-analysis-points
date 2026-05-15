"""
═══════════════════════════════════════════════════════════════════════
  X (Twitter) Analysis App — v7.0
  تطبيق تحليل منصة X باستخدام الذكاء الاصطناعي (Gemini API)
═══════════════════════════════════════════════════════════════════════
  Tech Stack:
    • Streamlit (UI)
    • Google Gemini API (AI Analysis)
    • Requests + BeautifulSoup4 (Data Fetching)
    • Pillow (Image Processing)
  
  Data Sources Fallback Chain:
    Twitter Guest API → FxTwitter → Nitter Mirrors
═══════════════════════════════════════════════════════════════════════
"""

import streamlit as st
import requests
import json
import base64
import re
import time
import html
from io import BytesIO
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
import google.generativeai as genai


# ═══════════════════════════════════════════════════════════════════════
# 1) APP CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="X Analysis App v7",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# RTL + Theme Custom CSS
st.markdown(
    """
    <style>
        html, body, [class*="css"] {
            direction: rtl;
            text-align: right;
            font-family: 'Segoe UI', 'Tahoma', sans-serif;
        }
        .stButton > button {
            background-color: #1DA1F2;
            color: white;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1.5rem;
            font-weight: bold;
        }
        .stButton > button:hover {
            background-color: #0d8ddb;
        }
        .metric-card {
            background-color: #1a1d24;
            border-radius: 10px;
            padding: 1rem;
            border-left: 4px solid #1DA1F2;
        }
        h1, h2, h3 {
            color: #1DA1F2;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════════
# 2) CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════════════

NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
]

GEMINI_MODELS = {
    "gemini-1.5-flash": {"rpm": 15, "rpd": 1500, "supports_vision": True},
    "gemini-2.0-flash": {"rpm": 15, "rpd": 1500, "supports_vision": True},
    "gemini-1.5-flash-8b": {"rpm": 15, "rpd": 1500, "supports_vision": True},
    "gemini-1.0-pro": {"rpm": 15, "rpd": 1500, "supports_vision": False},
}

REQUEST_DELAY = 1.5
MAX_RETRIES = 3
TIMEOUT = 12

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ═══════════════════════════════════════════════════════════════════════
# 3) DATA FETCHING (3-LEVEL FALLBACK)
# ═══════════════════════════════════════════════════════════════════════

def clean_text(text: str) -> str:
    """تنظيف النصوص من رموز HTML والمسافات الزائدة."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_with_retry(url: str, headers: dict | None = None) -> requests.Response | None:
    """جلب URL مع آلية إعادة محاولة."""
    headers = headers or {"User-Agent": USER_AGENT}
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(REQUEST_DELAY)
            r = requests.get(url, headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            continue
    return None


# ── المستوى 1: Twitter Guest API ──────────────────────────────────────
def fetch_via_guest_api(username: str) -> dict | None:
    """جلب بيانات الحساب عبر Twitter Guest API."""
    try:
        # الحصول على Guest Token
        token_url = "https://api.twitter.com/1.1/guest/activate.json"
        bearer = (
            "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
            "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
        )
        headers = {"Authorization": bearer, "User-Agent": USER_AGENT}
        r = requests.post(token_url, headers=headers, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        guest_token = r.json().get("guest_token")

        # جلب بيانات المستخدم
        user_url = (
            "https://api.twitter.com/graphql/G3KGOASz96M-Qu0nwmGXNg/UserByScreenName"
            f'?variables={{"screen_name":"{username}","withSafetyModeUserFields":true}}'
        )
        headers["x-guest-token"] = guest_token
        r = requests.get(user_url, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


# ── المستوى 2: FxTwitter ──────────────────────────────────────────────
def fetch_via_fxtwitter(username: str, tweet_id: str | None = None) -> dict | None:
    """جلب بيانات منشور أو حساب عبر FxTwitter."""
    try:
        if tweet_id:
            url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
        else:
            url = f"https://api.fxtwitter.com/{username}"
        r = fetch_with_retry(url)
        if r and r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


# ── المستوى 3: Nitter Scraping ────────────────────────────────────────
def fetch_via_nitter(username: str) -> dict | None:
    """استخراج بيانات الحساب من Nitter كمصدر احتياطي."""
    for mirror in NITTER_MIRRORS:
        try:
            url = f"{mirror}/{username}"
            r = fetch_with_retry(url)
            if not r or r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            profile = soup.find("div", class_="profile-card")
            if not profile:
                continue

            name = soup.find("a", class_="profile-card-fullname")
            bio = soup.find("div", class_="profile-bio")
            stats = soup.find_all("li", class_="profile-stat")
            tweets = []

            for tweet_div in soup.find_all("div", class_="timeline-item")[:20]:
                content = tweet_div.find("div", class_="tweet-content")
                date = tweet_div.find("span", class_="tweet-date")
                if content:
                    tweets.append(
                        {
                            "text": clean_text(content.get_text()),
                            "date": date.find("a")["title"] if date and date.find("a") else "",
                        }
                    )

            return {
                "source": "nitter",
                "mirror": mirror,
                "name": clean_text(name.get_text()) if name else username,
                "bio": clean_text(bio.get_text()) if bio else "",
                "stats": [clean_text(s.get_text()) for s in stats],
                "tweets": tweets,
            }
        except Exception:
            continue
    return None


# ── الواجهة الموحدة ───────────────────────────────────────────────────
def fetch_user_data(username: str) -> tuple[dict | None, str]:
    """جلب بيانات المستخدم باستخدام Fallback Chain."""
    username = username.replace("@", "").strip()

    with st.spinner("🔍 جاري المحاولة عبر Twitter Guest API..."):
        data = fetch_via_guest_api(username)
        if data:
            return data, "twitter_guest_api"

    with st.spinner("🔄 الانتقال إلى FxTwitter..."):
        data = fetch_via_fxtwitter(username)
        if data:
            return data, "fxtwitter"

    with st.spinner("🔁 المصدر الاحتياطي: Nitter..."):
        data = fetch_via_nitter(username)
        if data:
            return data, "nitter"

    return None, "failed"


# ═══════════════════════════════════════════════════════════════════════
# 4) IMAGE PROCESSING
# ═══════════════════════════════════════════════════════════════════════

def process_image_to_base64(image_url: str, size: tuple = (400, 400)) -> str | None:
    """تحميل وتغيير حجم الصورة وتحويلها إلى Base64."""
    try:
        r = fetch_with_retry(image_url)
        if not r:
            return None
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail(size, Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# 5) GEMINI AI ANALYSIS
# ═══════════════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """
أنت محلل استخباراتي خبير متخصص في تحليل وسائل التواصل الاجتماعي (OSINT).
حلل بيانات حساب X التالية وأخرج تقريراً منظماً بصيغة JSON صالحة فقط:

البيانات:
{data}

أخرج JSON بالهيكل التالي حصراً (دون أي نص إضافي):
{{
    "executive_summary": "ملخص تنفيذي موجز (3-5 جمل)",
    "account_pattern": {{
        "type": "نوع الحساب (شخصي/تجاري/مؤسسي/إخباري/مؤثر/بوت محتمل)",
        "activity_level": "مستوى النشاط (منخفض/متوسط/عالي)",
        "main_topics": ["موضوع 1", "موضوع 2", "موضوع 3"]
    }},
    "credibility_indicators": {{
        "score": "0-100",
        "positive_signals": ["إشارة 1", "إشارة 2"],
        "red_flags": ["علامة تحذير 1", "علامة تحذير 2"]
    }},
    "intelligence_profile": {{
        "language": "اللغة الأساسية",
        "geographic_indicators": "مؤشرات جغرافية محتملة",
        "active_hours": "ساعات النشاط المتوقعة",
        "engagement_style": "أسلوب التفاعل"
    }},
    "political_orientation": "التوجه السياسي إن وجد (محايد/يمين/يسار/إسلامي/ليبرالي/قومي)",
    "observed_patterns": ["نمط 1", "نمط 2", "نمط 3"],
    "recommendations": ["توصية 1", "توصية 2"]
}}
"""


def init_gemini(api_key: str, model_name: str):
    """تهيئة عميل Gemini."""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def analyze_with_gemini(
    model, data: dict, images_b64: list[str] | None = None
) -> dict | None:
    """تحليل البيانات باستخدام Gemini."""
    try:
        prompt = ANALYSIS_PROMPT.format(data=json.dumps(data, ensure_ascii=False, indent=2))
        contents = [prompt]

        if images_b64:
            for b64 in images_b64[:4]:  # حد أقصى 4 صور
                contents.append({"mime_type": "image/jpeg", "data": b64})

        response = model.generate_content(contents)
        text = response.text.strip()

        # تنظيف JSON من أي ```json ... ```
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": response.text if "response" in locals() else ""}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════
# 6) UI — STREAMLIT INTERFACE
# ═══════════════════════════════════════════════════════════════════════

def render_sidebar():
    """شريط جانبي للإعدادات."""
    with st.sidebar:
        st.markdown("## ⚙️ الإعدادات")
        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            help="احصل عليه من https://aistudio.google.com/apikey",
        )
        model_name = st.selectbox(
            "🤖 نموذج Gemini",
            options=list(GEMINI_MODELS.keys()),
            index=0,
        )
        st.markdown("---")
        st.markdown("### 📊 معلومات النموذج")
        info = GEMINI_MODELS[model_name]
        st.markdown(f"- **RPM:** {info['rpm']}")
        st.markdown(f"- **RPD:** {info['rpd']}")
        st.markdown(f"- **رؤية:** {'✅' if info['supports_vision'] else '❌'}")
        st.markdown("---")
        st.caption("Version 7.0 — May 2026")
        return api_key, model_name


def render_metrics(data: dict, source: str):
    """عرض الإحصائيات الأساسية."""
    cols = st.columns(4)
    with cols[0]:
        st.metric("📡 المصدر", source.replace("_", " ").title())
    with cols[1]:
        st.metric("📝 المنشورات", len(data.get("tweets", [])))
    with cols[2]:
        bio_len = len(data.get("bio", ""))
        st.metric("📄 طول الوصف", f"{bio_len} حرف")
    with cols[3]:
        st.metric("🕐 وقت الجلب", datetime.now().strftime("%H:%M:%S"))


def render_analysis_result(result: dict):
    """عرض نتائج التحليل بشكل بصري."""
    if "error" in result:
        st.error(f"❌ خطأ في التحليل: {result['error']}")
        return
    if "raw_response" in result:
        st.warning("⚠️ تعذر تحليل JSON، عرض الرد الخام:")
        st.code(result["raw_response"])
        return

    # الملخص التنفيذي
    st.markdown("### 📋 الملخص التنفيذي")
    st.info(result.get("executive_summary", "غير متوفر"))

    # نمط الحساب
    pattern = result.get("account_pattern", {})
    st.markdown("### 🎭 نمط الحساب")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**النوع:** {pattern.get('type', '-')}")
    c2.markdown(f"**النشاط:** {pattern.get('activity_level', '-')}")
    c3.markdown(f"**المواضيع:** {', '.join(pattern.get('main_topics', []))}")

    # المصداقية
    cred = result.get("credibility_indicators", {})
    st.markdown("### ✅ مؤشرات المصداقية")
    score = int(cred.get("score", "0").split("-")[0]) if isinstance(cred.get("score"), str) else int(cred.get("score", 0))
    st.progress(min(score, 100) / 100, text=f"درجة المصداقية: {score}/100")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**✔️ إشارات إيجابية:**")
        for s in cred.get("positive_signals", []):
            st.markdown(f"- {s}")
    with pc2:
        st.markdown("**⚠️ علامات تحذير:**")
        for s in cred.get("red_flags", []):
            st.markdown(f"- {s}")

    # ملف الاستخبارات
    intel = result.get("intelligence_profile", {})
    st.markdown("### 🌐 التعريفات الاستخباراتية")
    st.json(intel)

    # التوجه السياسي
    st.markdown("### 🏛️ التوجه السياسي")
    st.markdown(f"**{result.get('political_orientation', 'غير محدد')}**")

    # الأنماط
    st.markdown("### 🔍 الأنماط الملاحظة")
    for p in result.get("observed_patterns", []):
        st.markdown(f"- {p}")

    # التوصيات
    st.markdown("### 💡 التوصيات")
    for r in result.get("recommendations", []):
        st.success(r)

    # JSON كامل
    with st.expander("📦 عرض JSON الكامل"):
        st.json(result)


# ═══════════════════════════════════════════════════════════════════════
# 7) MAIN APP
# ═══════════════════════════════════════════════════════════════════════

def main():
    st.title("🐦 تطبيق تحليل منصة X — الإصدار 7.0")
    st.caption("تحليل ذكي للحسابات والمنشورات باستخدام Gemini AI + OSINT Fallback Chain")

    api_key, model_name = render_sidebar()

    tab1, tab2 = st.tabs(["🔎 تحليل حساب", "📝 تحليل منشور"])

    # ── تبويب تحليل حساب ────────────────────────────────────────────
    with tab1:
        username = st.text_input(
            "اسم المستخدم على X",
            placeholder="@username أو username",
            key="account_user",
        )
        analyze_images = st.checkbox("🖼️ تضمين تحليل صورة الملف الشخصي", value=False)

        if st.button("🚀 ابدأ التحليل", key="account_btn"):
            if not api_key:
                st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
                return
            if not username:
                st.error("⚠️ يرجى إدخال اسم المستخدم.")
                return

            data, source = fetch_user_data(username)
            if not data:
                st.error("❌ فشلت جميع مصادر البيانات.")
                return

            st.success(f"✅ تم جلب البيانات بنجاح من: **{source}**")
            render_metrics(data, source)

            with st.expander("📦 البيانات الخام"):
                st.json(data)

            images_b64 = []
            if analyze_images and "avatar" in data:
                with st.spinner("🖼️ معالجة الصور..."):
                    b64 = process_image_to_base64(data["avatar"])
                    if b64:
                        images_b64.append(b64)

            with st.spinner(f"🤖 جاري التحليل باستخدام {model_name}..."):
                model = init_gemini(api_key, model_name)
                result = analyze_with_gemini(model, data, images_b64)

            st.markdown("---")
            st.markdown("## 📊 نتائج التحليل")
            render_analysis_result(result)

            st.download_button(
                "💾 تنزيل التقرير (JSON)",
                data=json.dumps(result, ensure_ascii=False, indent=2),
                file_name=f"x_analysis_{username}_{datetime.now():%Y%m%d_%H%M%S}.json",
                mime="application/json",
            )

    # ── تبويب تحليل منشور ──────────────────────────────────────────
    with tab2:
        tweet_url = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/1234567890",
            key="tweet_url",
        )
        if st.button("🔬 حلل المنشور", key="tweet_btn"):
            if not api_key:
                st.error("⚠️ يرجى إدخال مفتاح Gemini API.")
                return
            m = re.search(r"(?:x|twitter)\.com/([^/]+)/status/(\d+)", tweet_url)
            if not m:
                st.error("⚠️ رابط منشور غير صالح.")
                return
            username, tweet_id = m.group(1), m.group(2)
            with st.spinner("🔍 جلب المنشور..."):
                data = fetch_via_fxtwitter(username, tweet_id)
            if not data:
                st.error("❌ تعذر جلب المنشور.")
                return
            st.success("✅ تم جلب المنشور")
            with st.expander("📦 بيانات المنشور"):
                st.json(data)

            with st.spinner(f"🤖 جاري التحليل باستخدام {model_name}..."):
                model = init_gemini(api_key, model_name)
                result = analyze_with_gemini(model, data)
            st.markdown("## 📊 نتائج التحليل")
            render_analysis_result(result)


if __name__ == "__main__":
    main()
