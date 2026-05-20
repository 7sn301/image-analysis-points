# ============================================================
#  محلل حسابات X الاستخباراتي – v10.1
#  إصلاح: OxmlElement import + تصميم احترافي + خط 16
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
from lxml import etree

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
]
NITTER_MIRRORS = [
    "https://nitter.privacydev.net","https://nitter.poast.org",
    "https://nitter.lucahammer.com","https://nitter.net",
    "https://nitter.1d4.us","https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu","https://nitter.moomoo.me",
    "https://nitter.it","https://nitter.fdn.fr",
]
FXTWITTER_API = "https://api.fxtwitter.com"
GEMINI_MODELS = {
    "gemini-2.5-flash":                    "⚡ Gemini 2.5 Flash (الأسرع)",
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

# ══════════════════════════════════════════════════════════════
#  دالة إنشاء عناصر XML  ← الإصلاح الرئيسي لخطأ OxmlElement
# ══════════════════════════════════════════════════════════════

_XML_NS = {
    'a':  'http://schemas.openxmlformats.org/drawingml/2006/main',
    'w':  'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'p':  'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r':  'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
}

def _el(tag: str):
    """إنشاء عنصر XML بدون الاعتماد على OxmlElement"""
    if ':' in tag:
        prefix, local = tag.split(':', 1)
        ns = _XML_NS.get(prefix, '')
        return etree.Element(f'{{{ns}}}{local}')
    return etree.Element(tag)

def _qn(tag: str) -> str:
    """تحويل prefix:local إلى {namespace}local"""
    if ':' in tag:
        prefix, local = tag.split(':', 1)
        ns = _XML_NS.get(prefix, '')
        return f'{{{ns}}}{local}'
    return tag

# ─── دوال مساعدة عامة ─────────────────────────────────────────

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
        if m: return m.group(1)
    return raw if re.match(r'^[A-Za-z0-9_]{1,50}$', raw) else ''

def extract_tweet_id(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r'/status/(\d+)', raw)
    if m: return m.group(1)
    return raw if raw.isdigit() else ''

def format_number(n) -> str:
    try:
        n = int(n)
    except Exception:
        return safe_text(n)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)

def format_date(d: str) -> str:
    if not d: return ''
    try:
        return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y/%m/%d %H:%M")
    except Exception:
        return safe_text(d)

def pil_to_base64(img: Image.Image) -> str:
    if img.mode in ('RGBA','P','LA'):
        bg  = Image.new('RGB', img.size, (255,255,255))
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
                try: val = int(stats[i].get_text(strip=True).replace(',','').replace('.',''))
                except Exception: val = 0
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
        except requests.exceptions.Timeout: last_err = "انتهت المهلة"
        except Exception as e: last_err = str(e)
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
        for p in tweet.get('media', {}).get('photos', []): media_urls.append(p.get('url',''))
        for v in tweet.get('media', {}).get('videos', []):
            if v.get('thumbnail_url'): media_urls.append(v['thumbnail_url'])
        return {
            'id':             tweet.get('id', tweet_id),
            'text':           tweet.get('text', ''),
            'date':           format_date(tweet.get('created_at', '')),
            'likes':          tweet.get('likes', 0),
            'retweets':       tweet.get('retweets', 0),
            'replies':        tweet.get('replies', 0),
            'views':          tweet.get('views', 0),
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
    except Exception: return None

def gemini_text(model, prompt: str) -> str:
    try: return model.generate_content(prompt).text
    except Exception as e: return f"❌ خطأ Gemini: {e}"

def gemini_with_images(model, prompt: str, images_b64: list) -> str:
    try:
        parts = [prompt]
        for b64 in images_b64:
            if b64: parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': b64}})
        return model.generate_content(parts).text
    except Exception as e: return f"❌ خطأ Gemini: {e}"

# ══════════════════════════════════════════════════════════════
#  تصدير Word – تصميم احترافي + خط 16 + RTL مُصلَح
# ══════════════════════════════════════════════════════════════

def export_to_word(
    title: str,
    data: dict,
    report_text: str,
    export_type: str = 'account',
    images_b64: list = None,
    image_analysis_text: str = '',
) -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches, Cm, Emu
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement as docxEl
        from docx.oxml.ns import qn as docxQn

        doc = Document()

        # ── إعداد الصفحة A4 ──
        sec = doc.sections[0]
        sec.page_width   = Inches(8.27)
        sec.page_height  = Inches(11.69)
        sec.top_margin   = Cm(2.0)
        sec.bottom_margin= Cm(2.0)
        sec.left_margin  = Cm(2.5)
        sec.right_margin = Cm(2.5)

        # ── RTL على مستوى الوثيقة ──
        try:
            styles_el = doc.element.find(docxQn('w:styles'))
            if styles_el is not None:
                for sty in styles_el.findall(docxQn('w:style')):
                    pPr = sty.find(docxQn('w:pPr'))
                    if pPr is None:
                        pPr = docxEl('w:pPr'); sty.append(pPr)
                    pPr.append(docxEl('w:bidi'))
                    jc = docxEl('w:jc'); jc.set(docxQn('w:val'), 'right'); pPr.append(jc)
        except Exception: pass

        # ── دوال مساعدة Word ──

        def _rtl_para(para):
            pPr = para._p.get_or_add_pPr()
            for old in pPr.findall(docxQn('w:jc')): pPr.remove(old)
            jc = docxEl('w:jc'); jc.set(docxQn('w:val'), 'right'); pPr.append(jc)
            for old in pPr.findall(docxQn('w:bidi')): pPr.remove(old)
            pPr.append(docxEl('w:bidi'))
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        def _rtl_run(run):
            rPr = run._r.get_or_add_rPr()
            for old in rPr.findall(docxQn('w:rtl')): rPr.remove(old)
            rPr.append(docxEl('w:rtl'))
            for old in rPr.findall(docxQn('w:cs')): rPr.remove(old)
            rPr.append(docxEl('w:cs'))

        def _spacing(para, before=60, after=60, line=300):
            pPr  = para._p.get_or_add_pPr()
            for old in pPr.findall(docxQn('w:spacing')): pPr.remove(old)
            sp   = docxEl('w:spacing')
            sp.set(docxQn('w:before'), str(before))
            sp.set(docxQn('w:after'),  str(after))
            sp.set(docxQn('w:line'),   str(line))
            sp.set(docxQn('w:lineRule'), 'auto')
            pPr.append(sp)

        def add_para(text, bold=False, size=16, color=None, italic=False,
                     before=60, after=60, line=320):
            p   = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, before, after, line)
            run = p.add_run(str(text) if text else '')
            run.bold    = bold
            run.italic  = italic
            run.font.size = Pt(size)
            if color: run.font.color.rgb = RGBColor(*color)
            _rtl_run(run)
            return p

        def add_h1(text):
            """عنوان رئيسي"""
            p = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, 200, 100, 340)
            # شريط ملوّن
            shd = docxEl('w:pBdr')
            bot = docxEl('w:bottom')
            bot.set(docxQn('w:val'), 'single')
            bot.set(docxQn('w:sz'),  '12')
            bot.set(docxQn('w:color'), '1F6FEB')
            shd.append(bot)
            p._p.get_or_add_pPr().append(shd)
            run = p.add_run(str(text))
            run.bold = True
            run.font.size = Pt(26)
            run.font.color.rgb = RGBColor(31,111,235)
            _rtl_run(run)
            return p

        def add_h2(text, color=(88,166,255)):
            p = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, 160, 80, 320)
            run = p.add_run(str(text))
            run.bold = True
            run.font.size = Pt(20)
            run.font.color.rgb = RGBColor(*color)
            _rtl_run(run)
            return p

        def add_h3(text, color=(86,211,100)):
            p = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, 120, 60, 300)
            run = p.add_run(str(text))
            run.bold = True
            run.font.size = Pt(17)
            run.font.color.rgb = RGBColor(*color)
            _rtl_run(run)
            return p

        def add_field_row(label, value):
            """صف بيانات: تسمية ملوّنة + قيمة"""
            p    = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, 40, 40, 300)
            # القيمة أولاً (لأن RTL)
            r_val = p.add_run(f"  {value}")
            r_val.font.size = Pt(16)
            r_val.font.color.rgb = RGBColor(230,237,243)
            _rtl_run(r_val)
            r_sep = p.add_run("  :  ")
            r_sep.font.size = Pt(16)
            r_sep.font.color.rgb = RGBColor(48,54,61)
            _rtl_run(r_sep)
            r_lbl = p.add_run(label)
            r_lbl.bold = True
            r_lbl.font.size = Pt(16)
            r_lbl.font.color.rgb = RGBColor(88,166,255)
            _rtl_run(r_lbl)
            return p

        def add_divider(style='thin'):
            p   = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, 40, 40, 240)
            char = '━' if style == 'thick' else '─'
            run = p.add_run(char * 60)
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(48,54,61)
            _rtl_run(run)

        def add_stat_line(label, value, color=(88,166,255)):
            """سطر إحصائي مميّز"""
            p = doc.add_paragraph()
            _rtl_para(p)
            _spacing(p, 30, 30, 280)
            r_v = p.add_run(f"  {value}")
            r_v.bold = True
            r_v.font.size = Pt(18)
            r_v.font.color.rgb = RGBColor(*color)
            _rtl_run(r_v)
            r_l = p.add_run(f"  {label}")
            r_l.font.size = Pt(14)
            r_l.font.color.rgb = RGBColor(139,148,158)
            _rtl_run(r_l)

        def insert_image_b64(b64, width_inches=4.0, caption=''):
            img_bytes = b64_to_bytes(b64)
            if not img_bytes: return
            try:
                img = Image.open(BytesIO(img_bytes))
                if img.mode != 'RGB': img = img.convert('RGB')
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=85)
                buf.seek(0)
                p = doc.add_paragraph()
                _rtl_para(p)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _spacing(p, 80, 80, 240)
                p.add_run().add_picture(buf, width=Inches(width_inches))
                if caption:
                    cp = doc.add_paragraph()
                    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cr = cp.add_run(caption)
                    cr.italic = True
                    cr.font.size = Pt(11)
                    cr.font.color.rgb = RGBColor(139,148,158)
                    _rtl_run(cr)
            except Exception as e:
                add_para(f"[تعذّر إدراج الصورة: {e}]", size=11, color=(200,100,100))

        def render_report_block(text, section_color=(88,166,255)):
            for line in text.split('\n'):
                s = line.strip()
                if not s:
                    doc.add_paragraph()
                    continue
                if s.startswith('## '):
                    add_h3(s[3:], color=section_color)
                elif s.startswith('# '):
                    add_h2(s[2:], color=section_color)
                elif s.startswith('**') and s.endswith('**'):
                    add_para(s.strip('*'), bold=True, size=16, color=section_color)
                elif s.startswith('- ') or s.startswith('• '):
                    add_para('   ' + s, size=16, color=(199,210,254), before=30, after=30)
                else:
                    add_para(s, size=16, before=40, after=40)

        # ════════ بناء المستند ════════

        # ─ صفحة الغلاف ─
        add_h1(title)
        add_para(
            f"📅 تاريخ التقرير: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
            size=13, color=(139,148,158), italic=True
        )
        add_para(
            "أُنتج بواسطة محلل حسابات X الاستخباراتي | Gemini AI | v10.1",
            size=12, color=(88,166,255), italic=True
        )
        add_divider('thick')
        doc.add_paragraph()

        # ─ الصور ─
        imgs = [i for i in (images_b64 or []) if i]
        if imgs:
            if export_type == 'account':
                add_h2("📸 صورة الملف الشخصي", color=(88,166,255))
                insert_image_b64(imgs[0], 2.8, "صورة الحساب")
                for ex in imgs[1:]: insert_image_b64(ex, 3.5, "صورة إضافية")
            else:
                add_h2("🖼️ صور التغريدة", color=(88,166,255))
                for idx, ib in enumerate(imgs):
                    insert_image_b64(ib, 4.5, f"صورة {idx+1}")
            add_divider()
            doc.add_paragraph()

        # ─ تحليل الصورة ─
        if image_analysis_text and image_analysis_text.strip():
            add_h2("🔬 تحليل الصورة بالذكاء الاصطناعي", color=(57,211,183))
            add_divider('thick')
            render_report_block(image_analysis_text, section_color=(57,211,183))
            add_divider('thick')
            doc.add_paragraph()

        # ─ البيانات ─
        if export_type == 'account':
            add_h2("👤 بيانات الحساب", color=(88,166,255))
            add_divider()
            fields = [
                ('الاسم الكامل',   data.get('name','')),
                ('المعرّف',        '@'+data.get('screen_name','')),
                ('الموقع',         data.get('location','')),
                ('تاريخ الانضمام', data.get('joined','')),
                ('المصدر',         data.get('source','')),
            ]
            for lbl, val in fields:
                if val: add_field_row(lbl, val)
            add_divider()
            # إحصاءات مميّزة
            add_h3("📊 الإحصاءات", color=(88,166,255))
            add_stat_line('متابِع',   format_number(data.get('followers',0)), (86,211,100))
            add_stat_line('يتابع',    format_number(data.get('following',0)), (88,166,255))
            add_stat_line('تغريدة',   format_number(data.get('tweets',0)),    (230,237,243))
            bio = data.get('bio','')
            if bio:
                doc.add_paragraph()
                add_h3("📝 الوصف", color=(88,166,255))
                add_para(bio, size=16, color=(199,210,254))
        else:
            add_h2("🐦 بيانات التغريدة", color=(88,166,255))
            add_divider()
            fields = [
                ('المؤلف',      data.get('author_name','')),
                ('المعرّف',     '@'+data.get('author_handle','')),
                ('التاريخ',     data.get('date','')),
                ('المصدر',      data.get('data_source','')),
            ]
            for lbl, val in fields:
                if val: add_field_row(lbl, val)
            add_divider()
            add_h3("📊 الإحصاءات", color=(88,166,255))
            add_stat_line('إعجاب',    format_number(data.get('likes',0)),    (86,211,100))
            add_stat_line('إعادة',    format_number(data.get('retweets',0)), (88,166,255))
            add_stat_line('رد',        format_number(data.get('replies',0)),  (240,136,62))
            add_stat_line('مشاهدة',   format_number(data.get('views',0)),    (230,237,243))
            tw = data.get('text','')
            if tw:
                doc.add_paragraph()
                add_h3("💬 نص التغريدة", color=(88,166,255))
                add_para(tw, size=16, color=(199,210,254), line=340)

        doc.add_paragraph()
        add_divider('thick')

        # ─ تقرير التحليل ─
        if report_text and report_text.strip():
            add_h2("📊 تقرير التحليل الاستخباراتي", color=(88,166,255))
            add_divider('thick')
            doc.add_paragraph()
            render_report_block(report_text)
            doc.add_paragraph()

        add_divider()
        add_para(
            "أُنتج بواسطة محلل حسابات X الاستخباراتي | Gemini AI | v10.1",
            size=11, color=(139,148,158), italic=True
        )

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ Word: {e}")
        return b''


# ══════════════════════════════════════════════════════════════
#  تصدير PowerPoint – تصميم احترافي + خط 16 + إصلاح OxmlElement
# ══════════════════════════════════════════════════════════════

def export_to_pptx(
    title: str,
    data: dict,
    report_text: str,
    export_type: str = 'account',
    images_b64: list = None,
    image_analysis_text: str = '',
) -> bytes:
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.oxml.ns import qn as pptxQn

        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        # ── لوحة الألوان ──
        C_DARK    = RGBColor(0x0d,0x11,0x17)
        C_CARD    = RGBColor(0x16,0x1b,0x22)
        C_CARD2   = RGBColor(0x1c,0x21,0x28)
        C_BLUE    = RGBColor(0x1f,0x6f,0xeb)
        C_ACCENT  = RGBColor(0x58,0xa6,0xff)
        C_WHITE   = RGBColor(0xe6,0xed,0xf3)
        C_GRAY    = RGBColor(0x8b,0x94,0x9e)
        C_GREEN   = RGBColor(0x56,0xd3,0x64)
        C_ORANGE  = RGBColor(0xf0,0x88,0x3e)
        C_TEAL    = RGBColor(0x39,0xd3,0xb7)
        C_PURPLE  = RGBColor(0xbc,0x8c,0xff)
        C_CARDBLU = RGBColor(0x0c,0x2d,0x6b)

        blank = prs.slide_layouts[6]

        # ── دوال مساعدة PPTX ──

        def new_slide(bg=None):
            sl = prs.slides.add_slide(blank)
            sl.background.fill.solid()
            sl.background.fill.fore_color.rgb = bg if bg else C_DARK
            return sl

        def _set_rtl(para, algn='r'):
            """ضبط RTL باستخدام lxml مباشرة"""
            p_elem = para._p
            pPr = p_elem.find(pptxQn('a:pPr'))
            if pPr is None:
                pPr = _el('a:pPr')
                p_elem.insert(0, pPr)
            pPr.set('rtl', '1')
            pPr.set('algn', algn)

        def _set_lang(run):
            r_elem = run._r
            rPr = r_elem.find(pptxQn('a:rPr'))
            if rPr is None:
                rPr = _el('a:rPr')
                r_elem.insert(0, rPr)
            rPr.set('lang', 'ar-SA')

        def tb(sl, text, l, t, w, h,
               size=16, bold=False, color=None,
               align=PP_ALIGN.RIGHT, italic=False):
            shape = sl.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h))
            tf    = shape.text_frame
            tf.word_wrap = True
            para  = tf.paragraphs[0]
            para.alignment = align
            _algn = {PP_ALIGN.RIGHT:'r', PP_ALIGN.CENTER:'ctr', PP_ALIGN.LEFT:'l'}
            _set_rtl(para, _algn.get(align,'r'))
            run = para.add_run()
            run.text        = str(text) if text else ''
            run.font.size   = Pt(size)
            run.font.bold   = bold
            run.font.italic = italic
            run.font.color.rgb = color if color else C_WHITE
            _set_lang(run)
            return shape

        def rect(sl, l, t, w, h, color, radius=False):
            from pptx.util import Inches as I
            sh = sl.shapes.add_shape(1, I(l),I(t),I(w),I(h))
            sh.fill.solid()
            sh.fill.fore_color.rgb = color
            sh.line.fill.background()
            return sh

        def top_bar(sl, color=None):
            rect(sl, 0, 0,    13.33, 0.09, color or C_BLUE)
        def bot_bar(sl, color=None):
            rect(sl, 0, 7.41, 13.33, 0.09, color or C_BLUE)

        def gradient_header(sl, title_text, subtitle='', icon='', title_color=None, bar_color=None):
            """رأس شريحة متدرّج احترافي"""
            rect(sl, 0, 0.09, 13.33, 1.05, C_CARD2)
            rect(sl, 0, 1.14, 13.33, 0.04, bar_color or C_BLUE)
            full = f"{icon}  {title_text}" if icon else title_text
            tb(sl, full, 0.4, 0.18, 12.5, 0.75,
               size=22, bold=True, color=title_color or C_ACCENT)
            if subtitle:
                tb(sl, subtitle, 0.4, 0.82, 12.5, 0.3,
                   size=12, color=C_GRAY)

        def img_into_slide(sl, b64, l, t, max_w, max_h):
            img_bytes = b64_to_bytes(b64)
            if not img_bytes: return False
            try:
                img = Image.open(BytesIO(img_bytes))
                if img.mode != 'RGB': img = img.convert('RGB')
                ow, oh = img.size
                ratio = ow / oh
                if ratio >= 1: w=min(max_w,max_h*ratio); h=w/ratio
                else:          h=min(max_h,max_w/ratio); w=h*ratio
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=85)
                buf.seek(0)
                sl.shapes.add_picture(buf, Inches(l),Inches(t),Inches(w),Inches(h))
                return True
            except Exception: return False

        def data_row(sl, label, value, y, label_color=None, value_color=None):
            """صف بيانات: قيمة + تسمية"""
            rect(sl, 0.4, y, 12.5, 0.58, C_CARD)
            rect(sl, 0.4, y+0.56, 12.5, 0.02, RGBColor(0x21,0x26,0x2d))
            tb(sl, value,  0.6,  y+0.04, 8.5, 0.5, size=16, color=value_color or C_WHITE)
            tb(sl, f":{label}", 9.3, y+0.04, 3.0, 0.5,
               size=15, bold=True, color=label_color or C_ACCENT)

        def stat_card(sl, label, value, x, y, w=3.9, h=1.5, color=None):
            rect(sl, x, y, w, h, C_CARD2)
            rect(sl, x, y, w, 0.06, color or C_BLUE)
            tb(sl, value, x, y+0.12, w, 0.85,
               size=28, bold=True, color=color or C_GREEN, align=PP_ALIGN.CENTER)
            tb(sl, label, x, y+0.95, w, 0.45,
               size=14, color=C_GRAY, align=PP_ALIGN.CENTER)

        def report_slides(lines, slide_title, t_color, icon='📊', bg_color=None):
            chunks = [lines[i:i+8] for i in range(0, len(lines), 8)]
            for ci, chunk in enumerate(chunks):
                sl = new_slide(bg_color)
                top_bar(sl, t_color)
                bot_bar(sl, t_color)
                suffix = f"  ({ci+1}/{len(chunks)})" if len(chunks) > 1 else ''
                gradient_header(sl, slide_title+suffix, icon=icon,
                                title_color=t_color, bar_color=t_color)
                y = 1.28
                for line in chunk:
                    s    = line.strip()
                    is_h = s.startswith('## ') or s.startswith('# ')
                    txt  = s.lstrip('#').strip()
                    if is_h:
                        rect(sl, 0.4, y, 12.5, 0.62, C_CARDBLU)
                        rect(sl, 0.4, y, 0.06, 0.62, t_color)
                        tb(sl, txt, 0.6, y+0.06, 12.2, 0.5,
                           size=17, bold=True, color=t_color)
                    elif s.startswith('- ') or s.startswith('• '):
                        tb(sl, '  •  '+txt, 0.6, y+0.04, 12.2, 0.55,
                           size=16, color=C_WHITE)
                    else:
                        tb(sl, txt, 0.6, y+0.06, 12.2, 0.52, size=16, color=C_WHITE)
                    y += 0.70
                    if y > 7.0: break

        # ══════════════════
        # 1. شريحة الغلاف
        # ══════════════════
        sl1 = new_slide()
        top_bar(sl1); bot_bar(sl1)
        # خلفية مزدوجة
        rect(sl1, 0, 0.09, 13.33, 7.32, C_DARK)
        rect(sl1, 0.6, 1.0, 12.13, 5.3, C_CARD)
        rect(sl1, 0.6, 1.0, 12.13, 0.08, C_BLUE)
        rect(sl1, 0.6, 6.22, 12.13, 0.08, C_BLUE)
        # شعار
        tb(sl1, "🔍", 5.9, 1.3, 1.5, 1.2, size=48, align=PP_ALIGN.CENTER)
        # العنوان
        tb(sl1, "محلل حسابات X الاستخباراتي",
           0.8, 2.5, 11.73, 0.8, size=18, color=C_GRAY, align=PP_ALIGN.CENTER)
        tb(sl1, title,
           0.8, 3.1, 11.73, 1.5, size=28, bold=True, color=C_WHITE, align=PP_ALIGN.CENTER)
        rect(sl1, 4.0, 4.65, 5.33, 0.06, C_BLUE)
        tb(sl1, f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}",
           0.8, 4.78, 11.73, 0.55, size=14, color=C_GRAY, align=PP_ALIGN.CENTER)
        tb(sl1, "Gemini AI  ·  v10.1",
           0.8, 5.4, 11.73, 0.5, size=13, color=C_ACCENT, align=PP_ALIGN.CENTER)

        # ══════════════════
        # 2. شريحة الصور
        # ══════════════════
        imgs = [i for i in (images_b64 or []) if i]
        if imgs:
            sl_img = new_slide()
            top_bar(sl_img); bot_bar(sl_img)
            if export_type == 'account':
                gradient_header(sl_img, "صورة الملف الشخصي", icon="📸",
                                title_color=C_ACCENT)
                img_into_slide(sl_img, imgs[0], 4.4, 1.4, 4.8, 5.4)
                ey = 1.4
                for ex in imgs[1:3]:
                    img_into_slide(sl_img, ex, 9.6, ey, 3.4, 2.4); ey += 2.7
                handle = f"@{data.get('screen_name','')}  –  {data.get('name','')}"
                tb(sl_img, handle, 0.4, 6.7, 12.5, 0.5,
                   size=14, color=C_GRAY, align=PP_ALIGN.CENTER)
            else:
                gradient_header(sl_img, "صور التغريدة", icon="🖼️", title_color=C_ACCENT)
                cnt   = min(len(imgs),3)
                pos_m = {
                    1:[(3.3,1.4,6.7,5.5)],
                    2:[(0.5,1.4,5.8,5.5),(6.8,1.4,5.8,5.5)],
                    3:[(0.4,1.4,3.9,5.0),(4.7,1.4,3.9,5.0),(9.0,1.4,3.9,5.0)],
                }
                for idx, pos in enumerate(pos_m[cnt]):
                    img_into_slide(sl_img, imgs[idx], *pos)
                    tb(sl_img, f"صورة {idx+1}",
                       pos[0], pos[1]+pos[3]+0.1, pos[2], 0.35,
                       size=13, color=C_GRAY, align=PP_ALIGN.CENTER)

        # ══════════════════
        # 3. شريحة تحليل الصورة ← جديد محسَّن
        # ══════════════════
        if image_analysis_text and image_analysis_text.strip():
            ia_lines = [l.strip() for l in image_analysis_text.split('\n') if l.strip()]

            # غلاف تحليل الصورة
            sl_ia_c = new_slide(RGBColor(0x06,0x14,0x2e))
            top_bar(sl_ia_c, C_TEAL); bot_bar(sl_ia_c, C_TEAL)
            rect(sl_ia_c, 1.5, 1.5, 10.33, 4.2, C_CARDBLU)
            rect(sl_ia_c, 1.5, 1.5, 10.33, 0.08, C_TEAL)
            rect(sl_ia_c, 1.5, 5.62, 10.33, 0.08, C_TEAL)
            tb(sl_ia_c, "🔬", 5.9, 1.9, 1.5, 1.0, size=44, align=PP_ALIGN.CENTER)
            tb(sl_ia_c, "تحليل الصورة بالذكاء الاصطناعي",
               1.7, 2.9, 10, 0.9, size=26, bold=True, color=C_TEAL, align=PP_ALIGN.CENTER)
            rect(sl_ia_c, 3.5, 3.88, 6.33, 0.06, C_TEAL)
            tb(sl_ia_c, "Gemini Vision  ·  OSINT Analysis",
               1.7, 4.05, 10, 0.55, size=14, color=C_GRAY, align=PP_ALIGN.CENTER)

            # شريحة جمع الصورة مع التحليل
            if imgs:
                sl_comb = new_slide(RGBColor(0x06,0x14,0x2e))
                top_bar(sl_comb, C_TEAL); bot_bar(sl_comb, C_TEAL)
                gradient_header(sl_comb, "الصورة وتحليلها", icon="🔬",
                                title_color=C_TEAL, bar_color=C_TEAL)
                # الصورة يميناً
                img_into_slide(sl_comb, imgs[0], 9.0, 1.35, 4.0, 5.6)
                # التحليل يساراً
                y = 1.35
                for line in ia_lines[:9]:
                    s   = line.strip()
                    is_h = s.startswith('## ') or s.startswith('# ')
                    txt  = s.lstrip('#').strip()
                    if is_h:
                        rect(sl_comb, 0.4, y, 8.4, 0.62, C_CARDBLU)
                        rect(sl_comb, 0.4, y, 0.07, 0.62, C_TEAL)
                        tb(sl_comb, txt, 0.55, y+0.06, 8.1, 0.5,
                           size=17, bold=True, color=C_TEAL)
                    else:
                        tb(sl_comb, txt, 0.5, y+0.06, 8.3, 0.52,
                           size=16, color=C_WHITE)
                    y += 0.70
                    if y > 6.9: break

            # بقية التحليل إن وُجد
            if len(ia_lines) > 9:
                report_slides(ia_lines[9:], "تحليل الصورة (تابع)",
                              C_TEAL, icon="🔬",
                              bg_color=RGBColor(0x06,0x14,0x2e))

        # ══════════════════
        # 4. شريحة البيانات
        # ══════════════════
        sl2 = new_slide()
        top_bar(sl2); bot_bar(sl2)

        if export_type == 'account':
            gradient_header(sl2, "بيانات الحساب", icon="👤")
            fields = [
                ('الاسم الكامل',   data.get('name',''),   C_WHITE),
                ('المعرّف',        '@'+data.get('screen_name',''), C_ACCENT),
                ('الموقع',         data.get('location',''), C_WHITE),
                ('تاريخ الانضمام', data.get('joined',''), C_GRAY),
                ('المصدر',         data.get('source',''),  C_GRAY),
            ]
            y = 1.32
            for lbl, val, col in fields:
                if val: data_row(sl2, lbl, val, y, value_color=col); y += 0.62
                if y > 4.6: break
            # إحصاءات
            sx = 0.4
            for lbl2, val2, col2 in [
                ('متابِع', format_number(data.get('followers',0)), C_GREEN),
                ('يتابع',  format_number(data.get('following',0)), C_ACCENT),
                ('تغريدة', format_number(data.get('tweets',0)),    C_WHITE),
            ]:
                stat_card(sl2, lbl2, val2, sx, 5.65, color=col2)
                sx += 4.32

            # الوصف إن كان قصيراً
            bio = data.get('bio','')
            if bio and y < 4.7:
                rect(sl2, 0.4, y, 12.5, 0.85, C_CARD2)
                bio_s = bio[:180] + ('…' if len(bio)>180 else '')
                tb(sl2, bio_s, 0.55, y+0.1, 12.2, 0.7, size=14, color=C_GRAY)

        else:
            gradient_header(sl2, "بيانات التغريدة", icon="🐦")
            fields = [
                ('المؤلف',  data.get('author_name',''),   C_WHITE),
                ('المعرّف', '@'+data.get('author_handle',''), C_ACCENT),
                ('التاريخ', data.get('date',''),           C_GRAY),
                ('المصدر',  data.get('data_source',''),   C_GRAY),
            ]
            y = 1.32
            for lbl, val, col in fields:
                if val: data_row(sl2, lbl, val, y, value_color=col); y += 0.62
            # إحصاءات
            sx = 0.4
            for lbl2, val2, col2 in [
                ('إعجاب',  format_number(data.get('likes',0)),    C_GREEN),
                ('إعادة',  format_number(data.get('retweets',0)), C_ACCENT),
                ('رد',      format_number(data.get('replies',0)),  C_ORANGE),
            ]:
                stat_card(sl2, lbl2, val2, sx, 5.65, color=col2)
                sx += 4.32
            # نص التغريدة
            tw = data.get('text','')
            if tw and y < 4.8:
                rect(sl2, 0.4, y, 12.5, 1.4, C_CARDBLU)
                tw_s = tw[:240] + ('…' if len(tw)>240 else '')
                tb(sl2, tw_s, 0.55, y+0.12, 12.2, 1.15, size=16, color=C_WHITE)

        # ══════════════════
        # 5. شرائح التقرير
        # ══════════════════
        if report_text and report_text.strip():
            rlines = [l.strip() for l in report_text.split('\n') if l.strip()]
            report_slides(rlines, "تقرير التحليل الاستخباراتي", C_ACCENT, icon="📊")

        # ══════════════════
        # 6. شريحة الخاتمة
        # ══════════════════
        sl_end = new_slide()
        top_bar(sl_end); bot_bar(sl_end)
        rect(sl_end, 2.0, 1.6, 9.33, 4.0, C_CARD)
        rect(sl_end, 2.0, 1.6, 9.33, 0.08, C_BLUE)
        rect(sl_end, 2.0, 5.52, 9.33, 0.08, C_BLUE)
        tb(sl_end, "✅", 6.0, 1.9, 1.3, 1.1, size=44, align=PP_ALIGN.CENTER)
        tb(sl_end, "انتهى التقرير",
           2.0, 2.95, 9.33, 1.0, size=34, bold=True,
           color=C_ACCENT, align=PP_ALIGN.CENTER)
        rect(sl_end, 4.0, 4.0, 5.33, 0.06, C_BLUE)
        tb(sl_end, "محلل حسابات X الاستخباراتي",
           2.0, 4.15, 9.33, 0.55, size=15, color=C_WHITE, align=PP_ALIGN.CENTER)
        tb(sl_end, "Gemini AI  ·  v10.1",
           2.0, 4.8, 9.33, 0.5, size=13, color=C_GRAY, align=PP_ALIGN.CENTER)

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
    image_analysis_text: str = '',
):
    st.markdown('<div class="section-title">📥 تصدير التقرير الكامل</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="export-section">', unsafe_allow_html=True)

    parts = []
    if images_b64:          parts.append(f"🖼️ {len([i for i in images_b64 if i])} صورة")
    if image_analysis_text: parts.append("🔬 تحليل الصورة")
    if report_text:         parts.append("📊 تقرير التحليل")
    if parts:
        st.markdown(f'<div class="info-box">📦 يتضمن التقرير: {" | ".join(parts)}</div>',
                    unsafe_allow_html=True)

    safe_t    = re.sub(r'[^\w\s-]','',title)[:30].strip().replace(' ','_')
    ts        = datetime.now().strftime('%Y%m%d_%H%M')
    base_name = f"X_Report_{safe_t}_{ts}"

    c1,c2,c3 = st.columns(3)
    with c1:
        docx_b = export_to_word(title,data,report_text,export_type,images_b64,image_analysis_text)
        if docx_b:
            st.download_button("📄 تحميل Word", docx_b,
                f"{base_name}.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"docx_{ts}")
    with c2:
        pptx_b = export_to_pptx(title,data,report_text,export_type,images_b64,image_analysis_text)
        if pptx_b:
            st.download_button("📊 تحميل PowerPoint", pptx_b,
                f"{base_name}.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key=f"pptx_{ts}")
    with c3:
        full_txt = ''
        if report_text:         full_txt += f"=== تقرير التحليل ===\n{report_text}\n\n"
        if image_analysis_text: full_txt += f"=== تحليل الصورة ===\n{image_analysis_text}\n"
        if full_txt:
            st.download_button("📝 تحميل TXT", full_txt.encode('utf-8'),
                f"{base_name}.txt", "text/plain", key=f"txt_{ts}")

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
    loc_span  = f'<span>📍 {loc}</span>'  if loc else ''
    join_span = f'<span>📅 {jnd}</span>'  if jnd else ''
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
    c1,c2 = st.columns([3,1])
    with c1: fetch_btn = st.button("🔍 جلب بيانات الحساب", key='fetch_account')
    with c2:
        if st.button("🗑️ مسح", key='clear_account'):
            for k in ['account_data','account_report','account_img_analysis']:
                st.session_state.pop(k,None)
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
                    mj=st.text_input("الانضمام",key='m_j'); mb=st.text_area("الوصف",key='m_b',height=80)
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

            if gemini_key and featured_b64:
                st.markdown('<div class="section-title">🔬 تحليل صورة الحساب</div>',
                            unsafe_allow_html=True)
                ap_acc = st.selectbox("نقطة التحليل", IMAGE_ANALYSIS_POINTS, key='acc_img_point')
                if st.button("🔬 تحليل صورة الحساب", key='analyze_acc_img'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        pt = f"""أنت خبير تحليل بصري واستخباراتي.
قم بـ: **{ap_acc}**
- تحليل دقيق ومفصّل | اذكر كل التفاصيل | كن موضوعياً | اكتب بالعربية"""
                        with st.spinner("🤖 جاري تحليل الصورة..."):
                            result = gemini_with_images(model, pt, [featured_b64])
                            st.session_state['account_img_analysis'] = result

            if 'account_img_analysis' in st.session_state:
                ia = st.session_state['account_img_analysis']
                st.markdown(
                    f'<div class="img-analysis-section" dir="rtl">{safe_html_lines(ia)}</div>',
                    unsafe_allow_html=True
                )

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
الاسم: {data.get('name','')} | المعرّف: @{data.get('screen_name','')}
الوصف: {data.get('bio','')} | المتابِعون: {format_number(data.get('followers',0))}
يتابع: {format_number(data.get('following',0))} | التغريدات: {format_number(data.get('tweets',0))}
الموقع: {data.get('location','')} | الانضمام: {data.get('joined','')}

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
                            report = gemini_with_images(model,prompt,imgs_ai) if imgs_ai else gemini_text(model,prompt)
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
                    f"تقرير حساب @{data.get('screen_name','unknown')}",
                    data, rpt, 'account', export_imgs,
                    st.session_state.get('account_img_analysis','')
                )


# ─── تبويب تحليل التغريدة ─────────────────────────────────────

def tweet_tab(gemini_key: str, gemini_model_name: str):
    st.markdown('<div class="section-title">🐦 تحليل تغريدة</div>', unsafe_allow_html=True)
    tweet_input = st.text_input(
        "رابط أو معرّف التغريدة",
        placeholder="https://x.com/user/status/1234567890123456789",
        key='tweet_url_input'
    )
    c1,c2 = st.columns([3,1])
    with c1: fetch_btn = st.button("🔍 جلب بيانات التغريدة", key='fetch_tweet')
    with c2:
        if st.button("🗑️ مسح", key='clear_tweet'):
            for k in ['tweet_data','tweet_report','tweet_media_b64','tweet_img_analysis']:
                st.session_state.pop(k,None)
            st.rerun()

    if fetch_btn and tweet_input:
        if re.search(r'(?:twitter|x)\.com/[A-Za-z0-9_]+$', tweet_input):
            st.markdown(
                '<div class="warning-box">⚠️ هذا رابط <b>حساب</b>! استخدم تبويب <b>👤 تحليل حساب X</b></div>',
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
                    mb64 = []
                    for murl in tdata.get('media_urls',[])[:3]:
                        b64 = url_to_base64(murl)
                        if b64: mb64.append(b64)
                    st.session_state['tweet_media_b64'] = mb64

    if 'tweet_data' in st.session_state:
        td = st.session_state['tweet_data']
        if 'error' in td:
            err = escape_html(td['error'])
            st.markdown(f'<div class="error-box">❌ {err}</div>', unsafe_allow_html=True)
            with st.expander("✏️ إدخال يدوي"):
                mt = st.text_area("نص التغريدة",key='mt_text',height=120)
                mc1,mc2 = st.columns(2)
                with mc1:
                    ma=st.text_input("اسم المؤلف",key='mt_a'); mh=st.text_input("المعرّف",key='mt_h')
                    md=st.text_input("التاريخ",key='mt_d')
                with mc2:
                    ml=st.text_input("الإعجابات",key='mt_l'); mr=st.text_input("الإعادات",key='mt_r')
                    mp=st.text_input("الردود",key='mt_p')
                if st.button("💾 حفظ",key='save_tweet_manual'):
                    st.session_state['tweet_data'] = {
                        'text':mt,'author_name':ma,'author_handle':mh.lstrip('@'),
                        'date':md,'likes':ml,'retweets':mr,'replies':mp,
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
            lang_s   = f'<div class="tweet-stat">🌐 {lang_v}</div>' if lang_v else ''
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
                    {lang_s}
                </div>
            </div>
            """, unsafe_allow_html=True)

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

            st.markdown('<div class="section-title">🔬 رفع صور للتحليل</div>',
                        unsafe_allow_html=True)
            uploaded_imgs = st.file_uploader(
                "ارفع صور للتحليل",
                type=['jpg','jpeg','png','webp'],
                accept_multiple_files=True, key='tweet_images'
            )
            all_imgs_b64 = list(tweet_media_b64)
            for uf in (uploaded_imgs or []):
                try:
                    b64 = pil_to_base64(Image.open(uf))
                    if b64: all_imgs_b64.append(b64)
                except Exception: pass

            ap_sel = st.selectbox("نقطة التحليل", IMAGE_ANALYSIS_POINTS, key='ap_select')

            if all_imgs_b64 and gemini_key:
                if st.button("🔬 تحليل الصور وحفظ للتصدير", key='analyze_imgs'):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        pt = f"""أنت خبير تحليل بصري واستخباراتي.
قم بـ: **{ap_sel}**
- تحليل دقيق ومفصّل | اذكر كل التفاصيل | كن موضوعياً | اكتب بالعربية"""
                        with st.spinner("🤖 جاري تحليل الصور..."):
                            result = gemini_with_images(model, pt, all_imgs_b64[:4])
                            st.session_state['tweet_img_analysis'] = result

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
التاريخ: {td.get('date','')} | الإعجابات: {td.get('likes',0)} | الإعادات: {td.get('retweets',0)}

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
                export_imgs = list(tweet_media_b64)
                for uf in (uploaded_imgs or []):
                    try:
                        b64 = pil_to_base64(Image.open(uf))
                        if b64 and b64 not in export_imgs: export_imgs.append(b64)
                    except Exception: pass
                render_export_buttons(
                    f"تحليل تغريدة @{td.get('author_handle','unknown')}",
                    td, t_rpt, 'tweet', export_imgs[:4],
                    st.session_state.get('tweet_img_analysis','')
                )


# ─── الشريط الجانبي ───────────────────────────────────────────

def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:16px 0;">
            <div style="font-size:2.5rem;">🔍</div>
            <h2 style="color:#58a6ff;margin:8px 0;font-size:1.3rem;">محلل حسابات X</h2>
            <p style="color:#8b949e;font-size:.85rem;">v10.1 | Gemini 2.5</p>
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
        ✅ <b>Word / PPTX</b> – تصدير مع الصور<br>
        ⚠️ <em>twikit معطّل مؤقتاً</em>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.checkbox("🐛 وضع التشخيص", key='debug_mode', value=False)
        st.markdown("---")
        st.markdown("""
        <div style="text-align:center;color:#8b949e;font-size:.8rem;">
            محلل حسابات X | v10.1 | 2025
        </div>
        """, unsafe_allow_html=True)
    return gemini_key, selected_model


# ─── الدالة الرئيسية ──────────────────────────────────────────

def main():
    st.markdown("""
    <div style="text-align:center;padding:20px 0 10px;direction:rtl;">
        <h1 style="color:#58a6ff;font-size:2rem;margin:0;">🔍 محلل حسابات X الاستخباراتي</h1>
        <p style="color:#8b949e;font-size:1rem;margin:8px 0 0;">
            Gemini 2.5 | Word | PowerPoint | تحليل بصري متقدم
        </p>
    </div>
    """, unsafe_allow_html=True)
    gemini_key, model_name = render_sidebar()
    tab1, tab2 = st.tabs(["👤 تحليل حساب X", "🐦 تحليل تغريدة"])
    with tab1: account_tab(gemini_key, model_name)
    with tab2: tweet_tab(gemini_key, model_name)


if __name__ == "__main__":
    main()
