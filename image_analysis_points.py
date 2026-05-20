# ============================================================
# محلل حسابات X الاستخباراتي - v10.3.5
# إصلاح: الشاشة السوداء عبر config.toml + CSS مبسّط للـ RTL فقط
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
    from pptx.util import Inches as PInches, Pt as PPt
    from pptx.dml.color import RGBColor as PRGBColor
    from pptx.enum.text import PP_ALIGN
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

try:
    import google.generativeai as genai
    GENAI_OK = True
except ImportError:
    GENAI_OK = False

# ─── ثوابت ───────────────────────────────────────────────────
VERSION         = "v10.3.5"
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
    "📍 تحليل الموقع الجغرافي":  "حدد الموقع الجغرافي والمعالم والدولة والمدينة المحتملة.",
    "👥 تحليل الأشخاص":          "صف الأشخاص في الصورة: الجنس، العمر، الملابس، الهوية.",
    "🚗 تحليل المركبات":          "حدد أي مركبات مع نوعها ولونها وأي معلومات مميزة.",
    "📄 تحليل المستندات":         "استخرج أي نصوص أو معلومات من مستندات أو لافتات.",
    "⚠️ تحليل التهديدات":         "حدد أي محتوى مثير للقلق أو تهديدات أو محتوى عنيف.",
    "🏛️ تحليل البنية التحتية":    "صف أي مبانٍ أو منشآت أو بنية تحتية مرئية.",
    "🕐 تحليل التوقيت":           "قدّر الوقت من الإضاءة والظلال.",
    "🎭 تحليل الأحداث":           "صف أي حدث أو اجتماع أو نشاط يجري.",
    "🔍 كشف التزوير":             "قيّم مدى أصالة الصورة وابحث عن علامات التلاعب.",
    "📊 تحليل شامل":              "قدم تحليلاً شاملاً من منظور استخباراتي.",
}

# ─── CSS للـ RTL فقط (بدون ألوان - الألوان من config.toml) ──
RTL_CSS = """
<style>
/* RTL فقط */
.stApp, html, body {
    direction: rtl !important;
}
.main .block-container {
    direction: rtl !important;
    max-width: 1100px !important;
}
p, span, div, h1, h2, h3, h4, h5, h6,
.stMarkdown, [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p {
    direction: rtl !important;
    text-align: right !important;
}
[data-testid="stSidebar"] * {
    direction: rtl !important;
    text-align: right !important;
}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    direction: rtl !important;
    text-align: right !important;
}
.stTextInput label, .stTextArea label,
.stSelectbox label,
label[data-testid="stWidgetLabel"] {
    direction: rtl !important;
    text-align: right !important;
    display: block !important;
    width: 100% !important;
}
.stAlert, .stSuccess, .stError,
.stWarning, .stInfo,
[data-testid="stAlert"] {
    direction: rtl !important;
    text-align: right !important;
}
.stAlert p, .stSuccess p, .stError p,
.stWarning p, .stInfo p {
    direction: rtl !important;
    text-align: right !important;
}
.stTabs [data-baseweb="tab-list"] {
    direction: rtl !important;
}
.stButton > button {
    width: 100% !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}
.streamlit-expanderHeader {
    direction: rtl !important;
    text-align: right !important;
}

/* بطاقات مخصصة */
.intel-card {
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.8rem 0;
    direction: rtl;
    text-align: right;
    background: rgba(255,255,255,0.03);
}

/* شريط تمرير */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { border-radius: 3px; }
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
    for pat in [r'(?:twitter\.com|x\.com)/([^/?#\s]+)',
                r'^([A-Za-z0-9_]{1,50})$']:
        m = re.search(pat, text)
        if m:
            u = m.group(1)
            if u.lower() not in ('home','explore','notifications',
                                  'messages','i','settings'):
                return u
    return None

def image_to_base64(img: Image.Image, fmt="JPEG") -> str:
    buf = io.BytesIO()
    rgb = img.convert("RGB") if fmt == "JPEG" else img
    rgb.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

def base64_to_bytesio(b64: str) -> io.BytesIO:
    return io.BytesIO(base64.b64decode(b64))

def download_image_b64(url: str):
    try:
        h = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            return image_to_base64(img)
    except: pass
    return None

def calc_image_size_word(b64, max_w=15.0, max_h=12.0):
    try:
        img = Image.open(base64_to_bytesio(b64))
        w, h = img.size
        ratio = w / h
        nw = min(max_w, max_h * ratio)
        nh = nw / ratio
        if nh > max_h: nh = max_h; nw = nh * ratio
        return Cm(nw), Cm(nh)
    except:
        return Cm(10), Cm(8)

def calc_image_size_pptx(b64, sw=9144000, sh=5143500, mg=457200):
    try:
        img = Image.open(base64_to_bytesio(b64))
        w, h = img.size
        sc = min((sw-mg*2)/w, (sh-mg*4)/h)
        return int(w*sc), int(h*sc)
    except:
        return int(sw*0.7), int(sh*0.6)

# ─── API calls ────────────────────────────────────────────────
def fetch_fxtwitter_tweet(tweet_id: str):
    try:
        r = requests.get(FXTWITTER_TWEET.format(tweet_id=tweet_id),
                         headers={"User-Agent": random.choice(USER_AGENTS)},
                         timeout=15)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == 200:
                return d.get("tweet") or d.get("status")
    except Exception as e:
        st.error(f"خطأ: {e}")
    return None

def fetch_fxtwitter_user(username: str):
    try:
        r = requests.get(FXTWITTER_USER.format(username=username),
                         headers={"User-Agent": random.choice(USER_AGENTS)},
                         timeout=15)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == 200:
                return d.get("user")
    except Exception as e:
        st.error(f"خطأ: {e}")
    return None

def fetch_user_tweets_twitterapi(username: str, api_key: str, limit=500):
    tweets, cursor = [], None
    headers = {"X-API-Key": api_key}
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
    return {cat: [k for k in kws if k.lower() in combined]
            for cat, kws in INTEL_KEYWORDS.items()
            if any(k.lower() in combined for k in kws)}

def get_threat_info(score: int):
    if score >= 8: return "🔴 خطر عالٍ جداً",  "#ff4444"
    if score >= 6: return "🟠 خطر عالٍ",        "#ff8800"
    if score >= 4: return "🟡 خطر متوسط",       "#ffcc00"
    if score >= 2: return "🟢 خطر منخفض",       "#44bb44"
    return "⚪ لا يوجد خطر",                     "#888888"

# ─── Gemini ───────────────────────────────────────────────────
def gemini_text(prompt: str, model_id: str) -> str:
    if not GENAI_OK:
        return "مكتبة google-generativeai غير مثبتة"
    try:
        m = genai.GenerativeModel(model_id)
        return m.generate_content(prompt).text
    except Exception as e:
        return f"خطأ في التحليل: {e}"

def gemini_with_images(prompt: str, images_b64: list, model_id: str) -> str:
    if not GENAI_OK:
        return "مكتبة google-generativeai غير مثبتة"
    try:
        m = genai.GenerativeModel(model_id)
        parts = [prompt] + [{"mime_type":"image/jpeg",
                              "data": base64.b64decode(b)} for b in images_b64]
        return m.generate_content(parts).text
    except Exception as e:
        return f"خطأ في تحليل الصورة: {e}"

def generate_intel_summary(user_data, tweets, keyword_hits, model_id) -> str:
    bio    = safe_text(user_data.get("description",""), "")
    name   = safe_text(user_data.get("name",""))
    sname  = safe_text(user_data.get("screen_name",""))
    loc    = safe_text(user_data.get("location",""), "")
    foll   = format_number(user_data.get("followers", 0))
    sample = "\n".join([
        (t.get("text","") if isinstance(t,dict) else str(t))
        for t in tweets[:100]
    ])
    kw_txt = "\n".join(f"- {c}: {', '.join(h)}"
                       for c, h in keyword_hits.items()) or "لا توجد"
    prompt = f"""أنت محلل استخباراتي متخصص. قدم تقريراً باللغة العربية عن:

**الحساب:** {name} (@{sname}) | الموقع: {loc} | المتابعون: {foll}
**السيرة:** {bio}

**الكلمات المفتاحية المكتشفة:**
{kw_txt}

**نماذج من التغريدات:**
{sample[:3000]}

**المطلوب (منسق بعناوين واضحة):**
1. مستوى التهديد (1-10 مع تبرير)
2. التصنيف (معادٍ للسعودية / متطرف / محرض / عادي)
3. أبرز الكلمات والمحتوى المثير للقلق
4. نمط السلوك والأسلوب
5. التوصيات الاستخباراتية"""
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

def export_to_word(user_data, tweets, intel_report,
                   exec_summary, images_data, text_analysis) -> bytes:
    if not DOCX_OK: return b""
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.5)

    def h(txt, lv=1):
        p = doc.add_heading(txt, level=lv)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_rtl_para(p)

    def para(txt, bold=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_rtl_para(p)
        run = p.add_run(txt)
        run.font.size = Pt(12)
        if bold: run.font.bold = True

    # غلاف
    tp = doc.add_paragraph()
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = tp.add_run("تقرير استخباراتي — محلل حسابات X")
    r.font.size = Pt(22); r.font.bold = True
    doc.add_paragraph(f"التاريخ: {datetime.now().strftime('%Y/%m/%d')} | {VERSION}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    if user_data:
        h("📋 بيانات الحساب", 1)
        for lbl, key in [("الاسم","name"),("المعرف","screen_name"),
                          ("الموقع","location"),("السيرة الذاتية","description"),
                          ("المتابعون","followers"),("يتابع","following"),
                          ("التغريدات","tweets"),("الإعجابات","likes")]:
            v = user_data.get(key,"")
            if v: para(f"{lbl}: {v if key not in ('followers','following','tweets','likes') else format_number(v)}")
        if user_data.get("created"):
            para(f"تاريخ الانضمام: {format_date(user_data['created'])}")

    if intel_report:
        doc.add_paragraph()
        h("🔍 التقرير الاستخباراتي", 1)
        for line in intel_report.split('\n'): para(line)

    if exec_summary:
        doc.add_paragraph()
        h("📊 الملخص التنفيذي", 1)
        for line in exec_summary.split('\n'): para(line)

    for i, img in enumerate(images_data or []):
        doc.add_page_break()
        h(f"🖼️ الصورة {i+1} — {img.get('label','')}", 2)
        if img.get("b64"):
            try:
                wc, hc = calc_image_size_word(img["b64"])
                doc.add_picture(base64_to_bytesio(img["b64"]), width=wc, height=hc)
            except: pass
        if img.get("analysis"):
            h("نتيجة التحليل:", 3)
            for line in img["analysis"].split('\n'): para(line)

    if text_analysis:
        doc.add_page_break()
        h("📝 تحليل النص", 1)
        for line in text_analysis.split('\n'): para(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

# ─── تصدير PowerPoint ─────────────────────────────────────────
def export_to_pptx(user_data, tweets, intel_report,
                   exec_summary, images_data, text_analysis) -> bytes:
    if not PPTX_OK: return b""

    prs = Presentation()
    prs.slide_width  = PInches(13.33)
    prs.slide_height = PInches(7.5)
    W = int(prs.slide_width)
    H = int(prs.slide_height)
    M = int(PInches(0.5))

    BG   = (13, 17, 23)
    CARD = (22, 27, 34)
    BLUE = (31, 111, 235)
    TEXT = (201, 209, 217)
    DIM  = (139, 148, 158)
    RED  = (248, 81, 73)

    def blank_slide():
        sl = prs.slides.add_slide(
            prs.slide_layouts[min(6, len(prs.slide_layouts)-1)])
        bg = sl.shapes.add_shape(1, 0, 0, W, H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = PRGBColor(*BG)
        bg.line.fill.background()
        return sl

    def title_bar(sl, title, subtitle=""):
        bar = sl.shapes.add_shape(1, 0, 0, W, int(PInches(1)))
        bar.fill.solid(); bar.fill.fore_color.rgb = PRGBColor(*BLUE)
        bar.line.fill.background()
        tb = sl.shapes.add_textbox(M, int(PInches(0.1)), W-2*M, int(PInches(0.8)))
        tf = tb.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
        run = p.add_run(); run.text = title
        run.font.size = PPt(26); run.font.bold = True
        run.font.color.rgb = PRGBColor(255,255,255)
        try: p._p.get_or_add_pPr().set('rtl','1')
        except: pass
        if subtitle:
            tb2 = sl.shapes.add_textbox(M, int(PInches(1.05)), W-2*M, int(PInches(0.4)))
            tf2 = tb2.text_frame
            p2 = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.RIGHT
            r2 = p2.add_run(); r2.text = subtitle
            r2.font.size = PPt(13); r2.font.color.rgb = PRGBColor(*DIM)
            try: p2._p.get_or_add_pPr().set('rtl','1')
            except: pass

    def add_text_box(sl, txt, l, t, w, h, fs=13,
                     bold=False, color=TEXT, center=False):
        tb = sl.shapes.add_textbox(l, t, w, h)
        tf = tb.text_frame; tf.word_wrap = True
        align = PP_ALIGN.CENTER if center else PP_ALIGN.RIGHT
        for i, line in enumerate(str(txt).split('\n')[:40]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            run = p.add_run(); run.text = line
            run.font.size = PPt(fs); run.font.bold = bold
            run.font.color.rgb = PRGBColor(*color)
            try: p._p.get_or_add_pPr().set('rtl','1')
            except: pass

    # شريحة 1: غلاف
    s1 = blank_slide()
    cx = int(PInches(1.5)); cy = int(PInches(1.5))
    cw = int(PInches(10.3)); ch = int(PInches(4.5))
    card = s1.shapes.add_shape(1, cx, cy, cw, ch)
    card.fill.solid(); card.fill.fore_color.rgb = PRGBColor(*CARD)
    card.line.color.rgb = PRGBColor(*BLUE); card.line.width = int(PPt(1.5))
    add_text_box(s1, "🔍 تقرير استخباراتي",
                 cx+M, cy+int(PInches(0.4)), cw-2*M, int(PInches(1.2)),
                 fs=32, bold=True, color=(255,255,255), center=True)
    add_text_box(s1, "محلل حسابات X الاستخباراتي",
                 cx+M, cy+int(PInches(1.6)), cw-2*M, int(PInches(0.7)),
                 fs=18, color=DIM, center=True)
    add_text_box(s1, f"التاريخ: {datetime.now().strftime('%Y/%m/%d')}  |  {VERSION}",
                 cx+M, cy+int(PInches(2.3)), cw-2*M, int(PInches(0.5)),
                 fs=13, color=DIM, center=True)
    # شارة سري
    badge = s1.shapes.add_shape(1,
                                  int(PInches(5.7)), cy+int(PInches(3.3)),
                                  int(PInches(1.9)), int(PInches(0.5)))
    badge.fill.solid(); badge.fill.fore_color.rgb = PRGBColor(*RED)
    badge.line.fill.background()
    add_text_box(s1, "🔒 سري للغاية",
                 int(PInches(5.7)), cy+int(PInches(3.3)),
                 int(PInches(1.9)), int(PInches(0.5)),
                 fs=12, bold=True, color=(255,255,255), center=True)

    # شريحة 2: ملف الحساب
    s2 = blank_slide()
    uname = f"@{safe_text(user_data.get('screen_name',''))}" if user_data else ""
    title_bar(s2, "📋 ملف الحساب", uname)
    if user_data:
        stats = [
            ("👥 المتابعون", format_number(user_data.get("followers",0))),
            ("➡️ يتابع",     format_number(user_data.get("following",0))),
            ("📝 التغريدات", format_number(user_data.get("tweets",0))),
            ("❤️ الإعجابات", format_number(user_data.get("likes",0))),
        ]
        bw = int(PInches(2.8)); bh = int(PInches(1.1)); gap = int(PInches(0.2))
        for i,(lbl,val) in enumerate(stats):
            bx = int(PInches(0.5)) + i*(bw+gap)
            by = int(PInches(1.7))
            bx_s = s2.shapes.add_shape(1, bx, by, bw, bh)
            bx_s.fill.solid(); bx_s.fill.fore_color.rgb = PRGBColor(*CARD)
            bx_s.line.color.rgb = PRGBColor(*BLUE); bx_s.line.width = int(PPt(1))
            add_text_box(s2, val, bx+int(PPt(5)), by+int(PPt(5)),
                         bw-int(PPt(10)), int(PInches(0.55)),
                         fs=22, bold=True, color=(88,166,255), center=True)
            add_text_box(s2, lbl, bx+int(PPt(5)), by+int(PInches(0.6)),
                         bw-int(PPt(10)), int(PInches(0.4)),
                         fs=11, color=DIM, center=True)

        bio  = safe_text(user_data.get("description",""), "")
        loc  = safe_text(user_data.get("location",""),    "")
        jnd  = format_date(safe_text(user_data.get("created","")))
        info = f"السيرة الذاتية:\n{bio}\n\nالموقع: {loc}  |  الانضمام: {jnd}"
        add_text_box(s2, info, M, int(PInches(3.0)), W-2*M, int(PInches(2.0)),
                     fs=12, color=TEXT)

    # شريحة 3+: التقرير الاستخباراتي
    if intel_report:
        for ci, chunk in enumerate([intel_report[i:i+700]
                                    for i in range(0, len(intel_report), 700)][:5]):
            s = blank_slide()
            title_bar(s, "🔍 التقرير الاستخباراتي",
                      f"جزء {ci+1}" if ci > 0 else "")
            add_text_box(s, chunk, M, int(PInches(1.3)), W-2*M, int(PInches(5.7)),
                         fs=13, color=TEXT)

    # شرائح الملخص التنفيذي
    if exec_summary:
        for ci, chunk in enumerate([exec_summary[i:i+700]
                                    for i in range(0, len(exec_summary), 700)][:4]):
            s = blank_slide()
            title_bar(s, "📊 الملخص التنفيذي",
                      f"جزء {ci+1}" if ci > 0 else "")
            add_text_box(s, chunk, M, int(PInches(1.3)), W-2*M, int(PInches(5.7)),
                         fs=13, color=TEXT)

    # شرائح الصور
    for i, img in enumerate(images_data or []):
        s = blank_slide()
        title_bar(s, f"🖼️ الصورة {i+1}", img.get('label',''))
        if img.get("b64"):
            try:
                iw, ih = calc_image_size_pptx(img["b64"], W, H)
                s.shapes.add_picture(base64_to_bytesio(img["b64"]),
                                     (W-iw)//2, int(PInches(1.3)), iw, ih)
            except: pass
        if img.get("analysis"):
            s2_ = blank_slide()
            title_bar(s2_, f"📝 تحليل الصورة {i+1}")
            add_text_box(s2_, img["analysis"][:700],
                         M, int(PInches(1.3)), W-2*M, int(PInches(5.7)),
                         fs=12, color=TEXT)

    # شريحة تحليل النص
    if text_analysis:
        s = blank_slide()
        title_bar(s, "📝 تحليل النص")
        add_text_box(s, text_analysis[:700],
                     M, int(PInches(1.3)), W-2*M, int(PInches(5.7)),
                     fs=13, color=TEXT)

    # شريحة الخاتمة
    s_end = blank_slide()
    add_text_box(s_end, "🔒 نهاية التقرير الاستخباراتي",
                 M, int(PInches(2.8)), W-2*M, int(PInches(1.2)),
                 fs=28, bold=True, color=(255,255,255), center=True)
    add_text_box(s_end, f"محلل حسابات X  |  {VERSION}",
                 M, int(PInches(4.2)), W-2*M, int(PInches(0.7)),
                 fs=14, color=DIM, center=True)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

# ─── أزرار التصدير ────────────────────────────────────────────
def render_export_buttons(user_data, tweets, intel_report,
                          exec_summary, images_data, text_analysis):
    st.markdown("---")
    st.markdown("### 📤 تصدير التقرير")
    c1, c2, c3 = st.columns(3)
    uname = safe_text((user_data or {}).get("screen_name","report"), "report")
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    with c1:
        if DOCX_OK:
            data = export_to_word(user_data or {}, tweets or [], intel_report or "",
                                   exec_summary or "", images_data or [],
                                   text_analysis or "")
            if data:
                st.download_button("📄 تنزيل Word", data=data,
                                   file_name=f"Intel_{uname}_{ts}.docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   use_container_width=True)
        else:
            st.info("python-docx غير مثبت")
    with c2:
        if PPTX_OK:
            data = export_to_pptx(user_data or {}, tweets or [], intel_report or "",
                                   exec_summary or "", images_data or [],
                                   text_analysis or "")
            if data:
                st.download_button("📊 تنزيل PowerPoint", data=data,
                                   file_name=f"Intel_{uname}_{ts}.pptx",
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                   use_container_width=True)
        else:
            st.info("python-pptx غير مثبت")
    with c3:
        ud = user_data or {}
        lines = ["=== بيانات الحساب ==="]
        for k in ("name","screen_name","description","location"):
            if ud.get(k): lines.append(f"{k}: {ud[k]}")
        if intel_report:  lines += ["","=== التقرير الاستخباراتي ===", intel_report]
        if exec_summary:  lines += ["","=== الملخص التنفيذي ===",      exec_summary]
        if text_analysis: lines += ["","=== تحليل النص ===",            text_analysis]
        st.download_button("📝 تنزيل TXT",
                           data="\n".join(lines).encode("utf-8"),
                           file_name=f"Intel_{uname}_{ts}.txt",
                           mime="text/plain", use_container_width=True)

# ─── بطاقة الحساب ─────────────────────────────────────────────
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
    ver    = " ✅" if user.get("blue_verified") else ""
    banner = user.get("banner_url","")
    avatar = (user.get("avatar_url","") or "").replace("_normal","_400x400")

    st.markdown(f"""
<div class="intel-card" style="padding:0;overflow:hidden;">
  {'<img src="'+banner+'" style="width:100%;height:130px;object-fit:cover;border-radius:10px 10px 0 0;">' if banner else ''}
  <div style="padding:1rem;direction:rtl;text-align:right;">
    {'<img src="'+avatar+'" style="width:80px;height:80px;border-radius:50%;border:3px solid #1f6feb;margin-top:-40px;display:block;margin-right:auto;">' if avatar else ''}
    <h2 style="color:#58a6ff;margin:0.5rem 0 0;">{name}{ver}</h2>
    <p style="color:#8b949e;margin:0 0 0.5rem;">@{sname}</p>
    {'<p>'+bio+'</p>' if bio else ""}
    {'<p style="font-size:13px;">📍 '+loc+'</p>' if loc else ""}
    <p style="font-size:13px;">📅 انضم: {joined}</p>
    <div style="display:flex;gap:1.5rem;justify-content:flex-end;flex-wrap:wrap;margin-top:1rem;padding-top:0.8rem;border-top:1px solid rgba(255,255,255,0.1);">
      <span><b style="color:#58a6ff;">{foll}</b> متابع</span>
      <span><b style="color:#58a6ff;">{fing}</b> يتابع</span>
      <span><b style="color:#58a6ff;">{twts}</b> تغريدة</span>
      <span><b style="color:#58a6ff;">{likes}</b> إعجاب</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── بطاقة التغريدة ───────────────────────────────────────────
def render_tweet_card(tweet: dict):
    if not tweet: return
    text   = safe_text(tweet.get("text",""), "")
    date   = format_date(safe_text(tweet.get("created_at","")))
    likes  = format_number(tweet.get("likes",0))
    rts    = format_number(tweet.get("retweets",0))
    views  = format_number(tweet.get("views",0))
    url    = safe_text(tweet.get("url",""), "#")
    author = tweet.get("author",{}) or {}
    aname  = safe_text(author.get("name",""))
    sname  = safe_text(author.get("screen_name",""))

    st.markdown(f"""
<div class="intel-card">
  <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
    <span style="font-size:13px;">📅 {date}</span>
    <b style="color:#58a6ff;">{aname} (@{sname})</b>
  </div>
  <p style="line-height:1.8;font-size:15px;">{text}</p>
  <div style="display:flex;gap:1.5rem;justify-content:flex-end;margin-top:0.8rem;">
    <span style="font-size:13px;">❤️ {likes}</span>
    <span style="font-size:13px;">🔁 {rts}</span>
    <span style="font-size:13px;">👁️ {views}</span>
    <a href="{url}" target="_blank" style="color:#58a6ff;font-size:13px;">🔗 عرض</a>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── الشريط الجانبي ───────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(f"## 🔍 محلل X\n`{VERSION}`")
        st.divider()

        gemini_key = st.text_input(
            "🤖 مفتاح Gemini API", type="password",
            key="gemini_api_key", placeholder="AIza...")
        if gemini_key and GENAI_OK:
            genai.configure(api_key=gemini_key)
            st.success("✅ Gemini مفعّل")

        twitter_key = st.text_input(
            "🐦 مفتاح TwitterAPI.io (اختياري)", type="password",
            key="twitter_api_key", placeholder="لجلب آخر 500 تغريدة")

        model_name = st.selectbox(
            "🧠 النموذج", list(GEMINI_MODELS.keys()), key="model_select")
        st.session_state["model_id"] = GEMINI_MODELS[model_name]

        st.divider()
        st.markdown("""
**📡 مصادر البيانات:**
- ✅ FxTwitter API
- ✅ TwitterAPI.io

**📖 الاستخدام:**
1. أدخل مفتاح Gemini
2. أدخل رابط حساب أو تغريدة
3. اضغط تحليل
4. صدّر التقرير
""")
    return twitter_key

# ─── تبويب تحليل الحساب ───────────────────────────────────────
def account_tab(twitter_api_key: str):
    st.markdown("## 👤 تحليل حساب X")

    col1, col2 = st.columns([4, 1])
    with col1:
        inp = st.text_input(
            "رابط الحساب أو اسم المستخدم",
            placeholder="https://x.com/username  أو  @username",
            key="account_input")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        go = st.button("🔍 جلب", key="fetch_account", use_container_width=True)

    if go and inp:
        with st.spinner("جاري الجلب..."):
            user, tweet = None, None
            tid = extract_tweet_id(inp)
            if tid:
                tweet = fetch_fxtwitter_tweet(tid)
                if tweet and tweet.get("author"):
                    un = tweet["author"].get("screen_name","")
                    if un: user = fetch_fxtwitter_user(un)
            if not user:
                un = extract_username(inp)
                if un: user = fetch_fxtwitter_user(un)
        if user:
            st.session_state["account_user"]  = user
            st.session_state["account_tweet"] = tweet
            st.success(f"✅ تم جلب @{user.get('screen_name','')}")
        else:
            st.error("❌ تعذّر الجلب. تحقق من الرابط أو اسم المستخدم.")

    user  = st.session_state.get("account_user")
    tweet = st.session_state.get("account_tweet")

    if not user:
        st.info("📌 أدخل رابط حساب X أو اسم المستخدم للبدء")
        return

    render_user_card(user)

    # ─── قسم التحليل الاستخباراتي ──────────────────────────
    st.markdown("---")
    st.markdown("## 🔍 التحليل الاستخباراتي الشامل")

    # جلب التغريدات
    tweets_list = st.session_state.get("fetched_tweets", [])

    col_a, col_b = st.columns(2)
    with col_b:
        if twitter_api_key:
            if st.button("📥 جلب آخر 500 منشور", key="fetch_tweets",
                         use_container_width=True):
                with st.spinner("جاري الجلب... قد يستغرق دقيقة"):
                    tweets_list = fetch_user_tweets_twitterapi(
                        user.get("screen_name",""), twitter_api_key, 500)
                    st.session_state["fetched_tweets"] = tweets_list
                st.success(f"✅ تم جلب {len(tweets_list)} منشور")
        else:
            st.warning("أدخل مفتاح TwitterAPI.io للجلب التلقائي")

    with col_a:
        manual_tweets = st.text_area(
            "📋 أو الصق نص التغريدات يدوياً",
            height=150, key="manual_tweets",
            placeholder="الصق هنا نصوص التغريدات...")

    # تجميع النصوص
    all_texts = []
    if tweets_list:
        all_texts += [t.get("text","") if isinstance(t,dict) else str(t)
                      for t in tweets_list]
    if manual_tweets.strip():
        all_texts += manual_tweets.strip().split('\n')

    if all_texts:
        st.info(f"📊 إجمالي النصوص المتاحة للتحليل: **{len(all_texts)}**")

        # فحص الكلمات المفتاحية
        kw_hits = scan_keywords(all_texts)
        if kw_hits:
            st.markdown("### ⚠️ الكلمات المفتاحية المكتشفة")
            for cat, hits in kw_hits.items():
                st.error(f"**{cat}:** {' | '.join(hits)}")
        else:
            st.success("✅ لم تُكتشف كلمات مفتاحية مثيرة للقلق")

        model_id = st.session_state.get("model_id", "gemini-2.5-flash-preview-05-20")
        gemini_key = st.session_state.get("gemini_api_key","")

        if st.button("🧠 بدء التحليل الاستخباراتي الشامل",
                     key="run_intel", use_container_width=True):
            if not gemini_key:
                st.error("❌ أدخل مفتاح Gemini API أولاً")
            else:
                with st.spinner("جاري التحليل الاستخباراتي..."):
                    report = generate_intel_summary(user, all_texts,
                                                    kw_hits, model_id)
                st.session_state["intel_report"] = report
                st.success("✅ اكتمل التحليل")

    intel_report = st.session_state.get("intel_report","")
    if intel_report:
        st.markdown("### 📋 التقرير الاستخباراتي")
        st.markdown(intel_report)

    # ─── تحليل الصور ──────────────────────────────────────
    st.markdown("---")
    st.markdown("## 🖼️ تحليل الصور")

    gemini_key = st.session_state.get("gemini_api_key","")
    model_id   = st.session_state.get("model_id", "gemini-2.5-flash-preview-05-20")

    # صورة الملف الشخصي
    avatar_url = (user.get("avatar_url","") or "").replace("_normal","_400x400")
    if avatar_url:
        with st.expander("🖼️ تحليل صورة الملف الشخصي"):
            analysis_type = st.selectbox(
                "نوع التحليل", list(IMAGE_ANALYSIS_POINTS.keys()),
                key="avatar_analysis_type")
            if st.button("🔍 تحليل الصورة", key="analyze_avatar",
                         use_container_width=True):
                if not gemini_key:
                    st.error("❌ أدخل مفتاح Gemini API")
                else:
                    with st.spinner("جاري التحليل..."):
                        b64 = download_image_b64(avatar_url)
                        if b64:
                            result = gemini_with_images(
                                IMAGE_ANALYSIS_POINTS[analysis_type],
                                [b64], model_id)
                            if "images_data" not in st.session_state:
                                st.session_state["images_data"] = []
                            st.session_state["images_data"].append({
                                "label": "صورة الملف الشخصي",
                                "b64": b64,
                                "analysis": result
                            })
                            st.success("✅ اكتمل التحليل")
                            st.markdown(result)
                        else:
                            st.error("تعذّر تنزيل الصورة")

    # رفع صور إضافية
    with st.expander("📤 رفع صور للتحليل"):
        uploaded = st.file_uploader(
            "اختر الصور", type=["jpg","jpeg","png","webp"],
            accept_multiple_files=True, key="uploaded_images")
        if uploaded:
            analysis_type2 = st.selectbox(
                "نوع التحليل", list(IMAGE_ANALYSIS_POINTS.keys()),
                key="upload_analysis_type")
            if st.button("🔍 تحليل الصور المرفوعة",
                         key="analyze_uploaded", use_container_width=True):
                if not gemini_key:
                    st.error("❌ أدخل مفتاح Gemini API")
                else:
                    if "images_data" not in st.session_state:
                        st.session_state["images_data"] = []
                    for f in uploaded:
                        with st.spinner(f"تحليل {f.name}..."):
                            img = Image.open(f)
                            b64 = image_to_base64(img)
                            result = gemini_with_images(
                                IMAGE_ANALYSIS_POINTS[analysis_type2],
                                [b64], model_id)
                            st.session_state["images_data"].append({
                                "label": f.name, "b64": b64, "analysis": result})
                            st.markdown(f"**{f.name}:**")
                            st.markdown(result)

    # أزرار التصدير
    render_export_buttons(
        user, tweets_list,
        st.session_state.get("intel_report",""),
        st.session_state.get("exec_summary",""),
        st.session_state.get("images_data",[]),
        st.session_state.get("text_analysis","")
    )

# ─── تبويب تحليل التغريدة ─────────────────────────────────────
def tweet_tab():
    st.markdown("## 🐦 تحليل تغريدة محددة")

    col1, col2 = st.columns([4,1])
    with col1:
        tweet_url = st.text_input(
            "رابط التغريدة",
            placeholder="https://x.com/user/status/123456789",
            key="tweet_input")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        go = st.button("🔍 جلب", key="fetch_tweet", use_container_width=True)

    if go and tweet_url:
        tid = extract_tweet_id(tweet_url)
        if not tid:
            st.error("❌ لم يُعثر على معرّف التغريدة في الرابط")
            return
        with st.spinner("جاري جلب التغريدة..."):
            tweet = fetch_fxtwitter_tweet(tid)
        if tweet:
            st.session_state["current_tweet"] = tweet
            st.success("✅ تم جلب التغريدة")
        else:
            st.error("❌ تعذّر جلب التغريدة")

    tweet = st.session_state.get("current_tweet")
    if not tweet:
        st.info("📌 أدخل رابط تغريدة للبدء")
        return

    render_tweet_card(tweet)

    gemini_key = st.session_state.get("gemini_api_key","")
    model_id   = st.session_state.get("model_id","gemini-2.5-flash-preview-05-20")

    # الصور المضمّنة
    media = tweet.get("media",{}) or {}
    imgs  = media.get("photos",[]) or []
    vids  = media.get("videos",[]) or []

    if imgs or vids:
        st.markdown("### 🖼️ الوسائط المضمّنة")
        images_b64 = []
        for ph in imgs:
            url = ph.get("url","")
            if url:
                b64 = download_image_b64(url)
                if b64:
                    images_b64.append(b64)
                    img_obj = Image.open(base64_to_bytesio(b64))
                    st.image(img_obj, use_column_width=True)
        if images_b64:
            analysis_type = st.selectbox(
                "نوع التحليل", list(IMAGE_ANALYSIS_POINTS.keys()),
                key="tweet_img_analysis")
            if st.button("🔍 تحليل الصور", key="analyze_tweet_imgs",
                         use_container_width=True):
                if not gemini_key:
                    st.error("❌ أدخل مفتاح Gemini API")
                else:
                    with st.spinner("جاري التحليل..."):
                        result = gemini_with_images(
                            IMAGE_ANALYSIS_POINTS[analysis_type],
                            images_b64, model_id)
                        st.session_state["img_analysis_tweet"] = result
                    st.markdown(result)

    # تحليل النص
    st.markdown("---")
    st.markdown("### 📝 تحليل النص")
    custom_prompt = st.text_area(
        "سؤال أو توجيه مخصص (اختياري)",
        key="custom_prompt",
        placeholder="مثال: هل هذا النص يحتوي على تحريض؟")

    if st.button("🧠 تحليل التغريدة", key="analyze_tweet_text",
                 use_container_width=True):
        if not gemini_key:
            st.error("❌ أدخل مفتاح Gemini API")
        else:
            tweet_text = tweet.get("text","")
            prompt = custom_prompt if custom_prompt.strip() else (
                f"حلل هذه التغريدة من منظور استخباراتي وأمني:\n\n{tweet_text}")
            with st.spinner("جاري التحليل..."):
                result = gemini_text(prompt, model_id)
                st.session_state["text_analysis"] = result
            st.markdown(result)

    text_analysis = st.session_state.get("text_analysis","")

    # الملخص التنفيذي
    if text_analysis:
        if st.button("📊 توليد الملخص التنفيذي", key="gen_exec",
                     use_container_width=True):
            with st.spinner("جاري توليد الملخص..."):
                p = f"اكتب ملخصاً تنفيذياً موجزاً (فقرة واحدة) لهذا التحليل:\n{text_analysis}"
                summary = gemini_text(p, model_id)
                st.session_state["exec_summary"] = summary
            st.markdown(summary)

    # أزرار التصدير
    render_export_buttons(
        st.session_state.get("account_user"),
        [],
        st.session_state.get("intel_report",""),
        st.session_state.get("exec_summary",""),
        st.session_state.get("images_data",[]),
        text_analysis
    )

# ─── الدالة الرئيسية ──────────────────────────────────────────
def main():
    # يجب أن تكون أول استدعاء
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # CSS للـ RTL فقط (الألوان من config.toml)
    st.markdown(RTL_CSS, unsafe_allow_html=True)

    # تهيئة session state
    for key in ("account_user","account_tweet","current_tweet",
                "intel_report","exec_summary","text_analysis",
                "images_data","fetched_tweets","model_id"):
        if key not in st.session_state:
            st.session_state[key] = [] if key in ("images_data","fetched_tweets") else ""

    # الشريط الجانبي
    twitter_api_key = render_sidebar()

    # العنوان الرئيسي
    st.markdown(f"""
<div style="text-align:center;padding:1.5rem 0;direction:rtl;">
  <h1 style="margin:0;">🔍 {PAGE_TITLE}</h1>
  <p style="margin:0.3rem 0 0;">{VERSION} | مدعوم بـ FxTwitter + Gemini AI</p>
</div>
""", unsafe_allow_html=True)
    st.divider()

    # التبويبات
    tab1, tab2 = st.tabs(["👤 تحليل حساب", "🐦 تحليل تغريدة"])
    with tab1:
        account_tab(twitter_api_key)
    with tab2:
        tweet_tab()

if __name__ == "__main__":
    main()
