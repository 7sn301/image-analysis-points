# -- coding: utf-8 --
"""
تحليل الصور في نقاط - مع التنسيق العربي الكامل من اليمين إلى اليسار
"""

import streamlit as st
import pytesseract
from PIL import Image
import numpy as np
import cv2
import re
import base64
from io import BytesIO


# --- إعداد التنسيق العربي ---
st.markdown("""
<style>
    body {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stApp {
        direction: rtl;
    }
    .stButton>button {
        float: right;
    }
    .stFileUploader>div>div>button {
        float: right;
    }
</style>
""", unsafe_allow_html=True)


# --- الوظائف الأساسية ---
def extract_arabic_text(image):
    """استخراج النص العربي بدقة عالية"""
    try:
        # تحويل الصورة وتحسينها
        img = np.array(image.convert('L'))
        img = cv2.medianBlur(img, 3)
        img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        
        # استخراج النص
        text = pytesseract.image_to_string(img, lang='ara', config='--oem 3 --psm 6')
        text = re.sub(r'[^\u0600-\u06FF\s\d\.,;:!؟]', '', text)
        return text.strip()
    except Exception as e:
        return f"خطأ في استخراج النص: {str(e)}"


def analyze_post(text):
    """تحليل النص مع التعرف على النقاط المطلوبة"""
    points = {
        "معرف_المنشور": "غير مُحدد",
        "معرف_التعليق": "غير مُحدد",
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": "غير مُحدد",
        "الهتكيم": "غير مُحدد"
    }

    # التعرف على المعرفات
    mentions = re.findall(r'(@\w+)', text)
    if len(mentions) >= 1:
        points["معرف_المنشور"] = mentions[0]
    if len(mentions) >= 2:
        points["معرف_التعليق"] = mentions[1]

    # التعرف على المدعو
    if any(word in text for word in ["مدعو الدين", "سالم الطويل", "النصيحة"]):
        points["المدعو"] = "المدعو الدين النصيحة سالم الطويل"

    # التعرف على المقطع والتحريم
    if "فيديو" in text or "مقطع" in text:
        points["المقطع"] = "يظهر أشخاص في مجلس، يتضمن محتوى يتعلق بالخروج عن ولي الأمر"
    
    if "تحريم" in text or "محرم" in text:
        points["الرأي"] = "تم الإشارة إلى تحريم الخروج عن ولي الأمر، والشخص غير قادر على ذلك"
    
    if "تهكم" in text or "ساخر" in text:
        points["الهتكيم"] = "يتضمن تهكمًا أو تعليقًا ساخرًا بشأن الموضوع"

    return points


# --- الواجهة الرئيسية ---
st.title("📸 تحليل الصور في نقاط")
st.write("قم بنسخ الصورة ولصقها هنا، أو ارفعها من جهازك")

# زر لصق الصورة
st.markdown("""
<script>
document.addEventListener('paste', function(e) {
    const items = e.clipboardData.items;
    for (let item of items) {
        if (item.kind === 'file' && item.type.includes('image')) {
            const reader = new FileReader();
            reader.onload = function(event) {
                document.getElementById('pasted_img').value = event.target.result.split(',')[1];
                document.getElementById('analyze_btn').click();
            };
            reader.readAsDataURL(item.getAsFile());
        }
    }
});
</script>
<input type='hidden' id='pasted_img' />
""", unsafe_allow_html=True)

# تحميل الصورة أو لصقها
uploaded = st.file_uploader("اختر صورة", type=["png", "jpg", "jpeg"])
pasted_img = st.session_state.get("pasted_img", "")

# عرض الصورة
if uploaded:
    img = Image.open(uploaded)
    st.image(img, caption="الصورة المرفوعة", use_column_width=True)
elif pasted_img:
    img = Image.open(BytesIO(base64.b64decode(pasted_img)))
    st.image(img, caption="الصورة المُلصقة", use_column_width=True)


# زر التحليل
analyze_btn = st.button("🔍 تحليل الصورة الآن", key="analyze_btn")

# التنفيذ
if analyze_btn and (uploaded or pasted_img):
    with st.spinner("جارٍ التحليل..."):
        if uploaded:
            text = extract_arabic_text(Image.open(uploaded))
        else:
            text = extract_arabic_text(Image.open(BytesIO(base64.b64decode(pasted_img))))
        
        results = analyze_post(text)
        
        # عرض النص
        st.subheader("📝 النص المستخرج")
        st.text_area("", text, height=150, disabled=True)
        
        # عرض النقاط
        st.subheader("📌 النقاط الرئيسية")
        for title, content in results.items():
            st.markdown(f"""
            <div style='background:#F0F4F8; padding:10px; border-radius:5px; margin:10px 0; border-right:4px solid #2563EB;'>
                <b>{title}:</b> {content}
            </div>
            """, unsafe_allow_html=True)
        
        # تنزيل النتائج
        st.download_button(
            "💾 تنزيل النتائج",
            data="\n".join([f"{k}: {v}" for k, v in results.items()]),
            file_name="تحليل_الصورة.txt",
            mime="text/plain"
        )


# --- قسم التعليمات ---
with st.expander("ℹ️ كيفية الاستخدام"):
    st.write("""
    1. انسخ الصورة من أي مكان (Ctrl+C)
    2. لصقها هنا (Ctrl+V)
    3. اضغط على تحليل الصورة
    4. جميع العناصر ستظهر من اليمين إلى اليسار
    """)
