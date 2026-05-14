# -- coding: utf-8 --
"""
تحليل الصور في نقاط - النسخة 3.1 (إصلاح API Key + معالجة أخطاء محسّنة)
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

# ============================================================
# --- إعداد الصفحة ---
# ============================================================
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide"
)

# ============================================================
# --- CSS ---
# ============================================================
st.markdown("""
<style>
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div,
    .stMultiSelect div {
        direction: rtl !important;
        text-align: right !important;
    }
    .stButton > button {
        background-color: #2563EB !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        width: 100% !important;
        border: none !important;
        cursor: pointer !important;
    }
    .stButton > button:hover {
        background-color: #1d4ed8 !important;
    }
    .result-card {
        background: #F8FAFC;
        padding: 14px 18px;
        border-radius: 10px;
        margin: 8px 0;
        border-right: 5px solid #2563EB;
        direction: rtl;
        text-align: right;
    }
    .result-card .card-label {
        font-size: 13px;
        font-weight: bold;
        color: #1e40af;
        margin-bottom: 6px;
    }
    .result-card .card-value {
        font-size: 15px;
        color: #1f2937;
        line-height: 1.8;
        white-space: pre-wrap;
        word-break: break-word;
        direction: rtl;
        text-align: right;
    }
    .result-card .card-value.undefined {
        color: #9ca3af;
        font-style: italic;
    }
    .card-id {
        border-right-color: #7c3aed !important;
        background: #f5f3ff !important;
    }
    .card-id .card-label { color: #6d28d9 !important; }
    .card-content {
        border-right-color: #059669 !important;
        background: #f0fdf4 !important;
    }
    .card-content .card-label { color: #047857 !important; }
    .card-content .card-value {
        font-size: 16px !important;
        line-height: 1.9 !important;
        background: white;
        padding: 10px 14px;
        border-radius: 8px;
        border: 1px solid #d1fae5;
        direction: rtl !important;
        text-align: right !important;
    }
    .card-comment {
        border-right-color: #0891b2 !important;
        background: #f0f9ff !important;
    }
    .card-comment .card-label { color: #0e7490 !important; }
    .card-opinion {
        border-right-color: #d97706 !important;
        background: #fffbeb !important;
    }
    .card-opinion .card-label { color: #b45309 !important; }
    .card-media {
        border-right-color: #e11d48 !important;
        background: #fff1f2 !important;
    }
    .card-media .card-label { color: #be123c !important; }
    .card-sarcasm {
        border-right-color: #ea580c !important;
        background: #fff7ed !important;
    }
    .verified-badge {
        display: inline-block;
        background: #dcfce7;
        color: #15803d;
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 6px;
    }
    .missing-badge {
        display: inline-block;
        background: #f3f4f6;
        color: #9ca3af;
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 12px;
    }
    .warning-banner {
        background: #fef3c7;
        border-right: 5px solid #f59e0b;
        padding: 14px 18px;
        border-radius: 10px;
        margin: 10px 0;
        direction: rtl;
    }
    .info-banner {
        background: #eff6ff;
        border-right: 5px solid #3b82f6;
        padding: 14px 18px;
        border-radius: 10px;
        margin: 10px 0;
        direction: rtl;
    }
    .error-banner {
        background: #fef2f2;
        border-right: 5px solid #ef4444;
        padding: 14px 18px;
        border-radius: 10px;
        margin: 10px 0;
        direction: rtl;
    }
    .stFileUploader label { direction: rtl; text-align: right; }
    section[data-testid="stSidebar"] > div {
        direction: rtl;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# --- الوظائف ---
# ============================================================

def validate_api_key(api_key):
    """
    ✅ جديد: التحقق من صحة مفتاح API قبل الإرسال
    """
    api_key = api_key.strip()
    if not api_key:
        return False, "⚠️ المفتاح فارغ - أدخل مفتاح API"
    if not api_key.startswith("AIza"):
        return False, "⚠️ المفتاح يجب أن يبدأ بـ AIza..."
    if len(api_key) < 30:
        return False, "⚠️ المفتاح قصير جداً - تأكد من نسخه كاملاً"
    return True, "✅ صيغة المفتاح صحيحة"


def preprocess_image_ocr(image):
    """
    معالجة الصورة لـ OCR
    """
    img = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def extract_text_ocr(image):
    """
    استخراج النص بـ OCR مع الحفاظ على @usernames
    """
    try:
        img_arr = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        config_full = '--oem 3 --psm 6'
        text_full = pytesseract.image_to_string(gray, lang='ara+eng', config=config_full)

        config_eng = '--oem 3 --psm 6'
        text_eng = pytesseract.image_to_string(gray, lang='eng', config=config_eng)

        mentions_eng = re.findall(r'@[A-Za-z0-9_]+', text_eng)

        text_clean = re.sub(r'[^\u0600-\u06FF\s\d@#_\.,;:!؟\-\u064b-\u065f]', ' ', text_full)
        text_clean = re.sub(r'\s+', ' ', text_clean).strip()

        return text_clean, mentions_eng

    except Exception as e:
        return f"خطأ: {str(e)}", []


def analyze_post_smart(text, mentions_eng):
    """
    تحليل ذكي للنص
    """
    points = {
        "معرف_المنشور": "غير مُحدد",
        "معرف_التعليق": "غير مُحدد",
        "المدعو":        "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "المقطع":        "غير مُحدد",
        "التعليق":       "غير مُحدد",
        "الرأي":         "غير مُحدد",
        "التهكم":        "غير مُحدد"
    }

    if len(mentions_eng) >= 1:
        points["معرف_المنشور"] = mentions_eng[0]
    if len(mentions_eng) >= 2:
        points["معرف_التعليق"] = mentions_eng[1]

    if points["معرف_المنشور"] == "غير مُحدد":
        mentions_ar = re.findall(r'@[\w\u0600-\u06FF]+', text)
        if len(mentions_ar) >= 1:
            points["معرف_المنشور"] = mentions_ar[0]
        if len(mentions_ar) >= 2:
            points["معرف_التعليق"] = mentions_ar[1]

    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]

    name_patterns = [
        r'(?:ردّ على|رد على|يرد على|ذكر|بشيخنا|الشيخ|الأستاذ|الدكتور)\s+([\u0600-\u06FF][\u0600-\u06FF\s]{2,25})',
        r'(?:سالم|محمد|عبدالله|أحمد|علي)\s+[\u0600-\u06FF]{2,15}',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip() if 'بشيخنا' in pattern else match.group(0).strip()
            points["المدعو"] = name
            break

    arabic_lines = [l for l in lines if len(re.findall(r'[\u0600-\u06FF]', l)) > 10]
    if arabic_lines:
        points["محتوى_المنشور"] = arabic_lines[0]
        if len(arabic_lines) >= 2:
            points["التعليق"] = '\n'.join(arabic_lines[1:3])

    video_kw = ["فيديو", "مقطع", "تسجيل", "كليب", "يوتيوب", "تيكتوك", "رابط"]
    found = [k for k in video_kw if k in text]
    if found:
        points["المقطع"] = f"محتوى مرئي: {', '.join(found)}"

    opinion_map = {
        "تحريم|محرم|حرام": "تحريم الخروج على ولي الأمر",
        "موافق|صح|صحيح":   "موافقة على المحتوى",
        "مخالف|خطأ|غلط":   "مخالفة للمحتوى",
        "تهكم|ساخر|سخرية":  "تعليق ساخر",
        "أرى|رأيي|أعتقد":   "رأي شخصي",
    }
    for pattern, desc in opinion_map.items():
        if re.search(pattern, text):
            points["الرأي"] = desc
            break

    sarcasm_kw = ["تهكم", "ساخر", "سخرية", "😂", "🤣", "😅", "هههه", "يضحك", "مضحك"]
    if any(k in text for k in sarcasm_kw):
        points["التهكم"] = "يتضمن تهكماً أو سخرية"
    else:
        points["التهكم"] = "لا يوجد تهكم واضح"

    return points


def analyze_with_gemini(image, api_key):
    """
    ✅ Gemini Vision مع معالجة أخطاء شاملة ومفصّلة
    """
    # --- التحقق من المفتاح أولاً ---
    api_key = api_key.strip()
    is_valid, msg = validate_api_key(api_key)
    if not is_valid:
        return None, msg

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = """أنت محلل متخصص في تحليل لقطات شاشة منشورات تويتر/X باللغة العربية.

انظر إلى الصورة بدقة واستخرج هذه المعلومات:

تعليمات مهمة جداً:
- منشور تويتر بنيته: [صورة المستخدم] [الاسم] [@username] [التاريخ] ثم [نص المنشور]
- قد يوجد أسفله تعليق أو رد من مستخدم آخر بنفس البنية
- استخرج @username بالشكل الصحيح مع علامة @
- محتوى_المنشور = نص المنشور الأصلي فقط بدون الاسم أو التاريخ
- التعليق = نص الرد أو التعليق فقط بدون الاسم أو التاريخ
- المدعو = اسم الشخص المُشار إليه داخل النص وليس أصحاب الحسابات

أجب بـ JSON فقط بهذا الشكل بالضبط:
{
  "معرف_المنشور": "@username أو غير_محدد",
  "معرف_التعليق": "@username أو غير_محدد",
  "المدعو": "الاسم أو غير_محدد",
  "محتوى_المنشور": "نص المنشور الأصلي كاملاً",
  "المقطع": "وصف الميديا إن وجدت أو لا_يوجد",
  "التعليق": "نص التعليق كاملاً أو غير_محدد",
  "الرأي": "الموقف الرئيسي بجملة واحدة",
  "التهكم": "نعم مع توضيح مختصر أو لا"
}

لا تضف أي نص خارج الـ JSON."""

        response = model.generate_content([prompt, image])
        raw = response.text.strip()

        # تنظيف الرد
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*',     '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$',     '', raw, flags=re.MULTILINE)

        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            result = json.loads(json_match.group())
            return result, None

        return None, "❌ لم يُرجع Gemini JSON صالح - حاول مرة أخرى"

    except json.JSONDecodeError as e:
        return None, f"❌ خطأ في تحليل JSON: {str(e)}"

    except Exception as e:
        err = str(e)

        # ✅ رسائل خطأ واضحة حسب نوع الخطأ
        if "API_KEY_INVALID" in err or "400" in err:
            return None, (
                "🔑 مفتاح API غير صالح\n\n"
                "الحل:\n"
                "1. اذهب إلى aistudio.google.com/apikey\n"
                "2. اضغط Create API Key\n"
                "3. انسخ المفتاح الجديد (يبدأ بـ AIza)\n"
                "4. ألصقه في خانة المفتاح بالشريط الجانبي"
            )
        elif "PERMISSION_DENIED" in err or "403" in err:
            return None, "🚫 المفتاح موجود لكن بدون صلاحية - فعّل Gemini API في مشروعك على Google Cloud"
        elif "QUOTA_EXCEEDED" in err or "429" in err:
            return None, "⏱️ تجاوزت حد الاستخدام المجاني - انتظر دقيقة ثم أعد المحاولة"
        elif "timeout" in err.lower() or "deadline" in err.lower():
            return None, "🌐 انتهت مهلة الاتصال - تحقق من الإنترنت وأعد المحاولة"
        elif "model" in err.lower() and "not found" in err.lower():
            return None, "🤖 نموذج Gemini غير متاح - جرب تغيير النموذج إلى gemini-pro"
        else:
            return None, f"❌ خطأ غير متوقع: {err}"


# ============================================================
# --- إعدادات حقول النتائج ---
# ============================================================
FIELD_CONFIG = {
    "معرف_المنشور":  {"icon": "🔵", "label": "معرف المنشور",  "css": "card-id",      "hint": "@username صاحب المنشور"},
    "معرف_التعليق":  {"icon": "🟣", "label": "معرف التعليق",  "css": "card-id",      "hint": "@username صاحب التعليق"},
    "المدعو":        {"icon": "👤", "label": "المدعو",         "css": "result-card",  "hint": "الشخص المذكور في النص"},
    "محتوى_المنشور": {"icon": "📝", "label": "محتوى المنشور", "css": "card-content", "hint": "نص المنشور الأصلي"},
    "المقطع":        {"icon": "🎬", "label": "المقطع",         "css": "card-media",   "hint": "الفيديو أو الصورة المرفقة"},
    "التعليق":       {"icon": "💬", "label": "التعليق",        "css": "card-comment", "hint": "نص التعليق أو الرد"},
    "الرأي":         {"icon": "⚖️", "label": "الرأي",          "css": "card-opinion", "hint": "الموقف أو الحكم"},
    "التهكم":        {"icon": "😏", "label": "التهكم",         "css": "card-sarcasm", "hint": "وجود تهكم أو سخرية"},
}


def render_result_card(key, value):
    """
    عرض بطاقة نتيجة واحدة بـ RTL صحيح
    """
    cfg = FIELD_CONFIG.get(key, {"icon": "📌", "label": key, "css": "result-card", "hint": ""})
    undefined_values = ["غير مُحدد", "غير_محدد", "غير محدد", "غير محددة", None, ""]
    is_undefined = (value in undefined_values)

    badge         = '<span class="missing-badge">غير محدد</span>' if is_undefined else '<span class="verified-badge">✓ محدد</span>'
    value_class   = "undefined" if is_undefined else ""
    display_value = "—" if is_undefined else str(value)

    html = f"""
    <div class="result-card {cfg['css']}" dir="rtl">
        <div class="card-label">
            {cfg['icon']} {cfg['label']}
            {badge}
            <span style="font-size:11px; color:#9ca3af; font-weight:normal; margin-right:6px;">
                ({cfg['hint']})
            </span>
        </div>
        <div class="card-value {value_class}" dir="rtl" style="text-align:right;">
            {display_value}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# --- الشريط الجانبي ---
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ الإعدادات")

    analysis_mode = st.radio(
        "طريقة التحليل",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق ✨)"],
        index=1
    )

    api_key = ""
    if "Gemini" in analysis_mode:

        # ✅ تحميل المفتاح من secrets تلقائياً إن وُجد
        default_key = ""
        try:
            default_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            default_key = ""

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            value=default_key,
            type="password",
            placeholder="AIzaSy...",
            help="احصل على مفتاح مجاني من aistudio.google.com"
        )

        # ✅ التحقق الفوري من صيغة المفتاح
        if api_key:
            is_valid, val_msg = validate_api_key(api_key)
            if is_valid:
                st.markdown("""
                <div style='background:#dcfce7; border-radius:8px;
                            padding:8px 12px; font-size:13px; color:#15803d;
                            direction:rtl; margin-top:4px;'>
                    ✅ صيغة المفتاح صحيحة
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='background:#fef2f2; border-radius:8px;
                            padding:8px 12px; font-size:13px; color:#dc2626;
                            direction:rtl; margin-top:4px;'>
                    {val_msg}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class='info-banner' style='font-size:13px; margin-top:6px;'>
                💡 للحصول على مفتاح مجاني:<br>
                <a href='https://aistudio.google.com/apikey' target='_blank'>
                    👉 aistudio.google.com/apikey
                </a>
            </div>
            """, unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📌 النقاط المُستخرجة")
    all_fields = list(FIELD_CONFIG.keys())
    points_to_show = st.multiselect(
        "اختر النقاط للعرض",
        options=all_fields,
        default=all_fields,
        format_func=lambda x: f"{FIELD_CONFIG[x]['icon']} {FIELD_CONFIG[x]['label']}"
    )

    st.divider()
    st.markdown("""
    <div style='font-size:13px; color:#6b7280; direction:rtl; line-height:1.8;'>
        <b>النسخة:</b> 3.1<br>
        <b>الصيغ:</b> PNG, JPG, JPEG, WEBP<br>
        <b>الحد الأقصى:</b> 200MB
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# --- الواجهة الرئيسية ---
# ============================================================
st.markdown(
    "<h1 style='text-align:right; direction:rtl;'>📸 تحليل الصور في نقاط</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align:right; color:#6b7280; direction:rtl;'>"
    "ارفع لقطة شاشة لمنشور تويتر/X وسيتم تحليلها وتنظيمها تلقائياً"
    "</p>",
    unsafe_allow_html=True
)

col1, col2 = st.columns([1, 1], gap="large")

# ============================================================
# --- العمود الأيمن: رفع الصورة ---
# ============================================================
with col1:
    st.markdown(
        "<h3 style='direction:rtl; text-align:right;'>📤 رفع الصورة</h3>",
        unsafe_allow_html=True
    )

    uploaded = st.file_uploader(
        "اختر صورة أو اسحبها هنا",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="visible"
    )

    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="الصورة المرفوعة", use_container_width=True)

        fmt = getattr(img, 'format', None) or uploaded.type.split('/')[-1].upper()
        st.markdown(f"""
        <div class='result-card' style='margin-top:8px;'>
            <div class='card-label'>📊 معلومات الصورة</div>
            <div class='card-value'>
                📐 الأبعاد: {img.width} × {img.height} بكسل<br>
                📁 الصيغة: {fmt}<br>
                💾 الحجم: {len(uploaded.getvalue()) / 1024:.1f} KB
            </div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# --- العمود الأيسر: التحليل والنتائج ---
# ============================================================
with col2:
    st.markdown(
        "<h3 style='direction:rtl; text-align:right;'>🔍 النتائج</h3>",
        unsafe_allow_html=True
    )

    if not uploaded:
        st.markdown("""
        <div class='warning-banner'>
            📂 قم برفع صورة من الجهة اليمنى للبدء
        </div>
        """, unsafe_allow_html=True)

    else:
        analyze_btn = st.button("🚀 تحليل الصورة الآن", use_container_width=True)

        if analyze_btn:
            img     = Image.open(uploaded)
            results = None
            used_mode = ""

            # ============================================
            # طريقة Gemini AI
            # ============================================
            if "Gemini" in analysis_mode:

                if not api_key or not api_key.strip():
                    st.markdown("""
                    <div class='error-banner'>
                        🔑 أدخل مفتاح Gemini API في الشريط الجانبي أولاً<br>
                        <small>
                            <a href='https://aistudio.google.com/apikey' target='_blank'>
                                احصل على مفتاح مجاني من هنا
                            </a>
                        </small>
                    </div>
                    """, unsafe_allow_html=True)
                    st.stop()

                # التحقق من صيغة المفتاح
                is_valid, val_msg = validate_api_key(api_key)
                if not is_valid:
                    st.markdown(f"""
                    <div class='error-banner'>
                        {val_msg}
                    </div>
                    """, unsafe_allow_html=True)
                    st.stop()

                with st.spinner("🤖 Gemini AI يحلل الصورة..."):
                    results, error_msg = analyze_with_gemini(img, api_key)
                    used_mode = "Gemini AI"

                # ✅ عرض الخطأ بشكل منظم مع الحل
                if error_msg:
                    st.markdown(f"""
                    <div class='error-banner'>
                        <b>⚠️ خطأ في Gemini:</b><br><br>
                        <span style='white-space:pre-line;'>{error_msg}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.info("🔄 يتم التحويل تلقائياً إلى OCR...")
                    results = None

            # ============================================
            # طريقة OCR (أو fallback)
            # ============================================
            if results is None:
                with st.spinner("🔤 OCR يستخرج النص..."):
                    text, mentions_eng = extract_text_ocr(img)
                    results   = analyze_post_smart(text, mentions_eng)
                    used_mode = used_mode or "OCR"

                with st.expander("📝 النص المستخرج بالـ OCR (للمراجعة)"):
                    st.code(text, language=None)
                    if mentions_eng:
                        st.success(f"🔵 معرفات وُجدت: {' | '.join(mentions_eng)}")
                    else:
                        st.warning("⚠️ لم يتم العثور على @معرفات - استخدم Gemini AI للحصول على نتائج أدق")

            # ============================================
            # عرض النتائج
            # ============================================
            filled = sum(
                1 for v in results.values()
                if v not in ["غير مُحدد", "غير_محدد", "غير محدد", "غير محددة", None, ""]
            )
            total = len(results)
            pct   = int(filled / total * 100)

            st.success(f"✅ تم التحليل بـ {used_mode} | {filled}/{total} نقاط ({pct}%)")
            st.progress(pct / 100)

            st.markdown(
                "<h4 style='direction:rtl; text-align:right; margin-top:16px;'>📌 النقاط المُستخرجة</h4>",
                unsafe_allow_html=True
            )

            for key in points_to_show:
                if key in results:
                    render_result_card(key, results[key])

            # ============================================
            # تنزيل النتائج
            # ============================================
            st.divider()
            st.markdown(
                "<div style='direction:rtl; font-weight:bold; margin-bottom:8px;'>💾 تنزيل النتائج</div>",
                unsafe_allow_html=True
            )

            txt_lines = []
            for k, v in results.items():
                cfg   = FIELD_CONFIG.get(k, {})
                label = cfg.get("label", k)
                icon  = cfg.get("icon", "•")
                txt_lines.append(f"{icon} {label}: {v}")
            txt_output = "\n".join(txt_lines)

            col_a, col_b = st.columns(2)

            with col_a:
                st.download_button(
                    "📄 تنزيل TXT",
                    data=txt_output,
                    file_name="تحليل_الصورة.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col_b:
                json_output = json.dumps(results, ensure_ascii=False, indent=2)
                st.download_button(
                    "📋 تنزيل JSON",
                    data=json_output,
                    file_name="تحليل_الصورة.json",
                    mime="application/json",
                    use_container_width=True
                )


# ============================================================
# --- التعليمات ---
# ============================================================
st.divider()
with st.expander("ℹ️ كيفية الاستخدام"):
    st.markdown("""
    <div style='direction:rtl; text-align:right; line-height:2.2;'>
        <b>1.</b> ارفع لقطة شاشة لمنشور تويتر/X<br>
        <b>2.</b> اختر طريقة التحليل من الشريط الجانبي:<br>
        &nbsp;&nbsp;&nbsp;• <b>🤖 Gemini AI</b> ✨: الأدق - يفهم الصورة كاملاً ويستخرج @username بدقة<br>
        &nbsp;&nbsp;&nbsp;• <b>🔤 OCR</b>: مجاني - يعمل بدون API لكن أقل دقة<br>
        <b>3.</b> اضغط "تحليل الصورة الآن"<br>
        <b>4.</b> راجع النتائج ونزّلها بصيغة TXT أو JSON<br>
        <br>
        <b>💡 نصيحة للحصول على مفتاح Gemini مجاني:</b><br>
        &nbsp;&nbsp;&nbsp;اذهب إلى 
        <a href='https://aistudio.google.com/apikey' target='_blank'>
            aistudio.google.com/apikey
        </a>
        ← اضغط Create API Key ← انسخ المفتاح
    </div>
    """, unsafe_allow_html=True)
