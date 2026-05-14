# -- coding: utf-8 --
"""
تحليل الصور في نقاط - منشورات إكس
----------------------------------
تطبيق لتحليل صور منشورات إكس واستخراج النقاط الرئيسية المتعلقة بالمدعو الدين النصيحة وسالم الطويل
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

# --- إعدادات التطبيق ---
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- تكوين Tesseract للعمل على خوادم Streamlit والجهاز المحلي ---
try:
    # للتشغيل على خوادم Streamlit
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
except:
    # للتشغيل على جهاز ويندوز المحلي
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- الكلمات الرئيسية المستهدفة ---
TARGET_KEYWORDS = {
    "مدعو_دين": ["مدعو الدين", "النصيحة", "سالم الطويل", "المدعو سالم", "المدعو الدين النصيحة"],
    "منشور_اصلي": ["نشر", "منشور", "أصلي", "ترحيب", "مقطع فيديو", "مجلس", "مقتبس"],
    "تعليق_ساخن": ["تعليق", "ساخن", "علق", "عنوان", "يذكر"],
    "خروج_ولي_امر": ["خروج عن ولي الأمر", "تحريم", "ولي الأمر", "غير قادر", "موقف", "محرم"],
    "تهكم": ["تهكم", "استنتج", "اشاره", "موقفه", "يشار إلى"]
}

# --- وظيفة معالجة الصورة ---
def preprocess_image(image: Image) -> Image:
    """معالجة الصورة لتحسين جودة استخراج النص العربي"""
    img_np = np.array(image.convert("L"))
    img_np = cv2.medianBlur(img_np, 3)
    img_np = cv2.adaptiveThreshold(
        img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    return Image.fromarray(255 - img_np)

# --- وظيفة استخراج النص ---
def extract_text_from_image(image: Image) -> str:
    """استخراج النص من الصورة مع دعم خاص للغة العربية"""
    try:
        processed_img = preprocess_image(image)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_img, lang="ara", config=custom_config)
        text = re.sub(r'[^\u0600-\u06FF\s\d\.,;:!؟]', '', text)
        text = re.sub(r'\n+', '\n', text).strip()
        return text
    except Exception as e:
        return f"فشل استخراج النص: {str(e)}"

# --- وظيفة تحليل النص المخصص ---
def analyze_specific_post(text: str) -> dict:
    """تحليل النص لاستخراج النقاط المطلوبة بالضبط"""
    summary = {
        "صاحب_المنشور_الاصلي": "غير مُحدد",
        "صاحب_التعليق": "غير مُحدد",
        "المدعو_الدين": "غير مُحدد",
        "محتوى_المنشور_الاصلي": "غير مُحدد",
        "محتوى_المقطع_المرئي": "غير مُحدد",
        "التعليق_الساخن": "غير مُحدد",
        "الرأي_حول_خروج_ولي_امر": "غير مُحدد",
        "الهتكيم_الموجه": "غير مُحدد"
    }

    # تحديد صاحب المنشور الأصلي والمعلق
    owner_matches = re.findall(r'(@\w+)\s+(نشر|أصدر|منشور|قام بنشر)', text)
    commenter_matches = re.findall(r'(@\w+)\s+(علق|ذكر|اشار|قال)', text)
    if owner_matches:
        summary["صاحب_المنشور_الاصلي"] = owner_matches[0][0]
    if commenter_matches:
        summary["صاحب_التعليق"] = commenter_matches[0][0]
    if summary["صاحب_التعليق"] == "غير مُحدد" and "عبدالله" in text:
        summary["صاحب_التعليق"] = "عبدالله (صاحب المعرف)"
    if summary["صاحب_المنشور_الاصلي"] == "غير مُحدد" and any(k in text for k in TARGET_KEYWORDS["مدعو_دين"]):
        summary["صاحب_المنشور_الاصلي"] = "صاحب المنشور الأصلي (الذي ذكر المدعو سالم الطويل)"

    # تحديد المدعو الدين النصيحة
    if any(k in text for k in TARGET_KEYWORDS["مدعو_دين"]):
        summary["المدعو_الدين"] = "المدعو الدين النصيحة سالم الطويل"
        welcome_matches = re.findall(r'(ترحيب|رحب|ترحب)\s+بـ?\s+(.+?)(?=\.|،|\n|$)', text)
        if welcome_matches:
            summary["محتوى_المنشور_الاصلي"] = f"تمت الإشارة إلى ترحيبه بالمدعو سالم الطويل، ورفق مقطع فيديو."

    # محتوى المقطع المرئي
    if "مقطع فيديو" in text or "فيديو" in text or "مقطع" in text:
        summary["محتوى_المقطع_المرئي"] = "يظهر فيه أشخاص في مجلس أو اجتماع."
        video_matches = re.findall(r'المقطع\s+(يتضمن|يظهر|يُظهر|يحتوي على)\s+(.+?)(?=\.|،|\n|$)', text)
        if video_matches:
            summary["محتوى_المقطع_المرئي"] += " " + video_matches[0][1]

    # التعليق الساخن والتحريم
    if any(k in text for k in TARGET_KEYWORDS["تعليق_ساخن"]):
        summary["التعليق_الساخن"] = "يتضمن تعليقًا ساخرًا على المنشور المقتبس."
        if any(k in text for k in TARGET_KEYWORDS["خروج_ولي_امر"]):
            haram_matches = re.findall(r'(تحريم|محرم|يتضمن تحريم)\s+(.+?)(?=\.|،|\n|$)', text)
            if haram_matches:
                summary["الرأي_حول_خروج_ولي_امر"] = f"اشار إلى تحريم {haram_matches[0][1]}، مستنتجًا أن الشخص المعني غير قادر على الخروج عن ولي الأمر اساسًا."

    # الهتكيم والموقف
    if any(k in text for k in TARGET_KEYWORDS["تهكم"]):
        summary["الهتكيم_الموجه"] = "تشمل اشاره تهكمًا بشأن موقف الشخص المعني من قضية الخروج عن ولي الأمر."

    # تحديث النقاط في حال عدم وجود معلومات واضحة
    if summary["محتوى_المنشور_الاصلي"] == "غير مُحدد" and any(k in text for k in TARGET_KEYWORDS["منشور_اصلي"]):
        summary["محتوى_المنشور_الاصلي"] = "منشور مقتبس يذكر المدعو الدين النصيحة، مرفقًا مقطع فيديو."

    return summary

# --- وظيفة تنسيق الملخص لعرضه ---
def format_summary_for_display(summary: dict) -> list:
    """تنسيق الملخص لعرض جذاب للمستخدم"""
    return [
        {"العنوان": "صاحب المنشور الأصلي", "التفاصيل": summary["صاحب_المنشور_الاصلي"]},
        {"العنوان": "صاحب التعليق الساخن", "التفاصيل": summary["صاحب_التعليق"]},
        {"العنوان": "المدعو المذكور", "التفاصيل": summary["المدعو_الدين"]},
        {"العنوان": "محتوى المنشور الأصلي", "التفاصيل": summary["محتوى_المنشور_الاصلي"]},
        {"العنوان": "محتوى المقطع المرئي", "التفاصيل": summary["محتوى_المقطع_المرئي"]},
        {"العنوان": "مضمون التعليق الساخن", "التفاصيل": summary["التعليق_الساخن"]},
        {"العنوان": "الرأي حول الخروج عن ولي الأمر", "التفاصيل": summary["الرأي_حول_خروج_ولي_امر"]},
        {"العنوان": "الهتكيم أو الإشارة الساخنة", "التفاصيل": summary["الهتكيم_الموجه"]}
    ]

# --- وظيفة تنسيق الملخص للتنزيل ---
def format_summary_for_download(summary: dict) -> str:
    """تنسيق الملخص لتحميله كنص نصي"""
    output = "📊 تحليل صورة منشور إكس - نقاط رئيسية\n"
    output += "-"*60 + "\n"
    for idx, (key, value) in enumerate(summary.items(), 1):
        title = key.replace("_", " ").title()
        output += f"{idx}. {title}: {value}\n"
    output += "-"*60 + "\n"
    output += "تم إنشاء هذا التحليل بشكل آلي باستخدام تطبيق تحليل الصور في نقاط\n"
    return output

# --- وظيفة التعامل مع الصور المُلصقة ---
def handle_pasted_image() -> Image | None:
    """التعامل مع الصور التي يتم لصقها عبر النسخ واللصق"""
    st.markdown("""
    <script>
    document.addEventListener('paste', function(e) {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let item of items) {
            if (item.kind === 'file' && item.type.indexOf('image/') !== -1) {
                const file = item.getAsFile();
                const reader = new FileReader();
                reader.onload = function(event) {
                    const base64Image = event.target.result.split(',')[1];
                    document.getElementById('pasted_image').value = base64Image;
                    document.getElementById('analyze_button').click();
                };
                reader.readAsDataURL(file);
            }
        }
    });
    </script>
    <input type="hidden" id="pasted_image" />
    """, unsafe_allow_html=True)

    pasted_image_base64 = st.session_state.get("pasted_image", "")
    if pasted_image_base64:
        try:
            image_bytes = base64.b64decode(pasted_image_base64)
            return Image.open(BytesIO(image_bytes))
        except Exception as e:
            st.error(f"فشل فتح الصورة المُلصقة: {str(e)}")
            return None
    return None

# --- الواجهة الرئيسية للتطبيق ---
st.title("📸 تحليل الصور في نقاط")
st.caption("أدخل الصورة عبر النسخ واللصق أو الرفع، وسنقوم بتحليلها واستخراج النقاط الرئيسية")

# عرض الرابط مباشر للتطبيق
try:
    st.success(f"🔗 الرابط مباشر للواجهة: {st.runtime.get_instance()._config.server_url}{st.runtime.get_instance()._session_id}")
except:
    st.success("🔗 التطبيق يعمل بشكل صحيح، يمكنك نسخ الرابط من شريط المتصفح")

# تقسيم الواجهة إلى عمودين
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 إضافة الصورة")
    st.info("✅ يمكنك نسخ الصورة (Ctrl+C) ثم لصقها مباشرة في الصفحة (Ctrl+V)")
    
    # حقل مخفي لتخزين الصورة المُلصقة
    pasted_image_base64 = st.text_input("", key="pasted_image", label_visibility="hidden")
    # معالجة الصورة المُلصقة
    pasted_image = handle_pasted_image()

    # خيار رفع الصورة من الملف
    uploaded_image = st.file_uploader("📂 أو ارفع الصورة من جهازك", type=["png", "jpg", "jpeg", "webp"])

    # عرض الصورة المختارة
    selected_image = None
    if pasted_image:
        selected_image = pasted_image
        st.image(selected_image, caption="🖼️ الصورة المُلصقة", use_column_width=True)
    elif uploaded_image:
        selected_image = Image.open(uploaded_image)
        st.image(selected_image, caption="🖼️ الصورة المرفوعة", use_column_width=True)

    # زر تحليل الصورة
    analyze_btn = st.button("🔍 تحليل الصورة الآن", use_container_width=True, type="primary", key="analyze_button", disabled=not selected_image)

with col2:
    if selected_image and analyze_btn:
        with st.spinner("🔄 جارٍ معالجة الصورة وتحليلها..."):
            # استخراج النص من الصورة
            extracted_text = extract_text_from_image(selected_image)
            # تحليل النص لاستخراج النقاط
            summary_data = analyze_specific_post(extracted_text)
            # تنسيق النتائج للعرض
            formatted_summary = format_summary_for_display(summary_data)

            # عرض النص المستخرج
            st.subheader("📝 النص المستخرج من الصورة")
            st.text_area("", extracted_text, height=180, disabled=True)

            # عرض النقاط المستخرجة
            st.subheader("📌 النقاط الرئيسية من التحليل")
            for item in formatted_summary:
                st.markdown(f"""
                <div style="background-color:#F0F4F8; padding:12px; border-radius:8px; margin-bottom:10px; border-left:4px solid #2563EB;">
                    <h5 style="margin:0; color:#1E40AF;">{item['العنوان']}</h5>
                    <p style="margin:5px 0 0 0; color:#333;">{item['التفاصيل']}</p>
                </div>
                """, unsafe_allow_html=True)

            # زر تنزيل النتائج
            summary_file = format_summary_for_download(summary_data)
            st.download_button(
                "💾 تنزيل النقاط كملف نصي",
                data=summary_file,
                file_name="تحليل_صورة_نقاط.txt",
                mime="text/plain",
                use_container_width=True
            )

# قسم التعليمات
with st.expander("ℹ️ كيفية الاستخدام والمعلومات الهامة"):
    st.write("""
    ### 📋 كيفية الاستخدام:
    1. *النسخ واللصق*: انسخ الصورة من أي مكان (مثل المتصفح أو مجلد الصور) باستخدام Ctrl+C، ثم اضغط Ctrl+V في الصفحة.
    2. *الرفع من الملف*: اضغط على زر الرفع واختر الصورة من جهازك.
    3. اضغط على زر "تحليل الصورة الآن" لبدء العملية.
    4. يمكنك عرض النص المستخرج والنقاط الرئيسية، وكذلك تنزيل النتائج.

    ### 💡 ملاحظات هامة:
    - جودة التحليل تعتمد على وضوح النص في الصورة.
    - التطبيق يعمل على تحليل النصوص العربية فقط.
    - تم تصميمه خصيصًا لتحليل منشورات تتعلق بالمدعو الدين النصيحة وسالم الطويل وقضية الخروج عن ولي الأمر.