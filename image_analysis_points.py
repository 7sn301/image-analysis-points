# -*- coding: utf-8 -*-
"""تحليل الصور في نقاط - النسخة 3.6 (إصلاح Gemini 2.0 Flash)"""
import streamlit as st
import pytesseract
import json
from PIL import Image
import numpy as np
import cv2
import re
import google.generativeai as genai
from io import BytesIO

# ========== قاموس الكلمات الدلالية ==========
SEMANTIC_KEYWORDS = {
    "عام": [
        "قرارات", "قيادة المرأة", "السعودية", "الولاء", "الانتماء",
        "الأمن", "الاستقرار", "التنمية", "الرؤية", "2030"
    ],
    "المتطرفون": [
        "العودة", "العريفي", "السويدان", "الحبيب", "الخلف", "الحجوري",
        "الخارج", "الخوارج", "الخارجية", "الخارجون", "الخارجي"
    ],
    "سياسية": [
        "قطر", "ترمب", "إيران", "تركيا", "أمريكا", "روسيا", "الصين",
        "فلسطين", "غزة", "الحرب", "السلام", "الاتفاقية", "العقوبات"
    ],
    "الترفيه": [
        "الرياض", "فعالية", "موسم", "ترفيه", "سياحة", "الدرعية",
        "العلا", "الأمم", "كأس", "مباراة", "فريق", "نادي"
    ],
    "التجنيس": [
        "التجنيس", "السعودة", "الوظائف", "العمالة", "الأجانب",
        "الجنسية", "الإقامة", "الاستثمار", "الاقتصاد"
    ],
    "تهكم_وسخرية": [
        "🤣", "😂", "😆", "😁", "😄", "😅", "🤪", "🙃",
        "مضحك", "مهزلة", "سخرية", "ساخر", "استهزاء", "تهكم",
        "نكتة", "مقلب", "فشل", "فاشل", "كارثة", "مصيبة",
        "عيب", "عار", "خزي", "فضيحة", "فضائح", "فضيحه",
        "تزييف", "تزوير", "كذب", "كاذب", "كذاب",
        "مسرحية", "تمثيلية", "ممثل", "تمثيل",
        "كوميديا", "كوميدي", "مضحكه", "مضحكة"
    ]
}

# ========== وظائف الكشف عن التصنيفات ==========
def detect_category(text):
    if not text:
        return {}
    found_categories = {}
    for category, keywords in SEMANTIC_KEYWORDS.items():
        found = [kw for kw in keywords if kw in text]
        if found:
            found_categories[category] = found
    return found_categories

def is_sarcastic_text(text):
    if not text:
        return False, 0, []
    sarcastic_keywords = SEMANTIC_KEYWORDS.get("تهكم_وسخرية", [])
    found = [kw for kw in sarcastic_keywords if kw in text]
    return len(found) > 0, len(found), found

def get_topic_from_text(text):
    if not text:
        return "غير محدد"
    topics = {
        "الخروج على ولي الأمر": ["الخروج", "ولي الأمر", "الحاكم", "الحكومة", "النظام"],
        "التجنيس": ["تجنيس", "سعودة", "أجانب", "جنسية"],
        "السياسة": ["قطر", "ترمب", "إيران", "تركيا", "أمريكا", "فلسطين", "غزة"],
        "الترفيه": ["ترفيه", "سياحة", "موسم", "فعالية"],
        "المتطرفون": ["العودة", "العريفي", "الخارج", "الخوارج"]
    }
    for topic, keywords in topics.items():
        for kw in keywords:
            if kw in text:
                return topic
    return "عام"

# ========== إعداد الصفحة ==========
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CSS مخصص ==========
st.markdown("""
<style>
    .main, .block-container, .stApp {
        direction: rtl !important;
        text-align: right !important;
    }
    .result-card {
        background: #1e1e2e;
        border-right: 4px solid #4CAF50;
        border-radius: 12px;
        padding: 15px;
        margin: 10px 0;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .result-card.missing {
        border-right-color: #f44336;
    }
    .result-card.summary {
        border-right-color: #2196F3;
        min-height: 120px;
    }
    .result-card.x-account {
        border-right-color: #1DA1F2;
    }
    .card-label {
        font-size: 13px;
        color: #aaa;
        margin-bottom: 5px;
    }
    .card-value {
        font-size: 16px;
        font-weight: bold;
        color: white;
    }
    .success-banner {
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin: 15px 0;
        direction: rtl;
    }
    .error-banner {
        background: linear-gradient(135deg, #f44336, #d32f2f);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin: 15px 0;
        direction: rtl;
    }
    .warning-banner {
        background: linear-gradient(135deg, #ff9800, #f57c00);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin: 15px 0;
        direction: rtl;
    }
    .x-link {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #000000;
        color: white !important;
        padding: 8px 15px;
        border-radius: 20px;
        text-decoration: none !important;
        font-weight: bold;
        transition: all 0.3s;
        margin-top: 5px;
    }
    .x-link:hover {
        background: #333333;
        transform: scale(1.05);
        color: white !important;
    }
    .x-icon {
        width: 18px;
        height: 18px;
        fill: white;
        display: inline-block;
        vertical-align: middle;
    }
    .category-tag {
        display: inline-block;
        background: #333;
        color: #fff;
        padding: 4px 12px;
        border-radius: 15px;
        margin: 2px;
        font-size: 12px;
    }
    .category-tag.sarcastic { background: #ff9800; }
    .category-tag.political { background: #2196F3; }
    .category-tag.general   { background: #4CAF50; }
    .model-badge {
        display: inline-block;
        background: #6200ea;
        color: white;
        padding: 3px 10px;
        border-radius: 10px;
        font-size: 12px;
        margin-right: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ========== Session State ==========
for key, default in {
    "api_key": st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else "",
    "analysis_done": False,
    "results": None,
    "extracted_text": "",
    "analysis_method": "",
    "used_model": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ========== وظيفة رابط X ==========
def make_x_link(username):
    if not username or username in ["غير مُحدد", "غير محدد", "None", ""]:
        return "غير مُحدد"
    clean = username.replace("@", "").strip()
    x_svg = '<svg class="x-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
    return f'<a href="https://x.com/{clean}" target="_blank" class="x-link">{x_svg} @{clean}</a>'

# ========== وظائف مساعدة ==========
def validate_api_key(key):
    key = key.strip()
    if not key:
        return False, "⚠️ المفتاح فارغ"
    if not key.startswith("AIza"):
        return False, "⚠️ المفتاح يجب أن يبدأ بـ AIza..."
    if len(key) < 30:
        return False, "⚠️ المفتاح قصير جداً"
    return True, "✅ صيغة المفتاح صحيحة"

def preprocess_image_ocr(image):
    try:
        img = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
        sharpened = cv2.filter2D(thresh, -1, kernel)
        return Image.fromarray(sharpened)
    except:
        return image

def extract_text_ocr(image):
    try:
        img_array = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        text_arabic = pytesseract.image_to_string(
            gray, lang='ara+eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )
        text_english = pytesseract.image_to_string(gray, lang='eng', config='--oem 3 --psm 6')
        mentions = re.findall(r'@[A-Za-z0-9_]+', text_english)
        cleaned = re.sub(r'[^\u0600-\u06FF\s\d@#_.,;:!؟\-\u200c\u200d\u064b-\u065f]', ' ', text_arabic)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned, mentions
    except Exception as e:
        return f"خطأ في OCR: {str(e)}", []

def generate_executive_summary(results, extracted_text=""):
    post_id       = results.get("معرف_المنشور",   "غير مُحدد")
    comment_id    = results.get("معرف_التعليق",   "غير مُحدد")
    invited       = results.get("المدعو",          "غير مُحدد")
    post_content  = results.get("محتوى_المنشور",  "غير مُحدد")
    clip          = results.get("المقطع",          "غير مُحدد")
    comment_text  = results.get("التعليق",         "غير مُحدد")
    opinion       = results.get("الرأي",           "غير مُحدد")

    full_text = " ".join([extracted_text, str(comment_text), str(post_content)])
    is_sarcastic, _, _ = is_sarcastic_text(full_text)
    topic = get_topic_from_text(full_text)

    def short(txt, n=120):
        return (txt[:n] + "...") if len(txt) > n else txt

    parts = []

    # جزء 1 – النشر
    if post_id != "غير مُحدد":
        if post_content != "غير مُحدد":
            parts.append(f"نشر صاحب المعرف {post_id} منشوراً يتضمن {short(post_content)}")
        else:
            parts.append(f"نشر صاحب المعرف {post_id} منشوراً")

    # جزء 2 – الاقتباس
    if invited != "غير مُحدد":
        parts.append(f"مقتبساً من المدعو {invited}")

    # جزء 3 – المقطع
    if clip != "غير مُحدد":
        parts.append(f"مرفقاً مقطع فيديو يظهر فيه {short(clip)}")

    # جزء 4 – التعليق
    if comment_id != "غير مُحدد":
        if comment_text != "غير مُحدد":
            parts.append(f"حيث علّق صاحب المعرف {comment_id} بأن {short(comment_text)}")
        else:
            parts.append(f"حيث علّق صاحب المعرف {comment_id}")

    # جزء 5 – الرأي
    if opinion != "غير مُحدد":
        parts.append(f"مستنتجاً أن {short(opinion)}")

    # جزء 6 – التهكم
    if is_sarcastic:
        parts.append(f"في إشارة تنطوي على تهكم بشأن {topic}")

    if parts:
        return "، ".join(parts) + "."
    return "غير مُحدد - لم يتم استخراج معلومات كافية من الصورة"

def analyze_post_smart(text, mentions):
    results = {
        "معرف_المنشور":  "غير مُحدد",
        "معرف_التعليق":  "غير مُحدد",
        "المدعو":         "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "المقطع":         "غير مُحدد",
        "التعليق":        "غير مُحدد",
        "الرأي":          "غير مُحدد",
        "الملخص_التنفيذي":"غير مُحدد"
    }
    if mentions:
        results["معرف_المنشور"] = mentions[0]
        if len(mentions) > 1:
            results["معرف_التعليق"] = mentions[1]

    def first_match(patterns, txt):
        for p in patterns:
            m = re.search(p, txt)
            if m:
                return m.group(1).strip()
        return "غير مُحدد"

    results["المدعو"]         = first_match([r'المدعو\s+([@\w\s]+)', r'الشيخ\s+([@\w\s]+)', r'الداعية\s+([@\w\s]+)'], text)
    results["محتوى_المنشور"] = first_match([r'محتوى[:\s]+([^\n]+)', r'المنشور[:\s]+([^\n]+)', r'يتضمن[:\s]+([^\n]+)'], text)
    results["المقطع"]         = first_match([r'مقطع[:\s]+([^\n]+)', r'فيديو[:\s]+([^\n]+)', r'يظهر[:\s]+([^\n]+)'], text)
    results["التعليق"]        = first_match([r'التعليق[:\s]+([^\n]+)', r'علق[:\s]+([^\n]+)', r'حيث[:\s]+([^\n]+)'], text)
    results["الرأي"]          = first_match([r'الرأي[:\s]+([^\n]+)', r'استنتج[:\s]+([^\n]+)', r'رأي[:\s]+([^\n]+)'], text)

    results["الملخص_التنفيذي"] = generate_executive_summary(results, text)
    return results

# ========== تحليل Gemini (مُصلَح) ==========
def analyze_with_gemini(image, api_key):
    try:
        genai.configure(api_key=api_key.strip())

        # ✅ قائمة النماذج المتاحة (من الأحدث للأقدم)
        models_to_try = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
        ]

        model = None
        used_model_name = ""
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                used_model_name = model_name
                break
            except Exception:
                continue

        if model is None:
            return None, "❌ لا يوجد نموذج Gemini متاح حالياً", ""

        prompt = """
أنت محلل متخصص في تحليل منشورات تويتر/اكس (X).
قم بتحليل الصورة المرفقة واستخراج المعلومات التالية بدقة تامة.

أعد JSON فقط بدون أي نص إضافي أو علامات markdown:
{
    "معرف_المنشور": "معرف صاحب المنشور الأصلي كاملاً مثل @username",
    "معرف_التعليق": "معرف صاحب التعليق أو المنشور المقتبس إن وجد",
    "المدعو": "اسم أو معرف الشخص المدعو أو المقتبس منه المنشور",
    "محتوى_المنشور": "نص المنشور الأصلي كاملاً أو باختصار مفيد",
    "المقطع": "وصف المقطع المرئي أو الفيديو المرفق إن وجد",
    "التعليق": "نص التعليق على المنشور",
    "الرأي": "الرأي أو التحليل أو الاستنتاج المقدم",
    "الملخص_التنفيذي": "ملخص تنفيذي كامل جملة واحدة لا تقل عن 80 كلمة تتضمن: من نشر، ما هو المحتوى، من المدعو، ما هو المقطع، ما هو التعليق، ما هو الرأي، وهل يوجد تهكم أو سخرية وعن ماذا"
}

قواعد صارمة:
- أعد JSON فقط، لا نص قبله ولا بعده
- استخدم "غير مُحدد" لأي حقل غير موجود في الصورة
- الملخص_التنفيذي يجب أن يكون جملة متصلة لا تقل عن 80 كلمة
- استخرج المعرفات (@username) بدقة كاملة
- حلل وجود أي تهكم أو سخرية بعمق

مثال الملخص_التنفيذي المطلوب:
"نشر صاحب المعرف @username منشوراً يتضمن [محتوى المنشور]، مقتبساً من المدعو [المدعو]، مرفقاً مقطع فيديو يظهر فيه [وصف المقطع]، حيث علّق صاحب المعرف @commenter بأن [التعليق]، مستنتجاً أن [الرأي]، في إشارة تنطوي على تهكم بشأن [الموضوع]."
"""

        response = model.generate_content([prompt, image])
        raw = response.text.strip()

        # تنظيف markdown
        cleaned = re.sub(r'^```(json)?\s*', '', raw)
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()

        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            result = json.loads(match.group())
            for field in ["معرف_المنشور","معرف_التعليق","المدعو",
                          "محتوى_المنشور","المقطع","التعليق","الرأي","الملخص_التنفيذي"]:
                if field not in result:
                    result[field] = "غير مُحدد"
            return result, None, used_model_name
        else:
            return None, f"لم يُرجع Gemini JSON صالح. الاستجابة: {raw[:200]}", used_model_name

    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err:
            return None, "❌ مفتاح API غير صالح. تأكد من صحة المفتاح.", ""
        elif "PERMISSION_DENIED" in err:
            return None, "❌ لا توجد صلاحية للوصول. تأكد من تفعيل API.", ""
        elif "QUOTA_EXCEEDED" in err:
            return None, "❌ تم تجاوز الحصة اليومية. استخدم OCR أو انتظر الغد.", ""
        elif "DeadlineExceeded" in err or "timeout" in err.lower():
            return None, "⏱️ انتهى الوقت. حاول مرة أخرى أو استخدم OCR.", ""
        else:
            return None, f"❌ خطأ: {err}", ""

# ========== إعدادات الحقول ==========
FIELD_CONFIG = {
    "معرف_المنشور":  {"icon": "👤", "label": "معرف المنشور",     "is_username": True},
    "معرف_التعليق":  {"icon": "💬", "label": "معرف التعليق",     "is_username": True},
    "المدعو":         {"icon": "🎯", "label": "المدعو / المقتبس"},
    "محتوى_المنشور": {"icon": "📝", "label": "محتوى المنشور"},
    "المقطع":         {"icon": "🎬", "label": "المقطع / الفيديو"},
    "التعليق":        {"icon": "💭", "label": "التعليق"},
    "الرأي":          {"icon": "🧠", "label": "الرأي / التحليل"},
    "الملخص_التنفيذي":{"icon": "📋", "label": "الملخص التنفيذي", "is_summary": True}
}

def render_result_card(field_key, value):
    config = FIELD_CONFIG.get(field_key, {"icon": "📄", "label": field_key})
    is_missing = value in ["غير مُحدد", "غير محدد", "", None, "None"]
    card_class = "missing" if is_missing else ("summary" if config.get("is_summary") else "")

    if config.get("is_username") and not is_missing:
        x_link = make_x_link(value)
        st.markdown(f"""
        <div class="result-card x-account">
            <div class="card-label">{config['icon']} {config['label']}</div>
            <div class="card-value">{x_link}</div>
        </div>""", unsafe_allow_html=True)
    else:
        display = value if not is_missing else "⚠️ غير مُحدد"
        st.markdown(f"""
        <div class="result-card {card_class}">
            <div class="card-label">{config['icon']} {config['label']}</div>
            <div class="card-value">{display}</div>
        </div>""", unsafe_allow_html=True)

# ========================================================
#                    الشريط الجانبي
# ========================================================
with st.sidebar:
    st.title("⚙️ الإعدادات")

    analysis_mode = st.radio(
        "طريقة التحليل:",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق ✨)"],
        index=1
    )

    if "Gemini" in analysis_mode:
        st.markdown("---")
        st.subheader("🔐 مفتاح Gemini API")
        new_key = st.text_input(
            "أدخل مفتاح Gemini API:",
            value=st.session_state.api_key,
            type="password",
            key="_api_key_input"
        )
        if new_key:
            st.session_state.api_key = new_key

        if st.session_state.api_key:
            is_valid, msg = validate_api_key(st.session_state.api_key)
            color = "green" if is_valid else "red"
            st.markdown(f"<p style='color:{color}'>{msg}</p>", unsafe_allow_html=True)
        else:
            st.caption("💡 احصل على مفتاح مجاني: https://aistudio.google.com/apikey")

    st.markdown("---")
    st.subheader("👁️ إعدادات العرض")
    all_fields = list(FIELD_CONFIG.keys())
    selected_fields = st.multiselect("اختر الحقول للعرض:", all_fields, default=all_fields)

    st.markdown("---")
    st.subheader("📊 إحصائيات الجلسة")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("الصور", "1" if st.session_state.analysis_done else "0")
    with c2:
        st.metric("الطريقة", st.session_state.analysis_method if st.session_state.analysis_method else "-")

    if st.session_state.analysis_done and st.session_state.results:
        filled = sum(1 for v in st.session_state.results.values() if v not in ["غير مُحدد","غير محدد","",None])
        total  = len(st.session_state.results)
        st.progress(filled/total)
        st.caption(f"✅ {filled}/{total} حقول ({int(filled/total*100)}%)")

    if st.session_state.used_model:
        st.markdown(f'<span class="model-badge">🤖 {st.session_state.used_model}</span>', unsafe_allow_html=True)

    if st.session_state.analysis_done:
        if st.button("🗑️ مسح النتائج", use_container_width=True):
            for k in ["analysis_done","results","extracted_text","analysis_method","used_model"]:
                st.session_state[k] = False if k == "analysis_done" else (None if k == "results" else "")
            st.rerun()

    with st.expander("📚 القاموس الدلالي"):
        for cat, kws in SEMANTIC_KEYWORDS.items():
            st.markdown(f"**{cat}:** {', '.join(kws[:5])}...")

# ========================================================
#                    الواجهة الرئيسية
# ========================================================
st.title("📸 تحليل الصور في نقاط")
st.markdown("---")

uploaded_file = st.file_uploader(
    "📤 اختر صورة لتحليلها:",
    type=["png","jpg","jpeg","webp"],
    help="الحد الأقصى: 200 ميجابايت"
)

if uploaded_file:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1,1])

    with col1:
        st.image(image, caption="الصورة المُرفوعة", use_container_width=True)
        st.caption(f"📐 {image.size[0]}×{image.size[1]} بكسل | "
                   f"📦 {len(uploaded_file.getvalue())/1024:.1f} KB")

    with col2:
        st.markdown("### 🚀 ابدأ التحليل")
        use_gemini = "Gemini" in analysis_mode and bool(st.session_state.api_key)

        if st.button("🔍 تحليل الصورة الآن", use_container_width=True):
            if "Gemini" in analysis_mode:
                if not st.session_state.api_key:
                    st.error("❌ يرجى إدخال مفتاح Gemini API أولاً")
                    use_gemini = False
                else:
                    is_valid, msg = validate_api_key(st.session_state.api_key)
                    if not is_valid:
                        st.error(msg)
                        use_gemini = False

            with st.spinner("⏳ جاري تحليل الصورة..."):
                results, method_used, used_model = None, "", ""

                if use_gemini:
                    results, error, used_model = analyze_with_gemini(image, st.session_state.api_key)
                    if error:
                        st.warning(f"{error}\n\n🔄 سيتم التحويل إلى OCR...")
                        results = None
                    else:
                        method_used = "Gemini AI ✨"

                if results is None:
                    proc = preprocess_image_ocr(image)
                    text, mentions = extract_text_ocr(proc)
                    st.session_state.extracted_text = text
                    results = analyze_post_smart(text, mentions)
                    method_used = "OCR تقليدي 🔤"
                    used_model  = "Tesseract"

                st.session_state.results         = results
                st.session_state.analysis_method = method_used
                st.session_state.analysis_done   = True
                st.session_state.used_model      = used_model
                st.rerun()

# ========== عرض النتائج ==========
if st.session_state.analysis_done and st.session_state.results:
    res    = st.session_state.results
    filled = sum(1 for v in res.values() if v not in ["غير مُحدد","غير محدد","",None])
    total  = len(res)
    pct    = int(filled/total*100)

    st.markdown(f"""
    <div class="success-banner">
        <h3>✅ تم التحليل بنجاح!</h3>
        <p>طريقة التحليل: <strong>{st.session_state.analysis_method}</strong>
           {f'| النموذج: <strong>{st.session_state.used_model}</strong>' if st.session_state.used_model else ''}</p>
        <p>تم استخراج <strong>{filled}/{total}</strong> حقول ({pct}%)</p>
    </div>
    """, unsafe_allow_html=True)

    st.progress(pct/100)

    # التصنيفات
    if st.session_state.extracted_text:
        cats = detect_category(st.session_state.extracted_text)
        if cats:
            st.markdown("### 🏷️ التصنيفات المكتشفة:")
            tags_html = ""
            for cat, words in cats.items():
                css = "sarcastic" if "تهكم" in cat else ("political" if "سياسية" in cat else "general")
                for w in words[:3]:
                    tags_html += f'<span class="category-tag {css}">{cat}: {w}</span>'
            st.markdown(tags_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 النتائج:")

    for field in selected_fields:
        if field in res:
            render_result_card(field, res[field])

    st.markdown("---")
    d1, d2 = st.columns(2)
    with d1:
        txt = "\n".join([f"{k}: {v}" for k, v in res.items()])
        st.download_button("📄 تنزيل TXT", data=txt.encode('utf-8'),
                           file_name="analysis_result.txt", mime="text/plain",
                           use_container_width=True)
    with d2:
        js = json.dumps(res, ensure_ascii=False, indent=2)
        st.download_button("📋 تنزيل JSON", data=js.encode('utf-8'),
                           file_name="analysis_result.json", mime="application/json",
                           use_container_width=True)

    if st.session_state.extracted_text:
        with st.expander("📝 النص المستخرج من OCR"):
            st.text_area("النص الخام:", value=st.session_state.extracted_text,
                         disabled=True, height=150)

# ========== دليل الاستخدام ==========
with st.expander("📖 دليل الاستخدام"):
    st.markdown("""
### خطوات التحليل:
1️⃣ **اختر طريقة التحليل** من الشريط الجانبي (OCR مجاني أو Gemini AI)

2️⃣ **احصل على مفتاح Gemini** من: https://aistudio.google.com/apikey

3️⃣ **ارفع الصورة** (PNG / JPG / WEBP حتى 200 MB)

4️⃣ **اضغط "تحليل الصورة الآن"**
   - يحاول Gemini أولاً (2.0 Flash ← 2.0 Flash Exp ← 1.5 Flash Latest)
   - إذا فشل ينتقل تلقائياً إلى OCR

### مميزات الإصدار 3.6:
- ✅ دعم Gemini 2.0 Flash (إصلاح خطأ النموذج القديم)
- ✅ Fallback تلقائي لأحدث نموذج متاح
- ✅ روابط X قابلة للنقر لجميع المعرفات
- ✅ ملخص تنفيذي ديناميكي مبني على البيانات الفعلية
- ✅ حفظ مفتاح API طوال الجلسة
""")

# ========== التذييل ==========
st.markdown("---")
st.caption("© تحليل الصور في نقاط - الإصدار 3.6 | "
           "[احصل على مفتاح Gemini المجاني](https://aistudio.google.com/apikey)")
