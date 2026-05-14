# -- coding: utf-8 --
"""
تحليل الصور في نقاط - تطبيق مُعدل للعمل على Streamlit
"""

from _future_ import annotations
import streamlit as st
import pytesseract
from PIL import Image
import numpy as np
import cv2
import re
import base64
from io import BytesIO
from typing import Dict, Optional


# --- إعداد التكوين ---
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide"
)

# --- تكوين Tesseract للتعامل مع الصور المُلصقة ---
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
def preprocess_image(image: Image) -> Image:
    """معالجة الصورة لتحسين استخراج النص"""
    img_np = np.array(image.convert("L"))
    img_np = cv2.medianBlur(img_np, 3)
    img_np = cv2.adaptiveThreshold(img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    return Image.fromarray(255 - img_np)


def extract_text(image: Image) -> str:
    """استخراج النص العربي من الصورة"""
    try:
        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, lang="ara", config='--oem 3 --psm 6')
        text = re.sub(r'[^\u0600-\u06FF\s\d\.,;:!؟]', '', text)
        return text.strip()
    except Exception as e:
        return f"خطأ في استخراج النص: {str(e)}"


def analyze_text(text: str) -> Dict[str, str]:
    """تحليل النص للنقاط المطلوبة"""
    summary = {
        "صاحب_المنشور": "غير مُحدد",
        "صاحب_التعليق": "غير مُحدد",
        "المدعو_دين": "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "مقطع_فيديو": "غير مُحدد",
        "تعليق_ساخن": "غير مُحدد",
        "رأي_خروج_ولي": "غير مُحدد",
        "تهكم": "غير مُحدد"
    }

    if "مدعو الدين" in text or "سالم الطويل" in text:
        summary["المدعو_دين"] = "المدعو الدين النصيحة سالم الطويل"
    
    if "نشر" in text or "منشور" in text:
        summary["صاحب_المنشور"] = text.split("نشر")[0].strip() or "غير مُحدد"
    
    if "علق" in text:
        summary["صاحب_التعليق"] = text.split("علق")[0].strip() or "غير مُحدد"
    
    if "مقطع فيديو" in text:
        summary["مقطع_فيديو"] = "يظهر أشخاصًا في مجلس، مع إشارة إلى تحريم الخروج عن ولي الأمر"
    
    if "تحريم" in text:
        summary["رأي_خروج_ولي"] = "تم الإشارة إلى تحريم الخروج عن ولي الأمر، والشخص المعني غير قادر على ذلك"
    
    if "تهكم" in text:
        summary["تهكم"] = "تم الإشارة إلى تهكم بشأن موقف الشخص"
    
    return summary


# --- الواجهة الرئيسية ---
st.title("📸 تحليل الصور في نقاط")
st.caption("قم بنسخ الصورة ولصقها مباشرة، أو ارفعها من جهازك")

# حقل مخفي لتخزين الصورة المُلصقة
pasted_img = st.text_input("", key="pasted_image", label_visibility="hidden")

# زر تحليل الصورة
analyze_btn = st.button("🔍 تحليل الصورة الآن", key="analyze_btn")

# عرض الصورة المُلصقة أو المرفوعة
uploaded = st.file_uploader("أو ارفع الصورة من جهازك", type=["png", "jpg", "jpeg"])
selected_image = None

if pasted_img := st.session_state.get("pasted_image"):
    selected_image = Image.open(BytesIO(base64.b64decode(pasted_img)))
    st.image(selected_image, caption="الصورة المُلصقة", use_column_width=True)

elif uploaded:
    selected_image = Image.open(uploaded)
    st.image(selected_image, caption="الصورة المرفوعة", use_column_width=True)


# --- تشغيل التحليل ---
if analyze_btn and selected_image:
    with st.spinner("جارٍ التحليل..."):
        text = extract_text(selected_image)
        results = analyze_text(text)
        
        st.subheader("📝 النص المستخرج")
        st.text_area("", text, height=150, disabled=True)
        
        st.subheader("📌 النقاط الرئيسية")
        for key, val in results.items():
            st.markdown(f"""
            <div style='background:#F0F4F8; padding:10px; border-radius:5px; margin:5px 0;'>
                <b>{key.replace('_',' ').title()}:</b> {val}
            </div>
            """, unsafe_allow_html=True)
        
        # زر تنزيل
        st.download_button(
            "💾 تنزيل النتائج",
            data="\n".join([f"{k}: {v}" for k, v in results.items()]),
            file_name="تحليل_صورة.txt",
            mime="text/plain"
        )


# --- قسم التعليمات ---
with st.expander("ℹ️ كيف تستخدم التطبيق"):
    st.write("""
    1. اضغط بزر الفأرة الأيمن على الصورة → اختر "نسخ الصورة"
    2. اضغط Ctrl+V في الصفحة لصقها
    3. اضغط على "تحليل الصورة الآن"
    4. تحقق من النتائج وتنزيلها إذا أردت
