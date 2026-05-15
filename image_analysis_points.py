# -*- coding: utf-8 -*-
"""
المشهد التنفيذي - الإصدار 6.0
استخراج النص من صور المنشور + تفريغ المقاطع + تدقيق لغوي ذكي
"""

import sys
import re
import json
import io
import os
import time
import base64
import tempfile
import subprocess
import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# فحص المكتبات
missing_libs = []
for lib in ["pytesseract", "cv2", "numpy", "PIL", "google.generativeai"]:
    try:
        __import__(lib)
    except ImportError:
        missing_libs.append(lib)

if missing_libs:
    st.error("مكتبات مفقودة: " + ", ".join(missing_libs))
    st.stop()

import pytesseract
import cv2
import numpy as np
from PIL import Image
import google.generativeai as genai

# ==================== إعداد الصفحة ====================
st.set_page_config(
    page_title="المشهد التنفيذي",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CSS ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&display=swap');
* { font-family: 'Tajawal', sans-serif !important; }
html, body, [class*='css'] { direction: rtl; text-align: right; font-size: 17px; }

.main-hero {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 40px;
    text-align: center;
    margin-bottom: 30px;
}
.main-hero h1 { font-size: 2.6rem; font-weight: 900; color: #58a6ff; margin: 0; }
.main-hero p  { font-size: 1.1rem; color: #8b949e; margin-top: 10px; }

.stat-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    margin-bottom: 10px;
}
.stat-card h3 { font-size: 1.8rem; color: #58a6ff; margin: 0; }
.stat-card p  { color: #8b949e; margin: 5px 0 0 0; font-size: 0.85rem; }

.result-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
}
.result-card:hover { border-color: #58a6ff; }
.result-card .field-label { color: #8b949e; font-size: 0.85rem; margin-bottom: 6px; }
.result-card .field-value { color: #e6edf3; font-size: 1rem; line-height: 1.7; }

.summary-card {
    background: linear-gradient(135deg, #0d1117, #1c2128);
    border: 1px solid #388bfd;
    border-radius: 12px;
    padding: 25px;
    margin-top: 20px;
}
.summary-card h4 { color: #58a6ff; font-size: 1.1rem; margin-bottom: 15px; }
.summary-card p  { color: #e6edf3; line-height: 1.9; font-size: 1.05rem; }

.media-card {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 12px;
}
.media-card .media-title { color: #f0883e; font-size: 0.9rem; font-weight: 700; margin-bottom: 8px; }
.media-card .media-text  { color: #c9d1d9; font-size: 0.95rem; line-height: 1.6; }

.transcript-card {
    background: linear-gradient(135deg, #0d1117, #1a1f2e);
    border: 1px solid #8957e5;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
}
.transcript-card h4 { color: #bc8cff; font-size: 1rem; margin-bottom: 12px; }
.transcript-card p  { color: #e6edf3; line-height: 1.8; }

.language-badge {
    background: linear-gradient(135deg, #1f3a5f, #2a1a3a);
    border: 1px solid #388bfd;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.8rem;
    color: #bc8cff;
    display: inline-block;
    margin: 4px 2px;
}
.progress-step {
    background: #161b22;
    border-right: 3px solid #58a6ff;
    padding: 8px 15px;
    margin: 5px 0;
    border-radius: 0 8px 8px 0;
    color: #c9d1d9;
    font-size: 0.9rem;
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
    "عام":            ["منشور", "تغريدة", "تعليق", "رأي", "شخص", "مستخدم"],
    "المتطرفون":      ["إرهاب", "تطرف", "داعش", "جهاد", "تكفير", "غلو"],
    "سياسية":         ["سياسة", "حكومة", "برلمان", "وزير", "رئيس", "انتخابات"],
    "الترفيه":        ["فيلم", "مسلسل", "فنان", "غناء", "كرة", "رياضة"],
    "التجنيس":        ["تجنيس", "جنسية", "مواطنة", "هوية", "وافد"],
    "تهكم_وسخرية":   ["هههه", "😂", "🤣", "طبعاً", "بكل تأكيد", "واضح", "معروف"]
}

# ==================== دوال مساعدة ====================
def validate_api_key(key):
    return bool(key and key.strip().startswith('AIza') and len(key.strip()) > 30)

def detect_category(text):
    if not text:
        return "عام"
    for category, keywords in SEMANTIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "عام"

def is_sarcastic_text(text):
    if not text:
        return False
    return any(ind in text for ind in SEMANTIC_KEYWORDS.get("تهكم_وسخرية", []))

def get_topic_from_text(text):
    if not text:
        return "موضوع عام"
    cat = detect_category(text)
    return {"المتطرفون": "قضايا التطرف", "سياسية": "الشأن السياسي",
            "الترفيه": "الترفيه والرياضة", "التجنيس": "قضايا التجنيس",
            "تهكم_وسخرية": "تعليق ساخر", "عام": "موضوع عام"}.get(cat, "موضوع عام")

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
    'media_extraction_log': []
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==================== OCR ====================
def preprocess_image_ocr(image):
    arr = np.array(image)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if len(arr.shape) == 3 else arr
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(cv2.fastNlMeansDenoising(binary, h=10))

def extract_text_ocr(image):
    try:
        text = pytesseract.image_to_string(preprocess_image_ocr(image), config='--oem 3 --psm 6 -l ara+eng')
        return text.strip() or "لم يتم استخراج نص"
    except Exception as e:
        return "خطأ في OCR: " + str(e)

# ==================== استخراج وسائط X/Twitter ====================
def download_media_yt_dlp(url, output_dir):
    """
    تنزيل الوسائط (صور + فيديو) من منشور X باستخدام yt-dlp
    """
    results = {"images": [], "video": None, "audio": None, "error": None}
    try:
        # تنزيل الفيديو إن وجد
        video_path = os.path.join(output_dir, "video.mp4")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--output", video_path,
            "--format", "best[ext=mp4]/best",
            "--max-filesize", "50m",
            "--quiet",
            "--no-warnings",
            url
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            results["video"] = video_path
            # استخراج الصوت من الفيديو
            audio_path = os.path.join(output_dir, "audio.mp3")
            audio_cmd = ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a",
                         audio_path, "-y", "-loglevel", "quiet"]
            subprocess.run(audio_cmd, capture_output=True, timeout=30)
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                results["audio"] = audio_path
    except Exception as e:
        results["error"] = str(e)

    # تنزيل الصور من الصفحة
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # البحث عن صور og
            og_images = soup.find_all('meta', property='og:image')
            for i, tag in enumerate(og_images[:4]):
                img_url = tag.get('content', '')
                if img_url and 'pbs.twimg.com' in img_url:
                    try:
                        img_resp = requests.get(img_url, timeout=10)
                        if img_resp.status_code == 200:
                            img_path = os.path.join(output_dir, f"image_{i}.jpg")
                            with open(img_path, 'wb') as f:
                                f.write(img_resp.content)
                            results["images"].append(img_path)
                    except:
                        pass
    except:
        pass

    return results

# ==================== تحليل صورة المنشور بـ Gemini ====================
def extract_text_from_post_image(image_path, api_key):
    """
    استخراج النص المكتوب في صورة المنشور باستخدام Gemini Vision
    """
    if not validate_api_key(api_key):
        return ""
    try:
        genai.configure(api_key=api_key.strip())
        img = Image.open(image_path)
        prompt = (
            "أنت خبير في قراءة وتحليل الصور.\n"
            "المهمة: استخرج كل النص المكتوب في هذه الصورة بدقة تامة.\n"
            "اقرأ كل النصوص العربية والإنجليزية الموجودة في الصورة.\n"
            "أعد النص المستخرج فقط بدون أي تعليق أو إضافة.\n"
            "إذا لم يوجد نص، أعد: لا يوجد نص في الصورة."
        )
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content([prompt, img])
        return response.text.strip()
    except Exception as e:
        # fallback إلى OCR
        try:
            img = Image.open(image_path)
            return extract_text_ocr(img)
        except:
            return ""

# ==================== تفريغ الفيديو/الصوت بـ Gemini ====================
def transcribe_video_with_gemini(video_path, api_key):
    """
    تفريغ محتوى الفيديو إلى نص باستخدام Gemini
    """
    if not validate_api_key(api_key) or not video_path:
        return ""
    try:
        genai.configure(api_key=api_key.strip())
        file_size = os.path.getsize(video_path)

        # رفع الملف إلى Gemini Files API إذا كان أكبر من 4MB
        if file_size > 4 * 1024 * 1024:
            uploaded_file = genai.upload_file(video_path)
            # انتظار معالجة الملف
            max_wait = 60
            waited = 0
            while waited < max_wait:
                file_status = genai.get_file(uploaded_file.name)
                if file_status.state.name == "ACTIVE":
                    break
                time.sleep(3)
                waited += 3

            prompt = (
                "أنت خبير في تحليل ومعالجة محتوى الفيديو.\n"
                "المهمة: فرّغ هذا الفيديو وأعد ما يُقال فيه بالكامل.\n"
                "اشمل:\n"
                "1. النص المنطوق (كلام الأشخاص) كاملاً\n"
                "2. النصوص الظاهرة على الشاشة (إن وجدت)\n"
                "3. وصف موجز لمحتوى الفيديو في سطر واحد في النهاية\n"
                "أعد النتيجة بالعربية إن كان المحتوى عربياً، وإلا بالإنجليزية."
            )
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content([prompt, file_status])
            genai.delete_file(uploaded_file.name)
            return response.text.strip()
        else:
            # للملفات الصغيرة: قراءة مباشرة
            with open(video_path, 'rb') as f:
                video_data = f.read()
            video_b64 = base64.b64encode(video_data).decode()
            prompt = (
                "أنت خبير في تحليل ومعالجة محتوى الفيديو.\n"
                "المهمة: فرّغ هذا الفيديو وأعد ما يُقال فيه بالكامل.\n"
                "اشمل:\n"
                "1. النص المنطوق (كلام الأشخاص) كاملاً\n"
                "2. النصوص الظاهرة على الشاشة (إن وجدت)\n"
                "3. وصف موجز لمحتوى الفيديو في سطر واحد في النهاية\n"
                "أعد النتيجة بالعربية إن كان المحتوى عربياً، وإلا بالإنجليزية."
            )
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content([
                prompt,
                {"mime_type": "video/mp4", "data": video_b64}
            ])
            return response.text.strip()
    except Exception as e:
        return "خطأ في تفريغ الفيديو: " + str(e)


def transcribe_audio_with_gemini(audio_path, api_key):
    """
    تفريغ الصوت إلى نص باستخدام Gemini
    """
    if not validate_api_key(api_key) or not audio_path:
        return ""
    try:
        genai.configure(api_key=api_key.strip())
        uploaded_file = genai.upload_file(audio_path)
        max_wait = 30
        waited = 0
        while waited < max_wait:
            file_status = genai.get_file(uploaded_file.name)
            if file_status.state.name == "ACTIVE":
                break
            time.sleep(2)
            waited += 2

        prompt = (
            "فرّغ هذا الصوت إلى نص كاملاً بدقة تامة.\n"
            "أعد النص المنطوق فقط بدون أي تعليق.\n"
            "إذا كان الكلام عربياً أعده بالعربية، وإذا كان إنجليزياً أعده بالإنجليزية."
        )
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content([prompt, file_status])
        genai.delete_file(uploaded_file.name)
        return response.text.strip()
    except Exception as e:
        return "خطأ في تفريغ الصوت: " + str(e)

# ==================== سحب كامل لوسائط المنشور ====================
def fetch_tweet_with_media(url, api_key, status_container=None):
    """
    جلب المنشور مع كل وسائطه: نص + صور + فيديو + تفريغ
    """
    result = {
        "url": url,
        "text": "",
        "author": "",
        "images_text": [],
        "video_transcript": "",
        "has_video": False,
        "has_images": False,
        "media_log": [],
        "error": None
    }

    def log(msg):
        result["media_log"].append(msg)
        if status_container:
            status_container.markdown('<div class="progress-step">' + msg + '</div>', unsafe_allow_html=True)

    log("🔍 جارٍ جلب بيانات المنشور...")

    # جلب النص الأساسي
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            og_desc = soup.find('meta', property='og:description')
            if og_desc:
                result["text"] = og_desc.get('content', '')
            og_title = soup.find('meta', property='og:title')
            if og_title:
                result["author"] = og_title.get('content', '')
            log("✅ تم جلب النص الأساسي للمنشور")
        else:
            log("⚠️ HTTP " + str(resp.status_code) + " عند جلب المنشور")
    except Exception as e:
        result["error"] = str(e)
        log("❌ خطأ في الاتصال: " + str(e))
        return result

    # تنزيل الوسائط في مجلد مؤقت
    with tempfile.TemporaryDirectory() as tmpdir:

        # ---- تنزيل الصور ----
        log("🖼️ جارٍ البحث عن الصور المرفقة...")
        images_downloaded = 0
        try:
            soup_fresh = BeautifulSoup(resp.text, 'html.parser')
            og_images = soup_fresh.find_all('meta', property='og:image')
            for i, tag in enumerate(og_images[:4]):
                img_url = tag.get('content', '')
                if img_url and ('pbs.twimg.com' in img_url or 'twimg.com' in img_url):
                    try:
                        img_resp = requests.get(img_url + ":large", timeout=10)
                        if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                            img_path = os.path.join(tmpdir, "img_" + str(i) + ".jpg")
                            with open(img_path, 'wb') as f:
                                f.write(img_resp.content)
                            log("🖼️ تم تنزيل الصورة " + str(i+1) + " — جارٍ استخراج النص...")
                            # استخراج النص من الصورة
                            img_text = extract_text_from_post_image(img_path, api_key)
                            if img_text and img_text != "لا يوجد نص في الصورة" and len(img_text) > 5:
                                result["images_text"].append(img_text)
                                result["has_images"] = True
                                log("✅ تم استخراج النص من الصورة " + str(i+1))
                            else:
                                log("ℹ️ الصورة " + str(i+1) + " لا تحتوي على نص")
                            images_downloaded += 1
                    except Exception as img_err:
                        log("⚠️ خطأ في الصورة " + str(i+1) + ": " + str(img_err)[:50])
        except Exception as e:
            log("⚠️ خطأ في استخراج الصور: " + str(e)[:50])

        if images_downloaded == 0:
            log("ℹ️ لم يتم العثور على صور مرفقة")

        # ---- تنزيل الفيديو ----
        log("🎬 جارٍ البحث عن مقطع فيديو...")
        try:
            video_path = os.path.join(tmpdir, "video.mp4")
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--output", video_path,
                "--format", "best[ext=mp4]/best",
                "--max-filesize", "50m",
                "--quiet",
                "--no-warnings",
                url
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

            if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                file_size_mb = round(os.path.getsize(video_path) / (1024*1024), 1)
                log("✅ تم تنزيل الفيديو (" + str(file_size_mb) + " MB) — جارٍ التفريغ...")
                result["has_video"] = True

                # تفريغ الفيديو
                transcript = transcribe_video_with_gemini(video_path, api_key)
                if transcript and not transcript.startswith("خطأ"):
                    result["video_transcript"] = transcript
                    log("✅ تم تفريغ الفيديو بنجاح (" + str(len(transcript)) + " حرف)")
                else:
                    # محاولة تفريغ الصوت فقط
                    log("⚠️ محاولة تفريغ الصوت بدلاً من الفيديو...")
                    audio_path = os.path.join(tmpdir, "audio.mp3")
                    audio_cmd = ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a",
                                 audio_path, "-y", "-loglevel", "quiet"]
                    subprocess.run(audio_cmd, capture_output=True, timeout=30)
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                        transcript = transcribe_audio_with_gemini(audio_path, api_key)
                        if transcript and not transcript.startswith("خطأ"):
                            result["video_transcript"] = transcript
                            log("✅ تم تفريغ الصوت بنجاح")
                        else:
                            log("⚠️ " + (transcript or "فشل التفريغ"))
            else:
                log("ℹ️ لا يوجد فيديو في هذا المنشور")
        except FileNotFoundError:
            log("⚠️ yt-dlp غير مثبت — تخطي تنزيل الفيديو")
        except subprocess.TimeoutExpired:
            log("⏱️ انتهت مهلة تنزيل الفيديو (90 ثانية)")
        except Exception as e:
            log("⚠️ خطأ في تنزيل الفيديو: " + str(e)[:60])

    log("🎯 اكتمل جمع بيانات المنشور")
    return result

# ==================== JSON Parser ====================
def parse_gemini_json(raw_text):
    if not raw_text:
        return None
    try:
        m = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if m:
            return json.loads(m.group())
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

# ==================== تحسين اللغة العربية ====================
def polish_arabic_with_gemini(summary_text, api_key):
    if not summary_text or len(summary_text.strip()) < 20 or not validate_api_key(api_key):
        return summary_text, False
    prompt = (
        "أنت مدقق لغوي محترف متخصص في اللغة العربية الفصحى.\n"
        "صحح الملخص التالي إملائياً ونحوياً دون تغيير المعنى:\n\n"
        + summary_text +
        "\n\nأعد الملخص المُصحَّح فقط بدون أي كلام إضافي."
    )
    try:
        genai.configure(api_key=api_key.strip())
        for m in ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                r = genai.GenerativeModel(m).generate_content(prompt)
                c = r.text.strip()
                if c and len(c) > 10:
                    return c, True
            except:
                continue
    except:
        pass
    return summary_text, False

def correct_with_sahehly_api(text, sahehly_key):
    if not text or not sahehly_key or len(sahehly_key.strip()) < 10:
        return text, False
    try:
        r = requests.post(
            "https://sahehly.com/api/v1/correct",
            json={"text": text[:3000], "services": ["spelling", "grammar", "punctuation"]},
            headers={"Authorization": "Bearer " + sahehly_key.strip(),
                     "Content-Type": "application/json"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json().get("corrected_text", text), True
    except:
        pass
    return text, False

def enhance_arabic_summary(text, api_key, sahehly_key=""):
    if not st.session_state.get('enable_arabic_enhancement', True):
        return text, "بدون تحسين", False
    if sahehly_key and len(sahehly_key.strip()) > 10:
        c, ok = correct_with_sahehly_api(text, sahehly_key)
        if ok:
            return c, "صححلي API", True
    if validate_api_key(api_key):
        c, ok = polish_arabic_with_gemini(text, api_key)
        if ok:
            return c, "Gemini مدقق لغوي", True
    return text, "بدون تحسين", False

# ==================== بروميبت Gemini الشامل ====================
def build_full_analysis_prompt(post_text, images_text_list, video_transcript):
    """
    بناء بروميبت شامل يدمج نص المنشور + نص الصور + تفريغ الفيديو
    """
    sections = []
    if post_text:
        sections.append("=== نص المنشور ===\n" + post_text)
    if images_text_list:
        for i, img_txt in enumerate(images_text_list):
            sections.append("=== نص الصورة المرفقة " + str(i+1) + " ===\n" + img_txt)
    if video_transcript:
        sections.append("=== تفريغ المقطع المرفق ===\n" + video_transcript)

    combined = "\n\n".join(sections) if sections else "لا يوجد محتوى"

    prompt = (
        "أنت محلل متخصص في تحليل منشورات منصة X (تويتر).\n"
        "لديك المحتوى الكامل للمنشور بما يشمل النص والصور والمقاطع.\n\n"
        + combined +
        "\n\n"
        "قواعد الملخص التنفيذي الإلزامية:\n"
        "- اللغة العربية الفصحى حصراً\n"
        "- لا تقل عن 100 كلمة\n"
        "- اربط المنشور بمحتوى الصور والمقاطع إن وجدت\n"
        "- وضّح الرسالة الكاملة التي أراد صاحب المنشور إيصالها\n\n"
        "أعد النتائج بتنسيق JSON فقط:\n"
        "{\n"
        '  "معرف_المنشور": "معرف صاحب المنشور (مع @) أو غير مُحدد",\n'
        '  "معرف_التعليق": "معرف المعلّق (مع @) أو غير مُحدد",\n'
        '  "المدعو": "الشخص المُستشهد به أو غير مُحدد",\n'
        '  "محتوى_المنشور": "النص الكامل للمنشور",\n'
        '  "محتوى_الصورة": "النص المستخرج من الصورة المرفقة أو غير مُحدد",\n'
        '  "تفريغ_المقطع": "النص المفرَّغ من المقطع أو غير مُحدد",\n'
        '  "التعليق": "نص التعليق أو غير مُحدد",\n'
        '  "الرأي": "الرأي والموقف المُعبَّر عنه",\n'
        '  "الملخص_التنفيذي": "ملخص شامل لا يقل عن 100 كلمة يدمج كل محتوى المنشور"\n'
        "}\n\n"
        "مهم: أعد JSON فقط بدون أي نص إضافي."
    )
    return prompt

# ==================== تحليل شامل مع Gemini ====================
def analyze_full_post_with_gemini(tweet_data, api_key):
    """
    التحليل الشامل: نص + صور + فيديو
    """
    if not validate_api_key(api_key):
        return None, "مفتاح API غير صالح", ""

    post_text       = tweet_data.get("text", "")
    images_text     = tweet_data.get("images_text", [])
    video_transcript= tweet_data.get("video_transcript", "")

    prompt = build_full_analysis_prompt(post_text, images_text, video_transcript)
    genai.configure(api_key=api_key.strip())

    models = ["gemini-2.0-flash-lite", "gemini-2.5-flash",
              "gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash"]
    last_err = ""
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            result = parse_gemini_json(response.text)
            if result:
                required = ["معرف_المنشور", "معرف_التعليق", "المدعو", "محتوى_المنشور",
                            "محتوى_الصورة", "تفريغ_المقطع", "التعليق", "الرأي", "الملخص_التنفيذي"]
                for f in required:
                    result.setdefault(f, "غير مُحدد")
                # حقن محتوى الصور والفيديو إذا لم يتضمنها Gemini
                if images_text and result.get("محتوى_الصورة") in ["غير مُحدد", ""]:
                    result["محتوى_الصورة"] = " | ".join(images_text)
                if video_transcript and result.get("تفريغ_المقطع") in ["غير مُحدد", ""]:
                    result["تفريغ_المقطع"] = video_transcript
                # تحسين الملخص
                if st.session_state.get('enable_arabic_enhancement', True):
                    enhanced, method, ok = enhance_arabic_summary(
                        result.get("الملخص_التنفيذي", ""),
                        api_key,
                        st.session_state.get('sahehly_api_key', '')
                    )
                    if ok:
                        result["الملخص_التنفيذي"] = enhanced
                        result["_enhancement_method"] = method
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED", "429", "rate_limit"]):
                last_err = model_name + ": تجاوز الحصة"
                time.sleep(2)
            elif any(x in err for x in ["404", "MODEL_NOT_FOUND"]):
                last_err = model_name + ": غير متاح"
            elif "API_KEY_INVALID" in err:
                return None, "مفتاح API غير صالح", ""
            else:
                last_err = model_name + ": " + err[:50]
    return None, "فشل التحليل: " + last_err, ""

# ==================== تحليل الصورة المرفوعة ====================
GEMINI_IMAGE_PROMPT = (
    "أنت محلل متخصص في تحليل منشورات X.\n"
    "حلل هذه الصورة واستخرج كل المعلومات.\n\n"
    "قواعد الملخص: عربية فصحى، لا تقل عن 80 كلمة.\n\n"
    "أعد JSON فقط:\n"
    "{\n"
    '  "معرف_المنشور": "...",\n'
    '  "معرف_التعليق": "...",\n'
    '  "المدعو": "...",\n'
    '  "محتوى_المنشور": "...",\n'
    '  "محتوى_الصورة": "النص المكتوب في الصورة المرفقة إن وجد",\n'
    '  "تفريغ_المقطع": "غير مُحدد",\n'
    '  "التعليق": "...",\n'
    '  "الرأي": "...",\n'
    '  "الملخص_التنفيذي": "ملخص شامل لا يقل عن 80 كلمة"\n'
    "}"
)

def analyze_with_gemini(image, api_key):
    if not validate_api_key(api_key):
        return None, "مفتاح API غير صالح", ""
    genai.configure(api_key=api_key.strip())
    models = ["gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash",
              "gemini-1.5-flash-latest", "gemini-1.5-flash"]
    last_err = ""
    for model_name in models:
        try:
            r = genai.GenerativeModel(model_name).generate_content([GEMINI_IMAGE_PROMPT, image])
            result = parse_gemini_json(r.text)
            if result:
                for f in ["معرف_المنشور","معرف_التعليق","المدعو","محتوى_المنشور",
                          "محتوى_الصورة","تفريغ_المقطع","التعليق","الرأي","الملخص_التنفيذي"]:
                    result.setdefault(f, "غير مُحدد")
                if st.session_state.get('enable_arabic_enhancement', True):
                    enhanced, method, ok = enhance_arabic_summary(
                        result.get("الملخص_التنفيذي",""), api_key,
                        st.session_state.get('sahehly_api_key',''))
                    if ok:
                        result["الملخص_التنفيذي"] = enhanced
                        result["_enhancement_method"] = method
                return result, None, model_name
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["QUOTA_EXCEEDED","429"]): time.sleep(2)
            last_err = model_name + ": " + err[:40]
    return None, "فشل: " + last_err, ""

def analyze_post_smart(text):
    return {
        "معرف_المنشور": next(iter(re.findall(r'@[\w\u0600-\u06FF]+', text)), "غير مُحدد"),
        "معرف_التعليق": "غير مُحدد",
        "المدعو": "غير مُحدد",
        "محتوى_المنشور": text[:300],
        "محتوى_الصورة": "غير مُحدد",
        "تفريغ_المقطع": "غير مُحدد",
        "التعليق": "غير مُحدد",
        "الرأي": "تعليق ساخر" if is_sarcastic_text(text) else "موضوع " + detect_category(text),
        "الملخص_التنفيذي": "منشور على منصة X يناقش: " + text[:150]
    }

def extract_text_ocr_image(image):
    return extract_text_ocr(image)

def analyze_image_full(image, api_key, use_gemini):
    if use_gemini and validate_api_key(api_key):
        result, err, model = analyze_with_gemini(image, api_key)
        if result:
            return result, "Gemini (" + model + ")", model
    ocr_text = extract_text_ocr_image(image)
    result = analyze_post_smart(ocr_text)
    if st.session_state.get('enable_arabic_enhancement', True) and validate_api_key(api_key):
        enhanced, emethod, ok = enhance_arabic_summary(
            result.get("الملخص_التنفيذي", ""), api_key,
            st.session_state.get('sahehly_api_key', ''))
        if ok:
            result["الملخص_التنفيذي"] = enhanced
            result["_enhancement_method"] = emethod
    return result, "OCR + تحليل ذكي", ""

# ==================== تكوين الحقول ====================
FIELD_CONFIG = {
    "معرف_المنشور":    {"icon": "👤", "label": "صاحب المنشور"},
    "معرف_التعليق":    {"icon": "💬", "label": "صاحب التعليق"},
    "المدعو":          {"icon": "🎯", "label": "الشخص المُستشهد به"},
    "محتوى_المنشور":   {"icon": "📝", "label": "محتوى المنشور"},
    "محتوى_الصورة":    {"icon": "🖼️", "label": "نص الصورة المرفقة"},
    "تفريغ_المقطع":    {"icon": "🎬", "label": "تفريغ المقطع"},
    "التعليق":         {"icon": "💭", "label": "نص التعليق"},
    "الرأي":           {"icon": "🔍", "label": "الرأي والموقف"},
    "الملخص_التنفيذي": {"icon": "📋", "label": "الملخص التنفيذي"}
}

# ==================== عرض النتائج ====================
def render_result_card(field_key, value):
    if not value or str(value).strip() in ["غير مُحدد", "غير محدد", ""]:
        return
    conf = FIELD_CONFIG.get(field_key, {"icon": "📌", "label": field_key})

    if field_key == "الملخص_التنفيذي":
        st.markdown(
            '<div class="summary-card">'
            '<h4>' + conf['icon'] + ' ' + conf['label'] + '</h4>'
            '<p>' + str(value) + '</p>'
            '</div>', unsafe_allow_html=True)

    elif field_key in ["محتوى_الصورة", "تفريغ_المقطع"]:
        icon_color = {"محتوى_الصورة": "#f0883e", "تفريغ_المقطع": "#bc8cff"}.get(field_key, "#58a6ff")
        st.markdown(
            '<div class="transcript-card">'
            '<h4 style="color:' + icon_color + ';">' + conf['icon'] + ' ' + conf['label'] + '</h4>'
            '<p>' + str(value) + '</p>'
            '</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="result-card">'
            '<div class="field-label">' + conf['icon'] + ' ' + conf['label'] + '</div>'
            '<div class="field-value">' + str(value) + '</div>'
            '</div>', unsafe_allow_html=True)

def render_all_results(result, selected_fields):
    if not result:
        st.warning("لا توجد نتائج")
        return
    emethod = result.get("_enhancement_method", "")
    if emethod:
        st.markdown(
            '<div style="text-align:right;margin-bottom:12px;">'
            '<span class="language-badge">✨ تحسين اللغة: ' + emethod + '</span>'
            '</div>', unsafe_allow_html=True)
    has_img = result.get("محتوى_الصورة","") not in ["غير مُحدد",""]
    has_vid = result.get("تفريغ_المقطع","") not in ["غير مُحدد",""]
    if has_img or has_vid:
        badges = ""
        if has_img: badges += '<span class="language-badge">🖼️ يحتوي صورة مُحلَّلة</span> '
        if has_vid: badges += '<span class="language-badge">🎬 يحتوي مقطع مُفرَّغ</span>'
        st.markdown('<div style="text-align:right;margin-bottom:12px;">' + badges + '</div>', unsafe_allow_html=True)

    for field_key in selected_fields:
        if field_key in result:
            render_result_card(field_key, result[field_key])
    if "الملخص_التنفيذي" not in selected_fields and "الملخص_التنفيذي" in result:
        render_result_card("الملخص_التنفيذي", result["الملخص_التنفيذي"])

def download_buttons(result, prefix="result"):
    if not result:
        return
    col1, col2 = st.columns(2)
    with col1:
        txt = "\n".join(k + ": " + str(v) for k, v in result.items() if not k.startswith("_"))
        st.download_button("📄 تحميل TXT", txt, prefix + ".txt", "text/plain")
    with col2:
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        st.download_button("📊 تحميل JSON", json.dumps(clean, ensure_ascii=False, indent=2),
                           prefix + ".json", "application/json")

# ==================== الشريط الجانبي ====================
with st.sidebar:
    st.markdown("## ⚙️ إعدادات التحليل")
    analysis_mode = st.radio("طريقة التحليل", ["🤖 Gemini AI (أدق)", "📝 OCR (مجاني)"], index=0)
    use_gemini = "Gemini" in analysis_mode

    if use_gemini:
        api_input = st.text_input("🔑 مفتاح Gemini API", value=st.session_state.api_key,
                                  type="password", placeholder="AIza...")
        if api_input != st.session_state.api_key:
            st.session_state.api_key = api_input
        if st.session_state.api_key:
            st.success("✅ مفتاح صالح") if validate_api_key(st.session_state.api_key) else st.error("❌ مفتاح غير صالح")
        st.markdown("🔗 [احصل على مفتاح مجاني](https://aistudio.google.com/apikey)")

    st.markdown("---")
    st.markdown("### ✨ تحسين اللغة العربية")
    st.session_state.enable_arabic_enhancement = st.toggle(
        "تفعيل التدقيق اللغوي", value=st.session_state.enable_arabic_enhancement)
    if st.session_state.enable_arabic_enhancement:
        st.info("Gemini يدقق إملاء ونحو الملخص")
        with st.expander("🔑 مفتاح صححلي (اختياري)"):
            sah = st.text_input("مفتاح صححلي API", value=st.session_state.sahehly_api_key,
                                type="password", placeholder="للأعمال فقط")
            st.session_state.sahehly_api_key = sah
            st.markdown("🔗 [اشترك في صححلي](https://sahehly.com/Pricing/AddBusinessRequest)")

    st.markdown("---")
    st.markdown("### 📋 الحقول المعروضة")
    selected_fields = st.multiselect(
        "اختر الحقول", list(FIELD_CONFIG.keys()), default=list(FIELD_CONFIG.keys()),
        format_func=lambda x: FIELD_CONFIG[x]['icon'] + " " + FIELD_CONFIG[x]['label'])

    st.markdown("---")
    st.markdown("### 📊 إحصائيات الجلسة")
    c1, c2 = st.columns(2)
    with c1: st.metric("📸 محلّلة", st.session_state.total_analyzed)
    with c2: st.metric("✅ ناجحة", st.session_state.success_count)

    if st.button("🗑️ مسح النتائج"):
        for k in ['results','analysis_done','url_analysis_done','url_results',
                  'tweet_data','total_analyzed','success_count','media_extraction_log']:
            v = defaults.get(k)
            st.session_state[k] = [] if isinstance(v, list) else (0 if isinstance(v, int) else (False if isinstance(v, bool) else None))
        st.rerun()

    with st.expander("📖 القاموس الدلالي"):
        for cat, words in SEMANTIC_KEYWORDS.items():
            st.markdown("**" + cat + "**: " + ", ".join(words[:4]) + "...")

# ==================== الواجهة الرئيسية ====================
st.markdown("""
<div class="main-hero">
    <h1>🎬 المشهد التنفيذي</h1>
    <p>تحليل منشورات X — نص · صور · مقاطع · ملخص ذكي</p>
    <p><span class="language-badge">✨ الإصدار 6.0 — تحليل وسائط متكامل</span></p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown('<div class="stat-card"><h3>' + str(st.session_state.total_analyzed) + '</h3><p>📸 محلّلة</p></div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="stat-card"><h3>' + str(st.session_state.success_count) + '</h3><p>✅ ناجحة</p></div>', unsafe_allow_html=True)
with c3:
    st.markdown('<div class="stat-card"><h3>' + ("🟢" if st.session_state.enable_arabic_enhancement else "🔴") + '</h3><p>✨ التدقيق اللغوي</p></div>', unsafe_allow_html=True)
with c4:
    st.markdown('<div class="stat-card"><h3>🎬 + 🖼️</h3><p>تحليل وسائط</p></div>', unsafe_allow_html=True)

# ==================== تبويبات ====================
tab_url, tab_upload, tab_paste, tab_guide = st.tabs([
    "🔗 رابط X (متكامل)",
    "📤 رفع صور",
    "📋 لصق صورة",
    "📖 دليل الاستخدام"
])

# ==================== تبويب رابط X ====================
with tab_url:
    st.markdown("### 🔗 تحليل منشور X — نص + صور + مقاطع")
    st.info("🆕 الإصدار 6.0: يسحب تلقائياً النص من الصور ويفرّغ مقاطع الفيديو المرفقة")

    tweet_url = st.text_input("أدخل رابط منشور X",
                               placeholder="https://x.com/username/status/123456789",
                               key="tweet_url_input")

    col1, col2 = st.columns(2)
    with col1:
        fetch_only = st.button("📥 جلب بيانات المنشور فقط", key="fetch_only")
    with col2:
        fetch_analyze = st.button("🚀 جلب وتحليل كامل", key="fetch_analyze")

    if fetch_only and tweet_url:
        if "x.com" in tweet_url or "twitter.com" in tweet_url:
            status_box = st.empty()
            with st.spinner("جارٍ الجلب..."):
                td = fetch_tweet_with_media(tweet_url, st.session_state.api_key, status_box)
                st.session_state.tweet_data = td
            st.success("✅ تم جلب البيانات")
            st.rerun()
        else:
            st.warning("أدخل رابط X صحيح")

    if fetch_analyze and tweet_url:
        if "x.com" in tweet_url or "twitter.com" in tweet_url:
            if not validate_api_key(st.session_state.api_key):
                st.error("❌ أدخل مفتاح Gemini API أولاً للتحليل الكامل")
            else:
                status_box = st.container()
                progress_placeholder = status_box.empty()

                with st.spinner("⏳ جارٍ الجلب الشامل والتحليل..."):
                    # المرحلة 1: جلب الوسائط
                    progress_placeholder.info("المرحلة 1/2: جلب المنشور والوسائط...")
                    td = fetch_tweet_with_media(tweet_url, st.session_state.api_key, None)
                    st.session_state.tweet_data = td

                    # عرض سجل العمليات
                    if td.get("media_log"):
                        with st.expander("📋 سجل عمليات الجلب", expanded=True):
                            for log_item in td["media_log"]:
                                st.markdown('<div class="progress-step">' + log_item + '</div>',
                                            unsafe_allow_html=True)

                    # المرحلة 2: التحليل
                    progress_placeholder.info("المرحلة 2/2: التحليل الذكي...")
                    result, err, model_name = analyze_full_post_with_gemini(td, st.session_state.api_key)

                    if not result:
                        # fallback
                        fallback_text = td.get("text", "")
                        if td.get("images_text"):
                            fallback_text += " | " + " | ".join(td["images_text"])
                        if td.get("video_transcript"):
                            fallback_text += " | " + td["video_transcript"]
                        result = analyze_post_smart(fallback_text)

                    st.session_state.url_results = result
                    st.session_state.url_analysis_done = True
                    st.session_state.analysis_method = "Gemini شامل (" + model_name + ")"
                    st.session_state.total_analyzed += 1
                    if result:
                        st.session_state.success_count += 1

                progress_placeholder.empty()
                st.rerun()
        else:
            st.warning("أدخل رابط X صحيح")

    # عرض بيانات المنشور المجلوب
    if st.session_state.tweet_data:
        td = st.session_state.tweet_data
        st.markdown("---")
        st.markdown("#### 📄 بيانات المنشور")

        if td.get("author"):
            st.markdown('<div class="result-card"><div class="field-label">👤 صاحب المنشور</div>'
                        '<div class="field-value">' + td["author"] + '</div></div>', unsafe_allow_html=True)
        if td.get("text"):
            st.text_area("نص المنشور", td["text"], height=80, disabled=True)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            has_img = bool(td.get("images_text"))
            st.markdown("🖼️ صور: " + ("✅ " + str(len(td["images_text"])) if has_img else "❌ لا يوجد"))
        with col_b:
            has_vid = bool(td.get("video_transcript"))
            st.markdown("🎬 فيديو: " + ("✅ مُفرَّغ" if has_vid else "❌ لا يوجد"))
        with col_c:
            st.markdown("📝 نص: " + ("✅" if td.get("text") else "❌"))

        if td.get("images_text"):
            with st.expander("🖼️ النص المستخرج من الصور"):
                for i, img_txt in enumerate(td["images_text"]):
                    st.markdown('<div class="media-card">'
                                '<div class="media-title">الصورة ' + str(i+1) + '</div>'
                                '<div class="media-text">' + img_txt + '</div>'
                                '</div>', unsafe_allow_html=True)

        if td.get("video_transcript"):
            with st.expander("🎬 تفريغ المقطع"):
                st.markdown('<div class="transcript-card">'
                            '<h4>النص المُفرَّغ</h4>'
                            '<p>' + td["video_transcript"] + '</p>'
                            '</div>', unsafe_allow_html=True)

        if td.get("error"):
            st.warning("⚠️ " + td["error"])

    # عرض نتائج التحليل
    if st.session_state.url_analysis_done and st.session_state.url_results:
        st.markdown("---")
        st.markdown("### ✅ نتائج التحليل الشامل")
        render_all_results(st.session_state.url_results, selected_fields)
        download_buttons(st.session_state.url_results, "mashad_result")

# ==================== تبويب رفع الصور ====================
with tab_upload:
    st.markdown("### 📤 رفع صور متعددة للتحليل")
    uploaded_files = st.file_uploader(
        "اسحب صور المنشورات هنا",
        type=['png', 'jpg', 'jpeg', 'webp', 'bmp'],
        accept_multiple_files=True, key="batch_uploader")

    if uploaded_files:
        cols = st.columns(min(len(uploaded_files), 3))
        for i, f in enumerate(uploaded_files):
            with cols[i % 3]:
                st.image(Image.open(f), caption=f.name, use_column_width=True)

        if st.button("🚀 تحليل جميع الصور", key="analyze_batch"):
            pb = st.progress(0)
            st_txt = st.empty()
            batch_results = []
            for i, uf in enumerate(uploaded_files):
                st_txt.text("تحليل " + str(i+1) + "/" + str(len(uploaded_files)) + ": " + uf.name)
                img = Image.open(uf)
                result, method, _ = analyze_image_full(img, st.session_state.api_key, use_gemini)
                st.session_state.total_analyzed += 1
                if result:
                    st.session_state.success_count += 1
                    batch_results.append({"file": uf.name, "result": result, "method": method})
                pb.progress((i+1)/len(uploaded_files))
                time.sleep(0.3)
            st.session_state.results = batch_results
            st.session_state.analysis_done = True
            st_txt.text("✅ تم تحليل " + str(len(batch_results)) + " صورة")
            st.rerun()

    if st.session_state.analysis_done and st.session_state.results:
        st.markdown("### نتائج التحليل")
        for i, item in enumerate(st.session_state.results):
            with st.expander(item['file'] + " | " + item['method'], expanded=(i == 0)):
                render_all_results(item['result'], selected_fields)
                download_buttons(item['result'], "img_result_" + str(i+1))

# ==================== تبويب لصق الصورة ====================
with tab_paste:
    st.markdown("### 📋 رفع صورة مباشرة")
    paste_file = st.file_uploader("اختر صورة", type=['png','jpg','jpeg','webp'], key="paste_uploader")
    if paste_file:
        image = Image.open(paste_file)
        st.image(image, use_column_width=True)
        if st.button("🚀 تحليل الصورة", key="analyze_paste"):
            with st.spinner("جارٍ التحليل..."):
                result, method, _ = analyze_image_full(image, st.session_state.api_key, use_gemini)
                st.session_state.total_analyzed += 1
                if result:
                    st.session_state.success_count += 1
                    st.success("✅ " + method)
                    render_all_results(result, selected_fields)
                    download_buttons(result, "paste_result")
                else:
                    st.error("فشل التحليل")

# ==================== دليل الاستخدام ====================
with tab_guide:
    st.markdown("""
### 📖 دليل المشهد التنفيذي — الإصدار 6.0

#### 🆕 ميزات الإصدار الجديد
- **استخراج النص من الصور**: يقرأ تلقائياً أي نص أو صورة مرفقة في المنشور
- **تفريغ مقاطع الفيديو**: يحوّل الكلام المنطوق في الفيديو إلى نص مكتوب
- **ملخص تنفيذي شامل**: يدمج نص المنشور + الصور + الفيديو في ملخص واحد متكامل

#### 🔗 تبويب رابط X (الأهم)
1. أدخل رابط أي منشور X
2. اضغط **جلب وتحليل كامل**
3. سيقوم التطبيق تلقائياً بـ:
   - سحب نص المنشور
   - تنزيل الصور المرفقة واستخراج نصوصها
   - تنزيل الفيديو وتفريغه إلى نص
4. ينتج ملخصاً تنفيذياً شاملاً يعكس المنشور الكامل

#### ⚙️ المتطلبات
- مفتاح Gemini API (مجاني من [aistudio.google.com](https://aistudio.google.com/apikey))
- yt-dlp وffmpeg مثبتان (في packages.txt)

#### 💡 نصائح
- الفيديوهات الكبيرة (أكبر من 50 MB) قد تستغرق وقتاً أطول
- للنتائج الأفضل استخدم نموذج gemini-2.0-flash
    """)

# ==================== التذييل ====================
st.markdown("""
<div class="footer">
    🎬 المشهد التنفيذي — الإصدار 6.0<br>
    تحليل منشورات X بالذكاء الاصطناعي | نص · صور · مقاطع<br>
    <a href="https://aistudio.google.com/apikey" style="color:#58a6ff;">مفتاح Gemini</a>
    &nbsp;|&nbsp;
    <a href="https://sahehly.com" style="color:#58a6ff;">صححلي</a>
</div>
""", unsafe_allow_html=True)
