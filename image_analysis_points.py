# -*- coding: utf-8 -*-
"""تحليل الصور في نقاط - النسخة 3.5 (ملخص تنفيذي ديناميكي + أيقونة X)"""
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
        "ironically", "sarcastic", "sarcasm", "mocking", "mock",
        "مضحك", "مهزلة", "سخرية", "ساخر", "استهزاء", "تهكم",
        "نكتة", "مقلب", "فشل", "فاشل", "كارثة", "مصيبة",
        "عيب", "عار", "خزي", "فضيحة", "فضائح", "فضيحه", "فضايح",
        "تزييف", "تزوير", "كذب", "كاذب", "كذاب", "كذب",
        "مسرحية", "تمثيلية", "ممثل", "تمثيل", "تمثيل",
        "كوميديا", "كوميدي", "مضحك", "مضحكه", "مضحكة"
    ]
}

# ========== وظائف الكشف عن التصنيفات ==========
def detect_category(text):
    """الكشف عن التصنيفات الدلالية في النص"""
    if not text:
        return {}
    found_categories = {}
    for category, keywords in SEMANTIC_KEYWORDS.items():
        found = [kw for kw in keywords if kw in text]
        if found:
            found_categories[category] = found
    return found_categories

def is_sarcastic_text(text):
    """الكشف عن التهكم في النص"""
    if not text:
        return False, 0, []
    sarcastic_keywords = SEMANTIC_KEYWORDS.get("تهكم_وسخرية", [])
    found = [kw for kw in sarcastic_keywords if kw in text]
    return len(found) > 0, len(found), found

def get_topic_from_text(text):
    """تحديد موضوع التهكم بناءً على كلمات مفتاحية"""
    if not text:
        return "غير محدد"
    # كلمات مفتاحية لمواضيع مختلفة
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

# CSS مخصص
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
        background: #1DA1F2;
        color: white;
        padding: 8px 15px;
        border-radius: 20px;
        text-decoration: none;
        font-weight: bold;
        transition: all 0.3s;
    }
    .x-link:hover {
        background: #0d8ecf;
        transform: scale(1.05);
    }
    .x-icon {
        width: 20px;
        height: 20px;
        fill: white;
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
    .category-tag.sarcastic {
        background: #ff9800;
    }
    .category-tag.political {
        background: #2196F3;
    }
    .category-tag.general {
        background: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# ========== Session State ==========
if "api_key" not in st.session_state:
    st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "results" not in st.session_state:
    st.session_state.results = None
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "analysis_method" not in st.session_state:
    st.session_state.analysis_method = ""

# ========== وظيفة إنشاء رابط X ==========
def make_x_link(username):
    """إنشاء رابط X (تويتر) مع أيقونة"""
    if not username or username == "غير مُحدد":
        return "غير مُحدد"
    
    # إزالة @ إذا كان موجوداً
    clean_username = username.replace("@", "").strip()
    
    # SVG أيقونة X (تويتر)
    x_icon = '''
    <svg class="x-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
    '''
    
    return f'''
    <a href="https://x.com/{clean_username}" target="_blank" class="x-link">
        {x_icon}
        @{clean_username}
    </a>
    '''

# ========== الوظائف المساعدة ==========
def validate_api_key(key):
    """التحقق من صحة مفتاح API"""
    key = key.strip()
    if not key:
        return False, "⚠️ المفتاح فارغ"
    if not key.startswith("AIza"):
        return False, "⚠️ المفتاح يجب أن يبدأ بـ AIza..."
    if len(key) < 30:
        return False, "⚠️ المفتاح قصير جداً (يجب أن يكون 30 حرف على الأقل)"
    return True, "✅ صيغة المفتاح صحيحة"

def preprocess_image_ocr(image):
    """معالجة الصورة لتحسين OCR"""
    try:
        img = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(thresh, -1, kernel)
        return Image.fromarray(sharpened)
    except:
        return image

def extract_text_ocr(image):
    """استخراج النص من الصورة باستخدام OCR"""
    try:
        img_array = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        
        # استخراج النص العربي
        text_arabic = pytesseract.image_to_string(
            gray, 
            lang='ara+eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )
        
        # استخراج النص الإنجليزي للـ mentions
        text_english = pytesseract.image_to_string(
            gray,
            lang='eng',
            config='--oem 3 --psm 6'
        )
        
        # استخراج الـ mentions
        mentions = re.findall(r'@[A-Za-z0-9_]+', text_english)
        
        # تنظيف النص
        cleaned_text = re.sub(r'[^\u0600-\u06FF\s\d@#_.,;:!؟\-\u200c\u200d\u064b-\u065f]', ' ', text_arabic)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        return cleaned_text, mentions
    except Exception as e:
        return f"خطأ في OCR: {str(e)}", []

def generate_executive_summary(results, extracted_text=""):
    """توليد الملخص التنفيذي الديناميكي بناءً على البيانات المستخرجة"""
    # استخراج البيانات مع قيم افتراضية
    post_id = results.get("معرف_المنشور", "غير مُحدد")
    comment_id = results.get("معرف_التعليق", "غير مُحدد")
    invited = results.get("المدعو", "غير مُحدد")
    post_content = results.get("محتوى_المنشور", "غير مُحدد")
    clip = results.get("المقطع", "غير مُحدد")
    comment_text = results.get("التعليق", "غير مُحدد")
    opinion = results.get("الرأي", "غير مُحدد")
    
    # الكشف عن التهكم والموضوع
    is_sarcastic, sarcasm_count, sarcasm_words = is_sarcastic_text(extracted_text + " " + str(comment_text) + " " + str(post_content))
    topic = get_topic_from_text(extracted_text + " " + str(post_content))
    
    # بناء الملخص التنفيذي
    summary_parts = []
    
    # الجزء 1: معلومات النشر
    if post_id != "غير مُحدد":
        summary_parts.append(f"نشر صاحب المعرف {post_id}")
        if post_content != "غير مُحدد":
            # اختصار المحتوى إذا كان طويلاً
            content_summary = post_content[:150] + "..." if len(post_content) > 150 else post_content
            summary_parts.append(f"منشوراً يتضمن {content_summary}")
    
    # الجزء 2: المقتبس/المدعو
    if invited != "غير مُحدد":
        summary_parts.append(f"مقتبساً من المدعو {invited}")
    
    # الجزء 3: المقطع
    if clip != "غير مُحدد":
        summary_parts.append(f"مرفقاً مقطع فيديو يظهر فيه {clip}")
    
    # الجزء 4: التعليق
    if comment_id != "غير مُحدد":
        comment_intro = f"، حيث علّق صاحب المعرف {comment_id}"
        if comment_text != "غير مُحدد":
            comment_summary = comment_text[:150] + "..." if len(comment_text) > 150 else comment_text
            summary_parts.append(f"{comment_intro} بأن {comment_summary}")
    
    # الجزء 5: الرأي والتهكم
    if opinion != "غير مُحدد":
        summary_parts.append(f"مستنتجاً أن {opinion}")
    
    if is_sarcastic:
        summary_parts.append(f"، في إشارة تنطوي على تهكم بشأن {topic}")
    
    # دمج الأجزاء
    if summary_parts:
        summary = "".join(summary_parts) + "."
        return summary
    
    return "غير مُحدد - لم يتم استخراج معلومات كافية من الصورة"

def analyze_post_smart(text, mentions):
    """تحليل ذكي للمنشور مع استخراج جميع الحقول"""
    results = {
        "معرف_المنشور": "غير مُحدد",
        "معرف_التعليق": "غير مُحدد",
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": "غير مُحدد",
        "الملخص_التنفيذي": "غير مُحدد"
    }
    
    # استخراج المعرفات
    if mentions:
        results["معرف_المنشور"] = mentions[0]
        if len(mentions) > 1:
            results["معرف_التعليق"] = mentions[1]
    
    # استخراج المدعو
    invited_patterns = [
        r'المدعو\s+([@\w\s]+)',
        r'الشيخ\s+([@\w\s]+)',
        r'الداعية\s+([@\w\s]+)',
        r'(@\w+)'
    ]
    for pattern in invited_patterns:
        match = re.search(pattern, text)
        if match:
            results["المدعو"] = match.group(1).strip()
            break
    
    # استخراج المحتوى
    content_patterns = [
        r'محتوى[:\s]+([^\n]+)',
        r'المنشور[:\s]+([^\n]+)',
        r'يتضمن[:\s]+([^\n]+)'
    ]
    for pattern in content_patterns:
        match = re.search(pattern, text)
        if match:
            results["محتوى_المنشور"] = match.group(1).strip()
            break
    
    # استخراج المقطع
    clip_patterns = [
        r'مقطع[:\s]+([^\n]+)',
        r'فيديو[:\s]+([^\n]+)',
        r'يظهر[:\s]+([^\n]+)'
    ]
    for pattern in clip_patterns:
        match = re.search(pattern, text)
        if match:
            results["المقطع"] = match.group(1).strip()
            break
    
    # استخراج التعليق
    comment_patterns = [
        r'التعليق[:\s]+([^\n]+)',
        r'علق[:\s]+([^\n]+)',
        r'حيث[:\s]+([^\n]+)'
    ]
    for pattern in comment_patterns:
        match = re.search(pattern, text)
        if match:
            results["التعليق"] = match.group(1).strip()
            break
    
    # استخراج الرأي
    opinion_patterns = [
        r'الرأي[:\s]+([^\n]+)',
        r'رأي[:\s]+([^\n]+)',
        r'استنتج[:\s]+([^\n]+)',
        r'حيث[:\s]+([^\n]+)'
    ]
    for pattern in opinion_patterns:
        match = re.search(pattern, text)
        if match:
            results["الرأي"] = match.group(1).strip()
            break
    
    # الكشف عن التصنيفات
    categories = detect_category(text)
    
    # توليد الملخص التنفيذي الديناميكي
    results["الملخص_التنفيذي"] = generate_executive_summary(results, text)
    
    return results

def analyze_with_gemini(image, api_key):
    """تحليل الصورة باستخدام Gemini"""
    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        أنت محلل متخصص في تحليل منشورات تويتر/اكس (X). قم بتحليل الصورة المرفقة واستخراج المعلومات التالية بدقة:

        المطلوب استخراجه (بصيغة JSON فقط):
        {
            "معرف_المنشور": "معرف صاحب المنشور الأصلي (مثلاً: @username)",
            "معرف_التعليق": "معرف صاحب التعليق/المنشور المقتبس إن وجد",
            "المدعو": "اسم أو معرف الشخص المدعو/المقتبس منه المنشور",
            "محتوى_المنشور": "نص المنشور الأصلي باختصار",
            "المقطع": "وصف المقطع المرئي/الفيديو إن وجد",
            "التعليق": "نص التعليق على المنشور",
            "الرأي": "الرأي أو التحليل المقدم في المنشور",
            "الملخص_التنفيذي": "ملخص تنفيذي كامل يتضمن: من نشر المنشور، ما هو المحتوى، من المدعو/المقتبس، ما هو المقطع، ما هو التعليق، ما هو الرأي، وهل يوجد تهكم أو سخرية"
        }

        قواعد مهمة:
        1. أعد JSON فقط بدون أي نص إضافي
        2. إذا لم تجد معلومة معينة، اكتب "غير مُحدد"
        3. الملخص التنفيذي يجب أن يكون جملة واحدة كاملة لا تقل عن 80 كلمة
        4. تأكد من استخراج جميع المعرفات (@username) بدقة
        5. حلل المحتوى بعمق لاستخراج أي تهكم أو سخرية
        
        مثال على الملخص التنفيذي المطلوب:
        "نشر صاحب المعرف @username منشوراً يتضمن [محتوى المنشور]، مقتبساً من المدعو [المدعو]، مرفقاً مقطع فيديو يظهر فيه [وصف المقطع]، حيث علّق صاحب المعرف @commenter بأن [التعليق]، مستنتجاً أن [الرأي]، في إشارة تنطوي على تهكم بشأن [الموضوع]."
        """
        
        response = model.generate_content([prompt, image])
        raw_response = response.text
        
        # تنظيف الاستجابة
        cleaned = re.sub(r'^```(json)?\s*', '', raw_response.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        
        # استخراج JSON
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            result = json.loads(match.group())
            
            # التأكد من وجود جميع الحقول
            required_fields = ["معرف_المنشور", "معرف_التعليق", "المدعو", 
                             "محتوى_المنشور", "المقطع", "التعليق", "الرأي", "الملخص_التنفيذي"]
            for field in required_fields:
                if field not in result:
                    result[field] = "غير مُحدد"
            
            return result, None
        else:
            return None, "لم يتم العثور على JSON صالح في الاستجابة"
            
    except Exception as e:
        error_str = str(e)
        if "API_KEY_INVALID" in error_str:
            return None, "❌ مفتاح API غير صالح. تأكد من صحة المفتاح."
        elif "PERMISSION_DENIED" in error_str:
            return None, "❌ لا توجد صلاحية للوصول. تأكد من تفعيل API."
        elif "QUOTA_EXCEEDED" in error_str:
            return None, "❌ تم تجاوز الحصة اليومية. استخدم OCR أو انتظر الغد."
        elif "DeadlineExceeded" in error_str or "timeout" in error_str:
            return None, "⏱️ انتهى الوقت المحدد. حاول مرة أخرى أو استخدم OCR."
        else:
            return None, f"❌ خطأ غير متوقع: {error_str}"

# ========== إعدادات العرض ==========
FIELD_CONFIG = {
    "معرف_المنشور": {"icon": "👤", "label": "معرف المنشور", "is_username": True},
    "معرف_التعليق": {"icon": "💬", "label": "معرف التعليق", "is_username": True},
    "المدعو": {"icon": "🎯", "label": "المدعو/المقتبس"},
    "محتوى_المنشور": {"icon": "📝", "label": "محتوى المنشور"},
    "المقطع": {"icon": "🎬", "label": "المقطع/الفيديو"},
    "التعليق": {"icon": "💭", "label": "التعليق"},
    "الرأي": {"icon": "🧠", "label": "الرأي/التحليل"},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي", "is_summary": True}
}

def render_result_card(field_key, value):
    """عرض بطاقة النتيجة مع أيقونة X للمعرفات"""
    config = FIELD_CONFIG.get(field_key, {"icon": "📄", "label": field_key})
    
    is_missing = value in ["غير مُحدد", "", None, "None"]
    card_class = "missing" if is_missing else "summary" if config.get("is_summary") else ""
    
    if config.get("is_username") and not is_missing:
        # عرض رابط X للمعرفات
        x_link = make_x_link(value)
        st.markdown(f"""
        <div class="result-card x-account {card_class}">
            <div class="card-label">{config['icon']} {config['label']}</div>
            <div class="card-value">{x_link}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # عرض عادي
        display_value = value if not is_missing else "⚠️ غير مُحدد"
        st.markdown(f"""
        <div class="result-card {card_class}">
            <div class="card-label">{config['icon']} {config['label']}</div>
            <div class="card-value">{display_value}</div>
        </div>
        """, unsafe_allow_html=True)

# ========== الشريط الجانبي ==========
with st.sidebar:
    st.title("⚙️ الإعدادات")
    
    # اختيار طريقة التحليل
    analysis_mode = st.radio(
        "طريقة التحليل:",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق ✨)"],
        index=1
    )
    
    # إعدادات Gemini
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
        
        # التحقق من المفتاح
        if st.session_state.api_key:
            is_valid, message = validate_api_key(st.session_state.api_key)
            color = "green" if is_valid else "red"
            st.markdown(f"<p style='color: {color};'>{message}</p>", unsafe_allow_html=True)
            
            if not is_valid:
                st.caption("💡 احصل على مفتاح مجاني من: https://aistudio.google.com/apikey")
        else:
            st.caption("💡 احصل على مفتاح مجاني من: https://aistudio.google.com/apikey")
    
    # إعدادات العرض
    st.markdown("---")
    st.subheader("👁️ إعدادات العرض")
    
    all_fields = list(FIELD_CONFIG.keys())
    selected_fields = st.multiselect(
        "اختر الحقول للعرض:",
        all_fields,
        default=all_fields
    )
    
    # إحصائيات الجلسة
    st.markdown("---")
    st.subheader("📊 إحصائيات الجلسة")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("الصور المحللة", "1" if st.session_state.analysis_done else "0")
    with col2:
        st.metric("طريقة التحليل", st.session_state.analysis_method if st.session_state.analysis_method else "-")
    
    if st.session_state.analysis_done and st.session_state.results:
        filled = sum(1 for v in st.session_state.results.values() 
                    if v not in ["غير مُحدد", "", None])
        total = len(st.session_state.results)
        st.progress(filled/total)
        st.caption(f"تم استخراج {filled}/{total} حقول ({int(filled/total*100)}%)")
    
    # زر مسح النتائج
    if st.session_state.analysis_done:
        if st.button("🗑️ مسح النتائج", use_container_width=True):
            st.session_state.analysis_done = False
            st.session_state.results = None
            st.session_state.extracted_text = ""
            st.session_state.analysis_method = ""
            st.rerun()
    
    # عرض القاموس الدلالي
    with st.expander("📚 القاموس الدلالي"):
        for category, keywords in SEMANTIC_KEYWORDS.items():
            st.markdown(f"**{category}:** {', '.join(keywords[:5])}...")

# ========== الواجهة الرئيسية ==========
st.title("📸 تحليل الصور في نقاط")
st.markdown("---")

# رفع الصورة
uploaded_file = st.file_uploader(
    "📤 اختر صورة لتحليلها:",
    type=["png", "jpg", "jpeg", "webp"],
    help="الحد الأقصى: 200 ميجابايت"
)

if uploaded_file:
    # عرض الصورة
    image = Image.open(uploaded_file)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(image, caption="الصورة المُرفوعة", use_container_width=True)
        
        # معلومات الصورة
        st.caption(f"📐 الأبعاد: {image.size[0]} × {image.size[1]} بكسل | "
                  f"📦 الحجم: {len(uploaded_file.getvalue())/1024:.1f} كيلوبايت")
    
    with col2:
        # زر التحليل
        st.markdown("### 🚀 ابدأ التحليل")
        
        use_gemini = "Gemini" in analysis_mode and st.session_state.api_key
        
        if st.button("🔍 تحليل الصورة الآن", use_container_width=True):
            # التحقق من المفتاح إذا كان Gemini
            if "Gemini" in analysis_mode:
                if not st.session_state.api_key:
                    st.error("❌ يرجى إدخال مفتاح Gemini API أولاً")
                    use_gemini = False
                else:
                    is_valid, message = validate_api_key(st.session_state.api_key)
                    if not is_valid:
                        st.error(message)
                        use_gemini = False
            
            with st.spinner("⏳ جاري تحليل الصورة..."):
                results = None
                method_used = ""
                
                # محاولة استخدام Gemini
                if use_gemini:
                    results, error = analyze_with_gemini(image, st.session_state.api_key)
                    if error:
                        st.warning(error)
                        st.info("🔄 سيتم المحاولة بالطريقة التقليدية (OCR)...")
                    else:
                        method_used = "Gemini AI ✨"
                
                # الانتقال إلى OCR إذا فشل Gemini أو لم يُستخدم
                if results is None:
                    processed_image = preprocess_image_ocr(image)
                    text, mentions = extract_text_ocr(processed_image)
                    st.session_state.extracted_text = text
                    results = analyze_post_smart(text, mentions)
                    method_used = "OCR تقليدي 🔤"
                
                # حفظ النتائج
                st.session_state.results = results
                st.session_state.analysis_method = method_used
                st.session_state.analysis_done = True
                
                st.rerun()

# ========== عرض النتائج ==========
if st.session_state.analysis_done and st.session_state.results:
    results = st.session_state.results
    
    # شريط النجاح
    filled = sum(1 for v in results.values() if v not in ["غير مُحدد", "", None])
    total = len(results)
    percentage = int(filled/total*100)
    
    st.markdown(f"""
    <div class="success-banner">
        <h3>✅ تم التحليل بنجاح!</h3>
        <p>طريقة التحليل: <strong>{st.session_state.analysis_method}</strong></p>
        <p>تم استخراج <strong>{filled}/{total}</strong> حقول ({percentage}%)</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.progress(percentage/100)
    
    # عرض التصنيفات المكتشفة
    if st.session_state.extracted_text:
        categories = detect_category(st.session_state.extracted_text)
        if categories:
            st.markdown("### 🏷️ التصنيفات المكتشفة:")
            cols = st.columns(len(categories))
            for idx, (cat, words) in enumerate(categories.items()):
                with cols[idx]:
                    st.markdown(f"**{cat}:**")
                    for word in words[:3]:
                        st.markdown(f'<span class="category-tag">{word}</span>', 
                                  unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📋 النتائج:")
    
    # عرض الحقول المحددة
    for field in selected_fields:
        if field in results:
            render_result_card(field, results[field])
    
    # أزرار التنزيل
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        # تنزيل TXT
        txt_content = "\n".join([f"{k}: {v}" for k, v in results.items()])
        st.download_button(
            "📄 تنزيل النتائج (TXT)",
            data=txt_content.encode('utf-8'),
            file_name="analysis_result.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        # تنزيل JSON
        json_content = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button(
            "📋 تنزيل النتائج (JSON)",
            data=json_content.encode('utf-8'),
            file_name="analysis_result.json",
            mime="application/json",
            use_container_width=True
        )
    
    # عرض النص المستخرج للمراجعة
    if st.session_state.extracted_text:
        with st.expander("📝 النص المستخرج من OCR (للمراجعة)"):
            st.text_area("النص الخام:", value=st.session_state.extracted_text, 
                        disabled=True, height=150)

# ========== دليل الاستخدام ==========
with st.expander("📖 دليل الاستخدام"):
    st.markdown("""
    ### خطوات التحليل:
    1️⃣ **اختر طريقة التحليل:**
       - **OCR تقليدي**: مجاني، يعمل على الجهاز محلياً
       - **Gemini AI**: أدق، يتطلب مفتاح API (مجاني من Google)
    
    2️⃣ **احصل على مفتاح Gemini:**
       - انتقل إلى: https://aistudio.google.com/apikey
       - أنشئ مفتاحاً مجانياً
       - أدخله في الشريط الجانبي
    
    3️⃣ **ارفع صورة:**
       - الصيغ المدعومة: PNG, JPG, JPEG, WEBP
       - الحد الأقصى: 200 ميجابايت
    
    4️⃣ **اضغط "تحليل الصورة الآن":**
       - سيحاول التطبيق استخدام Gemini أولاً
       - إذا فشل، ينتقل تلقائياً إلى OCR
    
    ### ملاحظات مهمة:
    - ✅ المعرفات (@username) تظهر كروابط قابلة للنقر تؤدي إلى حساب X
    - ✅ الملخص التنفيذي يُولد تلقائياً بناءً على البيانات المستخرجة
    - ✅ يمكنك تنزيل النتائج بصيغة TXT أو JSON
    """)

# ========== التذييل ==========
st.markdown("---")
st.caption("© تحليل الصور في نقاط - الإصدار 3.5 | [احصل على مفتاح Gemini المجاني](https://aistudio.google.com/apikey)")
