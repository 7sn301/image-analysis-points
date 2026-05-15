# المشهد التنفيذي v6.1 - تحليل منشورات X/Twitter بالذكاء الاصطناعي
# إصلاح كامل لـ Regex ودعم روابط x.com و twitter.com

import os
import re
import io
import json
import base64
import tempfile
import subprocess
import shutil
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, urljoin, parse_qs
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS_AVAILABLE = True
except ImportError:
    BS_AVAILABLE = False

# ===== إعدادات التطبيق =====
APP_NAME = "المشهد التنفيذي"
APP_VERSION = "6.1"
APP_EMOJI = "🎯"

# ===== نماذج Gemini المدعومة =====
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

# ===== إعدادات OCR =====
TESSERACT_LANG = "ara+eng"

# ===== Regex للتحقق من روابط X/Twitter =====
TWEET_URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(\d+)(?:\?.*)?',
    re.IGNORECASE
)

# ===== دوال التحقق من روابط X =====
def is_tweet_url(url: str) -> bool:
    """التحقق من أن الرابط هو رابط منشور X/Twitter صالح"""
    if not url:
        return False
    return bool(TWEET_URL_PATTERN.match(url.strip()))

def extract_tweet_id(url: str) -> Optional[str]:
    """استخراج معرّف المنشور من الرابط"""
    match = TWEET_URL_PATTERN.search(url)
    if match:
        return match.group(1)
    return None

def normalize_tweet_url(url: str) -> str:
    """تطبيع الرابط (إزالة البارامترات وتحويل x.com إلى twitter.com)"""
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        return url.split("?")[0]
    
    match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status/', url, re.IGNORECASE)
    username = match.group(1) if match else "user"
    
    return f"https://twitter.com/{username}/status/{tweet_id}"

# ===== دوال جلب المنشور =====
def fetch_via_nitter(tweet_url: str) -> Dict[str, Any]:
    """جلب المنشور عبر Nitter"""
    tweet_id = extract_tweet_id(tweet_url)
    if not tweet_id:
        return {"error": "معرّف المنشور غير صالح"}
    
    match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status/', tweet_url, re.IGNORECASE)
    username = match.group(1) if match else ""
    
    if not username:
        return {"error": "اسم المستخدم غير صالح"}
    
    nitter_mirrors = [
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
        "https://nitter.kavin.rocks",
        "https://nitter.net",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ar,en-US;q=0.9",
    }
    
    for mirror in nitter_mirrors:
        try:
            nitter_url = f"{mirror}/{username}/status/{tweet_id}"
            resp = requests.get(nitter_url, headers=headers, timeout=15, allow_redirects=True)
            
            if resp.status_code == 200 and "html" in resp.headers.get("Content-Type", "").lower():
                if BS_AVAILABLE:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    result = {
                        "text": "",
                        "author": username,
                        "images": [],
                        "video_url": "",
                        "source_mirror": mirror
                    }
                    
                    tweet_content = soup.find("div", class_="tweet-content")
                    if tweet_content:
                        result["text"] = tweet_content.get_text(strip=True)
                    
                    for img in soup.find_all("img"):
                        src = img.get("src", "")
                        if "/pic/" in src or ".jpg" in src or ".png" in src:
                            full_url = urljoin(mirror, src)
                            if full_url not in result["images"]:
                                result["images"].append(full_url)
                    
                    video = soup.find("video")
                    if video:
                        src = video.get("src", "")
                        if src:
                            result["video_url"] = urljoin(mirror, src)
                    
                    return result
                else:
                    return {"error": "مكتبة BeautifulSoup غير مثبتة"}
        except Exception:
            continue
    
    return {"error": "تعذّر الوصول عبر جميع مرايا Nitter"}

def download_media_yt_dlp(tweet_url: str, output_dir: str) -> Dict[str, Any]:
    """تحميل الوسائط بـ yt-dlp"""
    clean_url = normalize_tweet_url(tweet_url)
    result = {"images": [], "video_path": "", "error": ""}
    
    try:
        cmd = ["yt-dlp", "--no-playlist", "--write-thumbnail", "--skip-download",
               "--output", os.path.join(output_dir, "thumb.%(ext)s"), "--timeout", "30", clean_url]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        video_cmd = ["yt-dlp", "--no-playlist", "--format", "best[height<=720]",
                     "--output", os.path.join(output_dir, "video.%(ext)s"), "--timeout", "60", clean_url]
        subprocess.run(video_cmd, capture_output=True, text=True, timeout=90)
        
        for fname in os.listdir(output_dir):
            fpath = os.path.join(output_dir, fname)
            if fname.startswith("thumb"):
                result["images"].append(fpath)
            elif fname.startswith("video"):
                result["video_path"] = fpath
    except subprocess.TimeoutExpired:
        result["error"] = "انتهت مهلة التحميل"
    except Exception as e:
        result["error"] = str(e)
    
    return result

def fetch_tweet_with_media(url: str, api_key: str, status_container=None) -> Dict[str, Any]:
    """الدالة الرئيسية لجلب المنشور"""
    def log(msg):
        if status_container:
            status_container.info(msg)
    
    if not is_tweet_url(url):
        return {"error": "❌ الرابط غير صالح", "url": url}
    
    tweet_id = extract_tweet_id(url)
    log(f"✅ تم التعرف على المنشور | ID: {tweet_id}")
    
    result = {"tweet_id": tweet_id, "url": url, "text": "", "author": "",
              "images_text": "", "video_transcript": "", "raw_images": [], "error": ""}
    
    log("🔍 جاري جلب المنشور عبر Nitter...")
    nitter_data = fetch_via_nitter(url)
    
    if "error" not in nitter_data or nitter_data.get("text"):
        result["text"] = nitter_data.get("text", "")
        result["author"] = nitter_data.get("author", "")
        result["raw_images"] = nitter_data.get("images", [])
        log(f"✅ تم جلب النص: {result['text'][:50] if result['text'] else 'لا يوجد'}...")
    else:
        log(f"⚠️ Nitter: {nitter_data.get('error', '')}")
    
    log("📥 جاري تحميل الوسائط...")
    with tempfile.TemporaryDirectory() as tmpdir:
        media = download_media_yt_dlp(url, tmpdir)
        
        for img_path in media.get("images", []):
            if os.path.exists(img_path):
                log("🖼️ جاري قراءة نص الصورة...")
                img_text = extract_text_from_post_image(img_path, api_key)
                if img_text:
                    result["images_text"] += img_text + "\n"
        
        if media.get("video_path") and os.path.exists(media["video_path"]):
            log("🎬 جاري تفريغ الفيديو...")
            result["video_transcript"] = transcribe_video_with_gemini(media["video_path"], api_key)
    
    return result

# ===== دوال OCR =====
def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """معالجة الصورة لتحسين OCR"""
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageEnhance.Contrast(image).enhance(1.5)
    return image

def extract_text_from_post_image(image_path: str, api_key: str) -> str:
    """استخراج النص من الصورة"""
    try:
        with Image.open(image_path) as img:
            processed = preprocess_image_for_ocr(img)
            text = pytesseract.image_to_string(processed, lang=TESSERACT_LANG, config="--psm 6")
            if text.strip():
                return text.strip()
    except Exception:
        pass
    
    if api_key and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            response = model.generate_content([
                "استخرج النص المكتوب في هذه الصورة بدقة",
                {"mime_type": "image/jpeg", "data": image_data}
            ])
            return response.text if hasattr(response, "text") else ""
        except Exception:
            return ""
    
    return ""

def transcribe_video_with_gemini(video_path: str, api_key: str) -> str:
    """تفريغ الفيديو"""
    if not api_key or not GENAI_AVAILABLE:
        return "(يتطلب مفتاح Gemini API)"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        with open(video_path, "rb") as f:
            video_data = f.read()
        
        mime_type = "video/mp4"
        if video_path.endswith(".webm"):
            mime_type = "video/webm"
        elif video_path.endswith(".mov"):
            mime_type = "video/quicktime"
        
        response = model.generate_content([
            "قدّم نصاً كاملاً لما يُقال في هذا الفيديو",
            {"mime_type": mime_type, "data": video_data}
        ])
        
        return response.text if hasattr(response, "text") else ""
    except Exception as e:
        return f"خطأ: {str(e)}"

# ===== دوال تحسين العربية =====
def improve_arabic_text(text: str, mode: str = "gemini", api_key: str = "") -> str:
    """تحسين النص العربي"""
    if not text:
        return ""
    
    if mode == "gemini" and api_key and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            prompt = "أعد صياغة النص التالي تصحيحاً لغوياً:\n\n" + text
            response = model.generate_content(prompt)
            return response.text if hasattr(response, "text") else text
        except Exception:
            pass
    
    text = text.replace(" ,", "،").replace(",", "،")
    text = text.replace(" ?", "؟").replace("?", "؟")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ===== التحليل الذكي =====
def analyze_full_post_with_gemini(tweet_data: Dict, api_key: str, user_instructions: str = "") -> Dict[str, Any]:
    """تحليل المنشور"""
    if not api_key or not GENAI_AVAILABLE:
        return {"error": "مفتاح Gemini مطلوب", "executive_summary": "(يتطلب API)"}
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        context_parts = []
        if tweet_data.get("text"):
            context_parts.append(f"نص المنشور:\n{tweet_data['text']}")
        if tweet_data.get("images_text"):
            context_parts.append(f"النص في الصور:\n{tweet_data['images_text']}")
        if tweet_data.get("video_transcript"):
            context_parts.append(f"تفريغ الفيديو:\n{tweet_data['video_transcript']}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""حلّل المحتوى التالي تحليلاً تنفيذياً:

المطلوب:
1. ملخص تنفيذي شامل
2. أبرز النقاط
3. المخاطر
4. التوصيات

{user_instructions if user_instructions else ''}

المحتوى:
{context if context else '(لا يوجد)'}

أرجع JSON:
{{
    "author": "الناشر",
    "executive_summary": "الملخص",
    "key_points": ["نقطة 1"],
    "risks": ["مخاطر"],
    "recommendations": ["توصيات"],
    "sentiment": "محايد"
}}
"""
        
        response = model.generate_content(prompt)
        text = response.text if hasattr(response, "text") else ""
        
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        return {"executive_summary": text, "author": tweet_data.get("author", "")}
        
    except Exception as e:
        return {"error": f"خطأ: {str(e)}", "executive_summary": "(فشل)"}

# ===== واجهة Streamlit =====
def main():
    st.set_page_config(
        page_title=f"{APP_NAME} v{APP_VERSION}",
        page_icon=APP_EMOJI,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
    
    """, unsafe_allow_html=True)
    
    st.title(f"{APP_EMOJI} {APP_NAME}")
    st.caption(f"الإصدار {APP_VERSION} — تحليل منشورات X/Twitter")
    
    with st.sidebar:
        st.header("⚙️ الإعدادات")
        
        gemini_key = st.text_input(
            "🔑 مفتاح Gemini API",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="احصل عليه من: https://aistudio.google.com/apikey"
        )
        
        st.subheader("📝 إعدادات التحليل")
        
        analysis_mode = st.selectbox(
            "وضع التحليل",
            options=["تحليل شامل", "تحليل سريع", "تحليل تفصيلي"],
            index=0
        )
        
        arabic_improve = st.checkbox("تحسين اللغة العربية", value=True)
        
        st.markdown("---")
        st.markdown("**📚 دليل الاستخدام:**")
        st.markdown("""
        1. أدخل رابط منشور X
        2. اضغط "جلب وتحليل"
        3. راجع الملخص التنفيذي
        """)
    
    tab1, tab2, tab3 = st.tabs(["🔗 تحليل بالرابط", "🖼️ تحليل صورة", "📚 دليل"])
    
    with tab1:
        st.markdown("### 🔗 أدخل رابط منشور X")
        
        tweet_url = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/123456789?s=20",
            help="يقبل روابط x.com و twitter.com"
        )
        
        if tweet_url:
            if is_tweet_url(tweet_url):
                tweet_id = extract_tweet_id(tweet_url)
                st.success(f"✅ رابط صالح | ID: `{tweet_id}`")
            else:
                st.error("❌ الرابط غير مدعوم")
                st.markdown("""
                **أمثلة:**
                - `https://x.com/user/status/123`
                - `https://twitter.com/user/status/123`
                """)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            fetch_btn = st.button("🔍 جلب وتحليل", type="primary", use_container_width=True)
        
        with col2:
            clear_btn = st.button("🗑️ مسح", use_container_width=True)
        
        if clear_btn:
            st.session_state.pop("tweet_result", None)
            st.session_state.pop("analysis_result", None)
            st.rerun()
        
        if fetch_btn and tweet_url:
            if not is_tweet_url(tweet_url):
                st.error("❌ الرابط غير صالح")
            elif not gemini_key:
                st.error("❌ أدخل مفتاح Gemini أولاً")
            else:
                status_box = st.empty()
                progress_bar = st.progress(0)
                
                with st.spinner("جاري التحليل..."):
                    try:
                        status_box.info("🔄 جلب المنشور...")
                        progress_bar.progress(20)
                        
                        tweet_data = fetch_tweet_with_media(tweet_url, gemini_key, status_box)
                        
                        if tweet_data.get("error"):
                            status_box.error(f"❌ {tweet_data['error']}")
                            progress_bar.empty()
                        else:
                            status_box.info("📝 تحسين النص...")
                            progress_bar.progress(50)
                            
                            if arabic_improve and tweet_data.get("text"):
                                tweet_data["text_improved"] = improve_arabic_text(
                                    tweet_data["text"], "gemini", gemini_key
                                )
                            
                            status_box.info("🤖 التحليل الذكي...")
                            progress_bar.progress(75)
                            
                            analysis = analyze_full_post_with_gemini(
                                tweet_data, gemini_key, f"وضع: {analysis_mode}"
                            )
                            
                            st.session_state["tweet_result"] = tweet_data
                            st.session_state["analysis_result"] = analysis
                            
                            status_box.success("✅ تم بنجاح!")
                            progress_bar.progress(100)
                            
                    except Exception as e:
                        status_box.error(f"❌ خطأ: {str(e)}")
                        progress_bar.empty()
                
                if st.session_state.get("tweet_result"):
                    st.markdown("---")
                    st.markdown("### 📊 نتائج التحليل")
                    
                    result = st.session_state["tweet_result"]
                    analysis = st.session_state.get("analysis_result", {})
                    
                    col_a1, col_a2, col_a3 = st.columns(3)
                    with col_a1:
                        st.metric("معرّف", result.get("tweet_id", "—"))
                    with col_a2:
                        st.metric("الناشر", result.get("author", "—"))
                    with col_a3:
                        st.metric("الوسائط", len(result.get("raw_images", [])))
                    
                    tab_r1, tab_r2, tab_r3 = st.tabs(["📝 النص", "🖼️ الصور", "🎬 الفيديو"])
                    
                    with tab_r1:
                        st.markdown("#### نص المنشور")
                        st.text_area("النص الأصلي", value=result.get("text", ""), height=150, disabled=True, label_visibility="collapsed")
                        
                        if result.get("text_improved"):
                            st.markdown("#### النص المحسّن ✨")
                            st.text_area("المحسّن", value=result["text_improved"], height=150, disabled=True, label_visibility="collapsed")
                        
                        st.markdown("---")
                        st.markdown("#### الملخص التنفيذي")
                        
                        if analysis.get("executive_summary"):
                            st.markdown(analysis["executive_summary"])
                        else:
                            st.info("لا يوجد ملخص")
                    
                    with tab_r2:
                        if result.get("images_text"):
                            st.markdown("#### النص من الصور")
                            st.text_area("نص الصور", value=result["images_text"], height=200, disabled=True, label_visibility="collapsed")
                        else:
                            st.info("لا يوجد")
                    
                    with tab_r3:
                        if result.get("video_transcript"):
                            st.markdown("#### تفريغ الفيديو")
                            st.text_area("التفريغ", value=result["video_transcript"], height=200, disabled=True, label_visibility="collapsed")
                        else:
                            st.info("لا يوجد")
    
    with tab2:
        st.markdown("### 🖼️ تحليل صورة مباشرة")
        
        uploaded_file = st.file_uploader(
            "ارفع صورة",
            type=["jpg", "jpeg", "png", "gif", "webp"],
            accept_multiple_files=False
        )
        
        if uploaded_file and gemini_key:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            st.image(uploaded_file, caption="الصورة", use_container_width=True)
            
            if st.button("🔍 تحليل", type="primary"):
                with st.spinner("جاري التحليل..."):
                    text = extract_text_from_post_image(tmp_path, gemini_key)
                    
                    if text:
                        st.success("✅ تم استخراج النص")
                        st.text_area("النص", value=text, height=150)
                    else:
                        st.warning("⚠️ لم يتم استخراج نص")
                
                try:
                    os.remove(tmp_path)
                except:
                    pass
    
    with tab3:
        st.markdown("""
        ### 📚 دليل الاستخدام
        
        #### الميزات:
        1. **دعم شامل**: x.com و twitter.com
        2. **OCR للصور**: قراءة النص
        3. **تفريغ الفيديو**: تحويل لنص
        4. **تحليل ذكي**: Gemini 2.0
        5. **تحسين العربية**: تصحيح لغوي
        
        #### الروابط المدعومة:
        ```
        ✅ https://x.com/user/status/123
        ✅ https://x.com/user/status/123?s=20
        ✅ https://twitter.com/user/status/123
        ```
        
        #### المتطلبات:
        - مفتاح Gemini API (مجاني)
        - Tesseract OCR
        - yt-dlp
        """)

if __name__ == "__main__":
    main()
