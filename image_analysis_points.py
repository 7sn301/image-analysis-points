# ============================================================
# محلل حسابات X  - v9.7
# جديد: تصدير Word + PowerPoint + إصلاح اتجاه النص
# ============================================================

import streamlit as st
import requests
import re
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image
from bs4 import BeautifulSoup
import html as html_module

st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
* { font-family: 'Cairo', sans-serif !important; }
.stApp {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    color: #e6edf3; direction: rtl;
}
.main .block-container { padding: 1.5rem 2rem; max-width: 1200px; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    border-left: 1px solid #30363d;
}
[data-testid="stSidebar"] * { direction: rtl; text-align: right; }
.stButton > button {
    background: linear-gradient(135deg, #238636, #2ea043);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 0.5rem 1.2rem;
    transition: all 0.2s; width: 100%;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2ea043, #3fb950);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(46,160,67,0.4);
}
.stTextInput input, .stTextArea textarea {
    background: #21262d !important; color: #e6edf3 !important;
    border: 1px solid #30363d !important; border-radius: 8px !important;
    direction: rtl !important; text-align: right !important;
}
.featured-image-container {
    width: 100%; border-radius: 16px; overflow: hidden;
    margin-bottom: 1.5rem; border: 2px solid #30363d;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5); max-height: 420px;
}
.featured-image-container img { width:100%; object-fit:cover; display:block; }
.upload-hint {
    border: 2px dashed #30363d; border-radius: 12px; padding: 1.2rem;
    text-align: center; color: #8b949e; margin: 0.5rem 0;
    background: rgba(255,255,255,0.02);
}
.profile-header {
    background: linear-gradient(135deg, #161b22, #21262d);
    border: 1px solid #30363d; border-radius: 16px;
    padding: 1.5rem; margin: 0.5rem 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.info-box    { background:rgba(56,139,253,0.1);  border:1px solid #1f6feb;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; text-align:right; }
.success-box { background:rgba(46,160,67,0.1);   border:1px solid #238636;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; text-align:right; }
.error-box   { background:rgba(248,81,73,0.1);   border:1px solid #da3633;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; text-align:right; }
.warning-box { background:rgba(210,153,34,0.1);  border:1px solid #d29922;  border-radius:10px; padding:1rem; margin:0.5rem 0; direction:rtl; text-align:right; }
.report-section {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.8rem;
    margin: 1rem 0;
    direction: rtl !important;
    text-align: right !important;
    line-height: 2.0;
    white-space: pre-wrap;
    unicode-bidi: embed;
}
.export-bar {
    display: flex;
    gap: 0.8rem;
    margin-top: 1rem;
    flex-wrap: wrap;
    justify-content: flex-end;
}
.stTabs [data-baseweb="tab-list"] {
    background: #161b22; border-radius: 10px;
    padding: 4px; gap: 4px; border: 1px solid #30363d;
}
.stTabs [data-baseweb="tab"] {
    color: #8b949e; border-radius: 8px;
    padding: 8px 20px; font-weight: 600;
}
.stTabs [aria-selected="true"] { background: #238636 !important; color: white !important; }
[data-testid="stMetric"] {
    background: #21262d; border: 1px solid #30363d;
    border-radius: 10px; padding: 0.8rem;
}
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# الثوابت
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

NITTER_MIRRORS = [
    "https://nitter.privacyredirect.com",
    "https://xcancel.com",
    "https://nitter.poast.org",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.space",
    "https://nuku.trabun.org",
    "https://lightbrd.com",
    "https://nitter.kareem.one",
    "https://nitter.net",
]

FXTWITTER_API = "https://api.fxtwitter.com"

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]

IMAGE_ANALYSIS_POINTS = [
    "الموقع الجغرافي أو المؤشرات المكانية",
    "الأشخاص والهويات المرئية",
    "المعدات والتجهيزات الظاهرة",
    "المركبات وأرقام اللوحات",
    "العلامات والشعارات والنصوص",
    "الزمن والمناخ والإضاءة",
    "البنية التحتية والمنشآت",
    "الأنشطة والتجمعات البشرية",
    "الدلالات الأمنية والاستخباراتية",
    "التناقضات والعناصر غير العادية",
]

# ──────────────────────────────────────────────
# دوال مساعدة
# ──────────────────────────────────────────────
def safe_text(text: str) -> str:
    if not text:
        return ""
    text = BeautifulSoup(str(text), "html.parser").get_text()
    return re.sub(r'\s+', ' ', text).strip()

def escape_html(text: str) -> str:
    return html_module.escape(str(text)) if text else ""

def extract_username(s: str) -> str:
    s = s.strip()
    m = re.search(r'(?:twitter|x)\.com/([A-Za-z0-9_]+)', s)
    if m:
        return m.group(1)
    return s.lstrip("@")

def extract_tweet_id(s: str) -> str:
    s = s.strip()
    m = re.search(r'/status/(\d+)', s)
    if m:
        return m.group(1)
    if s.isdigit():
        return s
    return ""

def format_number(n) -> str:
    try:
        raw = str(n).replace(",", "").replace(" ", "")
        val = int(float(raw))
        if val >= 1_000_000:
            return f"{val/1_000_000:.1f}M"
        if val >= 1_000:
            return f"{val/1_000:.1f}K"
        return str(val)
    except:
        return str(n) if n else "0"

def format_date(d: str) -> str:
    if not d:
        return ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(d, fmt).strftime("%d/%m/%Y %H:%M")
        except:
            pass
    return str(d)[:16]

def pil_to_base64(img: Image.Image) -> str:
    if img.mode in ("RGBA", "P", "LA", "CMYK"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

def url_to_base64(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENTS[0]}, timeout=10)
        if r.status_code == 200:
            return pil_to_base64(Image.open(BytesIO(r.content)))
    except:
        pass
    return ""

# ──────────────────────────────────────────────
# تصدير Word
# ──────────────────────────────────────────────
def export_to_word(title: str, data: dict, report_text: str, report_type: str = "account") -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement

        doc = Document()

        # إعداد اتجاه RTL للصفحة
        section = doc.sections[0]
        section.page_width  = Inches(11.69)
        section.page_height = Inches(8.27)

        def set_rtl(paragraph):
            pPr = paragraph._p.get_or_add_pPr()
            bidi = OxmlElement('w:bidi')
            pPr.append(bidi)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        def add_rtl_para(doc, text, bold=False, size=12, color=None):
            p = doc.add_paragraph()
            set_rtl(p)
            run = p.add_run(text)
            run.bold = bold
            run.font.size = Pt(size)
            if color:
                run.font.color.rgb = RGBColor(*color)
            return p

        # العنوان الرئيسي
        add_rtl_para(doc, "🔍 محلل حسابات X الاستخباراتي", bold=True, size=20, color=(88,166,255))
        add_rtl_para(doc, f"تقرير: {title}", bold=True, size=16)
        add_rtl_para(doc, f"التاريخ: {datetime.now().strftime('%d/%m/%Y %H:%M')}", size=10, color=(139,148,158))
        doc.add_paragraph()

        # بيانات الحساب أو التغريدة
        add_rtl_para(doc, "═" * 50, size=10, color=(48,54,61))

        if report_type == "account":
            add_rtl_para(doc, "📋 بيانات الحساب", bold=True, size=14, color=(63,185,80))
            fields = [
                ("الاسم",          data.get("name","")),
                ("المعرّف",        f"@{data.get('screen_name','')}"),
                ("المتابعون",      format_number(data.get("followers_count",0))),
                ("يتابع",          format_number(data.get("following_count",0))),
                ("التغريدات",      format_number(data.get("tweet_count",0))),
                ("الموقع",         data.get("location","")),
                ("تاريخ الإنشاء", format_date(data.get("created_at",""))),
                ("النبذة",         data.get("description","")),
                ("موثّق",          "نعم ✅" if data.get("verified") else "لا"),
            ]
        else:
            add_rtl_para(doc, "📋 بيانات التغريدة", bold=True, size=14, color=(63,185,80))
            fields = [
                ("المؤلف",        data.get("author_name","")),
                ("المعرّف",       f"@{data.get('author_screen_name','')}"),
                ("النص",          data.get("text","")),
                ("الإعجابات",     format_number(data.get("likes",0))),
                ("إعادة النشر",   format_number(data.get("retweets",0))),
                ("الردود",        format_number(data.get("replies",0))),
                ("المشاهدات",     format_number(data.get("views",0))),
                ("التاريخ",       format_date(data.get("created_at",""))),
            ]

        for label, value in fields:
            if value:
                p = doc.add_paragraph()
                set_rtl(p)
                run_label = p.add_run(f"{label}: ")
                run_label.bold = True
                run_label.font.size = Pt(11)
                run_label.font.color.rgb = RGBColor(88,166,255)
                run_value = p.add_run(str(value))
                run_value.font.size = Pt(11)

        doc.add_paragraph()
        add_rtl_para(doc, "═" * 50, size=10, color=(48,54,61))

        # التقرير
        add_rtl_para(doc, "🤖 التقرير الاستخباراتي", bold=True, size=14, color=(63,185,80))
        doc.add_paragraph()

        for line in report_text.split('\n'):
            line = line.strip()
            if not line:
                doc.add_paragraph()
                continue
            is_heading = line.startswith(('1.','2.','3.','4.','5.','6.','7.','8.','9.','#','##','###'))
            add_rtl_para(doc, line, bold=is_heading, size=11 if not is_heading else 12)

        # تذييل
        doc.add_paragraph()
        add_rtl_para(doc, "─" * 50, size=9, color=(48,54,61))
        add_rtl_para(doc, "تم إنشاؤه بواسطة: محلل حسابات X الاستخباراتي v9.7", size=9, color=(139,148,158))

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ في تصدير Word: {e}")
        return None

# ──────────────────────────────────────────────
# تصدير PowerPoint
# ──────────────────────────────────────────────
def export_to_pptx(title: str, data: dict, report_text: str, report_type: str = "account") -> bytes:
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.oxml.ns import qn

        prs = Presentation()
        prs.slide_width  = Inches(13.33)
        prs.slide_height = Inches(7.5)

        DARK_BG    = RGBColor(13,  17, 23)
        CARD_BG    = RGBColor(22,  27, 34)
        GREEN      = RGBColor(63, 185, 80)
        BLUE       = RGBColor(88, 166,255)
        LIGHT      = RGBColor(230,237,243)
        GRAY       = RGBColor(139,148,158)
        BORDER     = RGBColor(48,  54, 61)

        blank = prs.slide_layouts[6]

        def add_slide_bg(slide):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = DARK_BG

        def add_textbox(slide, text, left, top, width, height,
                        size=18, bold=False, color=LIGHT,
                        align=PP_ALIGN.RIGHT, wrap=True):
            txBox = slide.shapes.add_textbox(
                Inches(left), Inches(top), Inches(width), Inches(height)
            )
            tf = txBox.text_frame
            tf.word_wrap = wrap
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = "Cairo"
            # RTL
            pPr = p._p.get_or_add_pPr()
            pPr.set(qn('a:rtl'), '1')
            return txBox

        def add_rect(slide, left, top, width, height, fill_color, alpha=None):
            shape = slide.shapes.add_shape(
                1,
                Inches(left), Inches(top), Inches(width), Inches(height)
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill_color
            shape.line.fill.background()
            return shape

        # ── الشريحة 1: الغلاف ──
        s1 = prs.slides.add_slide(blank)
        add_slide_bg(s1)
        add_rect(s1, 0, 2.8, 13.33, 0.08, GREEN)
        add_textbox(s1, "🔍 محلل حسابات X الاستخباراتي",
                    0.5, 1.0, 12.0, 1.2, size=36, bold=True, color=BLUE)
        add_textbox(s1, title,
                    0.5, 2.2, 12.0, 0.8, size=24, bold=True, color=LIGHT)
        add_textbox(s1, f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    0.5, 3.2, 12.0, 0.6, size=16, color=GRAY)
        add_textbox(s1, "v9.7 — أداة تحليل استخباراتي",
                    0.5, 6.5, 12.0, 0.6, size=13, color=GRAY)

        # ── الشريحة 2: بيانات الحساب/التغريدة ──
        s2 = prs.slides.add_slide(blank)
        add_slide_bg(s2)
        add_rect(s2, 0.3, 0.2, 12.73, 1.0, CARD_BG)
        add_textbox(s2, "📋 البيانات الأساسية",
                    0.5, 0.3, 10.0, 0.7, size=22, bold=True, color=GREEN)

        if report_type == "account":
            fields = [
                (f"👤 الاسم: {data.get('name','')}",
                 f"🆔 المعرّف: @{data.get('screen_name','')}"),
                (f"👥 المتابعون: {format_number(data.get('followers_count',0))}",
                 f"➡️ يتابع: {format_number(data.get('following_count',0))}"),
                (f"🐦 التغريدات: {format_number(data.get('tweet_count',0))}",
                 f"📍 الموقع: {data.get('location','')}"),
                (f"📅 الإنشاء: {format_date(data.get('created_at',''))}",
                 f"✅ موثّق: {'نعم' if data.get('verified') else 'لا'}"),
            ]
        else:
            fields = [
                (f"✍️ المؤلف: {data.get('author_name','')}",
                 f"🆔 المعرّف: @{data.get('author_screen_name','')}"),
                (f"❤️ إعجابات: {format_number(data.get('likes',0))}",
                 f"🔁 إعادة نشر: {format_number(data.get('retweets',0))}"),
                (f"💬 ردود: {format_number(data.get('replies',0))}",
                 f"👁 مشاهدات: {format_number(data.get('views',0))}"),
                (f"📅 التاريخ: {format_date(data.get('created_at',''))}",
                 ""),
            ]

        y = 1.4
        for left_text, right_text in fields:
            add_rect(s2, 0.3, y, 12.73, 0.65, CARD_BG)
            add_textbox(s2, left_text,  0.5, y+0.05, 5.8, 0.55, size=14, color=LIGHT)
            if right_text:
                add_textbox(s2, right_text, 6.8, y+0.05, 5.8, 0.55, size=14, color=LIGHT)
            y += 0.72

        if report_type == "account" and data.get("description"):
            desc = data.get("description","")[:200]
            add_textbox(s2, f"📝 النبذة: {desc}", 0.5, y+0.1, 12.0, 0.8, size=13, color=GRAY)

        # ── شرائح التقرير (كل 8 أسطر = شريحة) ──
        lines = [l.strip() for l in report_text.split('\n') if l.strip()]
        chunks = [lines[i:i+8] for i in range(0, len(lines), 8)]

        for idx, chunk in enumerate(chunks):
            s = prs.slides.add_slide(blank)
            add_slide_bg(s)
            add_rect(s, 0.3, 0.15, 12.73, 0.9, CARD_BG)
            slide_title = "🤖 التقرير الاستخباراتي" if idx == 0 else f"📄 تابع... ({idx+1})"
            add_textbox(s, slide_title, 0.5, 0.2, 12.0, 0.7, size=20, bold=True, color=GREEN)

            y = 1.2
            for line in chunk:
                is_heading = bool(re.match(r'^[\d]+\.', line)) or line.startswith('#')
                col = BLUE if is_heading else LIGHT
                sz  = 15 if is_heading else 13
                bold = is_heading
                add_rect(s, 0.3, y, 12.73, 0.58, CARD_BG)
                add_textbox(s, line, 0.5, y+0.04, 12.0, 0.52,
                            size=sz, bold=bold, color=col)
                y += 0.62

            # رقم الشريحة
            add_textbox(s, f"{idx+2} / {len(chunks)+1}",
                        11.5, 7.1, 1.5, 0.3, size=10, color=GRAY, align=PP_ALIGN.LEFT)

        # ── الشريحة الأخيرة: الخاتمة ──
        last = prs.slides.add_slide(blank)
        add_slide_bg(last)
        add_rect(last, 0, 3.0, 13.33, 0.08, GREEN)
        add_textbox(last, "✅ انتهى التقرير",
                    0.5, 1.5, 12.0, 1.0, size=32, bold=True, color=GREEN)
        add_textbox(last, "محلل حسابات X الاستخباراتي v9.7",
                    0.5, 2.7, 12.0, 0.6, size=16, color=GRAY)
        add_textbox(last, f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    0.5, 3.4, 12.0, 0.5, size=13, color=GRAY)

        buf = BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        st.error(f"❌ خطأ في تصدير PowerPoint: {e}")
        return None

# ──────────────────────────────────────────────
# أزرار التصدير
# ──────────────────────────────────────────────
def render_export_buttons(title: str, data: dict, report_text: str,
                           report_type: str = "account", key_prefix: str = "acc"):
    st.markdown("---")
    st.markdown("#### 📤 تصدير التقرير")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📄 تصدير Word (.docx)", key=f"{key_prefix}_export_word", use_container_width=True):
            with st.spinner("⏳ جارٍ إنشاء ملف Word..."):
                docx_bytes = export_to_word(title, data, report_text, report_type)
                if docx_bytes:
                    st.download_button(
                        label="⬇️ تحميل Word",
                        data=docx_bytes,
                        file_name=f"تقرير_{title}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"{key_prefix}_dl_word",
                        use_container_width=True
                    )

    with col2:
        if st.button("📊 تصدير PowerPoint (.pptx)", key=f"{key_prefix}_export_pptx", use_container_width=True):
            with st.spinner("⏳ جارٍ إنشاء عرض PowerPoint..."):
                pptx_bytes = export_to_pptx(title, data, report_text, report_type)
                if pptx_bytes:
                    st.download_button(
                        label="⬇️ تحميل PowerPoint",
                        data=pptx_bytes,
                        file_name=f"عرض_{title}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        key=f"{key_prefix}_dl_pptx",
                        use_container_width=True
                    )

    with col3:
        txt_bytes = report_text.encode("utf-8")
        st.download_button(
            label="📝 تصدير نص (.txt)",
            data=txt_bytes,
            file_name=f"تقرير_{title}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            key=f"{key_prefix}_dl_txt",
            use_container_width=True
        )

# ──────────────────────────────────────────────
# Nitter
# ──────────────────────────────────────────────
def fetch_nitter(username: str, debug: bool = False) -> dict | None:
    headers = {
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ar,en;q=0.9",
    }
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{username}"
        try:
            r = requests.get(url, headers=headers, timeout=14)
            if r.status_code != 200:
                if debug: st.caption(f"⚠️ {mirror}: HTTP {r.status_code}")
                continue
            txt = r.text
            if any(x in txt.lower() for x in ["anubis","checking your browser","ddos-guard"]):
                if debug: st.caption(f"⚠️ {mirror}: Bot Protection")
                continue
            soup = BeautifulSoup(txt, "html.parser")
            name_el   = soup.select_one(".profile-card-fullname, .fullname, h1.fullname")
            screen_el = soup.select_one(".profile-card-username, .username")
            bio_el    = soup.select_one(".profile-bio p, .bio p, .profile-bio")
            stats     = soup.select(".profile-stat-num, .stats .stat-num, .profile-stat .profile-stat-num")
            img_el    = soup.select_one(".profile-card-avatar img, .avatar img, .profile-avatar img")
            if not name_el:
                if debug: st.caption(f"⚠️ {mirror}: لم يُعثر على اسم")
                continue
            profile_img = ""
            if img_el and img_el.get("src"):
                src = img_el["src"]
                profile_img = (mirror + src) if src.startswith("/") else src
            data = {
                "name":            safe_text(name_el.get_text()),
                "screen_name":     safe_text(screen_el.get_text()).lstrip("@") if screen_el else username,
                "description":     safe_text(bio_el.get_text()) if bio_el else "",
                "followers_count": safe_text(stats[0].get_text()) if len(stats)>0 else "0",
                "following_count": safe_text(stats[1].get_text()) if len(stats)>1 else "0",
                "tweet_count":     safe_text(stats[2].get_text()) if len(stats)>2 else "0",
                "profile_image_url": profile_img,
                "location": "", "verified": False, "created_at": "",
                "source": f"Nitter ({mirror})",
            }
            if debug: st.caption(f"✅ {mirror}: نجح الجلب")
            return data
        except Exception as e:
            if debug: st.caption(f"❌ {mirror}: {e}")
            continue
    return None

# ──────────────────────────────────────────────
# FxTwitter
# ──────────────────────────────────────────────
def fetch_fxtwitter(tweet_id: str) -> dict | None:
    try:
        r = requests.get(f"{FXTWITTER_API}/status/{tweet_id}", timeout=15)
        if r.status_code != 200: return None
        tw = r.json().get("tweet", {})
        if not tw: return None
        author = tw.get("author", {})
        return {
            "id": tweet_id,
            "text": safe_text(tw.get("text","")),
            "created_at": tw.get("created_at",""),
            "likes": tw.get("likes",0), "retweets": tw.get("retweets",0),
            "replies": tw.get("replies",0), "views": tw.get("views",0),
            "author_name": safe_text(author.get("name","")),
            "author_screen_name": safe_text(author.get("screen_name","")),
            "author_avatar": author.get("avatar_url",""),
            "media_photos": tw.get("media",{}).get("photos",[]),
            "source": "FxTwitter",
        }
    except: return None

# ──────────────────────────────────────────────
# Gemini
# ──────────────────────────────────────────────
def get_gemini_model(api_key: str, model_name: str):
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"❌ خطأ Gemini: {e}")
        return None

def gemini_text(model, prompt: str) -> str:
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"❌ خطأ: {e}"

def gemini_with_images(model, prompt: str, images_b64: list) -> str:
    try:
        parts = [prompt]
        for b64 in images_b64:
            parts.append({"mime_type": "image/jpeg", "data": b64})
        return model.generate_content(parts).text
    except Exception as e:
        return f"❌ خطأ: {e}"

# ──────────────────────────────────────────────
# بطاقة الملف الشخصي
# ──────────────────────────────────────────────
def render_profile_card(data: dict, featured_b64: str = None):
    if featured_b64:
        st.markdown(
            f'<div class="featured-image-container">'
            f'<img src="data:image/jpeg;base64,{featured_b64}" alt="صورة الحساب">'
            f'</div>', unsafe_allow_html=True
        )
    name        = escape_html(data.get("name","غير معروف"))
    screen_name = escape_html(data.get("screen_name",""))
    description = escape_html(data.get("description",""))
    location    = escape_html(data.get("location",""))
    created     = escape_html(format_date(data.get("created_at","")))
    source      = escape_html(data.get("source",""))
    verified    = data.get("verified",False)
    profile_url = data.get("profile_image_url","")
    followers   = format_number(data.get("followers_count",0))
    following   = format_number(data.get("following_count",0))
    tweets      = format_number(data.get("tweet_count",0))
    avatar_html = ""
    if profile_url:
        b64 = url_to_base64(profile_url)
        if b64:
            avatar_html = (f'<img src="data:image/jpeg;base64,{b64}" '
                           f'style="width:75px;height:75px;border-radius:50%;'
                           f'border:3px solid #238636;margin-left:1rem;flex-shrink:0;">')
    badge    = "✅ " if verified else ""
    loc_html = (f'<div style="color:#8b949e;font-size:0.85rem;margin-top:2px;">📍 {location}</div>' if location else "")
    bio_html = (f'<div style="color:#c9d1d9;line-height:1.7;margin-bottom:0.8rem;'
                f'word-break:break-word;text-align:right;">{description}</div>' if description else "")
    date_html = (f'<div style="color:#8b949e;font-size:0.8rem;text-align:center;margin-top:0.8rem;">'
                 f'📅 انضم: {created}</div>' if created else "")
    st.markdown(f"""
<div class="profile-header">
  <div style="display:flex;align-items:center;margin-bottom:0.8rem;">
    {avatar_html}
    <div style="flex:1;min-width:0;text-align:right;">
      <div style="color:#e6edf3;font-size:1.3rem;font-weight:700;">{badge}{name}</div>
      <div style="color:#58a6ff;font-size:0.95rem;">@{screen_name}</div>
      {loc_html}
    </div>
  </div>
  {bio_html}
  <hr style="border:none;border-top:1px solid #30363d;margin:0.8rem 0;">
  <div style="display:flex;gap:0.8rem;flex-wrap:wrap;justify-content:center;">
    <div style="background:#0d1117;border:1px solid #238636;border-radius:10px;padding:0.8rem 1.2rem;text-align:center;min-width:90px;">
      <div style="font-size:1.6rem;font-weight:700;color:#3fb950;">{followers}</div>
      <div style="font-size:0.8rem;color:#8b949e;">متابع</div>
    </div>
    <div style="background:#0d1117;border:1px solid #238636;border-radius:10px;padding:0.8rem 1.2rem;text-align:center;min-width:90px;">
      <div style="font-size:1.6rem;font-weight:700;color:#3fb950;">{following}</div>
      <div style="font-size:0.8rem;color:#8b949e;">يتابع</div>
    </div>
    <div style="background:#0d1117;border:1px solid #238636;border-radius:10px;padding:0.8rem 1.2rem;text-align:center;min-width:90px;">
      <div style="font-size:1.6rem;font-weight:700;color:#3fb950;">{tweets}</div>
      <div style="font-size:0.8rem;color:#8b949e;">تغريدة</div>
    </div>
  </div>
  {date_html}
  <div style="color:#484f58;font-size:0.75rem;text-align:center;margin-top:0.3rem;">المصدر: {source}</div>
</div>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# تبويب تحليل الحساب
# ──────────────────────────────────────────────
def account_tab(gemini_key: str, gemini_model_name: str):
    st.markdown("### 👤 تحليل حساب X")
    st.markdown("""<div class="upload-hint">🖼 أضف صورة الحساب (اختياري)<br>
    <small>اسحب وأفلت صورة البروفايل أو البانر</small></div>""", unsafe_allow_html=True)

    up_img = st.file_uploader("رفع صورة", type=["jpg","jpeg","png","webp"],
                               key="acc_img", label_visibility="collapsed")
    featured_b64 = None
    if up_img:
        try:
            featured_b64 = pil_to_base64(Image.open(up_img))
            st.success("✅ تم تحميل الصورة")
        except Exception as e:
            st.error(f"❌ {e}")

    col1, col2 = st.columns([3,1])
    with col1:
        uname_input = st.text_input("🔍 اسم المستخدم أو رابط الحساب",
                                     placeholder="@username أو https://x.com/username",
                                     key="acc_uname")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 تحليل", key="btn_fetch_acc", use_container_width=True)

    account_data = st.session_state.get("account_data_cache")

    if fetch_btn and uname_input:
        username = extract_username(uname_input)
        if not username:
            st.error("❌ أدخل اسم مستخدم صحيح")
            return
        debug = st.session_state.get("debug_mode", False)
        with st.spinner("⏳ جارٍ البحث عبر مرايا Nitter..."):
            account_data = fetch_nitter(username, debug=debug)
        if account_data:
            st.success(f"✅ تم الجلب — المصدر: {account_data['source']}")
            st.session_state["account_data_cache"] = account_data
        else:
            st.markdown('<div class="warning-box">⚠️ تعذّر الجلب — استخدم الإدخال اليدوي</div>',
                        unsafe_allow_html=True)

    with st.expander("✏️ إدخال البيانات يدوياً (دائماً يعمل)", expanded=not account_data):
        c1, c2 = st.columns(2)
        with c1:
            m_name      = st.text_input("الاسم الكامل",   value=account_data.get("name","") if account_data else "", key="m_name")
            m_screen    = st.text_input("اسم المستخدم",   value=account_data.get("screen_name","") if account_data else "", key="m_screen")
            m_followers = st.text_input("المتابعون",      value=str(account_data.get("followers_count","0")) if account_data else "0", key="m_followers")
            m_following = st.text_input("يتابع",          value=str(account_data.get("following_count","0")) if account_data else "0", key="m_following")
        with c2:
            m_tweets    = st.text_input("التغريدات",      value=str(account_data.get("tweet_count","0")) if account_data else "0", key="m_tweets")
            m_location  = st.text_input("الموقع",         value=account_data.get("location","") if account_data else "", key="m_location")
            m_created   = st.text_input("تاريخ الإنشاء", value=account_data.get("created_at","") if account_data else "", key="m_created")
            m_verified  = st.checkbox("موثّق ✅",         value=account_data.get("verified",False) if account_data else False, key="m_verified")
        m_bio = st.text_area("النبذة", value=account_data.get("description","") if account_data else "", height=100, key="m_bio")
        if st.button("💾 تأكيد البيانات", key="btn_manual"):
            account_data = {
                "name":m_name,"screen_name":m_screen,"description":m_bio,
                "followers_count":m_followers,"following_count":m_following,
                "tweet_count":m_tweets,"location":m_location,"created_at":m_created,
                "verified":m_verified,"profile_image_url":"","source":"إدخال يدوي",
            }
            st.session_state["account_data_cache"] = account_data
            st.success("✅ تم حفظ البيانات")

    if account_data:
        render_profile_card(account_data, featured_b64)

        if gemini_key and len(gemini_key) > 10:
            st.markdown("---")
            st.markdown("### 🤖 التقرير الاستخباراتي")
            imgs = [featured_b64] if featured_b64 else []
            prompt = f"""أنت محلل استخباراتي متخصص في تحليل حسابات X.

بيانات الحساب:
• الاسم: {account_data.get('name','')}
• المعرّف: @{account_data.get('screen_name','')}
• النبذة: {account_data.get('description','')}
• المتابعون: {account_data.get('followers_count',0)}
• يتابع: {account_data.get('following_count',0)}
• التغريدات: {account_data.get('tweet_count',0)}
• الموقع: {account_data.get('location','')}
• تاريخ الإنشاء: {account_data.get('created_at','')}
• موثّق: {account_data.get('verified',False)}
{"• (مرفق صورة للتحليل البصري)" if imgs else ""}

اكتب تقريراً استخباراتياً شاملاً باللغة العربية يتضمن:
1. 🔍 ملخص الهوية الرقمية
2. 📊 تحليل النشاط والتأثير
3. 🌍 المؤشرات الجغرافية
4. 🎭 تقييم مصداقية الحساب
5. ⚠️ نقاط الاهتمام والمخاطر
6. 🔗 التوصيات والخطوات التالية"""

            if st.button("🚀 توليد التقرير الاستخباراتي", key="btn_report"):
                with st.spinner("⏳ Gemini يحلّل البيانات..."):
                    model = get_gemini_model(gemini_key, gemini_model_name)
                    if model:
                        result = gemini_with_images(model, prompt, imgs) if imgs else gemini_text(model, prompt)
                        st.session_state["acc_report"] = result
                        st.session_state["acc_report_data"] = account_data

            if st.session_state.get("acc_report"):
                result = st.session_state["acc_report"]
                st.markdown(
                    f'<div class="report-section">{escape_html(result)}</div>',
                    unsafe_allow_html=True
                )
                render_export_buttons(
                    title=account_data.get("screen_name","حساب"),
                    data=account_data,
                    report_text=result,
                    report_type="account",
                    key_prefix="acc"
                )
        else:
            st.markdown('<div class="info-box">💡 أضف مفتاح Gemini لتوليد التقرير</div>',
                        unsafe_allow_html=True)

# ──────────────────────────────────────────────
# تبويب تحليل التغريدة
# ──────────────────────────────────────────────
def tweet_tab(gemini_key: str, gemini_model_name: str):
    st.markdown("### 🐦 تحليل تغريدة")
    col1, col2 = st.columns([3,1])
    with col1:
        tw_input = st.text_input("🔗 رابط أو معرّف التغريدة",
                                  placeholder="https://x.com/user/status/123456789",
                                  key="tw_input")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 جلب", key="btn_fetch_tw", use_container_width=True)

    tweet_data = st.session_state.get("tweet_data_cache")

    if fetch_btn and tw_input:
        tid = extract_tweet_id(tw_input)
        if not tid:
            if re.search(r'(?:twitter|x)\.com/[A-Za-z0-9_]+$', tw_input):
                st.markdown(
                    '<div class="warning-box">⚠️ هذا رابط <b>حساب</b> وليس تغريدة!<br>'
                    'استخدم تبويب <b>👤 تحليل حساب X</b> لتحليل الحساب،<br>'
                    'أو أدخل رابط تغريدة يحتوي على <b>/status/</b></div>',
                    unsafe_allow_html=True
                )
            else:
                st.error("❌ لم أتمكن من استخراج معرّف التغريدة")
            return
        with st.spinner("⏳ جارٍ جلب التغريدة..."):
            tweet_data = fetch_fxtwitter(tid)
        if tweet_data:
            st.success("✅ تم جلب التغريدة")
            st.session_state["tweet_data_cache"] = tweet_data
        else:
            st.error("❌ تعذّر جلب التغريدة — أدخل البيانات يدوياً")

    with st.expander("✏️ إدخال بيانات التغريدة يدوياً", expanded=not tweet_data):
        m_text = st.text_area("نص التغريدة", value=tweet_data.get("text","") if tweet_data else "", height=120, key="m_tw_text")
        mc1, mc2 = st.columns(2)
        with mc1:
            m_author  = st.text_input("اسم المؤلف",  value=tweet_data.get("author_name","") if tweet_data else "", key="m_tw_author")
            m_likes   = st.text_input("الإعجابات",   value=str(tweet_data.get("likes",0)) if tweet_data else "0", key="m_tw_likes")
            m_rts     = st.text_input("إعادة النشر", value=str(tweet_data.get("retweets",0)) if tweet_data else "0", key="m_tw_rts")
        with mc2:
            m_replies = st.text_input("الردود",      value=str(tweet_data.get("replies",0)) if tweet_data else "0", key="m_tw_replies")
            m_views   = st.text_input("المشاهدات",   value=str(tweet_data.get("views",0)) if tweet_data else "0", key="m_tw_views")
            m_date    = st.text_input("تاريخ النشر", value=tweet_data.get("created_at","") if tweet_data else "", key="m_tw_date")
        if st.button("💾 تأكيد بيانات التغريدة", key="btn_tw_manual"):
            tweet_data = {
                "text":m_text,"author_name":m_author,"likes":m_likes,
                "retweets":m_rts,"replies":m_replies,"views":m_views,
                "created_at":m_date,"media_photos":[],"source":"إدخال يدوي",
            }
            st.session_state["tweet_data_cache"] = tweet_data
            st.success("✅ تم حفظ البيانات")

    if tweet_data:
        author_name   = escape_html(tweet_data.get("author_name",""))
        author_screen = escape_html(tweet_data.get("author_screen_name",""))
        created       = escape_html(format_date(tweet_data.get("created_at","")))
        if author_name or author_screen:
            st.markdown(
                f'<div class="profile-header" style="padding:1rem;text-align:right;">'
                f'<b style="color:#58a6ff;">@{author_screen}</b> '
                f'<span style="color:#c9d1d9;">— {author_name}</span>'
                f'{" · <span style=\\"color:#8b949e;font-size:0.85rem;\\">" + created + "</span>" if created else ""}'
                f'</div>', unsafe_allow_html=True
            )

        st.markdown("#### 📝 نص المنشور")
        st.text_area("", value=tweet_data.get("text",""), height=130,
                     label_visibility="collapsed", key="tw_text_view")

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("❤️ إعجابات",   format_number(tweet_data.get("likes",0)))
        c2.metric("🔁 إعادة نشر", format_number(tweet_data.get("retweets",0)))
        c3.metric("💬 ردود",      format_number(tweet_data.get("replies",0)))
        c4.metric("👁 مشاهدات",   format_number(tweet_data.get("views",0)))

        photos = tweet_data.get("media_photos",[])
        if photos:
            st.markdown("#### 🖼 صور التغريدة")
            cols = st.columns(min(len(photos),3))
            for i,ph in enumerate(photos[:3]):
                url = ph.get("url","") if isinstance(ph,dict) else str(ph)
                if url: cols[i].image(url, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🔬 تحليل الصور بالذكاء الاصطناعي")
        up_imgs = st.file_uploader("ارفع صورة أو أكثر",
                                    type=["jpg","jpeg","png","webp"],
                                    accept_multiple_files=True, key="tw_imgs_upload")

        if up_imgs and gemini_key and len(gemini_key)>10:
            if st.button("🔬 تحليل الصور", key="btn_analyze_imgs"):
                imgs_b64 = []
                for uf in up_imgs:
                    try: imgs_b64.append(pil_to_base64(Image.open(uf)))
                    except Exception as e: st.warning(f"تخطي: {e}")
                if imgs_b64:
                    pts = "\n".join(f"{i+1}. {p}" for i,p in enumerate(IMAGE_ANALYSIS_POINTS))
                    prompt = f"""أنت محلل استخباراتي وخبير تحليل صور.

نقاط التحليل:
{pts}

حلّل الصور وأعطِ تقريراً مفصلاً بالعربية لكل نقطة."""
                    with st.spinner("⏳ Gemini يحلّل الصور..."):
                        model = get_gemini_model(gemini_key, gemini_model_name)
                        if model:
                            result = gemini_with_images(model, prompt, imgs_b64)
                            st.session_state["img_report"] = result
                            st.session_state["img_report_data"] = tweet_data

            if st.session_state.get("img_report"):
                result = st.session_state["img_report"]
                st.markdown(f'<div class="report-section">{escape_html(result)}</div>',
                            unsafe_allow_html=True)
                render_export_buttons(
                    title=f"صور_{tweet_data.get('id','tweet')}",
                    data=tweet_data, report_text=result,
                    report_type="tweet", key_prefix="img"
                )
        elif up_imgs:
            st.markdown('<div class="info-box">💡 أضف مفتاح Gemini لتحليل الصور</div>',
                        unsafe_allow_html=True)

        if gemini_key and len(gemini_key)>10:
            st.markdown("---")
            if st.button("📝 تحليل نص التغريدة بـ Gemini", key="btn_analyze_text"):
                tw_text = tweet_data.get("text","")
                if tw_text:
                    prompt = f"""حلّل هذه التغريدة تحليلاً استخباراتياً:

النص: "{tw_text}"
المؤلف: {tweet_data.get('author_name','')} @{tweet_data.get('author_screen_name','')}
الإعجابات: {tweet_data.get('likes',0)} | الريتويت: {tweet_data.get('retweets',0)}
التاريخ: {tweet_data.get('created_at','')}

التحليل:
1. 🎯 الهدف والرسالة الرئيسية
2. 🌍 المؤشرات الجغرافية والسياقية
3. 😤 المشاعر والتوجه الأيديولوجي
4. 📣 مستوى التأثير والانتشار
5. ⚠️ المخاطر والمؤشرات التحذيرية
6. 🔍 توصيات التحقيق"""
                    with st.spinner("⏳ Gemini يحلّل..."):
                        model = get_gemini_model(gemini_key, gemini_model_name)
                        if model:
                            result = gemini_text(model, prompt)
                            st.session_state["tw_report"] = result
                            st.session_state["tw_report_data"] = tweet_data

            if st.session_state.get("tw_report"):
                result = st.session_state["tw_report"]
                st.markdown(f'<div class="report-section">{escape_html(result)}</div>',
                            unsafe_allow_html=True)
                render_export_buttons(
                    title=f"تغريدة_{tweet_data.get('id','tweet')}",
                    data=tweet_data, report_text=result,
                    report_type="tweet", key_prefix="tw"
                )

# ──────────────────────────────────────────────
# الشريط الجانبي
# ──────────────────────────────────────────────
def render_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("## ⚙️ الإعدادات")
        st.markdown("---")
        st.markdown("### 🤖 Gemini AI")
        gemini_key = st.text_input("🔑 مفتاح Gemini API", type="password",
                                    placeholder="AIza...",
                                    help="https://aistudio.google.com/apikey",
                                    key="gemini_key")
        if gemini_key and len(gemini_key)>10:
            st.markdown('<div class="success-box">✅ مفتاح Gemini مُفعَّل</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="info-box">💡 <a href="https://aistudio.google.com/apikey" '
                        'target="_blank" style="color:#58a6ff;">احصل على مفتاح مجاني</a></div>',
                        unsafe_allow_html=True)
        gemini_model_name = st.selectbox("🧠 النموذج", GEMINI_MODELS, index=0, key="gemini_model")
        model_desc = {
            "gemini-2.5-flash":      "⚡ سريع ومجاني — الأفضل للاستخدام العام",
            "gemini-2.5-flash-lite": "🚀 الأسرع والأخف — مثالي للطلبات البسيطة",
            "gemini-2.5-pro":        "🧠 الأقوى والأذكى — للتحليلات المعمّقة",
        }
        st.caption(model_desc.get(gemini_model_name,""))
        st.markdown("---")
        st.markdown("### ℹ️ المصادر النشطة")
        st.markdown("""<div class="info-box">
            • ✅ Nitter (بيانات الحسابات)<br>
            • ✅ FxTwitter API (التغريدات)<br>
            • ✅ إدخال يدوي (دائماً يعمل)<br>
            • ✅ Gemini 2.5 (التحليل والتقارير)<br>
            • ✅ تصدير Word + PowerPoint
        </div>""", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### 🔬 التشخيص")
        st.checkbox("تفعيل وضع التشخيص", key="debug_mode")
        return gemini_key, gemini_model_name

# ──────────────────────────────────────────────
# الرئيسية
# ──────────────────────────────────────────────
def main():
    st.markdown("""
    <div style="text-align:center;padding:1.2rem 0 0.5rem;">
        <h1 style="color:#58a6ff;font-size:2.2rem;margin:0;">🔍 محلل حسابات X</h1>
        <p style="color:#8b949e;font-size:0.9rem;margin:0.3rem 0;">
            أداة تحليل استخباراتي • v9.7
        </p>
    </div>""", unsafe_allow_html=True)
    gemini_key, gemini_model_name = render_sidebar()
    tab1, tab2 = st.tabs(["👤 تحليل حساب X", "🐦 تحليل تغريدة"])
    with tab1:
        account_tab(gemini_key, gemini_model_name)
    with tab2:
        tweet_tab(gemini_key, gemini_model_name)

if __name__ == "__main__":
    main()
