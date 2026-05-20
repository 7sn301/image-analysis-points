# ============================================================
#  محلل حسابات X الاستخباراتي – v10.0
#  إضافة: تحليل الصور يُصدَّر في Word و PowerPoint
# ============================================================

import streamlit as st
import requests
import re
import base64
import html
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
.stTextArea>div>div>textarea {
    background-color: #161b22 !important; color: #e6edf3 !important;
    border: 1px solid #30363d !important; border-radius: 8px !important;
    direction: rtl !important; text-align: right !important;
}
.stButton>button {
    background: linear-gradient(135deg,#1f6feb,#388bfd);
    color:white !important; border:none !important; border-radius:8px !important;
    padding:.5rem 1.5rem !important; font-weight:700 !important; width:100%;
}
.stButton>button:hover { background: linear-gradient(135deg,#388bfd,#58a6ff) !important; }
.stDownloadButton>button {
    background: linear-gradient(135deg,#238636,#2ea043) !important;
    color:white !important; border:none !important; border-radius:8px !important;
    font-weight:700 !important; width:100%;
}
.profile-card {
    background:linear-gradient(135deg,#161b22,#1c2128);
    border:1px solid #30363d; border-radius:16px; padding:24px; margin:16px 0;
}
.profile-header { display:flex; gap:20px; align-items:flex-start; flex-direction:row-reverse; }
.profile-img { width:100px; height:100px; border-radius:50%; border:3px solid #1f6feb; object-fit:cover; }
.profile-img-placeholder {
    width:100px; height:100px; border-radius:50%; background:#21262d;
    display:flex; align-items:center; justify-content:center; font-size:48px;
}
.profile-name  { color:#e6edf3; font-size:1.4rem; font-weight:700; margin:0; }
.profile-handle { color:#8b949e; font-size:1rem; margin:4px 0; }
.profile-bio   { color:#c9d1d9; font-size:.95rem; margin:8px 0; line-height:1.6; }
.profile-stats { display:flex; gap:16px; margin:16px 0; flex-direction:row-reverse; flex-wrap:wrap; }
.stat-box { background:#21262d; border-radius:10px; padding:12px 20px; text-align:center; flex:1; min-width:80px; }
.stat-value { font-size:1.3rem; font-weight:700; color:#58a6ff; }
.stat-label { font-size:.8rem; color:#8b949e; margin-top:4px; }
.profile-meta { display:flex; gap:16px; flex-wrap:wrap; color:#8b949e; font-size:.9rem; flex-direction:row-reverse; }
.report-section {
    background:#161b22; border:1px solid #30363d; border-radius:12px;
    padding:20px; margin:16px 0; direction:rtl; text-align:right;
    line-height:1.8; white-space:pre-wrap; color:#e6edf3;
}
.img-analysis-section {
    background:#0c2d6b; border:1px solid #1f6feb; border-radius:12px;
    padding:20px; margin:16px 0; direction:rtl; text-align:right;
    line-height:1.8; white-space:pre-wrap; color:#e6edf3;
}
.tweet-card { background:#161b22; border:1px solid #30363d; border-radius:12px; padding:20px; margin:16px 0; }
.tweet-text { font-size:1.1rem; line-height:1.8; color:#e6edf3; direction:rtl; text-align:right; }
.tweet-stats { display:flex; gap:20px; margin-top:12px; color:#8b949e; flex-direction:row-reverse; flex-wrap:wrap; }
.tweet-stat  { display:flex; align-items:center; gap:6px; }
.info-box    { background:#0c2d6b; border:1px solid #1f6feb; border-radius:8px; padding:12px 16px; margin:8px 0; color:#79c0ff; }
.success-box { background:#0a3d1f; border:1px solid #238636; border-radius:8px; padding:12px 16px; margin:8px 0; color:#56d364; }
.warning-box { background:#2d1f00; border:1px solid #d29922; border-radius:8px; padding:12px 16px; margin:8px 0; color:#f0883e; }
.error-box   { background:#3d0a0a; border:1px solid #da3633; border-radius:8px; padding:12px 16px; margin:8px 0; color:#ff7b72; }
.section-title {
    font-size:1.2rem; font-weight:700; color:#58a6ff;
    border-bottom:2px solid #1f6feb; padding-bottom:8px;
    margin:20px 0 12px; direction:rtl; text-align:right;
}
.export-section { background:#161b22; border:1px solid #30363d; border-radius:12px; padding:16px; margin:16px 0; }
</style>
""", unsafe_allow_html=True)

# ─── الثوابت ──────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
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

GEMINI_MODELS = {
    "gemini-2.5-flash":                    "⚡ Gemini 2.5 Flash (الأسرع – مُوصى به)",
    "gemini-2.5-flash-lite-preview-06-17": "🪶 Gemini 2.5 Flash Lite (الأخف)",
    "gemini-2.5-pro":                      "💎 Gemini 2.5 Pro (الأقوى)",
}

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

def safe_text(v) -> str:
    return '' if v is None else str(v).strip()

def escape_html(v) -> str:
    return html.escape(safe_text(v))

def nl_to_br(t: str) -> str:
    return t.replace('\n', '<br>') if t else ''

def safe_html_lines(t: str) -> str:
    return nl_to_br(escape_html(t))

def extract_username(raw: str) -> str:
    raw = raw.strip().lstrip('@')
    for p in [r'(?:twitter|x)\.com/([A-Za-z0-9_]+)',
               r'nitter\.[^/]+/([A-Za-z0-9_]+)']:
        m = re.search(p, raw)
        if m:
            return m.group(1)
    return raw if re.match(r'^[A-Za-z0-9_]{1,50}$', raw) else ''

def extract_tweet_id(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r'/status/(\d+)', raw)
    if m:
        return m.group(1)
    return raw if raw.isdigit() else ''

def format_number(n) -> str:
    try:
        n = int(n)
    except Exception:
        return safe_text(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)

def format_date(d: str) -> str:
    if not d:
        return ''
    try:
        return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y/%m/%d %H:%M")
    except Exception:
        return safe_text(d)

def pil_to_base64(img: Image.Image) -> str:
    if img.mode in ('RGBA', 'P', 'LA'):
        bg  = Image.new('RGB', img.size, (255, 255, 255))
        src = img.convert('RGBA') if img.mode == 'P' else img
        bg.paste(src, mask=src.split()[-1])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def url_to_base64(url: str) -> str:
    try:
        r = requests.get(url, headers={'User-Agent': USER_AGENTS[0]}, timeout=10)
        r.raise_for_status()
        return pil_to_base64(Image.open(BytesIO(r.content)))
    except Exception:
        return ''

def b64_to_bytes(b64: str) -> bytes:
    try:
        return base64.b64decode(b64)
    except Exception:
        return b''

# ─── Nitter ───────────────────────────────────────────────────

def fetch_nitter(username: str, debug: bool = False) -> dict:
    headers  = {'User-Agent': USER_AGENTS[0], 'Accept-Language': 'ar,en;q=0.9'}
    last_err = ''
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"; continue
            cl = r.text.lower()
            if any(k in cl for k in ['captcha','cloudflare','enable javascript','ddos-guard']):
                last_err = "صفحة حماية"; continue
            soup = BeautifulSoup(r.text, 'html.parser')
            data = {'source': f'Nitter ({mirror})', 'username': username}
            ne = soup.select_one('.profile-card-fullname,.fullname,h1.profile-name')
            data['name'] = ne.get_text(strip=True) if ne else username
            he = soup.select_one('.profile-card-username,.username,.profile-handle')
            data['screen_name'] = he.get_text(strip=True).lstrip('@') if he else username
            be = soup.select_one('.profile-bio,.bio p,.profile-card-bio')
            data['bio'] = be.get_text(strip=True) if be else ''
            le = soup.select_one('.profile-location,.location')
            data['location'] = le.get_text(strip=True) if le else ''
            je = soup.select_one('.profile-joindate,.joindate')
            data['joined'] = je.get_text(strip=True) if je else ''
            stats  = soup.select('.profile-stat-num,.profile-stats .stat-num,.stats li .stat-num')
            labels = soup.select('.profile-stat-header,.profile-stats .stat-header,.stats li .stat-header')
            followers = following = tweets = 0
            for i, lel in enumerate(labels):
                lbl = lel.get_text(strip=True).lower()
                try:
                    val = int(stats[i].get_text(strip=True).replace(',','').replace('.',''))
                except Exception:
                    val = 0
                if 'follow' in lbl and 'ing' not in lbl: followers = val
                elif 'following' in lbl: following = val
                elif 'tweet' in lbl or 'post' in lbl: tweets = val
            if followers == 0:
                all_n = soup.select('.profile-stat-num')
                if len(all_n) >= 3:
                    try:
                        tweets    = int(all_n[0].get_text(strip=True).replace(',',''))
                        following = int(all_n[1].get_text(strip=True).replace(',',''))
                        followers = int(all_n[2].get_text(strip=True).replace(',',''))
                    except Exception: pass
            data.update({'followers':followers,'following':following,'tweets':tweets})
            ie = soup.select_one('.profile-card-avatar img,.avatar img,img.profile-pic')
            if ie and ie.get('src'):
                iurl = ie['src']
                if iurl.startswith('/'): iurl = mirror + iurl
                data['profile_image_url'] = iurl
                data['profile_image_b64']  = url_to_base64(iurl)
            else:
                data['profile_image_b64'] = ''
            if debug: st.write(f"✅ {mirror}")
            return data
        except requests.exceptions.Timeout:
            last_err = "انتهت المهلة"
        except Exception as e:
            last_err = str(e)
    return {'error': f'فشل جميع المرايا – {last_err}', 'source': 'Nitter'}

# ─── FxTwitter ───────────────────────────────────────────────

def fetch_fxtwitter(tweet_id: str) -> dict:
    try:
        r = requests.get(f"{FXTWITTER_API}/status/{tweet_id}", timeout=15)
        r.raise_for_status()
        raw   = r.json()
        tweet = raw.get('tweet', {})
        auth  = tweet.get('author', {})
        media_urls = []
        for p in tweet.get('media', {}).get('photos', []):
            media_urls.append(p.get('url', ''))
        for v in tweet.get('media', {}).get('videos', []):
            if v.get('thumbnail_url'):
                media_urls.append(v['thumbnail_url'])
        return {
            'id':             tweet.get('id', tweet_id),
            'text':           tweet.get('text', ''),
            'date':           format_date(tweet.get('created_at', '')),
            'likes':          tweet.get('likes', 0),
            'retweets':       tweet.get('retweets', 0),
            'replies':        tweet.get('replies', 0),
            'views':          tweet.get('views', 0),
            'bookmarks':      tweet.get('bookmarks', 0),
            'lang':           tweet.get('lang', ''),
            'url':            tweet.get('url', ''),
            'author_name':    auth.get('name', ''),
            'author_handle':  auth.get('screen_name', ''),
            'author_followers': auth.get('followers', 0),
            'author_bio':     auth.get('description', ''),
            'author_avatar':  auth.get('avatar_url', ''),
            'media_urls':     media_urls,
            'data_source':    'FxTwitter API',
        }
    except Exception as e:
        return {'error': str(e)}

# ─── Gemini ───────────────────────────────────────────────────

def get_gemini_model(api_key: str, model_name: str):
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except Exception:
        return None

def gemini_text(model, prompt: str) -> str:
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"❌ خطأ Gemini: {e}"

def gemini_with_images(model, prompt: str, images_b64: list) -> str:
    try:
        parts = [prompt]
        for b64 in images_b64:
            if b64:
                parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': b64}})
        return model.generate_content(parts).text
    except Exception as e:
        return f"❌ خطأ Gemini: {e}"

# ══════════════════════════════════════════════════════════════
#  تصدير Word  ── مع دعم الصور + تحليل الصور
# ══════════════════════════════════════════════════════════════

def export_to_word(
    title: str,
    data: dict,
    report_text: str,
    export_type: str = 'account',
    images_b64: list = None,
    image_analysis_text: str = '',     # ← تحليل الصورة بالذكاء الاصطناعي
) -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement

        doc = Document()
        sec = doc.sections[0]
        sec.page_width  = Inches(8.27)
        sec.page_height = Inches(11.69)
        sec.left_margin = sec.right_margin = Cm(2.5)

        # ── RTL على مستوى الوثيقة ──
        styles_el = doc.element.find(qn('w:styles'))
        if styles_el is not None:
            for style_el in styles_el.findall(qn('w:style')):
                pPr_s = style_el.find(qn('w:pPr'))
                if pPr_s is None:
                    pPr_s = OxmlElement('w:pPr')
                    style_el.append(pPr_s)
                pPr_s.append(OxmlElement('w:bidi'))
                jc = OxmlElement('w:jc')
                jc.set(qn('w:val'), 'right')
                pPr_s.append(jc)

        def force_rtl_para(para):
            pPr = para._p.get_or_add_pPr()
            for old in pPr.findall(qn('w:jc')):
                pPr.remove(old)
            jc = OxmlElement('w:jc')
            jc.set(qn('w:val'), 'right')
            pPr.append(jc)
            for old in pPr.findall(qn('w:bidi')):
                pPr.remove(old)
            pPr.append(OxmlElement('w:bidi'))
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        def force_rtl_run(run):
            rPr = run._r.get_or_add_rPr()
            for old in rPr.findall(qn('w:rtl')):
                rPr.remove(old)
            rPr.append(OxmlElement('w:rtl'))
            for old in rPr.findall(qn('w:cs')):
                rPr.remove(old)
            rPr.append(OxmlElement('w:cs'))

        def add_para(text, bold=False, size=12, color=None, italic=False):
            p   = doc.add_paragraph()
            force_rtl_para(p)
            run = p.add_run(str(text) if text else '')
            run.bold    = bold
            run.italic  = italic
            run.font.size = Pt(size)
            if color:
                run.font.color.rgb = RGBColor(*color)
            force_rtl_run(run)
            return p

        def add_heading(text, level=1):
            colors = {1:(31,111,235), 2:(88,166,255), 3:(86,211,100), 4:(240,136,62)}
            sizes  = {1:20, 2:15, 3:13, 4:12}
            add_para(text, bold=True,
                     size=sizes.get(level,13),
                     color=colors.get(level,(88,166,255)))

        def add_divider(ch='─', n=55):
            add_para(ch * n, size=9, color=(48,54,61))

        def add_colored_box_para(text, bg_color_hint='blue', size=11):
            """فقرة مُميّزة لتحليل الصورة"""
            add_para(text, size=size, color=(121,192,255))

        def insert_image_b64(b64, width_inches=3.0, caption=''):
            img_bytes = b64_to_bytes(b64)
            if not img_bytes: return
            try:
                img = Image.open(BytesIO(img_bytes))
                if img.mode != 'RGB': img = img.convert('RGB')
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=85)
                buf.seek(0)
                p = doc.add_paragraph()
                force_rtl_para(p)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(buf, width=Inches(width_inches))
                if caption:
                    cp = doc.add_paragraph()
                    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cr = cp.add_run(caption)
                    cr.font.size  = Pt(9)
                    cr.italic     = True
                    cr.font.color.rgb = RGBColor(139,148,158)
                    force_rtl_run(cr)
            except Exception as e:
                add_para(f"[تعذّر إدراج الصورة: {e}]", size=9, color=(200,100,100))

        def render_report_lines(text):
            """تصيير نص التقرير مع دعم العناوين"""
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped:
                    doc.add_paragraph()
                    continue
                if stripped.startswith('## '):
                    add_heading(stripped[3:], level=3)
                elif stripped.startswith('# '):
                    add_heading(stripped[2:], level=2)
                elif stripped.startswith('**') and stripped.endswith('**'):
                    add_para(stripped.strip('*'), bold=True, size=11)
                else:
                    add_para(stripped, size=11)

        # ══ بناء المستند ══

        add_heading(title, level=1)
        add_para(
            f"تاريخ التقرير: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
            size=10, color=(139,148,158), italic=True
        )
        add_divider()
        doc.add_paragraph()

        # الصور
        imgs = [i for i in (images_b64 or []) if i]
        if imgs:
            if export_type == 'account':
                add_heading("📸 صورة الملف الشخصي", level=2)
                insert_image_b64(imgs[0], 2.5, "صورة الحساب")
                for ex in imgs[1:]:
                    insert_image_b64(ex, 3.5, "صورة إضافية")
            else:
                add_heading("🖼️ صور التغريدة", level=2)
                for idx, ib in enumerate(imgs):
                    insert_image_b64(ib, 4.0, f"صورة {idx+1}")
            add_divider()
            doc.add_paragraph()

        # ══ قسم تحليل الصورة ══
        if image_analysis_text and image_analysis_text.strip():
            add_heading("🔬 تحليل الصورة بالذكاء الاصطناعي", level=2)
            add_divider('═', 55)
            render_report_lines(image_analysis_text)
            add_divider('═', 55)
            doc.add_paragraph()

        # البيانات
        if export_type == 'account':
            add_heading("👤 بيانات الحساب", level=2)
            fields = [
                ('الاسم الكامل',   data.get('name','')),
                ('المعرّف',        '@'+data.get('screen_name','')),
                ('المتابِعون',     format_number(data.get('followers',0))),
                ('يتابع',          format_number(data.get('following',0))),
                ('التغريدات',      format_number(data.get('tweets',0))),
                ('الموقع',         data.get('location','')),
                ('تاريخ الانضمام', data.get('joined','')),
                ('الوصف',          data.get('bio','')),
                ('المصدر',         data.get('source','')),
            ]
        else:
            add_heading("🐦 بيانات التغريدة", level=2)
            fields = [
                ('المؤلف',      data.get('author_name','')),
                ('المعرّف',     '@'+data.get('author_handle','')),
                ('التاريخ',     data.get('date','')),
                ('الإعجابات',   format_number(data.get('likes',0))),
                ('الإعادات',    format_number(data.get('retweets',0))),
                ('الردود',      format_number(data.get('replies',0))),
                ('المشاهدات',   format_number(data.get('views',0))),
                ('نص التغريدة', data.get('text','')),
                ('المصدر',      data.get('data_source','')),
            ]
        for label, value in fields:
            if value:
                add_para(f"{label}:  {value}", size=11)

        doc.add_paragraph()
        add_divider()

        # تقرير التحليل العام
        if report_text and report_text.strip():
            add_heading("📊 تقرير التحليل الاستخباراتي", level=2)
            doc.add_paragraph()
            render_report_lines(report_text)

        add_divider()
        add_para(
            "أُنتج بواسطة محلل حسابات X الاستخباراتي | Gemini AI | v10.0",
            size=9, color=(139,148,158), italic=True
        )

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ Word: {e}")
        return b''


# ══════════════════════════════════════════════════════════════
#  تصدير PowerPoint  ── مع دعم الصور + تحليل الصور
# ══════════════════════════════════════════════════════════════

def export_to_pptx(
    title: str,
    data: dict,
    report_text: str,
    export_type: str = 'account',
    images_b64: list = None,
    image_analysis_text: str = '',     # ← تحليل الصورة بالذكاء الاصطناعي
) -> bytes:
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.oxml.ns import qn
        from pptx.oxml import OxmlElement

        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        DARK    = RGBColor(0x0d,0x11,0x17)
        CARD    = RGBColor(0x16,0x1b,0x22)
        BLUE    = RGBColor(0x1f,0x6f,0xeb)
        ACCENT  = RGBColor(0x58,0xa6,0xff)
        WHITE   = RGBColor(0xe6,0xed,0xf3)
        GRAY    = RGBColor(0x8b,0x94,0x9e)
        GREEN   = RGBColor(0x56,0xd3,0x64)
        TEAL    = RGBColor(0x39,0xd3,0xd3)   # للتحليل البصري
        CARD_BLUE = RGBColor(0x0c,0x2d,0x6b) # خلفية تحليل الصورة

        blank = prs.slide_layouts[6]

        def new_slide():
            sl = prs.slides.add_slide(blank)
            sl.background.fill.solid()
            sl.background.fill.fore_color.rgb = DARK
            return sl

        def set_para_rtl(para, algn='r'):
            p_elem = para._p
            pPr = p_elem.find(qn('a:pPr'))
            if pPr is None:
                pPr = OxmlElement('a:pPr')
                p_elem.insert(0, pPr)
            pPr.set('rtl', '1')
            pPr.set('algn', algn)

        def add_tb(sl, text, l, t, w, h,
                   size=16, bold=False, color=None,
                   align=PP_ALIGN.RIGHT, italic=False):
            tb  = sl.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
            tf  = tb.text_frame
            tf.word_wrap = True
            para = tf.paragraphs[0]
            para.alignment = align
            algn_map = {PP_ALIGN.RIGHT:'r', PP_ALIGN.CENTER:'ctr', PP_ALIGN.LEFT:'l'}
            set_para_rtl(para, algn_map.get(align,'r'))
            run = para.add_run()
            run.text        = str(text) if text else ''
            run.font.size   = Pt(size)
            run.font.bold   = bold
            run.font.italic = italic
            run.font.color.rgb = color if color else WHITE
            r_elem = run._r
            rPr = r_elem.find(qn('a:rPr'))
            if rPr is None:
                rPr = OxmlElement('a:rPr')
                r_elem.insert(0, rPr)
            rPr.set('lang','ar-SA')
            return tb

        def add_rect(sl, l, t, w, h, color):
            shape = sl.shapes.add_shape(1,Inches(l),Inches(t),Inches(w),Inches(h))
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
            shape.line.fill.background()
            return shape

        def add_top_bar(sl):    add_rect(sl,0,0,   13.33,0.07,BLUE)
        def add_bottom_bar(sl): add_rect(sl,0,7.43,13.33,0.07,BLUE)

        def insert_image_pptx(sl, b64, l, t, max_w, max_h):
            img_bytes = b64_to_bytes(b64)
            if not img_bytes: return False
            try:
                img = Image.open(BytesIO(img_bytes))
                if img.mode != 'RGB': img = img.convert('RGB')
                orig_w, orig_h = img.size
                ratio = orig_w / orig_h
                if ratio >= 1:
                    w = min(max_w, max_h * ratio); h = w / ratio
                else:
                    h = min(max_h, max_w / ratio); w = h * ratio
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=85)
                buf.seek(0)
                sl.shapes.add_picture(buf,Inches(l),Inches(t),Inches(w),Inches(h))
                return True
            except Exception:
                return False

        def make_report_slides(lines_list, slide_title, title_color, bg_color=None):
            """إنشاء شرائح تقرير مع دعم ألوان مختلفة"""
            chunks = [lines_list[i:i+9] for i in range(0,len(lines_list),9)]
            for cidx, chunk in enumerate(chunks):
                sl = new_slide()
                add_top_bar(sl)
                add_bottom_bar(sl)
                if bg_color:
                    add_rect(sl, 0, 0.07, 13.33, 7.36, bg_color)
                stitle = slide_title
                if len(chunks) > 1:
                    stitle += f"  ({cidx+1}/{len(chunks)})"
                add_tb(sl, stitle, 0.4, 0.15, 12.5, 0.7,
                       size=20, bold=True, color=title_color)
                add_rect(sl, 0.4, 0.88, 12.5, 0.04, BLUE)
                y = 1.05
                for line in chunk:
                    is_h = line.startswith('## ') or line.startswith('# ')
                    txt  = line.lstrip('#').strip()
                    if is_h:
                        add_rect(sl, 0.4, y-0.04, 12.5, 0.54, CARD)
                        add_tb(sl, txt, 0.5, y, 12.3, 0.5,
                               size=15, bold=True, color=title_color)
                    else:
                        add_tb(sl, txt, 0.5, y, 12.3, 0.5, size=13, color=WHITE)
                    y += 0.62
                    if y > 6.9: break

        # ════════════════════════════════
        # شريحة 1: الغلاف
        # ════════════════════════════════
        sl1 = new_slide()
        add_top_bar(sl1); add_bottom_bar(sl1)
        add_rect(sl1, 1.5, 1.2, 10.33, 4.5, CARD)
        add_tb(sl1, "🔍 محلل حسابات X الاستخباراتي",
               1.7, 1.5, 10, 0.8, size=16, color=GRAY, align=PP_ALIGN.CENTER)
        add_tb(sl1, title,
               1.7, 2.3, 10, 1.5, size=30, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_rect(sl1, 4.0, 3.85, 5.33, 0.05, BLUE)
        add_tb(sl1, f"تاريخ التقرير: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
               1.7, 4.0, 10, 0.6, size=14, color=GRAY, align=PP_ALIGN.CENTER)
        add_tb(sl1, "Gemini AI  |  v10.0",
               1.7, 4.7, 10, 0.5, size=12, color=ACCENT, align=PP_ALIGN.CENTER)

        # ════════════════════════════════
        # شريحة 2: الصور (إن وجدت) + تحليلها
        # ════════════════════════════════
        imgs = [i for i in (images_b64 or []) if i]
        if imgs:
            sl_img = new_slide()
            add_top_bar(sl_img); add_bottom_bar(sl_img)
            if export_type == 'account':
                add_tb(sl_img, "📸 صورة الملف الشخصي",
                       0.4, 0.15, 12.5, 0.7, size=22, bold=True, color=ACCENT)
                add_rect(sl_img, 0.4, 0.88, 12.5, 0.04, BLUE)
                insert_image_pptx(sl_img, imgs[0], 4.2, 1.1, 5.0, 5.0)
                extra_y = 1.1
                for ex in imgs[1:3]:
                    insert_image_pptx(sl_img, ex, 9.7, extra_y, 3.0, 2.2)
                    extra_y += 2.4
                handle_t = f"@{data.get('screen_name','')}  –  {data.get('name','')}"
                add_tb(sl_img, handle_t, 0.4, 6.6, 12.5, 0.6,
                       size=14, color=GRAY, align=PP_ALIGN.CENTER)
            else:
                add_tb(sl_img, "🖼️ صور التغريدة",
                       0.4, 0.15, 12.5, 0.7, size=22, bold=True, color=ACCENT)
                add_rect(sl_img, 0.4, 0.88, 12.5, 0.04, BLUE)
                count = min(len(imgs), 3)
                positions = {
                    1: [(3.2,1.1,6.8,5.6)],
                    2: [(0.5,1.1,5.9,5.6),(6.9,1.1,5.9,5.6)],
                    3: [(0.4,1.1,3.9,5.2),(4.7,1.1,3.9,5.2),(9.0,1.1,3.9,5.2)],
                }
                for idx, pos in enumerate(positions[count]):
                    insert_image_pptx(sl_img, imgs[idx], pos[0],pos[1],pos[2],pos[3])
                    add_tb(sl_img, f"صورة {idx+1}",
                           pos[0], pos[1]+pos[3]+0.05, pos[2], 0.35,
                           size=12, color=GRAY, align=PP_ALIGN.CENTER)

        # ════════════════════════════════
        # شرائح تحليل الصورة ← جديد
        # ════════════════════════════════
        if image_analysis_text and image_analysis_text.strip():
            ia_lines = [l.strip() for l in image_analysis_text.split('\n') if l.strip()]

            # شريحة غلاف تحليل الصورة
            sl_ia_cover = new_slide()
            add_top_bar(sl_ia_cover); add_bottom_bar(sl_ia_cover)
            add_rect(sl_ia_cover, 0, 0.07, 13.33, 7.36, CARD_BLUE)
            add_rect(sl_ia_cover, 1.5, 2.0, 10.33, 3.5, RGBColor(0x0d,0x1f,0x4a))
            add_tb(sl_ia_cover, "🔬 تحليل الصورة بالذكاء الاصطناعي",
                   1.7, 2.3, 10, 1.0, size=26, bold=True,
                   color=TEAL, align=PP_ALIGN.CENTER)
            add_rect(sl_ia_cover, 3.0, 3.35, 7.33, 0.05, TEAL)
            add_tb(sl_ia_cover, "Gemini AI  –  تحليل بصري متقدم",
                   1.7, 3.5, 10, 0.6, size=15, color=GRAY, align=PP_ALIGN.CENTER)

            # الصور مع التحليل جنباً لجنب (إذا وجدت صورة واحدة فقط)
            if imgs and len(ia_lines) <= 12:
                sl_combined = new_slide()
                add_top_bar(sl_combined); add_bottom_bar(sl_combined)
                add_rect(sl_combined, 0, 0.07, 13.33, 7.36,
                         RGBColor(0x0a,0x18,0x2e))
                add_tb(sl_combined, "🔬 الصورة وتحليلها",
                       0.4, 0.15, 12.5, 0.7, size=20, bold=True, color=TEAL)
                add_rect(sl_combined, 0.4, 0.88, 12.5, 0.04, TEAL)

                # الصورة على اليمين
                insert_image_pptx(sl_combined, imgs[0], 8.8, 1.0, 4.2, 5.5)
                # النص على اليسار
                y = 1.0
                for line in ia_lines[:10]:
                    is_h = line.startswith('## ') or line.startswith('# ')
                    txt  = line.lstrip('#').strip()
                    if is_h:
                        add_rect(sl_combined, 0.4, y-0.04, 8.2, 0.52,
                                 RGBColor(0x0c,0x2d,0x6b))
                        add_tb(sl_combined, txt, 0.5, y, 8.0, 0.5,
                               size=14, bold=True, color=TEAL)
                    else:
                        add_tb(sl_combined, txt, 0.5, y, 8.0, 0.5,
                               size=12, color=WHITE)
                    y += 0.58
                    if y > 6.8: break
            else:
                # شرائح تحليل منفصلة
                make_report_slides(
                    ia_lines,
                    "🔬 تحليل الصورة",
                    TEAL,
                    bg_color=RGBColor(0x0a,0x18,0x2e)
                )

        # ════════════════════════════════
        # شريحة بيانات الحساب / التغريدة
        # ════════════════════════════════
        sl2 = new_slide()
        add_top_bar(sl2); add_bottom_bar(sl2)

        if export_type == 'account':
            add_tb(sl2, "👤 بيانات الحساب",
                   0.4, 0.15, 12.5, 0.7, size=22, bold=True, color=ACCENT)
            add_rect(sl2, 0.4, 0.88, 12.5, 0.04, BLUE)
            fields = [
                ('الاسم الكامل',   data.get('name','')),
                ('المعرّف',        '@'+data.get('screen_name','')),
                ('المتابِعون',     format_number(data.get('followers',0))),
                ('يتابع',          format_number(data.get('following',0))),
                ('التغريدات',      format_number(data.get('tweets',0))),
                ('الموقع',         data.get('location','')),
                ('تاريخ الانضمام', data.get('joined','')),
            ]
            y = 1.05
            for lbl, val in fields:
                if val:
                    add_tb(sl2, f"{val}  :{lbl}", 0.4, y, 12.5, 0.52, size=15, color=WHITE)
                    add_rect(sl2, 0.4, y+0.5, 12.5, 0.01, RGBColor(0x21,0x26,0x2d))
                    y += 0.56
                    if y > 5.5: break
            bio = data.get('bio','')
            if bio and y < 6.0:
                bio_short = bio[:160] + ('…' if len(bio)>160 else '')
                add_rect(sl2, 0.4, y, 12.5, 0.9, CARD)
                add_tb(sl2, f"الوصف:  {bio_short}", 0.5, y+0.05, 12.3, 0.8, size=12, color=GRAY)
            stats_data = [
                ('المتابِعون', format_number(data.get('followers',0)), GREEN),
                ('يتابع',      format_number(data.get('following',0)), ACCENT),
                ('التغريدات',  format_number(data.get('tweets',0)),    WHITE),
            ]
            sx = 0.4
            for lbl, val, col in stats_data:
                add_rect(sl2, sx, 5.9, 4.1, 1.35, CARD)
                add_tb(sl2, val, sx, 6.0, 4.1, 0.75, size=26, bold=True, color=col, align=PP_ALIGN.CENTER)
                add_tb(sl2, lbl, sx, 6.75, 4.1, 0.4, size=12, color=GRAY, align=PP_ALIGN.CENTER)
                sx += 4.4
        else:
            add_tb(sl2, "🐦 بيانات التغريدة",
                   0.4, 0.15, 12.5, 0.7, size=22, bold=True, color=ACCENT)
            add_rect(sl2, 0.4, 0.88, 12.5, 0.04, BLUE)
            fields = [
                ('المؤلف',    data.get('author_name','')),
                ('المعرّف',   '@'+data.get('author_handle','')),
                ('التاريخ',   data.get('date','')),
                ('الإعجابات', format_number(data.get('likes',0))),
                ('الإعادات',  format_number(data.get('retweets',0))),
                ('الردود',    format_number(data.get('replies',0))),
                ('المشاهدات', format_number(data.get('views',0))),
            ]
            y = 1.05
            for lbl, val in fields:
                if val:
                    add_tb(sl2, f"{val}  :{lbl}", 0.4, y, 12.5, 0.52, size=15, color=WHITE)
                    add_rect(sl2, 0.4, y+0.5, 12.5, 0.01, RGBColor(0x21,0x26,0x2d))
                    y += 0.56
            tw = data.get('text','')
            if tw and y < 6.2:
                short = tw[:220] + ('…' if len(tw)>220 else '')
                add_rect(sl2, 0.4, y+0.1, 12.5, 1.5, CARD)
                add_tb(sl2, short, 0.5, y+0.2, 12.3, 1.3, size=13, color=WHITE)

        # ════════════════════════════════
        # شرائح التقرير العام
        # ════════════════════════════════
        if report_text and report_text.strip():
            lines = [l.strip() for l in report_text.split('\n') if l.strip()]
            make_report_slides(lines, "📊 تقرير التحليل الاستخباراتي", ACCENT)

        # ════════════════════════════════
        # شريحة الخاتمة
        # ════════════════════════════════
        sl_end = new_slide()
        add_top_bar(sl_end); add_bottom_bar(sl_end)
        add_rect(sl_end, 2.0, 1.8, 9.33, 3.5, CARD)
        add_tb(sl_end, "✅ انتهى التقرير",
               2.0, 2.3, 9.33, 1.2, size=34, bold=True,
               color=ACCENT, align=PP_ALIGN.CENTER)
        add_rect(sl_end, 3.5, 3.5, 6.33, 0.05, BLUE)
        add_tb(sl_end, "محلل حسابات X الاستخباراتي",
               2.0, 3.6, 9.33, 0.6, size=16, color=WHITE, align=PP_ALIGN.CENTER)
        add_tb(sl_end, "Gemini AI  |  v10.0",
               2.0, 4.3, 9.33, 0.5, size=13, color=GRAY, align=PP_ALIGN.CENTER)

        buf = BytesIO()
        prs.save(buf)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ PowerPoint: {e}")
        return b''


# ─── أزرار التصدير ────────────────────────────────────────────

def render_export_buttons(
    title: str,
    data: dict,
    report_text: str,
    export_type: str = 'account',
    images_b64: list = None,
    image_analysis_text: str = '',    # ← تحليل الصورة
):
    st.markdown('<div class="section-title">📥 تصدير التقرير الكامل</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="export-section">', unsafe_allow_html=True)

    # معلومات ما سيُصدَّر
    parts = []
    if images_b64:           parts.append(f"🖼️ {len([i for i in images_b64 if i])} صورة")
    if image_analysis_text:  parts.append("🔬 تحليل الصورة")
    if report_text:          parts.append("📊 تقرير التحليل")
    if parts:
        summary = " | ".join(parts)
        st.markdown(f'<div class="info-box">📦 يتضمن التقرير: {summary}</div>',
                    unsafe_allow_html=True)

    safe_t    = re.sub(r'[^\w\s-]', '', title)[:30].strip().replace(' ', '_')
    ts        = datetime.now().strftime('%Y%m%d_%H%M')
    base_name = f"X_Report_{safe_t}_{ts}"

    col1, col2, col3 = st.columns(3)

    with col1:
        docx_b = export_to_word(
            title, data, report_text, export_type, images_b64, image_analysis_text
        )
        if docx_b:
            st.download_button(
                label="📄 تحميل Word",
                data=docx_b,
                file_name=f"{base_name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"docx_{ts}",
            )

    with col2:
        pptx_b = export_to_pptx(
            title, data, report_text, export_type, images_b64, image_analysis_text
        )
        if pptx_b:
            st.download_button(
                label="📊 تحميل PowerPoint",
                data=pptx_b,
                file_name=f"{base_name}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key=f"pptx_{ts}",
            )

    with col3:
        # دمج كل النصوص في ملف TXT واحد
        full_txt = ''
        if report_text:       full_txt += f"=== تقرير التحليل ===\n{report_text}\n\n"
        if image_analysis_text: full_txt += f"=== تحليل الصورة ===\n{image_analysis_text}\n"
        if full_txt:
            st.download_button(
                label="📝 تحميل TXT",
                data=full_txt.encode('utf-8'),
                file_name=f"{base_name}.txt",
                mime="text/plain",
                key=f"txt_{ts}",
            )

    st.markdown('</div>', unsafe_allow_html=True)


# ─── بطاقة الملف الشخصي ──────────────────────────────────────

def render_profile_card(data: dict, featured_b64: str = None):
    name     = escape_html(data.get('name','غير متاح'))
    handle   = escape_html(data.get('screen_name',''))
    bio_html = safe_html_lines(data.get('bio',''))
    fol      = format_number(data.get('followers',0))
    fing     = format_number(data.get('following',0))
    twts     = format_number(data.get('tweets',0))
    loc      = escape_html(data.get('location',''))
    jnd      = escape_html(data.get('joined',''))
    src      = escape_html(data.get('source',''))
    if featured_b64:
        img_html = f'<img src="data:image/jpeg;base64,{featured_b64}" class="profile-img">'
    elif data.get('profile_image_b64'):
        b64 = data['profile_image_b64']
        img_html = f'<img src="data:image/jpeg;base64,{b64}" class="profile-img">'
    else:
        img_html = '<div class="profile-img-placeholder">👤</div>'
    loc_span  = f'<span>📍 {loc}</span>' if loc else ''
    join_span = f'<span>📅 انضم: {jnd}</span>' if jnd else ''
    src_span  = f'<span>🔗 {src}</span>'
    st.markdown(f"""
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
            <div class="stat-box"><div class="stat-value">{fol}</div><div class="stat-label">متابِع</div></div>
            <div class="stat-box"><div class="stat-value">{fing}</div><div class="stat-label">يتابع</div></div>
            <div class="stat-box"><div class="stat-value">{twts}</div><div class="stat-label">تغريدة</div></div>
        </div>
        <div class="profile-meta">{loc_span}{join_span}{src_span}</div>
    </div>
    """, unsafe_allow_html=True)


# ─── تبويب تحليل الحساب ───────────────────────────────────────

def account_tab(gemini_key: str, gemini_model_name: str):
    st.markdown('<div class="section-title">👤 تحليل حساب X</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "📸 ارفع صورة الملف الشخصي أو البانر",
        type=['jpg','jpeg','png','webp'], key='account_img'
    )
    featured_b64 = None
    if uploaded:
        try:
            img = Image.open(uploaded)
            featured_b64 = pil_to_base64(img)
            col_img, _ = st.columns([1,3])
            with col_img:
                st.image(uploaded, caption="الصورة المرفوعة", use_container_width=True)
        except Exception as e:
            st.error(f"❌ خطأ في تحميل الصورة: {e}")

    st.markdown('<div class="section-title">🔍 جلب بيانات الحساب</div>', unsafe_allow_html=True)
    user_input = st.text_input(
        "اسم المستخدم أو الرابط",
        placeholder="مثال: elonmusk أو https://x.com/elonmusk",
        key='account_username'
    )
    c1, c2 = st.columns([3,1])
    with c1:
        fetch_btn = st.button("🔍 جلب بيانات الحساب", key='fetch_account')
    with c2:
        if st.button("🗑️ مسح", key='clear_account'):
            for k in ['account_data','account_report','account_img_analysis']:
                st.session_state.pop(k, None)
            st.rerun()

    if fetch_btn and user_input:
        username = extract_username(user_input)
        if not username:
            st.markdown('<div class="error-box">❌ لم أتمكن من استخراج اسم المستخدم</div>',
                        unsafe_allow_html=True)
        else:
            with st.spinner(f"🔄 جاري جلب بيانات @{username}..."):
                data = fetch_nitter(username, debug=st.session_state.get('debug_mode',False))
                st.session_state['account_data'] = data

    if 'account_data' in st.session_state:
        data = st.session_state['account_data']
        if 'error' in data and not data.get('name'):
            err = escape_html(data.get('error',''))
            st.markdown(f'<div class="error-box">❌ {err}</div>', unsafe_allow_html=True)
            with st.expander("✏️ إدخال يدوي"):
                c1,c2 = st.columns(2)
                with c1:
                    mn=st.text_input("الاسم",key='m_name'); mh=st.text_input("المعرّف",key='m_handle')
                    mf=st.text_input("المتابِعون",key='m_f'); mfg=st.text_input("يتابع",key='m_fg')
                with c2:
                    mt=st.text_input("التغريدات",key='m_t'); ml=st.text_input("الموقع",key='m_l')
                    mj=st.text_input("تاريخ الانضمام",key='m_j'); mb=st.text_area("الوصف",key='m_b',height=80)
                if st.button("💾 حفظ",key='save_manual'):
                    st.session_state['account_data'] = {
                        'name':mn,'screen_name':mh.lstrip('@'),
                        'followers':mf,'following':mfg,'tweets':mt,
                        'location':ml,'joined':mj,'bio':mb,'source':'إدخال يدوي',
                    }
                    st.rerun()
        else:
            src = escape_html(data.get('source',''))
            st.markdown(f'<div class="success-box">✅ تم جلب البيانات: {src}</div>',
                        unsafe_allow_html=True)
            render_profile_card(data, featured_b64)

            # ── تحليل صورة البروفايل ──────────────────────────
            if gemini_key and featured_b64:
                st.markdown('<div class="section-title">🔬 تحليل صورة الحساب</div>',
                            unsafe_allow_html=True)
                analysis_point_acc = st.selectbox(
                    "نقطة التحليل للصورة",
                    IMAGE_ANALYSIS_POINTS,
                    key='acc_img_point'
                )
                if st.button("🔬 تحليل صورة الحساب", key='analyze_acc_img'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        pt = f"""أنت خبير تحليل بصري واستخباراتي.
قم بـ: **{analysis_point_acc}**
التعليمات:
- تحليل دقيق ومفصّل
- اذكر كل التفاصيل الملاحظة
- كن موضوعياً وعلمياً
- اكتب باللغة العربية"""
                        with st.spinner("🤖 جاري تحليل الصورة..."):
                            result = gemini_with_images(model, pt, [featured_b64])
                            st.session_state['account_img_analysis'] = result

            if 'account_img_analysis' in st.session_state:
                ia = st.session_state['account_img_analysis']
                st.markdown(
                    f'<div class="img-analysis-section" dir="rtl">{safe_html_lines(ia)}</div>',
                    unsafe_allow_html=True
                )

            # ── تقرير Gemini العام ──────────────────────────
            st.markdown('<div class="section-title">🤖 تقرير استخباراتي شامل</div>',
                        unsafe_allow_html=True)
            if not gemini_key:
                st.markdown('<div class="warning-box">⚠️ أدخل مفتاح Gemini API في الشريط الجانبي</div>',
                            unsafe_allow_html=True)
            else:
                if st.button("🚀 توليد التقرير", key='gen_account_report'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        prompt = f"""أنت محلل استخباراتي متخصص في تحليل حسابات X.
قم بتحليل الحساب التالي وتقديم تقرير شامل باللغة العربية:
الاسم: {data.get('name','')}
المعرّف: @{data.get('screen_name','')}
الوصف: {data.get('bio','')}
المتابِعون: {format_number(data.get('followers',0))}
يتابع: {format_number(data.get('following',0))}
التغريدات: {format_number(data.get('tweets',0))}
الموقع: {data.get('location','')}
تاريخ الانضمام: {data.get('joined','')}

## 1. ملخص الهوية
## 2. تحليل النشاط والتأثير
## 3. المؤشرات الجغرافية والثقافية
## 4. تقييم مصداقية الحساب
## 5. المخاطر والملاحظات
## 6. التوصيات"""
                        imgs_ai = []
                        if featured_b64: imgs_ai.append(featured_b64)
                        elif data.get('profile_image_b64'): imgs_ai.append(data['profile_image_b64'])
                        with st.spinner("🤖 جاري التحليل..."):
                            if imgs_ai:
                                report = gemini_with_images(model, prompt, imgs_ai)
                            else:
                                report = gemini_text(model, prompt)
                            st.session_state['account_report'] = report

            if 'account_report' in st.session_state:
                rpt = st.session_state['account_report']
                st.markdown(
                    f'<div class="report-section" dir="rtl">{safe_html_lines(rpt)}</div>',
                    unsafe_allow_html=True
                )
                export_imgs = []
                if featured_b64: export_imgs.append(featured_b64)
                if data.get('profile_image_b64') and not featured_b64:
                    export_imgs.append(data['profile_image_b64'])

                render_export_buttons(
                    title=f"تقرير حساب @{data.get('screen_name','unknown')}",
                    data=data,
                    report_text=rpt,
                    export_type='account',
                    images_b64=export_imgs,
                    image_analysis_text=st.session_state.get('account_img_analysis',''),
                )


# ─── تبويب تحليل التغريدة ─────────────────────────────────────

def tweet_tab(gemini_key: str, gemini_model_name: str):
    st.markdown('<div class="section-title">🐦 تحليل تغريدة</div>', unsafe_allow_html=True)

    tweet_input = st.text_input(
        "رابط أو معرّف التغريدة",
        placeholder="https://x.com/user/status/1234567890123456789",
        key='tweet_url_input'
    )
    c1, c2 = st.columns([3,1])
    with c1:
        fetch_btn = st.button("🔍 جلب بيانات التغريدة", key='fetch_tweet')
    with c2:
        if st.button("🗑️ مسح", key='clear_tweet'):
            for k in ['tweet_data','tweet_report','tweet_media_b64','tweet_img_analysis']:
                st.session_state.pop(k, None)
            st.rerun()

    if fetch_btn and tweet_input:
        if re.search(r'(?:twitter|x)\.com/[A-Za-z0-9_]+$', tweet_input):
            st.markdown(
                '<div class="warning-box">⚠️ هذا رابط <b>حساب</b> وليس تغريدة! '
                'استخدم تبويب <b>👤 تحليل حساب X</b></div>',
                unsafe_allow_html=True
            )
        else:
            tid = extract_tweet_id(tweet_input)
            if not tid:
                st.markdown('<div class="error-box">❌ تعذّر استخراج معرّف التغريدة</div>',
                            unsafe_allow_html=True)
            else:
                with st.spinner("🔄 جاري جلب التغريدة..."):
                    tdata = fetch_fxtwitter(tid)
                    st.session_state['tweet_data'] = tdata
                    media_b64_list = []
                    for murl in tdata.get('media_urls',[])[:3]:
                        b64 = url_to_base64(murl)
                        if b64: media_b64_list.append(b64)
                    st.session_state['tweet_media_b64'] = media_b64_list

    if 'tweet_data' in st.session_state:
        td = st.session_state['tweet_data']
        if 'error' in td:
            err = escape_html(td['error'])
            st.markdown(f'<div class="error-box">❌ {err}</div>', unsafe_allow_html=True)
            with st.expander("✏️ إدخال يدوي"):
                manual_text = st.text_area("نص التغريدة", key='mt_text', height=120)
                mc1,mc2 = st.columns(2)
                with mc1:
                    ma=st.text_input("اسم المؤلف",key='mt_a'); mh=st.text_input("المعرّف",key='mt_h')
                    md=st.text_input("التاريخ",key='mt_d')
                with mc2:
                    ml=st.text_input("الإعجابات",key='mt_l'); mr=st.text_input("الإعادات",key='mt_r')
                    mp=st.text_input("الردود",key='mt_p')
                if st.button("💾 حفظ",key='save_tweet_manual'):
                    st.session_state['tweet_data'] = {
                        'text':manual_text,'author_name':ma,
                        'author_handle':mh.lstrip('@'),'date':md,
                        'likes':ml,'retweets':mr,'replies':mp,
                        'views':0,'media_urls':[],'data_source':'إدخال يدوي',
                    }
                    st.session_state['tweet_media_b64'] = []
                    st.rerun()
        else:
            src_n = escape_html(td.get('data_source','FxTwitter'))
            st.markdown(f'<div class="success-box">✅ تم جلب التغريدة: {src_n}</div>',
                        unsafe_allow_html=True)

            tw_html  = safe_html_lines(td.get('text',''))
            aut_name = escape_html(td.get('author_name',''))
            aut_hand = escape_html(td.get('author_handle',''))
            date_v   = escape_html(td.get('date',''))
            lang_v   = escape_html(td.get('lang',''))
            lang_span = f'<div class="tweet-stat">🌐 {lang_v}</div>' if lang_v else ''

            st.markdown(f"""
            <div class="tweet-card">
                <div style="margin-bottom:12px;direction:rtl;text-align:right;">
                    <strong style="color:#e6edf3;font-size:1.1rem;">{aut_name}</strong>
                    <span style="color:#8b949e;margin-right:8px;">@{aut_hand}</span>
                    <span style="color:#8b949e;font-size:.85rem;float:left;">{date_v}</span>
                </div>
                <div class="tweet-text">{tw_html}</div>
                <div class="tweet-stats">
                    <div class="tweet-stat">❤️ {format_number(td.get('likes',0))}</div>
                    <div class="tweet-stat">🔁 {format_number(td.get('retweets',0))}</div>
                    <div class="tweet-stat">💬 {format_number(td.get('replies',0))}</div>
                    <div class="tweet-stat">👁️ {format_number(td.get('views',0))}</div>
                    {lang_span}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # صور التغريدة
            media_urls      = td.get('media_urls',[])
            tweet_media_b64 = st.session_state.get('tweet_media_b64',[])
            if media_urls:
                st.markdown('<div class="section-title">🖼️ صور التغريدة</div>',
                            unsafe_allow_html=True)
                cols = st.columns(min(len(media_urls),3))
                for i,murl in enumerate(media_urls[:3]):
                    with cols[i]:
                        try: st.image(murl, use_container_width=True)
                        except Exception: pass

            # رفع صور إضافية
            st.markdown('<div class="section-title">🔬 رفع صور للتحليل</div>',
                        unsafe_allow_html=True)
            uploaded_imgs = st.file_uploader(
                "ارفع صور إضافية للتحليل",
                type=['jpg','jpeg','png','webp'],
                accept_multiple_files=True,
                key='tweet_images'
            )

            all_images_b64 = list(tweet_media_b64)
            for uf in (uploaded_imgs or []):
                try:
                    b64 = pil_to_base64(Image.open(uf))
                    if b64: all_images_b64.append(b64)
                except Exception: pass

            analysis_point = st.selectbox(
                "نقطة التحليل", IMAGE_ANALYSIS_POINTS, key='ap_select'
            )

            # ── زر تحليل الصورة ──
            if all_images_b64 and gemini_key:
                if st.button("🔬 تحليل الصور وحفظ النتيجة للتصدير", key='analyze_imgs'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        pt = f"""أنت خبير تحليل بصري واستخباراتي.
قم بـ: **{analysis_point}**
- تحليل دقيق ومفصّل
- اذكر كل التفاصيل الملاحظة
- كن موضوعياً وعلمياً
- اكتب باللغة العربية"""
                        with st.spinner("🤖 جاري تحليل الصور..."):
                            result = gemini_with_images(model, pt, all_images_b64[:4])
                            # ← حفظ النتيجة في session_state للتصدير
                            st.session_state['tweet_img_analysis'] = result

            # عرض نتيجة تحليل الصورة
            if 'tweet_img_analysis' in st.session_state:
                ia = st.session_state['tweet_img_analysis']
                st.markdown(
                    f'<div class="img-analysis-section" dir="rtl">{safe_html_lines(ia)}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    '<div class="success-box">✅ تم حفظ تحليل الصورة – سيظهر في ملفات التصدير</div>',
                    unsafe_allow_html=True
                )

            # ── تحليل نص التغريدة ──
            st.markdown('<div class="section-title">🤖 تحليل نص التغريدة</div>',
                        unsafe_allow_html=True)
            if not gemini_key:
                st.markdown('<div class="warning-box">⚠️ أدخل مفتاح Gemini API</div>',
                            unsafe_allow_html=True)
            else:
                if st.button("📊 تحليل نص التغريدة", key='analyze_tweet_text'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        prompt = f"""أنت محلل استخباراتي متخصص في تحليل منشورات X.
حلّل التغريدة التالية وقدّم تقريراً باللغة العربية:
النص: {td.get('text','')}
المؤلف: {td.get('author_name','')} (@{td.get('author_handle','')})
التاريخ: {td.get('date','')}
الإعجابات: {td.get('likes',0)} | الإعادات: {td.get('retweets',0)}

## 1. تحليل المحتوى والرسالة
## 2. تحليل اللغة والأسلوب
## 3. السياق والتوقيت
## 4. التأثير والانتشار
## 5. مصداقية الحساب الناشر
## 6. التوصيات الاستخباراتية"""
                        with st.spinner("🤖 جاري التحليل..."):
                            report = gemini_text(model, prompt)
                            st.session_state['tweet_report'] = report

            if 'tweet_report' in st.session_state:
                t_rpt = st.session_state['tweet_report']
                st.markdown(
                    f'<div class="report-section" dir="rtl">{safe_html_lines(t_rpt)}</div>',
                    unsafe_allow_html=True
                )

                # جمع الصور
                export_imgs = list(tweet_media_b64)
                for uf in (uploaded_imgs or []):
                    try:
                        b64 = pil_to_base64(Image.open(uf))
                        if b64 and b64 not in export_imgs:
                            export_imgs.append(b64)
                    except Exception: pass

                render_export_buttons(
                    title=f"تحليل تغريدة @{td.get('author_handle','unknown')}",
                    data=td,
                    report_text=t_rpt,
                    export_type='tweet',
                    images_b64=export_imgs[:4],
                    image_analysis_text=st.session_state.get('tweet_img_analysis',''),
                )


# ─── الشريط الجانبي ───────────────────────────────────────────

def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:16px 0;">
            <div style="font-size:2.5rem;">🔍</div>
            <h2 style="color:#58a6ff;margin:8px 0;font-size:1.3rem;">محلل حسابات X</h2>
            <p style="color:#8b949e;font-size:.85rem;">v10.0 | Gemini 2.5</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### 🔑 إعدادات Gemini AI")
        gemini_key = st.text_input(
            "مفتاح Gemini API", type="password",
            placeholder="AIza...", key='gemini_api_key',
            help="https://aistudio.google.com/apikey"
        )
        selected_model = st.selectbox(
            "نموذج Gemini",
            options=list(GEMINI_MODELS.keys()),
            format_func=lambda x: GEMINI_MODELS[x],
            key='gemini_model'
        )
        if gemini_key:
            st.markdown('<div class="success-box">✅ مفتاح Gemini جاهز</div>',
                        unsafe_allow_html=True)
        else:
            link = "https://aistudio.google.com/apikey"
            st.markdown(
                f'<div class="info-box">ℹ️ أدخل مفتاح API للتفعيل<br>'
                f'<a href="{link}" target="_blank" style="color:#58a6ff;">احصل على مفتاح مجاني</a></div>',
                unsafe_allow_html=True
            )
        st.markdown("---")
        st.markdown("### 📡 المصادر النشطة")
        st.markdown("""
        <div style="direction:rtl;text-align:right;font-size:.9rem;">
        ✅ <b>Nitter</b> – بيانات الحسابات<br>
        ✅ <b>FxTwitter API</b> – بيانات التغريدات<br>
        ✅ <b>Gemini 2.5</b> – التحليل الذكي<br>
        ✅ <b>Word / PPTX</b> – تصدير مع الصور والتحليل<br>
        ⚠️ <em>twikit معطّل مؤقتاً (KEY_BYTE)</em>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.checkbox("🐛 وضع التشخيص", key='debug_mode', value=False)
        st.markdown("---")
        st.markdown("""
        <div style="text-align:center;color:#8b949e;font-size:.8rem;">
            محلل حسابات X | v10.0 | 2025
        </div>
        """, unsafe_allow_html=True)
    return gemini_key, selected_model


# ─── الدالة الرئيسية ──────────────────────────────────────────

def main():
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px;direction:rtl;">
        <h1 style="color:#58a6ff;font-size:2rem;margin:0;">
            🔍 محلل حسابات X الاستخباراتي
        </h1>
        <p style="color:#8b949e;font-size:1rem;margin:8px 0 0;">
            تحليل متقدم للحسابات والتغريدات والصور – Gemini 2.5 | Word | PowerPoint
        </p>
    </div>
    """, unsafe_allow_html=True)
    gemini_key, model_name = render_sidebar()
    tab1, tab2 = st.tabs(["👤 تحليل حساب X", "🐦 تحليل تغريدة"])
    with tab1:
        account_tab(gemini_key, model_name)
    with tab2:
        tweet_tab(gemini_key, model_name)


if __name__ == "__main__":
    main()
