# ============================================================
# المشهد التنفيذي v6.2 — تحليل منشورات X/Twitter
# إصلاحات: Gemini debug + author @handle + retweet detection
# ============================================================

import os, re, json, tempfile, subprocess, requests, traceback
from typing import Dict, Any, Optional, List
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

# ─────────────────────────────────────────
APP_NAME    = "المشهد التنفيذي"
APP_VERSION = "6.2"
APP_EMOJI   = "🎯"
TESSERACT_LANG = "ara+eng"
GEMINI_MODELS  = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

TWEET_URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/?#]+)/status/(\d+)',
    re.IGNORECASE
)

# ─────────────────── URL helpers ─────────────────────────────
def is_tweet_url(url: str) -> bool:
    return bool(url and TWEET_URL_PATTERN.search(url.strip()))

def extract_tweet_id(url: str) -> Optional[str]:
    m = TWEET_URL_PATTERN.search(url)
    return m.group(2) if m else None

def extract_username(url: str) -> Optional[str]:
    m = TWEET_URL_PATTERN.search(url)
    return m.group(1) if m else None

def normalize_tweet_url(url: str) -> str:
    tid  = extract_tweet_id(url)
    user = extract_username(url) or "user"
    return f"https://twitter.com/{user}/status/{tid}" if tid else url.split("?")[0]

# ─────────────────── oEmbed (المصدر الأول) ──────────────────
def fetch_via_oembed(tweet_url: str) -> Dict[str, Any]:
    """
    Twitter oEmbed API — مجاني تماماً، بدون مفتاح
    يُرجع: نص المنشور + اسم صاحب الحساب + @handle
    """
    clean = normalize_tweet_url(tweet_url)
    url_handle = extract_username(tweet_url) or ""

    for endpoint in [
        f"https://publish.twitter.com/oembed?url={clean}&lang=ar&omit_script=true",
        f"https://publish.twitter.com/oembed?url={clean}&omit_script=true",
    ]:
        try:
            r = requests.get(endpoint, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            data = r.json()

            # ── استخراج النص ──
            html_raw = data.get("html", "")
            text = ""
            if BS_AVAILABLE and html_raw:
                soup = BeautifulSoup(html_raw, "html.parser")
                for a in soup.find_all("a", href=True):
                    if "t.co" in a["href"]:
                        a.decompose()
                text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()

            # ── اسم الحساب + @handle ──
            display_name  = data.get("author_name", url_handle)
            author_page   = data.get("author_url", "")
            handle_from_url = ""
            if author_page:
                hm = re.search(r"twitter\.com/([^/?#]+)", author_page, re.I)
                if hm:
                    handle_from_url = "@" + hm.group(1)
            handle = handle_from_url or ("@" + url_handle if url_handle else "")

            # ── كشف إعادة النشر ──
            is_retweet = bool(
                re.search(r"^RT @", text) or
                (url_handle and handle and
                 url_handle.lower() != handle.lstrip("@").lower() and
                 bool(re.search(r"@" + re.escape(url_handle), text, re.I)))
            )

            return {
                "text": text,
                "display_name": display_name,
                "handle": handle,
                "author_url": author_page,
                "is_retweet": is_retweet,
                "rt_by_handle": ("@" + url_handle) if is_retweet else "",
                "source": "oembed",
                "raw_html": html_raw,
            }
        except Exception:
            continue

    return {"error": "فشل oEmbed API"}

# ─────────────────── Nitter (المصدر الثاني) ─────────────────
def fetch_via_nitter(tweet_url: str) -> Dict[str, Any]:
    tweet_id = extract_tweet_id(tweet_url)
    username = extract_username(tweet_url) or ""
    if not tweet_id or not username:
        return {"error": "رابط غير صالح"}

    mirrors = [
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
        "https://nitter.net",
        "https://nitter.cz",
    ]
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ar,en;q=0.9"}

    for mirror in mirrors:
        try:
            r = requests.get(f"{mirror}/{username}/status/{tweet_id}",
                             headers=headers, timeout=10, allow_redirects=True)
            if r.status_code != 200 or not BS_AVAILABLE:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            result: Dict[str, Any] = {
                "text": "", "display_name": username,
                "handle": "@" + username,
                "images": [], "video_url": "", "source": mirror
            }
            node = soup.find("div", class_="tweet-content")
            if node:
                result["text"] = node.get_text(strip=True)
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "/pic/" in src or ".jpg" in src or ".png" in src:
                    fu = urljoin(mirror, src)
                    if fu not in result["images"]:
                        result["images"].append(fu)
            vid = soup.find("video")
            if vid and vid.get("src"):
                result["video_url"] = urljoin(mirror, vid["src"])
            if result["text"]:
                return result
        except Exception:
            continue
    return {"error": "تعذّر الوصول عبر جميع مرايا Nitter"}

# ─────────────────── yt-dlp (الوسائط) ──────────────────────
def download_media_yt_dlp(tweet_url: str, out: str) -> Dict[str, Any]:
    clean = normalize_tweet_url(tweet_url)
    res = {"images": [], "video_path": "", "error": ""}
    try:
        subprocess.run(
            ["yt-dlp", "--no-playlist", "--write-thumbnail",
             "--skip-download", "--output", os.path.join(out, "thumb.%(ext)s"), clean],
            capture_output=True, text=True, timeout=30)
        subprocess.run(
            ["yt-dlp", "--no-playlist", "--format", "best[height<=720]",
             "--output", os.path.join(out, "video.%(ext)s"), clean],
            capture_output=True, text=True, timeout=60)
        for f in os.listdir(out):
            fp = os.path.join(out, f)
            if f.startswith("thumb"):
                res["images"].append(fp)
            elif f.startswith("video"):
                res["video_path"] = fp
    except subprocess.TimeoutExpired:
        res["error"] = "انتهت المهلة"
    except Exception as e:
        res["error"] = str(e)
    return res

# ─────────────────── الجلب الرئيسي ─────────────────────────
def fetch_tweet_with_media(url: str, api_key: str,
                           status_box=None) -> Dict[str, Any]:
    def log(msg, kind="info"):
        if not status_box: return
        getattr(status_box, kind, status_box.info)(msg)

    if not is_tweet_url(url):
        return {"error": "❌ الرابط غير صالح"}

    tweet_id  = extract_tweet_id(url)
    url_user  = extract_username(url) or ""
    log(f"✅ تم التعرف — ID: {tweet_id} | حساب الرابط: @{url_user}")

    result: Dict[str, Any] = {
        "tweet_id": tweet_id,
        "url": url,
        "text": "",
        "display_name": "",
        "handle": "@" + url_user,
        "is_retweet": False,
        "rt_by_handle": "",
        "images_text": "",
        "video_transcript": "",
        "raw_images": [],
        "error": "",
    }

    # ── oEmbed ──
    log("🔗 oEmbed API...")
    oe = fetch_via_oembed(url)
    if "error" not in oe and oe.get("text"):
        result.update({
            "text": oe["text"],
            "display_name": oe.get("display_name", ""),
            "handle": oe.get("handle", result["handle"]),
            "is_retweet": oe.get("is_retweet", False),
            "rt_by_handle": oe.get("rt_by_handle", ""),
        })
        log("✅ oEmbed نجح", "success")
    else:
        log(f"⚠️ oEmbed فشل — {oe.get('error','')}، تجربة Nitter...", "warning")
        ni = fetch_via_nitter(url)
        if "error" not in ni and ni.get("text"):
            result.update({
                "text": ni["text"],
                "display_name": ni.get("display_name", ""),
                "handle": ni.get("handle", result["handle"]),
                "raw_images": ni.get("images", []),
            })
            log("✅ Nitter نجح", "success")
        else:
            log(f"⚠️ Nitter فشل — {ni.get('error','')}", "warning")

    # ── yt-dlp للوسائط ──
    log("📥 تحميل الوسائط...")
    with tempfile.TemporaryDirectory() as tmpdir:
        media = download_media_yt_dlp(url, tmpdir)
        for ip in media.get("images", []):
            if os.path.exists(ip):
                t = extract_text_from_image(ip, api_key)
                if t:
                    result["images_text"] += t + "\n"
        if media.get("video_path") and os.path.exists(media["video_path"]):
            log("🎬 تفريغ الفيديو...")
            result["video_transcript"] = transcribe_video(
                media["video_path"], api_key)

    return result

# ─────────────────── OCR ─────────────────────────────────────
def preprocess_img(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("L")
    return ImageEnhance.Contrast(img).enhance(1.5)

def extract_text_from_image(path: str, api_key: str) -> str:
    try:
        with Image.open(path) as img:
            t = pytesseract.image_to_string(
                preprocess_img(img), lang=TESSERACT_LANG, config="--psm 6")
            if t.strip():
                return t.strip()
    except Exception:
        pass
    if api_key and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            m = genai.GenerativeModel("gemini-2.0-flash")
            with open(path, "rb") as f:
                data = f.read()
            r = m.generate_content([
                "استخرج كل النص في هذه الصورة بدقة",
                {"mime_type": "image/jpeg", "data": data}
            ])
            return r.text if hasattr(r, "text") else ""
        except Exception:
            pass
    return ""

def transcribe_video(path: str, api_key: str) -> str:
    if not api_key or not GENAI_AVAILABLE:
        return "(يتطلب Gemini API)"
    try:
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel("gemini-2.0-flash")
        mime = "video/webm" if path.endswith(".webm") else "video/mp4"
        with open(path, "rb") as f:
            data = f.read()
        r = m.generate_content([
            "فرّغ كل ما يُقال في الفيديو نصاً كاملاً",
            {"mime_type": mime, "data": data}
        ])
        return r.text if hasattr(r, "text") else ""
    except Exception as e:
        return "خطأ: " + str(e)

# ─────────────────── تحسين العربية ──────────────────────────
def improve_arabic_text(text: str, api_key: str) -> str:
    if not text or not api_key or not GENAI_AVAILABLE:
        return text
    try:
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel("gemini-2.0-flash")
        r = m.generate_content(
            "أعد صياغة النص العربي التالي تصحيحاً لغوياً فقط، "
            "بدون تغيير المعنى وبدون مقدمات.\n\nالنص:\n" + text)
        return r.text if hasattr(r, "text") else text
    except Exception:
        return text

# ─────────────────── Gemini Analysis ────────────────────────
def analyze_with_gemini(tweet_data: Dict, api_key: str,
                        mode: str = "تحليل شامل") -> Dict[str, Any]:
    if not api_key:
        return {
            "executive_summary": "⚠️ أدخل مفتاح Gemini API في الشريط الجانبي",
            "_error_detail": "لا يوجد مفتاح API"
        }
    if not GENAI_AVAILABLE:
        return {
            "executive_summary": "⚠️ مكتبة google-generativeai غير مثبتة",
            "_error_detail": "مكتبة مفقودة"
        }

    parts: List[str] = []
    if tweet_data.get("text"):
        parts.append("نص المنشور:\n" + tweet_data["text"])
    if tweet_data.get("images_text"):
        parts.append("النص المستخرج من الصور:\n" + tweet_data["images_text"])
    if tweet_data.get("video_transcript"):
        parts.append("تفريغ الفيديو:\n" + tweet_data["video_transcript"])
    context = "\n\n".join(parts) or "(لا يوجد محتوى)"

    prompt = (
        "أنت محلل إعلامي متخصص. حلّل المنشور التالي تحليلاً تنفيذياً "
        "بالعربية الفصحى الواضحة.\n"
        "الحساب: " + tweet_data.get("handle", "") + "\n"
        "وضع التحليل: " + mode + "\n\n"
        "المحتوى:\n" + context + "\n\n"
        "قدّم التحليل بالتنسيق التالي:\n"
        "**الملخص التنفيذي:** [ملخص شامل في فقرة واحدة]\n\n"
        "**أبرز النقاط:**\n- ...\n- ...\n\n"
        "**المخاطر أو الإشكالات:**\n- ...\n\n"
        "**التوصيات:**\n- ...\n\n"
        "**التوجه العام:** [إيجابي / سلبي / محايد]\n\n"
        "**الدلالة الإعلامية:** [تحليل موجز]"
    )

    errors_log: List[str] = []

    for model_name in GEMINI_MODELS:
        try:
            genai.configure(api_key=api_key)
            model  = genai.GenerativeModel(model_name)
            resp   = model.generate_content(prompt)
            text   = resp.text if hasattr(resp, "text") else ""

            if not text.strip():
                errors_log.append(f"{model_name}: استجابة فارغة")
                continue

            def extract_section(label: str) -> str:
                pat = r"\*\*" + re.escape(label) + r"\*\*[:\s]*(.*?)(?=\n\*\*|\Z)"
                m   = re.search(pat, text, re.DOTALL | re.IGNORECASE)
                return m.group(1).strip() if m else ""

            def extract_list(label: str) -> List[str]:
                section = extract_section(label)
                items   = re.findall(r"[-•]\s*(.+)", section)
                return [i.strip() for i in items if i.strip()] or [section]

            return {
                "executive_summary": extract_section("الملخص التنفيذي") or text,
                "key_points":        extract_list("أبرز النقاط"),
                "risks":             extract_list("المخاطر أو الإشكالات"),
                "recommendations":   extract_list("التوصيات"),
                "sentiment":         extract_section("التوجه العام"),
                "media_meaning":     extract_section("الدلالة الإعلامية"),
                "model_used":        model_name,
                "raw_text":          text,
            }

        except Exception as e:
            errors_log.append(f"{model_name}: {str(e)}")
            continue

    error_detail = " | ".join(errors_log) if errors_log else "خطأ غير معروف"
    return {
        "executive_summary": (
            "❌ فشل التحليل بجميع النماذج\n\n"
            "**السبب التقني:**\n```\n" + error_detail + "\n```\n\n"
            "**الحلول المقترحة:**\n"
            "- تحقق من صحة مفتاح Gemini API\n"
            "- تحقق من حصة الاستخدام على Google AI Studio\n"
            "- جرّب تغيير المفتاح من: https://aistudio.google.com/apikey"
        ),
        "_error_detail": error_detail,
    }

# ─────────────────── CSS ─────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl;
    }
    .block-container {
        direction: rtl !important;
        text-align: right !important;
        padding-top: 1.5rem !important;
        max-width: 1100px;
    }
    [data-testid="stHeadingWithActionElements"] h1 {
        text-align: center !important;
        font-family: 'Tajawal', sans-serif !important;
        font-weight: 700 !important;
    }
    [data-testid="stCaptionContainer"] p { text-align: center !important; }
    [data-testid="stSidebar"], [data-testid="stSidebar"] * {
        direction: rtl !important; text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }
    input, textarea, select {
        direction: rtl !important; text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }
    label { direction: rtl !important; text-align: right !important;
            font-family: 'Tajawal', sans-serif !important; }
    .stButton > button {
        font-family: 'Tajawal', sans-serif !important;
        font-size: 15px !important; border-radius: 8px !important;
    }
    .stTabs [data-baseweb="tab-list"] { direction: rtl !important; }
    .stTabs [data-baseweb="tab"] { font-family: 'Tajawal', sans-serif !important; }
    [data-testid="stAlert"] {
        direction: rtl !important; text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }
    [data-testid="stMetric"], [data-testid="stMetricLabel"] {
        text-align: center !important; justify-content: center !important;
    }
    .result-card {
        border: 1px solid rgba(99,102,241,.35); border-radius: 12px;
        padding: 1.2rem 1.4rem; margin-bottom: .8rem;
        background: rgba(15,15,35,.45); direction: rtl;
        text-align: right; font-family: 'Tajawal', sans-serif; line-height: 1.8;
    }
    .author-card {
        border: 1px solid rgba(34,197,94,.35); border-radius: 10px;
        padding: .7rem 1rem; background: rgba(34,197,94,.07);
        direction: rtl; font-family: 'Tajawal', sans-serif;
        margin-bottom: 1rem;
    }
    .rt-badge {
        background: rgba(251,191,36,.15); border: 1px solid rgba(251,191,36,.4);
        border-radius: 6px; padding: .3rem .7rem; font-size: .85rem;
        color: #fbbf24; font-family: 'Tajawal', sans-serif;
    }
    code, pre { direction: ltr !important; text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────── واجهة Streamlit ────────────────────────
def main():
    st.set_page_config(
        page_title=APP_NAME + " " + APP_VERSION,
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_css()

    st.markdown(
        "<h1 style='text-align:center;font-family:Tajawal,sans-serif;'>"
        + APP_EMOJI + " " + APP_NAME + "</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center;color:#9ca3af;font-size:.95rem;"
        "font-family:Tajawal,sans-serif;margin-bottom:1.5rem;'>"
        "الإصدار " + APP_VERSION + " — تحليل منشورات X/Twitter بالذكاء الاصطناعي"
        "</p>",
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.markdown("### ⚙️ الإعدادات")
        gemini_key = st.text_input(
            "🔑 مفتاح Gemini API",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="https://aistudio.google.com/apikey"
        )
        st.markdown("---")
        st.markdown("### 📝 إعدادات التحليل")
        analysis_mode = st.selectbox(
            "وضع التحليل",
            ["تحليل شامل", "تحليل سريع", "تحليل تفصيلي"]
        )
        arabic_improve = st.checkbox("✨ تحسين اللغة العربية", value=True)
        st.checkbox("🖼️ OCR الصور", value=True)
        st.checkbox("🎬 تفريغ الفيديو", value=True)
        st.markdown("---")
        st.markdown("### 📊 الجلسة")
        if "cnt" not in st.session_state:
            st.session_state["cnt"] = 0
        st.metric("التحليلات", st.session_state["cnt"])
        st.markdown("---")
        st.markdown(
            "<small style='color:#6b7280'>الروابط المدعومة:<br>"
            "x.com/user/status/ID<br>twitter.com/user/status/ID<br>"
            "مع أو بدون ?s=20</small>",
            unsafe_allow_html=True
        )

    tab1, tab2, tab3 = st.tabs(["🔗 تحليل بالرابط", "🖼️ تحليل صورة", "📚 الدليل"])

    with tab1:
        st.markdown("### 🔗 أدخل رابط منشور X")
        tweet_url = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/123456789?s=20"
        )
        if tweet_url.strip():
            if is_tweet_url(tweet_url):
                tid = extract_tweet_id(tweet_url)
                usr = extract_username(tweet_url)
                st.success("✅ رابط صالح | ID: `" + str(tid) + "` | الحساب: @" + str(usr))
            else:
                st.error("❌ الرابط غير مدعوم")

        col1, col2 = st.columns(2)
        with col1:
            fetch_btn = st.button("🔍 جلب وتحليل", type="primary", use_container_width=True)
        with col2:
            clear_btn = st.button("🗑️ مسح النتائج", use_container_width=True)

        if clear_btn:
            for k in ["tweet_result", "analysis_result"]:
                st.session_state.pop(k, None)
            st.rerun()

        if fetch_btn:
            if not tweet_url.strip():
                st.warning("⚠️ أدخل الرابط أولاً")
            elif not is_tweet_url(tweet_url):
                st.error("❌ الرابط غير صالح")
            elif not gemini_key.strip():
                st.error("❌ أدخل مفتاح Gemini API في الشريط الجانبي")
            else:
                sbox = st.empty()
                pbar = st.progress(0)
                with st.spinner("جاري الجلب والتحليل..."):
                    try:
                        sbox.info("🔄 جاري جلب المنشور...")
                        pbar.progress(15)
                        td = fetch_tweet_with_media(tweet_url, gemini_key, sbox)
                        if td.get("error"):
                            sbox.error(td["error"])
                            pbar.empty()
                        else:
                            pbar.progress(50)
                            if arabic_improve and td.get("text"):
                                sbox.info("📝 تحسين النص العربي...")
                                td["text_improved"] = improve_arabic_text(td["text"], gemini_key)
                            pbar.progress(65)
                            sbox.info("🤖 جاري التحليل بـ Gemini...")
                            analysis = analyze_with_gemini(td, gemini_key, analysis_mode)
                            pbar.progress(100)
                            st.session_state["tweet_result"]   = td
                            st.session_state["analysis_result"] = analysis
                            st.session_state["cnt"] = st.session_state.get("cnt", 0) + 1
                            if "_error_detail" in analysis:
                                sbox.warning("⚠️ اكتمل الجلب لكن فشل التحليل — راجع الملخص للتفاصيل")
                            else:
                                sbox.success("✅ اكتمل التحليل!")
                    except Exception as e:
                        sbox.error("❌ خطأ: " + str(e))
                        st.code(traceback.format_exc(), language="text")
                        pbar.empty()

        if st.session_state.get("tweet_result"):
            td = st.session_state["tweet_result"]
            an = st.session_state.get("analysis_result", {})

            st.markdown("---")
            st.markdown("### 📊 نتائج التحليل")

            # بطاقة الحساب
            is_rt     = td.get("is_retweet", False)
            handle    = td.get("handle", "")
            d_name    = td.get("display_name", "")
            rt_handle = td.get("rt_by_handle", "")
            author_html = (
                "<div class='author-card'><b>👤 صاحب المنشور الأصلي:</b> "
                + d_name + " <code>" + handle + "</code>"
            )
            if is_rt:
                author_html += "<br><span class='rt-badge'>🔁 أعاد النشر: " + rt_handle + "</span>"
            author_html += "</div>"
            st.markdown(author_html, unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            with c1: st.metric("🆔 ID", td.get("tweet_id", "—"))
            with c2: st.metric("🤖 النموذج", an.get("model_used", "—"))
            with c3: st.metric("📎 وسائط", len(td.get("raw_images", [])) + (1 if td.get("video_transcript") else 0))

            tr1, tr2, tr3 = st.tabs(["📝 النص والملخص", "🖼️ نص الصور", "🎬 تفريغ الفيديو"])

            with tr1:
                if td.get("text"):
                    st.markdown("#### 📄 النص الأصلي")
                    st.text_area("", value=td["text"], height=140, disabled=True,
                                 label_visibility="collapsed", key="orig_t")
                if td.get("text_improved"):
                    st.markdown("#### ✨ النص بعد التحسين")
                    st.text_area("", value=td["text_improved"], height=140, disabled=True,
                                 label_visibility="collapsed", key="impr_t")
                st.markdown("---")
                st.markdown("#### 🎯 الملخص التنفيذي")
                if an.get("executive_summary"):
                    st.markdown(
                        "<div class='result-card'>" +
                        an["executive_summary"].replace("\n", "<br>") +
                        "</div>", unsafe_allow_html=True)
                if an.get("key_points") and an["key_points"] != [""]:
                    st.markdown("#### 🔑 أبرز النقاط")
                    for p in an["key_points"]:
                        if p: st.markdown("- " + p)
                if an.get("risks") and an["risks"] != [""]:
                    st.markdown("#### ⚠️ المخاطر")
                    for r in an["risks"]:
                        if r: st.markdown("- " + r)
                if an.get("recommendations") and an["recommendations"] != [""]:
                    st.markdown("#### 💡 التوصيات")
                    for rc in an["recommendations"]:
                        if rc: st.markdown("- " + rc)
                if an.get("sentiment"):
                    clr = {"إيجابي":"🟢","سلبي":"🔴","محايد":"🟡"}.get(an["sentiment"],"⚪")
                    st.markdown("**التوجه:** " + clr + " " + an["sentiment"])
                if an.get("media_meaning"):
                    st.markdown("#### 📡 الدلالة الإعلامية")
                    st.markdown(an["media_meaning"])
                st.markdown("---")
                out_txt = (
                    "الحساب: " + handle + "\nالاسم: " + d_name +
                    "\nID: " + str(td.get("tweet_id","")) +
                    "\n\nالنص:\n" + td.get("text","") +
                    "\n\nالملخص التنفيذي:\n" + an.get("executive_summary","")
                )
                st.download_button("⬇️ تنزيل (.txt)",
                    data=out_txt.encode("utf-8"),
                    file_name="almashhad_result.txt", mime="text/plain")

            with tr2:
                if td.get("images_text"):
                    st.text_area("", value=td["images_text"], height=200,
                                 disabled=True, label_visibility="collapsed", key="img_t")
                else:
                    st.info("لا يوجد نص مستخرج من الصور")

            with tr3:
                if td.get("video_transcript"):
                    st.text_area("", value=td["video_transcript"], height=200,
                                 disabled=True, label_visibility="collapsed", key="vid_t")
                else:
                    st.info("لا يوجد تفريغ للفيديو")

    with tab2:
        st.markdown("### 🖼️ تحليل صورة مباشرة")
        upl = st.file_uploader("ارفع صورة", type=["jpg","jpeg","png","webp"])
        if upl:
            st.image(upl, use_container_width=True)
            if st.button("🔍 استخراج النص", type="primary") and gemini_key:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(upl.getvalue()); tp = tmp.name
                with st.spinner("جاري الاستخراج..."):
                    txt = extract_text_from_image(tp, gemini_key)
                try: os.remove(tp)
                except: pass
                if txt: st.success("✅ تم"); st.text_area("النص المستخرج", value=txt, height=200)
                else: st.warning("⚠️ لم يُستخرج نص")

    with tab3:
        st.markdown("""
        ### 📚 دليل استخدام المشهد التنفيذي v6.2
        | الميزة | الوصف |
        |--------|-------|
        | 🔗 جلب المنشور | oEmbed ← Nitter ← yt-dlp |
        | 👤 الحساب | اسم + @handle + كشف إعادة النشر 🔁 |
        | ❌ أخطاء Gemini | يعرض السبب ويقترح الحل |
        """)

if __name__ == "__main__":
    main()
