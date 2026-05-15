# -*- coding: utf-8 -*-
"""
تحليل الصور في نقاط - الإصدار 5.0
تحسين اللغة العربية في الملخص التنفيذي باستخدام Gemini + صححلي
"""

import sys
import re
import json
import io
import time
import base64
import streamlit as st
import requests
from bs4 import BeautifulSoup

# فحص المكتبات
missing_libs = []
for lib in ["pytesseract", "cv2", "numpy", "PIL", "google.generativeai"]:
    try:
        __import__(lib)
    except ImportError:
        missing_libs.append(lib)

if missing_libs:
    st.error(f"مكتبات مفقودة: {', '.join(missing_libs)}")
    st.stop()

import pytesseract
import cv2
import numpy as np
from PIL import Image
import google.generativeai as genai

# ==================== إعداد الصفحة ====================
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CSS مخصص RTL ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=Cairo:wght@300;400;600;700;900&display=swap');

* { font-family: 'Tajawal', 'Cairo', 'Segoe UI', sans-serif !important; }
html, body, [class*='css'] { direction: rtl; text-align: right; font-size: 17px; }

.main-hero {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 40px;
    text-align: center;
    margin-bottom: 30px;
}
.main-hero h1 { font-size: 2.5rem; font-weight: 900; color: #58a6ff; margin: 0; }
.main-hero p { font-size: 1.1rem; color: #8b949e; margin-top: 10px; }

.stat-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    margin-bottom: 10px;
}
.stat-card h3 { font-size: 2rem; color: #58a6ff; margin: 0; }
.stat-card p { color: #8b949e; margin: 5px 0 0 0; font-size: 0.9rem; }

.result-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
    transition: border-color 0.3s;
}
.result-card:hover { border-color: #58a6ff; }
.result-card .field-label { color: #8b949e; font-size: 0.85rem; margin-bottom: 5px; }
.result-card .field-value { color: #e6edf3; font-size: 1rem; line-height: 1.6; }

.summary-card {
    background: linear-gradient(135deg, #0d1117, #1c2128);
    border: 1px solid #388bfd;
    border-radius: 12px;
    padding: 25px;
    margin-top: 20px;
}
.summary-card h4 { color: #58a6ff; font-size: 1.1rem; margin-bottom: 15px; }
.summary-card p { color: #e6edf3; line-height: 1.8; font-size: 1rem; }

.language-badge {
    background: linear-gradient(135deg, #1f3a5f, #2a1a3a);
    border: 1px solid #388bfd;
    border-radius: 20px;
    padding: 5px 15px;
    font-size: 0.8rem;
    color: #bc8cff;
    display: inline-block;
    margin-top: 8px;
}

.stButton > button {
    background: linear-gradient(135deg, #238636, #2ea043) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 25px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    transition: all 0.3s !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 15px rgba(35,134,54,0.4) !important;
}

.footer {
    text-align: center;
    color: #8b949e;
    font-size: 0.85rem;
    padding: 20px;
    border-top: 1px solid #30363d;
    margin-top: 40px;
}

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #58a6ff; }
</style>
""", unsafe_allow_html=True)

# ==================== القاموس الدلالي ====================
SEMANTIC_KEYWORDS = {
    "عام": ["منشور", "تغريدة", "تعليق", "رأي", "شخص", "مستخدم"],
    "المتطرفون": ["إرهاب", "تطرف", "داعش", "جهاد", "تكفير", "غلو"],
    "سياسية": ["سياسة", "حكومة", "برلمان", "وزير", "رئيس", "انتخابات"],
    "الترفيه": ["فيلم", "مسلسل", "فنان", "غناء", "كرة", "رياضة"],
    "التجنيس": ["تجنيس", "جنسية", "مواطنة", "هوية", "وافد"],
    "تهكم_وسخرية": ["هههه", "😂", "🤣", "طبعاً", "بكل تأكيد", "واضح", "معروف"]
}

# ==================== دوال مساعدة ====================
def validate_api_key(key):
    return key and key.strip().startswith('AIza') and len(key.strip()) > 30

def detect_category(text):
    if not text:
        return "عام"
    text_lower = text.lower()
    for category, keywords in SEMANTIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return "عام"

def is_sarcastic_text(text):
    if not text:
        return False
    sarcasm_indicators = SEMANTIC_KEYWORDS.get("تهكم_وسخرية", [])
    return any(indicator in text for indicator in sarcasm_indicators)

def get_topic_from_text(text):
    if not text:
        return "موضوع عام"
    category = detect_category(text)
    topics = {
        "المتطرفون": "قضايا التطرف",
        "سياسية": "الشأن السياسي",
        "الترفيه": "الترفيه والرياضة",
        "التجنيس": "قضايا التجنيس",
        "تهكم_وسخرية": "تعليق ساخر",
        "عام": "موضوع عام"
    }
    return topics.get(category, "موضوع عام")

def make_x_link(username):
    if not username:
        return "#"
    clean = username.replace("@", "").strip()
    return f"https://x.com/{clean}" if clean else "#"

# ==================== Session State ====================
def get_default_api_key():
    try:
        return st.secrets.get('GEMINI_API_KEY', '')
    except:
        return ''

defaults = {
    'api_key': get_default_api_key(),
    'sahehly_api_key': '',
    'results': [],
    'analysis_done': False,
    'url_analysis_done': False,
    'url_results': None,
    'tweet_data': None,
    'analysis_method': '',
    'used_model': '',
    'total_analyzed': 0,
    'success_count': 0,
    'enable_arabic_enhancement': True,
    'enhancement_method': 'gemini'
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==================== OCR ====================
def preprocess_image_ocr(image):
    img_array = np.array(image)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    denoised = cv2.fastNlMeansDenoising(binary, h=10)
    return Image.fromarray(denoised)

def extract_text_ocr(image):
    try:
        processed = preprocess_image_ocr(image)
        config = '--oem 3 --psm 6 -l ara+eng'
        text = pytesseract.image_to_string(processed, config=config)
        return text.strip() if text.strip() else "لم يتم استخراج نص"
    except Exception as e:
        return f"خطأ في OCR: {str(e)}"

# ==================== تحسين اللغة العربية ====================
def polish_arabic_with_gemini(summary_text, api_key):
    if not summary_text or len(summary_text.strip()) < 20:
        return summary_text, False
    if not validate_api_key(api_key):
        return summary_text, False

    polish_prompt = (
        "أنت مدقق لغوي محترف متخصص في اللغة العربية الفصحى.\n\n"
        "مهمتك: صحح الملخص التالي لغوياً وإملائياً ونحوياً دون تغيير المعنى أو الحذف.\n\n"
        "الملخص الأصلي:\n"
        + summary_text +
        "\n\nقواعد التصحيح الإلزامية:\n"
        "1. صحح الأخطاء الإملائية (الهمزات، التاء المربوطة، الألف اللينة)\n"
        "2. صحح الأخطاء النحوية (التذكير/التأنيث، المفرد/الجمع، الإعراب)\n"
        "3. أصلح علامات الترقيم (الفواصل، النقاط، علامات التعجب)\n"
        "4. حسّن الصياغة مع الحفاظ التام على المعنى\n"
        "5. تجنب العامية والمصطلحات الدخيلة\n"
        "6. لا تزيد معلومات جديدة ولا تحذف معلومات موجودة\n\n"
        "أعد الملخص المُصحَّح فقط بدون أي كلام إضافي أو شرح."
    )

    try:
        genai.configure(api_key=api_key.strip())
        models_to_try = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(polish_prompt)
                corrected = response.text.strip()
                if corrected and len(corrected) > 10:
                    return corrected, True
            except Exception:
                continue
        return summary_text, False
    except Exception:
        return summary_text, False


def correct_with_sahehly_api(text, sahehly_key):
    if not text or not sahehly_key or len(sahehly_key.strip()) < 10:
        return text, False
    try:
        headers = {
            "Authorization": "Bearer " + sahehly_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "text": text[:3000],
            "services": ["spelling", "grammar", "punctuation"]
        }
        response = requests.post(
            "https://sahehly.com/api/v1/correct",
            json=payload,
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            corrected = data.get("corrected_text", text)
            return corrected, True
        else:
            return text, False
    except Exception:
        return text, False


def enhance_arabic_summary(summary_text, api_key, sahehly_key=""):
    if not st.session_state.get('enable_arabic_enhancement', True):
        return summary_text, "بدون تحسين", False

    # الأولوية 1: صححلي API
    if sahehly_key and len(sahehly_key.strip()) > 10:
        corrected, success = correct_with_sahehly_api(summary_text, sahehly_key)
        if success:
            return corrected, "صححلي API", True

    # الأولوية 2: Gemini مدقق لغوي
    if api_key and validate_api_key(api_key):
        corrected, success = polish_arabic_with_gemini(summary_text, api_key)
        if success:
            return corrected, "Gemini مدقق لغوي", True

    return summary_text, "بدون تحسين", False

# ==================== ملخص تنفيذي ====================
def generate_executive_summary(results, text=''):
    if not results:
        return "لا توجد بيانات كافية لإنشاء الملخص."
    topic = get_topic_from_text(text or str(results))
    is_sarcastic = is_sarcastic_text(text)
    summary_parts = []
    post_author = results.get("معرف_المنشور", "")
    comment_author = results.get("معرف_التعليق", "")
    content = results.get("محتوى_المنشور", "")
    opinion = results.get("الرأي", "")
    if post_author and post_author != "غير مُحدد":
        summary_parts.append("نشر المستخدم " + post_author + " منشوراً يتناول " + topic + ".")
    if content and content != "غير مُحدد":
        short_content = content[:100] + "..." if len(content) > 100 else content
        summary_parts.append("تضمّن المنشور: " + short_content)
    if comment_author and comment_author != "غير مُحدد":
        summary_parts.append("علّق عليه " + comment_author)
        if is_sarcastic:
            summary_parts.append("بأسلوب يحمل طابعاً ساخراً.")
    if opinion and opinion != "غير مُحدد":
        summary_parts.append("الرأي المُعبَّر عنه: " + opinion + ".")
    if not summary_parts:
        return "منشور يناقش موضوعاً عاماً على منصة X."
    return " ".join(summary_parts)

# ==================== تحليل نص ذكي ====================
def analyze_post_smart(text, mentions=[]):
    if not text:
        text = "لا يوجد نص"
    category = detect_category(text)
    is_sarcastic = is_sarcastic_text(text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    result = {
        "معرف_المنشور": "غير مُحدد",
        "معرف_التعليق": "غير مُحدد",
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": text[:200] if text else "غير مُحدد",
        "المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": "تعليق ساخر" if is_sarcastic else "موضوع " + category,
        "الملخص_التنفيذي": generate_executive_summary({"محتوى_المنشور": text}, text)
    }
    for line in lines:
        at_matches = re.findall(r'@[\w\u0600-\u06FF]+', line)
        if at_matches and result["معرف_المنشور"] == "غير مُحدد":
            result["معرف_المنشور"] = at_matches[0]
        if len(at_matches) > 1 and result["معرف_التعليق"] == "غير مُحدد":
            result["معرف_التعليق"] = at_matches[1]
    return result

# ==================== جلب محتوى X ====================
def fetch_tweet_content(url):
    result = {"url": url, "text": "", "author": "", "screenshot": None, "error": None}
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            og_desc = soup.find('meta', property='og:description')
            if og_desc:
                result["text"] = og_desc.get('content', '')
            og_title = soup.find('meta', property='og:title')
            if og_title:
                result["author"] = og_title.get('content', '')
        else:
            result["error"] = "HTTP " + str(response.status_code)
    except Exception as e:
        result["error"] = str(e)
    return result

# ==================== JSON Parser ====================
def parse_gemini_json(raw_text):
    if not raw_text:
        return None
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```\w*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned)
        return json.loads(cleaned)
    except:
        pass
    return None

# ==================== بروميبتات Gemini ====================
GEMINI_PROMPT = (
    "أنت محلل متخصص في تحليل منشورات X (تويتر).\n"
    "حلل هذه الصورة واستخرج المعلومات المطلوبة.\n\n"
    "قواعد اللغة العربية الإلزامية في الملخص التنفيذي:\n"
    "- استخدم اللغة العربية الفصحى الدقيقة حصراً\n"
    "- راعِ التذكير والتأنيث والجمع والإفراد\n"
    "- ضع علامات الترقيم في أماكنها الصحيحة\n"
    "- ابتعد عن العامية والمصطلحات الأجنبية\n\n"
    'أعد النتائج بتنسيق JSON فقط:\n'
    '{\n'
    '  "معرف_المنشور": "معرف المستخدم الذي نشر أصلاً (مع @) أو غير مُحدد",\n'
    '  "معرف_التعليق": "معرف من علّق (مع @) أو غير مُحدد",\n'
    '  "المدعو": "اسم أو معرف الشخص المُستشهد به أو غير مُحدد",\n'
    '  "محتوى_المنشور": "النص الكامل للمنشور الأصلي",\n'
    '  "المقطع": "وصف المقطع المرفق أو غير مُحدد",\n'
    '  "التعليق": "نص التعليق كاملاً أو غير مُحدد",\n'
    '  "الرأي": "الرأي أو الموقف المُعبَّر عنه",\n'
    '  "الملخص_التنفيذي": "اكتب ملخصاً تنفيذياً احترافياً بلغة عربية فصحى سليمة لا يقل عن 80 كلمة"\n'
    '}\n\n'
    'مهم: أعد JSON فقط بدون أي نص إضافي.'
)

GEMINI_TEXT_PROMPT = (
    "أنت محلل متخصص في تحليل منشورات X (تويتر).\n"
    "حلل هذا النص واستخرج المعلومات المطلوبة.\n\n"
    "النص: REPLACE_TEXT_HERE\n\n"
    "قواعد اللغة العربية الإلزامية في الملخص التنفيذي:\n"
    "- استخدم اللغة العربية الفصحى الدقيقة حصراً\n"
    "- راعِ التذكير والتأنيث والجمع والإفراد\n"
    "- ضع علامات الترقيم في أماكنها الصحيحة\n"
    "- ابتعد عن العامية والمصطلحات الأجنبية\n\n"
    'أعد النتائج بتنسيق JSON فقط:\n'
    '{\n'
    '  "معرف_المنشور": "معرف المستخدم الذي نشر أصلاً (مع @) أو غير مُحدد",\n'
    '  "معرف_التعليق": "معرف من علّق (مع @) أو غير مُحدد",\n'
    '  "المدعو": "اسم أو معرف الشخص المُستشهد به أو غير مُحدد",\n'
    '  "محتوى_المنشور": "النص الكامل للمنشور الأصلي",\n'
    '  "المقطع": "وصف المقطع المرفق أو غير مُحدد",\n'
    '  "التعليق": "نص التعليق كاملاً أو غير مُحدد",\n'
    '  "الرأي": "الرأي أو الموقف المُعبَّر عنه",\n'
    '  "الملخص_التنفيذي": "اكتب ملخصاً تنفيذياً احترافياً بلغة عربية فصحى سليمة لا يقل عن 80 كلمة"\n'
    '}\n\n'
    'مهم: أعد JSON فقط بدون أي نص إضافي.'
)

# ==================== Gemini: تحليل صورة ====================
def analyze_with_gemini(image, api_key):
    if not validate_api_key(api_key):
        return None, "مفتاح API غير صالح", ""
    genai.configure(api_key=api_key.strip())
    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]
    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([GEMINI_PROMPT, image])
            result = parse_gemini_json(response.text)
            if result:
                for field in ["معرف_المنشور", "معرف_التعليق", "المدعو",
                               "محتوى_المنشور", "المقطع", "التعليق",
                               "الرأي", "الملخص_التنفيذي"]:
                    result.setdefault(field, "غير مُحدد")
                if st.session_state.get('enable_arabic_enhancement', True):
                    enhanced, method, success = enhance_arabic_summary(
                        result.get("الملخص_التنفيذي", ""),
                        api_key,
                        st.session_state.get('sahehly_api_key', '')
                    )
                    if success:
                        result["الملخص_التنفيذي"] = enhanced
                        result["_enhancement_method"] = method
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit"]):
                last_error = model_name + ": تجاوز الحصة"
                time.sleep(2)
                continue
            elif any(x in err for x in ["404", "not found", "MODEL_NOT_FOUND"]):
                last_error = model_name + ": غير متاح"
                continue
            elif any(x in err for x in ["API_KEY_INVALID", "INVALID_ARGUMENT"]):
                return None, "مفتاح API غير صالح", ""
            elif "PERMISSION_DENIED" in err:
                return None, "لا توجد صلاحية", ""
            else:
                last_error = model_name + ": " + err[:60]
                continue
    return None, "فشل التحليل. آخر خطأ: " + last_error, ""

# ==================== Gemini: تحليل نص ====================
def analyze_text_with_gemini(text, api_key):
    if not validate_api_key(api_key):
        return None, "مفتاح API غير صالح", ""

    safe_prompt = GEMINI_TEXT_PROMPT.replace("REPLACE_TEXT_HERE", text[:2000])
    genai.configure(api_key=api_key.strip())

    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]

    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(safe_prompt)
            result = parse_gemini_json(response.text)
            if result:
                for field in ["معرف_المنشور", "معرف_التعليق", "المدعو",
                               "محتوى_المنشور", "المقطع", "التعليق",
                               "الرأي", "الملخص_التنفيذي"]:
                    result.setdefault(field, "غير مُحدد")
                if st.session_state.get('enable_arabic_enhancement', True):
                    enhanced, method, success = enhance_arabic_summary(
                        result.get("الملخص_التنفيذي", ""),
                        api_key,
                        st.session_state.get('sahehly_api_key', '')
                    )
                    if success:
                        result["الملخص_التنفيذي"] = enhanced
                        result["_enhancement_method"] = method
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit"]):
                last_error = model_name + ": تجاوز الحصة"
                time.sleep(2)
                continue
            elif any(x in err for x in ["404", "not found", "MODEL_NOT_FOUND"]):
                last_error = model_name + ": غير متاح"
                continue
            elif any(x in err for x in ["API_KEY_INVALID", "INVALID_ARGUMENT"]):
                return None, "مفتاح API غير صالح", ""
            elif "PERMISSION_DENIED" in err:
                return None, "لا توجد صلاحية", ""
            else:
                last_error = model_name + ": " + err[:60]
                continue
    return None, "فشل التحليل النصي. آخر خطأ: " + last_error, ""

# ==================== تكوين الحقول ====================
FIELD_CONFIG = {
    "معرف_المنشور":    {"icon": "👤", "label": "صاحب المنشور",          "color": "blue"},
    "معرف_التعليق":    {"icon": "💬", "label": "صاحب التعليق",          "color": "green"},
    "المدعو":          {"icon": "🎯", "label": "الشخص المُستشهد به",    "color": "orange"},
    "محتوى_المنشور":   {"icon": "📝", "label": "محتوى المنشور",         "color": "blue"},
    "المقطع":          {"icon": "🎬", "label": "المقطع المرفق",         "color": "purple"},
    "التعليق":         {"icon": "💭", "label": "نص التعليق",            "color": "green"},
    "الرأي":           {"icon": "🔍", "label": "الرأي والموقف",         "color": "orange"},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي",      "color": "purple"}
}

# ==================== عرض النتائج ====================
def render_result_card(field_key, value, index=0):
    if not value or value in ["غير مُحدد", "غير محدد", ""]:
        return
    conf = FIELD_CONFIG.get(field_key, {"icon": "📌", "label": field_key})
    if field_key == "الملخص_التنفيذي":
        st.markdown(
            '<div class="summary-card">'
            '<h4>' + conf['icon'] + ' ' + conf['label'] + '</h4>'
            '<p>' + str(value) + '</p>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="result-card">'
            '<div class="field-label">' + conf['icon'] + ' ' + conf['label'] + '</div>'
            '<div class="field-value">' + str(value) + '</div>'
            '</div>',
            unsafe_allow_html=True
        )

def render_all_results(result, selected_fields, image_index=0):
    if not result:
        st.warning("لا توجد نتائج للعرض")
        return
    enhancement_method = result.get("_enhancement_method", "")
    if enhancement_method:
        st.markdown(
            '<div style="text-align:right; margin-bottom:10px;">'
            '<span class="language-badge">تم تحسين اللغة بواسطة: ' + enhancement_method + '</span>'
            '</div>',
            unsafe_allow_html=True
        )
    for field_key in selected_fields:
        if field_key in result:
            render_result_card(field_key, result[field_key], image_index)
    if "الملخص_التنفيذي" not in selected_fields and "الملخص_التنفيذي" in result:
        render_result_card("الملخص_التنفيذي", result["الملخص_التنفيذي"], image_index)

def download_buttons(result, prefix="result"):
    if not result:
        return
    col1, col2 = st.columns(2)
    with col1:
        txt_content = "\n".join([k + ": " + str(v) for k, v in result.items() if not k.startswith("_")])
        st.download_button("تحميل TXT", txt_content, prefix + ".txt", "text/plain")
    with col2:
        clean_result = {k: v for k, v in result.items() if not k.startswith("_")}
        st.download_button("تحميل JSON", json.dumps(clean_result, ensure_ascii=False, indent=2), prefix + ".json", "application/json")

# ==================== تحليل صورة كاملة ====================
def analyze_image_full(image, api_key, use_gemini):
    result, method, model_name = None, "غير محدد", ""
    if use_gemini and validate_api_key(api_key):
        result, err, model_name = analyze_with_gemini(image, api_key)
        if result:
            method = "Gemini (" + model_name + ")"
    if not result:
        ocr_text = extract_text_ocr(image)
        result = analyze_post_smart(ocr_text)
        method = "OCR + تحليل ذكي"
        if st.session_state.get('enable_arabic_enhancement', True) and validate_api_key(api_key):
            enhanced, emethod, success = enhance_arabic_summary(
                result.get("الملخص_التنفيذي", ""),
                api_key,
                st.session_state.get('sahehly_api_key', '')
            )
            if success:
                result["الملخص_التنفيذي"] = enhanced
                result["_enhancement_method"] = emethod
    return result, method, model_name

# ==================== الشريط الجانبي ====================
with st.sidebar:
    st.markdown("## ⚙️ إعدادات التحليل")

    analysis_mode = st.radio(
        "طريقة التحليل",
        ["🤖 Gemini AI (أدق)", "📝 OCR (مجاني)"],
        index=0
    )
    use_gemini = "Gemini" in analysis_mode

    if use_gemini:
        api_input = st.text_input(
            "🔑 مفتاح Gemini API",
            value=st.session_state.api_key,
            type="password",
            placeholder="AIza..."
        )
        if api_input != st.session_state.api_key:
            st.session_state.api_key = api_input
        if st.session_state.api_key:
            if validate_api_key(st.session_state.api_key):
                st.success("✅ مفتاح صالح")
            else:
                st.error("❌ مفتاح غير صالح")
        st.markdown("🔗 [احصل على مفتاح مجاني](https://aistudio.google.com/apikey)")

    st.markdown("---")
    st.markdown("### ✨ تحسين اللغة العربية")
    enable_enhancement = st.toggle(
        "تفعيل التدقيق اللغوي للملخص",
        value=st.session_state.enable_arabic_enhancement
    )
    st.session_state.enable_arabic_enhancement = enable_enhancement

    if enable_enhancement:
        st.info("يستخدم Gemini لتدقيق الإملاء والنحو في الملخص")
        with st.expander("🔑 مفتاح صححلي API (اختياري)"):
            sahehly_input = st.text_input(
                "مفتاح صححلي للأعمال",
                value=st.session_state.sahehly_api_key,
                type="password",
                placeholder="أدخل مفتاح صححلي إذا كان لديك اشتراك"
            )
            if sahehly_input != st.session_state.sahehly_api_key:
                st.session_state.sahehly_api_key = sahehly_input
            st.markdown("🔗 [اشترك في صححلي للأعمال](https://sahehly.com/Pricing/AddBusinessRequest)")

    st.markdown("---")
    st.markdown("### 📋 الحقول المعروضة")
    selected_fields = st.multiselect(
        "اختر الحقول",
        list(FIELD_CONFIG.keys()),
        default=list(FIELD_CONFIG.keys()),
        format_func=lambda x: FIELD_CONFIG[x]['icon'] + " " + FIELD_CONFIG[x]['label']
    )

    st.markdown("---")
    st.markdown("### 📊 إحصائيات الجلسة")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("📸 محلّلة", st.session_state.total_analyzed)
    with col_s2:
        st.metric("✅ ناجحة", st.session_state.success_count)

    if st.button("🗑️ مسح جميع النتائج"):
        for key in ['results', 'analysis_done', 'url_analysis_done',
                    'url_results', 'tweet_data', 'total_analyzed', 'success_count']:
            st.session_state[key] = [] if key == 'results' else (False if 'done' in key else (0 if 'count' in key or 'analyzed' in key else None))
        st.rerun()

    with st.expander("📖 القاموس الدلالي"):
        for cat, words in SEMANTIC_KEYWORDS.items():
            st.markdown("**" + cat + "**: " + ", ".join(words[:4]) + "...")

# ==================== الواجهة الرئيسية ====================
st.markdown("""
<div class="main-hero">
    <h1>🔍 تحليل الصور في نقاط</h1>
    <p>تحليل منشورات منصة X بالذكاء الاصطناعي · بسرعة ودقة</p>
    <p><span class="language-badge">✨ الإصدار 5.0 — تدقيق لغوي ذكي</span></p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="stat-card"><h3>' + str(st.session_state.total_analyzed) + '</h3><p>📸 صور محلّلة</p></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="stat-card"><h3>' + str(st.session_state.success_count) + '</h3><p>✅ تحليل ناجح</p></div>', unsafe_allow_html=True)
with col3:
    enhancement_status = "🟢 مفعّل" if st.session_state.enable_arabic_enhancement else "🔴 معطّل"
    st.markdown('<div class="stat-card"><h3>' + enhancement_status + '</h3><p>✨ التدقيق اللغوي</p></div>', unsafe_allow_html=True)
with col4:
    sahehly_status = "🟢 صححلي" if st.session_state.sahehly_api_key else "🤖 Gemini"
    st.markdown('<div class="stat-card"><h3>' + sahehly_status + '</h3><p>🔧 محرك التدقيق</p></div>', unsafe_allow_html=True)

# ==================== تبويبات ====================
tab_paste, tab_upload, tab_url, tab_guide = st.tabs([
    "📋 لصق من الحافظة",
    "📤 رفع صور",
    "🔗 رابط X",
    "📖 دليل الاستخدام"
])

# ==================== تبويب اللصق ====================
with tab_paste:
    st.markdown("### 📋 لصق صورة من الحافظة")
    st.info("انسخ الصورة (Ctrl+C) ثم ارفعها باستخدام الزر أدناه")
    paste_file = st.file_uploader("اختر صورة أو الصقها", type=['png', 'jpg', 'jpeg', 'webp'], key="paste_uploader")
    if paste_file:
        image = Image.open(paste_file)
        st.image(image, caption="الصورة المُختارة", use_column_width=True)
        if st.button("🚀 تحليل الصورة", key="analyze_paste"):
            with st.spinner("جارٍ التحليل..."):
                result, method, model_name = analyze_image_full(image, st.session_state.api_key, use_gemini)
                st.session_state.total_analyzed += 1
                if result:
                    st.session_state.success_count += 1
                    st.success("تم التحليل بنجاح | الطريقة: " + method)
                    emethod = result.get('_enhancement_method', '')
                    if emethod:
                        st.info("تم تحسين اللغة بواسطة: " + emethod)
                    render_all_results(result, selected_fields)
                    download_buttons(result, "paste_result")
                else:
                    st.error("فشل التحليل. جرّب OCR أو تحقق من المفتاح.")

# ==================== تبويب رفع الصور ====================
with tab_upload:
    st.markdown("### 📤 رفع صور متعددة")
    uploaded_files = st.file_uploader(
        "اسحب الصور هنا أو اضغط للاختيار",
        type=['png', 'jpg', 'jpeg', 'webp', 'bmp'],
        accept_multiple_files=True,
        key="batch_uploader"
    )
    if uploaded_files:
        st.markdown("#### الصور المُختارة (" + str(len(uploaded_files)) + ")")
        cols = st.columns(min(len(uploaded_files), 3))
        for i, f in enumerate(uploaded_files):
            with cols[i % 3]:
                img = Image.open(f)
                st.image(img, caption=f.name, use_column_width=True)

        if st.button("🚀 تحليل جميع الصور", key="analyze_batch"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            batch_results = []
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text("جارٍ تحليل الصورة " + str(i+1) + " من " + str(len(uploaded_files)) + "...")
                image = Image.open(uploaded_file)
                result, method, model_name = analyze_image_full(image, st.session_state.api_key, use_gemini)
                st.session_state.total_analyzed += 1
                if result:
                    st.session_state.success_count += 1
                    batch_results.append({"file": uploaded_file.name, "result": result, "method": method})
                progress_bar.progress((i + 1) / len(uploaded_files))
                time.sleep(0.5)
            st.session_state.results = batch_results
            st.session_state.analysis_done = True
            status_text.text("تم تحليل " + str(len(batch_results)) + " صورة!")
            st.rerun()

    if st.session_state.analysis_done and st.session_state.results:
        st.markdown("### نتائج التحليل (" + str(len(st.session_state.results)) + " صورة)")
        for i, item in enumerate(st.session_state.results):
            with st.expander(item['file'] + " — " + item['method'], expanded=(i == 0)):
                emethod = item['result'].get('_enhancement_method', '')
                if emethod:
                    st.markdown('<div style="text-align:right;"><span class="language-badge">✨ ' + emethod + '</span></div>', unsafe_allow_html=True)
                render_all_results(item['result'], selected_fields, i)
                download_buttons(item['result'], "result_" + str(i+1))

# ==================== تبويب رابط X ====================
with tab_url:
    st.markdown("### 🔗 تحليل منشور من رابط X")
    tweet_url = st.text_input(
        "أدخل رابط المنشور",
        placeholder="https://x.com/username/status/...",
        key="tweet_url_input"
    )
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📥 جلب المنشور فقط", key="fetch_only"):
            if tweet_url and ("x.com" in tweet_url or "twitter.com" in tweet_url):
                with st.spinner("جارٍ الجلب..."):
                    tweet_data = fetch_tweet_content(tweet_url)
                    st.session_state.tweet_data = tweet_data
                st.rerun()
            else:
                st.warning("أدخل رابط X/Twitter صحيح")

    with col_btn2:
        if st.button("🚀 جلب وتحليل", key="fetch_analyze"):
            if tweet_url and ("x.com" in tweet_url or "twitter.com" in tweet_url):
                with st.spinner("جارٍ الجلب والتحليل..."):
                    tweet_data = fetch_tweet_content(tweet_url)
                    st.session_state.tweet_data = tweet_data
                    result, method, model_name = None, "غير محدد", ""
                    tweet_text = tweet_data.get("text", "").strip()

                    if tweet_text and use_gemini and validate_api_key(st.session_state.api_key):
                        result, err, model_name = analyze_text_with_gemini(tweet_text, st.session_state.api_key)
                        if result:
                            method = "Gemini نص (" + model_name + ")"

                    if not result and tweet_data.get("screenshot") and use_gemini and validate_api_key(st.session_state.api_key):
                        result, err, model_name = analyze_with_gemini(tweet_data["screenshot"], st.session_state.api_key)
                        if result:
                            method = "Gemini صورة (" + model_name + ")"

                    if not result:
                        fallback_text = tweet_text if tweet_text else "لا يوجد نص متاح"
                        result = analyze_post_smart(fallback_text)
                        method = "تحليل نصي ذكي"
                        if st.session_state.get('enable_arabic_enhancement', True) and validate_api_key(st.session_state.api_key):
                            enhanced, emethod, success = enhance_arabic_summary(
                                result.get("الملخص_التنفيذي", ""),
                                st.session_state.api_key,
                                st.session_state.get('sahehly_api_key', '')
                            )
                            if success:
                                result["الملخص_التنفيذي"] = enhanced
                                result["_enhancement_method"] = emethod

                    st.session_state.url_results = result
                    st.session_state.url_analysis_done = True
                    st.session_state.analysis_method = method
                    st.session_state.used_model = model_name
                    st.session_state.total_analyzed += 1
                    if result:
                        st.session_state.success_count += 1
                st.rerun()
            else:
                st.warning("الرجاء إدخال رابط X/Twitter صحيح")

    if st.session_state.tweet_data:
        td = st.session_state.tweet_data
        st.markdown("#### بيانات المنشور المُجلَب")
        if td.get("text"):
            st.text_area("النص", td["text"], height=100, disabled=True)
        if td.get("author"):
            st.info("👤 " + td['author'])
        if td.get("error"):
            st.warning("⚠️ " + td['error'])

    if st.session_state.url_analysis_done and st.session_state.url_results:
        st.markdown("---")
        st.markdown("#### نتائج التحليل | الطريقة: " + st.session_state.analysis_method)
        emethod = st.session_state.url_results.get('_enhancement_method', '')
        if emethod:
            st.markdown('<div style="text-align:right;"><span class="language-badge">✨ ' + emethod + '</span></div>', unsafe_allow_html=True)
        render_all_results(st.session_state.url_results, selected_fields)
        download_buttons(st.session_state.url_results, "url_result")

# ==================== دليل الاستخدام ====================
with tab_guide:
    st.markdown("""
### 📖 دليل الاستخدام السريع

#### 🚀 البدء السريع
1. احصل على مفتاح Gemini من [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. أدخل المفتاح في الشريط الجانبي
3. ارفع صورة أو أدخل رابط X للتحليل

#### ✨ ميزة التدقيق اللغوي — جديد في v5.0
- مفعّلة تلقائياً وتُحسّن الملخص التنفيذي لغوياً
- Gemini كمدقق: يصحح الإملاء والنحو وعلامات الترقيم
- صححلي API: إذا كان لديك اشتراك أعمال في sahehly.com أدخل المفتاح للحصول على تدقيق أدق

#### 📋 تبويب لصق من الحافظة
- انسخ صورة من X ثم ارفعها

#### 📤 تبويب رفع صور
- يدعم PNG, JPG, JPEG, WebP, BMP
- يمكن رفع صور متعددة دفعة واحدة

#### 🔗 تبويب رابط X
- أدخل رابط المنشور مباشرة واضغط جلب وتحليل

#### 💾 تحميل النتائج
- TXT للمشاركة السريعة
- JSON للمعالجة البرمجية
    """)

# ==================== التذييل ====================
st.markdown("""
<div class="footer">
    📸 تحليل الصور في نقاط — الإصدار 5.0<br>
    مدعوم بـ Gemini AI + تدقيق لغوي ذكي<br>
    <a href="https://aistudio.google.com/apikey" style="color:#58a6ff;">احصل على مفتاح Gemini</a>
    &nbsp;|&nbsp;
    <a href="https://sahehly.com" style="color:#58a6ff;">صححلي للتدقيق اللغوي</a>
</div>
""", unsafe_allow_html=True)
