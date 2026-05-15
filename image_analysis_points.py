# -*- coding: utf-8 -*-
"""
تحليل الصور في نقاط - الإصدار 4.2
مع جميع الإصلاحات: KeyError + RTL + واجهة محسّنة
"""

# ============================================================
# فحص المكتبات المطلوبة
# ============================================================
missing_libs = []
try:
    import streamlit as st
except ImportError:
    missing_libs.append("streamlit")

try:
    import pytesseract
except ImportError:
    missing_libs.append("pytesseract")

try:
    import cv2
except ImportError:
    missing_libs.append("opencv-python-headless")

try:
    import numpy as np
except ImportError:
    missing_libs.append("numpy")

try:
    from PIL import Image
except ImportError:
    missing_libs.append("Pillow")

try:
    import google.generativeai as genai
except ImportError:
    missing_libs.append("google-generativeai")

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    missing_libs.append("requests / beautifulsoup4")

import re
import json
import io
import time
import base64

if missing_libs:
    import streamlit as st
    st.error(f"❌ مكتبات مفقودة: {', '.join(missing_libs)}")
    st.code("pip install " + " ".join(missing_libs))
    st.stop()

# ============================================================
# إعداد الصفحة
# ============================================================
st.set_page_config(
    page_title="🔍 تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS مخصص - واجهة محسّنة RTL
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=Cairo:wght@300;400;600;700;900&display=swap');

* {
    font-family: 'Tajawal', 'Cairo', 'Segoe UI', sans-serif !important;
}

html, body, [class*="css"] {
    direction: rtl;
    text-align: right;
    font-size: 17px;
}

.stApp {
    background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 40%, #0a0f1e 100%);
    min-height: 100vh;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    border-left: 2px solid #21262d;
    border-right: none;
    direction: rtl;
}

section[data-testid="stSidebar"] * {
    direction: rtl;
    text-align: right;
}

section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #58a6ff !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}

.main-hero {
    background: linear-gradient(135deg, #1a1f35 0%, #0d1117 50%, #1a1230 100%);
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 50px 40px;
    text-align: center;
    margin-bottom: 30px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}

.main-hero::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(88,166,255,0.05) 0%, transparent 60%);
    animation: pulse 4s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.5; }
    50% { transform: scale(1.1); opacity: 1; }
}

.hero-icon {
    font-size: 5rem;
    display: block;
    margin-bottom: 15px;
    animation: float 3s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
}

.hero-title {
    font-size: 3rem !important;
    font-weight: 900 !important;
    background: linear-gradient(135deg, #58a6ff, #a78bfa, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 10px 0 !important;
    line-height: 1.3 !important;
    direction: rtl;
}

.hero-subtitle {
    font-size: 1.3rem !important;
    color: #8b949e !important;
    margin-top: 10px !important;
    font-weight: 400 !important;
    direction: rtl;
}

.stats-row {
    display: flex;
    gap: 15px;
    margin-bottom: 25px;
    flex-direction: row-reverse;
    justify-content: center;
    flex-wrap: wrap;
}

.stat-card {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border: 1px solid #30363d;
    border-radius: 15px;
    padding: 20px 30px;
    text-align: center;
    min-width: 140px;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}

.stat-card:hover {
    transform: translateY(-3px);
    border-color: #58a6ff;
    box-shadow: 0 8px 25px rgba(88,166,255,0.15);
}

.stat-number {
    font-size: 2.2rem;
    font-weight: 900;
    color: #58a6ff;
    display: block;
}

.stat-label {
    font-size: 0.9rem;
    color: #8b949e;
    margin-top: 5px;
    display: block;
}

.stTabs [data-baseweb="tab-list"] {
    direction: rtl;
    background: #161b22;
    border-radius: 15px;
    padding: 8px;
    gap: 5px;
    border: 1px solid #30363d;
}

.stTabs [data-baseweb="tab"] {
    direction: rtl;
    border-radius: 10px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: #8b949e !important;
    padding: 12px 20px !important;
    transition: all 0.3s ease !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    color: white !important;
    box-shadow: 0 4px 15px rgba(31,111,235,0.4) !important;
}

.stTabs [data-baseweb="tab-panel"] {
    direction: rtl;
    padding-top: 20px;
}

.stFileUploader > div {
    border: 2px dashed #30363d !important;
    border-radius: 15px !important;
    background: #0d1117 !important;
    padding: 40px !important;
    text-align: center !important;
    transition: all 0.3s ease !important;
}

.stFileUploader > div:hover {
    border-color: #58a6ff !important;
    background: #0d1f36 !important;
}

.stButton > button {
    direction: rtl !important;
    font-family: 'Tajawal', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    padding: 12px 28px !important;
    transition: all 0.3s ease !important;
    border: none !important;
    cursor: pointer !important;
    width: 100% !important;
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    color: white !important;
    box-shadow: 0 4px 15px rgba(31,111,235,0.3) !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(31,111,235,0.4) !important;
}

.result-card {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 22px 25px;
    margin: 12px 0;
    direction: rtl;
    text-align: right;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}

.result-card:hover {
    border-color: #388bfd;
    box-shadow: 0 6px 20px rgba(56,139,253,0.15);
    transform: translateX(-3px);
}

.result-card.summary-card {
    border-left: 4px solid #a78bfa;
    background: linear-gradient(135deg, #1a1230, #1c2128);
}

.result-card.summary-card:hover {
    border-color: #a78bfa;
    box-shadow: 0 6px 20px rgba(167,139,250,0.15);
}

.card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    flex-direction: row-reverse;
}

.card-icon { font-size: 1.6rem; }

.card-label {
    font-size: 1rem;
    font-weight: 700;
    color: #8b949e;
}

.card-value {
    font-size: 1.2rem;
    font-weight: 500;
    color: #e6edf3;
    line-height: 1.7;
    direction: rtl;
    text-align: right;
}

.card-value.summary-value {
    font-size: 1.15rem;
    line-height: 2;
    color: #cdd9e5;
}

.x-link {
    color: #58a6ff !important;
    text-decoration: none !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    padding: 5px 12px !important;
    background: rgba(88,166,255,0.1) !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}

.x-link:hover {
    background: rgba(88,166,255,0.2) !important;
    transform: translateY(-1px) !important;
}

.success-banner {
    background: linear-gradient(135deg, #1a3a2a, #163b2e);
    border: 1px solid #2ea043;
    border-radius: 15px;
    padding: 20px 25px;
    margin: 15px 0;
    direction: rtl;
    text-align: right;
    display: flex;
    align-items: center;
    gap: 15px;
    flex-direction: row-reverse;
    box-shadow: 0 4px 15px rgba(46,160,67,0.15);
}

.success-banner-icon { font-size: 2rem; }

.success-banner-text {
    font-size: 1.1rem;
    font-weight: 600;
    color: #3fb950;
}

.tweet-card {
    background: linear-gradient(135deg, #0d1117, #161b22);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 25px;
    margin: 15px 0;
    direction: rtl;
    text-align: right;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}

.tweet-author {
    font-size: 1.2rem;
    font-weight: 700;
    color: #58a6ff;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-direction: row-reverse;
}

.tweet-text {
    font-size: 1.15rem;
    color: #e6edf3;
    line-height: 1.8;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    direction: rtl !important;
    text-align: right !important;
    font-family: 'Tajawal', sans-serif !important;
    font-size: 1rem !important;
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 10px !important;
    color: #e6edf3 !important;
    padding: 12px 15px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88,166,255,0.15) !important;
}

label, .stSelectbox label, .stMultiSelect label,
.stRadio label, .stCheckbox label {
    direction: rtl !important;
    text-align: right !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: #cdd9e5 !important;
}

p, .stMarkdown p {
    direction: rtl !important;
    text-align: right !important;
    font-size: 1.05rem !important;
    line-height: 1.8 !important;
    color: #cdd9e5 !important;
}

h1, h2, h3 {
    direction: rtl !important;
    text-align: right !important;
}

.stProgress > div > div {
    background: linear-gradient(90deg, #1f6feb, #388bfd) !important;
    border-radius: 10px !important;
}

.stAlert {
    direction: rtl !important;
    text-align: right !important;
    border-radius: 12px !important;
    font-size: 1rem !important;
}

.paste-zone {
    border: 2px dashed #388bfd;
    border-radius: 16px;
    padding: 50px;
    text-align: center;
    background: linear-gradient(135deg, rgba(31,111,235,0.05), rgba(56,139,253,0.03));
    margin: 15px 0;
    cursor: pointer;
    transition: all 0.3s ease;
    direction: rtl;
}

.paste-zone:hover {
    background: rgba(56,139,253,0.1);
    border-color: #58a6ff;
}

.paste-zone-icon { font-size: 3.5rem; display: block; margin-bottom: 15px; }
.paste-zone-text { font-size: 1.2rem; color: #8b949e; font-weight: 500; }

.extraction-rate {
    background: linear-gradient(135deg, #1a2a1a, #1c2820);
    border: 1px solid #2ea043;
    border-radius: 12px;
    padding: 15px 20px;
    text-align: center;
    font-size: 1.1rem;
    font-weight: 700;
    color: #3fb950;
    margin: 10px 0;
    direction: rtl;
}

hr {
    border-color: #21262d !important;
    margin: 20px 0 !important;
}

.stSelectbox > div > div,
.stMultiSelect > div > div {
    direction: rtl !important;
    background: #161b22 !important;
    border-color: #30363d !important;
    border-radius: 10px !important;
}

.streamlit-expanderHeader {
    direction: rtl !important;
    text-align: right !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    background: #161b22 !important;
    border-radius: 10px !important;
    border: 1px solid #30363d !important;
    padding: 12px 18px !important;
}

.streamlit-expanderContent {
    direction: rtl !important;
    text-align: right !important;
    background: #0d1117 !important;
    border: 1px solid #30363d !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    padding: 15px !important;
}

[data-testid="metric-container"] {
    direction: rtl !important;
    text-align: right !important;
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
    padding: 15px !important;
}

[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 900 !important;
    color: #58a6ff !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.95rem !important;
    color: #8b949e !important;
    font-weight: 600 !important;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #58a6ff; }

.footer {
    text-align: center;
    padding: 30px;
    color: #484f58;
    font-size: 0.9rem;
    margin-top: 50px;
    border-top: 1px solid #21262d;
    direction: rtl;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# القاموس الدلالي
# ============================================================
SEMANTIC_KEYWORDS = {
    "عام": ["منشور", "تغريدة", "تعليق", "رأي", "شخص", "مستخدم"],
    "المتطرفون": ["إرهاب", "تطرف", "داعش", "جهاد", "تكفير", "غلو"],
    "سياسية": ["سياسة", "حكومة", "برلمان", "وزير", "رئيس", "انتخابات"],
    "الترفيه": ["فيلم", "مسلسل", "فنان", "غناء", "كرة", "رياضة"],
    "التجنيس": ["تجنيس", "جنسية", "مواطنة", "هوية", "وافد"],
    "تهكم_وسخرية": ["هههه", "😂", "🤣", "طبعاً", "بكل تأكيد", "واضح", "معروف"]
}

# ============================================================
# وظائف مساعدة
# ============================================================
def detect_category(text):
    text_lower = text.lower()
    scores = {}
    for cat, keywords in SEMANTIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[cat] = score
    return sorted(scores, key=scores.get, reverse=True)[:3] if scores else ["عام"]

def is_sarcastic_text(text):
    sarcasm_indicators = SEMANTIC_KEYWORDS["تهكم_وسخرية"] + ["بالتأكيد", "طبعاً", "مستحيل"]
    count = sum(1 for ind in sarcasm_indicators if ind in text)
    return count >= 2

def get_topic_from_text(text):
    categories = detect_category(text)
    return categories[0] if categories else "عام"

def make_x_link(username):
    if not username or username == "غير مُحدد":
        return username
    clean = username.replace("@", "").strip()
    if not clean:
        return username
    x_icon = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
        <path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865z"/>
    </svg>"""
    return f'<a href="https://x.com/{clean}" target="_blank" class="x-link">{x_icon} @{clean}</a>'

def validate_api_key(key):
    if not key:
        return False
    key = key.strip()
    return key.startswith("AIza") and len(key) > 30

# ============================================================
# Session State
# ============================================================
def get_default_api_key():
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except:
        return ""

defaults = {
    "api_key": get_default_api_key(),
    "analysis_done": False,
    "results": None,
    "batch_results": [],
    "extracted_text": "",
    "analysis_method": "",
    "used_model": "",
    "tweet_data": None,
    "total_analyzed": 0,
    "url_analysis_done": False,
    "url_results": None,
    "pasted_image": None,
    "paste_analysis_done": False,
    "paste_results": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# OCR
# ============================================================
def preprocess_image_ocr(image):
    try:
        img_array = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        scaled = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoising(scaled, h=10)
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(thresh)
    except:
        return image

def extract_text_ocr(image):
    try:
        processed = preprocess_image_ocr(image)
        config = r'--oem 3 --psm 6 -l ara+eng'
        text = pytesseract.image_to_string(processed, config=config)
        return text.strip()
    except:
        try:
            return pytesseract.image_to_string(image, lang='ara+eng').strip()
        except:
            return ""

# ============================================================
# الملخص التنفيذي
# ============================================================
def generate_executive_summary(results, text=""):
    poster    = results.get("معرف_المنشور", "غير مُحدد")
    commenter = results.get("معرف_التعليق", "غير مُحدد")
    mentioned = results.get("المدعو", "غير مُحدد")
    content   = results.get("محتوى_المنشور", "")
    clip      = results.get("المقطع", "غير مُحدد")
    comment   = results.get("التعليق", "")
    opinion   = results.get("الرأي", "")
    is_sarcastic = is_sarcastic_text(text)
    topic = get_topic_from_text(text)

    parts = []
    if poster != "غير مُحدد":
        parts.append(f"نشر المستخدم {poster}")
    if content and content != "غير مُحدد":
        parts.append(
            f"منشوراً حول موضوع '{content[:60]}...'" if len(content) > 60
            else f"منشوراً بمحتوى '{content}'"
        )
    if mentioned != "غير مُحدد":
        parts.append(f"مستشهداً بـ {mentioned}")
    if clip != "غير مُحدد":
        parts.append(f"ومرفقاً مقطعاً يتضمن '{clip}'")
    if commenter != "غير مُحدد" and comment:
        parts.append(
            f"ثم علّق عليه {commenter} بقوله '{comment[:80]}'" if len(comment) > 80
            else f"ثم علّق عليه {commenter} بقوله '{comment}'"
        )
    if opinion:
        parts.append(
            f"مُعبِّراً عن رأيه بأن '{opinion[:100]}'" if len(opinion) > 100
            else f"مُعبِّراً عن رأيه بأن '{opinion}'"
        )
    if is_sarcastic:
        parts.append("وقد اتّسم الأسلوب بالتهكم والسخرية الضمنية")
    if topic != "عام":
        parts.append(f"وتندرج هذه التفاعلات ضمن نطاق الموضوعات {topic}")

    if parts:
        return "، ".join(parts) + "."
    return "لم يتم استخراج معلومات كافية من الصورة لبناء ملخص تنفيذي."

# ============================================================
# تحليل ذكي
# ============================================================
def analyze_post_smart(text, mentions=[]):
    results = {
        "معرف_المنشور":   "غير مُحدد",
        "معرف_التعليق":   "غير مُحدد",
        "المدعو":         "غير مُحدد",
        "محتوى_المنشور":  "غير مُحدد",
        "المقطع":         "غير مُحدد",
        "التعليق":        "غير مُحدد",
        "الرأي":          "غير مُحدد",
        "الملخص_التنفيذي":"غير مُحدد"
    }
    if not text:
        return results

    usernames = re.findall(r'@([\w\u0600-\u06ff]+)', text)
    if usernames:
        results["معرف_المنشور"] = "@" + usernames[0]
        if len(usernames) > 1:
            results["معرف_التعليق"] = "@" + usernames[1]
        if len(usernames) > 2:
            results["المدعو"] = "@" + usernames[2]

    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 15]
    if lines:
        results["محتوى_المنشور"] = lines[0][:200]
        if len(lines) > 1:
            results["التعليق"] = lines[-1][:200]

    opinion_patterns = [
        r'يقول[:\s]+(.+)', r'يرى[:\s]+(.+)',
        r'اعتقد[:\s]+(.+)', r'أرى[:\s]+(.+)'
    ]
    for pat in opinion_patterns:
        m = re.search(pat, text)
        if m:
            results["الرأي"] = m.group(1)[:200]
            break

    results["الملخص_التنفيذي"] = generate_executive_summary(results, text)
    return results

# ============================================================
# جلب محتوى X/Twitter
# ============================================================
def fetch_tweet_content(url):
    tweet_data = {"text": "", "author": "", "screenshot": None, "error": ""}
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={url}&lang=ar"
        r = requests.get(oembed_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            tweet_data["text"]   = BeautifulSoup(data.get("html", ""), "html.parser").get_text()
            tweet_data["author"] = data.get("author_name", "")
    except Exception as e:
        tweet_data["error"] = str(e)

    try:
        shot_url = f"https://image.thum.io/get/width/800/crop/600/{url}"
        r2 = requests.get(shot_url, timeout=15)
        if r2.status_code == 200:
            tweet_data["screenshot"] = Image.open(io.BytesIO(r2.content))
    except:
        pass

    return tweet_data

# ============================================================
# Gemini Prompts
# ============================================================
GEMINI_PROMPT = """
أنت محلل متخصص في تحليل منشورات منصة X (تويتر).
حلّل هذه الصورة واستخرج المعلومات بدقة.
أعد النتائج بتنسيق JSON صارم كالتالي:

{
  "معرف_المنشور": "معرف المستخدم الذي نشر أصلاً (مع @)",
  "معرف_التعليق": "معرف من علّق (مع @) أو غير مُحدد",
  "المدعو": "اسم أو معرف الشخص المُستشهد به أو غير مُحدد",
  "محتوى_المنشور": "النص الكامل للمنشور الأصلي",
  "المقطع": "وصف المقطع المرفق أو غير مُحدد",
  "التعليق": "نص التعليق كاملاً أو غير مُحدد",
  "الرأي": "الرأي أو الموقف المُعبَّر عنه",
  "الملخص_التنفيذي": "اكتب ملخصاً تنفيذياً احترافياً لا يقل عن 80 كلمة يشرح المنشور وسياقه وأهميته"
}

مهم: أعد JSON فقط بدون أي نص إضافي.
"""

# ✅ الإصلاح الأول: الأقواس المزدوجة داخل JSON تمنع KeyError
GEMINI_TEXT_PROMPT = """
أنت محلل متخصص في تحليل منشورات X (تويتر).
حلل هذا النص واستخرج المعلومات المطلوبة.
النص: {text}

أعد النتائج بتنسيق JSON فقط:
{{
  "معرف_المنشور": "معرف المستخدم الذي نشر أصلاً (مع @)",
  "معرف_التعليق": "معرف من علّق (مع @) أو غير مُحدد",
  "المدعو": "اسم أو معرف الشخص المُستشهد به أو غير مُحدد",
  "محتوى_المنشور": "النص الكامل للمنشور الأصلي",
  "المقطع": "وصف المقطع المرفق أو غير مُحدد",
  "التعليق": "نص التعليق كاملاً أو غير مُحدد",
  "الرأي": "الرأي أو الموقف المُعبَّر عنه",
  "الملخص_التنفيذي": "اكتب ملخصاً تنفيذياً احترافياً لا يقل عن 80 كلمة"
}}

مهم: أعد JSON فقط بدون أي نص إضافي.
"""

# ============================================================
# parse JSON
# ============================================================
def parse_gemini_json(raw_text):
    try:
        cleaned = re.sub(r'^```(json)?\s*', '', raw_text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

# ============================================================
# analyze_with_gemini (صورة)
# ============================================================
def analyze_with_gemini(image, api_key):
    if not validate_api_key(api_key):
        return None, "❌ مفتاح API غير صالح", ""

    genai.configure(api_key=api_key.strip())

    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]

    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([GEMINI_PROMPT, image])
            result = parse_gemini_json(response.text)
            if result:
                for field in ["معرف_المنشور", "معرف_التعليق", "المدعو",
                               "محتوى_المنشور", "المقطع", "التعليق",
                               "الرأي", "الملخص_التنفيذي"]:
                    result.setdefault(field, "غير مُحدد")
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit"]):
                last_error = f"⚠️ {model_name}: تجاوز الحصة"
                time.sleep(2)
                continue
            elif any(x in err for x in ["404", "not found", "MODEL_NOT_FOUND"]):
                last_error = f"⚠️ {model_name}: غير متاح"
                continue
            elif any(x in err for x in ["API_KEY_INVALID", "INVALID_ARGUMENT"]):
                return None, "❌ مفتاح API غير صالح", ""
            elif "PERMISSION_DENIED" in err:
                return None, "❌ لا توجد صلاحية - تحقق من المفتاح", ""
            else:
                last_error = f"⚠️ {model_name}: {err[:60]}"
                continue

    return None, f"❌ فشلت جميع النماذج. آخر خطأ: {last_error}\n💡 https://aistudio.google.com/apikey", ""

# ============================================================
# ✅ analyze_text_with_gemini (نص) - مع إصلاح KeyError
# ============================================================
def analyze_text_with_gemini(text, api_key):
    if not validate_api_key(api_key):
        return None, "❌ مفتاح API غير صالح", ""

    # ✅ الإصلاح الثاني: replace بدلاً من .format() لتجنب KeyError
    safe_prompt = GEMINI_TEXT_PROMPT.replace("{text}", text[:2000])

    genai.configure(api_key=api_key.strip())

    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]

    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(safe_prompt)
            result = parse_gemini_json(response.text)
            if result:
                for field in ["معرف_المنشور", "معرف_التعليق", "المدعو",
                               "محتوى_المنشور", "المقطع", "التعليق",
                               "الرأي", "الملخص_التنفيذي"]:
                    result.setdefault(field, "غير مُحدد")
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit"]):
                last_error = f"⚠️ {model_name}: تجاوز الحصة"
                time.sleep(2)
                continue
            elif any(x in err for x in ["404", "not found", "MODEL_NOT_FOUND"]):
                last_error = f"⚠️ {model_name}: غير متاح"
                continue
            elif any(x in err for x in ["API_KEY_INVALID", "INVALID_ARGUMENT"]):
                return None, "❌ مفتاح API غير صالح", ""
            elif "PERMISSION_DENIED" in err:
                return None, "❌ لا توجد صلاحية - تحقق من المفتاح", ""
            else:
                last_error = f"⚠️ {model_name}: {err[:60]}"
                continue

    return None, f"❌ فشل التحليل النصي. آخر خطأ: {last_error}", ""

# ============================================================
# إعداد عرض الحقول
# ============================================================
FIELD_CONFIG = {
    "معرف_المنشور":    {"icon": "👤", "label": "صاحب المنشور",      "is_x": True,  "is_summary": False},
    "معرف_التعليق":    {"icon": "💬", "label": "صاحب التعليق",      "is_x": True,  "is_summary": False},
    "المدعو":          {"icon": "🎯", "label": "الشخص المُستشهد به", "is_x": True,  "is_summary": False},
    "محتوى_المنشور":  {"icon": "📝", "label": "محتوى المنشور",      "is_x": False, "is_summary": False},
    "المقطع":          {"icon": "🎬", "label": "المقطع المرفق",      "is_x": False, "is_summary": False},
    "التعليق":         {"icon": "💭", "label": "نص التعليق",         "is_x": False, "is_summary": False},
    "الرأي":           {"icon": "🔍", "label": "الرأي والموقف",      "is_x": False, "is_summary": False},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي",    "is_x": False, "is_summary": True},
}

def render_result_card(field_key, value, config):
    if not value or value == "غير مُحدد":
        return
    icon       = config["icon"]
    label      = config["label"]
    is_x       = config["is_x"]
    is_summary = config["is_summary"]
    display_value = make_x_link(value) if is_x else value
    card_class  = "result-card summary-card" if is_summary else "result-card"
    value_class = "card-value summary-value"  if is_summary else "card-value"
    st.markdown(f"""
    <div class="{card_class}">
        <div class="card-header">
            <span class="card-icon">{icon}</span>
            <span class="card-label">{label}</span>
        </div>
        <div class="{value_class}">{display_value}</div>
    </div>
    """, unsafe_allow_html=True)

def render_all_results(results, method="", model_name="", selected_fields=None):
    if not results:
        return
    method_text = f"🤖 Gemini ({model_name})" if model_name else f"📝 {method}"
    st.markdown(f"""
    <div class="success-banner">
        <span class="success-banner-icon">✅</span>
        <span class="success-banner-text">تم التحليل بنجاح عبر {method_text}</span>
    </div>
    """, unsafe_allow_html=True)

    total_fields = len(FIELD_CONFIG)
    filled = sum(1 for k in FIELD_CONFIG if results.get(k) and results.get(k) != "غير مُحدد")
    pct = int((filled / total_fields) * 100)
    st.markdown(f"""
    <div class="extraction-rate">
        📊 نسبة استخراج البيانات: {pct}% ({filled}/{total_fields} حقل)
    </div>
    """, unsafe_allow_html=True)

    all_text = " ".join(str(v) for v in results.values())
    categories = detect_category(all_text)
    if categories:
        cats_html = " ".join(
            f'<span style="background:#1f6feb22;border:1px solid #1f6feb;border-radius:20px;'
            f'padding:4px 14px;font-size:0.85rem;color:#58a6ff;margin:3px;">{c}</span>'
            for c in categories
        )
        st.markdown(f'<div style="direction:rtl;margin:10px 0;">🏷️ التصنيفات: {cats_html}</div>',
                    unsafe_allow_html=True)

    fields_to_show = selected_fields if selected_fields else list(FIELD_CONFIG.keys())
    for field_key in FIELD_CONFIG:
        if field_key in fields_to_show:
            render_result_card(field_key, results.get(field_key, "غير مُحدد"), FIELD_CONFIG[field_key])

def download_buttons(results, prefix="result"):
    if not results:
        return
    col1, col2 = st.columns(2)
    with col1:
        txt_content = "\n".join(f"{k}: {v}" for k, v in results.items())
        st.download_button("⬇️ تنزيل TXT", txt_content, f"{prefix}.txt", "text/plain")
    with col2:
        json_content = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button("⬇️ تنزيل JSON", json_content, f"{prefix}.json", "application/json")

def analyze_image_full(image, api_key, use_gemini):
    if use_gemini and validate_api_key(api_key):
        result, error, model_name = analyze_with_gemini(image, api_key)
        if result:
            return result, "Gemini", model_name
    ocr_text = extract_text_ocr(image)
    mentions = re.findall(r'@[\w\u0600-\u06ff]+', ocr_text)
    result = analyze_post_smart(ocr_text, mentions)
    return result, "OCR", ""

# ============================================================
# الشريط الجانبي
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ إعدادات التحليل")
    st.divider()

    analysis_mode = st.radio(
        "🔧 طريقة التحليل",
        ["🤖 Gemini AI (أدق)", "📝 OCR (مجاني)"],
        index=0
    )
    use_gemini = "Gemini" in analysis_mode

    if use_gemini:
        st.markdown("### 🔑 مفتاح Gemini API")
        api_input = st.text_input(
            "أدخل المفتاح",
            value=st.session_state.api_key,
            type="password",
            placeholder="AIza...",
            label_visibility="collapsed"
        )
        if api_input != st.session_state.api_key:
            st.session_state.api_key = api_input

        if st.session_state.api_key:
            if validate_api_key(st.session_state.api_key):
                st.success("✅ مفتاح صالح")
            else:
                st.error("❌ مفتاح غير صالح")

        if st.button("🔍 اختبار النماذج المتاحة"):
            if validate_api_key(st.session_state.api_key):
                try:
                    genai.configure(api_key=st.session_state.api_key.strip())
                    models = list(genai.list_models())
                    vision_models = [
                        m.name for m in models
                        if "generateContent" in [
                            a.value if hasattr(a, 'value') else str(a)
                            for a in m.supported_generation_methods
                        ]
                    ]
                    st.success(f"✅ {len(vision_models)} نموذج متاح")
                    for m in vision_models[:5]:
                        st.code(m.replace("models/", ""), language=None)
                except Exception as e:
                    st.error(f"خطأ: {str(e)[:100]}")
            else:
                st.warning("⚠️ أدخل مفتاحاً صالحاً أولاً")

        st.markdown("🔗 [احصل على مفتاح مجاني](https://aistudio.google.com/apikey)")

    st.divider()

    st.markdown("### 📋 الحقول المعروضة")
    all_field_labels = {k: f"{v['icon']} {v['label']}" for k, v in FIELD_CONFIG.items()}
    selected_fields = st.multiselect(
        "اختر الحقول",
        options=list(all_field_labels.keys()),
        default=list(all_field_labels.keys()),
        format_func=lambda x: all_field_labels[x],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("### 📊 إحصائيات الجلسة")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📸 صور", st.session_state.total_analyzed)
    with col2:
        model_display = (
            st.session_state.used_model.replace("gemini-", "G-")
            if st.session_state.used_model else "---"
        )
        st.metric("🤖 نموذج", model_display)

    if st.button("🗑️ مسح جميع النتائج"):
        for key in ["analysis_done", "results", "batch_results", "extracted_text",
                    "analysis_method", "used_model", "tweet_data", "url_analysis_done",
                    "url_results", "pasted_image", "paste_analysis_done",
                    "paste_results", "total_analyzed"]:
            st.session_state[key] = defaults[key]
        st.rerun()

    with st.expander("📖 القاموس الدلالي"):
        for cat, kws in SEMANTIC_KEYWORDS.items():
            st.markdown(f"**{cat}:** {', '.join(kws[:4])}...")

# ============================================================
# الواجهة الرئيسية
# ============================================================
st.markdown("""
<div class="main-hero">
    <span class="hero-icon">🔍</span>
    <div class="hero-title">تحليل الصور في نقاط</div>
    <div class="hero-subtitle">تحليل منشورات منصة X بالذكاء الاصطناعي · بسرعة ودقة</div>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("""<div class="stat-card">
        <span class="stat-number">8</span>
        <span class="stat-label">حقل للتحليل</span>
    </div>""", unsafe_allow_html=True)
with col2:
    st.markdown("""<div class="stat-card">
        <span class="stat-number">6</span>
        <span class="stat-label">نموذج Gemini</span>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div class="stat-card">
        <span class="stat-number">{st.session_state.total_analyzed}</span>
        <span class="stat-label">صورة حُللت</span>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown("""<div class="stat-card">
        <span class="stat-number">3</span>
        <span class="stat-label">طرق الإدخال</span>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

tab_paste, tab_upload, tab_url, tab_guide = st.tabs([
    "📋 لصق من الحافظة",
    "📤 رفع صور",
    "🔗 رابط X",
    "📖 دليل الاستخدام"
])

# ─────────────────────────────────────────────
# تبويب 1: لصق من الحافظة
# ─────────────────────────────────────────────
with tab_paste:
    st.markdown("### 📋 الصق صورة من الحافظة")
    st.markdown("انسخ الصورة (Ctrl+C) ثم اضغط **Ctrl+V** في منطقة اللصق أدناه")

    try:
        from streamlit_paste_button import paste_image_button as pbutton
        paste_result = pbutton(
            label="📋 انقر هنا والصق صورة (Ctrl+V)",
            background_color="#1f6feb",
            hover_background_color="#388bfd",
            errors="ignore"
        )
        if paste_result and paste_result.image_data is not None:
            st.session_state.pasted_image = paste_result.image_data
            st.session_state.paste_analysis_done = False
    except ImportError:
        paste_component = """
        <div id="paste-zone" class="paste-zone" tabindex="0" style="outline:none;">
            <span class="paste-zone-icon">📋</span>
            <div class="paste-zone-text">
                انقر هنا ثم اضغط <strong>Ctrl+V</strong> للصق الصورة
            </div>
            <div id="paste-status" style="margin-top:10px;color:#58a6ff;font-size:0.9rem;"></div>
        </div>
        <script>
        const zone = document.getElementById('paste-zone');
        const status = document.getElementById('paste-status');
        zone.addEventListener('click', () => zone.focus());
        document.addEventListener('paste', function(e) {
            const items = e.clipboardData.items;
            for (let item of items) {
                if (item.type.startsWith('image/')) {
                    status.textContent = '✅ تم لصق الصورة!';
                    status.style.color = '#3fb950';
                }
            }
        });
        </script>
        """
        st.components.v1.html(paste_component, height=200)
        st.info("💡 لدعم اللصق المباشر أضف **streamlit-paste-button** إلى requirements.txt")

    if st.session_state.pasted_image is not None:
        img = st.session_state.pasted_image
        col_img, col_info = st.columns([1, 1])
        with col_img:
            st.image(img, caption="📸 الصورة الملصوقة", use_container_width=True)
        with col_info:
            st.markdown(f"""
            <div class="tweet-card">
                <div style="font-size:1rem;color:#8b949e;margin-bottom:8px;">📐 معلومات الصورة</div>
                <div style="color:#e6edf3;font-size:1rem;line-height:2;">
                    📏 الأبعاد: {img.size[0]} × {img.size[1]} بكسل<br>
                    🎨 النوع: {img.mode}<br>
                    📁 الحجم: {img.size[0]*img.size[1]//1000} KB تقريبًا
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🚀 تحليل الصورة الملصوقة", key="analyze_paste"):
            with st.spinner("⏳ جارٍ التحليل..."):
                result, method, model_name = analyze_image_full(
                    st.session_state.pasted_image,
                    st.session_state.api_key,
                    use_gemini
                )
                st.session_state.paste_results       = result
                st.session_state.paste_analysis_done = True
                st.session_state.analysis_method     = method
                st.session_state.used_model          = model_name
                st.session_state.total_analyzed     += 1
            st.rerun()

    if st.session_state.paste_analysis_done and st.session_state.paste_results:
        st.divider()
        render_all_results(
            st.session_state.paste_results,
            st.session_state.analysis_method,
            st.session_state.used_model,
            selected_fields
        )
        download_buttons(st.session_state.paste_results, "paste_result")

# ─────────────────────────────────────────────
# تبويب 2: رفع صور
# ─────────────────────────────────────────────
with tab_upload:
    st.markdown("### 📤 رفع صورة أو أكثر")

    uploaded_files = st.file_uploader(
        "اسحب الصور هنا أو انقر للتحديد",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
        key="file_uploader",
        label_visibility="collapsed"
    )

    if uploaded_files:
        st.markdown(f"**📸 {len(uploaded_files)} صورة محددة:**")
        cols = st.columns(min(len(uploaded_files), 4))
        images = []
        for i, f in enumerate(uploaded_files):
            img = Image.open(f)
            images.append(img)
            with cols[i % 4]:
                st.image(img, caption=f"صورة {i+1}", use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(f"🚀 تحليل {len(images)} صورة الآن", key="analyze_batch"):
            batch_results = []
            progress_bar  = st.progress(0, text="🔄 جارٍ التحليل...")

            for i, img in enumerate(images):
                progress_bar.progress(
                    (i + 1) / len(images),
                    text=f"🔄 تحليل الصورة {i+1} من {len(images)}..."
                )
                result, method, model_name = analyze_image_full(
                    img, st.session_state.api_key, use_gemini
                )
                batch_results.append({
                    "image_index": i + 1,
                    "filename": uploaded_files[i].name,
                    "result": result,
                    "method": method,
                    "model": model_name
                })
                if i < len(images) - 1:
                    time.sleep(1)

            progress_bar.progress(1.0, text="✅ اكتمل التحليل!")
            st.session_state.batch_results  = batch_results
            st.session_state.analysis_done  = True
            st.session_state.total_analyzed += len(images)
            if batch_results:
                st.session_state.used_model = batch_results[-1]["model"]
            st.rerun()

    if st.session_state.analysis_done and st.session_state.batch_results:
        st.divider()
        st.markdown(f"### ✅ نتائج التحليل ({len(st.session_state.batch_results)} صورة)")

        all_results  = [r["result"] for r in st.session_state.batch_results]
        all_json     = json.dumps(all_results, ensure_ascii=False, indent=2)
        st.download_button("⬇️ تنزيل جميع النتائج (JSON)", all_json,
                           "all_results.json", "application/json")

        for item in st.session_state.batch_results:
            with st.expander(f"📸 صورة {item['image_index']}: {item['filename']}"):
                render_all_results(
                    item["result"], item["method"], item["model"], selected_fields
                )
                download_buttons(item["result"], f"result_{item['image_index']}")

# ─────────────────────────────────────────────
# تبويب 3: رابط X  ✅ مع إصلاح KeyError
# ─────────────────────────────────────────────
with tab_url:
    st.markdown("### 🔗 تحليل منشور من رابط X")

    tweet_url = st.text_input(
        "أدخل رابط المنشور",
        placeholder="https://x.com/username/status/1234567890",
        label_visibility="visible"
    )

    col_fetch, col_analyze = st.columns(2)

    with col_fetch:
        if st.button("📥 جلب المنشور", key="fetch_tweet"):
            if tweet_url and ("x.com" in tweet_url or "twitter.com" in tweet_url):
                with st.spinner("⏳ جارٍ جلب المنشور..."):
                    tweet_data = fetch_tweet_content(tweet_url)
                    st.session_state.tweet_data        = tweet_data
                    st.session_state.url_analysis_done = False
                st.rerun()
            else:
                st.warning("⚠️ الرجاء إدخال رابط X/Twitter صحيح")

    # ✅ الإصلاح الثالث: استخدام .get() بدلاً من [] مع tweet_data
    with col_analyze:
        if st.button("🚀 جلب وتحليل", key="fetch_analyze"):
            if tweet_url and ("x.com" in tweet_url or "twitter.com" in tweet_url):
                with st.spinner("⏳ جارٍ الجلب والتحليل..."):
                    tweet_data = fetch_tweet_content(tweet_url)
                    st.session_state.tweet_data = tweet_data

                    result, method, model_name = None, "غير محدد", ""

                    # ✅ استخدام .get() لتجنب KeyError
                    tweet_text = tweet_data.get("text", "").strip()

                    # 1️⃣ Gemini على النص
                    if tweet_text and use_gemini and validate_api_key(st.session_state.api_key):
                        result, err, model_name = analyze_text_with_gemini(
                            tweet_text, st.session_state.api_key
                        )
                        if result:
                            method = "Gemini (نص)"

                    # 2️⃣ Gemini على Screenshot
                    if not result and tweet_data.get("screenshot") and use_gemini \
                            and validate_api_key(st.session_state.api_key):
                        result, err, model_name = analyze_with_gemini(
                            tweet_data["screenshot"], st.session_state.api_key
                        )
                        if result:
                            method = "Gemini (صورة)"

                    # 3️⃣ تحليل نصي ذكي
                    if not result:
                        fallback_text = tweet_text if tweet_text else "لا يوجد نص متاح"
                        result = analyze_post_smart(fallback_text)
                        method = "تحليل نصي ذكي"

                    # 4️⃣ OCR على Screenshot
                    if not result and tweet_data.get("screenshot"):
                        ocr_text = extract_text_ocr(tweet_data["screenshot"])
                        result   = analyze_post_smart(ocr_text)
                        method   = "OCR"

                    st.session_state.url_results       = result
                    st.session_state.url_analysis_done = True
                    st.session_state.analysis_method   = method
                    st.session_state.used_model        = model_name
                    st.session_state.total_analyzed   += 1
                st.rerun()
            else:
                st.warning("⚠️ الرجاء إدخال رابط X/Twitter صحيح")

    if st.session_state.tweet_data:
        td = st.session_state.tweet_data
        if td.get("author") or td.get("text"):
            st.markdown(f"""
            <div class="tweet-card">
                <div class="tweet-author">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
                         fill="#58a6ff" viewBox="0 0 16 16">
                        <path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425
                                 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86
                                 13.028h1.36L4.323 2.145H2.865z"/>
                    </svg>
                    {td.get('author', 'مجهول')}
                </div>
                <div class="tweet-text">{td.get('text', 'لا يوجد نص')[:500]}</div>
            </div>
            """, unsafe_allow_html=True)

        if td.get("screenshot"):
            st.image(td["screenshot"], caption="📸 Screenshot المنشور",
                     use_container_width=True)

    if st.session_state.url_analysis_done and st.session_state.url_results:
        st.divider()
        render_all_results(
            st.session_state.url_results,
            st.session_state.analysis_method,
            st.session_state.used_model,
            selected_fields
        )
        download_buttons(st.session_state.url_results, "url_result")

# ─────────────────────────────────────────────
# تبويب 4: دليل الاستخدام
# ─────────────────────────────────────────────
with tab_guide:
    st.markdown("""
    ### 📖 دليل الاستخدام السريع
    ---
    #### 🤖 للتحليل بالذكاء الاصطناعي (Gemini)
    1. احصل على مفتاح API المجاني من [Google AI Studio](https://aistudio.google.com/apikey)
    2. الصق المفتاح في الشريط الجانبي
    3. اختر **🤖 Gemini AI** من طريقة التحليل

    ---
    #### 📋 لصق من الحافظة
    1. افتح الصورة في أي برنامج وانسخها (Ctrl+C)
    2. اضغط على تبويب **لصق من الحافظة**
    3. انقر في المنطقة المخصصة ثم اضغط Ctrl+V

    ---
    #### 📤 رفع صور متعددة
    1. انقر على تبويب **رفع صور**
    2. اختر صورة أو أكثر (PNG, JPG, WEBP)
    3. اضغط **تحليل ... صورة الآن**

    ---
    #### 🔗 تحليل عبر الرابط
    1. انسخ رابط المنشور من X
    2. الصقه في خانة **رابط X**
    3. اضغط **جلب وتحليل**

    ---
    #### 📊 الحقول المُستخرجة
    | الحقل | الوصف |
    |-------|-------|
    | 👤 صاحب المنشور | معرف من نشر أصلاً |
    | 💬 صاحب التعليق | معرف من علّق |
    | 🎯 المُستشهد به | الشخص المذكور |
    | 📝 محتوى المنشور | النص الكامل |
    | 🎬 المقطع | وصف الفيديو/الصورة |
    | 💭 التعليق | نص التعليق |
    | 🔍 الرأي | الموقف المُعبَّر عنه |
    | 📋 الملخص التنفيذي | ملخص احترافي ≥80 كلمة |

    ---
    > 💡 **نصيحة:** استخدم Gemini 2.0 Flash Lite للحصول على 1500 تحليل/يوم مجاناً!
    """)

# ============================================================
# تذييل
# ============================================================
st.markdown("""
<div class="footer">
    📸 تحليل الصور في نقاط — الإصدار 4.2 &nbsp;|&nbsp;
    مبني بـ ❤️ باستخدام Streamlit & Gemini AI &nbsp;|&nbsp;
    <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#58a6ff;">
        🔑 احصل على مفتاح Gemini المجاني
    </a>
</div>
""", unsafe_allow_html=True)
