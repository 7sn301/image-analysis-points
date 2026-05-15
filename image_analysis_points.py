# المشهد التنفيذي v6.2 - تحليل منشورات X/Twitter بالذكاء الاصطناعي
# إصلاح: oEmbed API + CSS محسّن RTL + عنوان وسط

import os
import re
import json
import tempfile
import subprocess
import requests
from typing import Dict, Any, Optional
from urllib.parse import urljoin
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import pytesseract

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS_AVAILABLE = True
except ImportError:
    BS_AVAILABLE = False

# ===== إعدادات التطبيق =====
APP_NAME = "المشهد التنفيذي"
APP_VERSION = "6.2"
APP_EMOJI = "🎯"

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

TESSERACT_LANG = "ara+eng"

# ===== Regex للتحقق من روابط X/Twitter =====
TWEET_URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(\d+)(?:\?.*)?$',
    re.IGNORECASE
)

# ===== دوال التحقق من روابط X =====
def is_tweet_url(url: str) -> bool:
    if not url:
        return False
    return bool(TWEET_URL_PATTERN.match(url.strip()))

def extract_tweet_id(url: str) -> Optional[str]:
    match = TWEET_URL_PATTERN.search(url)
    return match.group(1) if match else None

def normalize_tweet_url(url: str) -> str:
    tweet_id = extract_tweet_id(url)
    match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status/', url, re.IGNORECASE)
    username = match.group(1) if match else "user"
    return f"https://twitter.com/{username}/status/{tweet_id}" if tweet_id else url.split("?")[0]

# ===== الطريقة 1: Twitter oEmbed API (مجاني - لا يحتاج API Key) =====
def fetch_via_oembed(tweet_url: str) -> Dict[str, Any]:
    """
    Twitter oEmbed API - مجاني بالكامل ولا يحتاج مصادقة
    يُرجع النص الكامل للمنشور
    """
    clean_url = normalize_tweet_url(tweet_url)

    endpoints = [
        f"https://publish.twitter.com/oembed?url={clean_url}&lang=ar&omit_script=true",
        f"https://publish.twitter.com/oembed?url={clean_url}&omit_script=true",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    for endpoint in endpoints:
        try:
            resp = requests.get(endpoint, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                html_content = data.get("html", "")
                author = data.get("author_name", "")
                author_url = data.get("author_url", "")

                # استخراج النص من HTML
                text = ""
                if BS_AVAILABLE and html_content:
                    soup = BeautifulSoup(html_content, "html.parser")
                    # إزالة الروابط والمرفقات والاحتفاظ بالنص فقط
                    for tag in soup.find_all(["script", "a"]):
                        if tag.get("href", "").startswith("https://t.co"):
                            tag.decompose()
                    text = soup.get_text(separator=" ", strip=True)
                    # تنظيف النص
                    text = re.sub(r'\s+', ' ', text).strip()
                    # إزالة اسم المؤلف من بداية النص إذا كان موجوداً
                    if author and text.startswith(author):
                        text = text[len(author):].strip()

                return {
                    "text": text,
                    "author": author,
                    "author_url": author_url,
                    "html": html_content,
                    "source": "oembed"
                }
        except Exception:
            continue

    return {"error": "فشل oEmbed API"}

# ===== الطريقة 2: Nitter (مرايا متعددة) =====
def fetch_via_nitter(tweet_url: str) -> Dict[str, Any]:
    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        return {"error": "معرّف المنشور غير صالح"}

    match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status/', tweet_url, re.IGNORECASE)
    username = match.group(1) if match else ""
    if not username:
        return {"error": "اسم المستخدم غير صالح"}

    nitter_mirrors = [
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
        "https://nitter.kavin.rocks",
        "https://nitter.net",
        "https://nitter.cz",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ar,en-US;q=0.9",
    }

    for mirror in nitter_mirrors:
        try:
            nitter_url = f"{mirror}/{username}/status/{tweet_id}"
            resp = requests.get(nitter_url, headers=headers, timeout=10, allow_redirects=True)

            if resp.status_code == 200 and BS_AVAILABLE:
                soup = BeautifulSoup(resp.text, "html.parser")

                result = {"text": "", "author": username, "images": [], "video_url": "", "source": mirror}

                tweet_content = soup.find("div", class_="tweet-content")
                if tweet_content:
                    result["text"] = tweet_content.get_text(strip=True)

                for img in soup.find_all("img"):
                    src = img.get("src", "")
                    if "/pic/" in src or ".jpg" in src or ".png" in src:
                        full_url = urljoin(mirror, src)
                        if full_url not in result["images"]:
                            result["images"].append(full_url)

                video = soup.find("video")
                if video:
                    src = video.get("src", "")
                    if src:
                        result["video_url"] = urljoin(mirror, src)

                if result["text"]:
                    return result
        except Exception:
            continue

    return {"error": "تعذّر الوصول عبر جميع مرايا Nitter"}

# ===== الطريقة 3: yt-dlp =====
def download_media_yt_dlp(tweet_url: str, output_dir: str) -> Dict[str, Any]:
    clean_url = normalize_tweet_url(tweet_url)
    result = {"images": [], "video_path": "", "error": ""}

    try:
        cmd = [
            "yt-dlp", "--no-playlist",
            "--write-thumbnail", "--skip-download",
            "--output", os.path.join(output_dir, "thumb.%(ext)s"),
            clean_url
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        video_cmd = [
            "yt-dlp", "--no-playlist",
            "--format", "best[height<=720]",
            "--output", os.path.join(output_dir, "video.%(ext)s"),
            clean_url
        ]
        subprocess.run(video_cmd, capture_output=True, text=True, timeout=60)

        for fname in os.listdir(output_dir):
            fpath = os.path.join(output_dir, fname)
            if fname.startswith("thumb"):
                result["images"].append(fpath)
            elif fname.startswith("video"):
                result["video_path"] = fpath

    except subprocess.TimeoutExpired:
        result["error"] = "انتهت مهلة التحميل"
    except Exception as e:
        result["error"] = str(e)

    return result

# ===== الدالة الرئيسية: جلب المنشور (3 طبقات Fallback) =====
def fetch_tweet_with_media(url: str, api_key: str, status_container=None) -> Dict[str, Any]:
    def log(msg, kind="info"):
        if status_container:
            if kind == "success":
                status_container.success(msg)
            elif kind == "warning":
                status_container.warning(msg)
            elif kind == "error":
                status_container.error(msg)
            else:
                status_container.info(msg)

    if not is_tweet_url(url):
        return {
            "error": "❌ الرابط غير صالح. الشكل الصحيح:\nhttps://x.com/username/status/ID",
            "url": url
        }

    tweet_id = extract_tweet_id(url)
    log(f"✅ تم التعرف على المنشور — ID: {tweet_id}")

    result = {
        "tweet_id": tweet_id,
        "url": url,
        "text": "",
        "author": "",
        "images_text": "",
        "video_transcript": "",
        "raw_images": [],
        "error": ""
    }

    # ── الطبقة 1: oEmbed (الأسرع والأموثق) ──
    log("🔗 جاري الاتصال بـ Twitter oEmbed API...")
    oembed = fetch_via_oembed(url)
    if "error" not in oembed and oembed.get("text"):
        result["text"] = oembed["text"]
        result["author"] = oembed.get("author", "")
        log(f"✅ oEmbed نجح — النص: {result['text'][:60]}...", "success")
    else:
        log(f"⚠️ oEmbed: {oembed.get('error', 'لا يوجد نص')} — جاري تجربة Nitter...", "warning")

        # ── الطبقة 2: Nitter ──
        log("🪞 جاري تجربة مرايا Nitter...")
        nitter = fetch_via_nitter(url)
        if "error" not in nitter and nitter.get("text"):
            result["text"] = nitter["text"]
            result["author"] = nitter.get("author", "")
            result["raw_images"] = nitter.get("images", [])
            log(f"✅ Nitter نجح — المصدر: {nitter.get('source', '')}", "success")
        else:
            log(f"⚠️ Nitter فشل — {nitter.get('error', '')}", "warning")

    # ── الطبقة 3: yt-dlp للوسائط ──
    log("📥 جاري تحميل الوسائط بـ yt-dlp...")
    with tempfile.TemporaryDirectory() as tmpdir:
        media = download_media_yt_dlp(url, tmpdir)

        for img_path in media.get("images", []):
            if os.path.exists(img_path):
                log("🖼️ جاري قراءة نص الصورة بـ OCR...")
                img_text = extract_text_from_image(img_path, api_key)
                if img_text:
                    result["images_text"] += img_text + "\n"

        if media.get("video_path") and os.path.exists(media["video_path"]):
            log("🎬 جاري تفريغ الفيديو...")
            transcript = transcribe_video(media["video_path"], api_key)
            result["video_transcript"] = transcript
            log("✅ تم تفريغ الفيديو", "success")

    return result

# ===== OCR =====
def preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageEnhance.Contrast(image).enhance(1.5)
    return image

def extract_text_from_image(image_path: str, api_key: str) -> str:
    try:
        with Image.open(image_path) as img:
            processed = preprocess_image(img)
            text = pytesseract.image_to_string(processed, lang=TESSERACT_LANG, config="--psm 6")
            if text.strip():
                return text.strip()
    except Exception:
        pass

    if api_key and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            with open(image_path, "rb") as f:
                image_data = f.read()
            response = model.generate_content([
                "استخرج كل النص المكتوب في هذه الصورة بدقة كاملة",
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            return response.text if hasattr(response, "text") else ""
        except Exception:
            return ""
    return ""

def transcribe_video(video_path: str, api_key: str) -> str:
    if not api_key or not GENAI_AVAILABLE:
        return "(يتطلب Gemini API)"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        with open(video_path, "rb") as f:
            video_data = f.read()
        mime_type = "video/mp4"
        if video_path.endswith(".webm"):
            mime_type = "video/webm"
        response = model.generate_content([
            "فرّغ كل ما يُقال في هذا الفيديو نصاً كاملاً",
            {"mime_type": mime_type, "data": video_data}
        ])
        return response.text if hasattr(response, "text") else ""
    except Exception as e:
        return f"خطأ: {str(e)}"

# ===== تحسين العربية =====
def improve_arabic_text(text: str, api_key: str = "") -> str:
    if not text:
        return ""
    if api_key and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = ("أعد صياغة النص العربي التالي تصحيحاً لغوياً فقط، "
                      "بدون تغيير المعنى، وبدون مقدمات.\n\nالنص:\n" + text)
            response = model.generate_content(prompt)
            return response.text if hasattr(response, "text") else text
        except Exception:
            pass
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ===== تحليل Gemini =====
def analyze_with_gemini(tweet_data: Dict, api_key: str, mode: str = "تحليل شامل") -> Dict[str, Any]:
    if not api_key or not GENAI_AVAILABLE:
        return {"executive_summary": "(يتطلب Gemini API)", "error": "لا يوجد مفتاح API"}

    for model_name in GEMINI_MODELS:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)

            context_parts = []
            if tweet_data.get("text"):
                context_parts.append("نص المنشور:\n" + tweet_data["text"])
            if tweet_data.get("images_text"):
                context_parts.append("النص في الصور:\n" + tweet_data["images_text"])
            if tweet_data.get("video_transcript"):
                context_parts.append("تفريغ الفيديو:\n" + tweet_data["video_transcript"])

            context = "\n\n".join(context_parts) or "(لا يوجد محتوى)"

            prompt = (
                "حلّل المحتوى التالي تحليلاً تنفيذياً بالعربية الفصحى.\n"
                "وضع التحليل: " + mode + "\n\n"
                "المطلوب:\n"
                "1. ملخص تنفيذي شامل\n"
                "2. أبرز النقاط\n"
                "3. المخاطر أو الإشكالات\n"
                "4. التوصيات العملية\n"
                "5. الدلالة الإعلامية\n\n"
                "المحتوى:\n" + context + "\n\n"
                "أجب بصيغة JSON:\n"
                '{"executive_summary":"...","key_points":["..."],'
                '"risks":["..."],"recommendations":["..."],"sentiment":"إيجابي/سلبي/محايد"}'
            )

            response = model.generate_content(prompt)
            text = response.text if hasattr(response, "text") else ""

            try:
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except Exception:
                pass

            return {
                "executive_summary": text,
                "author": tweet_data.get("author", ""),
            }
        except Exception:
            continue

    return {"executive_summary": "(فشل التحليل بجميع النماذج)", "error": "فشل Gemini"}

# ===== CSS محسّن: عنوان وسط + RTL =====
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');

    /* ===== RTL عام ===== */
    html, body {
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl;
    }

    /* ===== المحتوى الرئيسي RTL ===== */
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .block-container {
        direction: rtl !important;
        text-align: right !important;
    }

    /* ===== العنوان الرئيسي في الوسط ===== */
    h1, [data-testid="stHeadingWithActionElements"] h1 {
        text-align: center !important;
        font-family: 'Tajawal', sans-serif !important;
        font-weight: 700 !important;
        font-size: 2rem !important;
        padding: 0.5rem 0 !important;
    }

    /* ===== caption تحت العنوان وسط ===== */
    [data-testid="stCaptionContainer"] {
        text-align: center !important;
    }

    /* ===== الشريط الجانبي RTL ===== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] * {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }

    /* ===== حقول الإدخال: نص من اليمين ===== */
    input[type="text"], input[type="password"], textarea {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
        font-size: 15px !important;
    }

    /* ===== الأزرار وسط ===== */
    .stButton > button {
        font-family: 'Tajawal', sans-serif !important;
        font-size: 15px !important;
        border-radius: 8px !important;
        width: 100% !important;
    }

    /* ===== التبويبات RTL ===== */
    .stTabs [data-baseweb="tab-list"] {
        direction: rtl !important;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Tajawal', sans-serif !important;
        font-size: 15px !important;
    }

    /* ===== الكود والبرمجة LTR ===== */
    code, pre, .stCodeBlock {
        direction: ltr !important;
        text-align: left !important;
    }

    /* ===== بطاقات النتائج ===== */
    .result-card {
        border: 1px solid rgba(100, 100, 200, 0.3);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        background: rgba(20, 20, 40, 0.5);
        direction: rtl;
        text-align: right;
    }

    /* ===== المقياس (metric) وسط ===== */
    [data-testid="stMetric"] {
        text-align: center !important;
    }
    [data-testid="stMetricLabel"] {
        text-align: center !important;
        justify-content: center !important;
    }

    /* ===== Selectbox, checkbox RTL ===== */
    .stSelectbox label,
    .stCheckbox label,
    .stTextInput label,
    .stTextArea label {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }

    /* ===== Success/Warning/Error RTL ===== */
    [data-testid="stAlert"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }

    /* ===== Divider ===== */
    hr { margin: 1rem 0; }

    /* ===== Padding block ===== */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1100px;
    }
    </style>
    """, unsafe_allow_html=True)

# ===== الواجهة الرئيسية =====
def main():
    st.set_page_config(
        page_title=APP_NAME + " " + APP_VERSION,
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded"
    )

    inject_css()

    # ===== العنوان في الوسط =====
    st.markdown(
        "<h1 style='text-align:center;font-family:Tajawal,sans-serif;'>"
        + APP_EMOJI + " " + APP_NAME + "</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center;color:#888;font-family:Tajawal,sans-serif;'>"
        "الإصدار " + APP_VERSION + " — تحليل منشورات X/Twitter بالذكاء الاصطناعي"
        "</p>",
        unsafe_allow_html=True
    )

    # ===== الشريط الجانبي =====
    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")

        gemini_key = st.text_input(
            "🔑 مفتاح Gemini API",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="احصل عليه من: https://aistudio.google.com/apikey"
        )

        st.markdown("---")
        st.markdown("### 📝 إعدادات التحليل")

        analysis_mode = st.selectbox(
            "وضع التحليل",
            options=["تحليل شامل", "تحليل سريع", "تحليل تفصيلي"],
            index=0
        )

        arabic_improve = st.checkbox("✨ تحسين اللغة العربية", value=True)
        use_ocr = st.checkbox("🖼️ استخراج نص الصور (OCR)", value=True)
        use_video = st.checkbox("🎬 تفريغ الفيديو", value=True)

        st.markdown("---")
        st.markdown("### 📊 إحصائيات الجلسة")
        if "analysis_count" not in st.session_state:
            st.session_state["analysis_count"] = 0
        st.metric("عدد التحليلات", st.session_state["analysis_count"])

        st.markdown("---")
        st.markdown(
            "<small style='color:#888'>الروابط المدعومة:<br>"
            "x.com و twitter.com<br>"
            "مع أو بدون www<br>"
            "مع أو بدون ?s=20</small>",
            unsafe_allow_html=True
        )

    # ===== التبويبات =====
    tab1, tab2, tab3 = st.tabs(["🔗 تحليل بالرابط", "🖼️ تحليل صورة مباشرة", "📚 دليل الاستخدام"])

    # ========== التبويب الأول: تحليل بالرابط ==========
    with tab1:
        st.markdown("### 🔗 أدخل رابط منشور X")

        tweet_url = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/123456789?s=20",
            help="يقبل x.com و twitter.com بكل أشكالها"
        )

        # التحقق الفوري من الرابط
        if tweet_url:
            if is_tweet_url(tweet_url):
                tid = extract_tweet_id(tweet_url)
                st.success("✅ رابط صالح | معرّف المنشور: " + str(tid))
            else:
                st.error("❌ الرابط غير مدعوم — تأكد من وجود /status/ في الرابط")

        col1, col2 = st.columns(2)
        with col1:
            fetch_btn = st.button("🔍 جلب وتحليل", type="primary", use_container_width=True)
        with col2:
            clear_btn = st.button("🗑️ مسح النتائج", use_container_width=True)

        if clear_btn:
            for key in ["tweet_result", "analysis_result"]:
                st.session_state.pop(key, None)
            st.rerun()

        if fetch_btn:
            if not tweet_url:
                st.warning("⚠️ أدخل رابط المنشور أولاً")
            elif not is_tweet_url(tweet_url):
                st.error("❌ الرابط غير صالح")
            elif not gemini_key:
                st.error("❌ أدخل مفتاح Gemini API في الشريط الجانبي")
            else:
                status_box = st.empty()
                progress_bar = st.progress(0)

                with st.spinner("جاري الجلب والتحليل..."):
                    try:
                        progress_bar.progress(10)
                        tweet_data = fetch_tweet_with_media(tweet_url, gemini_key, status_box)

                        if tweet_data.get("error"):
                            status_box.error(tweet_data["error"])
                            progress_bar.empty()
                        else:
                            progress_bar.progress(50)

                            if arabic_improve and tweet_data.get("text"):
                                status_box.info("📝 تحسين النص العربي...")
                                tweet_data["text_improved"] = improve_arabic_text(
                                    tweet_data["text"], gemini_key
                                )

                            progress_bar.progress(70)
                            status_box.info("🤖 جاري التحليل الذكي...")

                            analysis = analyze_with_gemini(tweet_data, gemini_key, analysis_mode)

                            st.session_state["tweet_result"] = tweet_data
                            st.session_state["analysis_result"] = analysis
                            st.session_state["analysis_count"] = st.session_state.get("analysis_count", 0) + 1

                            progress_bar.progress(100)
                            status_box.success("✅ اكتمل التحليل!")

                    except Exception as e:
                        status_box.error("❌ خطأ: " + str(e))
                        progress_bar.empty()

            # عرض النتائج
            if st.session_state.get("tweet_result"):
                result = st.session_state["tweet_result"]
                analysis = st.session_state.get("analysis_result", {})

                st.markdown("---")
                st.markdown("### 📊 نتائج التحليل")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("🆔 معرّف المنشور", result.get("tweet_id", "—"))
                with c2:
                    st.metric("👤 الناشر", result.get("author", "—"))
                with c3:
                    imgs = len(result.get("raw_images", []))
                    vid = 1 if result.get("video_transcript") else 0
                    st.metric("📎 الوسائط", imgs + vid)

                tab_r1, tab_r2, tab_r3 = st.tabs(
                    ["📝 النص والملخص", "🖼️ نص الصور", "🎬 تفريغ الفيديو"]
                )

                with tab_r1:
                    if result.get("text"):
                        st.markdown("#### 📄 النص الأصلي")
                        st.text_area("", value=result["text"], height=150, disabled=True,
                                     key="orig_text", label_visibility="collapsed")

                    if result.get("text_improved"):
                        st.markdown("#### ✨ النص بعد التحسين")
                        st.text_area("", value=result["text_improved"], height=150,
                                     disabled=True, key="impr_text", label_visibility="collapsed")

                    st.markdown("---")
                    st.markdown("#### 🎯 الملخص التنفيذي")

                    if analysis.get("executive_summary"):
                        st.markdown(
                            "<div class='result-card'>" +
                            analysis["executive_summary"] +
                            "</div>",
                            unsafe_allow_html=True
                        )

                    if analysis.get("key_points"):
                        st.markdown("#### 🔑 أبرز النقاط")
                        for pt in analysis["key_points"]:
                            st.markdown("- " + pt)

                    if analysis.get("risks"):
                        st.markdown("#### ⚠️ المخاطر")
                        for r in analysis["risks"]:
                            st.markdown("- " + r)

                    if analysis.get("recommendations"):
                        st.markdown("#### 💡 التوصيات")
                        for rec in analysis["recommendations"]:
                            st.markdown("- " + rec)

                    if analysis.get("sentiment"):
                        sentiment_color = {
                            "إيجابي": "🟢", "سلبي": "🔴", "محايد": "🟡"
                        }.get(analysis["sentiment"], "⚪")
                        st.markdown("**التوجه:** " + sentiment_color + " " + analysis["sentiment"])

                    # تنزيل النتائج
                    st.markdown("---")
                    result_text = (
                        "الناشر: " + result.get("author", "") + "\n"
                        "معرّف المنشور: " + str(result.get("tweet_id", "")) + "\n\n"
                        "النص:\n" + result.get("text", "") + "\n\n"
                        "الملخص التنفيذي:\n" + analysis.get("executive_summary", "")
                    )
                    st.download_button(
                        "⬇️ تنزيل النتائج (.txt)",
                        data=result_text.encode("utf-8"),
                        file_name="almashhad_result.txt",
                        mime="text/plain"
                    )

                with tab_r2:
                    if result.get("images_text"):
                        st.markdown("#### 🖼️ النص المستخرج من الصور")
                        st.text_area("", value=result["images_text"], height=200,
                                     disabled=True, key="img_text", label_visibility="collapsed")
                    else:
                        st.info("لا يوجد نص مستخرج من الصور")

                with tab_r3:
                    if result.get("video_transcript"):
                        st.markdown("#### 🎬 تفريغ الفيديو")
                        st.text_area("", value=result["video_transcript"], height=200,
                                     disabled=True, key="vid_text", label_visibility="collapsed")
                    else:
                        st.info("لا يوجد تفريغ للفيديو")

    # ========== التبويب الثاني: تحليل صورة مباشرة ==========
    with tab2:
        st.markdown("### 🖼️ تحليل صورة مباشرة")

        uploaded = st.file_uploader(
            "ارفع صورة",
            type=["jpg", "jpeg", "png", "webp"],
            help="يدعم JPG, PNG, WebP"
        )

        if uploaded:
            st.image(uploaded, caption="الصورة المرفوعة", use_container_width=True)

            if st.button("🔍 استخراج النص", type="primary") and gemini_key:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name

                with st.spinner("جاري الاستخراج..."):
                    text = extract_text_from_image(tmp_path, gemini_key)

                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

                if text:
                    st.success("✅ تم الاستخراج")
                    st.text_area("النص المستخرج", value=text, height=200)
                else:
                    st.warning("⚠️ لم يتم استخراج نص")

    # ========== التبويب الثالث: دليل الاستخدام ==========
    with tab3:
        st.markdown("""
        ### 📚 دليل استخدام المشهد التنفيذي

        #### الميزات الرئيسية:
        | الميزة | الوصف |
        |--------|-------|
        | 🔗 جلب المنشور | يدعم x.com و twitter.com مع/بدون ?s= |
        | 🖼️ OCR الصور | يقرأ النص في الصور بـ Tesseract + Gemini |
        | 🎬 تفريغ الفيديو | يحول الفيديو لنص بـ Gemini 2.0 |
        | 🤖 تحليل ذكي | ملخص تنفيذي + نقاط + مخاطر + توصيات |
        | ✨ تحسين العربية | تصحيح لغوي بـ Gemini |

        #### الروابط المدعومة:
        ```
        ✅ https://x.com/user/status/123456789
        ✅ https://x.com/user/status/123456789?s=20
        ✅ https://twitter.com/user/status/123456789
        ✅ https://www.twitter.com/user/status/123456789
        ```

        #### آلية الجلب (3 طبقات):
        1. **Twitter oEmbed API** — مجاني، لا يحتاج مصادقة
        2. **Nitter Mirrors** — مرايا متعددة كبديل
        3. **yt-dlp** — لتحميل الوسائط (صور/فيديو)
        """)


if __name__ == "__main__":
    main()
