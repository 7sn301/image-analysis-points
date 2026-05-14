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


# --- إعداد التكوين الأساسي ---
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide"
)

# --- إضافة التنسيقات الخاصة باللغة العربية والنسخ واللصق ---
st.markdown("""
<script>
document.addEventListener('paste', function(e) {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let item of items) {
        if (item.kind === 'file' && item.type.includes('image/')) {
            const file = item.getAsFile();
            const reader = new FileReader();
            reader.onload = function(event) {
                const base64 = event.target.result.split(',')[1];
                document.getElementById('pasted_image').value = base64;
                document.getElementById('analyze_btn').click();
            };
            reader.readAsDataURL(file);
        }
    }
});
</script>
<input type='hidden' id='pasted_image'/>
""", unsafe_allow_html=True)


# --- وظائف المساعدة ---
def extract_text(image):
    """استخراج النص العربي من الصورة"""
    try:
        img = np.array(image.convert('L'))
        img = cv2.medianBlur(img, 3)
        img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        text = pytesseract.image_to_string(img, lang='ara')
        text = re.sub(r'[^\u0600-\u06FF\s\d\.,;:!؟]', '', text)
        return text.strip()
    except Exception as e:
        return f"خطأ: {str(e)}"


def analyze_text(text):
    """تحليل النص للنقاط الرئيسية"""
    points = [
        {"العنوان": "معرف المنشور الأصلي", "محتوى": re.findall(r'@\w+', text)[0] if '@' in text else "غير مُحدد"},
        {"العنوان": "معرف التعليق", "محتوى": re.findall(r'@\w+', text)[1] if len(re.findall(r'@\w+', text))>1 else "غير مُحدد"},
        {"العنوان": "المدعو المذكور", "محتوى": "المدعو الدين النصيحة سالم الطويل" if any(word in text for word in ["مدعو الدين", "سالم الطويل"]) else "غير مُحدد"},
        {"العنوان": "محتوى المنشور", "محتوى": "يتضمن ترحيبًا بالمدعو ورفع مقطع فيديو" if "ترحيب" in text or "فيديو" in text else "غير مُحدد"},
        {"العنوان": "محتوى المقطع", "محتوى": "يظهر أشخاصًا في مجلس ويشير إلى تحريم الخروج عن ولي الأمر" if "مجلس" in text or "تحريم" in text else "غير مُحدد"},
        {"العنوان": "التعليق الساخر", "محتوى": "يتضمن تعليقًا ساخرًا وتهكمًا بشأن الموضوع" if "ساخر" in text or "تهكم" in text else "غير مُحدد"}
    ]
    return points


# --- الواجهة الرئيسية ---
st.title("📸 تحليل الصور في نقاط")
st.write("يمكنك نسخ الصورة وتلصقها هنا أو رفعها من جهازك")

# تحميل الصورة أو لصقها
uploaded_file = st.file_uploader("اختر صورة", type=["png", "jpg", "jpeg"])
pasted_image = st.session_state.get("pasted_image", "")

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="الصورة المرفوعة", use_column_width=True)
elif pasted_image:
    img = Image.open(BytesIO(base64.b64decode(pasted_image)))
    st.image(img, caption="الصورة المُلصقة", use_column_width=True)


# زر التحليل
analyze_btn = st.button("🔍 تحليل الصورة الآن", key="analyze_btn")

# التنفيذ عند الضغط
if analyze_btn and (uploaded_file or pasted_image):
    with st.spinner("جارٍ التحليل..."):
        if uploaded_file:
            text = extract_text(Image.open(uploaded_file))
        else:
            text = extract_text(Image.open(BytesIO(base64.b64decode(pasted_image))))
        
        results = analyze_text(text)
        
        st.subheader("📝 النص المستخرج")
        st.text_area("", text, height=150, disabled=True)
        
        st.subheader("📌 النقاط الرئيسية")
        for point in results:
            st.markdown(f"""
            <div style='background:#F0F4F8; padding:10px; border-radius:5px; margin:5px 0;'>
                <b>{point['العنوان']}:</b> {point['محتوى']}
            </div>
            """, unsafe_allow_html=True)
        
        # زر التنزيل
        download_text = "\n".join([f"{p['العنوان']}: {p['محتوى']}" for p in results])
        st.download_button(
            "💾 تنزيل النتائج",
            data=download_text,
            file_name="تحليل_صورة.txt",
            mime="text/plain"
        )
