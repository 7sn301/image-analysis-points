# ============================================================
# محلل حسابات X الاستخباراتي - v10.3
# ============================================================
# التحديثات:
# - إزالة الاعتماد على Nitter (مات رسمياً 2024)
# - الاعتماد الكامل على FxTwitter API
# - تحليل الحساب عبر رابط تغريدة
# - إصلاح أسماء نماذج Gemini
# - الحفاظ على أبعاد الصور
# ============================================================

import streamlit as st
import requests
import base64
import io
import re
import random
import time
from datetime import datetime
from PIL import Image

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from pptx import Presentation
    from pptx.util import Inches as PInches, Pt as PPt, Emu as PEmu
    from pptx.dml.color import RGBColor as PRGBColor
    from pptx.enum.text import PP_ALIGN
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

# ─────────────────────────────────────────
# الثوابت
# ─────────────────────────────────────────
PAGE_TITLE = "محلل حسابات X الاستخباراتي"
PAGE_ICON  = "🔍"
VERSION    = "v10.3"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# FxTwitter API - المصدر الرئيسي الوحيد
FXTWITTER_API  = "https://api.fxtwitter.com/status/{tweet_id}"
FXTWITTER_USER = "https://api.fxtwitter.com/{username}"

GEMINI_MODELS = {
    "Gemini 2.5 Flash (موصى به)":    "gemini-2.5-flash",
    "Gemini 2.0 Flash Lite (اقتصادي)": "gemini-2.0-flash-lite",
    "Gemini 2.5 Pro (متقدم)":         "gemini-2.5-pro",
    "Gemini 1.5 Flash (احتياطي)":     "gemini-1.5-flash",
}

IMAGE_ANALYSIS_POINTS = {
    "📍 تحديد الموقع الجغرافي": (
        "حلل هذه الصورة لتحديد الموقع الجغرافي. ابحث عن: "
        "المعالم البارزة، اللافتات، الطرازات المعمارية، الغطاء النباتي، "
        "التضاريس، المركبات، ملابس السكان، أي نص أو لافتات مرئية. "
        "قدم احتمالات متعددة للمواقع مع مستويات ثقتك."
    ),
    "👤 تحليل الأشخاص والهويات": (
        "حلل الأشخاص الظاهرين في هذه الصورة. "
        "صف: السن التقريبي، الجنس، الملابس، الشعارات أو الرموز المرئية، "
        "لغة الجسد، العلاقات بين الأشخاص، أي معدات أو أدوات يحملونها. "
        "ركز على التفاصيل الاستخباراتية ذات الصلة."
    ),
    "🚗 تحليل المركبات والمعدات": (
        "حدد وحلل جميع المركبات والمعدات في الصورة. "
        "اذكر: النوع، الماركة إن أمكن، الحالة، أرقام اللوحات إن ظهرت، "
        "التحصينات أو التعديلات، الاستخدام المحتمل، "
        "أي معدات عسكرية أو أمنية."
    ),
    "📄 تحليل الوثائق والنصوص": (
        "اقرأ وحلل جميع النصوص والوثائق المرئية في الصورة. "
        "استخرج: النصوص المكتوبة، أرقام الوثائق، التواريخ، الأختام، "
        "الرموز الرسمية، أي معلومات تعريفية. "
        "حلل أهميتها الاستخباراتية."
    ),
    "⚔️ تحليل الأسلحة والتجهيزات": (
        "حلل أي أسلحة أو تجهيزات عسكرية أو أمنية في الصورة. "
        "صف: نوع السلاح، الطراز المحتمل، الحالة، طريقة الحمل، "
        "التكتيكات المرئية، مستوى التدريب الظاهر."
    ),
    "🏗️ تحليل البنية التحتية": (
        "حلل البنية التحتية والمنشآت المرئية. "
        "صف: نوع المبنى أو المنشأة، الحالة، الأهمية الاستراتيجية المحتملة، "
        "علامات الإنشاء أو الهدم، الاستخدام المحتمل، "
        "أي تعديلات أمنية مرئية."
    ),
    "⏰ تحليل التوقيت والزمن": (
        "حلل مؤشرات التوقيت في الصورة. ابحث عن: "
        "موضع الشمس وزاوية الضوء، الظلال، الطقس والموسم، "
        "الساعات أو التقويمات المرئية، مؤشرات الفترة الزمنية، "
        "علامات قِدَم الصورة أو حداثتها."
    ),
    "🔍 تحليل الأحداث والتجمعات": (
        "حلل أي حدث أو تجمع ظاهر في الصورة. "
        "صف: طبيعة الحدث، حجم الحشد المقدر، التنظيم، "
        "المزاج العام، الشعارات أو الرسائل، "
        "مستوى الأمن أو التنسيق الظاهر."
    ),
    "🔎 كشف التزوير والتلاعب": (
        "افحص هذه الصورة لكشف أي تلاعب أو تزوير. ابحث عن: "
        "عدم التناسق في الإضاءة، حواف غير طبيعية، تكرار البكسل، "
        "عناصر مضافة أو محذوفة، بيانات EXIF غير متسقة، "
        "علامات الذكاء الاصطناعي التوليدي. "
        "قدم تقييماً لمصداقية الصورة."
    ),
    "🧠 تحليل شامل ومتكامل": (
        "قم بتحليل استخباراتي شامل لهذه الصورة. "
        "اجمع جميع العناصر: الموقع، الأشخاص، المركبات، الأسلحة، "
        "البنية التحتية، التوقيت، والسياق العام. "
        "قدم تقييماً استخباراتياً متكاملاً مع توصيات للمتابعة."
    ),
}

# ─────────────────────────────────────────
# دوال مساعدة
# ─────────────────────────────────────────

def safe_text(val, default="غير متوفر"):
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def escape_html(text):
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def nl_to_br(text):
    return escape_html(text).replace("\n", "<br>")


def safe_html_lines(text, limit=40):
    lines = str(text).splitlines()[:limit]
    return "<br>".join(escape_html(ln) for ln in lines)


def extract_username(raw):
    raw = raw.strip().lstrip("@")
    for pattern in [
        r"(?:twitter\.com|x\.com)/([^/?#\s]+)",
        r"^([A-Za-z0-9_]{1,50})$",
    ]:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    return raw


def extract_tweet_id(raw):
    raw = raw.strip()
    m = re.search(r"/status(?:es)?/(\d+)", raw)
    if m:
        return m.group(1)
    if raw.isdigit():
        return raw
    return None


def format_number(n):
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return str(n)


def format_date(ts):
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)


def image_to_base64(img_obj):
    buf = io.BytesIO()
    fmt = getattr(img_obj, "format", None) or "PNG"
    if fmt.upper() == "JPEG":
        img_obj.save(buf, format="JPEG", quality=85)
    else:
        img_obj.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def base64_to_bytesio(b64_str):
    return io.BytesIO(base64.b64decode(b64_str))


def download_image_b64(url, timeout=15):
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        return image_to_base64(img)
    except Exception as e:
        st.warning(f"تعذّر تحميل الصورة: {e}")
        return None


# ─────────────────────────────────────────
# حساب أبعاد الصور (Word / PPTX)
# ─────────────────────────────────────────

def calc_image_size_word(b64_str, max_w_inch=5.5, max_h_inch=7.0):
    """احسب حجم الصورة للـ Word مع الحفاظ على النسبة."""
    try:
        bio = base64_to_bytesio(b64_str)
        img = Image.open(bio)
        w, h = img.size
        if w == 0 or h == 0:
            return {"width": Inches(4)}
        aspect = h / w
        if aspect * max_w_inch <= max_h_inch:
            return {"width": Inches(max_w_inch)}
        return {"height": Inches(max_h_inch)}
    except Exception:
        return {"width": Inches(4)}


def calc_image_size_pptx(b64_str, slide_w, slide_h,
                          max_w_ratio=0.78, max_h_ratio=0.62):
    """احسب أبعاد ومكان الصورة في PPTX مع التوسيط."""
    try:
        bio = base64_to_bytesio(b64_str)
        img = Image.open(bio)
        w, h = img.size
        if w == 0 or h == 0:
            return int(slide_w * 0.1), int(slide_h * 0.25), int(slide_w * 0.8), int(slide_h * 0.5)
        aspect = h / w
        max_w  = int(slide_w * max_w_ratio)
        max_h  = int(slide_h * max_h_ratio)
        if aspect * max_w <= max_h:
            pic_w = max_w
            pic_h = int(aspect * max_w)
        else:
            pic_h = max_h
            pic_w = int(max_h / aspect)
        left = int((slide_w - pic_w) / 2)
        top  = PEmu(1_050_000) + int((max_h - pic_h) / 2)
        return left, top, pic_w, pic_h
    except Exception:
        return int(slide_w * 0.1), int(slide_h * 0.25), int(slide_w * 0.8), int(slide_h * 0.5)


# ─────────────────────────────────────────
# جلب البيانات - FxTwitter API (الوحيد)
# ─────────────────────────────────────────

def fetch_fxtwitter(tweet_id: str) -> dict | None:
    """جلب بيانات التغريدة عبر FxTwitter API."""
    url = FXTWITTER_API.format(tweet_id=tweet_id)
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        if data.get("code") == 200 and "tweet" in data:
            return data["tweet"]
        return None
    except Exception as e:
        st.error(f"خطأ في FxTwitter API: {e}")
        return None


def fetch_account_fxtwitter(username: str, sample_tweet_id: str = None) -> dict | None:
    """
    جلب بيانات الحساب عبر FxTwitter.
    إذا كان sample_tweet_id متاحاً نستخدمه لجلب معلومات المؤلف.
    """
    if sample_tweet_id:
        tweet = fetch_fxtwitter(sample_tweet_id)
        if tweet and "author" in tweet:
            author = tweet["author"]
            return {
                "source": "fxtwitter",
                "username": author.get("screen_name", username),
                "name": author.get("name", username),
                "avatar_url": author.get("avatar_url"),
                "banner_url": author.get("banner_url"),
                "description": tweet.get("text", ""),
                "verified": author.get("verified", False),
                "sample_tweet": tweet,
            }
    return None


# ─────────────────────────────────────────
# نماذج Gemini
# ─────────────────────────────────────────

def _get_genai_model(api_key: str, model_name: str):
    if not GENAI_AVAILABLE:
        st.error("مكتبة google-generativeai غير مثبّتة.")
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"خطأ في تهيئة Gemini: {e}")
        return None


def gemini_text(prompt: str, api_key: str, model_name: str) -> str | None:
    model = _get_genai_model(api_key, model_name)
    if not model:
        return None
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        st.error(f"خطأ في توليد النص: {e}")
        return None


def gemini_with_images(prompt: str, images_b64: list,
                        api_key: str, model_name: str) -> str | None:
    model = _get_genai_model(api_key, model_name)
    if not model:
        return None
    try:
        parts = [prompt]
        for b64 in images_b64:
            raw = base64.b64decode(b64)
            img = Image.open(io.BytesIO(raw))
            fmt = (img.format or "PNG").lower()
            mime = "image/jpeg" if fmt in ("jpeg", "jpg") else "image/png"
            parts.append({"mime_type": mime, "data": b64})
        resp = model.generate_content(parts)
        return resp.text
    except Exception as e:
        st.error(f"خطأ في تحليل الصور: {e}")
        return None


# ─────────────────────────────────────────
# مساعدات Word RTL
# ─────────────────────────────────────────

def _set_rtl_para(para):
    """ضبط الفقرة على RTL في Word."""
    try:
        pPr = para._p.get_or_add_pPr()
        bidi = OxmlElement("w:bidi")
        bidi.set(qn("w:val"), "1")
        pPr.append(bidi)
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), "right")
        pPr.append(jc)
    except Exception:
        pass


def _add_word_section(doc, title: str, content: str,
                       title_color=None, level: int = 2):
    """إضافة قسم نصي في Word مع RTL."""
    h = doc.add_heading(title, level=level)
    _set_rtl_para(h)
    if title_color:
        for run in h.runs:
            run.font.color.rgb = RGBColor(*title_color)
    p = doc.add_paragraph(content)
    _set_rtl_para(p)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return p


# ─────────────────────────────────────────
# مساعدات PPTX RTL
# ─────────────────────────────────────────

def set_para_rtl_pptx(para):
    try:
        pPr = para._p.get_or_add_pPr()
        bidi = OxmlElement("a:rtl")
        bidi.text = "1"
        pPr.append(bidi)
    except Exception:
        pass


# ─────────────────────────────────────────
# دوال التصدير
# ─────────────────────────────────────────

def export_to_word(title: str, tweet_data: dict,
                   img_analysis: str, text_analysis: str,
                   exec_summary: str, images_b64: list) -> bytes | None:
    if not DOCX_AVAILABLE:
        st.error("مكتبة python-docx غير مثبّتة.")
        return None
    doc = Document()

    # إعداد الخط الافتراضي
    style = doc.styles["Normal"]
    font  = style.font
    font.name = "Arial"
    font.size = Pt(11)

    # العنوان الرئيسي
    h0 = doc.add_heading(f"تقرير استخباراتي – {title}", 0)
    _set_rtl_para(h0)
    for run in h0.runs:
        run.font.color.rgb = RGBColor(0xE9, 0x45, 0x60)

    doc.add_paragraph(f"التاريخ: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | الإصدار: {VERSION}")

    # ─── الملخص التنفيذي ───
    if exec_summary:
        h_es = doc.add_heading("📋 الملخص التنفيذي", 1)
        _set_rtl_para(h_es)
        for run in h_es.runs:
            run.font.color.rgb = RGBColor(0xE9, 0x45, 0x60)
            run.font.size = Pt(16)
        p_es = doc.add_paragraph(exec_summary)
        _set_rtl_para(p_es)
        p_es.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        doc.add_paragraph()

    # ─── بيانات التغريدة ───
    if tweet_data:
        _add_word_section(doc, "📌 بيانات التغريدة",
                          "\n".join(f"{k}: {v}" for k, v in tweet_data.items()),
                          title_color=(0x1D, 0xA1, 0xF2))

    # ─── تحليل الصور ───
    if images_b64:
        h_img = doc.add_heading("🖼️ الصور المرفقة وتحليلها", 1)
        _set_rtl_para(h_img)
        for b64 in images_b64:
            try:
                size_kw = calc_image_size_word(b64)
                doc.add_picture(base64_to_bytesio(b64), **size_kw)
                last = doc.paragraphs[-1]
                last.alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                doc.add_paragraph(f"[تعذّر إدراج الصورة: {e}]")
        if img_analysis:
            _add_word_section(doc, "نتائج تحليل الصور", img_analysis)

    # ─── تحليل النص ───
    if text_analysis:
        _add_word_section(doc, "📝 تحليل نص التغريدة", text_analysis,
                           title_color=(0x1D, 0xA1, 0xF2))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_to_pptx(title: str, tweet_data: dict,
                    img_analysis: str, text_analysis: str,
                    exec_summary: str, images_b64: list) -> bytes | None:
    if not PPTX_AVAILABLE:
        st.error("مكتبة python-pptx غير مثبّتة.")
        return None

    prs  = Presentation()
    sw   = prs.slide_width
    sh   = prs.slide_height
    DARK = PRGBColor(0x0D, 0x1B, 0x2A)
    RED  = PRGBColor(0xE9, 0x45, 0x60)
    BLUE = PRGBColor(0x1D, 0xA1, 0xF2)
    WHT  = PRGBColor(0xFF, 0xFF, 0xFF)

    def new_slide(layout_idx=6):
        layout = prs.slide_layouts[layout_idx]
        slide  = prs.slides.add_slide(layout)
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = DARK
        return slide

    def add_text_box(slide, text, x, y, w, h,
                      color=WHT, size=18, bold=False, align=PP_ALIGN.RIGHT):
        txb = slide.shapes.add_textbox(x, y, w, h)
        tf  = txb.text_frame
        tf.word_wrap = True
        p   = tf.paragraphs[0]
        p.alignment = align
        set_para_rtl_pptx(p)
        run = p.add_run()
        run.text = text
        run.font.color.rgb = color
        run.font.size = PPt(size)
        run.font.bold = bold
        return txb

    # ─── شريحة العنوان ───
    s0 = new_slide()
    add_text_box(s0, PAGE_TITLE, PInches(0.5), PInches(1), sw - PInches(1), PInches(1),
                 color=RED, size=32, bold=True, align=PP_ALIGN.CENTER)
    add_text_box(s0, title, PInches(0.5), PInches(2.2), sw - PInches(1), PInches(0.8),
                 color=WHT, size=22, align=PP_ALIGN.CENTER)
    add_text_box(s0, f"{datetime.utcnow().strftime('%Y-%m-%d')} | {VERSION}",
                 PInches(0.5), PInches(3.2), sw - PInches(1), PInches(0.5),
                 color=PRGBColor(0x88, 0x88, 0x88), size=14, align=PP_ALIGN.CENTER)

    # ─── شريحة الملخص التنفيذي ───
    if exec_summary:
        s_es = new_slide()
        add_text_box(s_es, "📋 الملخص التنفيذي", PInches(0.3), PInches(0.1),
                     sw - PInches(0.6), PInches(0.6),
                     color=RED, size=24, bold=True)
        # فاصل أحمر
        from pptx.util import Emu as _Emu
        line = s_es.shapes.add_shape(1, PInches(0.3), PInches(0.75),
                                      sw - PInches(0.6), _Emu(50000))
        line.fill.solid()
        line.fill.fore_color.rgb = RED
        line.line.fill.background()
        add_text_box(s_es, exec_summary[:700],
                     PInches(0.3), PInches(0.9),
                     sw - PInches(0.6), sh - PInches(1.2),
                     color=WHT, size=14)

    # ─── شريحة الصور ───
    for b64 in images_b64:
        si = new_slide()
        add_text_box(si, "🖼️ تحليل الصورة", PInches(0.3), PInches(0.05),
                     sw - PInches(0.6), PInches(0.4),
                     color=BLUE, size=20, bold=True)
        left, top, pw, ph = calc_image_size_pptx(b64, sw, sh)
        try:
            si.shapes.add_picture(base64_to_bytesio(b64), left, top, pw, ph)
        except Exception as e:
            add_text_box(si, f"[تعذّر الصورة: {e}]",
                         PInches(0.3), PInches(1), sw - PInches(0.6), PInches(1))

    # ─── شريحة تحليل النص ───
    if text_analysis:
        st_txt = new_slide()
        add_text_box(st_txt, "📝 تحليل النص", PInches(0.3), PInches(0.05),
                     sw - PInches(0.6), PInches(0.5),
                     color=BLUE, size=22, bold=True)
        add_text_box(st_txt, text_analysis[:700],
                     PInches(0.3), PInches(0.6),
                     sw - PInches(0.6), sh - PInches(0.9),
                     color=WHT, size=13)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────
# أزرار التصدير
# ─────────────────────────────────────────

def render_export_buttons(title: str):
    ss = st.session_state
    tweet_data   = ss.get("tweet_data",    {})
    img_analysis = ss.get("img_analysis",  "")
    text_analysis= ss.get("text_analysis", "")
    exec_summary = ss.get("exec_summary",  "")
    images_b64   = ss.get("images_b64",    [])

    if not any([tweet_data, img_analysis, text_analysis]):
        return

    st.divider()
    st.subheader("📥 تصدير التقرير")
    c1, c2, c3 = st.columns(3)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    safe  = re.sub(r"[^\w\u0600-\u06FF]", "_", title)[:30]

    with c1:
        docx = export_to_word(title, tweet_data, img_analysis,
                               text_analysis, exec_summary, images_b64)
        if docx:
            st.download_button("📄 Word", docx,
                                file_name=f"X_Report_{safe}_{stamp}.docx",
                                mime="application/vnd.openxmlformats-officedocument"
                                     ".wordprocessingml.document")

    with c2:
        pptx = export_to_pptx(title, tweet_data, img_analysis,
                                text_analysis, exec_summary, images_b64)
        if pptx:
            st.download_button("📊 PowerPoint", pptx,
                                file_name=f"X_Report_{safe}_{stamp}.pptx",
                                mime="application/vnd.openxmlformats-officedocument"
                                     ".presentationml.presentation")

    with c3:
        parts = []
        if tweet_data:
            parts.append("=== بيانات التغريدة ===\n" +
                          "\n".join(f"{k}: {v}" for k, v in tweet_data.items()))
        if exec_summary:
            parts.append(f"=== الملخص التنفيذي ===\n{exec_summary}")
        if img_analysis:
            parts.append(f"=== تحليل الصور ===\n{img_analysis}")
        if text_analysis:
            parts.append(f"=== تحليل النص ===\n{text_analysis}")
        txt = "\n\n".join(parts).encode("utf-8")
        st.download_button("📝 TXT", txt,
                            file_name=f"X_Report_{safe}_{stamp}.txt",
                            mime="text/plain")


# ─────────────────────────────────────────
# بطاقات العرض
# ─────────────────────────────────────────

def render_profile_card(data: dict):
    name     = escape_html(safe_text(data.get("name")))
    username = escape_html(safe_text(data.get("username")))
    desc     = nl_to_br(safe_text(data.get("description", "")))
    verified = "✅" if data.get("verified") else ""
    avatar   = data.get("avatar_url") or ""

    avatar_html = (f'<img src="{escape_html(avatar)}" '
                   f'style="width:80px;height:80px;border-radius:50%;'
                   f'border:3px solid #e94560;object-fit:cover;">'
                   if avatar else
                   '<div style="width:80px;height:80px;border-radius:50%;'
                   'background:#333;border:3px solid #e94560;"></div>')

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                border-radius:16px;padding:24px;
                border:1px solid #e94560;margin-bottom:20px;">
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
            {avatar_html}
            <div>
                <div style="font-size:1.4rem;font-weight:700;color:#fff;">
                    {name} {verified}
                </div>
                <div style="color:#1da1f2;font-size:1rem;">@{username}</div>
            </div>
        </div>
        <div style="color:#ccc;font-size:0.9rem;direction:rtl;">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def render_tweet_card(tweet: dict):
    author  = tweet.get("author", {})
    name    = escape_html(safe_text(author.get("name")))
    screen  = escape_html(safe_text(author.get("screen_name")))
    text    = nl_to_br(safe_text(tweet.get("text", "")))
    likes   = format_number(tweet.get("likes",    0))
    rts     = format_number(tweet.get("retweets", 0))
    replies = format_number(tweet.get("replies",  0))
    views   = format_number(tweet.get("views",    0))
    ts      = format_date(tweet.get("created_timestamp", 0))

    st.markdown(f"""
    <div style="background:#16213e;border-radius:12px;padding:20px;
                border:1px solid #1da1f2;margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;
                    align-items:center;margin-bottom:12px;">
            <div>
                <span style="color:#fff;font-weight:700;">{name}</span>
                <span style="color:#888;margin-right:8px;">@{screen}</span>
            </div>
            <span style="color:#888;font-size:0.85rem;">{ts}</span>
        </div>
        <div style="color:#e0e0e0;font-size:1rem;direction:rtl;
                    line-height:1.7;margin-bottom:16px;">{text}</div>
        <div style="display:flex;gap:24px;color:#888;font-size:0.9rem;">
            <span>❤️ {likes}</span>
            <span>🔁 {rts}</span>
            <span>💬 {replies}</span>
            <span>👁️ {views}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# تبويب تحليل الحساب
# ─────────────────────────────────────────

def account_tab(api_key: str, model_name: str):
    st.header("🔍 تحليل حساب X")

    # ── تحذير Nitter ──
    st.warning(
        "⚠️ **ملاحظة مهمة:** خدمة Nitter أُغلقت رسمياً منذ 2024. "
        "لتحليل الحساب، يُرجى إدخال **رابط أي تغريدة** للشخص المطلوب "
        "وسنستخرج بيانات الحساب منها تلقائياً.",
        icon="⚠️"
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        raw_input = st.text_input(
            "رابط تغريدة للحساب المطلوب تحليله",
            placeholder="https://x.com/username/status/1234567890",
            key="account_tweet_url"
        )
    with col2:
        uploaded_img = st.file_uploader(
            "صورة الملف الشخصي (اختياري)",
            type=["jpg", "png", "webp"],
            key="account_img"
        )

    if st.button("🔎 جلب بيانات الحساب", key="btn_fetch_account"):
        if not raw_input.strip():
            st.error("يرجى إدخال رابط التغريدة.")
            return

        tweet_id = extract_tweet_id(raw_input)
        if not tweet_id:
            st.error("❌ تعذّر استخراج معرّف التغريدة. تأكد من صحة الرابط.")
            return

        with st.spinner("⏳ جاري جلب البيانات عبر FxTwitter..."):
            tweet = fetch_fxtwitter(tweet_id)

        if not tweet:
            st.error("❌ تعذّر جلب بيانات التغريدة. تحقق من الرابط وأعد المحاولة.")
            return

        author = tweet.get("author", {})
        profile_data = {
            "source":      "FxTwitter API",
            "username":    author.get("screen_name", ""),
            "name":        author.get("name", ""),
            "avatar_url":  author.get("avatar_url"),
            "banner_url":  author.get("banner_url"),
            "description": tweet.get("text", ""),
            "verified":    author.get("verified", False),
        }
        st.session_state["account_profile"] = profile_data
        st.session_state["account_tweet"]   = tweet
        st.success("✅ تم جلب البيانات بنجاح!")

    # ─── عرض البيانات ───
    if "account_profile" in st.session_state:
        render_profile_card(st.session_state["account_profile"])
        tweet = st.session_state.get("account_tweet")
        if tweet:
            render_tweet_card(tweet)

    # ─── تحليل صورة الملف الشخصي ───
    st.divider()
    st.subheader("🖼️ تحليل صورة الملف الشخصي")

    images_b64: list[str] = []

    # صورة مُرفوعة
    if uploaded_img:
        img = Image.open(uploaded_img)
        b64 = image_to_base64(img)
        images_b64.append(b64)
        st.image(img, caption="الصورة المرفوعة", width=300)

    # صورة المستخدم من API
    profile = st.session_state.get("account_profile", {})
    if profile.get("avatar_url") and not uploaded_img:
        b64 = download_image_b64(profile["avatar_url"])
        if b64:
            images_b64.append(b64)
            bio = base64_to_bytesio(b64)
            st.image(bio, caption="صورة الملف الشخصي", width=150)

    if images_b64:
        point = st.selectbox(
            "نقطة تحليل الصورة",
            list(IMAGE_ANALYSIS_POINTS.keys()),
            key="account_img_point"
        )
        if st.button("🔍 تحليل الصورة", key="btn_account_img_analyze"):
            if not api_key:
                st.error("يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
                return
            prompt = IMAGE_ANALYSIS_POINTS[point]
            with st.spinner("🤖 جاري التحليل..."):
                result = gemini_with_images(prompt, images_b64, api_key, model_name)
            if result:
                st.session_state["img_analysis"] = result
                st.session_state["images_b64"]   = images_b64
                st.markdown(
                    f'<div style="background:#1a1a2e;border-radius:12px;'
                    f'padding:20px;border:1px solid #e94560;direction:rtl;">'
                    f'{nl_to_br(result)}</div>',
                    unsafe_allow_html=True
                )

    render_export_buttons(
        st.session_state.get("account_profile", {}).get("username", "account")
    )


# ─────────────────────────────────────────
# تبويب تحليل التغريدة
# ─────────────────────────────────────────

def tweet_tab(api_key: str, model_name: str):
    st.header("📌 تحليل تغريدة")

    col1, col2 = st.columns([3, 1])
    with col1:
        raw_url = st.text_input(
            "رابط التغريدة أو معرّفها",
            placeholder="https://x.com/user/status/123456 أو فقط الرقم",
            key="tweet_url_input"
        )
    with col2:
        uploaded_imgs = st.file_uploader(
            "صور التغريدة (اختياري)",
            type=["jpg", "png", "webp"],
            accept_multiple_files=True,
            key="tweet_imgs"
        )

    if st.button("🔎 جلب التغريدة", key="btn_fetch_tweet"):
        if not raw_url.strip():
            st.error("يرجى إدخال الرابط أو المعرّف.")
            return

        tweet_id = extract_tweet_id(raw_url) or (raw_url.strip() if raw_url.strip().isdigit() else None)
        if not tweet_id:
            st.error("❌ تعذّر استخراج معرّف التغريدة.")
            return

        with st.spinner("⏳ جاري جلب التغريدة..."):
            tweet = fetch_fxtwitter(tweet_id)

        if not tweet:
            st.error("❌ تعذّر جلب بيانات التغريدة.")
            return

        author = tweet.get("author", {})
        td = {
            "المعرّف":    tweet.get("id", ""),
            "النص":       tweet.get("text", ""),
            "المؤلف":     author.get("name", ""),
            "الحساب":     f"@{author.get('screen_name', '')}",
            "التاريخ":    format_date(tweet.get("created_timestamp", 0)),
            "الإعجابات":  format_number(tweet.get("likes",    0)),
            "إعادة نشر":  format_number(tweet.get("retweets", 0)),
            "الردود":     format_number(tweet.get("replies",  0)),
            "المشاهدات":  format_number(tweet.get("views",    0)),
            "اللغة":      tweet.get("lang", ""),
        }
        st.session_state["tweet_data"]   = td
        st.session_state["tweet_obj"]    = tweet
        st.session_state["text_analysis"] = ""
        st.session_state["exec_summary"]  = ""
        st.success("✅ تم جلب التغريدة بنجاح!")

    # ─── عرض التغريدة ───
    if "tweet_obj" in st.session_state:
        render_tweet_card(st.session_state["tweet_obj"])

        # صور من التغريدة
        tweet_obj = st.session_state["tweet_obj"]
        tweet_imgs_b64: list[str] = []

        media = tweet_obj.get("media", {})
        if isinstance(media, dict):
            for photo in media.get("photos", []):
                url = photo.get("url") or photo.get("thumbnail_url")
                if url:
                    b64 = download_image_b64(url)
                    if b64:
                        tweet_imgs_b64.append(b64)
                        st.image(base64_to_bytesio(b64),
                                 caption="صورة من التغريدة", width=400)

        # صور مرفوعة يدوياً
        for uf in (uploaded_imgs or []):
            img = Image.open(uf)
            b64 = image_to_base64(img)
            tweet_imgs_b64.append(b64)
            st.image(img, caption=f"صورة مرفوعة: {uf.name}", width=400)

        if tweet_imgs_b64:
            st.session_state["images_b64"] = tweet_imgs_b64

        # ─── تحليل الصورة ───
        if tweet_imgs_b64:
            st.divider()
            st.subheader("🖼️ تحليل الصورة")
            point = st.selectbox(
                "نقطة التحليل",
                list(IMAGE_ANALYSIS_POINTS.keys()),
                key="tweet_img_point"
            )
            if st.button("🔍 تحليل الصورة", key="btn_tweet_img"):
                if not api_key:
                    st.error("يرجى إدخال مفتاح Gemini API.")
                    return
                prompt = IMAGE_ANALYSIS_POINTS[point]
                with st.spinner("🤖 جاري تحليل الصورة..."):
                    result = gemini_with_images(
                        prompt, tweet_imgs_b64, api_key, model_name
                    )
                if result:
                    st.session_state["img_analysis"] = result
                    st.markdown(
                        f'<div style="background:#1a1a2e;border-radius:12px;'
                        f'padding:20px;border:1px solid #1da1f2;direction:rtl;">'
                        f'{nl_to_br(result)}</div>',
                        unsafe_allow_html=True
                    )

        # ─── تحليل النص ───
        st.divider()
        st.subheader("📝 تحليل نص التغريدة")
        tweet_text = st.session_state["tweet_data"].get("النص", "")
        if st.button("📝 تحليل النص", key="btn_text_analysis"):
            if not api_key:
                st.error("يرجى إدخال مفتاح Gemini API.")
                return
            if not tweet_text:
                st.error("النص فارغ.")
                return
            prompt = (
                "قم بتحليل استخباراتي شامل لهذه التغريدة:\n\n"
                f'"{tweet_text}"\n\n'
                "اشمل التحليل: المحتوى الرئيسي، النية، الخطاب، "
                "الكلمات المفتاحية، الخطورة المحتملة، مصداقية المعلومات."
            )
            with st.spinner("🤖 جاري التحليل..."):
                result = gemini_text(prompt, api_key, model_name)
            if result:
                st.session_state["text_analysis"] = result
                st.markdown(
                    f'<div style="background:#1a1a2e;border-radius:12px;'
                    f'padding:20px;border:1px solid #1da1f2;direction:rtl;">'
                    f'{nl_to_br(result)}</div>',
                    unsafe_allow_html=True
                )

        # ─── الملخص التنفيذي ───
        st.divider()
        st.subheader("🧠 الملخص التنفيذي")
        if st.button("🧠 توليد الملخص التنفيذي الشامل", key="btn_exec_summary"):
            if not api_key:
                st.error("يرجى إدخال مفتاح Gemini API.")
                return
            img_a  = st.session_state.get("img_analysis",  "")
            text_a = st.session_state.get("text_analysis", "")
            if not (img_a or text_a):
                st.warning("يرجى إجراء تحليل الصورة أو النص أولاً.")
                return

            prompt_es = (
                "بناءً على التحليلات التالية لتغريدة، أنشئ ملخصاً تنفيذياً استخباراتياً "
                "احترافياً يشمل:\n"
                "1. النتائج الرئيسية\n"
                "2. المؤشرات الاستخباراتية\n"
                "3. مستوى الخطورة (من 1 إلى 10)\n"
                "4. تقييم المصداقية\n"
                "5. السياق والخلفية\n"
                "6. التوصيات الفورية\n"
                "7. الاستراتيجية المقترحة\n\n"
                f"تحليل الصور:\n{img_a}\n\n"
                f"تحليل النص:\n{text_a}"
            )
            with st.spinner("🧠 جاري توليد الملخص التنفيذي..."):
                summary = gemini_text(prompt_es, api_key, model_name)
            if summary:
                st.session_state["exec_summary"] = summary
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#1a0a10,#2a1020);
                            border-radius:16px;padding:24px;
                            border:2px solid #e94560;
                            box-shadow:0 4px 20px rgba(233,69,96,0.3);
                            direction:rtl;margin-top:12px;">
                    <h3 style="color:#e94560;margin-bottom:16px;">
                        📋 الملخص التنفيذي
                    </h3>
                    {nl_to_br(summary)}
                </div>
                """, unsafe_allow_html=True)

    render_export_buttons(
        st.session_state.get("tweet_data", {}).get("الحساب", "tweet")
    )


# ─────────────────────────────────────────
# الشريط الجانبي
# ─────────────────────────────────────────

def render_sidebar() -> tuple[str, str]:
    with st.sidebar:
        st.markdown(f"### {PAGE_ICON} {PAGE_TITLE}")
        st.caption(f"الإصدار: **{VERSION}**")
        st.divider()

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            help="احصل على مفتاحك من https://aistudio.google.com/apikey",
            key="gemini_api_key_input"
        )

        model_label = st.selectbox(
            "🤖 النموذج",
            list(GEMINI_MODELS.keys()),
            key="model_selector"
        )
        model_name = GEMINI_MODELS[model_label]

        st.divider()
        st.markdown("#### 📡 مصادر البيانات")
        st.success("✅ FxTwitter API (نشط)")
        st.error("❌ Nitter (مغلق نهائياً 2024)")

        st.divider()
        st.markdown("#### 📖 كيفية الاستخدام")
        st.markdown("""
        1. أدخل مفتاح Gemini API
        2. **تحليل حساب:** أدخل رابط أي تغريدة للحساب
        3. **تحليل تغريدة:** أدخل رابط التغريدة مباشرة
        4. ارفع الصور وحدد نقطة التحليل
        5. صدّر النتائج (Word / PPTX / TXT)
        """)

    return api_key, model_name


# ─────────────────────────────────────────
# النقطة الرئيسية
# ─────────────────────────────────────────

def main():
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>
        body, .stApp { background-color: #0d1b2a; color: #e0e0e0; }
        .stTabs [data-baseweb="tab"] {
            font-size: 1rem; font-weight: 600; padding: 10px 24px;
        }
        .stTabs [aria-selected="true"] {
            border-bottom: 3px solid #e94560 !important;
            color: #e94560 !important;
        }
        .stButton > button {
            background: linear-gradient(135deg, #e94560, #c0392b);
            color: white; border: none; border-radius: 8px;
            font-weight: 600; padding: 8px 20px;
            transition: all 0.2s ease;
        }
        .stButton > button:hover { opacity: 0.85; transform: translateY(-1px); }
        .stTextInput > div > div > input { background-color: #1a2a3a; color: #fff; }
        .stSelectbox > div > div { background-color: #1a2a3a; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0d1b2a; }
        ::-webkit-scrollbar-thumb { background: #e94560; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)

    api_key, model_name = render_sidebar()

    tab1, tab2 = st.tabs(["🔍 تحليل حساب X", "📌 تحليل تغريدة"])
    with tab1:
        account_tab(api_key, model_name)
    with tab2:
        tweet_tab(api_key, model_name)


if __name__ == "__main__":
    main()
