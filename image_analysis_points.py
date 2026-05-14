# -*- coding: utf-8 -*-
"""
تحليل الصور في نقاط - النسخة 3.4 (قاموس الكلمات الدلالية + الملخص التنفيذي الكامل)
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
# ✅ قاموس الكلمات الدلالية (مصدر: تصنيف الكلمات الدلالية.docx)
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
    """كشف تصنيف النص بناءً على الكلمات الدلالية"""
    found = {}
    for category, keywords in SEMANTIC_KEYWORDS.items():
        matches = [kw for kw in keywords if kw in text]
        if matches:
            found[category] = matches
    return found


def is_sarcastic_text(text):
    """كشف التهكم بناءً على قاموس الكلمات الدلالية"""
    sarcasm_words = SEMANTIC_KEYWORDS["تهكم_وسخرية"]
    found = [kw for kw in sarcasm_words if kw in text]
    return len(found) > 0, found


def get_topic_from_text(text):
    """استخراج موضوع التهكم من النص بناءً على التصنيف"""
    if any(kw in text for kw in ["ولي الأمر", "الحكومة", "الملك", "الأمير", "مبس"]):
        return "قضية الخروج على ولي الأمر"
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

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "results" not in st.session_state:
    st.session_state.results = None

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "analysis_method" not in st.session_state:
    st.session_state.analysis_method = ""

# ─────────────────────────────────────────
# CSS للغة العربية (RTL)
# ─────────────────────────────────────────
st.markdown("""
<style>
    .main, .block-container, .stApp {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    }
    .css-1d391kg, [data-testid="stSidebar"] {
        direction: rtl !important;
    }
    .result-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border-right: 4px solid #4CAF50;
        border-radius: 12px;
        padding: 15px 20px;
        margin: 10px 0;
        direction: rtl;
        text-align: right;
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
        font-size: 13px;
        color: #aaa;
        margin-bottom: 5px;
        direction: rtl;
    }
    .card-value {
        font-size: 16px;
        font-weight: bold;
        color: #fff;
        direction: rtl;
        unicode-bidi: plaintext;
        line-height: 1.8;
    }
    .card-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 12px;
        margin-right: 8px;
    }
    .badge-success { background: #4CAF50; color: white; }
    .badge-missing { background: #f44336; color: white; }
    .success-banner {
        background: linear-gradient(135deg, #1a3a1a, #2d5a2d);
        border: 1px solid #4CAF50;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        color: white;
        margin: 15px 0;
        direction: rtl;
    }
    .error-banner {
        background: linear-gradient(135deg, #3a1a1a, #5a2d2d);
        border: 1px solid #f44336;
        border-radius: 15px;
        padding: 15px 20px;
        color: white;
        margin: 10px 0;
        direction: rtl;
    }
    .warning-banner {
        background: linear-gradient(135deg, #3a3a1a, #5a5a2d);
        border: 1px solid #FFC107;
        border-radius: 15px;
        padding: 15px 20px;
        color: white;
        margin: 10px 0;
        direction: rtl;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #45a049, #3d8b40);
    }
    .image-info {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 10px 15px;
        color: #ccc;
        font-size: 13px;
        direction: rtl;
        margin-top: 10px;
    }
    .key-valid   { color: #4CAF50; font-size: 13px; margin-top: 5px; }
    .key-invalid { color: #f44336; font-size: 13px; margin-top: 5px; }
    .summary-text {
        font-size: 15px;
        line-height: 2;
        text-align: justify;
        padding: 10px;
    }
    .category-tag {
        display: inline-block;
        background: #2196F3;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        margin: 2px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# دوال المعالجة
# ─────────────────────────────────────────

def validate_api_key(api_key):
    """التحقق من صحة مفتاح API"""
    api_key = api_key.strip() if api_key else ""
    if not api_key:
        return False, "⚠️ المفتاح فارغ - أدخل مفتاح API"
    if not api_key.startswith("AIza"):
        return False, "⚠️ المفتاح يجب أن يبدأ بـ AIza..."
    if len(api_key) < 30:
        return False, "⚠️ المفتاح قصير جداً - تأكد من نسخه كاملاً"
    return True, "✅ صيغة المفتاح صحيحة"


def preprocess_image_ocr(image):
    """معالجة الصورة قبل OCR"""
    try:
        img = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
        sharpened = cv2.filter2D(thresh, -1, kernel)
        return Image.fromarray(sharpened)
    except Exception:
        return image


def extract_text_ocr(image):
    """استخراج النص عبر OCR مع الحفاظ على @usernames"""
    try:
        img_arr = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        full_text = pytesseract.image_to_string(
            gray, lang='ara+eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )
        eng_text = pytesseract.image_to_string(
            gray, lang='eng',
            config='--oem 3 --psm 6'
        )
        mentions_eng = re.findall(r'@[A-Za-z0-9_]+', eng_text)

        clean_text = re.sub(r'[^\u0600-\u06FF\s\d@#_.,;:!؟\-\u200c\u200d]', ' ', full_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text, mentions_eng

    except Exception as e:
        return f"خطأ في OCR: {str(e)}", []


def generate_executive_summary(results, text):
    """
    ✅ توليد الملخص التنفيذي الكامل والمفصّل
       بالاعتماد على قاموس الكلمات الدلالية
    """
    post_id      = results.get("معرف_المنشور", "غير مُحدد")
    comment_id   = results.get("معرف_التعليق", "غير مُحدد")
    invited      = results.get("المدعو",        "غير مُحدد")
    post_content = results.get("محتوى_المنشور", "غير مُحدد")
    clip         = results.get("المقطع",        "غير مُحدد")
    comment_text = results.get("التعليق",       "غير مُحدد")
    opinion      = results.get("الرأي",         "غير مُحدد")

    if post_id == "غير مُحدد" and comment_id == "غير مُحدد":
        return "غير مُحدد - لم يتم استخراج معلومات كافية للملخص التنفيذي"

    # ── كشف التهكم والموضوع والتصنيف ──
    is_sarcastic, sarcasm_found = is_sarcastic_text(text)
    topic    = get_topic_from_text(text)
    detected = detect_category(text)

    summary = ""

    # ═══ الجملة 1: نشر صاحب المعرف ... ═══
    post_label = post_id.replace("@", "") if post_id != "غير مُحدد" else ""
    is_quote   = comment_id != "غير مُحدد"

    if post_label:
        summary += f"نشر صاحب المعرف {post_label} ({post_id})"
    else:
        summary += "نشر أحد المستخدمين"

    if is_sarcastic and is_quote:
        summary += " منشورًا يتضمن تعليقًا ساخرًا"
    else:
        summary += " منشورًا"

    if is_quote:
        comment_label = comment_id.replace("@", "") if comment_id != "غير مُحدد" else ""
        if invited != "غير مُحدد":
            summary += f" على منشور مقتبس للمدعو {invited} ({comment_id})"
        elif comment_label:
            summary += f" على منشور مقتبس ({comment_id})"

    summary += "،"

    # ═══ الجملة 2: حيث أشار صاحب المنشور الأصلي ... ═══
    original_content = ""
    if comment_text not in ["غير مُحدد", ""]:
        original_content = comment_text[:150]
    elif post_content not in ["غير مُحدد", ""]:
        original_content = post_content[:150]

    if original_content:
        summary += f" حيث أشار صاحب المنشور الأصلي إلى {original_content}"

    if invited != "غير مُحدد" and invited not in summary:
        summary += f" بالمدعو {invited}"

    has_clip = (
        clip not in ["غير مُحدد", "لا يوجد", ""]
        and any(k in clip for k in ["يوجد", "مرئي", "فيديو", "مقطع", "✅"])
    )
    if has_clip:
        summary += " مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس"

    summary += "،"

    # ═══ الجملة 3: فيما علّق صاحب المعرف ... ═══
    if post_label:
        summary += f" فيما علّق صاحب المعرف {post_label}"

    if opinion not in ["غير مُحدد", ""]:
        if "تحريم" in opinion or any(k in text for k in ["حرام", "محرم", "تحريم", "يحرم"]):
            summary += " بأن المقطع يتضمن تحريمًا للخروج على ولي الأمر"
        elif "موافق" in opinion:
            summary += " بموافقته على المحتوى"
        elif "مخالف" in opinion:
            summary += " بمخالفته للمحتوى"
        else:
            summary += f" بأن {opinion[:100]}"
    elif post_content not in ["غير مُحدد", ""]:
        summary += f" معلّقًا على المحتوى: {post_content[:100]}"

    summary += "،"

    # ═══ الجملة 4: مستنتجًا + التهكم ═══
    if is_sarcastic:
        if any(k in text for k in ["غير قادر", "مش قادر", "ما يقدر", "لا يستطيع"]):
            summary += " مستنتجًا أن الشخص المعني غير قادر على الخروج أساسًا،"

        summary += f" في إشارة تنطوي على تهكم بشأن موقفه من {topic}"

        categories_found = [c for c in detected if c != "تهكم_وسخرية"]
        if categories_found:
            cat_labels = {
                "عام":         "القضايا العامة",
                "المتطرفون":   "قضايا التطرف",
                "سياسية":      "القضايا السياسية",
                "الترفيه":     "قضايا الترفيه",
                "التجنيس":     "قضايا التجنيس"
            }
            cats = [cat_labels.get(c, c) for c in categories_found[:2]]
            summary += f" (يندرج ضمن: {' و'.join(cats)})"

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

    # ✅ معرفات من OCR الإنجليزي
    if mentions_eng:
        pts["معرف_المنشور"] = mentions_eng[0]
        if len(mentions_eng) > 1:
            pts["معرف_التعليق"] = mentions_eng[1]

    # ✅ fallback للمعرفات العربية
    if pts["معرف_المنشور"] == "غير مُحدد":
        ar_mentions = re.findall(r'@[\w\u0600-\u06FF]+', text)
        if ar_mentions:
            pts["معرف_المنشور"] = ar_mentions[0]
            if len(ar_mentions) > 1:
                pts["معرف_التعليق"] = ar_mentions[1]

    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]

    # ✅ استخراج المدعو
    name_patterns = [
        r'(?:بشيخنا|الشيخ|الأستاذ|الدكتور|الإمام)\s*[:\s]\s*([\u0600-\u06FF][\u0600-\u06FF\s]{2,25})',
        r'(?:ردّ على|رد على|يرد على|ذكر)\s+([\u0600-\u06FF\s]{3,25})',
    ]
    for pat in name_patterns:
        m = re.search(pat, text)
        if m:
            pts["المدعو"] = m.group(1).strip()
            break

    # ✅ محتوى المنشور
    arabic_lines = [l for l in lines if len(re.findall(r'[\u0600-\u06FF]', l)) > 8]
    if arabic_lines:
        pts["محتوى_المنشور"] = arabic_lines[0][:200]
        if len(arabic_lines) >= 2:
            pts["التعليق"] = '\n'.join(arabic_lines[1:3])

    # ✅ كشف المقطع
    if any(k in text for k in ["فيديو", "مقطع", "تسجيل", "كليب", "يوتيوب", "تيكتوك", "رابط"]):
        pts["المقطع"] = "✅ محتوى مرئي موجود"

    # ✅ الرأي (باستخدام القاموس الدلالي)
    opinion_map = {
        r'تحريم|محرم|حرام|يحرم': 'يتضمن تحريم الخروج على ولي الأمر',
        r'موافق|صحيح|صح':        'موافقة على المحتوى',
        r'مخالف|خطأ|غلط':        'مخالفة للمحتوى',
        r'أرى|رأيي|أعتقد':       'رأي شخصي',
    }
    for pat, desc in opinion_map.items():
        if re.search(pat, text):
            pts["الرأي"] = desc
            break

    # ✅ كشف التصنيف الدلالي
    detected_cats = detect_category(text)
    if detected_cats and pts["الرأي"] == "غير مُحدد":
        cat_names = [c for c in detected_cats if c != "تهكم_وسخرية"]
        if cat_names:
            pts["الرأي"] = f"يندرج ضمن: {', '.join(cat_names[:2])}"

    # ✅ توليد الملخص التنفيذي
    pts["الملخص_التنفيذي"] = generate_executive_summary(pts, text)

    return pts


def analyze_with_gemini(image, api_key):
    """تحليل متقدم باستخدام Gemini Vision"""
    try:
        api_key = api_key.strip()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = """
أنت محلل متخصص في تحليل لقطات شاشة منشورات تويتر/X باللغة العربية.
حلل الصورة المرفقة واستخرج المعلومات التالية بدقة عالية:

1. معرف_المنشور: معرف (@username) صاحب المنشور الأصلي (بالإنجليزي)
2. معرف_التعليق: معرف (@username) صاحب التعليق أو الاقتباس (بالإنجليزي)
3. المدعو: اسم الشخص المذكور أو المدعو في النص (بالعربي)
4. محتوى_المنشور: النص الكامل للمنشور الأصلي (بالعربي)
5. المقطع: وصف الفيديو أو المقطع المرفق إن وجد، أو "لا يوجد"
6. التعليق: نص التعليق أو الاقتباس المضاف (بالعربي)
7. الرأي: الرأي أو الحكم أو الموقف الظاهر في المنشور

8. الملخص_التنفيذي:
اكتب ملخصًا تنفيذيًا مفصّلاً وكاملاً بالصيغة التالية حرفياً:
"نشر صاحب المعرف [الاسم الظاهر] ([@username_المنشور]) منشورًا [يتضمن تعليقًا ساخرًا إن وجد سخرية] على منشور مقتبس للمدعو [اسم صاحب المنشور المقتبس] ([@username_التعليق])، حيث أشار صاحب المنشور الأصلي إلى [محتوى المنشور المقتبس] [مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس إن وجد مقطع]، فيما علّق صاحب المعرف [الاسم] بأن [محتوى التعليق/الرأي]، [مستنتجًا أن الشخص المعني غير قادر على ... أساسًا إن وجد هذا المعنى]، في إشارة تنطوي على تهكم بشأن موقفه من [موضوع التهكم]."

⚠️ قواعد صارمة للملخص التنفيذي:
- يجب أن يكون الملخص جملة واحدة متصلة وكاملة
- لا تختصر أو تحذف أي تفصيل مهم
- اذكر المعرفات (@username) والأسماء الكاملة معاً
- اذكر محتوى المنشور الأصلي ومحتوى التعليق
- اذكر وصف المقطع إن وجد
- اذكر الاستنتاج والتهكم إن وجدا
- الحد الأدنى للملخص: 80 كلمة

⚠️ قواعد عامة:
- أجب بصيغة JSON فقط بدون أي نص إضافي
- لا تضع ```json أو ``` حول الإجابة
- استخدم "غير محدد" فقط إذا كانت المعلومة غير موجودة فعلاً في الصورة

مثال للملخص المطلوب:
"نشر صاحب المعرف عبدالله الشريف (@AbdullahElshrif) منشورًا يتضمن تعليقًا ساخرًا على منشور مقتبس للمدعو الدين النصيحة (@boyousefalazmi)، حيث أشار صاحب المنشور الأصلي إلى ترحيبه بالمدعو سالم الطويل مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس، فيما علّق صاحب المعرف عبدالله الشريف بأن المقطع يتضمن تحريمًا للخروج على ولي الأمر، مستنتجًا أن الشخص المعني غير قادر على الخروج أساسًا، في إشارة تنطوي على تهكم بشأن موقفه من قضية الخروج على ولي الأمر."
"""

        response = model.generate_content([prompt, image])
        raw = response.text.strip()
        raw = re.sub(r'^```(json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        raw = raw.strip()

        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            result = json.loads(match.group())
            normalized = {
                "معرف_المنشور":    result.get("معرف_المنشور",    "غير مُحدد"),
                "معرف_التعليق":    result.get("معرف_التعليق",    "غير مُحدد"),
                "المدعو":           result.get("المدعو",           "غير مُحدد"),
                "محتوى_المنشور":   result.get("محتوى_المنشور",   "غير مُحدد"),
                "المقطع":           result.get("المقطع",           "غير مُحدد"),
                "التعليق":          result.get("التعليق",          "غير مُحدد"),
                "الرأي":            result.get("الرأي",            "غير مُحدد"),
                "الملخص_التنفيذي": result.get("الملخص_التنفيذي", "غير مُحدد"),
            }
            return normalized, None
        else:
            return None, f"لم يُرجع Gemini JSON صالح. الاستجابة: {raw[:200]}"

    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "api key not valid" in err.lower():
            return None, "❌ مفتاح API غير صالح - احصل على مفتاح جديد من: https://aistudio.google.com/apikey"
        elif "PERMISSION_DENIED" in err:
            return None, "❌ ليس لديك صلاحية - تأكد أن Gemini API مُفعّل في مشروعك"
        elif "QUOTA_EXCEEDED" in err or "quota" in err.lower():
            return None, "❌ تجاوزت الحد اليومي المجاني - انتظر حتى الغد"
        elif "timeout" in err.lower():
            return None, "❌ انتهت مهلة الاتصال - تحقق من الإنترنت"
        elif "model" in err.lower() and "not found" in err.lower():
            return None, "❌ النموذج غير متاح في منطقتك"
        else:
            return None, f"❌ خطأ غير متوقع: {err}"


# ─────────────────────────────────────────
# إعداد بيانات الحقول
# ─────────────────────────────────────────
FIELD_CONFIG = {
    "معرف_المنشور":    {"icon": "🆔", "label": "معرف المنشور"},
    "معرف_التعليق":    {"icon": "💬", "label": "معرف التعليق"},
    "المدعو":           {"icon": "👤", "label": "المدعو / المذكور"},
    "محتوى_المنشور":   {"icon": "📝", "label": "محتوى المنشور"},
    "المقطع":           {"icon": "🎬", "label": "المقطع / الفيديو"},
    "التعليق":          {"icon": "💭", "label": "التعليق"},
    "الرأي":            {"icon": "⚖️", "label": "الرأي / الموقف"},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي"},
}


def render_result_card(key, value):
    """عرض بطاقة نتيجة واحدة"""
    cfg = FIELD_CONFIG.get(key, {"icon": "📌", "label": key})
    is_missing = value in ["غير مُحدد", "غير محدد", None, ""]

    if key == "الملخص_التنفيذي":
        card_class = "result-card summary" if not is_missing else "result-card missing"
    else:
        card_class = "result-card missing" if is_missing else "result-card"

    badge_class = "badge-missing" if is_missing else "badge-success"
    badge_text  = "غير مُحدد"    if is_missing else "✓ مُحدد"
    display_val = "—"             if is_missing else value

    value_class = "card-value summary-text" if key == "الملخص_التنفيذي" and not is_missing \
                  else "card-value"

    st.markdown(f"""
    <div class="{card_class}">
        <div class="card-label">
            {cfg['icon']} {cfg['label']}
            <span class="card-badge {badge_class}">{badge_text}</span>
        </div>
        <div class="{value_class}">{display_val}</div>
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
            if is_valid:
                st.markdown(f'<p class="key-valid">{msg}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="key-invalid">{msg}</p>', unsafe_allow_html=True)
        else:
            st.caption("💡 احصل على مفتاح مجاني من [Google AI Studio](https://aistudio.google.com/apikey)")

    st.divider()

    all_fields = list(FIELD_CONFIG.keys())
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

    # ── عرض القاموس الدلالي ──
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
    col1, col2 = st.columns([1, 1])

    with col1:
        st.image(image, caption="الصورة المُرفوعة", use_container_width=True)
        w, h     = image.size
        size_kb  = uploaded_file.size / 1024
        st.markdown(f"""
        <div class="image-info">
            📐 الأبعاد: {w} × {h} بكسل &nbsp;|&nbsp;
            📁 الحجم: {size_kb:.1f} KB &nbsp;|&nbsp;
            🖼️ الصيغة: {image.format or uploaded_file.type.split('/')[-1].upper()}
        </div>
        """, unsafe_allow_html=True)

    with col2:
        analyze_btn = st.button("🚀 تحليل الصورة الآن", use_container_width=True)

        if analyze_btn:
            use_gemini  = "Gemini" in mode
            api_key_val = st.session_state.api_key.strip()

            if use_gemini and not api_key_val:
                st.markdown("""
                <div class="warning-banner">
                    ⚠️ لم تُدخل مفتاح Gemini API<br>
                    <small>سيتم التحويل إلى OCR تلقائياً</small>
                </div>""", unsafe_allow_html=True)
                use_gemini = False

            with st.spinner("⏳ جاري التحليل..."):
                results     = None
                method_used = ""

                # ── محاولة Gemini ──
                if use_gemini and api_key_val:
                    is_valid, valid_msg = validate_api_key(api_key_val)
                    if not is_valid:
                        st.markdown(f'<div class="error-banner">❌ {valid_msg}</div>',
                                    unsafe_allow_html=True)
                    else:
                        with st.status("🤖 Gemini AI يحلل الصورة..."):
                            results, err = analyze_with_gemini(image, api_key_val)
                            if err:
                                st.markdown(f'<div class="error-banner">{err}</div>',
                                            unsafe_allow_html=True)
                                st.info("🔄 التحويل التلقائي إلى OCR...")
                                results = None
                            else:
                                method_used = "Gemini AI ✨"

                # ── OCR كـ fallback أو اختيار أصلي ──
                if results is None:
                    with st.status("🔤 جاري استخراج النص بـ OCR..."):
                        text, mentions = extract_text_ocr(image)
                        st.session_state.extracted_text = text
                        results = analyze_post_smart(text, mentions)
                        method_used = "OCR تقليدي"

                st.session_state.results        = results
                st.session_state.analysis_method = method_used
                st.session_state.analysis_done   = True

        # ─────────────────────────────────────────
        # عرض النتائج
        # ─────────────────────────────────────────
        if st.session_state.analysis_done and st.session_state.results:
            results = st.session_state.results
            filled  = sum(
                1 for v in results.values()
                if v not in ["غير مُحدد", "غير محدد", None, ""]
            )
            total = len(results)
            pct   = int(filled / total * 100)

            st.markdown(f"""
            <div class="success-banner">
                ✅ تم التحليل بنجاح باستخدام <strong>{st.session_state.analysis_method}</strong><br>
                🎯 تم استخراج <strong>{filled} من {total}</strong> حقول ({pct}%)
            </div>""", unsafe_allow_html=True)

            st.progress(pct / 100)

            # ── عرض التصنيفات الدلالية المكتشفة ──
            if st.session_state.extracted_text:
                detected = detect_category(st.session_state.extracted_text)
                if detected:
                    cats_html = "".join([
                        f'<span class="category-tag">📂 {c}</span>'
                        for c in detected if c != "تهكم_وسخرية"
                    ])
                    if cats_html:
                        st.markdown(
                            f'<div style="margin:10px 0; direction:rtl;">'
                            f'التصنيفات المكتشفة: {cats_html}</div>',
                            unsafe_allow_html=True
                        )

            st.markdown("---")

            for key in points_to_show:
                if key in results:
                    render_result_card(key, results[key])

            # ── تنزيل النتائج ──
            st.markdown("### 💾 تنزيل النتائج")
            dl_col1, dl_col2 = st.columns(2)

            txt_content = "\n".join([
                f"{FIELD_CONFIG[k]['label']}: {v}"
                for k, v in results.items()
            ])
            with dl_col1:
                st.download_button(
                    "📄 تنزيل TXT",
                    data=txt_content.encode('utf-8'),
                    file_name="analysis_result.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with dl_col2:
                st.download_button(
                    "📋 تنزيل JSON",
                    data=json.dumps(results, ensure_ascii=False, indent=2).encode('utf-8'),
                    file_name="analysis_result.json",
                    mime="application/json",
                    use_container_width=True
                )

            if st.session_state.extracted_text:
                with st.expander("📝 النص المستخرج (للمراجعة)"):
                    st.text_area(
                        "النص الخام من OCR",
                        value=st.session_state.extracted_text,
                        height=150,
                        disabled=True
                    )


# ─────────────────────────────────────────
# تعليمات الاستخدام
# ─────────────────────────────────────────
with st.expander("📖 كيفية الاستخدام"):
    st.markdown("""
    ### خطوات الاستخدام:
    1. **اختر طريقة التحليل** من الشريط الجانبي:
       - 🔤 **OCR تقليدي**: مجاني، لا يحتاج مفتاح API
       - 🤖 **Gemini AI**: أدق وأذكى، يحتاج مفتاح API مجاني
    2. **للحصول على مفتاح Gemini** المجاني:
       - اذهب إلى [Google AI Studio](https://aistudio.google.com/apikey)
       - اضغط **"Create API Key"** وانسخ المفتاح
    3. **ارفع الصورة** (PNG, JPG, WEBP حتى 200MB)
    4. اضغط **"تحليل الصورة الآن"**

    ### ميزة القاموس الدلالي:
    - 📂 يكشف التصنيف تلقائياً (عام / سياسية / ترفيه / تجنيس / متطرفون)
    - 😏 يكشف التهكم والسخرية بدقة عالية
    - 📋 يولد ملخصاً تنفيذياً كاملاً ومفصّلاً
    """)


# ─────────────────────────────────────────
# تذييل الصفحة
# ─────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#888; font-size:13px; direction:rtl;">
    📸 تحليل الصور في نقاط - النسخة 3.4 | 
    <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#4CAF50;">
        احصل على مفتاح Gemini المجاني
    </a>
</div>
""", unsafe_allow_html=True)
