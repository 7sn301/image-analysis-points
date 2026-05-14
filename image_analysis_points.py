# -*- coding: utf-8 -*-
"""
تحليل الصور في نقاط - النسخة 3.5
(ملخص تنفيذي ديناميكي + أيقونة X + قاموس دلالي)
"""

import streamlit as st
import pytesseract
from PIL import Image
import numpy as np
import cv2
import re
import json
from io import BytesIO
import google.generativeai as genai

# ─────────────────────────────────────────
# ✅ قاموس الكلمات الدلالية
# ─────────────────────────────────────────
SEMANTIC_KEYWORDS = {
    "عام": [
        "قرارات", "قيادة المرأة", "دخول الملاعب", "الملك", "أوامر ملكية",
        "الترفيه", "الحفلات", "الكهرباء", "فاتورة", "الضريبة المضافة",
        "رؤية 2030", "البنزين", "ولي العهد", "محمد بن سلمان", "الملك عبدالله",
        "حساب المواطن", "الديوان الملكي", "الأمير", "الشعب", "الفساد",
        "معاصي", "اختلاط", "انحلال", "الراتب", "الإسكان", "الفواتير",
        "الجبري", "نيوم", "لاين", "هبد", "مبس", "النحل", "شهيد",
        "الحكومة", "ربعنا", "معزبكم", "عاطل", "البحر الأحمر", "سدايا",
        "اعتدال", "كروز", "القدية", "الحويطات", "الحويطي", "مسك",
        "أرامكو", "صندوق الاستثمارات", "تسويات", "إحسان",
        "الشمسية", "تشجير", "العلا", "كورال بلوم", "شريك",
        "الدب الداشر", "الذباب الإلكتروني", "وطنجي", "وطنجية",
        "منشار", "وطنيون", "وطني", "الشبوك", "وطنجيه", "حامد سلمة"
    ],
    "المتطرفون": [
        "العودة", "العريفي", "الإخوان", "الإرهاب", "الربيع العربي",
        "الثورات", "حسم", "المعتقلين", "حنين", "داعش", "مرسي",
        "سجون", "الحرية", "جمال خاشقجي", "الطريفي", "سفر الحوالي",
        "اعتصام", "تجمع", "حقوق الإنسان", "مباحث", "القرضاوي",
        "لادن", "القاعدة", "جبهة النصرة", "معتقلين", "معتقلون",
        "معتقلات", "لجين الهذلول", "حماس", "طالبان", "الصحوة",
        "أمن الدولة"
    ],
    "سياسية": [
        "قطر", "الدوحة", "تميم", "تركيا", "أردوغان", "علماء السلطان",
        "ترمب", "ترامب", "صفقة القرن", "القضية الفلسطينية",
        "مصر", "سوريا", "بايدن", "الحوثي", "حوثيين", "اليمن",
        "صنعاء", "عدن", "مأرب", "سايكوباث"
    ],
    "الترفيه": [
        "الرياض", "فعاليات", "فعالية", "تركي آل الشيخ",
        "بار حلال", "رقص", "أغاني", "العلمانية",
        "خمر", "خمور", "شراب", "كلوب", "مصارعة",
        "الحفلات", "معاصي", "اختلاط", "عادات",
        "ميزانية", "الملاعب", "ملعب", "نيكي", "عبده", "وايت"
    ],
    "التجنيس": [
        "التجنيس", "جنسية", "الجنسية", "المواطن", "تجنيس",
        "المجنس", "المجنسين", "المجنسون", "مجنس",
        "ترحيل الأجانب", "التوطين", "الوظائف", "السعودة", "سعودة"
    ],
    "تهكم_وسخرية": [
        "الدب الداشر", "منشار", "هبد", "سايكوباث",
        "الذباب الإلكتروني", "وطنجي", "وطنجية", "وطنجيون",
        "ربعنا", "معزبكم", "النحل", "الشبوك",
        "بار حلال", "😂", "🤣", "😅",
        "هههه", "يضحك", "مضحك", "تهكم", "ساخر", "سخرية",
        "مش قادر", "غير قادر"
    ]
}


def detect_category(text):
    found = {}
    for category, keywords in SEMANTIC_KEYWORDS.items():
        matches = [kw for kw in keywords if kw in text]
        if matches:
            found[category] = matches
    return found


def is_sarcastic_text(text):
    sarcasm_words = SEMANTIC_KEYWORDS["تهكم_وسخرية"]
    found = [kw for kw in sarcasm_words if kw in text]
    return len(found) > 0, found


def get_topic_from_text(text):
    if any(kw in text for kw in ["ولي الأمر", "الحكومة", "الملك", "الأمير", "مبس"]):
        return "قضية الخروج على ولي الأمر"
    if any(kw in text for kw in ["الزواج", "يتزوج", "فقير", "المواليد", "التجنيس"]):
        return "قضايا الزواج والتجنيس والسكان"
    if any(kw in text for kw in SEMANTIC_KEYWORDS["الترفيه"]):
        return "قضايا الترفيه والانفتاح الاجتماعي"
    if any(kw in text for kw in SEMANTIC_KEYWORDS["المتطرفون"]):
        return "قضايا التطرف والاعتقال"
    if any(kw in text for kw in SEMANTIC_KEYWORDS["سياسية"]):
        return "الموقف السياسي"
    if any(kw in text for kw in SEMANTIC_KEYWORDS["التجنيس"]):
        return "قضايا التجنيس"
    return "الموضوع المطروح"


# ─────────────────────────────────────────
# إعداد الصفحة
# ─────────────────────────────────────────
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# ✅ تهيئة session_state
# ─────────────────────────────────────────
if "api_key" not in st.session_state:
    try:
        st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        st.session_state.api_key = ""

if "analysis_done"    not in st.session_state: st.session_state.analysis_done    = False
if "results"          not in st.session_state: st.session_state.results          = None
if "extracted_text"   not in st.session_state: st.session_state.extracted_text   = ""
if "analysis_method"  not in st.session_state: st.session_state.analysis_method  = ""

# ─────────────────────────────────────────
# CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .main, .block-container, .stApp {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    }
    .css-1d391kg, [data-testid="stSidebar"] { direction: rtl !important; }

    .result-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border-right: 4px solid #4CAF50;
        border-radius: 12px;
        padding: 15px 20px;
        margin: 10px 0;
        direction: rtl;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .result-card.missing {
        border-right-color: #f44336;
        background: linear-gradient(135deg, #1e1e2e, #2e1e1e);
    }
    .result-card.summary {
        border-right-color: #2196F3;
        background: linear-gradient(135deg, #1e2e3e, #2a3a4e);
        min-height: 120px;
    }
    .card-label {
        font-size: 13px; color: #aaa;
        margin-bottom: 8px; direction: rtl;
    }
    .card-value {
        font-size: 16px; font-weight: bold;
        color: #fff; direction: rtl;
        unicode-bidi: plaintext; line-height: 1.8;
    }
    .summary-text {
        font-size: 15px; line-height: 2.2;
        text-align: justify; padding: 5px 10px;
    }
    .card-badge {
        display: inline-block; padding: 2px 10px;
        border-radius: 20px; font-size: 12px; margin-right: 8px;
    }
    .badge-success { background: #4CAF50; color: white; }
    .badge-missing  { background: #f44336; color: white; }

    /* ✅ أيقونة X مع رابط الحساب */
    .x-link {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #000;
        color: #fff !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: bold;
        text-decoration: none !important;
        margin-top: 6px;
        direction: ltr;
    }
    .x-link:hover { background: #333; }
    .x-icon {
        width: 16px; height: 16px;
        fill: white; display: inline-block;
    }

    .success-banner {
        background: linear-gradient(135deg, #1a3a1a, #2d5a2d);
        border: 1px solid #4CAF50; border-radius: 15px;
        padding: 20px; text-align: center;
        color: white; margin: 15px 0; direction: rtl;
    }
    .error-banner {
        background: linear-gradient(135deg, #3a1a1a, #5a2d2d);
        border: 1px solid #f44336; border-radius: 15px;
        padding: 15px 20px; color: white;
        margin: 10px 0; direction: rtl;
    }
    .warning-banner {
        background: linear-gradient(135deg, #3a3a1a, #5a5a2d);
        border: 1px solid #FFC107; border-radius: 15px;
        padding: 15px 20px; color: white;
        margin: 10px 0; direction: rtl;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white; border: none; border-radius: 10px;
        padding: 12px; font-size: 16px; font-weight: bold;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #45a049, #3d8b40); }
    .image-info {
        background: #1e1e2e; border-radius: 10px;
        padding: 10px 15px; color: #ccc;
        font-size: 13px; direction: rtl; margin-top: 10px;
    }
    .key-valid   { color: #4CAF50; font-size: 13px; }
    .key-invalid { color: #f44336; font-size: 13px; }
    .category-tag {
        display: inline-block; background: #2196F3;
        color: white; padding: 2px 8px;
        border-radius: 10px; font-size: 11px; margin: 2px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# ✅ أيقونة X SVG
# ─────────────────────────────────────────
X_ICON_SVG = """<svg class="x-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
<path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
</svg>"""


def make_x_link(username):
    """✅ إنشاء رابط X مع الأيقونة"""
    if not username or username == "غير مُحدد":
        return ""
    clean = username.replace("@", "").strip()
    url   = f"https://x.com/{clean}"
    return (
        f'<a href="{url}" target="_blank" class="x-link">'
        f'{X_ICON_SVG} {username}'
        f'</a>'
    )


# ─────────────────────────────────────────
# دوال المعالجة
# ─────────────────────────────────────────

def validate_api_key(api_key):
    api_key = api_key.strip() if api_key else ""
    if not api_key:              return False, "⚠️ المفتاح فارغ"
    if not api_key.startswith("AIza"): return False, "⚠️ يجب أن يبدأ بـ AIza..."
    if len(api_key) < 30:        return False, "⚠️ المفتاح قصير جداً"
    return True, "✅ صيغة المفتاح صحيحة"


def preprocess_image_ocr(image):
    try:
        img    = np.array(image.convert('RGB'))
        gray   = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray   = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray   = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
        return Image.fromarray(cv2.filter2D(thr, -1, kernel))
    except Exception:
        return image


def extract_text_ocr(image):
    try:
        img_arr = np.array(image.convert('RGB'))
        gray    = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        gray    = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        full_text = pytesseract.image_to_string(
            gray, lang='ara+eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )
        eng_text     = pytesseract.image_to_string(gray, lang='eng', config='--oem 3 --psm 6')
        mentions_eng = re.findall(r'@[A-Za-z0-9_]+', eng_text)

        clean = re.sub(r'[^\u0600-\u06FF\s\d@#_.,;:!؟\-\u200c\u200d]', ' ', full_text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean, mentions_eng
    except Exception as e:
        return f"خطأ في OCR: {str(e)}", []


# ─────────────────────────────────────────
# ✅ الملخص التنفيذي الديناميكي الكامل
# ─────────────────────────────────────────
def generate_executive_summary(results, text):
    """
    ✅ النسخة 3.5: ملخص ديناميكي 100% بناءً على محتوى الصورة الفعلي
    لا توجد كلمات مُشفَّرة — كل شيء يُبنى من الحقول المستخرجة
    """
    post_id      = results.get("معرف_المنشور",  "غير مُحدد")
    comment_id   = results.get("معرف_التعليق",  "غير مُحدد")
    invited      = results.get("المدعو",         "غير مُحدد")
    post_content = results.get("محتوى_المنشور", "غير مُحدد")
    clip         = results.get("المقطع",         "غير مُحدد")
    comment_text = results.get("التعليق",        "غير مُحدد")
    opinion      = results.get("الرأي",          "غير مُحدد")

    # حماية: إذا لم تتوفر المعلومات الأساسية
    if post_id == "غير مُحدد" and comment_id == "غير مُحدد":
        return "غير مُحدد - لم يتم استخراج معلومات كافية للملخص التنفيذي"

    # ── كشف التهكم والموضوع ──
    is_sarcastic, sarcasm_found = is_sarcastic_text(text)
    topic    = get_topic_from_text(text)
    detected = detect_category(text)

    post_label    = post_id.replace("@", "")    if post_id    != "غير مُحدد" else ""
    comment_label = comment_id.replace("@", "") if comment_id != "غير مُحدد" else ""
    is_quote      = comment_id != "غير مُحدد"

    summary = ""

    # ══════════════════════════════════════════════
    # الجملة 1: نشر صاحب المعرف ... منشورًا ...
    # ══════════════════════════════════════════════
    if post_label:
        summary += f"نشر صاحب المعرف {post_label} ({post_id})"
    else:
        summary += "نشر أحد المستخدمين"

    # تحديد طبيعة المنشور بناءً على محتواه الفعلي
    if is_sarcastic and is_quote:
        summary += " منشورًا يتضمن تعليقًا ساخرًا"
    elif is_quote:
        summary += " منشورًا"
    else:
        summary += " منشورًا"

    # على منشور مقتبس للمدعو ...
    if is_quote:
        if invited != "غير مُحدد":
            summary += f" على منشور مقتبس للمدعو {invited} ({comment_id})"
        elif comment_label:
            summary += f" على منشور مقتبس ({comment_id})"

    summary += "،"

    # ══════════════════════════════════════════════
    # الجملة 2: حيث تضمّن المنشور الأصلي ...
    # ══════════════════════════════════════════════
    # ✅ استخدام المحتوى الفعلي المستخرج من الصورة
    original_content = ""
    if comment_text not in ["غير مُحدد", "", None]:
        original_content = comment_text
    elif post_content not in ["غير مُحدد", "", None]:
        original_content = post_content

    if original_content:
        # اقتطاع النص الطويل بشكل ذكي عند آخر نقطة أو فاصلة
        if len(original_content) > 200:
            cut = original_content[:200]
            last_stop = max(cut.rfind('،'), cut.rfind('.'), cut.rfind('!'), cut.rfind('؟'))
            original_content = cut[:last_stop + 1] if last_stop > 100 else cut + "..."
        summary += f" حيث تضمّن المنشور الأصلي: \"{original_content}\""

    # ذكر المدعو إن لم يُذكر سابقاً
    if invited != "غير مُحدد" and invited not in summary:
        summary += f" في إشارة إلى المدعو {invited}"

    # وصف المقطع إن وُجد
    has_clip = (
        clip not in ["غير مُحدد", "لا يوجد", "", None]
        and any(k in clip for k in ["يوجد", "مرئي", "فيديو", "مقطع", "✅", "صورة"])
    )
    if has_clip:
        summary += f"، مرفقًا {clip}"

    summary += "،"

    # ══════════════════════════════════════════════
    # الجملة 3: فيما علّق صاحب المعرف ... بأن ...
    # ══════════════════════════════════════════════
    if post_label:
        summary += f" فيما علّق صاحب المعرف {post_label}"

    # ✅ استخدام الرأي الفعلي المستخرج
    if opinion not in ["غير مُحدد", "", None]:
        summary += f" بأن {opinion}"
    elif post_content not in ["غير مُحدد", "", None]:
        short_content = post_content[:120] + ("..." if len(post_content) > 120 else "")
        summary += f" معلّقًا: \"{short_content}\""

    summary += "،"

    # ══════════════════════════════════════════════
    # الجملة 4: الاستنتاج والتهكم
    # ══════════════════════════════════════════════
    if is_sarcastic:
        # كشف عبارات الاستنتاج من النص الفعلي
        if any(k in text for k in ["غير قادر", "مش قادر", "ما يقدر", "لا يستطيع"]):
            summary += " مستنتجًا أن الشخص المعني غير قادر على ذلك أساسًا،"
        elif any(k in text for k in ["ماعبيتم", "يستبدل", "يستبدلكم", "الأجانب"]):
            summary += " مستنتجًا أن النتيجة الحتمية هي الاستبدال بالأجانب،"

        summary += f" في إشارة تنطوي على تهكم بشأن موقفه من {topic}"

        # إضافة التصنيف الدلالي المكتشف
        cats = [c for c in detected if c != "تهكم_وسخرية"]
        if cats:
            cat_labels = {
                "عام":       "القضايا العامة",
                "المتطرفون": "قضايا التطرف",
                "سياسية":    "القضايا السياسية",
                "الترفيه":   "قضايا الترفيه",
                "التجنيس":   "قضايا التجنيس"
            }
            labels = [cat_labels.get(c, c) for c in cats[:2]]
            summary += f" (يندرج ضمن: {' و'.join(labels)})"
    else:
        # حتى لو لم يكن ساخراً، أضف موضوع النص
        if topic != "الموضوع المطروح":
            summary += f" في سياق {topic}"

    summary += "."
    return summary


def analyze_post_smart(text, mentions_eng):
    """تحليل ذكي للنص المستخرج"""
    pts = {
        "معرف_المنشور":    "غير مُحدد",
        "معرف_التعليق":    "غير مُحدد",
        "المدعو":           "غير مُحدد",
        "محتوى_المنشور":   "غير مُحدد",
        "المقطع":           "غير مُحدد",
        "التعليق":          "غير مُحدد",
        "الرأي":            "غير مُحدد",
        "الملخص_التنفيذي": "غير مُحدد"
    }

    if mentions_eng:
        pts["معرف_المنشور"] = mentions_eng[0]
        if len(mentions_eng) > 1:
            pts["معرف_التعليق"] = mentions_eng[1]

    if pts["معرف_المنشور"] == "غير مُحدد":
        ar = re.findall(r'@[\w\u0600-\u06FF]+', text)
        if ar:
            pts["معرف_المنشور"] = ar[0]
            if len(ar) > 1: pts["معرف_التعليق"] = ar[1]

    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]

    name_patterns = [
        r'(?:بشيخنا|الشيخ|الأستاذ|الدكتور|الإمام)\s*[:\s]\s*([\u0600-\u06FF][\u0600-\u06FF\s]{2,25})',
        r'(?:ردّ على|رد على|يرد على|ذكر)\s+([\u0600-\u06FF\s]{3,25})',
    ]
    for pat in name_patterns:
        m = re.search(pat, text)
        if m:
            pts["المدعو"] = m.group(1).strip()
            break

    arabic_lines = [l for l in lines if len(re.findall(r'[\u0600-\u06FF]', l)) > 8]
    if arabic_lines:
        pts["محتوى_المنشور"] = arabic_lines[0][:200]
        if len(arabic_lines) >= 2:
            pts["التعليق"] = '\n'.join(arabic_lines[1:3])

    if any(k in text for k in ["فيديو", "مقطع", "تسجيل", "كليب", "يوتيوب", "تيكتوك", "رابط"]):
        pts["المقطع"] = "✅ محتوى مرئي موجود"

    opinion_map = {
        r'تحريم|محرم|حرام|يحرم':           'يتضمن تحريمًا في المنشور',
        r'موافق|صحيح|صح':                   'موافقة على المحتوى',
        r'مخالف|خطأ|غلط':                   'مخالفة للمحتوى',
        r'أرى|رأيي|أعتقد':                  'رأي شخصي',
        r'يستبدل|استبدال|أجانب|كفاءات':    'نقد سياسة التجنيس والاستبدال',
        r'فقراء|فقير|يتزوجون|المواليد':     'نقد الأوضاع الاقتصادية وأثرها على الزواج',
    }
    for pat, desc in opinion_map.items():
        if re.search(pat, text):
            pts["الرأي"] = desc
            break

    detected_cats = detect_category(text)
    if detected_cats and pts["الرأي"] == "غير مُحدد":
        cat_names = [c for c in detected_cats if c != "تهكم_وسخرية"]
        if cat_names:
            pts["الرأي"] = f"يندرج ضمن: {', '.join(cat_names[:2])}"

    # ✅ توليد الملخص التنفيذي الديناميكي
    pts["الملخص_التنفيذي"] = generate_executive_summary(pts, text)
    return pts


def analyze_with_gemini(image, api_key):
    try:
        api_key = api_key.strip()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = """
أنت محلل متخصص في تحليل لقطات شاشة منشورات تويتر/X باللغة العربية.
حلل الصورة المرفقة واستخرج المعلومات التالية بدقة عالية:

1. معرف_المنشور: معرف (@username) صاحب المنشور الأصلي (بالإنجليزي)
2. معرف_التعليق: معرف (@username) صاحب المنشور المقتبس (بالإنجليزي)
3. المدعو: اسم الشخص المذكور أو المدعو في النص (بالعربي)
4. محتوى_المنشور: النص الكامل للمنشور الأصلي (بالعربي)
5. المقطع: وصف الفيديو أو المقطع أو الصورة المرفقة إن وجدت، أو "لا يوجد"
6. التعليق: نص المنشور المقتبس (بالعربي)
7. الرأي: الرأي أو الحكم أو الموقف الظاهر في المنشور الأصلي

8. الملخص_التنفيذي:
اكتب ملخصًا تنفيذيًا مفصّلاً وكاملاً يصف المنشور الموجود في الصورة فعلاً.
استخدم هذه الصيغة:
"نشر صاحب المعرف [الاسم] ([المعرف]) منشورًا [يتضمن تعليقًا ساخرًا/نقديًا إن وجد] على منشور مقتبس [لـ اسم/معرف صاحب المنشور المقتبس]، حيث تضمّن المنشور الأصلي: \"[نص المنشور الأصلي]\", فيما علّق صاحب المعرف [الاسم] بأن [موقفه/رأيه الفعلي من المنشور]، [مستنتجًا أن... إن وجد استنتاج]، في إشارة تنطوي على [تهكم/نقد/تعليق] بشأن [الموضوع الفعلي]."

⚠️ قواعد صارمة:
- اعتمد فقط على ما تراه في الصورة الحالية
- لا تستخدم أمثلة أو معلومات من خارج الصورة
- اذكر المعرفات والأسماء والمحتوى الفعلي الموجود في الصورة
- الحد الأدنى: 60 كلمة
- أجب بصيغة JSON فقط بدون ```json أو ```
- استخدم "غير محدد" فقط إذا كانت المعلومة غائبة فعلاً
"""
        response = model.generate_content([prompt, image])
        raw = response.text.strip()
        raw = re.sub(r'^```(json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw).strip()

        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            result = json.loads(match.group())
            return {
                "معرف_المنشور":    result.get("معرف_المنشور",    "غير مُحدد"),
                "معرف_التعليق":    result.get("معرف_التعليق",    "غير مُحدد"),
                "المدعو":           result.get("المدعو",           "غير مُحدد"),
                "محتوى_المنشور":   result.get("محتوى_المنشور",   "غير مُحدد"),
                "المقطع":           result.get("المقطع",           "غير مُحدد"),
                "التعليق":          result.get("التعليق",          "غير مُحدد"),
                "الرأي":            result.get("الرأي",            "غير مُحدد"),
                "الملخص_التنفيذي": result.get("الملخص_التنفيذي", "غير مُحدد"),
            }, None
        return None, f"لم يُرجع Gemini JSON صالح: {raw[:200]}"

    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "api key not valid" in err.lower():
            return None, "❌ مفتاح API غير صالح - احصل على مفتاح من: https://aistudio.google.com/apikey"
        elif "PERMISSION_DENIED"  in err: return None, "❌ ليس لديك صلاحية"
        elif "QUOTA_EXCEEDED"     in err: return None, "❌ تجاوزت الحد اليومي"
        elif "timeout"   in err.lower(): return None, "❌ انتهت مهلة الاتصال"
        else: return None, f"❌ خطأ: {err}"


# ─────────────────────────────────────────
# إعداد بيانات الحقول
# ─────────────────────────────────────────
FIELD_CONFIG = {
    "معرف_المنشور":    {"icon": "🆔", "label": "معرف المنشور",    "is_username": True},
    "معرف_التعليق":    {"icon": "💬", "label": "معرف التعليق",    "is_username": True},
    "المدعو":           {"icon": "👤", "label": "المدعو / المذكور", "is_username": False},
    "محتوى_المنشور":   {"icon": "📝", "label": "محتوى المنشور",   "is_username": False},
    "المقطع":           {"icon": "🎬", "label": "المقطع / الفيديو","is_username": False},
    "التعليق":          {"icon": "💭", "label": "التعليق",          "is_username": False},
    "الرأي":            {"icon": "⚖️", "label": "الرأي / الموقف",  "is_username": False},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي", "is_username": False},
}


def render_result_card(key, value):
    """✅ عرض بطاقة نتيجة مع أيقونة X للمعرفات"""
    cfg        = FIELD_CONFIG.get(key, {"icon": "📌", "label": key, "is_username": False})
    is_missing = value in ["غير مُحدد", "غير محدد", None, ""]

    if key == "الملخص_التنفيذي":
        card_class  = "result-card summary" if not is_missing else "result-card missing"
        value_class = "card-value summary-text"
    else:
        card_class  = "result-card missing" if is_missing else "result-card"
        value_class = "card-value"

    badge_class = "badge-missing" if is_missing else "badge-success"
    badge_text  = "غير مُحدد"    if is_missing else "✓ مُحدد"
    display_val = "—"             if is_missing else value

    # ✅ أيقونة X للمعرفات
    x_link_html = ""
    if cfg.get("is_username") and not is_missing:
        x_link_html = f'<br>{make_x_link(value)}'

    st.markdown(f"""
    <div class="{card_class}">
        <div class="card-label">
            {cfg['icon']} {cfg['label']}
            <span class="card-badge {badge_class}">{badge_text}</span>
        </div>
        <div class="{value_class}">{display_val}{x_link_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# الشريط الجانبي
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ الإعدادات")

    mode = st.radio(
        "طريقة التحليل",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق ✨)"],
        index=1
    )

    if "Gemini" in mode:
        st.divider()
        st.markdown("### 🔑 مفتاح Gemini API")

        def on_api_key_change():
            st.session_state.api_key = st.session_state._api_key_input

        new_key = st.text_input(
            label="أدخل المفتاح هنا",
            value=st.session_state.api_key,
            type="password",
            placeholder="AIzaSy...",
            key="_api_key_input",
            on_change=on_api_key_change,
            help="احصل على مفتاح مجاني من aistudio.google.com"
        )
        if new_key:
            st.session_state.api_key = new_key

        if st.session_state.api_key:
            is_valid, msg = validate_api_key(st.session_state.api_key)
            css_class = "key-valid" if is_valid else "key-invalid"
            st.markdown(f'<p class="{css_class}">{msg}</p>', unsafe_allow_html=True)
        else:
            st.caption("💡 [Google AI Studio](https://aistudio.google.com/apikey)")

    st.divider()
    all_fields     = list(FIELD_CONFIG.keys())
    points_to_show = st.multiselect(
        "اختر النقاط للعرض",
        options=all_fields,
        default=all_fields,
        format_func=lambda x: f"{FIELD_CONFIG[x]['icon']} {FIELD_CONFIG[x]['label']}"
    )

    st.divider()
    st.markdown("### 📊 إحصائيات الجلسة")
    if st.session_state.results:
        filled = sum(
            1 for v in st.session_state.results.values()
            if v not in ["غير مُحدد", "غير محدد", None, ""]
        )
        st.metric("الحقول المُحددة", f"{filled} / {len(FIELD_CONFIG)}")

    if st.button("🗑️ مسح النتائج"):
        st.session_state.analysis_done  = False
        st.session_state.results        = None
        st.session_state.extracted_text = ""
        st.rerun()

    st.divider()
    with st.expander("📚 القاموس الدلالي"):
        for cat, words in SEMANTIC_KEYWORDS.items():
            if cat != "تهكم_وسخرية":
                st.markdown(f"**{cat}** ({len(words)} كلمة)")


# ─────────────────────────────────────────
# الواجهة الرئيسية
# ─────────────────────────────────────────
st.markdown("# 📸 تحليل الصور في نقاط")
st.markdown("### استخرج معلومات المنشورات من لقطات الشاشة بدقة عالية")

uploaded_file = st.file_uploader(
    "اختر صورة لتحليلها",
    type=["png", "jpg", "jpeg", "webp"],
    help="الحد الأقصى 200 MB"
)

if uploaded_file:
    image = Image.open(uploaded_file)
    col1, col2 = st.
