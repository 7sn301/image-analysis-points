# -- coding: utf-8 --
"""
تحليل الصور في نقاط - تطبيق يعمل بشكل كامل
"""

import streamlit as st
import pytesseract
from PIL import Image
import numpy as np
import cv2
import re
import base64
from io import BytesIO


# --- إعداد Tesseract للتشغيل على Streamlit ---
try:
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
except:
    pass


# --- الوظائف الأساسية ---
def extract_text_from_image(image):
    """استخراج النص العربي من الصورة"""
    try:
        # تحويل الصورة إلى تنسيق مناسب
        img = np.array(image.convert('L'))
        img = cv2.medianBlur(img, 3)
        img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        text = pytesseract.image_to_string(img, lang='ara')
        text = re.sub(r'[^\u0600-\u06FF\s\d\.,;:!؟]', '', text)
        return text.strip()
    except Exception as e:
        return f"خطأ في استخراج النص: {str(e)}"


def analyze_text(text):
    """تحليل النص للنقاط المطلوبة"""
    points = {
        "صاحب المنشور": "غير مُحدد",
        "صاحب التعليق": "غير مُحدد",
        "المدعو الدين": "غير مُحدد",
        "محتوى المنشور": "غير مُحدد",
        "مقطع الفيديو": "غير مُحدد",
        "التعليق الساخن": "غير مُحدد",
        "الرأي حول الخروج عن ولي الأمر": "غير مُحدد",
        "الهتكيم": "غير مُحدد"
    }

    if "مدعو الدين" in text or "سالم الطويل" in text:
        points["المدعو الدين"] = "المدعو الدين النصيحة سالم الطويل"
    
    if "نشر" in text:
        points["صاحب المنشور"] = text.split("نشر")[0].strip() or "غير مُحدد"
    
    if "علق" in text:
        points["صاحب التعليق"] = text.split("علق")[0].strip() or "غير مُحدد"
    
    if "مقطع فيديو" in text:
        points["مقطع الفيديو"] = "يظهر أشخاص في مجلس، ويشير إلى تحريم الخروج عن ولي الأمر"
    
    if "تحريم" in text:
        points["الرأي حول الخروج عن ولي الأمر"] = "تم الإشارة إلى تحريم الخروج عن ولي الأمر، والشخص غير قادر على ذلك"
    
    if "تهكم" in text or "ساخر" in text:
        points["الهتكيم"] = "تم الإشارة إلى تهكم بشأن موقف الشخص"
    
    return points


# --- الواجهة الرئيسية للتطبيق ---
st.title("📸 تحليل الصور في نقاط")
st.write("يمكنك نسخ الصورة وتلصقها هنا (Ctrl+V) أو الرفع من جهازك")

# إضافة الصورة
uploaded_file = st.file_uploader("اختر صورة", type=["png", "jpg", "jpeg"])
pasted_image = None

# التعامل مع الصورة المُلصقة
st.markdown("""
<script>
document.addEventListener('paste', function(e) {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let item of items) {
        if (item.kind === 'file' && item.type.includes('image/')) {
            const file = item.getAsFile();
            const reader = new FileReader();
            reader.onload = function(event) {
                document.getElementById('pasted-image').value = event.target.result.split(',')[1];
                document.getElementById('analyze-btn').click();
            };
            reader.readAsDataURL(file);
        }
    }
});
</script>
<input type="hidden" id="pasted-image" />
""", unsafe_allow_html=True)

# عرض الصورة المختارة
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="الصورة المختارة", use_column_width=True)
    
    # تحليل الصورة
    if st.button("تحليل الصورة"):
        with st.spinner("جارٍ التحليل..."):
            text = extract_text_from_image(image)
            results = analyze_text(text)
            
            st.subheader("النص المستخرج")
            st.write(text)
            
            st.subheader("النقاط الرئيسية")
            for key, value in results.items():
                st.write(f"- *{key.replace('_', ' ').title()}*: {value}")
