# ============================================================
# محلل حسابات X الاستخباراتي - v10.2
# image_analysis_points.py
# ============================================================

import streamlit as st
import requests
import base64
import io
import re
import random
from datetime import datetime
from PIL import Image
from bs4 import BeautifulSoup
import google.generativeai as genai
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn as docx_qn
from pptx import Presentation
from pptx.util import Inches as PInches, Pt as PPt, Emu
from pptx.dml.color import RGBColor as PRGBColor
from pptx.enum.text import PP_ALIGN
import lxml.etree as etree

# ===================== الثوابت =====================
PAGE_TITLE = "محلل حسابات X الاستخباراتي"
PAGE_ICON = "🔍"
VERSION = "v10.2"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
]

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
    "https://nitter.net",
    "https://nitter.1d4.us",
]

FXTWITTER_API = "https://api.fxtwitter.com"

# ✅ أسماء النماذج المُصحَّحة
GEMINI_MODELS = {
    "Gemini 2.5 Flash (موصى به)": "gemini-2.5-flash",
    "Gemini 2.0 Flash Lite (اقتصادي)": "gemini-2.0-flash-lite",
    "Gemini 2.5 Pro (متقدم)": "gemini-2.5-pro",
    "Gemini 1.5 Flash (احتياطي)": "gemini-1.5-flash",
}

IMAGE_ANALYSIS_POINTS = {
    "📍 تحليل الموقع الجغرافي": (
        "حلّل هذه الصورة لتحديد الموقع الجغرافي المحتمل. ابحث عن: "
        "أسماء الأماكن والشوارع، اللافتات والعلامات، الطراز المعماري، "
        "الغطاء النباتي والمناخ، العلامات البارزة. قدّم تقريراً احترافياً باللغة العربية."
    ),
    "👤 تحليل الأشخاص والهويات": (
        "حلّل الأشخاص في الصورة: الجنس والعمر التقديري، الملابس ودلالاتها، "
        "الإيماءات والتعبيرات، أي وثائق أو شارات مرئية، العلاقات بين الأشخاص. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "🚗 تحليل المركبات والمعدات": (
        "حلّل المركبات والمعدات المرئية: الماركة والموديل، أرقام اللوحات إن وجدت، "
        "حالة المركبة، الاستخدام المحتمل، أي معدات خاصة. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "📄 تحليل الوثائق والنصوص": (
        "استخرج وحلّل أي نصوص أو وثائق في الصورة: النصوص المرئية، "
        "اللغة المستخدمة، نوع الوثيقة، المعلومات المستخلصة. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "🔫 تحليل الأسلحة والتجهيزات": (
        "حدّد وحلّل أي أسلحة أو تجهيزات عسكرية مرئية: النوع والطراز، "
        "حالة الاستخدام، الدلالات التكتيكية. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "🏗️ تحليل البنية التحتية": (
        "حلّل البنية التحتية والمنشآت المرئية: نوع المنشأة، حالتها، "
        "الاستخدام المحتمل، الأهمية الاستراتيجية. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "📅 تحليل التوقيت والزمن": (
        "حدّد الإطار الزمني من المؤشرات المرئية: الإضاءة الطبيعية، "
        "الظلال، الملابس الموسمية، التقنيات المرئية، أي تواريخ ظاهرة. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "⚠️ تحليل الأحداث والنشاطات": (
        "حلّل الأحداث والنشاطات الجارية: نوع الحدث، المشاركون، "
        "المرحلة الزمنية للحدث، الأهمية والخطورة. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "🔍 كشف التزوير والتلاعب": (
        "افحص الصورة للكشف عن أي تزوير أو تلاعب: تناسق الإضاءة، "
        "الحواف والتدرجات، علامات التعديل الرقمي، مستوى المصداقية. "
        "قدّم تقريراً احترافياً باللغة العربية."
    ),
    "🎯 تحليل شامل ومتكامل": (
        "قدّم تحليلاً شاملاً ومتكاملاً للصورة من جميع الجوانب الاستخباراتية: "
        "الموقع، الأشخاص، الأحداث، الزمن، الدلالات، التوصيات. "
        "قدّم تقريراً احترافياً مفصلاً باللغة العربية."
    ),
}


# =================== الدوال المساعدة ===================

def safe_text(text):
    if text is None:
        return ""
    return str(text).strip()


def escape_html(text):
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def nl_to_br(text):
    if not text:
        return ""
    return str(text).replace('\n', '<br>')


def safe_html_lines(text):
    if not text:
        return ""
    return escape_html(text).replace('\n', '<br>')


def extract_username(url_or_name):
    if not url_or_name:
        return ""
    url_or_name = str(url_or_name).strip()
    match = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)', url_or_name)
    if match:
        return match.group(1)
    return url_or_name.lstrip('@').strip()


def extract_tweet_id(url_or_id):
    if not url_or_id:
        return ""
    url_or_id = str(url_or_id).strip()
    match = re.search(r'status/(\d+)', url_or_id)
    if match:
        return match.group(1)
    if url_or_id.isdigit():
        return url_or_id
    return ""


def format_number(n):
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return str(n) if n else "0"


def format_date(date_str):
    if not date_str:
        return ""
    try:
        for fmt in ["%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                continue
    except Exception:
        pass
    return str(date_str)


def image_to_base64(img):
    try:
        buf = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def base64_to_bytesio(b64_str):
    try:
        return io.BytesIO(base64.b64decode(b64_str))
    except Exception:
        return None


def download_image_b64(url):
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            return image_to_base64(img)
    except Exception:
        pass
    return ""


# =================== جلب بيانات Nitter ===================

def fetch_nitter(username):
    username = extract_username(username)
    if not username:
        return None, "اسم المستخدم غير صالح"

    for mirror in NITTER_MIRRORS:
        try:
            url = f"{mirror}/{username}"
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
            }
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            data = {"username": username, "source": mirror}

            name_el = soup.select_one(".profile-card-fullname")
            data["name"] = name_el.get_text(strip=True) if name_el else username

            bio_el = soup.select_one(".profile-bio")
            data["bio"] = bio_el.get_text(strip=True) if bio_el else ""

            loc_el = soup.select_one(".profile-location")
            data["location"] = loc_el.get_text(strip=True) if loc_el else ""

            web_el = soup.select_one(".profile-website")
            data["website"] = web_el.get_text(strip=True) if web_el else ""

            join_el = soup.select_one(".profile-joindate")
            data["joined"] = join_el.get_text(strip=True) if join_el else ""

            tweets_el = soup.select_one('[href*="tweets"] .profile-stat-num')
            following_el = soup.select_one('[href*="following"] .profile-stat-num')
            followers_el = soup.select_one('[href*="followers"] .profile-stat-num')

            data["tweets_count"] = (
                tweets_el.get_text(strip=True).replace(",", "") if tweets_el else "0"
            )
            data["following_count"] = (
                following_el.get_text(strip=True).replace(",", "") if following_el else "0"
            )
            data["followers_count"] = (
                followers_el.get_text(strip=True).replace(",", "") if followers_el else "0"
            )

            avatar_el = soup.select_one(".profile-card-avatar img")
            if avatar_el:
                avatar_src = avatar_el.get("src", "")
                if avatar_src.startswith("/"):
                    avatar_src = mirror + avatar_src
                data["avatar_url"] = avatar_src
                data["avatar_b64"] = download_image_b64(avatar_src)
            else:
                data["avatar_url"] = ""
                data["avatar_b64"] = ""

            verified_el = soup.select_one(".profile-card-fullname .icon-ok-circled")
            data["verified"] = verified_el is not None

            return data, None

        except Exception:
            continue

    return None, "فشل الاتصال بجميع مرايا Nitter"


# =================== جلب بيانات FxTwitter ===================

def fetch_fxtwitter(tweet_id):
    tweet_id = extract_tweet_id(tweet_id)
    if not tweet_id:
        return None, "معرّف التغريدة غير صالح"

    try:
        url = f"{FXTWITTER_API}/status/{tweet_id}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None, f"خطأ HTTP {r.status_code}"

        j = r.json()
        tweet = j.get("tweet", {})
        if not tweet:
            return None, "لم يتم العثور على بيانات التغريدة"

        author = tweet.get("author", {})
        media = tweet.get("media", {})
        photos = media.get("photos", []) if media else []

        data = {
            "id": tweet_id,
            "text": tweet.get("text", ""),
            "created_at": tweet.get("created_at", ""),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "views": tweet.get("views", 0),
            "lang": tweet.get("lang", ""),
            "url": tweet.get("url", f"https://x.com/i/status/{tweet_id}"),
            "author_name": author.get("name", ""),
            "author_username": author.get("screen_name", ""),
            "author_followers": author.get("followers", 0),
            "author_following": author.get("following", 0),
            "author_verified": author.get("verified", False),
            "photos": [p.get("url", "") for p in photos],
            "has_media": len(photos) > 0,
        }

        photo_b64_list = []
        for photo_url in data["photos"][:3]:
            b64 = download_image_b64(photo_url)
            if b64:
                photo_b64_list.append(b64)
        data["photos_b64"] = photo_b64_list

        return data, None

    except Exception as e:
        return None, f"خطأ: {str(e)}"


# =================== Gemini AI ===================

def get_gemini_model(api_key, model_name):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def gemini_text(prompt, api_key, model_name):
    try:
        model = get_gemini_model(api_key, model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ Gemini: {str(e)}"


def gemini_with_images(prompt, images_b64, api_key, model_name):
    try:
        model = get_gemini_model(api_key, model_name)
        parts = []
        for b64 in images_b64:
            try:
                img_data = base64.b64decode(b64)
                parts.append(Image.open(io.BytesIO(img_data)))
            except Exception:
                pass
        parts.append(prompt)
        response = model.generate_content(parts)
        return response.text
    except Exception as e:
        return f"خطأ Gemini: {str(e)}"


# =================== RTL Helpers ===================

def _set_rtl_para(paragraph):
    try:
        pPr = paragraph._p.get_or_add_pPr()
        bidi = etree.SubElement(pPr, docx_qn('w:bidi'))
        bidi.set(docx_qn('w:val'), '1')
        jc = etree.SubElement(pPr, docx_qn('w:jc'))
        jc.set(docx_qn('w:val'), 'right')
    except Exception:
        pass


def _set_run_font(run, font_name="Arial", font_size=16, bold=False, color=None):
    try:
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        if color:
            run.font.color.rgb = RGBColor(*color)
    except Exception:
        pass


def set_para_rtl_pptx(paragraph):
    try:
        pPr = paragraph._p.get_or_add_pPr()
        pPr.set('rtl', '1')
        paragraph.alignment = PP_ALIGN.RIGHT
    except Exception:
        try:
            paragraph.alignment = PP_ALIGN.RIGHT
        except Exception:
            pass


# =================== تصدير Word ===================

def _add_word_section(doc, text, heading_color=(0, 120, 212)):
    for line in text.split('\n'):
        if not line.strip():
            p = doc.add_paragraph()
            _set_rtl_para(p)
            continue
        if line.startswith('###'):
            p = doc.add_heading(line.replace('###', '').strip(), level=3)
            _set_rtl_para(p)
            if p.runs:
                p.runs[0].font.color.rgb = RGBColor(*heading_color)
                p.runs[0].font.size = Pt(17)
        elif line.startswith('##'):
            p = doc.add_heading(line.replace('##', '').strip(), level=2)
            _set_rtl_para(p)
            if p.runs:
                p.runs[0].font.color.rgb = RGBColor(*heading_color)
                p.runs[0].font.size = Pt(18)
        elif line.startswith('#'):
            p = doc.add_heading(line.replace('#', '').strip(), level=1)
            _set_rtl_para(p)
            if p.runs:
                p.runs[0].font.color.rgb = RGBColor(*heading_color)
                p.runs[0].font.size = Pt(20)
        elif line.startswith('-') or line.startswith('*'):
            p = doc.add_paragraph()
            _set_rtl_para(p)
            run = p.add_run('• ' + line.lstrip('-* ').strip())
            _set_run_font(run, font_size=16)
        else:
            p = doc.add_paragraph(line.strip())
            _set_rtl_para(p)
            if p.runs:
                _set_run_font(p.runs[0], font_size=16)


def export_to_word(title, account_data=None, tweet_data=None,
                   report_text="", images_b64=None,
                   image_analysis_text="", exec_summary=""):
    doc = Document()

    try:
        sectPr = doc.element.body.get_or_add_sectPr()
        etree.SubElement(sectPr, docx_qn('w:bidi'))
    except Exception:
        pass

    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(16)

    # غلاف
    p = doc.add_paragraph()
    _set_rtl_para(p)
    r = p.add_run("🔍 محلل حسابات X الاستخباراتي")
    _set_run_font(r, font_size=26, bold=True, color=(0, 120, 212))

    doc.add_paragraph()

    p = doc.add_paragraph()
    _set_rtl_para(p)
    r = p.add_run(safe_text(title))
    _set_run_font(r, font_size=20, bold=True)

    p = doc.add_paragraph()
    _set_rtl_para(p)
    r = p.add_run(
        f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  {VERSION}"
    )
    _set_run_font(r, font_size=14, color=(100, 100, 100))

    doc.add_page_break()

    # الصور
    if images_b64:
        h = doc.add_heading('الصور المرفقة', level=1)
        _set_rtl_para(h)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(0, 120, 212)
            h.runs[0].font.size = Pt(20)
        for i, b64 in enumerate(images_b64[:3]):
            bio = base64_to_bytesio(b64)
            if bio:
                try:
                    p = doc.add_paragraph(f"صورة {i + 1}")
                    _set_rtl_para(p)
                    doc.add_picture(bio, width=Inches(4.5))
                    doc.add_paragraph()
                except Exception:
                    pass
        doc.add_page_break()

    # تحليل الصورة
    if image_analysis_text:
        h = doc.add_heading('تحليل الصورة بالذكاء الاصطناعي', level=1)
        _set_rtl_para(h)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(0, 120, 212)
            h.runs[0].font.size = Pt(20)
        _add_word_section(doc, image_analysis_text)
        doc.add_page_break()

    # بيانات الحساب
    if account_data:
        h = doc.add_heading('بيانات الحساب', level=1)
        _set_rtl_para(h)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(0, 120, 212)
            h.runs[0].font.size = Pt(20)
        fields = [
            ("الاسم", account_data.get("name", "")),
            ("المستخدم", f"@{account_data.get('username', '')}"),
            ("الوصف", account_data.get("bio", "")),
            ("الموقع", account_data.get("location", "")),
            ("تاريخ الانضمام", account_data.get("joined", "")),
            ("المتابعون", format_number(account_data.get("followers_count", 0))),
            ("يتابع", format_number(account_data.get("following_count", 0))),
            ("التغريدات", format_number(account_data.get("tweets_count", 0))),
        ]
        for label, value in fields:
            if value:
                p = doc.add_paragraph()
                _set_rtl_para(p)
                lr = p.add_run(f"{label}: ")
                _set_run_font(lr, font_size=16, bold=True, color=(0, 80, 160))
                vr = p.add_run(safe_text(value))
                _set_run_font(vr, font_size=16)
        doc.add_page_break()

    # بيانات التغريدة
    if tweet_data:
        h = doc.add_heading('بيانات التغريدة', level=1)
        _set_rtl_para(h)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(0, 120, 212)
            h.runs[0].font.size = Pt(20)
        fields = [
            ("الكاتب", tweet_data.get("author_name", "")),
            ("المستخدم", f"@{tweet_data.get('author_username', '')}"),
            ("نص التغريدة", tweet_data.get("text", "")),
            ("التاريخ", format_date(tweet_data.get("created_at", ""))),
            ("الإعجابات", format_number(tweet_data.get("likes", 0))),
            ("إعادة التغريد", format_number(tweet_data.get("retweets", 0))),
            ("المشاهدات", format_number(tweet_data.get("views", 0))),
        ]
        for label, value in fields:
            if value:
                p = doc.add_paragraph()
                _set_rtl_para(p)
                lr = p.add_run(f"{label}: ")
                _set_run_font(lr, font_size=16, bold=True, color=(0, 80, 160))
                vr = p.add_run(safe_text(value))
                _set_run_font(vr, font_size=16)
        doc.add_page_break()

    # تقرير التحليل
    if report_text:
        h = doc.add_heading('تقرير التحليل', level=1)
        _set_rtl_para(h)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(0, 120, 212)
            h.runs[0].font.size = Pt(20)
        _add_word_section(doc, report_text)
        doc.add_page_break()

    # الملخص التنفيذي
    if exec_summary:
        h = doc.add_heading('الملخص التنفيذي', level=1)
        _set_rtl_para(h)
        if h.runs:
            h.runs[0].font.color.rgb = RGBColor(233, 69, 96)
            h.runs[0].font.size = Pt(22)
        p = doc.add_paragraph('─' * 60)
        _set_rtl_para(p)
        if p.runs:
            _set_run_font(p.runs[0], font_size=10, color=(233, 69, 96))
        _add_word_section(doc, exec_summary, heading_color=(233, 69, 96))

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


# =================== تصدير PowerPoint ===================

def export_to_pptx(title, account_data=None, tweet_data=None,
                   report_text="", images_b64=None,
                   image_analysis_text="", exec_summary=""):
    prs = Presentation()
    prs.slide_width = Emu(9144000)
    prs.slide_height = Emu(5143500)
    W = prs.slide_width
    H = prs.slide_height

    DARK_BG = PRGBColor(10, 10, 30)
    BLUE = PRGBColor(0, 120, 212)
    RED = PRGBColor(233, 69, 96)
    WHITE = PRGBColor(255, 255, 255)
    GRAY = PRGBColor(180, 180, 180)

    def add_bg(slide, color=None):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = color if color else DARK_BG

    def add_title_box(slide, text, top=Emu(300000), color=None, font_size=32):
        txBox = slide.shapes.add_textbox(
            Emu(300000), top, W - Emu(600000), Emu(700000)
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        set_para_rtl_pptx(p)
        run = p.add_run()
        run.text = str(text)
        run.font.size = PPt(font_size)
        run.font.bold = True
        run.font.color.rgb = color if color else BLUE

    def add_content_box(slide, text, top=Emu(1200000),
                        height=Emu(3500000), font_size=16):
        txBox = slide.shapes.add_textbox(
            Emu(300000), top, W - Emu(600000), height
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        first = True
        for line in str(text).split('\n'):
            if not line.strip():
                continue
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            set_para_rtl_pptx(p)
            run = p.add_run()
            if line.startswith('###'):
                run.text = line.replace('###', '').strip()
                run.font.size = PPt(font_size + 2)
                run.font.bold = True
                run.font.color.rgb = RED
            elif line.startswith('##'):
                run.text = line.replace('##', '').strip()
                run.font.size = PPt(font_size + 3)
                run.font.bold = True
                run.font.color.rgb = BLUE
            elif line.startswith('#'):
                run.text = line.replace('#', '').strip()
                run.font.size = PPt(font_size + 5)
                run.font.bold = True
                run.font.color.rgb = BLUE
            else:
                run.text = line.strip()
                run.font.size = PPt(font_size)
                run.font.color.rgb = WHITE

    # غلاف
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)

    box = slide.shapes.add_textbox(
        Emu(300000), Emu(500000), W - Emu(600000), Emu(800000)
    )
    tf = box.text_frame
    p = tf.paragraphs[0]
    set_para_rtl_pptx(p)
    r = p.add_run()
    r.text = "🔍 محلل حسابات X الاستخباراتي"
    r.font.size = PPt(36)
    r.font.bold = True
    r.font.color.rgb = BLUE

    box2 = slide.shapes.add_textbox(
        Emu(300000), Emu(1600000), W - Emu(600000), Emu(900000)
    )
    tf2 = box2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    set_para_rtl_pptx(p2)
    r2 = p2.add_run()
    r2.text = safe_text(title)
    r2.font.size = PPt(28)
    r2.font.bold = True
    r2.font.color.rgb = WHITE

    box3 = slide.shapes.add_textbox(
        Emu(300000), Emu(3600000), W - Emu(600000), Emu(500000)
    )
    tf3 = box3.text_frame
    p3 = tf3.paragraphs[0]
    set_para_rtl_pptx(p3)
    r3 = p3.add_run()
    r3.text = f"{datetime.now().strftime('%Y-%m-%d')}  |  {VERSION}"
    r3.font.size = PPt(16)
    r3.font.color.rgb = GRAY

    # الصور
    if images_b64:
        for i, b64 in enumerate(images_b64[:3]):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_bg(slide)
            add_title_box(slide, f"صورة {i + 1}", color=BLUE, font_size=24)
            bio = base64_to_bytesio(b64)
            if bio:
                try:
                    slide.shapes.add_picture(
                        bio,
                        Emu(int(W * 0.1)), Emu(1000000),
                        Emu(int(W * 0.8)), Emu(int(H * 0.7)),
                    )
                except Exception:
                    pass

    # تحليل الصورة
    if image_analysis_text:
        lines = image_analysis_text.split('\n')
        chunks = [lines[i:i + 25] for i in range(0, len(lines), 25)]
        for ci, chunk_lines in enumerate(chunks):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_bg(slide)
            t = "🔍 تحليل الصورة" if ci == 0 else f"🔍 تحليل الصورة ({ci + 1})"
            add_title_box(slide, t, color=RED, font_size=28)
            add_content_box(slide, '\n'.join(chunk_lines), font_size=14)

    # بيانات الحساب
    if account_data:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        add_bg(slide)
        add_title_box(slide, "📊 بيانات الحساب", color=BLUE, font_size=28)
        fields = [
            f"الاسم: {account_data.get('name', '')}",
            f"@{account_data.get('username', '')}",
            f"الموقع: {account_data.get('location', '')}",
            f"المتابعون: {format_number(account_data.get('followers_count', 0))}",
            f"يتابع: {format_number(account_data.get('following_count', 0))}",
            f"التغريدات: {format_number(account_data.get('tweets_count', 0))}",
        ]
        add_content_box(slide, '\n'.join(fields), font_size=18)

    # بيانات التغريدة
    if tweet_data:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        add_bg(slide)
        add_title_box(slide, "🐦 بيانات التغريدة", color=BLUE, font_size=28)
        fields = [
            f"الكاتب: {tweet_data.get('author_name', '')}",
            f"@{tweet_data.get('author_username', '')}",
            f"النص: {tweet_data.get('text', '')[:200]}",
            f"الإعجابات: {format_number(tweet_data.get('likes', 0))}",
            f"إعادة التغريد: {format_number(tweet_data.get('retweets', 0))}",
            f"المشاهدات: {format_number(tweet_data.get('views', 0))}",
        ]
        add_content_box(slide, '\n'.join(fields), font_size=16)

    # تقرير التحليل
    if report_text:
        lines = report_text.split('\n')
        chunks = [lines[i:i + 20] for i in range(0, len(lines), 20)]
        for ci, chunk_lines in enumerate(chunks):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_bg(slide)
            t = "📋 تقرير التحليل" if ci == 0 else f"📋 تقرير التحليل ({ci + 1})"
            add_title_box(slide, t, color=BLUE, font_size=28)
            add_content_box(slide, '\n'.join(chunk_lines), font_size=14)

    # الملخص التنفيذي
    if exec_summary:
        lines = exec_summary.split('\n')
        chunks = [lines[i:i + 18] for i in range(0, len(lines), 18)]
        for ci, chunk_lines in enumerate(chunks):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = PRGBColor(15, 10, 35)

            t = "📋 الملخص التنفيذي" if ci == 0 else f"📋 الملخص التنفيذي ({ci + 1})"
            add_title_box(slide, t, color=RED, font_size=30)

            try:
                sep_box = slide.shapes.add_textbox(
                    Emu(300000), Emu(1020000), W - Emu(600000), Emu(60000)
                )
                sep_tf = sep_box.text_frame
                sep_p = sep_tf.paragraphs[0]
                sep_r = sep_p.add_run()
                sep_r.text = '─' * 70
                sep_r.font.color.rgb = RED
                sep_r.font.size = PPt(9)
            except Exception:
                pass

            add_content_box(
                slide, '\n'.join(chunk_lines),
                top=Emu(1120000), font_size=15,
            )

    # شريحة ختامية
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    end_box = slide.shapes.add_textbox(
        Emu(300000), Emu(2000000), W - Emu(600000), Emu(800000)
    )
    tf = end_box.text_frame
    p = tf.paragraphs[0]
    set_para_rtl_pptx(p)
    r = p.add_run()
    r.text = "انتهى التقرير"
    r.font.size = PPt(32)
    r.font.bold = True
    r.font.color.rgb = GRAY

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


# =================== أزرار التصدير ===================

def render_export_buttons(title, account_data=None, tweet_data=None,
                          report_text="", images_b64=None,
                          image_analysis_text="", exec_summary=""):
    st.markdown("---")
    st.subheader("📥 تصدير التقرير")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r'[^\w\u0600-\u06FF]', '_', safe_text(title))[:30]
    file_prefix = f"X_Report_{safe_title}_{timestamp}"

    col1, col2, col3 = st.columns(3)

    with col1:
        try:
            word_bytes = export_to_word(
                title=title, account_data=account_data,
                tweet_data=tweet_data, report_text=report_text,
                images_b64=images_b64,
                image_analysis_text=image_analysis_text,
                exec_summary=exec_summary,
            )
            st.download_button(
                "📄 تحميل Word", data=word_bytes,
                file_name=f"{file_prefix}.docx",
                mime="application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"خطأ Word: {e}")

    with col2:
        try:
            pptx_bytes = export_to_pptx(
                title=title, account_data=account_data,
                tweet_data=tweet_data, report_text=report_text,
                images_b64=images_b64,
                image_analysis_text=image_analysis_text,
                exec_summary=exec_summary,
            )
            st.download_button(
                "📊 تحميل PowerPoint", data=pptx_bytes,
                file_name=f"{file_prefix}.pptx",
                mime="application/vnd.openxmlformats-officedocument"
                     ".presentationml.presentation",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"خطأ PPTX: {e}")

    with col3:
        parts = [
            f"تقرير: {title}",
            f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]
        if report_text:
            parts += ["=== تقرير التحليل ===", report_text, ""]
        if image_analysis_text:
            parts += ["=== تحليل الصورة ===", image_analysis_text, ""]
        if exec_summary:
            parts += ["=== الملخص التنفيذي ===", exec_summary, ""]
        st.download_button(
            "📝 تحميل TXT",
            data='\n'.join(parts).encode('utf-8'),
            file_name=f"{file_prefix}.txt",
            mime="text/plain",
            use_container_width=True,
        )


# =================== بطاقة الحساب ===================

def render_profile_card(data):
    name = escape_html(safe_text(data.get("name", "")))
    username = escape_html(safe_text(data.get("username", "")))
    bio_html = safe_html_lines(data.get("bio", ""))
    location = escape_html(safe_text(data.get("location", "")))
    joined = escape_html(safe_text(data.get("joined", "")))
    followers = format_number(data.get("followers_count", 0))
    following = format_number(data.get("following_count", 0))
    tweets = format_number(data.get("tweets_count", 0))
    avatar_b64 = data.get("avatar_b64", "")
    img_src = (
        f"data:image/jpeg;base64,{avatar_b64}" if avatar_b64
        else "https://abs.twimg.com/sticky/default_profile_images/"
             "default_profile_400x400.png"
    )
    verified_badge = "✅ " if data.get("verified") else ""
    loc_row = (
        f'<div style="color:#aaa;margin-top:4px;">📍 {location}</div>'
        if location else ''
    )
    join_row = (
        f'<div style="color:#aaa;margin-top:4px;">📅 {joined}</div>'
        if joined else ''
    )

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);
                border:2px solid #0078d4;border-radius:16px;padding:20px;
                direction:rtl;text-align:right;
                font-family:'Segoe UI',Arial,sans-serif;margin-bottom:20px;">
        <div style="display:flex;align-items:center;gap:20px;flex-direction:row-reverse;">
            <img src="{img_src}"
                 style="width:80px;height:80px;border-radius:50%;
                        border:3px solid #0078d4;"/>
            <div>
                <div style="font-size:22px;font-weight:bold;color:#fff;">
                    {verified_badge}{name}
                </div>
                <div style="color:#0078d4;font-size:16px;">@{username}</div>
            </div>
        </div>
        <div style="color:#ddd;margin-top:12px;font-size:15px;line-height:1.7;">
            {bio_html}
        </div>
        {loc_row}{join_row}
        <div style="display:flex;justify-content:flex-end;gap:30px;
                    margin-top:16px;flex-wrap:wrap;">
            <div style="text-align:center;">
                <div style="font-size:20px;font-weight:bold;color:#0078d4;">
                    {followers}
                </div>
                <div style="color:#aaa;font-size:13px;">متابع</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:20px;font-weight:bold;color:#0078d4;">
                    {following}
                </div>
                <div style="color:#aaa;font-size:13px;">يتابع</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:20px;font-weight:bold;color:#0078d4;">
                    {tweets}
                </div>
                <div style="color:#aaa;font-size:13px;">تغريدة</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)


# =================== بطاقة التغريدة ===================

def display_tweet_card(data):
    author = escape_html(safe_text(data.get("author_name", "")))
    username = escape_html(safe_text(data.get("author_username", "")))
    text_html = safe_html_lines(data.get("text", ""))
    likes = format_number(data.get("likes", 0))
    retweets = format_number(data.get("retweets", 0))
    replies = format_number(data.get("replies", 0))
    views = format_number(data.get("views", 0))
    created = format_date(data.get("created_at", ""))
    lang = safe_text(data.get("lang", ""))
    verified_badge = "✅ " if data.get("author_verified") else ""

    st.markdown(f"""
    <div style="background:#16213e;border:1px solid #0078d4;border-radius:12px;
                padding:16px;direction:rtl;text-align:right;
                font-family:'Segoe UI',Arial,sans-serif;margin-bottom:16px;">
        <div style="margin-bottom:10px;">
            <span style="color:#fff;font-weight:bold;">
                {verified_badge}{author}
            </span>
            <span style="color:#0078d4;margin-right:8px;">@{username}</span>
        </div>
        <div style="color:#eee;font-size:16px;line-height:1.8;margin-bottom:12px;">
            {text_html}
        </div>
        <div style="display:flex;gap:20px;justify-content:flex-end;
                    flex-wrap:wrap;color:#aaa;font-size:14px;">
            <span>❤️ {likes}</span>
            <span>🔁 {retweets}</span>
            <span>💬 {replies}</span>
            <span>👁️ {views}</span>
            <span>🌐 {lang}</span>
            <span>📅 {created}</span>
        </div>
    </div>""", unsafe_allow_html=True)


# =================== تبويب الحساب ===================

def account_tab(api_key, model_name):
    st.header("🔍 تحليل حساب X")

    col1, col2 = st.columns([1, 2])
    with col1:
        uploaded_profile = st.file_uploader(
            "رفع صورة الملف الشخصي",
            type=["jpg", "jpeg", "png", "webp"],
            key="account_img_upload",
        )
    with col2:
        username_input = st.text_input(
            "اسم المستخدم أو رابط الحساب",
            placeholder="@username أو https://x.com/username",
            key="account_username",
        )

    if st.button(
        "🔍 جلب بيانات الحساب", key="btn_fetch_account", use_container_width=True
    ):
        if username_input:
            with st.spinner("جاري جلب البيانات..."):
                data, err = fetch_nitter(username_input)
                if err:
                    st.error(f"خطأ: {err}")
                else:
                    st.session_state['account_data'] = data
                    st.success("✅ تم جلب بيانات الحساب")

    account_data = st.session_state.get('account_data')
    if account_data:
        render_profile_card(account_data)

    profile_img_b64 = None
    if uploaded_profile:
        img = Image.open(uploaded_profile)
        profile_img_b64 = image_to_base64(img)
        st.image(img, caption="صورة الملف الشخصي", width=200)

    st.selectbox(
        "نقطة تحليل الصورة",
        list(IMAGE_ANALYSIS_POINTS.keys()),
        key="account_analysis_point",
    )

    if uploaded_profile and api_key:
        if st.button(
            "🔍 تحليل صورة الملف الشخصي", key="btn_analyze_profile_img"
        ):
            with st.spinner("جاري التحليل..."):
                point = st.session_state.get(
                    'account_analysis_point',
                    list(IMAGE_ANALYSIS_POINTS.keys())[0],
                )
                prompt = IMAGE_ANALYSIS_POINTS[point]
                result = gemini_with_images(
                    prompt, [profile_img_b64], api_key, model_name
                )
                st.session_state['account_img_analysis'] = result
                st.success("✅ تم حفظ تحليل الصورة")

    if st.session_state.get('account_img_analysis'):
        st.markdown("### 🔍 نتيجة تحليل الصورة")
        img_html = safe_html_lines(st.session_state['account_img_analysis'])
        st.markdown(
            f'<div style="background:#0f3460;border-radius:10px;padding:16px;'
            f'direction:rtl;text-align:right;color:#eee;line-height:1.8;">'
            f'{img_html}</div>',
            unsafe_allow_html=True,
        )

    if account_data and api_key:
        st.markdown("---")
        if st.button(
            "📊 توليد تقرير تحليل الحساب",
            key="btn_account_report",
            use_container_width=True,
        ):
            prompt = (
                "أنت محلل استخباراتي متخصص. قم بتحليل حساب X التالي وإعداد تقرير شامل:\n\n"
                f"الاسم: {account_data.get('name', '')}\n"
                f"المستخدم: @{account_data.get('username', '')}\n"
                f"الوصف: {account_data.get('bio', '')}\n"
                f"الموقع: {account_data.get('location', '')}\n"
                f"تاريخ الانضمام: {account_data.get('joined', '')}\n"
                f"المتابعون: {format_number(account_data.get('followers_count', 0))}\n"
                f"يتابع: {format_number(account_data.get('following_count', 0))}\n"
                f"التغريدات: {format_number(account_data.get('tweets_count', 0))}\n"
                f"تحليل الصورة: "
                f"{st.session_state.get('account_img_analysis', 'لم يتم تحليل الصورة')}\n\n"
                "قم بإعداد تقرير يشمل:\n"
                "## 1. ملخص هوية الحساب\n"
                "## 2. مستوى النشاط والتفاعل\n"
                "## 3. المؤشرات الجغرافية والثقافية\n"
                "## 4. تقييم المصداقية والموثوقية\n"
                "## 5. المخاطر والمؤشرات الحساسة\n"
                "## 6. التوصيات الاستخباراتية\n\n"
                "اكتب التقرير باللغة العربية بأسلوب احترافي."
            )
            with st.spinner("جاري توليد التقرير..."):
                report = gemini_text(prompt, api_key, model_name)
                st.session_state['account_report'] = report
                st.success("✅ تم توليد التقرير")

    if st.session_state.get('account_report'):
        st.markdown("### 📊 تقرير تحليل الحساب")
        r_html = safe_html_lines(st.session_state['account_report'])
        st.markdown(
            f'<div style="background:#16213e;border-radius:10px;padding:20px;'
            f'direction:rtl;text-align:right;color:#eee;line-height:1.8;">'
            f'{r_html}</div>',
            unsafe_allow_html=True,
        )
        imgs = [profile_img_b64] if profile_img_b64 else None
        render_export_buttons(
            title=f"تحليل حساب @{account_data.get('username', '') if account_data else 'X'}",
            account_data=account_data,
            report_text=st.session_state.get('account_report', ''),
            images_b64=imgs,
            image_analysis_text=st.session_state.get('account_img_analysis', ''),
            exec_summary=st.session_state.get('account_exec_summary', ''),
        )


# =================== تبويب التغريدة ===================

def tweet_tab(api_key, model_name):
    st.header("🐦 تحليل تغريدة")

    tweet_input = st.text_input(
        "رابط التغريدة أو معرّفها",
        placeholder="https://x.com/user/status/123... أو 1234567890",
        key="tweet_input",
    )

    if st.button(
        "🔍 جلب بيانات التغريدة", key="btn_fetch_tweet", use_container_width=True
    ):
        if tweet_input:
            with st.spinner("جاري جلب التغريدة..."):
                data, err = fetch_fxtwitter(tweet_input)
                if err:
                    st.error(f"خطأ: {err}")
                else:
                    st.session_state['tweet_data'] = data
                    st.success("✅ تم جلب التغريدة")

    tweet_data = st.session_state.get('tweet_data')

    if tweet_data:
        display_tweet_card(tweet_data)
        tweet_photos_b64 = tweet_data.get("photos_b64", [])
        if tweet_photos_b64:
            st.markdown("#### 🖼️ صور التغريدة")
            cols = st.columns(min(len(tweet_photos_b64), 3))
            for i, b64 in enumerate(tweet_photos_b64[:3]):
                bio = base64_to_bytesio(b64)
                if bio:
                    cols[i].image(bio, caption=f"صورة {i + 1}")

    st.markdown("---")
    uploaded_imgs = st.file_uploader(
        "رفع صور للتحليل (يمكن رفع عدة صور)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="tweet_imgs_upload",
    )

    all_images_b64 = []
    if tweet_data:
        all_images_b64.extend(tweet_data.get("photos_b64", []))

    if uploaded_imgs:
        for uf in uploaded_imgs:
            img = Image.open(uf)
            b64 = image_to_base64(img)
            if b64:
                all_images_b64.append(b64)
        cols = st.columns(min(len(uploaded_imgs), 3))
        for i, uf in enumerate(uploaded_imgs[:3]):
            uf.seek(0)
            cols[i].image(Image.open(uf), caption=uf.name, width=200)

    if all_images_b64 and api_key:
        st.selectbox(
            "اختر نقطة تحليل الصورة",
            list(IMAGE_ANALYSIS_POINTS.keys()),
            key="tweet_analysis_point",
        )
        if st.button(
            "🔍 تحليل الصور", key="btn_analyze_tweet_imgs", use_container_width=True
        ):
            with st.spinner("جاري تحليل الصور..."):
                point = st.session_state.get(
                    'tweet_analysis_point',
                    list(IMAGE_ANALYSIS_POINTS.keys())[0],
                )
                prompt = IMAGE_ANALYSIS_POINTS[point]
                result = gemini_with_images(
                    prompt, all_images_b64[:3], api_key, model_name
                )
                st.session_state['tweet_img_analysis'] = result
                st.success("✅ تم حفظ تحليل الصورة")

    if st.session_state.get('tweet_img_analysis'):
        st.markdown("### 🔍 نتيجة تحليل الصورة")
        img_html = safe_html_lines(st.session_state['tweet_img_analysis'])
        st.markdown(
            f'<div style="background:#0f3460;border-radius:10px;padding:16px;'
            f'direction:rtl;text-align:right;color:#eee;line-height:1.8;">'
            f'{img_html}</div>',
            unsafe_allow_html=True,
        )

    if tweet_data and api_key:
        st.markdown("---")
        if st.button(
            "📝 تحليل نص التغريدة",
            key="btn_analyze_tweet_text",
            use_container_width=True,
        ):
            prompt = (
                "أنت محلل استخباراتي. حلّل التغريدة التالية:\n\n"
                f"النص: {tweet_data.get('text', '')}\n"
                f"الكاتب: {tweet_data.get('author_name', '')} "
                f"(@{tweet_data.get('author_username', '')})\n"
                f"التاريخ: {format_date(tweet_data.get('created_at', ''))}\n"
                f"الإعجابات: {format_number(tweet_data.get('likes', 0))}\n"
                f"إعادة التغريد: {format_number(tweet_data.get('retweets', 0))}\n"
                f"المشاهدات: {format_number(tweet_data.get('views', 0))}\n"
                f"المتابعون: {format_number(tweet_data.get('author_followers', 0))}\n"
                f"تحليل الصورة: "
                f"{st.session_state.get('tweet_img_analysis', 'لا توجد صور')}\n\n"
                "قدّم تقريراً يشمل:\n"
                "## 1. تحليل المحتوى\n"
                "## 2. تحليل اللغة والأسلوب\n"
                "## 3. السياق الزمني والموضوعي\n"
                "## 4. الأثر والتأثير المتوقع\n"
                "## 5. تقييم مصداقية المصدر\n"
                "## 6. التوصيات الاستخباراتية\n\n"
                "اكتب التحليل باللغة العربية."
            )
            with st.spinner("جاري التحليل..."):
                analysis = gemini_text(prompt, api_key, model_name)
                st.session_state['tweet_analysis'] = analysis
                st.success("✅ تم التحليل")

    if st.session_state.get('tweet_analysis'):
        st.markdown("### 📝 تحليل نص التغريدة")
        a_html = safe_html_lines(st.session_state['tweet_analysis'])
        st.markdown(
            f'<div style="background:#16213e;border-radius:10px;padding:20px;'
            f'direction:rtl;text-align:right;color:#eee;line-height:1.8;">'
            f'{a_html}</div>',
            unsafe_allow_html=True,
        )

    # ── الملخص التنفيذي ──
    if tweet_data and api_key:
        st.markdown("---")
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1a0a1e,#2d1b3d);
                    border:2px solid #e94560;border-radius:12px;
                    padding:12px 20px;margin-bottom:10px;
                    direction:rtl;text-align:right;">
            <h3 style="color:#e94560;margin:0;">📋 الملخص التنفيذي</h3>
            <p style="color:#ccc;margin:5px 0 0 0;font-size:14px;">
                تقرير موحّد يجمع جميع نتائج التحليل في ملخص احترافي للقيادة
            </p>
        </div>""", unsafe_allow_html=True)

        if st.button(
            "🧠 توليد الملخص التنفيذي الشامل",
            key="btn_exec_summary",
            use_container_width=True,
        ):
            context_parts = []

            tweet_info = (
                "بيانات التغريدة:\n"
                f"- الكاتب: {tweet_data.get('author_name', '')} "
                f"(@{tweet_data.get('author_username', '')})\n"
                f"- النص: {tweet_data.get('text', '')}\n"
                f"- التاريخ: {format_date(tweet_data.get('created_at', ''))}\n"
                f"- الإعجابات: {format_number(tweet_data.get('likes', 0))}"
                f" | إعادة التغريد: {format_number(tweet_data.get('retweets', 0))}"
                f" | المشاهدات: {format_number(tweet_data.get('views', 0))}"
            )
            context_parts.append(tweet_info)

            if st.session_state.get('tweet_analysis'):
                context_parts.append(
                    "تحليل النص:\n"
                    + st.session_state['tweet_analysis'][:1500]
                )

            if st.session_state.get('tweet_img_analysis'):
                context_parts.append(
                    "تحليل الصورة:\n"
                    + st.session_state['tweet_img_analysis'][:1000]
                )

            sep = "\n---\n"
            exec_prompt = (
                "أنت محلل استخباراتي كبير. بناءً على المعلومات التالية:\n\n"
                + sep.join(context_parts)
                + "\n\nأعدّ ملخصاً تنفيذياً احترافياً يُقدَّم للقيادة، يتضمن:\n\n"
                "## الملخص التنفيذي\n\n"
                "### 🎯 النتائج الرئيسية\n"
                "(أبرز ما توصّل إليه التحليل في 3-5 نقاط محددة)\n\n"
                "### 🔍 المؤشرات الاستخباراتية\n"
                "(البيانات والإشارات ذات الأهمية الاستخباراتية)\n\n"
                "### ⚠️ مستوى الخطورة والأولوية\n"
                "(تصنيف: منخفض / متوسط / عالٍ / حرج - مع التبرير)\n\n"
                "### 📊 تقييم المصداقية\n"
                "(درجة الموثوقية من 10، مع المؤشرات الداعمة)\n\n"
                "### 🗺️ السياق والخلفية\n"
                "(الموضوع في سياقه الأشمل)\n\n"
                "### ✅ التوصيات الفورية\n"
                "(إجراءات يُنصح باتخاذها خلال 24-48 ساعة)\n\n"
                "### 📌 التوصيات الاستراتيجية\n"
                "(توصيات متوسطة وبعيدة المدى)\n\n"
                "اكتب الملخص باللغة العربية بأسلوب احترافي رسمي "
                "مناسب للتقارير الاستخباراتية."
            )

            with st.spinner("⏳ جاري توليد الملخص التنفيذي..."):
                exec_summary_text = gemini_text(exec_prompt, api_key, model_name)
                st.session_state['exec_summary'] = exec_summary_text
                st.success("✅ تم توليد الملخص التنفيذي")

    if st.session_state.get('exec_summary'):
        exec_html = safe_html_lines(st.session_state['exec_summary'])
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a0a1e 0%,#16213e 50%,#0f3460 100%);
                    border:2px solid #e94560;border-radius:14px;padding:24px;
                    direction:rtl;text-align:right;
                    font-family:'Segoe UI',Arial,sans-serif;
                    margin-top:16px;
                    box-shadow:0 4px 20px rgba(233,69,96,0.3);">
            <div style="display:flex;align-items:center;gap:10px;
                        flex-direction:row-reverse;margin-bottom:16px;">
                <span style="font-size:28px;">📋</span>
                <h2 style="color:#e94560;margin:0;font-size:22px;">
                    الملخص التنفيذي
                </h2>
            </div>
            <div style="color:#eee;font-size:16px;line-height:1.9;">
                {exec_html}
            </div>
        </div>""", unsafe_allow_html=True)

    if (
        st.session_state.get('tweet_analysis')
        or st.session_state.get('tweet_img_analysis')
        or st.session_state.get('exec_summary')
    ):
        render_export_buttons(
            title=(
                f"تحليل تغريدة @"
                f"{tweet_data.get('author_username', '') if tweet_data else 'X'}"
            ),
            tweet_data=tweet_data,
            report_text=st.session_state.get('tweet_analysis', ''),
            images_b64=all_images_b64[:3] if all_images_b64 else None,
            image_analysis_text=st.session_state.get('tweet_img_analysis', ''),
            exec_summary=st.session_state.get('exec_summary', ''),
        )


# =================== الشريط الجانبي ===================

def render_sidebar():
    with st.sidebar:
        st.markdown(f"## {PAGE_TITLE}")
        st.markdown(f"**الإصدار:** {VERSION}")
        st.markdown("---")

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="أدخل مفتاح Gemini API...",
            key="gemini_api_key",
        )
        st.markdown(
            "[🔗 احصل على مفتاح مجاني](https://aistudio.google.com/apikey)"
        )

        if api_key:
            st.success("✅ المفتاح مُدرج")
        else:
            st.warning("⚠️ يرجى إدخال المفتاح")

        st.markdown("---")
        model_choice = st.selectbox(
            "🤖 نموذج Gemini",
            list(GEMINI_MODELS.keys()),
            key="gemini_model_choice",
        )
        model_name = GEMINI_MODELS[model_choice]

        st.markdown("---")
        st.markdown("### 📡 المصادر المستخدمة")
        st.markdown("- **Nitter**: بيانات الحساب")
        st.markdown("- **FxTwitter API**: بيانات التغريدة")
        st.markdown("- **Gemini AI**: التحليل الذكي")
        st.markdown("- **Word / PPTX**: التصدير الاحترافي")
        st.markdown("---")
        st.markdown("⚠️ `twikit` معطّل مؤقتاً (خطأ KEY_BYTE)")

        debug = st.checkbox("🔧 وضع التشخيص", key="debug_mode")
        if debug:
            st.json({
                k: bool(st.session_state.get(k))
                for k in [
                    'account_data', 'tweet_data', 'account_report',
                    'tweet_analysis', 'account_img_analysis',
                    'tweet_img_analysis', 'exec_summary',
                ]
            })

        return api_key, model_name


# =================== main ===================

def main():
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    * { direction: rtl; }
    html, body, [class*="css"] {
        font-family: 'Cairo', 'Segoe UI', Arial, sans-serif !important;
        font-size: 16px;
    }
    .stApp { background-color: #0a0a1e; color: #eee; }
    .stButton > button {
        background: linear-gradient(135deg, #0078d4, #005a9e);
        color: white; border: none; border-radius: 8px;
        font-size: 16px; font-weight: 600; padding: 10px 20px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #005a9e, #003d6b);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,120,212,0.4);
    }
    .stTextInput > div > div > input,
    .stTextArea textarea {
        background: #16213e; color: #eee;
        border: 1px solid #0078d4; border-radius: 8px;
        font-size: 16px; direction: rtl; text-align: right;
    }
    .stSelectbox > div > div {
        background: #16213e; color: #eee;
        border: 1px solid #0078d4; direction: rtl;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #107c10, #0a5a0a);
        color: white; border: none; border-radius: 8px;
        font-size: 15px;
    }
    h1, h2, h3 {
        color: #0078d4 !important;
        direction: rtl;
        text-align: right;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 16px; font-weight: 600; color: #eee;
    }
    .stTabs [aria-selected="true"] {
        color: #0078d4 !important;
        border-bottom: 2px solid #0078d4;
    }
    div[data-testid="stSidebarContent"] { background: #0f0f2a; }
    </style>""", unsafe_allow_html=True)

    for key in [
        'account_data', 'tweet_data', 'account_report', 'tweet_analysis',
        'account_img_analysis', 'tweet_img_analysis',
        'exec_summary', 'account_exec_summary',
    ]:
        if key not in st.session_state:
            st.session_state[key] = None

    api_key, model_name = render_sidebar()

    st.title("🔍 محلل حسابات X الاستخباراتي")
    st.markdown(
        f"<p style='color:#aaa;direction:rtl;text-align:right;'>"
        f"الإصدار {VERSION} | مدعوم بـ Gemini AI</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["🏠 تحليل حساب X", "🐦 تحليل تغريدة"])

    with tab1:
        account_tab(api_key, model_name)

    with tab2:
        tweet_tab(api_key, model_name)


if __name__ == "__main__":
    main()
