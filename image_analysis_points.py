```python
# -*- coding: utf-8 -*-
"""
تحليل الصور في نقاط - الإصدار 5.0
مع تحسين اللغة العربية في الملخص التنفيذي
"""
import sys, re, json, io, time, base64
import streamlit as st
import pytesseract
import cv2
import numpy as np
from PIL import Image
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# ==================== فحص المكتبات ====================
missing_libs = []
libs_to_check = [
    ("streamlit", "streamlit"),
    ("pytesseract", "pytesseract"),
    ("cv2", "opencv-python-headless"),
    ("numpy", "numpy"),
    ("PIL", "Pillow"),
    ("google.generativeai", "google-generativeai"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
]
for lib, name in libs_to_check:
    try:
        __import__(lib)
    except ImportError:
        missing_libs.append(name)

if missing_libs:
    st.error(f"❌ مكتبات مفقودة: {', '.join(missing_libs)}")
    st.code("pip install " + " ".join(missing_libs))
    st.stop()

# ==================== إعداد الصفحة ====================
st.set_page_config(
    page_title="🔍 تحليل الصور في نقاط",
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

.main { background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%); }

.main-hero {
    background: linear-gradient(135deg, #1a1f2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 20px; padding: 40px; margin-bottom: 30px;
    border: 1px solid rgba(99,179,237,0.2);
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    text-align: center;
}
.hero-title {
    font-size: 2.8rem; font-weight: 900; color: #fff;
    text-shadow: 0 0 30px rgba(99,179,237,0.5);
    margin-bottom: 10px;
}
.hero-subtitle {
    font-size: 1.2rem; color: rgba(255,255,255,0.7);
    margin-bottom: 0;
}

.stat-card {
    background: linear-gradient(135deg, #1a1f2e, #16213e);
    border-radius: 15px; padding: 20px; text-align: center;
    border: 1px solid rgba(99,179,237,0.2);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.stat-card:hover { transform: translateY(-5px); box-shadow: 0 15px 40px rgba(0,0,0,0.4); }
.stat-number { font-size: 2rem; font-weight: 900; color: #63b3ed; }
.stat-label { font-size: 0.9rem; color: rgba(255,255,255,0.6); margin-top: 5px; }

.result-card {
    background: linear-gradient(135deg, #1a1f2e, #16213e);
    border-radius: 15px; padding: 20px; margin-bottom: 15px;
    border: 1px solid rgba(99,179,237,0.15);
    border-right: 4px solid #63b3ed;
    transition: all 0.3s ease;
}
.result-card:hover { border-right-color: #90cdf4; box-shadow: 0 8px 25px rgba(0,0,0,0.3); }
.field-label {
    font-size: 0.85rem; color: #90cdf4; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;
}
.field-value { font-size: 1rem; color: #e2e8f0; line-height: 1.7; }

.executive-summary {
    background: linear-gradient(135deg, #1a2744, #0f3460);
    border-radius: 15px; padding: 25px; margin: 15px 0;
    border: 2px solid rgba(99,179,237,0.4);
    font-size: 1.05rem; color: #e2e8f0; line-height: 1.9;
    text-align: justify;
}
.executive-summary-header {
    font-size: 1rem; color: #63b3ed; font-weight: 700;
    margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
}

.language-badge {
    display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 700; margin: 3px;
}
.badge-corrected { background: rgba(72,187,120,0.2); color: #68d391; border: 1px solid rgba(72,187,120,0.3); }
.badge-original  { background: rgba(237,137,54,0.2);  color: #f6ad55; border: 1px solid rgba(237,137,54,0.3); }
.badge-gemini    { background: rgba(99,179,237,0.2);  color: #63b3ed; border: 1px solid rgba(99,179,237,0.3); }

.stButton > button {
    background: linear-gradient(135deg, #2b6cb0, #1a365d) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; padding: 10px 24px !important;
    font-size: 1rem !important; font-weight: 700 !important;
    transition: all 0.3s ease !important; width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(43,108,176,0.4) !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #1a1f2e !important; color: #e2e8f0 !important;
    border: 1px solid rgba(99,179,237,0.3) !important;
    border-radius: 10px !important; font-size: 1rem !important;
    text-align: right !important; direction: rtl !important;
}

.paste-zone {
    border: 2px dashed rgba(99,179,237,0.4); border-radius: 15px;
    padding: 40px; text-align: center; margin: 20px 0;
    background: rgba(99,179,237,0.03);
    transition: all 0.3s ease; cursor: pointer;
}
.paste-zone:hover { border-color: rgba(99,179,237,0.8); background: rgba(99,179,237,0.08); }

.footer {
    text-align: center; padding: 30px; margin-top: 50px;
    color: rgba(255,255,255,0.4); font-size: 0.85rem;
    border-top: 1px solid rgba(255,255,255,0.1);
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a1f2e; }
::-webkit-scrollbar-thumb { background: #2b6cb0; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #63b3ed; }
</style>
""", unsafe_allow_html=True)

# ==================== القاموس الدلالي ====================
SEMANTIC_KEYWORDS = {
    "عام": ["منشور", "تغريدة", "تعليق", "رأي", "شخص", "مستخدم"],
    "المتطرفون": ["إرهاب", "تطرف", "داعش", "جهاد", "تكفير", "غلو"],
    "سياسية": ["سياسة", "حكومة", "برلمان", "وزير", "رئيس", "انتخابات"],
    "الترفيه": ["فيلم", "مسلسل", "فنان", "غناء", "كرة", "رياضة"],
    "التجنيس": ["تجنيس", "جنسية", "مواطنة", "هوية", "وافد"],
    "تهكم_وسخرية": ["هههه", "😂", "🤣", "طبعاً", "بكل تأكيد", "واضح", "معروف"],
}

# ==================== دوال مساعدة ====================
def detect_category(text):
    if not text:
        return "عام"
    text_lower = text.lower()
    for cat, keywords in SEMANTIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "عام"

def is_sarcastic_text(text):
    if not text:
        return False
    sarcasm_indicators = SEMANTIC_KEYWORDS.get("تهكم_وسخرية", [])
    return any(ind in text for ind in sarcasm_indicators)

def get_topic_from_text(text):
    if not text:
        return "موضوع عام"
    for cat, keywords in SEMANTIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "موضوع عام"

def make_x_link(username):
    if not username:
        return "#"
    username = username.strip().lstrip("@")
    return f"https://x.com/{username}" if username != "غير مُحدد" else "#"

def validate_api_key(key):
    return bool(key and key.strip().startswith("AIza") and len(key.strip()) > 30)

# ==================== Session State ====================
def get_default_api_key():
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""

defaults = {
    "api_key": get_default_api_key(),
    "results": [],
    "analysis_done": False,
    "url_analysis_done": False,
    "url_results": None,
    "tweet_data": None,
    "total_analyzed": 0,
    "success_count": 0,
    "fail_count": 0,
    "analysis_method": "غير محدد",
    "used_model": "",
    "polish_enabled": True,
    "sahehly_enabled": False,
    "sahehly_api_key": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==================== OCR ====================
def preprocess_image_ocr(image):
    img_array = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    scale = 2.0
    h, w = thresh.shape
    resized = cv2.resize(thresh, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    return Image.fromarray(resized)

def extract_text_ocr(image):
    try:
        processed = preprocess_image_ocr(image)
        config = "--oem 3 --psm 6 -l ara+eng"
        text = pytesseract.image_to_string(processed, config=config)
        return text.strip() if text.strip() else "لم يتم استخراج نص"
    except Exception as e:
        return f"خطأ OCR: {str(e)}"

# ==================== تحسين اللغة العربية ====================
def polish_arabic_summary_with_gemini(summary_text: str, api_key: str) -> tuple:
    """
    تلميع الملخص التنفيذي لغوياً باستخدام Gemini كمدقق لغوي
    يعوّض عن API صححلي مجاناً
    الإرجاع: (النص المصحح, هل تم التصحيح)
    """
    if not summary_text or len(summary_text.strip()) < 20:
        return summary_text, False
    if not validate_api_key(api_key):
        return summary_text, False

    polish_prompt = f"""أنت مدقق لغوي متخصص في اللغة العربية الفصحى.

المهمة: صحح الملخص التالي لغوياً وإملائياً ونحوياً دون تغيير المعنى مطلقاً.

الملخص الأصلي:
{summary_text}

قواعد التصحيح الإلزامية:
1. صحح الأخطاء الإملائية (مثل: إن/أن، الهمزات، التاء المربوطة)
2. صحح الأخطاء النحوية (التذكير/التأنيث، المفرد/الجمع، حروف الجر)
3. أصلح علامات الترقيم (الفواصل، النقاط، علامات الاستفهام)
4. حسّن الصياغة مع الحفاظ على المعنى الكامل
5. استخدم اللغة العربية الفصحى الراقية
6. لا تزيد ولا تحذف أي معلومة
7. حافظ على نفس الطول التقريبي

أعد الملخص المُصحَّح فقط بدون أي تعليق أو شرح."""

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


def correct_with_sahehly_api(text: str, sahehly_key: str) -> tuple:
    """
    تصحيح النص باستخدام API صححلي الرسمي (يحتاج خطة أعمال)
    الإرجاع: (النص المصحح, هل تم التصحيح)
    """
    if not text or not sahehly_key:
        return text, False
    try:
        headers = {
            "Authorization": f"Bearer {sahehly_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "text": text,
            "services": ["spelling", "grammar", "punctuation"],
        }
        response = requests.post(
            "https://sahehly.com/api/v1/correct",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            corrected = data.get("corrected_text", "")
            return (corrected, True) if corrected else (text, False)
        return text, False
    except Exception:
        return text, False


def enhance_arabic_summary(summary_text: str, api_key: str) -> tuple:
    """
    الدالة الرئيسية لتحسين اللغة العربية في الملخص:
    - إذا كان مفتاح صححلي متاحاً → استخدمه
    - وإلا → استخدم Gemini كمدقق لغوي
    الإرجاع: (النص المحسّن, طريقة التحسين)
    """
    if not summary_text or len(summary_text.strip()) < 20:
        return summary_text, "لم يتم التحسين"

    # أولاً: API صححلي (إذا كان متاحاً)
    if st.session_state.get("sahehly_enabled") and st.session_state.get("sahehly_api_key"):
        corrected, success = correct_with_sahehly_api(
            summary_text, st.session_state.sahehly_api_key
        )
        if success:
            return corrected, "صححلي API ✨"

    # ثانياً: Gemini كمدقق لغوي (مجاني)
    if st.session_state.get("polish_enabled") and validate_api_key(api_key):
        corrected, success = polish_arabic_summary_with_gemini(summary_text, api_key)
        if success:
            return corrected, "Gemini مدقق لغوي ✨"

    return summary_text, "بدون تحسين"

# ==================== parse JSON ====================
def parse_gemini_json(raw_text):
    if not raw_text:
        return None
    try:
        cleaned = re.sub(r"```(?:json)?", "", raw_text).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None

# ==================== ملخص تنفيذي ====================
def generate_executive_summary(results, text=""):
    if not results and not text:
        return "لا توجد بيانات كافية لإنشاء الملخص."
    lines = []
    if isinstance(results, dict):
        content = results.get("محتوى_المنشور", "")
        opinion = results.get("الرأي", "")
        comment = results.get("التعليق", "")
        author = results.get("معرف_المنشور", "")
        if author and author != "غير مُحدد":
            lines.append(f"نشر المستخدم {author} منشوراً")
        if content and content != "غير مُحدد":
            lines.append(f"يتناول: {content[:120]}")
        if opinion and opinion != "غير مُحدد":
            lines.append(f"ويعبّر عن موقف: {opinion[:100]}")
        if comment and comment != "غير مُحدد":
            lines.append(f"مع تعليق: {comment[:100]}")
    if text:
        topic = get_topic_from_text(text)
        is_sarcasm = is_sarcastic_text(text)
        lines.append(f"الموضوع الرئيسي: {topic}")
        if is_sarcasm:
            lines.append("يحتوي المنشور على نبرة تهكمية أو ساخرة.")
    return "، ".join(lines) + "." if lines else "محتوى غير واضح."

# ==================== تحليل ذكي ====================
def analyze_post_smart(text, mentions=None):
    if mentions is None:
        mentions = []
    if not text or text.strip() == "":
        text = "لا يوجد نص"
    category = detect_category(text)
    is_sarcasm = is_sarcastic_text(text)
    opinion = "تهكم وسخرية" if is_sarcasm else f"رأي في موضوع {category}"
    author = mentions[0] if mentions else "غير مُحدد"
    commenter = mentions[1] if len(mentions) > 1 else "غير مُحدد"
    summary = generate_executive_summary({"محتوى_المنشور": text[:150]}, text)
    return {
        "معرف_المنشور": author,
        "معرف_التعليق": commenter,
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": text[:300],
        "المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": opinion,
        "الملخص_التنفيذي": summary,
    }

# ==================== جلب محتوى X ====================
def fetch_tweet_content(url):
    result = {
        "url": url, "text": "", "author": "", "screenshot": None, "error": None
    }
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ar,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        meta_desc = soup.find("meta", {"name": "description"})
        og_desc = soup.find("meta", {"property": "og:description"})
        if meta_desc and meta_desc.get("content"):
            result["text"] = meta_desc["content"]
        elif og_desc and og_desc.get("content"):
            result["text"] = og_desc["content"]
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title:
            result["author"] = og_title.get("content", "")
    except Exception as e:
        result["error"] = str(e)
    return result

# ==================== بروميبتات Gemini ====================
GEMINI_PROMPT = """
أنت محلل متخصص في تحليل صور منشورات X (تويتر).
حلل هذه الصورة واستخرج جميع المعلومات المرئية.

أعد النتائج بتنسيق JSON فقط بدون أي نص إضافي:
{{
  "معرف_المنشور": "معرف المستخدم الذي نشر أصلاً (مع @)",
  "معرف_التعليق": "معرف من علّق (مع @) أو غير مُحدد",
  "المدعو": "اسم أو معرف الشخص المُستشهد به أو غير مُحدد",
  "محتوى_المنشور": "النص الكامل للمنشور الأصلي",
  "المقطع": "وصف المقطع أو الصورة المرفقة أو غير مُحدد",
  "التعليق": "نص التعليق كاملاً أو غير مُحدد",
  "الرأي": "الرأي أو الموقف المُعبَّر عنه في المنشور",
  "الملخص_التنفيذي": "اكتب ملخصاً تنفيذياً احترافياً باللغة العربية الفصحى السليمة لا يقل عن 80 كلمة، يشرح المنشور وسياقه وأهميته مع مراعاة دقة الصياغة والنحو والإملاء"
}}
"""

GEMINI_TEXT_PROMPT = """
أنت محلل لغوي متخصص في تحليل منشورات X (تويتر).
حلل هذا النص واستخرج المعلومات المطلوبة.

النص: {text}

⚠️ قواعد اللغة العربية الواجب اتباعها في الملخص التنفيذي:
- استخدم اللغة العربية الفصحى الدقيقة فقط
- لا تستخدم العامية أو المصطلحات الدخيلة
- راعِ التذكير والتأنيث والجمع والإفراد
- ضع علامات الترقيم في أماكنها الصحيحة
- ابدأ الجمل بأفعال أو أسماء مناسبة
- تجنب التكرار وضعف الصياغة

أعد النتائج بتنسيق JSON فقط بدون أي نص إضافي:
{{
  "معرف_المنشور": "معرف المستخدم الذي نشر أصلاً (مع @)",
  "معرف_التعليق": "معرف من علّق (مع @) أو غير مُحدد",
  "المدعو": "اسم أو معرف الشخص المُستشهد به أو غير مُحدد",
  "محتوى_المنشور": "النص الكامل للمنشور الأصلي",
  "المقطع": "وصف المقطع أو الصورة المرفقة أو غير مُحدد",
  "التعليق": "نص التعليق كاملاً أو غير مُحدد",
  "الرأي": "الرأي أو الموقف المُعبَّر عنه",
  "الملخص_التنفيذي": "اكتب ملخصاً تنفيذياً احترافياً باللغة العربية الفصحى السليمة لا يقل عن 80 كلمة، يشرح المنشور وسياقه وأهميته مع مراعاة دقة الصياغة والنحو والإملاء"
}}
"""

REQUIRED_FIELDS = [
    "معرف_المنشور", "معرف_التعليق", "المدعو",
    "محتوى_المنشور", "المقطع", "التعليق",
    "الرأي", "الملخص_التنفيذي",
]

# ==================== Gemini: تحليل صورة ====================
def analyze_with_gemini(image, api_key):
    if not validate_api_key(api_key):
        return None, "❌ مفتاح API غير صالح", ""
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
            if isinstance(image, Image.Image):
                response = model.generate_content([GEMINI_PROMPT, image])
            else:
                response = model.generate_content(GEMINI_PROMPT)
            result = parse_gemini_json(response.text)
            if result:
                for field in REQUIRED_FIELDS:
                    result.setdefault(field, "غير مُحدد")
                # تحسين الملخص التنفيذي
                if st.session_state.get("polish_enabled"):
                    enhanced, method = enhance_arabic_summary(
                        result.get("الملخص_التنفيذي", ""), api_key
                    )
                    result["الملخص_التنفيذي"] = enhanced
                    result["_polish_method"] = method
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit"]):
                last_error = f"⚠️ {model_name}: تجاوز الحصة"
                time.sleep(2)
                continue
            elif any(x in err for x in ["404", "not found", "MODEL_NOT_FOUND"]):
                last_error = f"⚠️ {model_name}: غير متاح"
                continue
            elif any(x in err for x in ["API_KEY_INVALID", "INVALID_ARGUMENT"]):
                return None, "❌ مفتاح API غير صالح", ""
            elif "PERMISSION_DENIED" in err:
                return None, "❌ لا توجد صلاحية - تحقق من المفتاح", ""
            else:
                last_error = f"⚠️ {model_name}: {err[:60]}"
                continue
    return None, f"❌ فشل التحليل. آخر خطأ: {last_error}", ""


# ==================== Gemini: تحليل نص ====================
def analyze_text_with_gemini(text, api_key):
    if not validate_api_key(api_key):
        return None, "❌ مفتاح API غير صالح", ""

    safe_prompt = GEMINI_TEXT_PROMPT.replace("{text}", text[:2000])
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
                for field in REQUIRED_FIELDS:
                    result.setdefault(field, "غير مُحدد")
                # تحسين الملخص التنفيذي
                if st.session_state.get("polish_enabled"):
                    enhanced, method = enhance_arabic_summary(
                        result.get("الملخص_التنفيذي", ""), api_key
                    )
                    result["الملخص_التنفيذي"] = enhanced
                    result["_polish_method"] = method
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit"]):
                last_error = f"⚠️ {model_name}: تجاوز الحصة"
                time.sleep(2)
                continue
            elif any(x in err for x in ["404", "not found", "MODEL_NOT_FOUND"]):
                last_error = f"⚠️ {model_name}: غير متاح"
                continue
            elif any(x in err for x in ["API_KEY_INVALID", "INVALID_ARGUMENT"]):
                return None, "❌ مفتاح API غير صالح", ""
            elif "PERMISSION_DENIED" in err:
                return None, "❌ لا توجد صلاحية - تحقق من المفتاح", ""
            else:
                last_error = f"⚠️ {model_name}: {err[:60]}"
                continue
    return None, f"❌ فشل التحليل النصي. آخر خطأ: {last_error}", ""


# ==================== تكوين الحقول ====================
FIELD_CONFIG = {
    "معرف_المنشور":   {"icon": "👤", "label": "صاحب المنشور",       "color": "#63b3ed"},
    "معرف_التعليق":   {"icon": "💬", "label": "صاحب التعليق",       "color": "#68d391"},
    "المدعو":          {"icon": "🎯", "label": "الشخص المُستشهد به", "color": "#f6ad55"},
    "محتوى_المنشور":  {"icon": "📝", "label": "محتوى المنشور",      "color": "#fc8181"},
    "المقطع":          {"icon": "🎬", "label": "المقطع المرفق",      "color": "#b794f4"},
    "التعليق":         {"icon": "💭", "label": "نص التعليق",         "color": "#76e4f7"},
    "الرأي":           {"icon": "🔍", "label": "الرأي والموقف",      "color": "#fbb6ce"},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي",   "color": "#90cdf4"},
}

# ==================== عرض النتائج ====================
def render_result_card(field_key, value, config, selected_fields):
    if field_key not in selected_fields:
        return
    if not value or value in ["غير مُحدد", "غير محدد", ""]:
        return
    cfg = config.get(field_key, {})
    icon = cfg.get("icon", "•")
    label = cfg.get("label", field_key)
    color = cfg.get("color", "#63b3ed")

    if field_key == "الملخص_التنفيذي":
        polish_method = ""
        if isinstance(value, dict):
            polish_method = value.get("_polish_method", "")
        st.markdown(f"""
        <div class="executive-summary">
            <div class="executive-summary-header">
                {icon} {label}
                {"<span class='language-badge badge-corrected'>✨ " + polish_method + "</span>" if polish_method else ""}
            </div>
            <div style="font-size:1.05rem; line-height:1.9; text-align:justify;">{value}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        x_link = ""
        if field_key in ["معرف_المنشور", "معرف_التعليق", "المدعو"]:
            link = make_x_link(str(value))
            if link != "#":
                x_link = f'<a href="{link}" target="_blank" style="color:{color};font-size:0.8rem;margin-right:8px;">🔗 الملف الشخصي</a>'
        st.markdown(f"""
        <div class="result-card" style="border-right-color:{color};">
            <div class="field-label">{icon} {label}</div>
            <div class="field-value">{value} {x_link}</div>
        </div>
        """, unsafe_allow_html=True)


def render_all_results(result, selected_fields, image=None):
    if not result:
        st.error("❌ لم يتم الحصول على نتائج.")
        return

    polish_method = result.get("_polish_method", "")
    method_badge = f"<span class='language-badge badge-corrected'>✨ {polish_method}</span>" if polish_method else ""

    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px; flex-wrap:wrap;">
        <h3 style="color:#63b3ed; margin:0;">📊 نتائج التحليل</h3>
        {method_badge}
        <span class='language-badge badge-gemini'>🤖 {result.get("_model", "Gemini")}</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    fields_left  = ["معرف_المنشور", "معرف_التعليق", "المدعو", "المقطع"]
    fields_right = ["محتوى_المنشور", "التعليق", "الرأي"]

    with col1:
        for f in fields_left:
            render_result_card(f, result.get(f, ""), FIELD_CONFIG, selected_fields)
    with col2:
        for f in fields_right:
            render_result_card(f, result.get(f, ""), FIELD_CONFIG, selected_fields)

    if "الملخص_التنفيذي" in selected_fields:
        render_result_card(
            "الملخص_التنفيذي",
            result.get("الملخص_التنفيذي", ""),
            FIELD_CONFIG,
            selected_fields,
        )

    if image:
        with st.expander("🖼️ الصورة الأصلية"):
            st.image(image, use_column_width=True)


def download_buttons(result):
    if not result:
        return
    col1, col2 = st.columns(2)
    with col1:
        lines = [f"{FIELD_CONFIG.get(k, {}).get('label', k)}: {v}"
                 for k, v in result.items() if not k.startswith("_")]
        txt_data = "\n".join(lines)
        st.download_button("📥 تحميل TXT", txt_data,
                           file_name="analysis.txt", mime="text/plain", key=f"dl_txt_{id(result)}")
    with col2:
        json_data = json.dumps(
            {k: v for k, v in result.items() if not k.startswith("_")},
            ensure_ascii=False, indent=2
        )
        st.download_button("📥 تحميل JSON", json_data,
                           file_name="analysis.json", mime="application/json", key=f"dl_json_{id(result)}")


# ==================== تحليل صورة كاملة ====================
def analyze_image_full(image, api_key, use_gemini):
    if use_gemini and validate_api_key(api_key):
        result, err, model_name = analyze_with_gemini(image, api_key)
        if result:
            result["_model"] = model_name
            result["_method"] = "Gemini AI"
            return result, None
        return None, err or "فشل التحليل"
    else:
        ocr_text = extract_text_ocr(image)
        result = analyze_post_smart(ocr_text)
        result["_model"] = "OCR"
        result["_method"] = "OCR"
        return result, None


# ==================== الشريط الجانبي ====================
with st.sidebar:
    st.markdown("## ⚙️ إعدادات التحليل")
    st.markdown("---")

    analysis_mode = st.radio(
        "🔧 طريقة التحليل",
        ["🤖 Gemini AI (أدق)", "📝 OCR (مجاني)"],
        index=0,
    )
    use_gemini = "Gemini" in analysis_mode

    if use_gemini:
        st.markdown("### 🔑 مفتاح Gemini API")
        api_input = st.text_input(
            "أدخل المفتاح",
            value=st.session_state.api_key,
            type="password",
            key="api_input_field",
        )
        if api_input != st.session_state.api_key:
            st.session_state.api_key = api_input

        if st.session_state.api_key:
            if validate_api_key(st.session_state.api_key):
                st.success("✅ مفتاح صالح")
            else:
                st.error("❌ مفتاح غير صالح")

        if st.button("🔍 اختبار النماذج المتاحة"):
            if validate_api_key(st.session_state.api_key):
                with st.spinner("جارٍ الاختبار..."):
                    try:
                        genai.configure(api_key=st.session_state.api_key.strip())
                        models = list(genai.list_models())
                        gemini_models = [
                            m.name for m in models
                            if "generateContent" in (m.supported_generation_methods or [])
                        ]
                        st.success(f"✅ {len(gemini_models)} نموذج متاح")
                        for m in gemini_models[:5]:
                            st.text(f"• {m.replace('models/', '')}")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:100]}")
            else:
                st.warning("⚠️ أدخل مفتاحاً صالحاً أولاً")

        st.markdown("🔗 [احصل على مفتاح مجاني](https://aistudio.google.com/apikey)")

    # --- تحسين اللغة العربية ---
    st.markdown("---")
    st.markdown("### ✨ تحسين اللغة العربية")
    st.session_state.polish_enabled = st.toggle(
        "🔤 تحسين الملخص لغوياً (Gemini)",
        value=st.session_state.polish_enabled,
        help="يستخدم Gemini كمدقق لغوي لتصحيح الإملاء والنحو في الملخص التنفيذي"
    )
    if st.session_state.polish_enabled:
        st.info("✅ Gemini سيُدقق الملخص لغوياً بعد كل تحليل")

    st.session_state.sahehly_enabled = st.toggle(
        "📝 استخدام API صححلي (اختياري)",
        value=st.session_state.sahehly_enabled,
        help="يتطلب اشتراك خطة الأعمال من sahehly.com"
    )
    if st.session_state.sahehly_enabled:
        sahehly_key_input = st.text_input(
            "مفتاح API صححلي",
            value=st.session_state.sahehly_api_key,
            type="password",
            help="احصل عليه من: sahehly.com/Pricing/AddBusinessRequest"
        )
        if sahehly_key_input != st.session_state.sahehly_api_key:
            st.session_state.sahehly_api_key = sahehly_key_input
        st.markdown("🔗 [الحصول على مفتاح صححلي](https://sahehly.com/Pricing/AddBusinessRequest)")

    # --- الحقول المعروضة ---
    st.markdown("---")
    st.markdown("### 📋 الحقول المعروضة")
    selected_fields = st.multiselect(
        "اختر الحقول",
        list(FIELD_CONFIG.keys()),
        default=list(FIELD_CONFIG.keys()),
        format_func=lambda x: f"{FIELD_CONFIG[x]['icon']} {FIELD_CONFIG[x]['label']}",
    )

    # --- إحصاءات الجلسة ---
    st.markdown("---")
    st.markdown("### 📊 إحصاءات الجلسة")
    st.metric("إجمالي التحليلات", st.session_state.total_analyzed)
    st.metric("ناجح", st.session_state.success_count)
    st.metric("فاشل", st.session_state.fail_count)

    if st.button("🗑️ مسح جميع النتائج"):
        for key in ["results", "url_results", "tweet_data"]:
            st.session_state[key] = [] if key == "results" else None
        for key in ["analysis_done", "url_analysis_done"]:
            st.session_state[key] = False
        for key in ["total_analyzed", "success_count", "fail_count"]:
            st.session_state[key] = 0
        st.rerun()

    # --- القاموس الدلالي ---
    st.markdown("---")
    with st.expander("📖 القاموس الدلالي"):
        for cat, keywords in SEMANTIC_KEYWORDS.items():
            st.markdown(f"**{cat}:** {', '.join(keywords[:4])}...")


# ==================== الواجهة الرئيسية ====================
st.markdown("""
<div class="main-hero">
    <div class="hero-title">🔍 تحليل الصور في نقاط</div>
    <div class="hero-subtitle">تحليل منشورات منصة X بالذكاء الاصطناعي · بسرعة ودقة</div>
</div>
""", unsafe_allow_html=True)

# بطاقات الإحصاء
col1, col2, col3, col4 = st.columns(4)
stats = [
    ("📊", st.session_state.total_analyzed, "إجمالي التحليلات"),
    ("✅", st.session_state.success_count,   "تحليلات ناجحة"),
    ("❌", st.session_state.fail_count,       "تحليلات فاشلة"),
    ("🤖", "Gemini" if use_gemini else "OCR", "طريقة التحليل"),
]
for col, (icon, val, lbl) in zip([col1, col2, col3, col4], stats):
    with col:
        st.markdown(f"""
        <div class="stat-card">
            <div style="font-size:2rem;">{icon}</div>
            <div class="stat-number">{val}</div>
            <div class="stat-label">{lbl}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==================== التبويبات ====================
tab_paste, tab_upload, tab_url, tab_guide = st.tabs([
    "📋 لصق من الحافظة",
    "📤 رفع صور",
    "🔗 رابط X",
    "📖 دليل الاستخدام",
])

# ---- تبويب اللصق ----
with tab_paste:
    st.markdown("### 📋 لصق صورة من الحافظة")
    st.markdown("""
    <div class="paste-zone" id="paste-zone">
        <div style="font-size:3rem;">📋</div>
        <div style="color:#63b3ed; font-size:1.1rem; margin-top:10px;">
            انسخ الصورة (Ctrl+C) ثم اضغط Ctrl+V في منطقة اللصق أدناه
        </div>
        <div style="color:rgba(255,255,255,0.5); font-size:0.9rem; margin-top:5px;">
            PNG · JPG · WebP · BMP
        </div>
    </div>
    """, unsafe_allow_html=True)

    paste_file = st.file_uploader(
        "أو ارفع الصورة مباشرة",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        key="paste_uploader",
        label_visibility="collapsed",
    )

    if paste_file:
        image = Image.open(paste_file)
        st.image(image, caption="الصورة المُختارة", use_column_width=True)

        if st.button("🚀 تحليل الصورة", key="analyze_paste"):
            with st.spinner("⏳ جارٍ التحليل..."):
                result, err = analyze_image_full(image, st.session_state.api_key, use_gemini)
                if result:
                    st.session_state.success_count += 1
                    st.session_state.total_analyzed += 1
                    st.success(f"✅ تم التحليل بنجاح")
                    render_all_results(result, selected_fields, image)
                    download_buttons(result)
                else:
                    st.session_state.fail_count += 1
                    st.session_state.total_analyzed += 1
                    st.error(f"❌ {err}")


# ---- تبويب رفع الصور ----
with tab_upload:
    st.markdown("### 📤 رفع صور للتحليل")
    uploaded_files = st.file_uploader(
        "اسحب الصور هنا أو انقر للاختيار",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
        key="batch_uploader",
    )

    if uploaded_files:
        st.info(f"📁 تم اختيار {len(uploaded_files)} صورة")
        cols = st.columns(min(len(uploaded_files), 4))
        images = []
        for i, f in enumerate(uploaded_files):
            img = Image.open(f)
            images.append(img)
            with cols[i % 4]:
                st.image(img, caption=f.name, use_column_width=True)

        if st.button("🚀 تحليل الكل", key="analyze_batch"):
            progress = st.progress(0)
            batch_results = []
            for i, img in enumerate(images):
                with st.spinner(f"⏳ تحليل {i+1}/{len(images)}..."):
                    result, err = analyze_image_full(img, st.session_state.api_key, use_gemini)
                    if result:
                        batch_results.append(result)
                        st.session_state.success_count += 1
                    else:
                        st.session_state.fail_count += 1
                    st.session_state.total_analyzed += 1
                    progress.progress((i + 1) / len(images))

            st.session_state.results = batch_results
            st.session_state.analysis_done = True
            st.rerun()

    if st.session_state.analysis_done and st.session_state.results:
        st.markdown(f"### 📊 نتائج التحليل ({len(st.session_state.results)} صورة)")
        for i, result in enumerate(st.session_state.results):
            with st.expander(f"📸 الصورة {i+1} — {result.get('معرف_المنشور', 'غير مُحدد')}"):
                render_all_results(result, selected_fields)
                download_buttons(result)


# ---- تبويب رابط X ----
with tab_url:
    st.markdown("### 🔗 تحليل منشور من رابط X")
    tweet_url = st.text_input(
        "أدخل رابط المنشور",
        placeholder="https://x.com/username/status/...",
        key="tweet_url_input",
    )

    col_fetch, col_analyze = st.columns(2)

    with col_fetch:
        if st.button("📥 جلب المنشور فقط", key="fetch_only"):
            if tweet_url and ("x.com" in tweet_url or "twitter.com" in tweet_url):
                with st.spinner("⏳ جارٍ الجلب..."):
                    tweet_data = fetch_tweet_content(tweet_url)
                    st.session_state.tweet_data = tweet_data
                if tweet_data.get("text"):
                    st.success("✅ تم جلب المنشور")
                else:
                    st.warning("⚠️ لم يتم استخراج نص — قد يكون المنشور خاصاً")
            else:
                st.warning("⚠️ الرجاء إدخال رابط X/Twitter صحيح")

    with col_analyze:
        if st.button("🚀 جلب وتحليل", key="fetch_analyze"):
            if tweet_url and ("x.com" in tweet_url or "twitter.com" in tweet_url):
                with st.spinner("⏳ جارٍ الجلب والتحليل..."):
                    tweet_data = fetch_tweet_content(tweet_url)
                    st.session_state.tweet_data = tweet_data

                    result, method, model_name = None, "غير محدد", ""
                    tweet_text = tweet_data.get("text", "").strip()

                    # 1️⃣ Gemini على النص
                    if tweet_text and use_gemini and validate_api_key(st.session_state.api_key):
                        result, err, model_name = analyze_text_with_gemini(
                            tweet_text, st.session_state.api_key
                        )
                        if result:
                            method = "Gemini (نص)"

                    # 2️⃣ Gemini على الصورة
                    if not result and tweet_data.get("screenshot") and use_gemini and validate_api_key(st.session_state.api_key):
                        result, err, model_name = analyze_with_gemini(
                            tweet_data["screenshot"], st.session_state.api_key
                        )
                        if result:
                            method = "Gemini (صورة)"

                    # 3️⃣ تحليل ذكي احتياطي
                    if not result:
                        fallback_text = tweet_text if tweet_text else "لا يوجد نص متاح"
                        result = analyze_post_smart(fallback_text)
                        method = "تحليل ذكي"

                    # 4️⃣ OCR احتياطي
                    if not result and tweet_data.get("screenshot"):
                        ocr_text = extract_text_ocr(tweet_data["screenshot"])
                        result = analyze_post_smart(ocr_text)
                        method = "OCR"

                    if result:
                        result["_model"] = model_name or method
                        result["_method"] = method
                        st.session_state.url_results = result
                        st.session_state.url_analysis_done = True
                        st.session_state.analysis_method = method
                        st.session_state.used_model = model_name
                        st.session_state.total_analyzed += 1
                        st.session_state.success_count += 1
                    else:
                        st.session_state.fail_count += 1
                        st.session_state.total_analyzed += 1
                st.rerun()
            else:
                st.warning("⚠️ الرجاء إدخال رابط X/Twitter صحيح")

    # عرض بيانات المنشور المجلوب
    if st.session_state.tweet_data:
        td = st.session_state.tweet_data
        with st.expander("📄 بيانات المنشور المجلوب", expanded=True):
            if td.get("text"):
                st.markdown(f"**النص:** {td['text'][:500]}")
            if td.get("author"):
                st.markdown(f"**الكاتب:** {td['author']}")
            if td.get("error"):
                st.error(f"خطأ: {td['error']}")

    # عرض النتائج
    if st.session_state.url_analysis_done and st.session_state.url_results:
        st.markdown("---")
        render_all_results(st.session_state.url_results, selected_fields)
        download_buttons(st.session_state.url_results)


# ---- تبويب الدليل ----
with tab_guide:
    st.markdown("""
### 📖 دليل الاستخدام السريع

#### 🤖 وضع Gemini AI (الأفضل)
1. احصل على مفتاح مجاني من [Google AI Studio](https://aistudio.google.com/apikey)
2. أدخله في الشريط الجانبي
3. اختر التبويب المناسب وابدأ التحليل

#### 📝 وضع OCR (بدون مفتاح)
- يعمل مباشرة بدون أي إعداد
- دقة أقل في النصوص المعقدة

#### ✨ تحسين اللغة العربية
- **Gemini مدقق لغوي**: مجاني ويصحح الإملاء والنحو تلقائياً
- **صححلي API**: دقة أعلى، يتطلب اشتراك أعمال من [sahehly.com](https://sahehly.com)

#### 📋 التبويبات
| التبويب | الاستخدام |
|---------|-----------|
| 📋 لصق | انسخ صورة وألصقها |
| 📤 رفع | ارفع ملف صورة |
| 🔗 رابط X | حلّل منشوراً من رابطه |

#### 💡 نصائح
- الصور عالية الدقة تعطي نتائج أفضل
- فعّل "تحسين الملخص لغوياً" للحصول على نص أكثر احترافية
- يمكن تحليل حتى 20 صورة دفعة واحدة
    """)


# ==================== الفوتر ====================
st.markdown("""
<div class="footer">
    📸 تحليل الصور في نقاط — الإصدار 5.0<br>
    ✨ مع تحسين اللغة العربية بالذكاء الاصطناعي<br>
    🔗 <a href="https://aistudio.google.com/apikey" style="color:#63b3ed;">احصل على مفتاح Gemini مجاناً</a>
    &nbsp;|&nbsp;
    🔗 <a href="https://sahehly.com" style="color:#63b3ed;">صححلي للتدقيق اللغوي</a>
</div>
""", unsafe_allow_html=True)
```

---

## requirements.txt

```
streamlit
Pillow
numpy
opencv-python-headless
pytesseract
google-generativeai
requests
beautifulsoup4
```

---

## packages.txt

```
tesseract-ocr
tesseract-ocr-ara
tesseract-ocr-eng
```

---

## .streamlit/config.toml

```toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
```
