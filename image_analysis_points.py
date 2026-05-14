# -- coding: utf-8 --
"""
تحليل الصور في نقاط - مع تنسيق عربي احترافي
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


# --- إعداد التنسيق العربي ---
ARABIC_STYLE = """
<style>
    .arabic-text {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 16px;
        line-height: 1.8;
    }
    .main-point {
        direction: rtl;
        text-align: right;
        background-color: #f0f4f8;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-right: 5px solid #2563eb;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .point-title {
        font-weight: bold;
        font-size: 18px;
        color: #1e40af;
        margin-bottom: 5px;
    }
    .point-content {
        font-size: 16px;
        color: #1f2937;
    }
    .upload-section {
        direction: rtl;
        text-align: right;
    }
</style>
"""

# تطبيق التنسيق
st.markdown(ARABIC_STYLE, unsafe_allow_html=True)


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
    """تحليل النص للنقاط الرئيسية المنظمة"""
    # استخراج المعرفات والمعلومات الرئيسية
    mentions = re.findall(r'@\w+', text)
    main_owner = mentions[0] if len(mentions) > 0 else "غير مُحدد"
    comment_owner = mentions[1] if len(mentions) > 1 else "غير مُحدد"
    
    # التحقق من المدعو الدين
    sheikh_name = "المدعو الدين النصيحة سالم الطويل" if any(keyword in text for keyword in ["مدعو الدين", "سالم الطويل", "النصيحة"]) else "غير مُحدد"
    
    # محتوى المنشور
    post_content = ""
    if "نشر" in text or "منشور" in text:
        post_part = text.split("نشر")[-1] if "نشر" in text else text
        post_content = post_part.split("علق")[0].strip() if "علق" in text else post_part.strip()
        post_content = post_content if post_content else "يتضمن منشورًا مقتبسًا عن المدعو الدين النصيحة"
    
    # محتوى المقطع
    video_content = ""
    if "فيديو" in text or "مقطع" in text:
        video_content = "يظهر أشخاصًا في مجلس، ويشير إلى تحريم الخروج عن ولي الأمر"
        if "تحريم" in text:
            video_content += "، ويُشير إلى أن الشخص المعني غير قادر على الخروج عن ولي الأمر"
    
    # التعليق الساخن
    comment_content = ""
    if "علق" in text:
        comment_part = text.split("علق")[-1].strip()
        comment_content = comment_part if comment_part else "يتضمن تعليقًا ساخرًا على المنشور المقتبس"
        if "تهكم" in text or "ساخر" in text:
            comment_content += "، وتشمل اشاره تهكمًا بشأن موقف الشخص المعني"
    
    # النقاط الرئيسية المنظمة
    points = [
        {
            "العنوان": "معرف صاحب المنشور الأصلي",
            "المحتوى": main_owner
        },
        {
            "العنوان": "معرف صاحب التعليق",
            "المحتوى": comment_owner
        },
        {
            "العنوان": "المدعو المذكور في المنشور",
            "المحتوى": sheikh_name
        },
        {
            "العنوان": "محتوى المنشور الأصلي",
            "المحتوى": post_content if post_content else "غير مُحدد"
        },
        {
            "العنوان": "تفاصيل المقطع المرئي",
            "المحتوى": video_content if video_content else "غير مُحدد"
        },
        {
            "العنوان": "مضمون التعليق الساخن",
            "المحتوى": comment_content if comment_content else "غير مُحدد"
        },
        {
            "العنوان": "الرأي حول قضية الخروج عن ولي الأمر",
            "المحتوى": "تم الإشارة إلى تحريم الخروج عن ولي الأمر، والشخص المعني غير قادر على القيام بذلك" if "تحريم" in text else "غير مُحدد"
        }
    ]
    
    return points, text


# --- الواجهة الرئيسية للتطبيق ---
st.title("📸 تحليل الصور في نقاط")
st.write("يمكنك نسخ الصورة وتلصقها هنا (Ctrl+V) أو الرفع من جهازك")

# قسم الرفع بالتنسيق العربي
st.markdown('<div class="upload-section">', unsafe_allow_html=True)
uploaded_file = st.file_uploader("اختر صورة من جهازك", type=["png", "jpg", "jpeg"])
st.markdown('</div>', unsafe_allow_html=True)

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
    
    # زر تحليل الصورة
    analyze_btn = st.button("🔍 بدء التحليل", key="analyze-btn")
    
    if analyze_btn:
        with st.spinner("جارٍ معالجة الصورة وتحليل النص..."):
            analysis_points, extracted_text = analyze_text(extract_text_from_image(image))
            
            # عرض النص المستخرج بالتنسيق العربي
            st.subheader("📝 النص المستخرج من الصورة")
            st.markdown(f'<div class="arabic-text">{extracted_text}</div>', unsafe_allow_html=True)
            
            # عرض النقاط الرئيسية
            st.subheader("📌 النقاط الرئيسية المستخرجة")
            for point in analysis_points:
                st.markdown(f"""
                <div class="main-point">
                    <div class="point-title">{point['العنوان']}</div>
                    <div class="point-content">{point['المحتوى']}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # زر تنزيل النتائج
            download_text = "📊 تحليل صورة منشور إكس\n"
            download_text += "-"*50 + "\n"
            download_text += "النص المستخرج:\n"
            download_text += extracted_text + "\n\n"
            download_text += "النقاط الرئيسية:\n"
            for i, point in enumerate(analysis_points, 1):
                download_text += f"{i}. {point['العنوان']}: {point['المحتوى']}\n"
            
            st.download_button(
                "💾 تنزيل النتائج كملف نصي",
                data=download_text,
                file_name="تحليل_صورة_إكس.txt",
                mime="text/plain"
