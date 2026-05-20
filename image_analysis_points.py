# ============================================================
#  محلل حسابات X  – v9.8
#  تصحيح: f-string backslash + RTL كامل + تصدير Word/PPTX
# ============================================================

import streamlit as st
import requests
import re
import os
import base64
import html
import json
from io import BytesIO
from datetime import datetime

from PIL import Image
from bs4 import BeautifulSoup

# ─── إعداد الصفحة ────────────────────────────────────────────
st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');

* { font-family: 'Cairo', sans-serif !important; direction: rtl; text-align: right; }

.stApp { background-color: #0d1117; color: #e6edf3; }

.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
.stSelectbox>div>div>select {
    background-color: #161b22 !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    direction: rtl !important;
    text-align: right !important;
}

.stButton>button {
    background: linear-gradient(135deg, #1f6feb, #388bfd);
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.5rem !important;
    font-weight: 700 !important;
    width: 100%;
}
.stButton>button:hover { background: linear-gradient(135deg, #388bfd, #58a6ff) !important; }

.stDownloadButton>button {
    background: linear-gradient(135deg, #238636, #2ea043) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    width: 100%;
}

.profile-card {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 24px;
    margin: 16px 0;
}
.profile-header { display: flex; gap: 20px; align-items: flex-start; flex-direction: row-reverse; }
.profile-img { width: 100px; height: 100px; border-radius: 50%; border: 3px solid #1f6feb; object-fit: cover; }
.profile-img-placeholder {
    width: 100px; height: 100px; border-radius: 50%;
    background: #21262d; display: flex; align-items: center;
    justify-content: center; font-size: 48px;
}
.profile-name { color: #e6edf3; font-size: 1.4rem; font-weight: 700; margin: 0; }
.profile-handle { color: #8b949e; font-size: 1rem; margin: 4px 0; }
.profile-bio { color: #c9d1d9; font-size: 0.95rem; margin: 8px 0; line-height: 1.6; }
.profile-stats {
    display: flex; gap: 16px; margin: 16px 0;
    flex-direction: row-reverse; flex-wrap: wrap;
}
.stat-box {
    background: #21262d; border-radius: 10px; padding: 12px 20px;
    text-align: center; flex: 1; min-width: 80px;
}
.stat-value { font-size: 1.3rem; font-weight: 700; color: #58a6ff; }
.stat-label { font-size: 0.8rem; color: #8b949e; margin-top: 4px; }
.profile-meta { display: flex; gap: 16px; flex-wrap: wrap; color: #8b949e; font-size: 0.9rem; flex-direction: row-reverse; }

.report-section {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 20px; margin: 16px 0; direction: rtl; text-align: right;
    line-height: 1.8; white-space: pre-wrap; color: #e6edf3;
}

.tweet-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 20px; margin: 16px 0;
}
.tweet-text { font-size: 1.1rem; line-height: 1.8; color: #e6edf3; direction: rtl; text-align: right; }
.tweet-stats { display: flex; gap: 20px; margin-top: 12px; color: #8b949e; flex-direction: row-reverse; flex-wrap: wrap; }
.tweet-stat { display: flex; align-items: center; gap: 6px; }

.info-box { background: #0c2d6b; border: 1px solid #1f6feb; border-radius: 8px; padding: 12px 16px; margin: 8px 0; color: #79c0ff; }
.success-box { background: #0a3d1f; border: 1px solid #238636; border-radius: 8px; padding: 12px 16px; margin: 8px 0; color: #56d364; }
.warning-box { background: #2d1f00; border: 1px solid #d29922; border-radius: 8px; padding: 12px 16px; margin: 8px 0; color: #f0883e; }
.error-box { background: #3d0a0a; border: 1px solid #da3633; border-radius: 8px; padding: 12px 16px; margin: 8px 0; color: #ff7b72; }

.section-title {
    font-size: 1.2rem; font-weight: 700; color: #58a6ff;
    border-bottom: 2px solid #1f6feb; padding-bottom: 8px;
    margin: 20px 0 12px; direction: rtl; text-align: right;
}
.export-section {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 16px; margin: 16px 0;
}
</style>
""", unsafe_allow_html=True)

# ─── الثوابت ──────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.lucahammer.com",
    "https://nitter.net",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://nitter.moomoo.me",
    "https://nitter.it",
    "https://nitter.fdn.fr",
]

FXTWITTER_API = "https://api.fxtwitter.com"

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.5-pro",
]

IMAGE_ANALYSIS_POINTS = [
    "تحليل الموقع الجغرافي (مباني، لافتات، طبيعة)",
    "تحليل الأشخاص (ملابس، جنسية، عمر تقريبي)",
    "تحليل المركبات (نوع، لوحة، دولة)",
    "تحليل الوثائق أو النصوص الظاهرة",
    "تحليل الأسلحة أو المعدات العسكرية",
    "تحليل البنية التحتية (جسور، طرق، مبانٍ)",
    "تحليل الأحداث (تظاهرة، حادثة، معركة)",
    "التحقق من الصورة (مؤشرات التزوير أو التلاعب)",
    "تحليل الزمن والتاريخ (ضوء، ظلال، تقويم)",
    "تحليل شامل عام للصورة",
]

# ─── دوال مساعدة ──────────────────────────────────────────────

def safe_text(text) -> str:
    """تحويل أي قيمة إلى نص آمن"""
    if text is None:
        return ''
    return str(text).strip()


def escape_html(text) -> str:
    """تهريب HTML مع ضمان نص آمن"""
    return html.escape(safe_text(text))


def nl_to_br(text: str) -> str:
    """تحويل السطر الجديد إلى <br> – لا backslash داخل f-string"""
    if not text:
        return ''
    return text.replace('\n', '<br>')


def safe_html_lines(text: str) -> str:
    """تنظيف + escape + تحويل أسطر لـ HTML"""
    if not text:
        return ''
    return nl_to_br(escape_html(text))


def extract_username(raw: str) -> str:
    """استخراج اسم المستخدم من رابط أو نص"""
    raw = raw.strip().lstrip('@')
    patterns = [
        r'(?:twitter|x)\.com/([A-Za-z0-9_]+)',
        r'nitter\.[^/]+/([A-Za-z0-9_]+)',
    ]
    for p in patterns:
        m = re.search(p, raw)
        if m:
            return m.group(1)
    if re.match(r'^[A-Za-z0-9_]{1,50}$', raw):
        return raw
    return ''


def extract_tweet_id(raw: str) -> str:
    """استخراج معرّف التغريدة من رابط أو نص"""
    raw = raw.strip()
    m = re.search(r'/status/(\d+)', raw)
    if m:
        return m.group(1)
    if raw.isdigit():
        return raw
    return ''


def format_number(n) -> str:
    """تنسيق الأرقام الكبيرة"""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return safe_text(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def format_date(d: str) -> str:
    """تنسيق التاريخ للعربية"""
    if not d:
        return ''
    try:
        dt = datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        return safe_text(d)


def pil_to_base64(img: Image.Image) -> str:
    """تحويل صورة PIL إلى base64 JPEG"""
    if img.mode in ('RGBA', 'P', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def url_to_base64(url: str) -> str:
    """تحميل صورة من URL وتحويلها لـ base64"""
    try:
        headers = {'User-Agent': USER_AGENTS[0]}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        return pil_to_base64(img)
    except Exception:
        return ''


# ─── جلب البيانات: Nitter ─────────────────────────────────────

def fetch_nitter(username: str, debug: bool = False) -> dict:
    """جلب بيانات حساب X من مرايا Nitter"""
    headers = {'User-Agent': USER_AGENTS[0], 'Accept-Language': 'ar,en;q=0.9'}
    last_error = ''

    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            if r.status_code != 200:
                last_error = f"HTTP {r.status_code}"
                continue

            # فحص صفحات الحماية
            content_lower = r.text.lower()
            if any(kw in content_lower for kw in ['captcha', 'cloudflare', 'enable javascript', 'ddos-guard']):
                last_error = "صفحة حماية"
                continue

            soup = BeautifulSoup(r.text, 'html.parser')

            # استخراج البيانات
            data = {'source': f'Nitter ({mirror})', 'username': username}

            # الاسم
            name_el = soup.select_one('.profile-card-fullname, .fullname, h1.profile-name')
            data['name'] = name_el.get_text(strip=True) if name_el else username

            # المعرّف
            handle_el = soup.select_one('.profile-card-username, .username, .profile-handle')
            if handle_el:
                data['screen_name'] = handle_el.get_text(strip=True).lstrip('@')
            else:
                data['screen_name'] = username

            # البايو
            bio_el = soup.select_one('.profile-bio, .bio p, .profile-card-bio')
            data['bio'] = bio_el.get_text(strip=True) if bio_el else ''

            # الموقع
            loc_el = soup.select_one('.profile-location, .location')
            data['location'] = loc_el.get_text(strip=True) if loc_el else ''

            # تاريخ الانضمام
            join_el = soup.select_one('.profile-joindate, .joindate')
            data['joined'] = join_el.get_text(strip=True) if join_el else ''

            # الإحصاءات
            stats = soup.select('.profile-stat-num, .profile-stats .stat-num, .stats li .stat-num')
            stat_labels = soup.select('.profile-stat-header, .profile-stats .stat-header, .stats li .stat-header')

            followers = following = tweets = 0
            for i, lbl_el in enumerate(stat_labels):
                lbl = lbl_el.get_text(strip=True).lower()
                try:
                    val_text = stats[i].get_text(strip=True).replace(',', '').replace('.', '')
                    val = int(val_text)
                except Exception:
                    val = 0
                if 'follow' in lbl and 'ing' not in lbl:
                    followers = val
                elif 'following' in lbl or 'متابَع' in lbl:
                    following = val
                elif 'tweet' in lbl or 'post' in lbl or 'تغريدة' in lbl:
                    tweets = val

            # محاولة بديلة لاستخراج الإحصاءات
            if followers == 0 and following == 0:
                all_nums = soup.select('.profile-stat-num')
                if len(all_nums) >= 3:
                    try:
                        tweets    = int(all_nums[0].get_text(strip=True).replace(',', ''))
                        following = int(all_nums[1].get_text(strip=True).replace(',', ''))
                        followers = int(all_nums[2].get_text(strip=True).replace(',', ''))
                    except Exception:
                        pass

            data['followers'] = followers
            data['following'] = following
            data['tweets']    = tweets

            # صورة البروفايل
            img_el = soup.select_one('.profile-card-avatar img, .avatar img, img.profile-pic')
            if img_el and img_el.get('src'):
                img_url = img_el['src']
                if img_url.startswith('/'):
                    img_url = mirror + img_url
                data['profile_image_url'] = img_url
                data['profile_image_b64'] = url_to_base64(img_url)
            else:
                data['profile_image_b64'] = ''

            if debug:
                st.write(f"✅ نجح: {mirror}")
            return data

        except requests.exceptions.Timeout:
            last_error = "انتهت المهلة"
        except Exception as e:
            last_error = str(e)
            if debug:
                st.write(f"❌ فشل {mirror}: {e}")

    return {'error': f'فشل جميع المرايا. آخر خطأ: {last_error}', 'source': 'Nitter'}


# ─── جلب البيانات: FxTwitter ─────────────────────────────────

def fetch_fxtwitter(tweet_id: str) -> dict:
    """جلب تفاصيل تغريدة عبر FxTwitter API"""
    url = f"{FXTWITTER_API}/status/{tweet_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        raw = r.json()
        tweet = raw.get('tweet', {})
        author = tweet.get('author', {})

        media_urls = []
        media = tweet.get('media', {})
        if media:
            for photo in media.get('photos', []):
                media_urls.append(photo.get('url', ''))
            for video in media.get('videos', []):
                if video.get('thumbnail_url'):
                    media_urls.append(video['thumbnail_url'])

        return {
            'id':          tweet.get('id', tweet_id),
            'text':        tweet.get('text', ''),
            'date':        format_date(tweet.get('created_at', '')),
            'likes':       tweet.get('likes', 0),
            'retweets':    tweet.get('retweets', 0),
            'replies':     tweet.get('replies', 0),
            'views':       tweet.get('views', 0),
            'bookmarks':   tweet.get('bookmarks', 0),
            'lang':        tweet.get('lang', ''),
            'source':      tweet.get('source', ''),
            'url':         tweet.get('url', ''),
            'author_name': author.get('name', ''),
            'author_handle': author.get('screen_name', ''),
            'author_followers': author.get('followers', 0),
            'author_bio':  author.get('description', ''),
            'author_avatar': author.get('avatar_url', ''),
            'media_urls':  media_urls,
            'data_source': 'FxTwitter API',
        }
    except Exception as e:
        return {'error': str(e)}


# ─── Gemini AI ────────────────────────────────────────────────

def get_gemini_model(api_key: str, model_name: str):
    """تهيئة نموذج Gemini"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        return None


def gemini_text(model, prompt: str) -> str:
    """إرسال prompt نصي إلى Gemini"""
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"❌ خطأ Gemini: {e}"


def gemini_with_images(model, prompt: str, images_b64: list) -> str:
    """إرسال prompt مع صور إلى Gemini"""
    try:
        import google.generativeai as genai
        parts = [prompt]
        for b64 in images_b64:
            if b64:
                parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': b64}})
        resp = model.generate_content(parts)
        return resp.text
    except Exception as e:
        return f"❌ خطأ Gemini: {e}"


# ─── تصدير Word ───────────────────────────────────────────────

def export_to_word(title: str, data: dict, report_text: str, export_type: str = 'account') -> bytes:
    """تصدير التقرير إلى ملف Word"""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement

        doc = Document()

        # إعداد الصفحة RTL
        section = doc.sections[0]
        section.page_width  = Inches(8.27)
        section.page_height = Inches(11.69)

        # دالة لضبط RTL في فقرة
        def set_rtl(para):
            pPr = para._p.get_or_add_pPr()
            bidi = OxmlElement('w:bidi')
            pPr.append(bidi)
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # دالة إضافة فقرة RTL
        def add_rtl_paragraph(text, bold=False, size=12, color=None):
            para = doc.add_paragraph()
            set_rtl(para)
            run = para.add_run(text)
            run.bold = bold
            run.font.size = Pt(size)
            if color:
                run.font.color.rgb = RGBColor(*color)
            # RTL للـ run
            rPr = run._r.get_or_add_rPr()
            rtl_el = OxmlElement('w:rtl')
            rPr.append(rtl_el)
            return para

        # العنوان الرئيسي
        add_rtl_paragraph(title, bold=True, size=20, color=(31, 111, 235))
        add_rtl_paragraph(f"تاريخ التقرير: {datetime.now().strftime('%Y/%m/%d %H:%M')}", size=10, color=(139, 148, 158))
        doc.add_paragraph()

        if export_type == 'account':
            add_rtl_paragraph("بيانات الحساب", bold=True, size=14, color=(88, 166, 255))
            fields = [
                ('الاسم',        data.get('name', '')),
                ('المعرّف',      '@' + data.get('screen_name', '')),
                ('المتابِعون',   format_number(data.get('followers', 0))),
                ('يتابع',        format_number(data.get('following', 0))),
                ('التغريدات',    format_number(data.get('tweets', 0))),
                ('الموقع',       data.get('location', '')),
                ('تاريخ الانضمام', data.get('joined', '')),
                ('الوصف',        data.get('bio', '')),
                ('المصدر',       data.get('source', '')),
            ]
        else:
            add_rtl_paragraph("بيانات التغريدة", bold=True, size=14, color=(88, 166, 255))
            fields = [
                ('المؤلف',       data.get('author_name', '')),
                ('المعرّف',      '@' + data.get('author_handle', '')),
                ('التاريخ',      data.get('date', '')),
                ('الإعجابات',    format_number(data.get('likes', 0))),
                ('الإعادات',     format_number(data.get('retweets', 0))),
                ('الردود',       format_number(data.get('replies', 0))),
                ('المشاهدات',    format_number(data.get('views', 0))),
                ('نص التغريدة',  data.get('text', '')),
                ('المصدر',       data.get('data_source', '')),
            ]

        for label, value in fields:
            if value:
                add_rtl_paragraph(f"{label}: {value}", size=11)

        doc.add_paragraph()

        if report_text:
            add_rtl_paragraph("تقرير التحليل الاستخباراتي", bold=True, size=14, color=(88, 166, 255))
            for line in report_text.split('\n'):
                if line.strip():
                    add_rtl_paragraph(line.strip(), size=11)

        add_rtl_paragraph("─" * 50, size=9, color=(48, 54, 61))
        add_rtl_paragraph("أُنتج بواسطة محلل حسابات X الاستخباراتي | Gemini AI", size=9, color=(139, 148, 158))

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ في إنشاء ملف Word: {e}")
        return b''


# ─── تصدير PowerPoint ─────────────────────────────────────────

def export_to_pptx(title: str, data: dict, report_text: str, export_type: str = 'account') -> bytes:
    """تصدير التقرير إلى ملف PowerPoint"""
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        DARK_BG   = RGBColor(0x0d, 0x11, 0x17)
        BLUE      = RGBColor(0x1f, 0x6f, 0xeb)
        LIGHT_TXT = RGBColor(0xe6, 0xed, 0xf3)
        GRAY_TXT  = RGBColor(0x8b, 0x94, 0x9e)
        ACCENT    = RGBColor(0x58, 0xa6, 0xff)

        blank_layout = prs.slide_layouts[6]  # Blank

        def add_slide():
            sl = prs.slides.add_slide(blank_layout)
            bg = sl.background
            fill = bg.fill
            fill.solid()
            fill.fore_color.rgb = DARK_BG
            return sl

        def add_textbox(sl, text, left, top, width, height,
                        font_size=18, bold=False, color=None, align=PP_ALIGN.RIGHT):
            txb = sl.shapes.add_textbox(
                Inches(left), Inches(top), Inches(width), Inches(height)
            )
            tf = txb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = str(text) if text else ''
            run.font.size = Pt(font_size)
            run.font.bold = bold
            run.font.color.rgb = color if color else LIGHT_TXT
            return txb

        def add_rect(sl, left, top, width, height, color):
            shape = sl.shapes.add_shape(
                1,  # MSO_SHAPE_TYPE.RECTANGLE
                Inches(left), Inches(top), Inches(width), Inches(height)
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
            shape.line.fill.background()
            return shape

        # ── شريحة الغلاف ──────────────────────────────────────
        sl1 = add_slide()
        add_rect(sl1, 0, 0, 13.33, 0.08, BLUE)
        add_textbox(sl1, title, 0.5, 1.5, 12.33, 2,
                    font_size=36, bold=True, color=LIGHT_TXT, align=PP_ALIGN.CENTER)
        add_textbox(sl1, "محلل حسابات X الاستخباراتي", 0.5, 3.2, 12.33, 0.8,
                    font_size=18, color=GRAY_TXT, align=PP_ALIGN.CENTER)
        now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
        add_textbox(sl1, f"تاريخ التقرير: {now_str}", 0.5, 4.2, 12.33, 0.6,
                    font_size=14, color=GRAY_TXT, align=PP_ALIGN.CENTER)
        add_rect(sl1, 0, 7.42, 13.33, 0.08, BLUE)

        # ── شريحة بيانات الحساب / التغريدة ────────────────────
        sl2 = add_slide()
        if export_type == 'account':
            add_textbox(sl2, "بيانات الحساب", 0.5, 0.3, 12, 0.7,
                        font_size=24, bold=True, color=ACCENT)
            fields = [
                ('الاسم',        data.get('name', '')),
                ('المعرّف',      '@' + data.get('screen_name', '')),
                ('المتابِعون',   format_number(data.get('followers', 0))),
                ('يتابع',        format_number(data.get('following', 0))),
                ('التغريدات',    format_number(data.get('tweets', 0))),
                ('الموقع',       data.get('location', '')),
                ('الوصف',        data.get('bio', '')),
            ]
        else:
            add_textbox(sl2, "بيانات التغريدة", 0.5, 0.3, 12, 0.7,
                        font_size=24, bold=True, color=ACCENT)
            fields = [
                ('المؤلف',       data.get('author_name', '')),
                ('المعرّف',      '@' + data.get('author_handle', '')),
                ('التاريخ',      data.get('date', '')),
                ('الإعجابات',    format_number(data.get('likes', 0))),
                ('الإعادات',     format_number(data.get('retweets', 0))),
                ('الردود',       format_number(data.get('replies', 0))),
                ('نص التغريدة',  data.get('text', '')[:200]),
            ]

        y_pos = 1.1
        for label, value in fields:
            if value:
                add_textbox(sl2, f"{label}:  {value}", 0.5, y_pos, 12, 0.5,
                            font_size=16, color=LIGHT_TXT)
                y_pos += 0.55
                if y_pos > 6.8:
                    break

        # ── شرائح التقرير ─────────────────────────────────────
        if report_text:
            lines = [l.strip() for l in report_text.split('\n') if l.strip()]
            lines_per_slide = 10
            chunks = [lines[i:i+lines_per_slide] for i in range(0, len(lines), lines_per_slide)]

            for idx, chunk in enumerate(chunks):
                sl = add_slide()
                slide_title = "تقرير التحليل الاستخباراتي"
                if len(chunks) > 1:
                    slide_title += f" ({idx + 1}/{len(chunks)})"
                add_textbox(sl, slide_title, 0.5, 0.2, 12, 0.7,
                            font_size=22, bold=True, color=ACCENT)
                add_rect(sl, 0.5, 0.95, 12, 0.04, BLUE)

                y = 1.1
                for line in chunk:
                    add_textbox(sl, line, 0.5, y, 12, 0.55, font_size=14, color=LIGHT_TXT)
                    y += 0.58
                    if y > 6.8:
                        break

        # ── شريحة الخاتمة ─────────────────────────────────────
        sl_end = add_slide()
        add_rect(sl_end, 0, 0, 13.33, 0.08, BLUE)
        add_textbox(sl_end, "انتهى التقرير", 0.5, 2.5, 12.33, 1.5,
                    font_size=32, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
        add_textbox(sl_end, "محلل حسابات X الاستخباراتي | Gemini AI",
                    0.5, 4.0, 12.33, 0.6, font_size=14, color=GRAY_TXT, align=PP_ALIGN.CENTER)
        add_rect(sl_end, 0, 7.42, 13.33, 0.08, BLUE)

        buf = BytesIO()
        prs.save(buf)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ في إنشاء ملف PowerPoint: {e}")
        return b''


# ─── أزرار التصدير ────────────────────────────────────────────

def render_export_buttons(title: str, data: dict, report_text: str, export_type: str = 'account'):
    """عرض أزرار تصدير Word و PowerPoint و TXT"""
    if not report_text and not data:
        return

    st.markdown('<div class="section-title">📥 تصدير التقرير</div>', unsafe_allow_html=True)
    st.markdown('<div class="export-section">', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    safe_title = re.sub(r'[^\w\s-]', '', title)[:30].strip().replace(' ', '_')
    timestamp  = datetime.now().strftime('%Y%m%d_%H%M')
    filename_base = f"X_Report_{safe_title}_{timestamp}"

    with col1:
        docx_bytes = export_to_word(title, data, report_text, export_type)
        if docx_bytes:
            st.download_button(
                label="📄 تحميل Word",
                data=docx_bytes,
                file_name=f"{filename_base}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"docx_{timestamp}",
            )

    with col2:
        pptx_bytes = export_to_pptx(title, data, report_text, export_type)
        if pptx_bytes:
            st.download_button(
                label="📊 تحميل PowerPoint",
                data=pptx_bytes,
                file_name=f"{filename_base}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key=f"pptx_{timestamp}",
            )

    with col3:
        if report_text:
            st.download_button(
                label="📝 تحميل TXT",
                data=report_text.encode('utf-8'),
                file_name=f"{filename_base}.txt",
                mime="text/plain",
                key=f"txt_{timestamp}",
            )

    st.markdown('</div>', unsafe_allow_html=True)


# ─── بطاقة الملف الشخصي ──────────────────────────────────────

def render_profile_card(data: dict, featured_b64: str = None):
    """عرض بطاقة بيانات حساب X"""
    name      = escape_html(data.get('name', 'غير متاح'))
    handle    = escape_html(data.get('screen_name', ''))
    bio_html  = safe_html_lines(data.get('bio', ''))
    followers = format_number(data.get('followers', 0))
    following = format_number(data.get('following', 0))
    tweets    = format_number(data.get('tweets', 0))
    location  = escape_html(data.get('location', ''))
    joined    = escape_html(data.get('joined', ''))
    source    = escape_html(data.get('source', ''))

    # صورة البروفايل
    if featured_b64:
        img_html = f'<img src="data:image/jpeg;base64,{featured_b64}" class="profile-img" alt="صورة الملف الشخصي">'
    elif data.get('profile_image_b64'):
        b64 = data['profile_image_b64']
        img_html = f'<img src="data:image/jpeg;base64,{b64}" class="profile-img" alt="صورة الملف الشخصي">'
    else:
        img_html = '<div class="profile-img-placeholder">👤</div>'

    # بناء عناصر meta بدون backslash في f-string
    loc_span  = f'<span>📍 {location}</span>' if location else ''
    join_span = f'<span>📅 انضم: {joined}</span>' if joined else ''
    src_span  = f'<span>🔗 المصدر: {source}</span>'

    card = f"""
    <div class="profile-card">
        <div class="profile-header">
            {img_html}
            <div class="profile-info">
                <h2 class="profile-name">{name}</h2>
                <p class="profile-handle">@{handle}</p>
                <p class="profile-bio">{bio_html}</p>
            </div>
        </div>
        <div class="profile-stats">
            <div class="stat-box">
                <div class="stat-value">{followers}</div>
                <div class="stat-label">متابِع</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{following}</div>
                <div class="stat-label">يتابع</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{tweets}</div>
                <div class="stat-label">تغريدة</div>
            </div>
        </div>
        <div class="profile-meta">
            {loc_span}{join_span}{src_span}
        </div>
    </div>
    """
    st.markdown(card, unsafe_allow_html=True)


# ─── تبويب تحليل الحساب ───────────────────────────────────────

def account_tab(gemini_key: str, gemini_model_name: str):
    st.markdown('<div class="section-title">👤 تحليل حساب X</div>', unsafe_allow_html=True)

    # رفع صورة الحساب
    uploaded = st.file_uploader(
        "📸 ارفع صورة الملف الشخصي أو البانر (اختياري)",
        type=['jpg', 'jpeg', 'png', 'webp'],
        key='account_img'
    )
    featured_b64 = None
    if uploaded:
        try:
            img = Image.open(uploaded)
            featured_b64 = pil_to_base64(img)
            col_img, _ = st.columns([1, 3])
            with col_img:
                st.image(uploaded, caption="الصورة المرفوعة", use_container_width=True)
        except Exception as e:
            st.error(f"❌ خطأ في تحميل الصورة: {e}")

    # إدخال اسم المستخدم
    st.markdown('<div class="section-title">🔍 جلب بيانات الحساب</div>', unsafe_allow_html=True)
    user_input = st.text_input(
        "اسم المستخدم أو الرابط",
        placeholder="مثال: elonmusk أو https://x.com/elonmusk",
        key='account_username'
    )

    col_fetch, col_clear = st.columns([3, 1])
    with col_fetch:
        fetch_btn = st.button("🔍 جلب بيانات الحساب", key='fetch_account')
    with col_clear:
        clear_btn = st.button("🗑️ مسح", key='clear_account')

    if clear_btn:
        for key in ['account_data', 'account_report']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    if fetch_btn and user_input:
        username = extract_username(user_input)
        if not username:
            st.markdown(
                '<div class="error-box">❌ لم أتمكن من استخراج اسم المستخدم. '
                'تأكد من الإدخال (مثال: elonmusk)</div>',
                unsafe_allow_html=True
            )
        else:
            with st.spinner(f"🔄 جاري جلب بيانات @{username} من Nitter..."):
                debug_mode = st.session_state.get('debug_mode', False)
                data = fetch_nitter(username, debug=debug_mode)
                st.session_state['account_data'] = data

    # عرض البيانات
    if 'account_data' in st.session_state:
        data = st.session_state['account_data']

        if 'error' in data and not data.get('name'):
            err_msg = escape_html(data.get('error', 'خطأ غير محدد'))
            st.markdown(f'<div class="error-box">❌ {err_msg}</div>', unsafe_allow_html=True)

            # إدخال يدوي
            st.markdown('<div class="section-title">✏️ إدخال يدوي</div>', unsafe_allow_html=True)
            with st.expander("📝 أدخل البيانات يدوياً"):
                c1, c2 = st.columns(2)
                with c1:
                    manual_name = st.text_input("الاسم الكامل", key='m_name')
                    manual_handle = st.text_input("اسم المستخدم (@)", key='m_handle')
                    manual_followers = st.text_input("المتابِعون", key='m_followers')
                    manual_following = st.text_input("يتابع", key='m_following')
                with c2:
                    manual_tweets   = st.text_input("عدد التغريدات", key='m_tweets')
                    manual_location = st.text_input("الموقع", key='m_loc')
                    manual_joined   = st.text_input("تاريخ الانضمام", key='m_joined')
                    manual_bio = st.text_area("الوصف", key='m_bio', height=80)

                if st.button("💾 حفظ البيانات اليدوية", key='save_manual'):
                    st.session_state['account_data'] = {
                        'name':        manual_name,
                        'screen_name': manual_handle.lstrip('@'),
                        'followers':   manual_followers,
                        'following':   manual_following,
                        'tweets':      manual_tweets,
                        'location':    manual_location,
                        'joined':      manual_joined,
                        'bio':         manual_bio,
                        'source':      'إدخال يدوي',
                    }
                    st.rerun()
        else:
            src_msg = escape_html(data.get('source', ''))
            st.markdown(f'<div class="success-box">✅ تم جلب البيانات من: {src_msg}</div>', unsafe_allow_html=True)
            render_profile_card(data, featured_b64)

            # توليد تقرير Gemini
            st.markdown('<div class="section-title">🤖 تحليل استخباراتي بالذكاء الاصطناعي</div>', unsafe_allow_html=True)
            if not gemini_key:
                st.markdown(
                    '<div class="warning-box">⚠️ أدخل مفتاح Gemini API في الشريط الجانبي لتفعيل التحليل</div>',
                    unsafe_allow_html=True
                )
            else:
                if st.button("🚀 توليد التقرير الاستخباراتي", key='gen_account_report'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if not model:
                        st.error("❌ فشل تهيئة نموذج Gemini")
                    else:
                        name_val     = data.get('name', '')
                        handle_val   = data.get('screen_name', '')
                        bio_val      = data.get('bio', '')
                        followers_v  = format_number(data.get('followers', 0))
                        following_v  = format_number(data.get('following', 0))
                        tweets_v     = format_number(data.get('tweets', 0))
                        location_v   = data.get('location', '')
                        joined_v     = data.get('joined', '')

                        prompt = f"""أنت محلل استخباراتي متخصص في تحليل حسابات منصة X (تويتر).
قم بتحليل الحساب التالي وتقديم تقرير استخباراتي شامل باللغة العربية:

**بيانات الحساب:**
- الاسم: {name_val}
- المعرّف: @{handle_val}
- الوصف: {bio_val}
- المتابِعون: {followers_v}
- يتابع: {following_v}
- التغريدات: {tweets_v}
- الموقع: {location_v}
- تاريخ الانضمام: {joined_v}

**يرجى تقديم تقرير يشمل:**

## 1. ملخص الهوية
تحليل الاسم والمعرّف وتاريخ الانضمام ومؤشرات الهوية الحقيقية.

## 2. تحليل النشاط والتأثير
نسبة المتابِعين/المتابَعين، مستوى التفاعل، طبيعة الحساب.

## 3. المؤشرات الجغرافية والثقافية
الموقع المُعلَن، اللغة، المؤشرات الثقافية في الوصف.

## 4. تقييم مصداقية الحساب
هل يبدو حقيقياً أم حساب بوت أو مزيف؟ المؤشرات الداعمة.

## 5. المخاطر والملاحظات الاستخباراتية
أي مؤشرات مثيرة للاهتمام أو تستوجب متابعة.

## 6. التوصيات
خطوات استقصائية مقترحة لمزيد من التحقق.

قدّم التقرير بشكل احترافي ومفصّل باللغة العربية."""

                        with st.spinner("🤖 جاري تحليل الحساب بالذكاء الاصطناعي..."):
                            images = []
                            if featured_b64:
                                images.append(featured_b64)
                            if images:
                                report = gemini_with_images(model, prompt, images)
                            else:
                                report = gemini_text(model, prompt)
                            st.session_state['account_report'] = report

            # عرض التقرير
            if 'account_report' in st.session_state:
                report = st.session_state['account_report']
                report_html = safe_html_lines(report)
                st.markdown(
                    f'<div class="report-section" dir="rtl">{report_html}</div>',
                    unsafe_allow_html=True
                )
                render_export_buttons(
                    title=f"تقرير حساب @{data.get('screen_name', 'unknown')}",
                    data=data,
                    report_text=report,
                    export_type='account'
                )


# ─── تبويب تحليل التغريدة ─────────────────────────────────────

def tweet_tab(gemini_key: str, gemini_model_name: str):
    st.markdown('<div class="section-title">🐦 تحليل تغريدة</div>', unsafe_allow_html=True)

    tweet_input = st.text_input(
        "رابط أو معرّف التغريدة",
        placeholder="مثال: https://x.com/user/status/1234567890123456789",
        key='tweet_url_input'
    )

    col_ft, col_fc = st.columns([3, 1])
    with col_ft:
        fetch_tweet_btn = st.button("🔍 جلب بيانات التغريدة", key='fetch_tweet')
    with col_fc:
        clear_tweet_btn = st.button("🗑️ مسح", key='clear_tweet')

    if clear_tweet_btn:
        for k in ['tweet_data', 'tweet_report']:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    if fetch_tweet_btn and tweet_input:
        # فحص إذا كان رابط حساب وليس تغريدة
        if re.search(r'(?:twitter|x)\.com/[A-Za-z0-9_]+$', tweet_input):
            st.markdown(
                '<div class="warning-box">⚠️ هذا رابط <b>حساب</b> وليس تغريدة!<br>'
                'انتقل إلى تبويب <b>👤 تحليل حساب X</b> لتحليل هذا الحساب،<br>'
                'أو أدخل رابط تغريدة يحتوي على <b>/status/</b></div>',
                unsafe_allow_html=True
            )
        else:
            tid = extract_tweet_id(tweet_input)
            if not tid:
                st.markdown(
                    '<div class="error-box">❌ لم أتمكن من استخراج معرّف التغريدة.<br>'
                    'تأكد أن الرابط يحتوي على /status/</div>',
                    unsafe_allow_html=True
                )
            else:
                with st.spinner("🔄 جاري جلب بيانات التغريدة..."):
                    tdata = fetch_fxtwitter(tid)
                    st.session_state['tweet_data'] = tdata

    # عرض بيانات التغريدة
    if 'tweet_data' in st.session_state:
        td = st.session_state['tweet_data']

        if 'error' in td:
            err_msg = escape_html(td['error'])
            st.markdown(f'<div class="error-box">❌ فشل جلب التغريدة: {err_msg}</div>', unsafe_allow_html=True)

            # إدخال يدوي
            st.markdown('<div class="section-title">✏️ إدخال يدوي للتغريدة</div>', unsafe_allow_html=True)
            with st.expander("📝 أدخل بيانات التغريدة يدوياً"):
                manual_text    = st.text_area("نص التغريدة", key='mt_text', height=120)
                mc1, mc2 = st.columns(2)
                with mc1:
                    manual_author  = st.text_input("اسم المؤلف", key='mt_author')
                    manual_handle2 = st.text_input("معرّف المؤلف (@)", key='mt_handle')
                    manual_date    = st.text_input("التاريخ", key='mt_date')
                with mc2:
                    manual_likes   = st.text_input("الإعجابات", key='mt_likes')
                    manual_rt      = st.text_input("الإعادات", key='mt_rt')
                    manual_replies = st.text_input("الردود", key='mt_replies')

                if st.button("💾 حفظ بيانات التغريدة", key='save_tweet_manual'):
                    st.session_state['tweet_data'] = {
                        'text':         manual_text,
                        'author_name':  manual_author,
                        'author_handle': manual_handle2.lstrip('@'),
                        'date':         manual_date,
                        'likes':        manual_likes,
                        'retweets':     manual_rt,
                        'replies':      manual_replies,
                        'views':        0,
                        'media_urls':   [],
                        'data_source':  'إدخال يدوي',
                    }
                    st.rerun()
        else:
            # عرض بيانات التغريدة
            src_name = escape_html(td.get('data_source', 'FxTwitter'))
            st.markdown(f'<div class="success-box">✅ تم جلب التغريدة من: {src_name}</div>', unsafe_allow_html=True)

            # بطاقة التغريدة
            tweet_text_html = safe_html_lines(td.get('text', ''))
            author_name  = escape_html(td.get('author_name', ''))
            author_handle = escape_html(td.get('author_handle', ''))
            date_val     = escape_html(td.get('date', ''))
            likes_val    = format_number(td.get('likes', 0))
            rt_val       = format_number(td.get('retweets', 0))
            rep_val      = format_number(td.get('replies', 0))
            views_val    = format_number(td.get('views', 0))
            lang_val     = escape_html(td.get('lang', ''))

            st.markdown(f"""
            <div class="tweet-card">
                <div style="margin-bottom:12px; direction:rtl; text-align:right;">
                    <strong style="color:#e6edf3; font-size:1.1rem;">{author_name}</strong>
                    <span style="color:#8b949e; margin-right:8px;">@{author_handle}</span>
                    <span style="color:#8b949e; font-size:0.85rem; float:left;">{date_val}</span>
                </div>
                <div class="tweet-text">{tweet_text_html}</div>
                <div class="tweet-stats">
                    <div class="tweet-stat">❤️ <span>{likes_val}</span></div>
                    <div class="tweet-stat">🔁 <span>{rt_val}</span></div>
                    <div class="tweet-stat">💬 <span>{rep_val}</span></div>
                    <div class="tweet-stat">👁️ <span>{views_val}</span></div>
                    {'<div class="tweet-stat">🌐 ' + lang_val + '</div>' if lang_val else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # عرض صور التغريدة
            media_urls = td.get('media_urls', [])
            if media_urls:
                st.markdown('<div class="section-title">🖼️ صور التغريدة</div>', unsafe_allow_html=True)
                cols = st.columns(min(len(media_urls), 3))
                for i, murl in enumerate(media_urls[:3]):
                    with cols[i]:
                        try:
                            st.image(murl, use_container_width=True)
                        except Exception:
                            pass

            # رفع صور للتحليل
            st.markdown('<div class="section-title">🔬 تحليل صور بالذكاء الاصطناعي</div>', unsafe_allow_html=True)
            uploaded_imgs = st.file_uploader(
                "ارفع صور للتحليل (يمكن رفع أكثر من صورة)",
                type=['jpg', 'jpeg', 'png', 'webp'],
                accept_multiple_files=True,
                key='tweet_images'
            )

            analysis_point = st.selectbox(
                "نقطة التحليل",
                IMAGE_ANALYSIS_POINTS,
                key='analysis_point_select'
            )

            if uploaded_imgs and gemini_key:
                if st.button("🔬 تحليل الصور", key='analyze_images'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        images_b64 = []
                        for uf in uploaded_imgs[:4]:
                            try:
                                img = Image.open(uf)
                                images_b64.append(pil_to_base64(img))
                            except Exception:
                                pass

                        if images_b64:
                            point_prompt = f"""أنت خبير في التحليل البصري والاستخباراتي.

قم بـ: **{analysis_point}**

تعليمات:
- قدّم تحليلاً دقيقاً ومفصّلاً
- اذكر كل التفاصيل الملاحظة
- كن موضوعياً وعلمياً
- اكتب باللغة العربية
- إذا لم تتمكن من التحديد بدقة، اذكر الاحتمالات المتاحة"""
                            with st.spinner("🤖 جاري تحليل الصور..."):
                                img_result = gemini_with_images(model, point_prompt, images_b64)
                                result_html = safe_html_lines(img_result)
                                st.markdown(
                                    f'<div class="report-section" dir="rtl">{result_html}</div>',
                                    unsafe_allow_html=True
                                )

            # تحليل نص التغريدة
            st.markdown('<div class="section-title">🤖 تحليل نص التغريدة</div>', unsafe_allow_html=True)
            if not gemini_key:
                st.markdown(
                    '<div class="warning-box">⚠️ أدخل مفتاح Gemini API في الشريط الجانبي</div>',
                    unsafe_allow_html=True
                )
            else:
                if st.button("📊 تحليل نص التغريدة", key='analyze_tweet_text'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        tweet_text_raw = td.get('text', '')
                        author_n  = td.get('author_name', '')
                        author_h  = td.get('author_handle', '')
                        date_raw  = td.get('date', '')
                        likes_raw = td.get('likes', 0)
                        rt_raw    = td.get('retweets', 0)

                        prompt = f"""أنت محلل استخباراتي متخصص في تحليل منشورات وسائل التواصل الاجتماعي.

حلّل التغريدة التالية وقدّم تقريراً استخباراتياً شاملاً باللغة العربية:

**بيانات التغريدة:**
- النص: {tweet_text_raw}
- المؤلف: {author_n} (@{author_h})
- التاريخ: {date_raw}
- الإعجابات: {likes_raw}
- الإعادات: {rt_raw}

**يرجى التحليل وفق النقاط التالية:**

## 1. تحليل المحتوى والرسالة
ما الرسالة الأساسية؟ هل هي موضوعية أم تحريضية أم دعائية؟

## 2. تحليل اللغة والأسلوب
المشاعر، الكلمات المفتاحية، مؤشرات الكذب أو المبالغة.

## 3. السياق والتوقيت
أهمية توقيت النشر، الأحداث المرتبطة المحتملة.

## 4. التأثير والانتشار
تقييم مستوى التفاعل ومدى انتشار المحتوى.

## 5. مصداقية الحساب
تقييم سريع لمصداقية الحساب الناشر.

## 6. التوصيات الاستخباراتية
هل تستحق هذه التغريدة متابعة؟ ما الخطوات المقترحة؟

قدّم التقرير بشكل احترافي باللغة العربية."""

                        with st.spinner("🤖 جاري تحليل التغريدة..."):
                            report = gemini_text(model, prompt)
                            st.session_state['tweet_report'] = report

            if 'tweet_report' in st.session_state:
                t_report = st.session_state['tweet_report']
                t_report_html = safe_html_lines(t_report)
                st.markdown(
                    f'<div class="report-section" dir="rtl">{t_report_html}</div>',
                    unsafe_allow_html=True
                )
                render_export_buttons(
                    title=f"تحليل تغريدة @{td.get('author_handle', 'unknown')}",
                    data=td,
                    report_text=t_report,
                    export_type='tweet'
                )


# ─── الشريط الجانبي ───────────────────────────────────────────

def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:16px 0;">
            <div style="font-size:2.5rem;">🔍</div>
            <h2 style="color:#58a6ff; margin:8px 0; font-size:1.3rem;">محلل حسابات X</h2>
            <p style="color:#8b949e; font-size:0.85rem;">v9.8 | Gemini 2.5</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🔑 إعدادات Gemini AI")

        gemini_key = st.text_input(
            "مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            key='gemini_api_key',
            help="احصل على مفتاحك من: https://aistudio.google.com/apikey"
        )

        model_options = {
            "gemini-2.5-flash":                  "⚡ Gemini 2.5 Flash (الأسرع – مُوصى به)",
            "gemini-2.5-flash-lite-preview-06-17": "🪶 Gemini 2.5 Flash Lite (الأخف)",
            "gemini-2.5-pro":                    "💎 Gemini 2.5 Pro (الأقوى)",
        }

        selected_model = st.selectbox(
            "نموذج Gemini",
            options=list(model_options.keys()),
            format_func=lambda x: model_options[x],
            key='gemini_model'
        )

        if gemini_key:
            st.markdown('<div class="success-box">✅ مفتاح Gemini جاهز</div>', unsafe_allow_html=True)
        else:
            link_url = "https://aistudio.google.com/apikey"
            st.markdown(
                f'<div class="info-box">ℹ️ أدخل مفتاح API للتفعيل<br>'
                f'<a href="{link_url}" target="_blank" style="color:#58a6ff;">احصل على مفتاح مجاني</a></div>',
                unsafe_allow_html=True
            )

        st.markdown("---")
        st.markdown("### 📡 المصادر النشطة")
        st.markdown("""
        <div style="direction:rtl; text-align:right;">
        ✅ <strong>Nitter</strong> – جلب بيانات الحسابات<br>
        ✅ <strong>FxTwitter API</strong> – جلب التغريدات<br>
        ✅ <strong>Gemini 2.5</strong> – التحليل الذكي<br>
        ✅ <strong>Word/PPTX</strong> – تصدير التقارير<br>
        ⚠️ <em>twikit معطّل مؤقتاً (خطأ KEY_BYTE)</em>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        debug_mode = st.checkbox("🐛 وضع التشخيص", key='debug_mode', value=False)

        st.markdown("---")
        st.markdown("""
        <div style="text-align:center; color:#8b949e; font-size:0.8rem;">
            محلل حسابات X الاستخباراتي<br>
            v9.8 | 2025
        </div>
        """, unsafe_allow_html=True)

    return gemini_key, selected_model


# ─── الدالة الرئيسية ──────────────────────────────────────────

def main():
    st.markdown("""
    <div style="text-align:center; padding:20px 0 10px; direction:rtl;">
        <h1 style="color:#58a6ff; font-size:2rem; margin:0;">
            🔍 محلل حسابات X الاستخباراتي
        </h1>
        <p style="color:#8b949e; font-size:1rem; margin:8px 0 0;">
            تحليل متقدم للحسابات والتغريدات باستخدام الذكاء الاصطناعي Gemini 2.5
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
