# -*- coding: utf-8 -*-
"""تحليل الصور في نقاط - النسخة 4.1 (لصق من الحافظة + صور متعددة + رابط X)"""

import streamlit as st

# ========== فحص المكتبات ==========
missing_libs = []
try:
    import pytesseract
except ImportError:
    missing_libs.append("pytesseract")
try:
    import cv2
except ImportError:
    missing_libs.append("opencv-python-headless")
try:
    import numpy as np
except ImportError:
    missing_libs.append("numpy")
try:
    import google.generativeai as genai
except ImportError:
    missing_libs.append("google-generativeai")
try:
    from PIL import Image
except ImportError:
    missing_libs.append("Pillow")
try:
    import requests
except ImportError:
    missing_libs.append("requests")
try:
    from bs4 import BeautifulSoup
except ImportError:
    missing_libs.append("beautifulsoup4")
try:
    from streamlit_paste_button import paste_image_button as pbutton
    PASTE_AVAILABLE = True
except ImportError:
    PASTE_AVAILABLE = False
    missing_libs.append("streamlit-paste-button")

if missing_libs:
    st.warning(f"⚠️ مكتبات مفقودة: {', '.join(missing_libs)}")
    st.code("\n".join(missing_libs), language="text")
    st.info("أضف المكتبات في ملف requirements.txt ثم أعد النشر")
    # لا نوقف التطبيق - نكمل بالمكتبات المتاحة

import json, re, time
from io import BytesIO
import base64

# ========== إعداد الصفحة ==========
st.set_page_config(
    page_title="تحليل الصور في نقاط",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== قاموس الكلمات الدلالية ==========
SEMANTIC_KEYWORDS = {
    "عام": ["قرارات","قيادة المرأة","السعودية","الولاء","الانتماء","الأمن","الاستقرار","التنمية","الرؤية","2030"],
    "المتطرفون": ["العودة","العريفي","السويدان","الحبيب","الخلف","الحجوري","الخارج","الخوارج","الخارجية","الخارجون"],
    "سياسية": ["قطر","ترمب","إيران","تركيا","أمريكا","روسيا","الصين","فلسطين","غزة","الحرب","السلام"],
    "الترفيه": ["الرياض","فعالية","موسم","ترفيه","سياحة","الدرعية","العلا","كأس","مباراة","نادي"],
    "التجنيس": ["التجنيس","السعودة","الوظائف","العمالة","الأجانب","الجنسية","الإقامة","الاستثمار"],
    "تهكم_وسخرية": ["🤣","😂","😆","مضحك","مهزلة","سخرية","ساخر","استهزاء","تهكم","نكتة","فشل","فاشل","كارثة","فضيحة","كذب","مسرحية","كوميديا"]
}

def detect_category(text):
    if not text: return {}
    found = {}
    for cat, kws in SEMANTIC_KEYWORDS.items():
        f = [k for k in kws if k in text]
        if f: found[cat] = f
    return found

def is_sarcastic_text(text):
    if not text: return False, 0, []
    kws = SEMANTIC_KEYWORDS.get("تهكم_وسخرية", [])
    found = [k for k in kws if k in text]
    return len(found) > 0, len(found), found

def get_topic_from_text(text):
    if not text: return "غير محدد"
    topics = {
        "الخروج على ولي الأمر": ["الخروج","ولي الأمر","الحاكم","الحكومة"],
        "التجنيس": ["تجنيس","سعودة","أجانب","جنسية"],
        "السياسة": ["قطر","ترمب","إيران","فلسطين","غزة"],
        "الترفيه": ["ترفيه","سياحة","موسم","فعالية"],
        "المتطرفون": ["العودة","العريفي","الخارج","الخوارج"]
    }
    for topic, kws in topics.items():
        for kw in kws:
            if kw in text: return topic
    return "عام"

# ========== CSS ==========
st.markdown("""
<style>
    .main,.block-container,.stApp{direction:rtl!important;text-align:right!important;}

    /* بطاقات النتائج */
    .result-card{background:#1e1e2e;border-right:4px solid #4CAF50;border-radius:12px;
        padding:15px;margin:10px 0;color:white;box-shadow:0 4px 6px rgba(0,0,0,0.1);}
    .result-card.missing{border-right-color:#f44336;}
    .result-card.summary{border-right-color:#2196F3;min-height:100px;}
    .result-card.x-account{border-right-color:#000;}
    .card-label{font-size:13px;color:#aaa;margin-bottom:5px;}
    .card-value{font-size:15px;font-weight:bold;color:white;}

    /* البانرات */
    .success-banner{background:linear-gradient(135deg,#4CAF50,#45a049);color:white;
        padding:15px;border-radius:12px;margin:10px 0;direction:rtl;}
    .batch-header{background:linear-gradient(135deg,#0f3460,#16213e);color:white;
        padding:12px 15px;border-radius:10px;margin:10px 0;direction:rtl;}

    /* منطقة لصق الصورة */
    .paste-zone{
        background:#1a1a2e;
        border:3px dashed #4CAF50;
        border-radius:15px;
        padding:40px 20px;
        text-align:center;
        cursor:pointer;
        transition:all 0.3s;
        margin:10px 0;
        direction:rtl;
    }
    .paste-zone:hover{
        background:#16213e;
        border-color:#45a049;
        transform:scale(1.01);
    }
    .paste-zone.active{
        border-color:#2196F3;
        background:#0d1b2a;
    }
    .paste-icon{font-size:50px;margin-bottom:10px;}
    .paste-title{color:#4CAF50;font-size:20px;font-weight:bold;margin:10px 0;}
    .paste-subtitle{color:#888;font-size:14px;}
    .paste-hint{
        background:#333;
        color:#aaa;
        padding:8px 15px;
        border-radius:20px;
        font-size:13px;
        display:inline-block;
        margin-top:10px;
    }

    /* منشور X */
    .tweet-card{background:#15202b;border:2px solid #1DA1F2;border-radius:15px;
        padding:20px;margin:10px 0;color:white;direction:rtl;}
    .tweet-author{color:#1DA1F2;font-weight:bold;font-size:18px;margin-bottom:8px;}
    .tweet-text{font-size:15px;line-height:1.8;margin:10px 0;color:#e7e9ea;}
    .tweet-meta{color:#8899a6;font-size:13px;margin-top:10px;}

    /* رابط X */
    .x-link{display:inline-flex;align-items:center;gap:8px;background:#000;
        color:white!important;padding:8px 15px;border-radius:20px;
        text-decoration:none!important;font-weight:bold;transition:all 0.3s;}
    .x-link:hover{background:#333;transform:scale(1.05);}
    .x-icon{width:18px;height:18px;fill:white;vertical-align:middle;}

    /* تاغات */
    .category-tag{display:inline-block;background:#333;color:#fff;
        padding:4px 12px;border-radius:15px;margin:2px;font-size:12px;}
    .category-tag.sarcastic{background:#ff9800;}
    .category-tag.political{background:#2196F3;}
    .category-tag.general{background:#4CAF50;}
    .model-badge{display:inline-block;background:#6200ea;color:white;
        padding:3px 10px;border-radius:10px;font-size:12px;}
    .image-counter{background:#333;color:#fff;padding:3px 10px;
        border-radius:10px;font-size:13px;display:inline-block;margin:3px;}

    /* URL box */
    .url-box{background:#15202b;border:2px solid #1DA1F2;border-radius:12px;
        padding:20px;margin:10px 0;}

    /* صورة ملصقة */
    .pasted-image-container{
        background:#1e1e2e;
        border:2px solid #4CAF50;
        border-radius:12px;
        padding:15px;
        margin:10px 0;
        text-align:center;
    }
    .pasted-label{color:#4CAF50;font-size:14px;font-weight:bold;margin-bottom:10px;}

    /* تبويبات */
    div[data-testid="stTabs"] button{font-size:15px;}

    /* زر الصق */
    .stButton > button {
        direction: rtl !important;
    }
</style>
""", unsafe_allow_html=True)

# ========== Session State ==========
def get_default_api_key():
    try: return st.secrets.get("GEMINI_API_KEY","")
    except: return ""

defaults = {
    "api_key": get_default_api_key(),
    "analysis_done": False,
    "results": None,
    "batch_results": [],
    "extracted_text": "",
    "analysis_method": "",
    "used_model": "",
    "tweet_data": None,
    "total_analyzed": 0,
    "url_analysis_done": False,
    "url_results": None,
    "pasted_image": None,          # ← الصورة الملصقة من الحافظة
    "paste_analysis_done": False,  # ← هل تم تحليل الصورة الملصقة
    "paste_results": None          # ← نتائج الصورة الملصقة
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ========== وظيفة رابط X ==========
def make_x_link(username):
    if not username or username in ["غير مُحدد","غير محدد","None",""]:
        return "غير مُحدد"
    clean = username.replace("@","").strip()
    svg = '<svg class="x-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
    return f'<a href="https://x.com/{clean}" target="_blank" class="x-link">{svg} @{clean}</a>'

# ========== وظائف مساعدة ==========
def validate_api_key(key):
    key = key.strip()
    if not key: return False, "⚠️ المفتاح فارغ"
    if not key.startswith("AIza"): return False, "⚠️ يجب أن يبدأ بـ AIza..."
    if len(key) < 30: return False, "⚠️ المفتاح قصير جداً"
    return True, "✅ صيغة المفتاح صحيحة"

def preprocess_image_ocr(image):
    try:
        img = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
        return Image.fromarray(cv2.filter2D(thresh,-1,kernel))
    except: return image

def extract_text_ocr(image):
    try:
        arr = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        ar_text = pytesseract.image_to_string(
            gray, lang='ara+eng',
            config='--oem 3 --psm 6 -c preserve_interword_spaces=1'
        )
        en_text = pytesseract.image_to_string(gray, lang='eng', config='--oem 3 --psm 6')
        mentions = re.findall(r'@[A-Za-z0-9_]+', en_text)
        cleaned = re.sub(r'[^\u0600-\u06FF\s\d@#_.,;:!؟\-\u200c\u200d\u064b-\u065f]',' ',ar_text)
        return re.sub(r'\s+',' ',cleaned).strip(), mentions
    except Exception as e:
        return f"خطأ OCR: {str(e)}", []

def generate_executive_summary(res, txt=""):
    pid  = res.get("معرف_المنشور","غير مُحدد")
    cid  = res.get("معرف_التعليق","غير مُحدد")
    inv  = res.get("المدعو","غير مُحدد")
    cont = res.get("محتوى_المنشور","غير مُحدد")
    clip = res.get("المقطع","غير مُحدد")
    comm = res.get("التعليق","غير مُحدد")
    opin = res.get("الرأي","غير مُحدد")
    full = " ".join([txt, str(comm), str(cont)])
    sarc,_,_ = is_sarcastic_text(full)
    topic = get_topic_from_text(full)
    def s(t, n=120): return (str(t)[:n]+"...") if len(str(t))>n else str(t)
    parts = []
    if pid != "غير مُحدد":
        parts.append(f"نشر صاحب المعرف {pid} منشوراً يتضمن {s(cont)}"
                     if cont != "غير مُحدد"
                     else f"نشر صاحب المعرف {pid} منشوراً")
    if inv  != "غير مُحدد": parts.append(f"مقتبساً من المدعو {inv}")
    if clip != "غير مُحدد": parts.append(f"مرفقاً مقطع فيديو يظهر فيه {s(clip)}")
    if cid  != "غير مُحدد":
        parts.append(f"حيث علّق صاحب المعرف {cid} بأن {s(comm)}"
                     if comm != "غير مُحدد"
                     else f"حيث علّق صاحب المعرف {cid}")
    if opin != "غير مُحدد": parts.append(f"مستنتجاً أن {s(opin)}")
    if sarc: parts.append(f"في إشارة تنطوي على تهكم بشأن {topic}")
    return ("، ".join(parts)+".") if parts else "غير مُحدد - لم يتم استخراج معلومات كافية"

def analyze_post_smart(text, mentions):
    res = {k:"غير مُحدد" for k in
           ["معرف_المنشور","معرف_التعليق","المدعو","محتوى_المنشور",
            "المقطع","التعليق","الرأي","الملخص_التنفيذي"]}
    if mentions:
        res["معرف_المنشور"] = mentions[0]
        if len(mentions) > 1: res["معرف_التعليق"] = mentions[1]
    def fm(pats, t):
        for p in pats:
            m = re.search(p, t)
            if m: return m.group(1).strip()
        return "غير مُحدد"
    res["المدعو"]         = fm([r'المدعو\s+([@\w\s]+)',r'الشيخ\s+([@\w\s]+)'], text)
    res["محتوى_المنشور"] = fm([r'محتوى[:\s]+([^\n]+)',r'يتضمن[:\s]+([^\n]+)'], text)
    res["المقطع"]         = fm([r'مقطع[:\s]+([^\n]+)',r'فيديو[:\s]+([^\n]+)'], text)
    res["التعليق"]        = fm([r'التعليق[:\s]+([^\n]+)',r'علق[:\s]+([^\n]+)'], text)
    res["الرأي"]          = fm([r'الرأي[:\s]+([^\n]+)',r'استنتج[:\s]+([^\n]+)'], text)
    res["الملخص_التنفيذي"] = generate_executive_summary(res, text)
    return res

# ========== جلب منشور X ==========
def fetch_tweet_content(tweet_url):
    result = {
        "text": "", "author": "", "author_username": "",
        "screenshot_url": None, "success": False,
        "method": "", "url": tweet_url
    }
    m = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)', tweet_url)
    if m:
        result["author_username"] = m.group(1)
    else:
        return result

    # oEmbed API
    try:
        oembed_url = f"https://publish.twitter.com/oembed?url={tweet_url}&omit_script=true&lang=ar"
        resp = requests.get(oembed_url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        if resp.ok:
            data = resp.json()
            html_content = data.get("html","")
            soup = BeautifulSoup(html_content, "html.parser")
            for tag in soup.find_all(["script","style"]): tag.decompose()
            text = re.sub(r'\s+',' ', soup.get_text(separator=" ").strip())
            result["text"]    = text
            result["author"]  = data.get("author_name","")
            result["success"] = True
            result["method"]  = "oEmbed"
    except Exception as e:
        result["method"] = f"فشل oEmbed: {str(e)[:50]}"

    # Screenshot via microlink
    try:
        micro = f"https://api.microlink.io/?url={tweet_url}&screenshot=true&meta=false&embed=screenshot.url"
        r2 = requests.get(micro, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        if r2.ok:
            scr = r2.json().get("data",{}).get("screenshot",{}).get("url")
            if scr: result["screenshot_url"] = scr
    except: pass

    if not result["screenshot_url"]:
        result["screenshot_url"] = f"https://image.thum.io/get/width/800/crop/600/noanimate/{tweet_url}"

    return result

# ========== Gemini ==========
GEMINI_PROMPT = """
أنت محلل متخصص في تحليل منشورات تويتر/اكس (X).
حلل الصورة المرفقة واستخرج المعلومات بدقة. أعد JSON فقط بدون markdown:
{
    "معرف_المنشور": "@username صاحب المنشور",
    "معرف_التعليق": "@username صاحب التعليق إن وجد",
    "المدعو": "الشخص المدعو أو المقتبس منه",
    "محتوى_المنشور": "نص المنشور الأصلي كاملاً",
    "المقطع": "وصف الفيديو أو المقطع إن وجد",
    "التعليق": "نص التعليق",
    "الرأي": "الرأي أو الاستنتاج",
    "الملخص_التنفيذي": "ملخص تنفيذي كامل جملة واحدة لا تقل عن 80 كلمة"
}
قواعد: JSON فقط - غير مُحدد للغائب - الملخص لا يقل عن 80 كلمة.
مثال الملخص: نشر صاحب المعرف @X منشوراً يتضمن [المحتوى]، مقتبساً من [المدعو]، حيث علّق @Y بأن [التعليق]، مستنتجاً أن [الرأي]، في إشارة تنطوي على تهكم بشأن [الموضوع].
"""

GEMINI_TEXT_PROMPT = """
أنت محلل متخصص في تحليل منشورات تويتر/اكس (X).
حلل النص التالي واستخرج المعلومات. أعد JSON فقط:

النص: {text}

{{
    "معرف_المنشور": "@username صاحب المنشور",
    "معرف_التعليق": "@username صاحب التعليق إن وجد",
    "المدعو": "الشخص المدعو أو المقتبس منه",
    "محتوى_المنشور": "نص المنشور الأصلي",
    "المقطع": "وصف الفيديو إن وجد",
    "التعليق": "نص التعليق",
    "الرأي": "الرأي أو الاستنتاج",
    "الملخص_التنفيذي": "ملخص تنفيذي لا يقل عن 80 كلمة"
}}
قواعد: JSON فقط - غير مُحدد للغائب.
"""

def parse_gemini_json(raw):
    cleaned = re.sub(r'^```(json)?\s*','',raw.strip())
    cleaned = re.sub(r'\s*```$','',cleaned).strip()
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        result = json.loads(match.group())
        for f in ["معرف_المنشور","معرف_التعليق","المدعو","محتوى_المنشور",
                  "المقطع","التعليق","الرأي","الملخص_التنفيذي"]:
            if f not in result: result[f] = "غير مُحدد"
        return result
    return None

def run_gemini(input_data, api_key, is_image=True):
    """تشغيل Gemini على صورة أو نص مع Fallback"""
    try:
        genai.configure(api_key=api_key.strip())
        models_to_try = [
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
        ]
        last_error = ""
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                if is_image:
                    response = model.generate_content([GEMINI_PROMPT, input_data])
                else:
                    prompt = GEMINI_TEXT_PROMPT.format(text=input_data)
                    response = model.generate_content(prompt)
                result = parse_gemini_json(response.text)
                if result:
                    return result, None, model_name
                last_error = f"{model_name}: لم يُرجع JSON"
                continue
            except Exception as e:
                err = str(e)
                if any(x in err for x in ["QUOTA_EXCEEDED","429","quota","ResourceExhausted"]):
                    last_error = f"⚠️ {model_name}: تجاوز الحصة"
                    time.sleep(2); continue
                elif any(x in err for x in ["404","not found","NOT_FOUND"]):
                    last_error = f"⚠️ {model_name}: غير متاح"; continue
                elif "API_KEY_INVALID" in err:
                    return None, "❌ مفتاح API غير صالح", ""
                elif "PERMISSION_DENIED" in err:
                    return None, "❌ لا توجد صلاحية", ""
                else:
                    last_error = f"❌ {model_name}: {err[:80]}"; continue
        return None, f"❌ فشلت جميع النماذج\n{last_error}", ""
    except Exception as e:
        return None, f"❌ خطأ: {str(e)}", ""

# ========== إعدادات الحقول ==========
FIELD_CONFIG = {
    "معرف_المنشور":   {"icon":"👤","label":"معرف المنشور",    "is_username":True},
    "معرف_التعليق":   {"icon":"💬","label":"معرف التعليق",    "is_username":True},
    "المدعو":          {"icon":"🎯","label":"المدعو / المقتبس"},
    "محتوى_المنشور":  {"icon":"📝","label":"محتوى المنشور"},
    "المقطع":          {"icon":"🎬","label":"المقطع / الفيديو"},
    "التعليق":         {"icon":"💭","label":"التعليق"},
    "الرأي":           {"icon":"🧠","label":"الرأي / التحليل"},
    "الملخص_التنفيذي": {"icon":"📋","label":"الملخص التنفيذي","is_summary":True}
}

def render_result_card(field_key, value):
    config     = FIELD_CONFIG.get(field_key, {"icon":"📄","label":field_key})
    is_missing = value in ["غير مُحدد","غير محدد","",None,"None"]
    card_class = "missing" if is_missing else ("summary" if config.get("is_summary") else "")
    if config.get("is_username") and not is_missing:
        st.markdown(f"""
        <div class="result-card x-account">
            <div class="card-label">{config['icon']} {config['label']}</div>
            <div class="card-value">{make_x_link(value)}</div>
        </div>""", unsafe_allow_html=True)
    else:
        display = value if not is_missing else "⚠️ غير مُحدد"
        st.markdown(f"""
        <div class="result-card {card_class}">
            <div class="card-label">{config['icon']} {config['label']}</div>
            <div class="card-value">{display}</div>
        </div>""", unsafe_allow_html=True)

def render_all_results(results, selected_fields):
    filled = sum(1 for v in results.values() if v not in ["غير مُحدد","غير محدد","",None])
    total  = len(results)
    pct    = int(filled/total*100)
    st.markdown(f"""
    <div class="success-banner">
        <h4>✅ تم التحليل بنجاح — {filled}/{total} حقول ({pct}%)</h4>
    </div>""", unsafe_allow_html=True)
    st.progress(pct/100)
    for field in selected_fields:
        if field in results:
            render_result_card(field, results[field])

def download_buttons(results, prefix=""):
    c1, c2 = st.columns(2)
    with c1:
        txt = "\n".join([f"{k}: {v}" for k,v in results.items()])
        st.download_button("📄 TXT", data=txt.encode('utf-8'),
                           file_name=f"{prefix}result.txt",
                           mime="text/plain", use_container_width=True)
    with c2:
        js = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button("📋 JSON", data=js.encode('utf-8'),
                           file_name=f"{prefix}result.json",
                           mime="application/json", use_container_width=True)

def analyze_image_full(image, api_key, use_gemini):
    """تحليل صورة بـ Gemini أو OCR"""
    results = None
    method  = ""
    model   = ""
    if use_gemini:
        results, error, model = run_gemini(image, api_key, is_image=True)
        if error:
            st.warning(f"⚠️ {error[:80]} → OCR")
            results = None
        else:
            method = "Gemini AI ✨"
    if results is None:
        proc = preprocess_image_ocr(image)
        text, mentions = extract_text_ocr(proc)
        results = analyze_post_smart(text, mentions)
        method  = "OCR 🔤"
        model   = "Tesseract"
    return results, method, model

# ============================================================
#                      الشريط الجانبي
# ============================================================
with st.sidebar:
    st.title("⚙️ الإعدادات")

    analysis_mode = st.radio(
        "طريقة التحليل:",
        ["🔤 OCR تقليدي (مجاني)", "🤖 Gemini AI (أدق ✨)"],
        index=1
    )

    if "Gemini" in analysis_mode:
        st.markdown("---")
        st.subheader("🔐 مفتاح Gemini API")
        new_key = st.text_input(
            "أدخل مفتاح Gemini API:",
            value=st.session_state.api_key,
            type="password", key="_api_key_input"
        )
        if new_key: st.session_state.api_key = new_key

        if st.session_state.api_key:
            ok, msg = validate_api_key(st.session_state.api_key)
            st.markdown(f"<p style='color:{'green' if ok else 'red'}'>{msg}</p>",
                        unsafe_allow_html=True)
            if st.button("🔍 اختبر المفتاح", use_container_width=True):
                with st.spinner("جاري الاختبار..."):
                    try:
                        genai.configure(api_key=st.session_state.api_key.strip())
                        models = genai.list_models()
                        avail  = [m.name.replace("models/","") for m in models
                                  if "generateContent" in m.supported_generation_methods]
                        st.success(f"✅ يعمل! ({len(avail)} نموذج متاح)")
                        for mn in avail[:6]: st.code(mn, language="text")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:100]}")
        else:
            st.caption("💡 https://aistudio.google.com/apikey")

    st.markdown("---")
    st.subheader("👁️ الحقول المعروضة")
    all_fields      = list(FIELD_CONFIG.keys())
    selected_fields = st.multiselect("اختر الحقول:", all_fields, default=all_fields)

    st.markdown("---")
    st.subheader("📊 إحصائيات")
    st.metric("الصور المحللة", st.session_state.total_analyzed)
    if st.session_state.used_model:
        st.markdown(f'<span class="model-badge">🤖 {st.session_state.used_model}</span>',
                    unsafe_allow_html=True)

    has_results = (st.session_state.analysis_done or
                   st.session_state.url_analysis_done or
                   st.session_state.paste_analysis_done)
    if has_results:
        if st.button("🗑️ مسح النتائج", use_container_width=True):
            for k in ["analysis_done","results","batch_results","extracted_text",
                      "analysis_method","used_model","url_analysis_done","url_results",
                      "tweet_data","total_analyzed","pasted_image",
                      "paste_analysis_done","paste_results"]:
                st.session_state[k] = (
                    False if k in ["analysis_done","url_analysis_done","paste_analysis_done"]
                    else None if k in ["results","url_results","tweet_data","pasted_image","paste_results"]
                    else [] if k == "batch_results"
                    else 0  if k == "total_analyzed"
                    else ""
                )
            st.rerun()

    with st.expander("📚 القاموس الدلالي"):
        for cat, kws in SEMANTIC_KEYWORDS.items():
            st.markdown(f"**{cat}:** {', '.join(kws[:4])}...")

# ============================================================
#                      الواجهة الرئيسية
# ============================================================
st.title("📸 تحليل الصور في نقاط")
st.markdown("---")

use_gemini = "Gemini" in analysis_mode and bool(st.session_state.api_key)

# التبويبات الأربعة
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 لصق من الحافظة",
    "🖼️ رفع صورة (مفردة/متعددة)",
    "🔗 رابط منشور X",
    "📖 دليل الاستخدام"
])

# ============================================================
#  التبويب 1: لصق من الحافظة  ← الجديد
# ============================================================
with tab1:
    st.markdown("### 📋 الصق صورة مباشرة من الحافظة")
    st.caption("خذ لقطة شاشة (Ctrl+PrtSc أو Snipping Tool) ثم الصقها هنا بـ Ctrl+V")

    if PASTE_AVAILABLE:
        # ===== استخدام مكتبة streamlit-paste-button =====
        st.markdown("""
        <div class="paste-zone">
            <div class="paste-icon">📋</div>
            <div class="paste-title">اضغط الزر أدناه ثم الصق بـ Ctrl+V</div>
            <div class="paste-subtitle">يدعم: PNG, JPG, WEBP من الحافظة</div>
            <div class="paste-hint">💡 خذ Screenshot ثم Ctrl+V</div>
        </div>
        """, unsafe_allow_html=True)

        paste_result = pbutton(
            label="📋 انقر ثم الصق الصورة (Ctrl+V)",
            background_color="#1e1e2e",
            hover_background_color="#2d2d3e",
            text_color="#ffffff",
            errors="raise"
        )

        if paste_result.image_data is not None:
            pasted_img = paste_result.image_data
            st.session_state.pasted_image = pasted_img

            st.markdown('<div class="pasted-image-container">'
                        '<div class="pasted-label">✅ تم إدراج الصورة بنجاح!</div>'
                        '</div>', unsafe_allow_html=True)
            st.image(pasted_img, caption="الصورة الملصقة", use_container_width=True)
            st.caption(f"📐 {pasted_img.size[0]}×{pasted_img.size[1]} بكسل")

    else:
        # ===== بديل: مكون HTML مخصص لالتقاط Paste =====
        st.warning("⚠️ مكتبة streamlit-paste-button غير مثبتة — استخدام البديل المدمج")

        # مكون HTML مخصص للصق
        paste_html = """
        <div id="paste-area" style="
            background:#1a1a2e;
            border:3px dashed #4CAF50;
            border-radius:15px;
            padding:50px 20px;
            text-align:center;
            cursor:pointer;
            transition:all 0.3s;
            margin:10px 0;
            font-family:Arial,sans-serif;
        " tabindex="0">
            <div style="font-size:50px;margin-bottom:10px;">📋</div>
            <div style="color:#4CAF50;font-size:20px;font-weight:bold;margin:10px 0;direction:rtl;">
                انقر هنا ثم اضغط Ctrl+V لإدراج الصورة
            </div>
            <div style="color:#888;font-size:14px;direction:rtl;">
                يدعم الصور من الحافظة مباشرة
            </div>
        </div>
        <canvas id="canvas" style="display:none;"></canvas>
        <div id="preview" style="margin-top:10px;text-align:center;"></div>
        <div id="status" style="color:#4CAF50;text-align:center;margin-top:10px;direction:rtl;"></div>

        <script>
        const pasteArea = document.getElementById('paste-area');
        const canvas    = document.getElementById('canvas');
        const ctx       = canvas.getContext('2d');
        const preview   = document.getElementById('preview');
        const status    = document.getElementById('status');

        // تفعيل منطقة اللصق عند النقر عليها
        pasteArea.addEventListener('click', function() {
            pasteArea.focus();
            pasteArea.style.borderColor = '#2196F3';
            pasteArea.style.background  = '#0d1b2a';
            status.textContent = '✅ جاهز للصق — اضغط Ctrl+V الآن';
            status.style.color = '#2196F3';
        });

        // الاستماع لحدث اللصق في كامل الصفحة
        window.addEventListener('paste', function(e) {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            for (let item of items) {
                if (item.type.indexOf('image') !== -1) {
                    const blob = item.getAsFile();
                    const img  = new Image();
                    const url  = URL.createObjectURL(blob);
                    img.onload = function() {
                        canvas.width  = img.width;
                        canvas.height = img.height;
                        ctx.drawImage(img, 0, 0);
                        const dataURL = canvas.toDataURL('image/png');

                        // عرض المعاينة
                        preview.innerHTML = '<img src="' + dataURL +
                            '" style="max-width:100%;max-height:300px;border-radius:10px;' +
                            'border:2px solid #4CAF50;"/>';

                        pasteArea.style.borderColor = '#4CAF50';
                        status.textContent = '✅ تم إدراج الصورة! اضغط "تحليل" أدناه';
                        status.style.color = '#4CAF50';

                        // إرسال الصورة إلى Streamlit
                        Streamlit.setComponentValue(dataURL);
                        URL.revokeObjectURL(url);
                    };
                    img.src = url;
                    break;
                }
            }
        });

        // تفعيل الاستجابة
        Streamlit.setComponentReady();
        </script>
        """

        import streamlit.components.v1 as components
        paste_data = components.html(paste_html, height=350)

        # معالجة بيانات الصورة من المكون
        if paste_data and isinstance(paste_data, str) and paste_data.startswith("data:image"):
            try:
                header, encoded = paste_data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                pasted_img = Image.open(BytesIO(img_bytes))
                st.session_state.pasted_image = pasted_img
                st.image(pasted_img, caption="✅ الصورة الملصقة", use_container_width=True)
                st.caption(f"📐 {pasted_img.size[0]}×{pasted_img.size[1]} بكسل")
            except Exception as e:
                st.error(f"❌ خطأ في معالجة الصورة: {str(e)}")

    # ===== زر التحليل للصورة الملصقة =====
    if st.session_state.pasted_image is not None:
        st.markdown("---")
        if st.button("🔍 تحليل الصورة الملصقة", use_container_width=True,
                     key="analyze_paste"):
            with st.spinner("⏳ جاري التحليل..."):
                results, method, model = analyze_image_full(
                    st.session_state.pasted_image, st.session_state.api_key, use_gemini
                )
                st.session_state.paste_results      = results
                st.session_state.paste_analysis_done = True
                st.session_state.analysis_method     = method
                st.session_state.used_model          = model
                st.session_state.total_analyzed     += 1
            st.rerun()

    # عرض نتائج الصورة الملصقة
    if st.session_state.paste_analysis_done and st.session_state.paste_results:
        st.markdown("---")
        st.markdown(
            f'<div class="batch-header">✅ {st.session_state.analysis_method} | '
            f'<span class="model-badge">{st.session_state.used_model}</span></div>',
            unsafe_allow_html=True
        )
        render_all_results(st.session_state.paste_results, selected_fields)
        download_buttons(st.session_state.paste_results, prefix="paste_")

# ============================================================
#  التبويب 2: رفع الصور
# ============================================================
with tab2:
    uploaded_files = st.file_uploader(
        "📤 اختر صورة أو أكثر:",
        type=["png","jpg","jpeg","webp"],
        accept_multiple_files=True,
        help="يمكنك رفع عدة صور — الحد الأقصى 200 MB لكل صورة"
    )

    if uploaded_files:
        total_imgs = len(uploaded_files)
        st.markdown(f'<span class="image-counter">📷 {total_imgs} صورة مُرفوعة</span>',
                    unsafe_allow_html=True)

        # معاينة الصور
        cols = st.columns(min(total_imgs, 3))
        for i, f in enumerate(uploaded_files[:6]):
            with cols[i % 3]:
                st.image(Image.open(f), caption=f.name, use_container_width=True)
        if total_imgs > 6:
            st.caption(f"... و {total_imgs-6} صورة إضافية")

        if st.button("🚀 تحليل جميع الصور", use_container_width=True):
            if "Gemini" in analysis_mode and not st.session_state.api_key:
                st.error("❌ أدخل مفتاح Gemini API أولاً")
            else:
                batch_results = []
                prog = st.progress(0)
                stat = st.empty()

                for idx, uf in enumerate(uploaded_files):
                    prog.progress((idx)/total_imgs)
                    stat.markdown(f'<p style="color:#aaa;font-size:13px;">⏳ {idx+1}/{total_imgs}: {uf.name}</p>',
                                  unsafe_allow_html=True)
                    image = Image.open(uf)
                    results, method, model = analyze_image_full(
                        image, st.session_state.api_key, use_gemini
                    )
                    batch_results.append({
                        "file_name": uf.name,
                        "method": method,
                        "model": model,
                        "results": results
                    })
                    if use_gemini and idx < total_imgs-1:
                        time.sleep(1)

                prog.progress(1.0)
                stat.markdown('<p style="color:#4CAF50;">✅ اكتمل التحليل!</p>',
                              unsafe_allow_html=True)
                st.session_state.batch_results  = batch_results
                st.session_state.analysis_done  = True
                st.session_state.total_analyzed = total_imgs
                st.session_state.used_model     = model
                st.rerun()

    # عرض نتائج الدفعة
    if st.session_state.analysis_done and st.session_state.batch_results:
        batch = st.session_state.batch_results
        st.markdown("---")
        st.markdown(f"### 📊 نتائج {len(batch)} صورة")

        all_data = [{"ملف": b["file_name"], "طريقة": b["method"], **b["results"]}
                    for b in batch]
        st.download_button(
            "📦 تنزيل جميع النتائج (JSON)",
            data=json.dumps(all_data, ensure_ascii=False, indent=2).encode('utf-8'),
            file_name="all_results.json",
            mime="application/json",
            use_container_width=True
        )

        for i, b in enumerate(batch):
            icon = "✅" if b["results"].get("معرف_المنشور","غير مُحدد") != "غير مُحدد" else "⚠️"
            with st.expander(f"{icon} {i+1}. {b['file_name']} | {b['method']}", expanded=(i==0)):
                st.markdown(
                    f'<div class="batch-header">📷 {b["file_name"]} | '
                    f'<span class="model-badge">{b["model"]}</span></div>',
                    unsafe_allow_html=True
                )
                render_all_results(b["results"], selected_fields)
                download_buttons(b["results"], prefix=f"img{i+1}_")

# ============================================================
#  التبويب 3: رابط منشور X
# ============================================================
with tab3:
    st.markdown("""
    <div class="url-box">
        <h4 style="color:#1DA1F2;margin:0 0 8px 0;">
            <svg style="width:20px;height:20px;fill:#1DA1F2;vertical-align:middle;margin-left:5px;"
                 viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17
                 l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161
                 17.52h1.833L7.084 4.126H5.117z"/></svg>
            تحليل منشور من رابطه
        </h4>
        <p style="color:#8899a6;font-size:13px;margin:0;">
            أدخل رابط المنشور وسيُجلب ويُحلَّل تلقائياً
        </p>
    </div>
    """, unsafe_allow_html=True)

    tweet_url_input = st.text_input(
        "🔗 رابط منشور X:",
        placeholder="https://x.com/username/status/1234567890"
    )

    url_valid = False
    if tweet_url_input:
        if re.search(r'(?:twitter\.com|x\.com)/[^/]+/status/\d+', tweet_url_input):
            st.success("✅ رابط صحيح")
            url_valid = True
        else:
            st.error("❌ رابط غير صحيح — الصيغة: https://x.com/username/status/ID")

    ca, cb = st.columns(2)
    with ca:
        fetch_btn = st.button("📥 جلب المنشور فقط",
                               disabled=not url_valid, use_container_width=True)
    with cb:
        analyze_url_btn = st.button("🔍 جلب وتحليل مباشرة",
                                    disabled=not url_valid, use_container_width=True)

    if fetch_btn and url_valid:
        with st.spinner("⏳ جاري جلب المنشور..."):
            td = fetch_tweet_content(tweet_url_input)
            st.session_state.tweet_data = td
        if td["success"]:
            st.markdown(f"""
            <div class="tweet-card">
                <div class="tweet-author">{make_x_link(td['author_username'])} — {td['author']}</div>
                <div class="tweet-text">{td['text']}</div>
                <div class="tweet-meta">📡 {td['method']} |
                    <a href="{tweet_url_input}" target="_blank" style="color:#1DA1F2;">فتح المنشور ↗</a>
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.warning("⚠️ تعذّر جلب النص — سيُستخدم Screenshot للتحليل")
        if td.get("screenshot_url"):
            st.image(td["screenshot_url"], caption="لقطة شاشة المنشور",
                     use_container_width=True)

    if analyze_url_btn and url_valid:
        with st.spinner("⏳ جاري الجلب والتحليل..."):
            td = fetch_tweet_content(tweet_url_input)
            st.session_state.tweet_data = td

            if td["success"]:
                st.markdown(f"""
                <div class="tweet-card">
                    <div class="tweet-author">{make_x_link(td['author_username'])}</div>
                    <div class="tweet-text">{td['text']}</div>
                    <div class="tweet-meta">📡 {td['method']}</div>
                </div>""", unsafe_allow_html=True)

            results = None; method_u = ""; used_model = ""

            # محاولة 1: Gemini على النص
            if td["success"] and td["text"] and use_gemini:
                results, error, used_model = run_gemini(
                    td["text"], st.session_state.api_key, is_image=False
                )
                if error: st.warning(f"⚠️ {error[:60]}"); results = None
                else: method_u = "Gemini AI (نص) ✨"

            # محاولة 2: Gemini على Screenshot
            if results is None and td.get("screenshot_url") and use_gemini:
                try:
                    sr = requests.get(td["screenshot_url"], timeout=15)
                    if sr.ok:
                        si = Image.open(BytesIO(sr.content))
                        results, error, used_model = run_gemini(
                            si, st.session_state.api_key, is_image=True
                        )
                        if error: results = None
                        else: method_u = "Gemini AI (Screenshot) ✨"
                except: pass

            # محاولة 3: تحليل نصي مباشر
            if results is None and td["success"] and td["text"]:
                mentions = re.findall(r'@[A-Za-z0-9_]+', td["text"])
                results  = analyze_post_smart(td["text"], mentions)
                method_u = "تحليل نصي 📝"; used_model = "Smart Parser"

            # محاولة 4: OCR على Screenshot
            if results is None and td.get("screenshot_url"):
                try:
                    sr = requests.get(td["screenshot_url"], timeout=15)
                    if sr.ok:
                        si = Image.open(BytesIO(sr.content))
                        proc = preprocess_image_ocr(si)
                        text, mentions = extract_text_ocr(proc)
                        results = analyze_post_smart(text, mentions)
                        method_u = "OCR Screenshot 🔤"; used_model = "Tesseract"
                except: pass

            if results:
                st.session_state.url_results      = results
                st.session_state.url_analysis_done = True
                st.session_state.analysis_method   = method_u
                st.session_state.used_model        = used_model
                st.session_state.total_analyzed   += 1
                st.rerun()
            else:
                st.error("❌ فشل التحليل — تأكد من صحة الرابط والمفتاح")

    if st.session_state.url_analysis_done and st.session_state.url_results:
        st.markdown("---")
        st.markdown(
            f'<div class="batch-header">✅ {st.session_state.analysis_method} | '
            f'<span class="model-badge">{st.session_state.used_model}</span></div>',
            unsafe_allow_html=True
        )
        render_all_results(st.session_state.url_results, selected_fields)
        download_buttons(st.session_state.url_results, prefix="url_")

# ============================================================
#  التبويب 4: دليل الاستخدام
# ============================================================
with tab4:
    st.markdown("""
## 📋 التبويب 1 — لصق من الحافظة (الأسرع):
1. خذ لقطة شاشة بـ **Ctrl + PrtSc** أو **Snipping Tool (Win+Shift+S)**
2. انقر على منطقة اللصق
3. اضغط **Ctrl+V**
4. اضغط **"تحليل الصورة الملصقة"**

---

## 🖼️ التبويب 2 — رفع الصور:
1. اختر **صورة أو أكثر** من جهازك
2. اضغط **"تحليل جميع الصور"**
3. نزّل جميع النتائج في ملف JSON واحد

---

## 🔗 التبويب 3 — رابط منشور X:
1. الصق رابط المنشور: `https://x.com/username/status/ID`
2. اضغط **"جلب وتحليل مباشرة"**
3. يجلب التطبيق النص ويحلله تلقائياً

---

## 🔑 الحصول على مفتاح Gemini:
1. اذهب إلى: https://aistudio.google.com/apikey
2. اضغط **"Create API Key"**
3. انسخ المفتاح وضعه في الشريط الجانبي

---

## 💡 نصائح:
- ✅ **Gemini 2.0 Flash Lite** — أكثر النماذج مرونة (1500 طلب/يوم)
- ⚡ إذا تجاوزت الحصة يتحول تلقائياً للنموذج التالي
- 🐦 تحليل رابط X يعمل بدون مفتاح X API
""")

st.markdown("---")
st.caption("© تحليل الصور في نقاط — الإصدار 4.1 | "
           "[احصل على مفتاح Gemini](https://aistudio.google.com/apikey)")
