# -*- coding: utf-8 -*-
"""
تحليل الصور في نقاط - النسخة 3.3 (الملخص التنفيذي + إصلاح مفتاح API)
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

# ─────────────────────────────────────────
# إعداد الصفحة
# ─────────────────────────────────────────
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# ✅ تهيئة session_state (أول شيء في الكود)
# ─────────────────────────────────────────
if "api_key" not in st.session_state:
    try:
        st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        st.session_state.api_key = ""

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "results" not in st.session_state:
    st.session_state.results = None

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "analysis_method" not in st.session_state:
    st.session_state.analysis_method = ""

# ─────────────────────────────────────────
# CSS للغة العربية (RTL)
# ─────────────────────────────────────────
st.markdown("""
<style>
    /* الاتجاه العام */
    .main, .block-container, .stApp {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    }
    
    /* الشريط الجانبي */
    .css-1d391kg, [data-testid="stSidebar"] {
        direction: rtl !important;
    }
    
    /* بطاقات النتائج */
    .result-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border-right: 4px solid #4CAF50;
        border-radius: 12px;
        padding: 15px 20px;
        margin: 10px 0;
        direction: rtl;
        text-align: right;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    .result-card.missing {
        border-right-color: #f44336;
        background: linear-gradient(135deg, #1e1e2e, #2e1e1e);
    }
    
    .result-card.summary {
        border-right-color: #2196F3;
        background: linear-gradient(135deg, #1e2e3e, #2a3a4e);
        min-height: 120px;
    }
    
    .card-label {
        font-size: 13px;
        color: #aaa;
        margin-bottom: 5px;
        direction: rtl;
    }
    
    .card-value {
        font-size: 16px;
        font-weight: bold;
        color: #fff;
        direction: rtl;
        unicode-bidi: plaintext;
        line-height: 1.8;
    }
    
    .card-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 12px;
        margin-right: 8px;
    }
    
    .badge-success { background: #4CAF50; color: white; }
    .badge-missing { background: #f44336; color: white; }
    
    /* بانر النجاح */
    .success-banner {
        background: linear-gradient(135deg, #1a3a1a, #2d5a2d);
        border: 1px solid #4CAF50;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        color: white;
        margin: 15px 0;
        direction: rtl;
    }
    
    /* بانر الخطأ */
    .error-banner {
        background: linear-gradient(135deg, #3a1a1a, #5a2d2d);
        border: 1px solid #f44336;
        border-radius: 15px;
        padding: 15px 20px;
        color: white;
        margin: 10px 0;
        direction: rtl;
    }
    
    /* بانر التحذير */
    .warning-banner {
        background: linear-gradient(135deg, #3a3a1a, #5a5a2d);
        border: 1px solid #FFC107;
        border-radius: 15px;
        padding: 15px 20px;
        color: white;
        margin: 10px 0;
        direction: rtl;
    }

    /* زر التحليل */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #4CAF50, #45a049);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #45a049, #3d8b40);
    }
    
    /* معلومات الصورة */
    .image-info {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 10px 15px;
        color: #ccc;
        font-size: 13px;
        direction: rtl;
        margin-top: 10px;
    }

    /* مؤشر صحة المفتاح */
    .key-valid {
        color: #4CAF50;
        font-size: 13px;
        margin-top: 5px;
    }
    .key-invalid {
        color: #f44336;
        font-size: 13px;
        margin-top: 5px;
    }
    
    /* تنسيق الملخص التنفيذي */
    .summary-text {
        font-size: 15px;
        line-height: 2;
        text-align: justify;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# دوال المعالجة
# ─────────────────────────────────────────

def validate_api_key(api_key):
    """التحقق من صحة مفتاح API"""
    api_key = api_key.strip() if api_key else ""
    if not api_key:
        return False, "⚠️ المفتاح فارغ - أدخل مفتاح API"
    if not api_key.startswith("AIza"):
        return False, "⚠️ المفتاح يجب أن يبدأ بـ AIza..."
    if len(api_key) < 30:
        return False, "⚠️ المفتاح قصير جداً - تأكد من نسخه كاملاً"
    return True, "✅ صيغة المفتاح صحيحة"


def preprocess_image_ocr(image):
    """معالجة الصورة قبل OCR"""
    try:
        img = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
        sharpened = cv2.filter2D(thresh, -1, kernel)
        return Image.fromarray(sharpened)
    except Exception as e:
        return image


def extract_text_ocr(image):
    """استخراج النص عبر OCR مع الحفاظ على @usernames"""
    try:
        img_arr = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        # تشغيل OCR بالعربية والإنجليزية
        full_text = pytesseract.image_to_string(
            gray, lang='ara+eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )

        # تشغيل OCR بالإنجليزية فقط لاستخراج @usernames
        eng_text = pytesseract.image_to_string(
            gray, lang='eng',
            config='--oem 3 --psm 6'
        )
        mentions_eng = re.findall(r'@[A-Za-z0-9_]+', eng_text)

        # تنظيف النص مع الحفاظ على الرموز المهمة
        clean_text = re.sub(r'[^\u0600-\u06FF\s\d@#_.,;:!؟\-\u200c\u200d]', ' ', full_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text, mentions_eng

    except Exception as e:
        return f"خطأ في OCR: {str(e)}", []


def generate_executive_summary(results, text):
    """
    ✅ توليد الملخص التنفيذي بالصيغة المطلوبة
    """
    # استخراج المعلومات
    post_id = results.get("معرف_المنشور", "غير مُحدد")
    comment_id = results.get("معرف_التعليق", "غير مُحدد")
    invited = results.get("المدعو", "غير مُحدد")
    post_content = results.get("محتوى_المنشور", "")
    comment = results.get("التعليق", "")
    opinion = results.get("الرأي", "")
    video = results.get("المقطع", "غير مُحدد")
    
    # بناء المل_summmary بالصيغة المطلوبة
    parts = []
    
    # المقدمة: نشر صاحب المعرف...
    if post_id != "غير مُحدد":
        post_id_clean = post_id.replace("@", "")
        parts.append(f"نشر صاحب المعرف {post_id_clean} ({post_id})")
    
    # نوع المنشور والمحتوى
    content_parts = []
    
    # تحديد نوع المنشور (تعليق ساخر، منشور عادي، إلخ)
    is_sarcastic = any(kw in text for kw in ["تهكم", "ساخر", "سخرية", "😂", "🤣", "😅", "هههه", "يضحك", "مضحك"])
    
    if is_sarcastic:
        content_parts.append("منشورًا يتضمن تعليقًا ساخرًا")
    else:
        content_parts.append("منشورًا")
    
    # على منشور مقتبس...
    if comment_id != "غير مُحدد":
        comment_id_clean = comment_id.replace("@", "")
        content_parts.append(f"على منشور مقتبس للمدعو {comment_id_clean} ({comment_id})")
    
    if content_parts:
        parts.append(" ".join(content_parts))
    
    # حيث أشار...
    where_parts = []
    
    # المدعو
    if invited != "غير مُحدد" and invited:
        where_parts.append(f"المدعو {invited}")
    
    # المقطع
    if video != "غير مُحدد" and "يوجد" in video:
        where_parts.append("مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس")
    
    if where_parts:
        parts.append(f"، حيث أشار صاحب المنشور الأصلي إلى ترحيبه بالمدعو {invited} مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس")
    
    # فيما علّق...
    comment_parts = []
    
    if post_id != "غير مُحدد":
        post_id_clean = post_id.replace("@", "")
        comment_parts.append(f"فيما علّق صاحب المعرف {post_id_clean}")
    
    # الرأي/التحليل
    if opinion != "غير مُحدد" and opinion:
        if "تحريم" in opinion or "حرام" in text:
            comment_parts.append(f"بأن المقطع يتضمن تحريمًا للخروج على ولي الأمر")
        elif "موافق" in opinion:
            comment_parts.append(f"بموافقته على المحتوى")
        elif "مخالف" in opinion:
            comment_parts.append(f"بمخالفته للمحتوى")
        else:
            comment_parts.append(f"بأن {opinion}")
    
    # التهكم/الاستنتاج
    if is_sarcastic:
        if "غير قادر" in text or "مش قادر" in text:
            comment_parts.append("، مستنتجًا أن الشخص المعني غير قادر على الخروج أساسًا، في إشارة تنطوي على تهكم بشأن موقفه من قضية الخروج على ولي الأمر")
        else:
            comment_parts.append("، في إشارة تنطوي على تهكم بشأن الموضوع")
    
    if comment_parts:
        parts.append(" ".join(comment_parts))
    
    # دمج الجمل
    if len(parts) >= 2:
        summary = "".join(parts) + "."
        return summary
    else:
        # إذا لم نستطع بناء المل_summsummary الكامل
        return "غير مُحدد - لم يتم استخراج معلومات كافية للملخص التنفيذي"


def analyze_post_smart(text, mentions_eng):
    """تحليل ذكي للنص المستخرج"""
    pts = {
        "معرف_المنشور": "غير مُحدد",
        "معرف_التعليق": "غير مُحدد",
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": "غير مُحدد",
        "المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": "غير مُحدد",
        "الملخص_التنفيذي": "غير مُحدد"
    }

    # ✅ معرفات من OCR الإنجليزي (أدق)
    if mentions_eng:
        pts["معرف_المنشور"] = mentions_eng[0]
        if len(mentions_eng) > 1:
            pts["معرف_التعليق"] = mentions_eng[1]

    # ✅ fallback للمعرفات العربية
    if pts["معرف_المنشور"] == "غير مُحدد":
        ar_mentions = re.findall(r'@[\w\u0600-\u06FF]+', text)
        if ar_mentions:
            pts["معرف_المنشور"] = ar_mentions[0]
            if len(ar_mentions) > 1:
                pts["معرف_التعليق"] = ar_mentions[1]

    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]

    # ✅ استخراج المدعو
    name_patterns = [
        r'(?:بشيخنا|الشيخ|الأستاذ|الدكتور|الإمام)\s*[:\s]\s*([\u0600-\u06FF][\u0600-\u06FF\s]{2,25})',
        r'(?:ردّ على|رد على|يرد على|ذكر)\s+([\u0600-\u06FF\s]{3,25})',
    ]
    for pat in name_patterns:
        m = re.search(pat, text)
        if m:
            pts["المدعو"] = m.group(1).strip()
            break

    # ✅ محتوى المنشور = أسطر عربية نظيفة
    arabic_lines = [l for l in lines if len(re.findall(r'[\u0600-\u06FF]', l)) > 8]
    if arabic_lines:
        pts["محتوى_المنشور"] = arabic_lines[0][:200]
        if len(arabic_lines) >= 2:
            pts["التعليق"] = '\n'.join(arabic_lines[1:3])

    # ✅ كشف المقطع
    if any(k in text for k in ["فيديو", "مقطع", "تسجيل", "كليب", "يوتيوب", "تيكتوك", "رابط"]):
        pts["المقطع"] = "✅ محتوى مرئي موجود"

    # ✅ الرأي
    opinion_map = {
        r'تحريم|محرم|حرام': 'يتضمن تحريم الخروج على ولي الأمر',
        r'موافق|صحيح|صح': 'موافقة على المحتوى',
        r'مخالف|خطأ|غلط': 'مخالفة للمحتوى',
        r'أرى|رأيي|أعتقد': 'رأي شخصي',
    }
    for pat, desc in opinion_map.items():
        if re.search(pat, text):
            pts["الرأي"] = desc
            break

    # ✅ توليد المل_summsummary التنفيذي
    pts["الملخص_التنفيذي"] = generate_executive_summary(pts, text)

    return pts


def analyze_with_gemini(image, api_key):
    """تحليل متقدم باستخدام Gemini Vision"""
    try:
        api_key = api_key.strip()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = """
        أنت محلل متخصص في تحليل لقطات شاشة منشورات تويتر/X باللغة العربية.
        حلل الصورة المرفقة واستخرج المعلومات التالية بدقة عالية:

        1. معرف_المنشور: معرف (@username) صاحب المنشور الأصلي (بالإنجليزي)
        2. معرف_التعليق: معرف (@username) صاحب التعليق أو الاقتباس (بالإنجليزي)
        3. المدعو: اسم الشخص المذكور أو المدعو في النص (بالعربي)
        4. محتوى_المنشور: النص الكامل للمنشور الأصلي (بالعربي)
        5. المقطع: وصف الفيديو أو المقطع المرفق إن وجد، أو "لا يوجد"
        6. التعليق: نص التعليق أو الاقتباس المضاف (بالعربي)
        7. الرأي: الرأي أو الحكم أو الموقف الظاهر في المنشور
        
        8. الملخص_التنفيذي: اكتب ملخصًا تنفيذيًا احترافيًا بالصيغة التالية:
           "نشر صاحب المعرف [الاسم] ([@username]) منشورًا [يتضمن تعليقًا ساخرًا/عاديًا] [على منشور مقتبس للمدعو [الاسم] ([@username])]، حيث أشار صاحب المنشور الأصلي إلى [الموضوع] [مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس إن وجد]، فيما علّق صاحب المعرف [الاسم] [بالرأي/التحليل]، [مستنتجًا أن...، في إشارة تنطوي على تهكم بشأن... إن وجد تهكم]."

        ⚠️ مهم جداً:
        - أجب بصيغة JSON فقط بدون أي نص إضافي
        - لا تضع ```json أو ``` حول الإجابة
        - استخدم "غير محدد" إذا لم تجد المعلومة

        مثال للإجابة المطلوبة:
        {
          "معرف_المنشور": "@AbdullahElshrif",
          "معرف_التعليق": "@boyousefalazmi",
          "المدعو": "الدين النصيحة",
          "محتوى_المنشور": "طلع بيحرم الخروج على ولي الأمر عشان مش قادر يخرج أساساً",
          "المقطع": "يوجد مقطع فيديو",
          "التعليق": "مرحبا ومسهلا\\nبشيخنا: سالم الطويل حفظه الله",
          "الرأي": "يتضمن تهكمًا على منشور مقتبس",
          "الملخص_التنفيذي": "نشر صاحب المعرف عبدالله الشريف (@AbdullahElshrif) منشورًا يتضمن تعليقًا ساخرًا على منشور مقتبس للمدعو الدين النصيحة (@boyousefalazmi)، حيث أشار صاحب المنشور الأصلي إلى ترحيبه بالمدعو سالم الطويل مرفقًا مقطع فيديو يظهر فيه أشخاص في مجلس، فيما علّق صاحب المعرف عبدالله الشريف بأن المقطع يتضمن تحريمًا للخروج على ولي الأمر، مستنتجًا أن الشخص المعني غير قادر على الخروج أساسًا، في إشارة تنطوي على تهكم بشأن موقفه من قضية الخروج على ولي الأمر."
        }
        """
        
        response = model.generate_content([prompt, image])
        raw = response.text.strip()

        # تنظيف الاستجابة
        raw = re.sub(r'^```(json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        raw = raw.strip()

        # استخراج JSON
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            result = json.loads(match.group())
            # تطبيع المفاتيح
            normalized = {
                "معرف_المنشور": result.get("معرف_المنشور", "غير مُحدد"),
                "معرف_التعليق": result.get("معرف_التعليق", "غير مُحدد"),
                "المدعو": result.get("المدعو", "غير مُحدد"),
                "محتوى_المنشور": result.get("محتوى_المنشور", "غير مُحدد"),
                "المقطع": result.get("المقطع", "غير مُحدد"),
                "التعليق": result.get("التعليق", "غير مُحدد"),
                "الرأي": result.get("الرأي", "غير مُحدد"),
                "الملخص_التنفيذي": result.get("الملخص_التنفيذي", "غير مُحدد"),
            }
            return normalized, None
        else:
            return None, f"لم يُرجع Gemini JSON صالح. الاستجابة: {raw[:200]}"

    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "api key not valid" in err.lower():
            return None, "❌ مفتاح API غير صالح - احصل على مفتاح جديد من: https://aistudio.google.com/apikey"
        elif "PERMISSION_DENIED" in err:
            return None, "❌ ليس لديك صلاحية - تأكد أن Gemini API مُفعّل في مشروعك"
        elif "QUOTA_EXCEEDED" in err or "quota" in err.lower():
            return None, "❌ تجاوزت الحد اليومي المجاني - انتظر حتى الغد أو فعّل الفوترة"
        elif "timeout" in err.lower():
            return None, "❌ انتهت مهلة الاتصال - تحقق من الإنترنت وحاول مجدداً"
        elif "model" in err.lower() and "not found" in err.lower():
            return None, "❌ النموذج غير متاح - تأكد أن gemini-1.5-flash مدعوم في منطقتك"
        else:
            return None, f"❌ خطأ غير متوقع: {err}"


# ─────────────────────────────────────────
# إعداد بيانات الحقول (مُعدّل - بدون التهكم، مع الملخص التنفيذي)
# ─────────────────────────────────────────
FIELD_CONFIG = {
    "معرف_المنشور":  {"icon": "🆔", "label": "معرف المنشور",   "class": "primary"},
    "معرف_التعليق":  {"icon": "💬", "label": "معرف التعليق",   "class": "secondary"},
    "المدعو":        {"icon": "👤", "label": "المدعو / المذكور", "class": "person"},
    "محتوى_المنشور": {"icon": "📝", "label": "محتوى المنشور",  "class": "content"},
    "المقطع":        {"icon": "🎬", "label": "المقطع / الفيديو", "class": "media"},
    "التعليق":       {"icon": "💭", "label": "التعليق",         "class": "comment"},
    "الرأي":         {"icon": "⚖️", "label": "الرأي / الموقف",  "class": "opinion"},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي", "class": "summary"},  # ✅ جديد
}


def render_result_card(key, value):
    """عرض بطاقة نتيجة واحدة"""
    cfg = FIELD_CONFIG.get(key, {"icon": "📌", "label": key, "class": ""})
    is_missing = value in ["غير مُحدد", "غير محدد", None, ""]
    card_class = "result-card missing" if is_missing else "result-card"
    
    # تنسيق خاص للملخص التنفيذي
    if key == "الملخص_التنفيذي":
        card_class = "result-card summary" if not is_missing else "result-card missing"
    
    badge_class = "badge-missing" if is_missing else "badge-success"
    badge_text = "غير مُحدد" if is_missing else "✓ مُحدد"
    display_value = "—" if is_missing else value

    # تنسيق خاص للمل_summsummary الطويل
    if key == "الملخص_التنفيذي" and not is_missing:
        st.markdown(f"""
        <div class="{card_class}">
            <div class="card-label">
                {cfg['icon']} {cfg['label']}
                <span class="card-badge {badge_class}">{badge_text}</span>
            </div>
            <div class="card-value summary-text">{display_value}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="{card_class}">
            <div class="card-label">
                {cfg['icon']} {cfg['label']}
                <span class="card-badge {badge_class}">{badge_text}</span>
            </div>
            <div class="card-value">{display_value}</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# الشريط الجانبي
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ الإعدادات")

    # ✅ اختيار طريقة التحليل
    mode = st.radio(
        "طريقة التحليل",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق ✨)"],
        index=1
    )

    if "Gemini" in mode:
        st.divider()
        st.markdown("### 🔑 مفتاح Gemini API")

        # ✅ الإصلاح الرئيسي: استخدام session_state + key فريد
        def on_api_key_change():
            """callback يُحدِّث session_state عند تغيير المفتاح"""
            st.session_state.api_key = st.session_state._api_key_input

        new_key = st.text_input(
            label="أدخل المفتاح هنا",
            value=st.session_state.api_key,      # ✅ يحمل القيمة المحفوظة
            type="password",
            placeholder="AIzaSy...",
            key="_api_key_input",                 # ✅ key فريد لـ session_state
            on_change=on_api_key_change,          # ✅ callback لحفظ التغييرات
            help="احصل على مفتاح مجاني من aistudio.google.com"
        )

        # ✅ تحديث session_state دائماً
        if new_key:
            st.session_state.api_key = new_key

        # ✅ عرض حالة المفتاح فوراً
        if st.session_state.api_key:
            is_valid, msg = validate_api_key(st.session_state.api_key)
            if is_valid:
                st.markdown(f'<p class="key-valid">{msg}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="key-invalid">{msg}</p>', unsafe_allow_html=True)
        else:
            st.caption("💡 احصل على مفتاح مجاني من [Google AI Studio](https://aistudio.google.com/apikey)")

    st.divider()

    # ✅ اختيار الحقول للعرض
    all_fields = list(FIELD_CONFIG.keys())
    points_to_show = st.multiselect(
        "اختر النقاط للعرض",
        options=all_fields,
        default=all_fields,
        format_func=lambda x: f"{FIELD_CONFIG[x]['icon']} {FIELD_CONFIG[x]['label']}"
    )

    st.divider()
    st.markdown("### 📊 إحصائيات الجلسة")
    if st.session_state.results:
        filled = sum(1 for v in st.session_state.results.values()
                     if v not in ["غير مُحدد", "غير محدد", None, ""])
        st.metric("الحقول المُحددة", f"{filled} / {len(FIELD_CONFIG)}")

    if st.button("🗑️ مسح النتائج"):
        st.session_state.analysis_done = False
        st.session_state.results = None
        st.session_state.extracted_text = ""
        st.rerun()


# ─────────────────────────────────────────
# الواجهة الرئيسية
# ─────────────────────────────────────────
st.markdown("# 📸 تحليل الصور في نقاط")
st.markdown("### استخرج معلومات المنشورات من لقطات الشاشة بدقة عالية")

# ✅ رفع الصورة
uploaded_file = st.file_uploader(
    "اختر صورة لتحليلها",
    type=["png", "jpg", "jpeg", "webp"],
    help="الحد الأقصى 200 MB"
)

if uploaded_file:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1])

    with col1:
        st.image(image, caption="الصورة المُرفوعة", use_container_width=True)
        w, h = image.size
        size_kb = uploaded_file.size / 1024
        st.markdown(f"""
        <div class="image-info">
            📐 الأبعاد: {w} × {h} بكسل &nbsp;|&nbsp;
            📁 الحجم: {size_kb:.1f} KB &nbsp;|&nbsp;
            🖼️ الصيغة: {image.format or uploaded_file.type.split('/')[-1].upper()}
        </div>
        """, unsafe_allow_html=True)

    with col2:
        analyze_btn = st.button("🚀 تحليل الصورة الآن", use_container_width=True)

        if analyze_btn:
            use_gemini = "Gemini" in mode
            api_key_val = st.session_state.api_key.strip()

            if use_gemini and not api_key_val:
                st.markdown("""
                <div class="warning-banner">
                    ⚠️ لم تُدخل مفتاح Gemini API<br>
                    <small>أدخل المفتاح في الشريط الجانبي أو سيتم التحويل إلى OCR تلقائياً</small>
                </div>
                """, unsafe_allow_html=True)
                use_gemini = False

            with st.spinner("⏳ جاري التحليل..."):
                results = None
                method_used = ""

                # ─── محاولة Gemini ───
                if use_gemini and api_key_val:
                    is_valid, valid_msg = validate_api_key(api_key_val)
                    if not is_valid:
                        st.markdown(f'<div class="error-banner">❌ {valid_msg}</div>',
                                    unsafe_allow_html=True)
                    else:
                        with st.status("🤖 Gemini AI يحلل الصورة..."):
                            results, err = analyze_with_gemini(image, api_key_val)
                            if err:
                                st.markdown(f'<div class="error-banner">{err}</div>',
                                            unsafe_allow_html=True)
                                st.info("🔄 التحويل التلقائي إلى OCR...")
                                results = None
                            else:
                                method_used = "Gemini AI ✨"

                # ─── OCR كـ fallback أو اختيار أصلي ───
                if results is None:
                    with st.status("🔤 جاري استخراج النص بـ OCR..."):
                        text, mentions = extract_text_ocr(image)
                        st.session_state.extracted_text = text
                        results = analyze_post_smart(text, mentions)
                        method_used = "OCR تقليدي"

                # ─── حفظ النتائج في session_state ───
                st.session_state.results = results
                st.session_state.analysis_method = method_used
                st.session_state.analysis_done = True

        # ─────────────────────────────────────────
        # عرض النتائج
        # ─────────────────────────────────────────
        if st.session_state.analysis_done and st.session_state.results:
            results = st.session_state.results
            filled = sum(1 for v in results.values()
                         if v not in ["غير مُحدد", "غير محدد", None, ""])
            total = len(results)
            pct = int(filled / total * 100)

            # بانر النجاح
            st.markdown(f"""
            <div class="success-banner">
                ✅ تم التحليل بنجاح باستخدام <strong>{st.session_state.analysis_method}</strong><br>
                🎯 تم استخراج <strong>{filled} من {total}</strong> حقول ({pct}%)
            </div>
            """, unsafe_allow_html=True)

            st.progress(pct / 100)
            st.markdown("---")

            # عرض البطاقات
            for key in points_to_show:
                if key in results:
                    render_result_card(key, results[key])

            # ─── تنزيل النتائج ───
            st.markdown("### 💾 تنزيل النتائج")
            dl_col1, dl_col2 = st.columns(2)

            # TXT
            txt_content = "\n".join([
                f"{FIELD_CONFIG[k]['label']}: {v}"
                for k, v in results.items()
            ])
            with dl_col1:
                st.download_button(
                    "📄 تنزيل TXT",
                    data=txt_content.encode('utf-8'),
                    file_name="analysis_result.txt",
                    mime="text/plain",
                    use_container_width=True
                )

            # JSON
            with dl_col2:
                st.download_button(
                    "📋 تنزيل JSON",
                    data=json.dumps(results, ensure_ascii=False, indent=2).encode('utf-8'),
                    file_name="analysis_result.json",
                    mime="application/json",
                    use_container_width=True
                )

            # ─── النص المستخرج من OCR ───
            if st.session_state.extracted_text:
                with st.expander("📝 النص المستخرج (للمراجعة)"):
                    st.text_area(
                        "النص الخام من OCR",
                        value=st.session_state.extracted_text,
                        height=150,
                        disabled=True
                    )

# ─────────────────────────────────────────
# تعليمات الاستخدام
# ─────────────────────────────────────────
with st.expander("📖 كيفية الاستخدام"):
    st.markdown("""
    ### خطوات الاستخدام:
    1. **اختر طريقة التحليل** من الشريط الجانبي:
       - 🔤 **OCR تقليدي**: مجاني، لا يحتاج مفتاح API
       - 🤖 **Gemini AI**: أدق وأذكى، يحتاج مفتاح API مجاني
    2. **للحصول على مفتاح Gemini** المجاني:
       - اذهب إلى [Google AI Studio](https://aistudio.google.com/apikey)
       - سجّل دخول بحساب Google
       - اضغط **"Create API Key"**
       - انسخ المفتاح (يبدأ بـ `AIzaSy...`)
       - الصقه في خانة المفتاح بالشريط الجانبي
    3. **ارفع الصورة** (PNG, JPG, WEBP حتى 200MB)
    4. اضغط **"تحليل الصورة الآن"**
    
    ### ملاحظات مهمة:
    - 🔒 **الأمان**: لا يتم حفظ مفاتيح API أو الصور
    - 💡 **المفتاح يبقى محفوظاً** طوال الجلسة تلقائياً
    - 🔄 إذا فشل Gemini، سيتحول التطبيق تلقائياً إلى OCR
    """)

# ─────────────────────────────────────────
# تذييل الصفحة
# ─────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#888; font-size:13px; direction:rtl;">
    📸 تحليل الصور في نقاط - النسخة 3.3 | 
    <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#4CAF50;">
        احصل على مفتاح Gemini المجاني
    </a>
</div>
""", unsafe_allow_html=True)
