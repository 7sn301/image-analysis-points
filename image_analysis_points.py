# ============================================================
# محلل حسابات X الاستخباراتي - v10.3.4
# إصلاح: شاشة سوداء + RTL كامل + تصدير احترافي
# ============================================================

import streamlit as st
import requests
import json
import base64
import re
import io
import os
import time
import random
from datetime import datetime
from PIL import Image

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

try:
    from pptx import Presentation
    from pptx.util import Inches as PInches, Pt as PPt, Emu
    from pptx.dml.color import RGBColor as PRGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn as pqn
    from pptx.oxml import parse_xml
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

import google.generativeai as genai

# ─── ثوابت ───────────────────────────────────────────────────
VERSION         = "v10.3.4"
PAGE_TITLE      = "محلل حسابات X الاستخباراتي"
PAGE_ICON       = "🔍"
FXTWITTER_TWEET = "https://api.fxtwitter.com/status/{tweet_id}"
FXTWITTER_USER  = "https://api.fxtwitter.com/{username}"
TWITTERAPI_BASE = "https://api.twitterapi.io"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
]

GEMINI_MODELS = {
    "gemini-2.5-flash (سريع - موصى به)": "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro (متقدم)":            "gemini-2.5-pro-preview-05-06",
    "gemini-2.0-flash (اقتصادي)":        "gemini-2.0-flash",
}

# كلمات مفتاحية للتحليل الاستخباراتي
INTEL_KEYWORDS = {
    "العداء المباشر للسعودية": [
        "ارض الحرمين","المهلكة","ال سلول","شولوم","البقرة","الحلوب",
        "قمع","فساد","إسقاط النظام","تكميم الأفواه","اعتقالات سياسية",
        "معتقل","العدائية","مقاطعة السعودية","حملة ضد السعودية",
        "فضائح السعودية","فشل سعودي","استهداف السعودية",
    ],
    "التحريض السياسي": [
        "زعزعة الأمن","إسقاط الحكم","التحريض ضد الدولة","الفوضى",
        "العصيان","التجنيد ضد السعودية","إسقاط النظام","ثورة",
        "الدعوة للتظاهر","مظاهرة","انتفاضة","تمرد","عصيان مدني",
    ],
    "الحملات الإعلامية المعادية": [
        "الذباب الإلكتروني","غسيل سمعة","حراك شعبي","انفجار شعبي",
        "الغضب الشعبي","الشارع يغلي","قمع حريات",
    ],
    "الإساءة للهوية الوطنية": [
        "العاطلين","البطالة","العنصرية ضد السعوديين","كراهية السعوديين",
        "الإساءة للهوية الوطنية","التشكيك بالوطنية","إهانة رموز الدولة",
    ],
}

IMAGE_ANALYSIS_POINTS = {
    "📍 تحليل الموقع الجغرافي": "حدد الموقع الجغرافي والمعالم والدولة والمدينة المحتملة من الصورة.",
    "👥 تحليل الأشخاص": "صف الأشخاص في الصورة: الجنس، العمر التقريبي، الملابس، الهوية المحتملة.",
    "🚗 تحليل المركبات": "حدد أي مركبات تظهر في الصورة مع نوعها ولونها وأي معلومات مميزة.",
    "📄 تحليل المستندات": "استخرج أي نصوص أو معلومات من مستندات أو لافتات أو كتابات في الصورة.",
    "⚠️ تحليل التهديدات": "حدد أي محتوى مثير للقلق أو تهديدات أو محتوى عنيف في الصورة.",
    "🏛️ تحليل البنية التحتية": "صف أي مبانٍ أو منشآت أو بنية تحتية مرئية في الصورة.",
    "🕐 تحليل التوقيت": "قدّر الوقت من الإضاءة والظلال وأي مؤشرات زمنية في الصورة.",
    "🎭 تحليل الأحداث": "صف أي حدث أو اجتماع أو نشاط يجري في الصورة.",
    "🔍 كشف التزوير": "قيّم مدى أصالة الصورة وابحث عن علامات التحرير أو التلاعب.",
    "📊 تحليل شامل": "قدم تحليلاً شاملاً كاملاً لجميع جوانب الصورة من منظور استخباراتي.",
}

# ─── CSS مُصلح (يحل مشكلة الشاشة السوداء) ──────────────────
FIXED_CSS = """
<style>
/* ========= إصلاح الشاشة السوداء - إجبار الألوان ========= */
html, body {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
}

.stApp {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    direction: rtl !important;
    font-family: 'Segoe UI', 'Arial', sans-serif !important;
}

/* إصلاح الحاوية الرئيسية */
.main .block-container {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    padding-top: 2rem !important;
    max-width: 1100px !important;
}

/* إصلاح جميع النصوص */
p, span, label, div, h1, h2, h3, h4, h5, h6,
.stMarkdown, .stMarkdown p, .stMarkdown span,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p {
    color: #c9d1d9 !important;
    direction: rtl !important;
    text-align: right !important;
}

/* ========= الشريط الجانبي ========= */
[data-testid="stSidebar"] {
    background-color: #161b22 !important;
    direction: rtl !important;
}
[data-testid="stSidebar"] * {
    color: #c9d1d9 !important;
    direction: rtl !important;
    text-align: right !important;
}

/* ========= حقول الإدخال ========= */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stTextInput input,
.stTextArea textarea {
    background-color: #21262d !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    direction: rtl !important;
    text-align: right !important;
    font-size: 14px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88,166,255,0.2) !important;
}

/* ========= Labels ========= */
.stTextInput label,
.stTextArea label,
.stSelectbox label,
label[data-testid="stWidgetLabel"] {
    color: #8b949e !important;
    direction: rtl !important;
    text-align: right !important;
    font-size: 13px !important;
    display: block !important;
    width: 100% !important;
}

/* ========= الأزرار ========= */
.stButton > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.5rem !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    direction: rtl !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #388bfd, #58a6ff) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 15px rgba(31,111,235,0.4) !important;
}

/* ========= التبويبات ========= */
.stTabs [data-baseweb="tab-list"] {
    background-color: #161b22 !important;
    border-radius: 10px !important;
    gap: 4px !important;
    direction: rtl !important;
    border-bottom: 2px solid #30363d !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    color: #8b949e !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    padding: 0.5rem 1.2rem !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background-color: #1f6feb !important;
    color: #ffffff !important;
}

/* ========= القائمة المنسدلة ========= */
.stSelectbox > div > div {
    background-color: #21262d !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    direction: rtl !important;
}
.stSelectbox > div > div > div {
    color: #c9d1d9 !important;
}

/* ========= رسائل التنبيه ========= */
.stAlert, .stSuccess, .stError, .stWarning, .stInfo,
[data-testid="stAlert"] {
    direction: rtl !important;
    text-align: right !important;
    border-radius: 8px !important;
}
.stAlert p, .stSuccess p, .stError p, .stWarning p, .stInfo p {
    color: inherit !important;
    direction: rtl !important;
    text-align: right !important;
}

/* ========= الفاصل ========= */
hr {
    border-color: #30363d !important;
}

/* ========= بطاقات مخصصة ========= */
.intel-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.8rem 0;
    direction: rtl;
    text-align: right;
}
.intel-card h3, .intel-card h4 {
    color: #58a6ff !important;
    margin-bottom: 0.5rem;
}
.intel-card p, .intel-card span, .intel-card li {
    color: #c9d1d9 !important;
}

/* ========= الميزان ========= */
.threat-badge {
    display: inline-block;
    padding: 0.3rem 1rem;
    border-radius: 20px;
    font-weight: bold;
    font-size: 14px;
    margin: 0.5rem 0;
}

/* ========= Expander ========= */
.streamlit-expanderHeader {
    background-color: #161b22 !important;
    color: #c9d1d9 !important;
    direction: rtl !important;
    text-align: right !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
}
.streamlit-expanderContent {
    background-color: #0d1117 !important;
    border: 1px solid #30363d !important;
    direction: rtl !important;
}

/* ========= تمرير ========= */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #58a6ff; }

/* ========= إصلاح download button ========= */
.stDownloadButton > button {
    background: linear-gradient(135deg, #238636, #2ea043) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    direction: rtl !important;
}
</style>
"""

# ─── دوال مساعدة ─────────────────────────────────────────────
def safe_text(val, default="غير متوفر"):
    if val is None: return default
    s = str(val).strip()
    return s if s else default

def format_number(n):
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(n)

def format_date(s):
    try:
        dt = datetime.strptime(s, "%a %b %d %H:%M:%S +0000 %Y")
        return dt.strftime("%Y/%m/%d")
    except: return safe_text(s)

def extract_tweet_id(url):
    m = re.search(r'/status/(\d+)', str(url))
    return m.group(1) if m else None

def extract_username(text):
    text = text.strip().lstrip('@')
    for pat in [r'(?:twitter\.com|x\.com)/([^/?#\s]+)', r'^([A-Za-z0-9_]{1,50})$']:
        m = re.search(pat, text)
        if m:
            u = m.group(1)
            if u.lower() not in ('home','explore','notifications','messages','i','settings'):
                return u
    return None

def image_to_base64(img: Image.Image, fmt="JPEG") -> str:
    buf = io.BytesIO()
    rgb = img.convert("RGB") if fmt == "JPEG" else img
    rgb.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

def base64_to_bytesio(b64: str) -> io.BytesIO:
    return io.BytesIO(base64.b64decode(b64))

def download_image_b64(url: str) -> str | None:
    try:
        h = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            return image_to_base64(img)
    except: pass
    return None

def calc_image_size_word(b64, max_w_cm=15.0, max_h_cm=12.0):
    try:
        img = Image.open(base64_to_bytesio(b64))
        w, h = img.size
        ratio = w / h
        if w > h:
            nw = min(max_w_cm, max_w_cm)
            nh = nw / ratio
        else:
            nh = min(max_h_cm, max_h_cm)
            nw = nh * ratio
        if nw > max_w_cm: nw = max_w_cm; nh = nw / ratio
        if nh > max_h_cm: nh = max_h_cm; nw = nh * ratio
        return Cm(nw), Cm(nh)
    except:
        return Cm(10), Cm(8)

def calc_image_size_pptx(b64, slide_w=9144000, slide_h=5143500, margin=457200):
    try:
        img = Image.open(base64_to_bytesio(b64))
        w, h = img.size
        max_w = slide_w - margin * 2
        max_h = slide_h - margin * 4
        scale = min(max_w / w, max_h / h)
        return int(w * scale), int(h * scale)
    except:
        return int(slide_w * 0.7), int(slide_h * 0.6)

# ─── جلب البيانات ─────────────────────────────────────────────
def fetch_fxtwitter_tweet(tweet_id: str) -> dict | None:
    try:
        url = FXTWITTER_TWEET.format(tweet_id=tweet_id)
        h   = {"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"}
        r   = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == 200:
                return d.get("tweet") or d.get("status")
    except Exception as e:
        st.error(f"خطأ في جلب التغريدة: {e}")
    return None

def fetch_fxtwitter_user(username: str) -> dict | None:
    try:
        url = FXTWITTER_USER.format(username=username)
        h   = {"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"}
        r   = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == 200:
                return d.get("user")
    except Exception as e:
        st.error(f"خطأ في جلب بيانات الحساب: {e}")
    return None

def fetch_user_tweets_twitterapi(username: str, api_key: str, limit: int = 500) -> list:
    tweets, cursor = [], None
    headers = {"X-API-Key": api_key, "Accept": "application/json"}
    while len(tweets) < limit:
        params = {"userName": username, "limit": 20}
        if cursor: params["cursor"] = cursor
        try:
            r = requests.get(f"{TWITTERAPI_BASE}/twitter/user/last_tweets",
                             headers=headers, params=params, timeout=20)
            if r.status_code != 200: break
            d = r.json()
            batch = d.get("tweets", d.get("data", []))
            if not batch: break
            tweets.extend(batch)
            cursor = d.get("next_cursor") or d.get("cursor")
            if not cursor: break
            time.sleep(0.3)
        except: break
    return tweets[:limit]

def scan_keywords(texts: list) -> dict:
    combined = " ".join(texts).lower()
    found = {}
    for cat, kws in INTEL_KEYWORDS.items():
        hits = [k for k in kws if k.lower() in combined]
        if hits: found[cat] = hits
    return found

def get_threat_level(score: int) -> tuple:
    if score >= 8: return "🔴 خطر عالٍ جداً", "#ff4444", "red"
    if score >= 6: return "🟠 خطر عالٍ",       "#ff8800", "orange"
    if score >= 4: return "🟡 خطر متوسط",     "#ffcc00", "yellow"
    if score >= 2: return "🟢 خطر منخفض",     "#44bb44", "green"
    return "⚪ لا يوجد خطر",                   "#888888", "gray"

# ─── Gemini ───────────────────────────────────────────────────
def gemini_text(prompt: str, model_id: str) -> str:
    try:
        m  = genai.GenerativeModel(model_id)
        r  = m.generate_content(prompt)
        return r.text
    except Exception as e:
        return f"خطأ في التحليل: {e}"

def gemini_with_images(prompt: str, images_b64: list, model_id: str) -> str:
    try:
        m    = genai.GenerativeModel(model_id)
        parts = [prompt]
        for b64 in images_b64:
            data = base64.b64decode(b64)
            parts.append({"mime_type": "image/jpeg", "data": data})
        r = m.generate_content(parts)
        return r.text
    except Exception as e:
        return f"خطأ في تحليل الصورة: {e}"

def generate_intel_summary(user_data: dict, tweets: list, keyword_hits: dict, model_id: str) -> str:
    bio   = safe_text(user_data.get("description",""))
    name  = safe_text(user_data.get("name",""))
    sname = safe_text(user_data.get("screen_name",""))
    loc   = safe_text(user_data.get("location",""))
    foll  = format_number(user_data.get("followers","0"))
    
    tweets_sample = "\n".join([
        t.get("text","") if isinstance(t, dict) else str(t)
        for t in tweets[:100]
    ])
    
    kw_text = ""
    for cat, hits in keyword_hits.items():
        kw_text += f"- {cat}: {', '.join(hits)}\n"
    
    prompt = f"""
أنت محلل استخباراتي متخصص في تحليل حسابات وسائل التواصل الاجتماعي.
قم بتحليل الحساب التالي وتقديم تقرير استخباراتي شامل باللغة العربية.

## بيانات الحساب:
- الاسم: {name} (@{sname})
- الموقع: {loc}
- عدد المتابعين: {foll}
- السيرة الذاتية: {bio}

## الكلمات المفتاحية المكتشفة:
{kw_text if kw_text else "لم تُكتشف كلمات مفتاحية مثيرة للقلق"}

## نماذج من التغريدات (أول 100):
{tweets_sample[:3000] if tweets_sample else "لا توجد تغريدات متاحة"}

## المطلوب:
1. **مستوى التهديد** (1-10): حدد رقماً من 1 إلى 10
2. **التصنيف**: (معادٍ للسعودية / متطرف / محرض / عادي)
3. **الكلمات المكتشفة**: عدد ونوع الكلمات المثيرة للقلق
4. **نمط السلوك**: وصف نمط التغريدات والأسلوب
5. **المحتوى المثير للقلق**: أبرز المحتوى المشكوك فيه
6. **التوصيات**: توصيات استخباراتية للتعامل مع هذا الحساب

قدم التقرير بتنسيق منظم مع عناوين واضحة.
"""
    return gemini_text(prompt, model_id)

# ─── تصدير Word ───────────────────────────────────────────────
def _set_rtl_para(para):
    try:
        pPr = para._p.get_or_add_pPr()
        bidi = OxmlElement('w:bidi')
        bidi.set(qn('w:val'), '1')
        pPr.append(bidi)
        jc = OxmlElement('w:jc')
        jc.set(qn('w:val'), 'right')
        pPr.append(jc)
    except: pass

def export_to_word(user_data: dict, tweets: list, intel_report: str,
                   exec_summary: str, images_data: list, text_analysis: str) -> bytes:
    if not DOCX_OK:
        return b""
    doc = Document()
    # إعداد الصفحة
    section = doc.sections[0]
    section.page_width  = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.5)

    def add_rtl_heading(text, level=1):
        h = doc.add_heading(text, level=level)
        h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_rtl_para(h)
        for run in h.runs:
            run.font.color.rgb = RGBColor(0x1F, 0x6F, 0xEB)

    def add_rtl_para(text, bold=False, color=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_rtl_para(p)
        run = p.add_run(text)
        run.font.size = Pt(12)
        if bold: run.font.bold = True
        if color: run.font.color.rgb = RGBColor(*color)
        return p

    # غلاف
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run("تقرير استخباراتي - محلل حسابات X")
    run.font.size = Pt(22); run.font.bold = True
    run.font.color.rgb = RGBColor(0x1F, 0x6F, 0xEB)
    doc.add_paragraph(f"التاريخ: {datetime.now().strftime('%Y/%m/%d')} | {VERSION}").alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # بيانات الحساب
    if user_data:
        add_rtl_heading("📋 بيانات الحساب", 1)
        fields = [
            ("الاسم",          user_data.get("name","")),
            ("المعرف",         f"@{user_data.get('screen_name','')}"),
            ("الموقع",         user_data.get("location","")),
            ("السيرة الذاتية", user_data.get("description","")),
            ("المتابعون",      format_number(user_data.get("followers",0))),
            ("يتابع",          format_number(user_data.get("following",0))),
            ("التغريدات",      format_number(user_data.get("tweets",0))),
            ("الإعجابات",      format_number(user_data.get("likes",0))),
            ("تاريخ الانضمام", format_date(user_data.get("created",""))),
        ]
        for label, val in fields:
            if val and val != "غير متوفر":
                add_rtl_para(f"{label}: {val}")

    doc.add_paragraph()

    # التقرير الاستخباراتي
    if intel_report:
        add_rtl_heading("🔍 التقرير الاستخباراتي", 1)
        for line in intel_report.split('\n'):
            add_rtl_para(line)

    doc.add_paragraph()

    # الملخص التنفيذي
    if exec_summary:
        add_rtl_heading("📊 الملخص التنفيذي", 1)
        for line in exec_summary.split('\n'):
            add_rtl_para(line)

    # الصور والتحليلات
    for i, img_info in enumerate(images_data or []):
        doc.add_page_break()
        add_rtl_heading(f"🖼️ الصورة {i+1} - {img_info.get('label','')}", 2)
        if img_info.get("b64"):
            try:
                w_cm, h_cm = calc_image_size_word(img_info["b64"])
                doc.add_picture(base64_to_bytesio(img_info["b64"]), width=w_cm, height=h_cm)
            except: pass
        if img_info.get("analysis"):
            add_rtl_heading("نتيجة التحليل:", 3)
            for line in img_info["analysis"].split('\n'):
                add_rtl_para(line)

    # تحليل النص
    if text_analysis:
        doc.add_page_break()
        add_rtl_heading("📝 تحليل النص", 1)
        for line in text_analysis.split('\n'):
            add_rtl_para(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

# ─── تصدير PowerPoint ─────────────────────────────────────────
def _set_rtl_pptx(tf):
    try:
        from lxml import etree
        for para in tf.text_frame.paragraphs:
            pPr = para._p.get_or_add_pPr()
            pPr.set('algn', 'r')
            pPr.set('rtl', '1')
    except: pass

def _add_pptx_slide(prs, layout_idx=6):
    layout = prs.slide_layouts[min(layout_idx, len(prs.slide_layouts)-1)]
    return prs.slides.add_slide(layout)

def _pptx_textbox(slide, left, top, width, height,
                  text, font_size=18, bold=False,
                  color=(201,209,217), bg=None, align=PP_ALIGN.RIGHT):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf    = txBox.text_frame
    tf.word_wrap = True
    if bg:
        fill = txBox.fill
        fill.solid()
        fill.fore_color.rgb = PRGBColor(*bg)
    para = tf.paragraphs[0]
    para.alignment = align
    run  = para.add_run()
    run.text = text
    run.font.size  = PPt(font_size)
    run.font.bold  = bold
    run.font.color.rgb = PRGBColor(*color)
    try:
        pPr = para._p.get_or_add_pPr()
        pPr.set('rtl','1'); pPr.set('algn','r')
    except: pass
    return txBox

def export_to_pptx(user_data: dict, tweets: list, intel_report: str,
                   exec_summary: str, images_data: list, text_analysis: str) -> bytes:
    if not PPTX_OK:
        return b""

    prs = Presentation()
    prs.slide_width  = PInches(13.33)
    prs.slide_height = PInches(7.5)

    W = int(prs.slide_width)
    H = int(prs.slide_height)
    M = int(PInches(0.5))

    C_BG    = (13, 17, 23)       # خلفية داكنة
    C_CARD  = (22, 27, 34)       # بطاقة
    C_BLUE  = (31, 111, 235)     # أزرق رئيسي
    C_TEXT  = (201, 209, 217)    # نص فاتح
    C_DIM   = (139, 148, 158)    # نص خافت
    C_RED   = (248, 81, 73)      # أحمر تهديد
    C_GREEN = (63, 185, 80)      # أخضر

    def bg_slide(slide, color=C_BG):
        bg = slide.shapes.add_shape(1, 0, 0, W, H)
        bg.fill.solid(); bg.fill.fore_color.rgb = PRGBColor(*color)
        bg.line.fill.background()

    def add_slide_title(slide, title, subtitle=""):
        bg_slide(slide)
        # شريط عنوان
        bar = slide.shapes.add_shape(1, 0, 0, W, int(PInches(1)))
        bar.fill.solid(); bar.fill.fore_color.rgb = PRGBColor(*C_BLUE)
        bar.line.fill.background()
        _pptx_textbox(slide, M, int(PInches(0.1)), W - 2*M, int(PInches(0.8)),
                      title, font_size=28, bold=True, color=(255,255,255), align=PP_ALIGN.RIGHT)
        if subtitle:
            _pptx_textbox(slide, M, int(PInches(1.1)), W - 2*M, int(PInches(0.5)),
                          subtitle, font_size=14, color=C_DIM, align=PP_ALIGN.RIGHT)

    # ── شريحة 1: الغلاف ──────────────────────────────────────
    s1 = _add_pptx_slide(prs)
    bg_slide(s1)
    # بطاقة وسط
    card_x = int(PInches(1.5)); card_y = int(PInches(1.5))
    card_w = int(PInches(10.3)); card_h = int(PInches(4.5))
    card = s1.shapes.add_shape(1, card_x, card_y, card_w, card_h)
    card.fill.solid(); card.fill.fore_color.rgb = PRGBColor(*C_CARD)
    card.line.color.rgb = PRGBColor(*C_BLUE); card.line.width = int(PPt(1.5))

    _pptx_textbox(s1, card_x+M, card_y+int(PInches(0.3)), card_w-2*M, int(PInches(1.2)),
                  "🔍 تقرير استخباراتي", font_size=34, bold=True,
                  color=(255,255,255), align=PP_ALIGN.CENTER)
    _pptx_textbox(s1, card_x+M, card_y+int(PInches(1.5)), card_w-2*M, int(PInches(0.8)),
                  "محلل حسابات X الاستخباراتي", font_size=20,
                  color=C_DIM, align=PP_ALIGN.CENTER)
    _pptx_textbox(s1, card_x+M, card_y+int(PInches(2.3)), card_w-2*M, int(PInches(0.6)),
                  f"التاريخ: {datetime.now().strftime('%Y/%m/%d')}  |  {VERSION}",
                  font_size=14, color=C_DIM, align=PP_ALIGN.CENTER)
    # شارة سري
    badge = s1.shapes.add_shape(1, int(PInches(5.8)), card_y+int(PInches(3.3)),
                                 int(PInches(1.7)), int(PInches(0.5)))
    badge.fill.solid(); badge.fill.fore_color.rgb = PRGBColor(*C_RED)
    badge.line.fill.background()
    _pptx_textbox(s1, int(PInches(5.8)), card_y+int(PInches(3.3)),
                  int(PInches(1.7)), int(PInches(0.5)),
                  "🔒 سري", font_size=13, bold=True,
                  color=(255,255,255), align=PP_ALIGN.CENTER)

    # ── شريحة 2: ملف الحساب ──────────────────────────────────
    s2 = _add_pptx_slide(prs)
    add_slide_title(s2, "📋 ملف الحساب",
                    f"@{safe_text(user_data.get('screen_name',''))} | {safe_text(user_data.get('name',''))}" if user_data else "")

    if user_data:
        stats = [
            ("👥 المتابعون", format_number(user_data.get("followers",0))),
            ("➡️ يتابع",    format_number(user_data.get("following",0))),
            ("📝 التغريدات", format_number(user_data.get("tweets",0))),
            ("❤️ الإعجابات", format_number(user_data.get("likes",0))),
        ]
        box_w = int(PInches(2.5)); box_h = int(PInches(1.0))
        gap   = int(PInches(0.3))
        for i, (lbl, val) in enumerate(stats):
            bx = int(PInches(0.5)) + i * (box_w + gap)
            by = int(PInches(1.7))
            box = s2.shapes.add_shape(1, bx, by, box_w, box_h)
            box.fill.solid(); box.fill.fore_color.rgb = PRGBColor(*C_CARD)
            box.line.color.rgb = PRGBColor(*C_BLUE); box.line.width = int(PPt(0.75))
            _pptx_textbox(s2, bx, by+int(PPt(2)), box_w, int(PPt(20)),
                          val, font_size=20, bold=True,
                          color=(88,166,255), align=PP_ALIGN.CENTER)
            _pptx_textbox(s2, bx, by+int(PInches(0.55)), box_w, int(PPt(18)),
                          lbl, font_size=12, color=C_DIM, align=PP_ALIGN.CENTER)

        bio = safe_text(user_data.get("description",""))
        loc = safe_text(user_data.get("location",""))
        joined = format_date(safe_text(user_data.get("created","")))
        info_text = f"السيرة الذاتية: {bio}\nالموقع: {loc} | الانضمام: {joined}"
        _pptx_textbox(s2, M, int(PInches(3.0)), W-2*M, int(PInches(1.8)),
                      info_text, font_size=13, color=C_TEXT, align=PP_ALIGN.RIGHT)

    # ── شريحة 3: التقرير الاستخباراتي ────────────────────────
    if intel_report:
        chunks = [intel_report[i:i+800] for i in range(0, len(intel_report), 800)]
        for ci, chunk in enumerate(chunks[:4]):
            s = _add_pptx_slide(prs)
            add_slide_title(s, f"🔍 التقرير الاستخباراتي {'(تابع)' if ci>0 else ''}",
                            f"الجزء {ci+1} من {len(chunks)}" if len(chunks)>1 else "")
            _pptx_textbox(s, M, int(PInches(1.4)), W-2*M, int(PInches(5.5)),
                          chunk, font_size=13, color=C_TEXT, align=PP_ALIGN.RIGHT)

    # ── شريحة 4: الملخص التنفيذي ─────────────────────────────
    if exec_summary:
        chunks = [exec_summary[i:i+800] for i in range(0, len(exec_summary), 800)]
        for ci, chunk in enumerate(chunks[:3]):
            s = _add_pptx_slide(prs)
            add_slide_title(s, f"📊 الملخص التنفيذي {'(تابع)' if ci>0 else ''}")
            _pptx_textbox(s, M, int(PInches(1.4)), W-2*M, int(PInches(5.5)),
                          chunk, font_size=13, color=C_TEXT, align=PP_ALIGN.RIGHT)

    # ── شريحة 5: الصور ───────────────────────────────────────
    for i, img_info in enumerate(images_data or []):
        s = _add_pptx_slide(prs)
        add_slide_title(s, f"🖼️ الصورة {i+1}: {img_info.get('label','')}")
        if img_info.get("b64"):
            try:
                iw, ih = calc_image_size_pptx(img_info["b64"], W, H)
                ix = (W - iw) // 2
                iy = int(PInches(1.3))
                s.shapes.add_picture(base64_to_bytesio(img_info["b64"]), ix, iy, iw, ih)
            except: pass
        if img_info.get("analysis"):
            s2_ = _add_pptx_slide(prs)
            add_slide_title(s2_, f"📝 تحليل الصورة {i+1}")
            _pptx_textbox(s2_, M, int(PInches(1.4)), W-2*M, int(PInches(5.5)),
                          img_info["analysis"][:800], font_size=12,
                          color=C_TEXT, align=PP_ALIGN.RIGHT)

    # ── شريحة 6: تحليل النص ──────────────────────────────────
    if text_analysis:
        s = _add_pptx_slide(prs)
        add_slide_title(s, "📝 تحليل النص")
        _pptx_textbox(s, M, int(PInches(1.4)), W-2*M, int(PInches(5.5)),
                      text_analysis[:800], font_size=13,
                      color=C_TEXT, align=PP_ALIGN.RIGHT)

    # ── شريحة 7: الخاتمة ─────────────────────────────────────
    s_end = _add_pptx_slide(prs)
    bg_slide(s_end)
    _pptx_textbox(s_end, M, int(PInches(2.5)), W-2*M, int(PInches(1.5)),
                  "🔒 نهاية التقرير الاستخباراتي", font_size=28, bold=True,
                  color=(255,255,255), align=PP_ALIGN.CENTER)
    _pptx_textbox(s_end, M, int(PInches(4.0)), W-2*M, int(PInches(0.8)),
                  f"محلل حسابات X الاستخباراتي | {VERSION}",
                  font_size=14, color=C_DIM, align=PP_ALIGN.CENTER)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

# ─── أزرار التصدير ────────────────────────────────────────────
def render_export_buttons(user_data, tweets, intel_report, exec_summary, images_data, text_analysis):
    user_data    = user_data    or {}
    intel_report = intel_report or ""
    exec_summary = exec_summary or ""
    images_data  = images_data  or []
    text_analysis= text_analysis or ""

    st.markdown("---")
    st.markdown("### 📤 تصدير التقرير")
    c1, c2, c3 = st.columns(3)

    uname = safe_text(user_data.get("screen_name","report"), "report")
    ts    = datetime.now().strftime("%Y%m%d_%H%M")

    with c1:
        if DOCX_OK:
            docx_data = export_to_word(user_data, tweets, intel_report,
                                        exec_summary, images_data, text_analysis)
            if docx_data:
                st.download_button("📄 تنزيل Word",  data=docx_data,
                                   file_name=f"Intel_{uname}_{ts}.docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   use_container_width=True)
    with c2:
        if PPTX_OK:
            pptx_data = export_to_pptx(user_data, tweets, intel_report,
                                        exec_summary, images_data, text_analysis)
            if pptx_data:
                st.download_button("📊 تنزيل PowerPoint", data=pptx_data,
                                   file_name=f"Intel_{uname}_{ts}.pptx",
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                   use_container_width=True)
    with c3:
        txt_parts = []
        if user_data:
            txt_parts.append("=== بيانات الحساب ===")
            for k in ("name","screen_name","description","location","followers","following","tweets","likes","created"):
                v = user_data.get(k,"")
                if v: txt_parts.append(f"{k}: {v}")
        if intel_report: txt_parts += ["", "=== التقرير الاستخباراتي ===", intel_report]
        if exec_summary:  txt_parts += ["", "=== الملخص التنفيذي ===",    exec_summary]
        if text_analysis: txt_parts += ["", "=== تحليل النص ===",          text_analysis]
        txt_bytes = "\n".join(txt_parts).encode("utf-8")
        st.download_button("📝 تنزيل TXT", data=txt_bytes,
                           file_name=f"Intel_{uname}_{ts}.txt",
                           mime="text/plain", use_container_width=True)

# ─── عرض بطاقة الحساب ────────────────────────────────────────
def render_user_card(user: dict):
    if not user: return
    name   = safe_text(user.get("name",""))
    sname  = safe_text(user.get("screen_name",""))
    bio    = safe_text(user.get("description",""), "")
    loc    = safe_text(user.get("location",""),    "")
    joined = format_date(safe_text(user.get("created","")))
    foll   = format_number(user.get("followers",0))
    fing   = format_number(user.get("following",0))
    twts   = format_number(user.get("tweets",   0))
    likes  = format_number(user.get("likes",    0))
    ver    = "✅ موثق" if user.get("blue_verified") else ""
    banner = user.get("banner_url","")
    avatar = (user.get("avatar_url","") or "").replace("_normal","_400x400")

    banner_html = f'<img src="{banner}" style="width:100%;height:120px;object-fit:cover;border-radius:10px 10px 0 0;">' if banner else ""
    avatar_html = f'<img src="{avatar}" style="width:80px;height:80px;border-radius:50%;border:3px solid #1f6feb;margin-top:-40px;">' if avatar else "👤"

    st.markdown(f"""
<div class="intel-card" style="padding:0;overflow:hidden;">
  {banner_html}
  <div style="padding:1rem;text-align:right;">
    {avatar_html}
    <h2 style="color:#58a6ff;margin:0.5rem 0 0;">{name} {ver}</h2>
    <p style="color:#8b949e;margin:0 0 0.5rem;">@{sname}</p>
    {'<p style="color:#c9d1d9;">'+bio+'</p>' if bio else ""}
    {'<p style="color:#8b949e;font-size:13px;">📍 '+loc+'</p>' if loc else ""}
    <p style="color:#8b949e;font-size:13px;">📅 انضم: {joined}</p>
    <div style="display:flex;gap:1rem;justify-content:flex-end;flex-wrap:wrap;margin-top:0.8rem;">
      <span style="color:#c9d1d9;"><b style="color:#58a6ff;">{foll}</b> متابع</span>
      <span style="color:#c9d1d9;"><b style="color:#58a6ff;">{fing}</b> يتابع</span>
      <span style="color:#c9d1d9;"><b style="color:#58a6ff;">{twts}</b> تغريدة</span>
      <span style="color:#c9d1d9;"><b style="color:#58a6ff;">{likes}</b> إعجاب</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── عرض بطاقة التغريدة ──────────────────────────────────────
def render_tweet_card(tweet: dict):
    if not tweet: return
    text  = safe_text(tweet.get("text",""), "")
    date  = format_date(safe_text(tweet.get("created_at","")))
    likes = format_number(tweet.get("likes",0))
    rts   = format_number(tweet.get("retweets",0))
    views = format_number(tweet.get("views",0))
    url   = safe_text(tweet.get("url",""), "#")
    author= tweet.get("author",{}) or {}
    aname = safe_text(author.get("name",""))
    sname = safe_text(author.get("screen_name",""))

    st.markdown(f"""
<div class="intel-card">
  <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
    <span style="color:#8b949e;font-size:13px;">📅 {date}</span>
    <span style="color:#58a6ff;font-weight:bold;">{aname} (@{sname})</span>
  </div>
  <p style="color:#c9d1d9;line-height:1.7;font-size:15px;">{text}</p>
  <div style="display:flex;gap:1.5rem;justify-content:flex-end;margin-top:0.8rem;">
    <span style="color:#8b949e;font-size:13px;">❤️ {likes}</span>
    <span style="color:#8b949e;font-size:13px;">🔁 {rts}</span>
    <span style="color:#8b949e;font-size:13px;">👁️ {views}</span>
    <a href="{url}" target="_blank" style="color:#58a6ff;font-size:13px;">🔗 عرض</a>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── الشريط الجانبي ───────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(f"""
<div style="text-align:center;padding:1rem 0;direction:rtl;">
  <h2 style="color:#58a6ff;margin:0;">🔍 محلل X</h2>
  <p style="color:#8b949e;font-size:12px;margin:0;">{VERSION}</p>
</div>
""", unsafe_allow_html=True)
        st.markdown("---")

        # مفتاح Gemini
        st.markdown('<p style="color:#8b949e;font-size:13px;text-align:right;">🤖 مفتاح Gemini API</p>', unsafe_allow_html=True)
        gemini_key = st.text_input("Gemini API Key", type="password", key="gemini_api_key",
                                    label_visibility="collapsed",
                                    placeholder="أدخل مفتاح Gemini API")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            st.success("✅ تم تفعيل Gemini")

        # مفتاح TwitterAPI.io
        st.markdown('<p style="color:#8b949e;font-size:13px;text-align:right;">🐦 مفتاح TwitterAPI.io (اختياري)</p>', unsafe_allow_html=True)
        twitter_key = st.text_input("TwitterAPI Key", type="password", key="twitter_api_key",
                                     label_visibility="collapsed",
                                     placeholder="لجلب آخر 500 تغريدة")

        # اختيار النموذج
        st.markdown('<p style="color:#8b949e;font-size:13px;text-align:right;">🧠 نموذج الذكاء الاصطناعي</p>', unsafe_allow_html=True)
        model_name = st.selectbox("النموذج", list(GEMINI_MODELS.keys()), key="model_select",
                                   label_visibility="collapsed")
        st.session_state["model_id"] = GEMINI_MODELS[model_name]

        st.markdown("---")
        st.markdown("""
<div style="direction:rtl;text-align:right;font-size:12px;color:#8b949e;">
<b style="color:#58a6ff;">📡 مصادر البيانات:</b><br>
✅ FxTwitter API (نشط)<br>
✅ TwitterAPI.io (اختياري)<br><br>
<b style="color:#58a6ff;">📖 طريقة الاستخدام:</b><br>
1. أدخل مفتاح Gemini<br>
2. أدخل رابط حساب أو تغريدة<br>
3. اضغط تحليل<br>
4. صدّر التقرير
</div>
""", unsafe_allow_html=True)

        return twitter_key

# ─── تبويب تحليل الحساب ───────────────────────────────────────
def account_tab(twitter_api_key: str):
    st.markdown('<h3 style="color:#58a6ff;text-align:right;">👤 تحليل حساب X</h3>', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        account_input = st.text_input(
            "رابط الحساب أو اسم المستخدم",
            placeholder="مثال: https://x.com/username أو @username",
            key="account_input", label_visibility="visible"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 جلب البيانات", key="fetch_account", use_container_width=True)

    if fetch_btn and account_input:
        user = None
        tweet = None

        # محاولة استخراج معرف التغريدة
        tid = extract_tweet_id(account_input)
        if tid:
            with st.spinner("جاري جلب التغريدة..."):
                tweet = fetch_fxtwitter_tweet(tid)
            if tweet and tweet.get("author"):
                uname = tweet["author"].get("screen_name","")
                if uname:
                    with st.spinner(f"جاري جلب بيانات @{uname}..."):
                        user = fetch_fxtwitter_user(uname)

        if not user:
            uname = extract_username(account_input)
            if uname:
                with st.spinner(f"جاري جلب بيانات @{uname}..."):
                    user = fetch_fxtwitter_user(uname)

        if user:
            st.session_state["account_user"]  = user
            st.session_state["account_tweet"] = tweet
            st.success(f"✅ تم جلب بيانات @{user.get('screen_name','')}")
        else:
            st.error("❌ تعذّر جلب البيانات. تأكد من صحة الرابط أو اسم المستخدم.")

    user  = st.session_state.get("account_user")
    tweet = st.session_state.get("account_tweet")

    if user:
        render_user_card(user)

        # ─── جلب التغريدات للتحليل ───────────────────────────
        st.markdown("---")
        st.markdown('<h4 style="color:#58a6ff;text-align:right;">🔍 التحليل الاستخباراتي الشامل للمنشورات</h4>', unsafe_allow_html=True)

        col_a, col_b = st.columns([1,1])
        with col_b:
            if twitter_api_key:
                if st.button("📥 جلب آخر 500 منشور تلقائياً", key="fetch_tweets", use_container_width=True):
                    with st.spinner("جاري جلب المنشورات... قد يستغرق هذا دقيقة"):
                        tweets = fetch_user_tweets_twitterapi(
                            user.get("screen_name",""), twitter_api_key, 500
                        )
