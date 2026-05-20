# ================================================================
#  محلل حسابات X الاستخباراتي
#  الإصدار: v10.3.3
#  التحديثات:
#   - إصلاح RTL كامل في التقارير والواجهة
#   - PowerPoint احترافي بتصميم متناسق
#   - تضمين بايو + بيانات الحساب في جميع التقارير
#   - شرائح PPTX منظمة: غلاف + ملف الحساب + تحليل
# ================================================================

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

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ════════════════════════════════════════════════════
#  الثوابت
# ════════════════════════════════════════════════════

PAGE_TITLE = "محلل حسابات X الاستخباراتي"
PAGE_ICON  = "🔍"
VERSION    = "v10.3.3"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

FXTWITTER_TWEET = "https://api.fxtwitter.com/status/{tweet_id}"
FXTWITTER_USER  = "https://api.fxtwitter.com/{username}"
TWITTERAPI_BASE = "https://api.twitterapi.io"

GEMINI_MODELS = {
    "Gemini 2.5 Flash (موصى به)":       "gemini-2.5-flash",
    "Gemini 2.0 Flash Lite (اقتصادي)":  "gemini-2.0-flash-lite",
    "Gemini 2.5 Pro (متقدم)":            "gemini-2.5-pro",
    "Gemini 1.5 Flash (احتياطي)":        "gemini-1.5-flash",
}

INTEL_KEYWORDS = {
    "🔴 عداء مباشر للمملكة": [
        "ارض الحرمين", "المهلكة", "ال سلول", "آل سلول",
        "شولوم", "البقرة", "الحلوب", "العلوج",
        "الغنيمة", "سلاليم", "النظام السعودي",
    ],
    "🟠 تحريض سياسي": [
        "قمع", "فساد", "إسقاط النظام", "تكميم الأفواه",
        "اعتقالات سياسية", "معتقل رأي", "سجن ظلم",
        "انتهاك حقوق", "سجناء الرأي", "بطش الحكومة",
    ],
    "🟡 حملات إعلامية عدائية": [
        "مقاطعة السعودية", "حملة ضد السعودية",
        "فضائح السعودية", "فشل سعودي", "الذباب الإلكتروني",
        "غسيل سمعة", "استهداف السعودية", "زعزعة الأمن",
        "إسقاط الحكم", "التحريض ضد الدولة", "الفوضى",
        "التجنيد ضد السعودية", "البطالة", "العاطلين",
    ],
    "🟣 إساءة للهوية الوطنية": [
        "كراهية السعوديين", "العنصرية ضد السعوديين",
        "إهانة رموز الدولة", "التشكيك بالوطنية",
        "الإساءة للهوية الوطنية", "ازدراء السعودية",
    ],
    "⚫ تحريض على العصيان": [
        "تمرد", "عصيان", "انتفاضة", "الشارع يغلي",
        "ثورة", "الدعوة للتظاهر", "مظاهرة",
        "قمع حريات", "انفجار شعبي", "حراك شعبي",
        "الغضب الشعبي", "العصيان المدني", "الربيع العربي",
    ],
}

IMAGE_ANALYSIS_POINTS = {
    "📍 تحديد الموقع الجغرافي": (
        "حلل هذه الصورة لتحديد الموقع الجغرافي. ابحث عن: "
        "المعالم البارزة، اللافتات، الطرازات المعمارية، الغطاء النباتي، "
        "التضاريس، المركبات، ملابس السكان. "
        "قدم احتمالات متعددة للمواقع مع مستويات ثقتك."
    ),
    "👤 تحليل الأشخاص والهويات": (
        "حلل الأشخاص الظاهرين. صف: السن، الجنس، الملابس، "
        "الشعارات، لغة الجسد، العلاقات، المعدات."
    ),
    "🚗 تحليل المركبات والمعدات": (
        "حدد وحلل المركبات والمعدات. اذكر: النوع، الماركة، "
        "الحالة، أرقام اللوحات، التحصينات، الاستخدام المحتمل."
    ),
    "📄 تحليل الوثائق والنصوص": (
        "اقرأ وحلل النصوص والوثائق. استخرج: النصوص، أرقام الوثائق، "
        "التواريخ، الأختام، الرموز الرسمية."
    ),
    "⚔️ تحليل الأسلحة والتجهيزات": (
        "حلل الأسلحة والتجهيزات. صف: النوع، الطراز، الحالة، "
        "طريقة الحمل، التكتيكات، مستوى التدريب."
    ),
    "🏗️ تحليل البنية التحتية": (
        "حلل البنية التحتية. صف: النوع، الحالة، الأهمية الاستراتيجية."
    ),
    "⏰ تحليل التوقيت والزمن": (
        "حلل مؤشرات التوقيت: موضع الشمس، الظلال، الطقس، القِدَم."
    ),
    "🔍 تحليل الأحداث والتجمعات": (
        "حلل الحدث أو التجمع. صف: الطبيعة، حجم الحشد، التنظيم."
    ),
    "🔎 كشف التزوير والتلاعب": (
        "افحص الصورة لكشف التلاعب. ابحث عن: عدم التناسق، "
        "حواف غير طبيعية، علامات الذكاء الاصطناعي."
    ),
    "🧠 تحليل شامل ومتكامل": (
        "تحليل استخباراتي شامل: الموقع، الأشخاص، المركبات، "
        "الأسلحة، البنية التحتية، التوقيت، السياق."
    ),
}


# ════════════════════════════════════════════════════
#  دوال مساعدة
# ════════════════════════════════════════════════════

def safe_text(val, default="غير متوفر"):
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def escape_html(text):
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def nl_to_br(text):
    return escape_html(text).replace("\n", "<br>")


def extract_tweet_id(raw):
    raw = raw.strip()
    m = re.search(r"/status(?:es)?/(\d+)", raw)
    if m:
        return m.group(1)
    if raw.isdigit() and len(raw) > 5:
        return raw
    return None


def extract_username(raw):
    raw = raw.strip().lstrip("@")
    m = re.search(r"(?:twitter\.com|x\.com)/([^/?#\s]+)", raw)
    if m:
        c = m.group(1)
        if c.lower() not in ("status","i","intent","search","hashtag"):
            return c
    m = re.match(r"^([A-Za-z0-9_]{1,50})$", raw)
    if m:
        return m.group(1)
    return raw


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
    if fmt.upper() in ("JPEG","JPG"):
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


# ════════════════════════════════════════════════════
#  حساب أبعاد الصور
# ════════════════════════════════════════════════════

def calc_image_size_word(b64_str, max_w=5.5, max_h=7.0):
    try:
        img = Image.open(base64_to_bytesio(b64_str))
        w, h = img.size
        if w == 0 or h == 0:
            return {"width": Inches(4)}
        if (h/w) * max_w <= max_h:
            return {"width": Inches(max_w)}
        return {"height": Inches(max_h)}
    except Exception:
        return {"width": Inches(4)}


def calc_image_size_pptx(b64_str, slide_w, slide_h,
                          mwr=0.70, mhr=0.55):
    try:
        img = Image.open(base64_to_bytesio(b64_str))
        w, h = img.size
        if w == 0 or h == 0:
            return int(slide_w*.1),int(slide_h*.25),int(slide_w*.8),int(slide_h*.5)
        aspect = h / w
        max_w  = int(slide_w * mwr)
        max_h  = int(slide_h * mhr)
        if aspect * max_w <= max_h:
            pw = max_w; ph = int(aspect * max_w)
        else:
            ph = max_h; pw = int(max_h / aspect)
        left = int((slide_w - pw) / 2)
        top  = PEmu(1_300_000) + int((max_h - ph) / 2)
        return left, top, pw, ph
    except Exception:
        return int(slide_w*.1),int(slide_h*.25),int(slide_w*.8),int(slide_h*.5)


# ════════════════════════════════════════════════════
#  جلب البيانات
# ════════════════════════════════════════════════════

def fetch_fxtwitter_tweet(tweet_id):
    url = FXTWITTER_TWEET.format(tweet_id=tweet_id)
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept":"application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        d = r.json()
        return d["tweet"] if d.get("code")==200 and "tweet" in d else None
    except Exception as e:
        st.error(f"خطأ في جلب التغريدة: {e}")
        return None


def fetch_fxtwitter_user(username):
    username = username.strip().lstrip("@")
    url = FXTWITTER_USER.format(username=username)
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept":"application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        d = r.json()
        return d["user"] if d.get("code")==200 and "user" in d else None
    except Exception as e:
        st.error(f"خطأ في جلب الحساب: {e}")
        return None


def fetch_user_tweets_twitterapi(username, tapi_key, limit=500):
    username = username.strip().lstrip("@")
    url      = f"{TWITTERAPI_BASE}/twitter/user/last_tweets"
    headers  = {"X-API-Key": tapi_key, "Content-Type":"application/json"}
    all_tweets = []
    cursor     = None
    max_pages  = 30
    progress   = st.progress(0, text="جاري جلب التغريدات...")
    page = 0
    while len(all_tweets) < limit and page < max_pages:
        params = {"userName": username}
        if cursor:
            params["cursor"] = cursor
        try:
            r = requests.get(url, headers=headers, params=params, timeout=25)
            r.raise_for_status()
            data   = r.json()
            tweets = data.get("tweets", [])
            if not tweets:
                break
            for t in tweets:
                text = (t.get("text") or t.get("full_text") or
                        t.get("rawContent") or "")
                if text:
                    all_tweets.append(text.strip())
            cursor = (data.get("next_cursor") or data.get("cursor") or
                      data.get("nextCursor"))
            if not cursor:
                break
            page += 1
            pct = min(int((len(all_tweets)/limit)*100), 99)
            progress.progress(pct, text=f"تم جلب {len(all_tweets)} تغريدة...")
            time.sleep(0.3)
        except requests.exceptions.HTTPError as e:
            st.error(f"خطأ HTTP {r.status_code}: {e}")
            break
        except Exception as e:
            st.error(f"خطأ: {e}")
            break
    progress.progress(100, text=f"✅ تم جلب {len(all_tweets)} تغريدة")
    time.sleep(0.5)
    progress.empty()
    return all_tweets[:limit]


# ════════════════════════════════════════════════════
#  الكشف الكلمي
# ════════════════════════════════════════════════════

def scan_keywords(tweets_text):
    found = {}
    tl    = tweets_text.lower()
    for cat, kws in INTEL_KEYWORDS.items():
        hits = [(kw, tl.count(kw.lower())) for kw in kws if tl.count(kw.lower()) > 0]
        if hits:
            found[cat] = sorted(hits, key=lambda x: -x[1])
    return found


# ════════════════════════════════════════════════════
#  Gemini
# ════════════════════════════════════════════════════

def _get_model(api_key, model_name):
    if not GENAI_AVAILABLE:
        st.error("مكتبة google-generativeai غير مثبّتة.")
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"خطأ في تهيئة Gemini: {e}")
        return None


def gemini_text(prompt, api_key, model_name):
    model = _get_model(api_key, model_name)
    if not model:
        return None
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        st.error(f"خطأ في Gemini: {e}")
        return None


def gemini_with_images(prompt, images_b64, api_key, model_name):
    model = _get_model(api_key, model_name)
    if not model:
        return None
    try:
        parts = [prompt]
        for b64 in images_b64:
            raw  = base64.b64decode(b64)
            img  = Image.open(io.BytesIO(raw))
            fmt  = (img.format or "PNG").lower()
            mime = "image/jpeg" if fmt in ("jpeg","jpg") else "image/png"
            parts.append({"mime_type": mime, "data": b64})
        return model.generate_content(parts).text
    except Exception as e:
        st.error(f"خطأ في تحليل الصور: {e}")
        return None


def generate_intel_summary(tweets_list, profile_data, found_keywords,
                            api_key, model_name):
    kw_section = ""
    for cat, hits in found_keywords.items():
        kw_section += f"\n{cat}:\n"
        for kw, cnt in hits:
            kw_section += f"  - '{kw}' تكرر {cnt} مرة\n"

    sample = tweets_list[:80]
    tweets_sample = "\n---\n".join(sample)

    bio       = profile_data.get("description","")
    name      = profile_data.get("name","")
    username  = profile_data.get("screen_name","")
    followers = format_number(profile_data.get("followers",0))
    location  = profile_data.get("location","")
    joined    = safe_text(profile_data.get("joined",""),"")[:10]

    prompt = f"""أنت محلل استخباراتي متخصص في رصد المحتوى الرقمي المعادي للمملكة العربية السعودية.

## بيانات الحساب المستهدف:
- **الاسم:** {name}
- **معرّف الحساب:** @{username}
- **الوصف (البايو):** {bio}
- **الموقع:** {location}
- **تاريخ الإنشاء:** {joined}
- **عدد المتابعين:** {followers}
- **عدد التغريدات المُحللة:** {len(tweets_list)}

## الكلمات الدلالية المكتشفة تلقائياً:
{kw_section if kw_section else "لم تُكتشف كلمات دلالية صريحة"}

## عيّنة من المنشورات ({len(sample)} منشور):
{tweets_sample}

---

## التقرير الاستخباراتي المطلوب:

### بيانات الحساب المستهدف ###
* **الاسم:** {name}
* **معرّف الحساب:** @{username}
* **الوصف:** {bio}
* **الموقع:** {location}
* **عدد المتابعين:** {followers}
* **وصف الحساب (تحليل البايو):** [وصف تحليلي للبايو وما يدل عليه من توجهات]
* **الكلمات الدلالية المكتشفة:** {kw_section if kw_section else "لم تُكتشف كلمات دلالية صريحة تلقائياً"}

---

### 1. التصنيف الاستخباراتي النهائي ###
اختر من: [معادٍ للمملكة | متطرف | محرِّض | مثير للرأي العام | ناشط سياسي | عادي]

### 2. مستوى الخطورة ###
رقم من 1 إلى 10 مع تبرير

### 3. المحاور العدائية المكتشفة ###
من القائمة:
- عداء مباشر للمملكة
- تحريض سياسي
- حملات إعلامية عدائية
- إساءة للهوية الوطنية
- تحريض على العصيان

### 4. تحليل نمط النشر ###
التكرار، مواضيع التركيز، الأسلوب، مؤشرات التنسيق

### 5. مؤشرات التطرف ###
أنماط التطرف الفكري أو الديني أو السياسي

### 6. ملخص الخطر الأمني ###
فقرة واحدة مركّزة

### 7. التوصيات ###
إجراءات موصى بها + مستوى الأولوية

قدّم التقرير بالعربية بأسلوب رسمي مناسب للجهات الأمنية."""

    return gemini_text(prompt, api_key, model_name)


# ════════════════════════════════════════════════════
#  مساعدات Word RTL
# ════════════════════════════════════════════════════

def _set_rtl_para(para):
    try:
        pPr  = para._p.get_or_add_pPr()
        bidi = OxmlElement("w:bidi")
        bidi.set(qn("w:val"), "1")
        pPr.append(bidi)
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), "right")
        pPr.append(jc)
    except Exception:
        pass


def _add_word_section(doc, title, content, color=None, level=2):
    h = doc.add_heading(title, level=level)
    _set_rtl_para(h)
    if color:
        for run in h.runs:
            run.font.color.rgb = RGBColor(*color)
    p = doc.add_paragraph(content)
    _set_rtl_para(p)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return p


# ════════════════════════════════════════════════════
#  مساعدات PPTX
# ════════════════════════════════════════════════════

def _set_rtl_pptx(para):
    try:
        pPr  = para._p.get_or_add_pPr()
        bidi = OxmlElement("a:rtl")
        bidi.text = "1"
        pPr.append(bidi)
    except Exception:
        pass


# ════════════════════════════════════════════════════
#  تصدير Word
# ════════════════════════════════════════════════════

def export_to_word(title, tweet_data, img_analysis,
                   text_analysis, exec_summary, images_b64,
                   intel_report="", account_user=None):
    if not DOCX_AVAILABLE:
        st.error("مكتبة python-docx غير مثبّتة.")
        return None

    doc   = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    #
