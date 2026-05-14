# -- coding: utf-8 --
"""
تحليل الصور في نقاط - النسخة المُحسَّنة 2.0
"""

import streamlit as st
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2
import re
import base64
from io import BytesIO
import google.generativeai as genai  # ✅ إضافة جديدة - AI أذكى

# ============================================================
# --- إعداد التنسيق العربي ---
# ============================================================
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide"
)

st.markdown("""
<style>
    body, .stApp, [data-testid="stAppViewContainer"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton > button {
        float: right;
        background-color: #2563EB;
        color: white;
        border-radius: 8px;
        padding: 8px 20px;
        font-size: 16px;
    }
    .stButton > button:hover {
        background-color: #1d4ed8;
    }
    .result-card {
        background: #F0F4F8;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 8px 0;
        border-right: 5px solid #2563EB;
        direction: rtl;
    }
    .result-card b {
        color: #1e40af;
    }
    .success-banner {
        background: #d1fae5;
        border-right: 5px solid #10b981;
        padding: 12px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .warning-banner {
        background: #fef3c7;
        border-right: 5px solid #f59e0b;
        padding: 12px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# --- الوظائف المُحسَّنة ---
# ============================================================

def preprocess_image(image):
    """
    ✅ تحسين: معالجة الصورة بشكل أفضل قبل OCR
    """
    img = np.array(image.convert('RGB'))
    
    # تحويل لرمادي
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # تكبير الصورة لتحسين دقة OCR
    scale = 2.0
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # إزالة الضوضاء
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    
    # ✅ إصلاح: استخدام THRESH_BINARY بدلاً من BINARY_INV
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # تحسين الحدة
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(thresh, -1, kernel)
    
    return Image.fromarray(sharpened)


def extract_arabic_text(image):
    """
    ✅ تحسين: استخراج النص مع الحفاظ على @ والأرقام
    """
    try:
        processed = preprocess_image(image)
        img_array = np.array(processed)
        
        # إعدادات OCR محسّنة
        config = '--oem 3 --psm 3 -c preserve_interword_spaces=1'
        text = pytesseract.image_to_string(img_array, lang='ara+eng', config=config)
        
        # ✅ إصلاح: الحفاظ على @ والأرقام والروابط
        text = re.sub(r'[^\u0600-\u06FF\s\d@#_\.,;:!؟\-]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    except Exception as e:
        return f"خطأ في استخراج النص: {str(e)}"


def analyze_post_smart(text):
    """
    ✅ تحسين كبير: تحليل ذكي لأي نص بدون كلمات مُشفرة
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

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # ✅ استخراج المعرفات بشكل أفضل
    mentions = re.findall(r'@[\w\u0600-\u06FF]+', text)
    if len(mentions) >= 1:
        points["معرف_المنشور"] = mentions[0]
    if len(mentions) >= 2:
        points["معرف_التعليق"] = mentions[1]

    # ✅ استخراج المدعو - أكثر مرونة
    name_patterns = [
        r'(?:ردّ على|رد على|يرد على|يرد|ذكر)\s+([\u0600-\u06FF\s]+)',
        r'(?:المدعو|الشيخ|الأستاذ|الدكتور)\s+([\u0600-\u06FF\s]{3,30})',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            points["المدعو"] = match.group(1).strip()
            break
    # إذا لم يجد، استخدم أول اسم مذكور
    if points["المدعو"] == "غير مُحدد" and mentions:
        points["المدعو"] = mentions[0]

    # ✅ استخراج محتوى المنشور - أول 3 أسطر
    if len(lines) >= 1:
        post_content = ' '.join(lines[:3])
        if len(post_content) > 20:
            points["محتوى_المنشور"] = post_content[:200] + ("..." if len(post_content) > 200 else "")

    # ✅ استخراج التعليق - آخر 2 سطر
    if len(lines) >= 2:
        comment = ' '.join(lines[-2:])
        if len(comment) > 10:
            points["التعليق"] = comment[:200]

    # ✅ كشف المقطع بشكل أوسع
    video_keywords = ["فيديو", "مقطع", "تسجيل", "كليب", "رابط", "يوتيوب", "تيكتوك"]
    found_video = [kw for kw in video_keywords if kw in text]
    if found_video:
        points["المقطع"] = f"تم الكشف عن محتوى مرئي: ({', '.join(found_video)})"

    # ✅ استخراج الرأي - أذكى
    opinion_keywords = {
        "تحريم": "يتضمن حكماً شرعياً بالتحريم",
        "تحليل": "يتضمن تحليلاً للموضوع",
        "موافق": "يُعبّر عن موافقة",
        "مخالف": "يُعبّر عن مخالفة",
        "رأيي": "يُعبّر عن رأي شخصي",
        "أرى": "يُعبّر عن رأي شخصي",
        "أعتقد": "يُعبّر عن رأي شخصي",
        "صحيح": "يُؤكد صحة الموضوع",
        "خطأ": "يُشير إلى وجود خطأ",
    }
    for keyword, description in opinion_keywords.items():
        if keyword in text:
            points["الرأي"] = description
            break

    # ✅ كشف التهكم بشكل أوسع
    sarcasm_keywords = ["تهكم", "ساخر", "سخرية", "😂", "🤣", "هههه", "😅", "يضحك", "مضحك"]
    found_sarcasm = [kw for kw in sarcasm_keywords if kw in text]
    if found_sarcasm:
        points["التهكم"] = "يتضمن تهكماً أو سخرية"

    return points


def analyze_with_gemini(image, api_key):
    """
    ✅ جديد: تحليل متقدم باستخدام Google Gemini Vision
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        حلل هذه الصورة التي تحتوي على نص عربي واستخرج المعلومات التالية بدقة:
        
        1. معرف_المنشور: معرف صاحب المنشور الأصلي (@username)
        2. معرف_التعليق: معرف صاحب التعليق (@username)
        3. المدعو: اسم الشخص المذكور أو المدعو في النص
        4. محتوى_المنشور: ملخص المنشور الأصلي
        5. المقطع: وصف المقطع أو الفيديو إن وجد
        6. التعليق: نص التعليق
        7. الرأي: الرأي أو الحكم المذكور
        8. التهكم: هل يوجد تهكم أو سخرية؟
        
        أجب بصيغة JSON فقط.
        """
        
        response = model.generate_content([prompt, image])
        
        # تحليل JSON من الرد
        json_text = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_text:
            import json
            return json.loads(json_text.group())
        return None
    except Exception as e:
        return None


# ============================================================
# --- الواجهة الرئيسية ---
# ============================================================
st.title("📸 تحليل الصور في نقاط")
st.markdown("<p style='color:#6b7280;'>قم برفع الصورة وسيتم تحليلها واستخراج النقاط الرئيسية تلقائياً</p>",
            unsafe_allow_html=True)

# ============================================================
# --- الشريط الجانبي ---
# ============================================================
with st.sidebar:
    st.header("⚙️ الإعدادات")
    
    analysis_mode = st.radio(
        "طريقة التحليل",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق)"],
        index=0
    )
    
    if "Gemini" in analysis_mode:
        api_key = st.text_input("🔑 مفتاح Gemini API", type="password",
                                 help="احصل على مفتاح مجاني من: https://aistudio.google.com")
    
    st.divider()
    st.markdown("### 📌 النقاط المُستخرجة")
    points_to_extract = st.multiselect(
        "اختر النقاط المطلوبة",
        ["معرف_المنشور", "معرف_التعليق", "المدعو",
         "محتوى_المنشور", "المقطع", "التعليق", "الرأي", "التهكم"],
        default=["معرف_المنشور", "معرف_التعليق", "المدعو",
                 "محتوى_المنشور", "المقطع", "التعليق", "الرأي", "التهكم"]
    )

# ============================================================
# --- منطقة رفع الصورة ---
# ============================================================
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📤 رفع الصورة")
    uploaded = st.file_uploader(
        "اختر صورة (PNG, JPG, JPEG, WEBP)",
        type=["png", "jpg", "jpeg", "webp"],
        help="يمكنك أيضاً سحب الصورة وإفلاتها هنا"
    )
    
    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="✅ الصورة المرفوعة", use_container_width=True)
        
        # ✅ معلومات الصورة
        st.markdown(f"""
        <div class='result-card'>
        📐 <b>الأبعاد:</b> {img.width} × {img.height} بكسل<br>
        📁 <b>الصيغة:</b> {img.format or uploaded.type}<br>
        💾 <b>الحجم:</b> {len(uploaded.getvalue()) / 1024:.1f} KB
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.subheader("🔍 التحليل والنتائج")
    
    if uploaded:
        analyze_btn = st.button("🚀 تحليل الصورة الآن", use_container_width=True)
        
        if analyze_btn:
            with st.spinner("⏳ جارٍ التحليل... يرجى الانتظار"):
                img = Image.open(uploaded)
                
                # --- اختيار طريقة التحليل ---
                if "Gemini" in analysis_mode and api_key:
                    results = analyze_with_gemini(img, api_key)
                    if not results:
                        st.warning("⚠️ فشل Gemini، سيتم التحويل إلى OCR التقليدي")
                        text = extract_arabic_text(img)
                        results = analyze_post_smart(text)
                else:
                    text = extract_arabic_text(img)
                    results = analyze_post_smart(text)
                
                st.success("✅ تم التحليل بنجاح!")
                
                # --- عرض النص المستخرج ---
                if "Gemini" not in analysis_mode:
                    with st.expander("📝 النص المستخرج من الصورة"):
                        st.text_area("", text, height=120, disabled=True)
                
                # --- عرض النقاط ---
                st.markdown("### 📌 النقاط المُستخرجة")
                for key, value in results.items():
                    if key in points_to_extract:
                        color = "#10b981" if value != "غير مُحدد" else "#9ca3af"
                        icon = "✅" if value != "غير مُحدد" else "⭕"
                        st.markdown(f"""
                        <div class='result-card'>
                        {icon} <b>{key}:</b><br>
                        <span style='color:{color}; margin-right:20px;'>{value}</span>
                        </div>
                        """, unsafe_allow_html=True)
                
                # --- تنزيل النتائج ---
                st.divider()
                col_a, col_b = st.columns(2)
                
                with col_a:
                    txt_output = "\n".join([f"{k}: {v}" for k, v in results.items()])
                    st.download_button(
                        "💾 تنزيل TXT",
                        data=txt_output,
                        file_name="تحليل_الصورة.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                with col_b:
                    import json
                    json_output = json.dumps(results, ensure_ascii=False, indent=2)
                    st.download_button(
                        "📋 تنزيل JSON",
                        data=json_output,
                        file_name="تحليل_الصورة.json",
                        mime="application/json",
                        use_container_width=True
                    )
    else:
        st.markdown("""
        <div class='warning-banner'>
        👆 قم برفع صورة أولاً من الجهة اليسرى للبدء في التحليل
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# --- قسم التعليمات ---
# ============================================================
st.divider()
with st.expander("ℹ️ كيفية الاستخدام"):
    st.markdown("""
    1. **ارفع الصورة** من جهازك (PNG, JPG, WEBP)
    2. **اختر طريقة التحليل** من الشريط الجانبي:
       - **OCR تقليدي**: مجاني، يعمل دون إنترنت
       - **Gemini AI**: أدق بكثير، يحتاج مفتاح API مجاني
    3. **اضغط تحليل** وانتظر النتائج
    4. **نزّل النتائج** بصيغة TXT أو JSON
    """)
