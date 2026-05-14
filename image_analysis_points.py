# -- coding: utf-8 --
"""
تحليل الصور في نقاط - النسخة 3.0 (إصلاح OCR + Gemini + RTL)
"""

import streamlit as st
import pytesseract
from PIL import Image
import numpy as np
import cv2
import re
import base64
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
# --- CSS محسّن للـ RTL + عرض النقاط ---
# ============================================================
st.markdown("""
<style>
    /* RTL عام */
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* إصلاح Streamlit inputs */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div,
    .stMultiSelect div {
        direction: rtl !important;
        text-align: right !important;
    }

    /* زر التحليل */
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

    /* ===== بطاقات النتائج ===== */

    /* بطاقة عادية */
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
        margin-bottom: 4px;
    }
    .result-card .card-value {
        font-size: 15px;
        color: #1f2937;
        line-height: 1.7;
        white-space: pre-wrap;
        word-break: break-word;
        direction: rtl;
        text-align: right;
    }
    .result-card .card-value.undefined {
        color: #9ca3af;
        font-style: italic;
    }

    /* بطاقة المعرفات */
    .card-id {
        border-right-color: #7c3aed !important;
        background: #f5f3ff !important;
    }
    .card-id .card-label { color: #6d28d9 !important; }

    /* بطاقة المحتوى - أكبر */
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

    /* بطاقة التعليق */
    .card-comment {
        border-right-color: #0891b2 !important;
        background: #f0f9ff !important;
    }
    .card-comment .card-label { color: #0e7490 !important; }

    /* بطاقة الرأي */
    .card-opinion {
        border-right-color: #d97706 !important;
        background: #fffbeb !important;
    }
    .card-opinion .card-label { color: #b45309 !important; }

    /* بطاقة المقطع */
    .card-media {
        border-right-color: #e11d48 !important;
        background: #fff1f2 !important;
    }
    .card-media .card-label { color: #be123c !important; }

    /* بطاقة التهكم */
    .card-sarcasm {
        border-right-color: #ea580c !important;
        background: #fff7ed !important;
    }

    /* شريط التحقق */
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

    /* تحذير وتنبيه */
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

    /* إخفاء label فارغة */
    .stFileUploader label { direction: rtl; text-align: right; }

    /* شريط جانبي */
    section[data-testid="stSidebar"] > div {
        direction: rtl;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# --- الوظائف ---
# ============================================================

def preprocess_image_ocr(image):
    """معالجة الصورة لـ OCR - نسخة محسّنة"""
    img = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # تكبير 2x لتحسين الدقة
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    # إزالة الضوضاء مع الحفاظ على الحواف
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    # Threshold ذكي
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def extract_text_ocr(image):
    """
    استخراج النص بـ OCR مع الحفاظ الكامل على @usernames
    """
    try:
        # نسختان: واحدة للنص العربي وواحدة للـ @ الإنجليزي
        img_arr = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        # استخراج النص الكامل (عربي + إنجليزي)
        config_full = '--oem 3 --psm 6'
        text_full = pytesseract.image_to_string(gray, lang='ara+eng', config=config_full)

        # استخراج إنجليزي فقط للـ @usernames
        config_eng = '--oem 3 --psm 6'
        text_eng = pytesseract.image_to_string(gray, lang='eng', config=config_eng)

        # استخراج @mentions من النص الإنجليزي (أدق)
        mentions_eng = re.findall(r'@[A-Za-z0-9_]+', text_eng)

        # تنظيف النص العربي مع الحفاظ على @
        text_clean = re.sub(r'[^\u0600-\u06FF\s\d@#_\.,;:!؟\-\u064b-\u065f]', ' ', text_full)
        text_clean = re.sub(r'\s+', ' ', text_clean).strip()

        return text_clean, mentions_eng

    except Exception as e:
        return f"خطأ: {str(e)}", []


def analyze_post_smart(text, mentions_eng):
    """
    تحليل ذكي للنص مع دعم @usernames المستخرجة منفصلاً
    """
    points = {
        "معرف_المنشور": "غير مُحدد",
        "معرف_التعليق": "غير مُحدد",
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": "غير مُحدد",
        "التهكم": "غير مُحدد"
    }

    # --- المعرفات: من OCR الإنجليزي (أدق) ---
    if len(mentions_eng) >= 1:
        points["معرف_المنشور"] = mentions_eng[0]
    if len(mentions_eng) >= 2:
        points["معرف_التعليق"] = mentions_eng[1]

    # إذا لم يجد من الإنجليزي، جرب من النص الكامل
    if points["معرف_المنشور"] == "غير مُحدد":
        mentions_ar = re.findall(r'@[\w\u0600-\u06FF]+', text)
        if len(mentions_ar) >= 1:
            points["معرف_المنشور"] = mentions_ar[0]
        if len(mentions_ar) >= 2:
            points["معرف_التعليق"] = mentions_ar[1]

    # --- تقسيم النص إلى أسطر نظيفة ---
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]

    # --- المدعو ---
    name_patterns = [
        r'(?:ردّ على|رد على|يرد على|ذكر|بشيخنا|الشيخ|الأستاذ|الدكتور)\s+([\u0600-\u06FF][\u0600-\u06FF\s]{2,25})',
        r'(?:سالم|محمد|عبدالله|أحمد|علي)\s+[\u0600-\u06FF]{2,15}',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip() if '(' in pattern or 'بشيخنا' in pattern else match.group(0).strip()
            points["المدعو"] = name
            break

    # --- محتوى المنشور: أسطر بعد أول معرف وقبل التعليق ---
    # نبحث عن أطول سطر يحتوي على نص عربي حقيقي (> 15 حرف)
    arabic_lines = [l for l in lines if len(re.findall(r'[\u0600-\u06FF]', l)) > 10]
    if arabic_lines:
        # أول كتلة نص عربي = محتوى المنشور
        points["محتوى_المنشور"] = arabic_lines[0]
        # آخر كتلة = التعليق
        if len(arabic_lines) >= 2:
            points["التعليق"] = '\n'.join(arabic_lines[1:3])

    # --- المقطع ---
    video_kw = ["فيديو", "مقطع", "تسجيل", "كليب", "يوتيوب", "تيكتوك", "رابط"]
    found = [k for k in video_kw if k in text]
    if found:
        points["المقطع"] = f"محتوى مرئي: {', '.join(found)}"

    # --- الرأي ---
    opinion_map = {
        "تحريم|محرم|حرام": "تحريم الخروج على ولي الأمر",
        "موافق|صح|صحيح": "موافقة على المحتوى",
        "مخالف|خطأ|غلط": "مخالفة للمحتوى",
        "تهكم|ساخر|سخرية": "تعليق ساخر",
        "أرى|رأيي|أعتقد": "رأي شخصي",
    }
    for pattern, desc in opinion_map.items():
        if re.search(pattern, text):
            points["الرأي"] = desc
            break

    # --- التهكم ---
    sarcasm_kw = ["تهكم", "ساخر", "سخرية", "😂", "🤣", "😅", "هههه", "يضحك", "مضحك"]
    if any(k in text for k in sarcasm_kw):
        points["التهكم"] = "يتضمن تهكماً أو سخرية"
    else:
        points["التهكم"] = "لا يوجد تهكم واضح"

    return points


def analyze_with_gemini(image, api_key):
    """
    ✅ Gemini Vision مع Prompt محسّن جداً لمنشورات تويتر العربية
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # ✅ Prompt دقيق ومفصّل
        prompt = """أنت محلل متخصص في تحليل لقطات شاشة منشورات تويتر/X باللغة العربية.

انظر إلى الصورة بدقة واستخرج هذه المعلومات:

**تعليمات مهمة جداً:**
- منشور تويتر بنيته: [صورة المستخدم] [الاسم] [@username] [التاريخ] ثم [نص المنشور]
- قد يوجد أسفله تعليق/رد من مستخدم آخر بنفس البنية
- استخرج @username بالشكل الصحيح مع علامة @
- محتوى_المنشور = نص المنشور الأصلي فقط (بدون الاسم أو التاريخ)
- التعليق = نص الرد/التعليق فقط (بدون الاسم أو التاريخ)
- المدعو = اسم الشخص المُشار إليه داخل النص (غير أصحاب الحسابات)

أجب بـ JSON فقط بهذا الشكل بالضبط:
{
  "معرف_المنشور": "@username_هنا أو غير_محدد",
  "معرف_التعليق": "@username_هنا أو غير_محدد",
  "المدعو": "الاسم_هنا أو غير_محدد",
  "محتوى_المنشور": "نص_المنشور_الأصلي_كاملاً",
  "المقطع": "وصف_الميديا_إن_وجدت أو لا_يوجد",
  "التعليق": "نص_التعليق_كاملاً أو غير_محدد",
  "الرأي": "الموقف_الرئيسي_بجملة_واحدة",
  "التهكم": "نعم - توضيح مختصر / لا"
}

لا تضف أي نص خارج الـ JSON."""

        response = model.generate_content([prompt, image])
        raw = response.text.strip()

        # تنظيف الرد من ```json إذا وُجدت
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        # استخراج JSON
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            result = json.loads(json_match.group())
            return result, None
        return None, "لم يُرجع Gemini JSON صالح"

    except json.JSONDecodeError as e:
        return None, f"خطأ في تحليل JSON: {str(e)}"
    except Exception as e:
        return None, f"خطأ في Gemini: {str(e)}"


# ============================================================
# --- دالة عرض النتيجة - RTL منظم ---
# ============================================================

FIELD_CONFIG = {
    "معرف_المنشور":  {"icon": "🔵", "label": "معرف المنشور",  "css": "card-id",      "hint": "@username صاحب المنشور"},
    "معرف_التعليق":  {"icon": "🟣", "label": "معرف التعليق",  "css": "card-id",      "hint": "@username صاحب التعليق"},
    "المدعو":        {"icon": "👤", "label": "المدعو",         "css": "result-card",  "hint": "الشخص المذكور في النص"},
    "محتوى_المنشور": {"icon": "📝", "label": "محتوى المنشور", "css": "card-content", "hint": "نص المنشور الأصلي"},
    "المقطع":        {"icon": "🎬", "label": "المقطع",         "css": "card-media",   "hint": "الفيديو أو الصورة المرفقة"},
    "التعليق":       {"icon": "💬", "label": "التعليق",        "css": "card-comment", "hint": "نص التعليق/الرد"},
    "الرأي":         {"icon": "⚖️", "label": "الرأي",          "css": "card-opinion", "hint": "الموقف أو الحكم"},
    "التهكم":        {"icon": "😏", "label": "التهكم",         "css": "card-sarcasm", "hint": "وجود تهكم أو سخرية"},
}

def render_result_card(key, value):
    """عرض بطاقة نتيجة واحدة بـ RTL صحيح"""
    cfg = FIELD_CONFIG.get(key, {"icon": "📌", "label": key, "css": "result-card", "hint": ""})
    is_undefined = (value in ["غير مُحدد", "غير_محدد", "غير محدد", None, ""])
    
    badge = '<span class="missing-badge">غير محدد</span>' if is_undefined else '<span class="verified-badge">✓ محدد</span>'
    value_class = "undefined" if is_undefined else ""
    display_value = "—" if is_undefined else str(value)

    html = f"""
    <div class="result-card {cfg['css']}" dir="rtl">
        <div class="card-label">
            {cfg['icon']} {cfg['label']}
            {badge}
            <span style="font-size:11px; color:#9ca3af; font-weight:normal; margin-right:6px;">({cfg['hint']})</span>
        </div>
        <div class="card-value {value_class}" dir="rtl" style="text-align:right;">{display_value}</div>
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
        index=1  # Gemini افتراضي لأنه أدق
    )

    api_key = ""
    if "Gemini" in analysis_mode:
        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            placeholder="AIza...",
            help="احصل على مفتاح مجاني من aistudio.google.com"
        )
        if not api_key:
            st.markdown("""
            <div class='info-banner' style='font-size:13px;'>
            💡 احصل على مفتاح مجاني:<br>
            <a href='https://aistudio.google.com' target='_blank'>aistudio.google.com</a>
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
    st.markdown("### 📋 معلومات")
    st.markdown("""
    <div style='font-size:13px; color:#6b7280; direction:rtl;'>
    <b>النسخة:</b> 3.0<br>
    <b>الصيغ:</b> PNG, JPG, JPEG, WEBP<br>
    <b>الحد الأقصى:</b> 200MB
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# --- الواجهة الرئيسية ---
# ============================================================
st.markdown("<h1 style='text-align:right; direction:rtl;'>📸 تحليل الصور في نقاط</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:right; color:#6b7280; direction:rtl;'>ارفع لقطة شاشة لمنشور تويتر/X وسيتم تحليلها وتنظيمها تلقائياً</p>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap="large")

# ============================================================
# --- العمود الأيمن: رفع الصورة ---
# ============================================================
with col1:
    st.markdown("<h3 style='direction:rtl; text-align:right;'>📤 رفع الصورة</h3>", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "اختر صورة أو اسحبها هنا",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="visible"
    )

    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="الصورة المرفوعة", use_container_width=True)

        st.markdown(f"""
        <div class='result-card' style='margin-top:8px;'>
            <div class='card-label'>📊 معلومات الصورة</div>
            <div class='card-value'>
                📐 الأبعاد: {img.width} × {img.height} بكسل<br>
                📁 الصيغة: {getattr(img, 'format', None) or uploaded.type.split('/')[-1].upper()}<br>
                💾 الحجم: {len(uploaded.getvalue()) / 1024:.1f} KB
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# --- العمود الأيسر: التحليل والنتائج ---
# ============================================================
with col2:
    st.markdown("<h3 style='direction:rtl; text-align:right;'>🔍 النتائج</h3>", unsafe_allow_html=True)

    if not uploaded:
        st.markdown("""
        <div class='warning-banner'>
            📂 قم برفع صورة من الجهة اليمنى للبدء
        </div>
        """, unsafe_allow_html=True)
    else:
        analyze_btn = st.button("🚀 تحليل الصورة الآن", use_container_width=True)

        if analyze_btn:
            img = Image.open(uploaded)
            results = None
            error_msg = None
            used_mode = ""

            # ---- تحديد طريقة التحليل ----
            if "Gemini" in analysis_mode:
                if not api_key:
                    st.error("⚠️ أدخل مفتاح Gemini API أولاً من الشريط الجانبي")
                    st.stop()

                with st.spinner("🤖 Gemini AI يحلل الصورة..."):
                    results, error_msg = analyze_with_gemini(img, api_key)
                    used_mode = "Gemini AI"

                if error_msg:
                    st.warning(f"⚠️ {error_msg} — التحويل إلى OCR...")
                    results = None

            if results is None:
                with st.spinner("🔤 OCR يستخرج النص..."):
                    text, mentions_eng = extract_text_ocr(img)
                    results = analyze_post_smart(text, mentions_eng)
                    used_mode = "OCR"

                    # عرض النص الخام للمراجعة
                    with st.expander("📝 النص المستخرج (للمراجعة)"):
                        st.code(text, language=None)
                        if mentions_eng:
                            st.success(f"🔵 معرفات وُجدت: {' | '.join(mentions_eng)}")

            # ---- إحصائيات سريعة ----
            filled = sum(1 for v in results.values() if v not in ["غير مُحدد", "غير_محدد", "غير محدد", None, ""])
            total = len(results)
            pct = int(filled / total * 100)

            st.success(f"✅ تم التحليل بـ {used_mode} | {filled}/{total} نقاط ({pct}%)")

            # شريط تقدم
            st.progress(pct / 100)

            # ---- عرض النقاط بـ RTL منظم ----
            st.markdown("<h4 style='direction:rtl; text-align:right; margin-top:16px;'>📌 النقاط المُستخرجة</h4>",
                        unsafe_allow_html=True)

            for key in points_to_show:
                if key in results:
                    render_result_card(key, results[key])

            # ---- تنزيل النتائج ----
            st.divider()
            st.markdown("<div style='direction:rtl; font-weight:bold;'>💾 تنزيل النتائج</div>",
                        unsafe_allow_html=True)

            col_a, col_b = st.columns(2)

            txt_lines = []
            for k, v in results.items():
                cfg = FIELD_CONFIG.get(k, {})
                label = cfg.get("label", k)
                txt_lines.append(f"{cfg.get('icon','•')} {label}: {v}")
            txt_output = "\n".join(txt_lines)

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
    <div style='direction:rtl; text-align:right; line-height:2;'>
    <b>1.</b> ارفع لقطة شاشة لمنشور تويتر/X<br>
    <b>2.</b> اختر طريقة التحليل من الشريط الجانبي:<br>
    &nbsp;&nbsp;&nbsp;• <b>Gemini AI</b> ✨: الأدق - يفهم الصورة كاملاً ويستخرج @username بدقة<br>
    &nbsp;&nbsp;&nbsp;• <b>OCR</b>: مجاني - يعمل بدون API لكن أقل دقة<br>
    <b>3.</b> اضغط "تحليل الصورة الآن"<br>
    <b>4.</b> راجع النتائج ونزّلها بصيغة TXT أو JSON<br>
    <br>
    <b>💡 نصيحة:</b> Gemini AI يعطي نتائج أدق بكثير خصوصاً لـ @usernames ومحتوى المنشور
    </div>
    """, unsafe_allow_html=True)
