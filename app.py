# -*- coding: utf-8 -*-
"""
X (Twitter) Account & Post Analyzer — v8.0
Fixed: profile card, followers/following/posts, profile image, join date, location, verified
"""

import streamlit as st
import requests
import re
import json
import random
import base64
import time
from datetime import datetime
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
import google.generativeai as genai

# ─── إعدادات الصفحة ────────────────────────────────────────────────
st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS مخصص ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .profile-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1117 100%);
        border: 1px solid #1DA1F2;
        border-radius: 16px;
        padding: 24px;
        margin: 12px 0;
        direction: rtl;
        text-align: right;
    }
    .profile-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 16px;
        flex-direction: row-reverse;
    }
    .profile-avatar {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 3px solid #1DA1F2;
        object-fit: cover;
    }
    .profile-name {
        font-size: 22px;
        font-weight: bold;
        color: #e2e8f0;
    }
    .profile-username {
        font-size: 15px;
        color: #8899a6;
    }
    .verified-badge {
        color: #1DA1F2;
        font-size: 18px;
    }
    .stat-box {
        background: rgba(29, 161, 242, 0.1);
        border-radius: 10px;
        padding: 12px;
        text-align: center;
    }
    .stat-number {
        font-size: 20px;
        font-weight: bold;
        color: #1DA1F2;
    }
    .stat-label {
        font-size: 12px;
        color: #8899a6;
    }
    .info-row {
        color: #b0bec5;
        font-size: 14px;
        margin: 4px 0;
        direction: rtl;
    }
    .source-badge {
        background: #1DA1F2;
        color: white;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        display: inline-block;
        margin-top: 8px;
    }
    div[data-testid="stMetricValue"] {
        color: #1DA1F2;
    }
    .stTabs [data-baseweb="tab-list"] {
        direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

# ─── ثوابت ──────────────────────────────────────────────────────────
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I6xUzrxb%2F5MoHmP1LLMEBPKdpv%2Fw%3D"

GRAPHQL_IDS = [
    "Sfq_BSQ7VVpC3u9ycqwKYg",
    "32pL5BWe9WKeSK1MoPvFQQ",
    "G3KGOASz96M-Kg0ydkdm_A",
    "qW5u-DAuXpMEG0zA1F7UGQ",
    "BQ6xjFU6Mgm-WhZquxI_mg",
]

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://nitter.moomoo.me",
    "https://nitter.it",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# ─── Regex ──────────────────────────────────────────────────────────
TWEET_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/(\d+)(?:[/?#].*)?$",
    re.I
)
PROFILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(@?\w+)(?:[/?#].*)?$",
    re.I
)

# ─── مساعدات ────────────────────────────────────────────────────────
def format_number(n) -> str:
    """تنسيق الأرقام الكبيرة."""
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except (ValueError, TypeError):
        return "—"

def extract_username_from_url(url: str) -> str | None:
    """استخراج اسم المستخدم من رابط X/Twitter أو نص مباشر."""
    if not url:
        return None
    # إزالة query string وfragment
    url_clean = re.sub(r'[?#].*$', '', url.strip())
    
    # تجاهل روابط التغريدات
    if TWEET_URL_RE.search(url_clean):
        return None
    
    m = PROFILE_URL_RE.search(url_clean)
    if m:
        return m.group(1).lstrip("@").strip()
    
    # فحص يدوي للنطاقات
    for domain in ["x.com/", "twitter.com/"]:
        if domain in url_clean:
            parts = url_clean.split(domain)
            if len(parts) > 1:
                candidate = parts[1].split("/")[0].strip()
                if candidate and re.match(r'^\w+$', candidate):
                    return candidate
    
    # نص مباشر (مثل @ghamao0 أو ghamao0)
    clean = url.lstrip("@").strip()
    if re.match(r'^\w+$', clean):
        return clean
    
    return None

def extract_tweet_id(url: str) -> str | None:
    """استخراج معرف التغريدة من رابط."""
    m = TWEET_URL_RE.search(url)
    return m.group(1) if m else None

def image_to_base64(url: str) -> str | None:
    """تحويل صورة URL إلى base64."""
    try:
        url_hq = re.sub(r'_normal|_bigger|_mini', '_400x400', url)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url_hq, headers=headers, timeout=10)
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
        # fallback: الحجم الاعتيادي
        resp2 = requests.get(url, headers=headers, timeout=10)
        if resp2.status_code == 200:
            return base64.b64encode(resp2.content).decode()
    except Exception:
        pass
    return None

# ─── جلب البيانات: Twitter Guest API ────────────────────────────────
def get_guest_token() -> str | None:
    """الحصول على Guest Token."""
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": random.choice(USER_AGENTS),
    }
    try:
        resp = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("guest_token")
    except Exception:
        pass
    return None

def fetch_via_guest_api(username: str) -> dict | None:
    """جلب بيانات الحساب عبر Twitter Guest API GraphQL."""
    guest_token = get_guest_token()
    if not guest_token:
        return None
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "x-guest-token": guest_token,
        "User-Agent": random.choice(USER_AGENTS),
        "Content-Type": "application/json",
        "Accept": "*/*",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
    }
    
    variables = json.dumps({
        "screen_name": username,
        "withSafetyModeUserFields": True,
    })
    features = json.dumps({
        "hidden_profile_likes_enabled": True,
        "hidden_profile_subscriptions_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "subscriptions_verification_info_verified_since_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "responsive_web_twitter_article_notes_tab_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    })
    
    for qid in GRAPHQL_IDS:
        try:
            url = f"https://twitter.com/i/api/graphql/{qid}/UserByScreenName"
            params = {"variables": variables, "features": features}
            resp = requests.get(url, headers=headers, params=params, timeout=12)
            
            if resp.status_code != 200:
                continue
            
            data = resp.json()
            user = (
                data.get("data", {})
                    .get("user", {})
                    .get("result", {})
            )
            
            if not user:
                continue
            
            legacy = user.get("legacy", {})
            if not legacy:
                continue
            
            # استخراج تاريخ الانضمام
            created_at_raw = legacy.get("created_at", "")
            join_date = ""
            if created_at_raw:
                try:
                    dt = datetime.strptime(created_at_raw, "%a %b %d %H:%M:%S +0000 %Y")
                    join_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    join_date = created_at_raw
            
            return {
                "username": legacy.get("screen_name", username),
                "display_name": legacy.get("name", ""),
                "bio": legacy.get("description", ""),
                "location": legacy.get("location", ""),
                "followers_count": legacy.get("followers_count", 0),
                "following_count": legacy.get("friends_count", 0),
                "posts_count": legacy.get("statuses_count", 0),
                "profile_image_url": legacy.get("profile_image_url_https", "").replace("_normal", "_400x400"),
                "join_date": join_date,
                "verified": legacy.get("verified", False),
                "is_blue_verified": user.get("is_blue_verified", False),
                "tweets": [],
                "source": f"guest_api_{qid[:8]}",
            }
        except Exception:
            continue
    
    return None

# ─── جلب البيانات: FxTwitter API ─────────────────────────────────────
def fetch_via_fxtwitter(username: str, tweet_id: str | None = None) -> dict | None:
    """جلب بيانات عبر FxTwitter API (يعمل بدون مصادقة)."""
    if not tweet_id:
        return None
    
    try:
        url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(url, headers=headers, timeout=12)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        tweet = data.get("tweet", {})
        author = tweet.get("author", {})
        
        if not author:
            return None
        
        return {
            "username": author.get("screen_name", username),
            "display_name": author.get("name", ""),
            "bio": author.get("description", ""),
            "location": author.get("location", ""),
            "followers_count": author.get("followers", 0),
            "following_count": author.get("following", 0),
            "posts_count": author.get("tweets", 0),
            "profile_image_url": author.get("avatar_url", "").replace("_normal", "_400x400"),
            "join_date": author.get("created_at", ""),
            "verified": author.get("verified", False),
            "is_blue_verified": author.get("is_blue_verified", False),
            "tweets": [tweet] if tweet else [],
            "source": "fxtwitter",
        }
    except Exception:
        pass
    return None

# ─── جلب البيانات: Nitter ─────────────────────────────────────────────
def fetch_via_nitter(username: str) -> dict | None:
    """جلب بيانات من مرايا Nitter."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    random.shuffle(NITTER_MIRRORS)
    for mirror in NITTER_MIRRORS:
        try:
            url = f"{mirror}/{username}"
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            if resp.status_code != 200:
                continue
            if "captcha" in resp.text.lower() or "rate limit" in resp.text.lower():
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # استخراج الاسم
            name_el = soup.select_one(".profile-card-fullname, .fullname")
            display_name = name_el.get_text(strip=True) if name_el else ""
            
            # اسم المستخدم
            uname_el = soup.select_one(".profile-card-username, .username")
            uname = uname_el.get_text(strip=True).lstrip("@") if uname_el else username
            
            # Bio
            bio_el = soup.select_one(".profile-bio, .bio")
            bio = bio_el.get_text(strip=True) if bio_el else ""
            
            # الموقع
            loc_el = soup.select_one(".profile-location span, .profile-card-extra .location span")
            location = loc_el.get_text(strip=True) if loc_el else ""
            
            # تاريخ الانضمام
            join_el = soup.select_one(".profile-joindate span[title], .profile-card-extra .join-date span")
            join_date = join_el.get("title", "") if join_el else ""
            
            # صورة الحساب
            avatar_el = soup.select_one(".profile-card-avatar img, .avatar img")
            avatar_url = ""
            if avatar_el:
                avatar_url = avatar_el.get("src", "")
                if avatar_url and not avatar_url.startswith("http"):
                    avatar_url = mirror + avatar_url
            
            # الإحصاءات
            def parse_stat(selector: str, alt_selector: str = "") -> int:
                el = soup.select_one(selector)
                if not el and alt_selector:
                    el = soup.select_one(alt_selector)
                if el:
                    val = el.get_text(strip=True).replace(",", "").replace(".", "").replace(" ", "")
                    match = re.search(r'\d+', val)
                    return int(match.group()) if match else 0
                return 0
            
            followers = parse_stat(".followers .profile-stat-num", ".profile-stat-header:contains('Followers') + .profile-stat-num")
            following = parse_stat(".following .profile-stat-num", ".profile-stat-header:contains('Following') + .profile-stat-num")
            posts = parse_stat(".tweets .profile-stat-num", ".profile-stat-header:contains('Tweets') + .profile-stat-num")
            
            # إذا فشل الاستخراج، ابحث بطريقة بديلة
            if followers == 0 and following == 0:
                stats = soup.select(".profile-stat-num")
                stat_headers = soup.select(".profile-stat-header")
                for i, header in enumerate(stat_headers):
                    h_text = header.get_text(strip=True).lower()
                    val_text = stats[i].get_text(strip=True).replace(",", "") if i < len(stats) else "0"
                    val_match = re.search(r'[\d]+', val_text)
                    val = int(val_match.group()) if val_match else 0
                    if "follow" in h_text and "ing" in h_text:
                        following = val
                    elif "follow" in h_text:
                        followers = val
                    elif "tweet" in h_text or "post" in h_text:
                        posts = val
            
            # التحقق من البيانات المستخرجة
            if not display_name and followers == 0 and not bio:
                continue
            
            # التغريدات
            tweets = []
            for item in soup.select(".timeline-item, .tweet-body")[:20]:
                text_el = item.select_one(".tweet-content, .tweet-text")
                date_el = item.select_one(".tweet-date a, time")
                if text_el:
                    tweets.append({
                        "text": text_el.get_text(strip=True),
                        "date": date_el.get_text(strip=True) if date_el else "",
                    })
            
            return {
                "username": uname,
                "display_name": display_name,
                "bio": bio,
                "location": location,
                "followers_count": followers,
                "following_count": following,
                "posts_count": posts,
                "profile_image_url": avatar_url,
                "join_date": join_date,
                "verified": False,
                "is_blue_verified": False,
                "tweets": tweets,
                "source": f"nitter_{mirror.split('//')[1].split('/')[0]}",
            }
        except Exception:
            continue
    
    return None

# ─── الدالة الرئيسية للجلب ──────────────────────────────────────────
def fetch_user_data(username: str, tweet_id: str | None = None) -> tuple[dict | None, str]:
    """جلب بيانات الحساب بنظام الفال‑باك الثلاثي."""
    username = username.replace("@", "").strip()
    
    # 1. Twitter Guest API (الأفضل - يعطي كل البيانات)
    with st.spinner("🔍 جاري المحاولة عبر Twitter Guest API..."):
        data = fetch_via_guest_api(username)
        if data and (data.get("followers_count", 0) > 0 or data.get("display_name")):
            return data, data.get("source", "guest_api")
    
    # 2. FxTwitter (يحتاج tweet_id)
    if tweet_id:
        with st.spinner("🔄 جاري المحاولة عبر FxTwitter..."):
            data = fetch_via_fxtwitter(username, tweet_id)
            if data:
                return data, "fxtwitter"
    
    # 3. Nitter (الملاذ الأخير)
    with st.spinner("🔁 المصدر الاحتياطي: Nitter..."):
        data = fetch_via_nitter(username)
        if data:
            return data, data.get("source", "nitter")
    
    # فشل جميع المصادر
    return None, "failed"

# ─── عرض بطاقة الحساب ───────────────────────────────────────────────
def render_profile_card(data: dict):
    """عرض بطاقة الحساب الكاملة مع صورة وإحصاءات."""
    username = data.get("username", "")
    display_name = data.get("display_name", username)
    bio = data.get("bio", "")
    location = data.get("location", "")
    join_date = data.get("join_date", "")
    followers = data.get("followers_count", 0)
    following = data.get("following_count", 0)
    posts = data.get("posts_count", 0)
    verified = data.get("verified", False)
    is_blue = data.get("is_blue_verified", False)
    profile_img_url = data.get("profile_image_url", "")
    source = data.get("source", "")
    
    # تحويل الصورة لـ base64
    img_html = ""
    if profile_img_url:
        b64 = image_to_base64(profile_img_url)
        if b64:
            img_html = f'<img class="profile-avatar" src="data:image/jpeg;base64,{b64}" alt="صورة الحساب" />'
        else:
            img_html = f'<img class="profile-avatar" src="{profile_img_url}" alt="صورة الحساب" onerror="this.style.display=\'none\'" />'
    else:
        img_html = '<div style="width:80px;height:80px;border-radius:50%;background:#1DA1F2;display:flex;align-items:center;justify-content:center;font-size:32px;border:3px solid #1DA1F2;">👤</div>'
    
    # شارة التوثيق
    badge = ""
    if is_blue:
        badge = ' <span title="موثق ✓" style="color:#1DA1F2;">✓</span>'
    elif verified:
        badge = ' <span title="موثق رسمي" style="color:#FFD700;">★</span>'
    
    # مصدر البيانات بالعربي
    source_labels = {
        "fxtwitter": "FxTwitter",
        "nitter": "Nitter",
        "manual": "يدوي",
    }
    for key, label in source_labels.items():
        if key in source:
            source_display = label
            break
    else:
        source_display = "Twitter API" if "guest" in source or "api" in source.lower() else source
    
    # HTML البطاقة
    card_html = f"""
    <div class="profile-card">
        <div class="profile-header">
            {img_html}
            <div>
                <div class="profile-name">{display_name}{badge}</div>
                <div class="profile-username">@{username}</div>
                <span class="source-badge">📡 {source_display}</span>
            </div>
        </div>
        
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:16px 0;">
            <div class="stat-box">
                <div class="stat-number">{format_number(followers)}</div>
                <div class="stat-label">👥 متابعون</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{format_number(following)}</div>
                <div class="stat-label">➡️ يتابع</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{format_number(posts)}</div>
                <div class="stat-label">📝 منشورات</div>
            </div>
        </div>
        
        {"<div class='info-row'>📄 " + bio + "</div>" if bio else ""}
        {"<div class='info-row'>📍 " + location + "</div>" if location else ""}
        {"<div class='info-row'>📅 تاريخ الانضمام: " + join_date + "</div>" if join_date else ""}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

# ─── تحليل Gemini ───────────────────────────────────────────────────
def analyze_with_gemini(model, data: dict, analysis_type: str = "account") -> str:
    """إرسال البيانات لـ Gemini للتحليل."""
    if analysis_type == "account":
        prompt = f"""
أنت محلل OSINT متخصص في تحليل حسابات X (تويتر). 
قم بتحليل الحساب التالي وتقديم تقرير مفصل بالعربية:

المعلومات:
- اسم المستخدم: @{data.get('username', '')}
- الاسم المعروض: {data.get('display_name', '')}
- الوصف: {data.get('bio', '')}
- الموقع: {data.get('location', '')}
- المتابعون: {format_number(data.get('followers_count', 0))}
- يتابع: {format_number(data.get('following_count', 0))}
- عدد المنشورات: {format_number(data.get('posts_count', 0))}
- تاريخ الانضمام: {data.get('join_date', '')}
- موثق: {'نعم' if data.get('is_blue_verified') or data.get('verified') else 'لا'}

التغريدات الأخيرة:
{chr(10).join([f"- {t.get('text', '')[:200]}" for t in data.get('tweets', [])[:10]])}

قدم تحليلاً شاملاً يتضمن:
1. نظرة عامة على الحساب
2. نسبة الانخراط (engagement)
3. أنماط النشر
4. المحتوى والاهتمامات
5. مؤشرات المصداقية
6. التوصيات
"""
    else:
        prompt = f"حلل هذا المنشور من X:\n\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في التحليل: {str(e)}"

# ─── الشريط الجانبي ──────────────────────────────────────────────────
def setup_sidebar() -> tuple:
    """إعداد الشريط الجانبي."""
    with st.sidebar:
        st.title("⚙️ الإعدادات")
        st.markdown("---")
        
        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            help="احصل عليه من: https://aistudio.google.com/apikey"
        )
        
        if api_key:
            try:
                genai.configure(api_key=api_key)
                model_name = st.selectbox(
                    "🤖 نموذج Gemini",
                    ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
                    index=0
                )
                model = genai.GenerativeModel(model_name)
                st.success("✅ مفتاح API صحيح")
                return api_key, model
            except Exception as e:
                st.error(f"❌ خطأ: {e}")
        else:
            st.info("أدخل مفتاح API لتفعيل التحليل الذكي")
        
        st.markdown("---")
        st.markdown("""
        <div style='text-align:center; color:#8899a6; font-size:12px; direction:rtl;'>
        محلل حسابات X — الإصدار 8.0<br>
        بواسطة: فريق التطوير
        </div>
        """, unsafe_allow_html=True)
    
    return None, None

# ─── تبويب تحليل الحساب ─────────────────────────────────────────────
def account_tab(model):
    """واجهة تحليل الحساب."""
    st.markdown("## 👤 تحليل حساب X")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        profile_input = st.text_input(
            "🔗 أدخل رابط الحساب أو اسم المستخدم",
            placeholder="مثال: https://x.com/username أو @username",
            label_visibility="collapsed"
        )
    with col2:
        analyze_btn = st.button("🔍 تحليل", use_container_width=True, type="primary")
    
    if analyze_btn and profile_input:
        # استخراج اسم المستخدم
        username = extract_username_from_url(profile_input)
        
        if not username:
            clean = profile_input.lstrip("@").strip()
            if re.match(r'^\w+$', clean):
                username = clean
            else:
                st.error("⚠️ تعذر استخراج اسم المستخدم. حاول إدخال @username مباشرة.")
                return
        
        st.info(f"🔍 جاري تحليل: **@{username}**")
        
        # محاولة استخراج tweet_id إن وجد
        tweet_id = extract_tweet_id(profile_input)
        
        # جلب البيانات
        data, source = fetch_user_data(username, tweet_id)
        
        if data:
            st.success(f"✅ تم جلب البيانات من: **{source}**")
            
            # عرض بطاقة الحساب
            render_profile_card(data)
            
            # تحليل Gemini
            if model:
                st.markdown("---")
                st.markdown("### 🤖 التحليل الذكي")
                with st.spinner("⏳ جاري تحليل الحساب..."):
                    analysis = analyze_with_gemini(model, data, "account")
                st.markdown(analysis)
            else:
                st.info("💡 أدخل مفتاح Gemini API في الشريط الجانبي للحصول على تحليل ذكي مفصل.")
        else:
            st.error("❌ تعذر جلب بيانات الحساب من جميع المصادر.")
            st.markdown("""
            **أسباب محتملة:**
            - الحساب خاص أو محذوف
            - Twitter/X يحجب طلبات Streamlit Cloud
            - تجاوز حد الطلبات (Rate Limit)
            
            **الحل:** أدخل البيانات يدوياً:
            """)
            
            with st.expander("📝 إدخال البيانات يدوياً"):
                c1, c2 = st.columns(2)
                with c1:
                    m_followers = st.number_input("المتابعون", 0, step=1)
                    m_following = st.number_input("يتابع", 0, step=1)
                    m_posts = st.number_input("المنشورات", 0, step=1)
                with c2:
                    m_name = st.text_input("الاسم المعروض")
                    m_bio = st.text_area("الوصف")
                    m_location = st.text_input("الموقع")
                    m_join = st.text_input("تاريخ الانضمام")
                
                if st.button("✅ تطبيق البيانات"):
                    manual_data = {
                        "username": username,
                        "display_name": m_name,
                        "bio": m_bio,
                        "location": m_location,
                        "followers_count": m_followers,
                        "following_count": m_following,
                        "posts_count": m_posts,
                        "profile_image_url": "",
                        "join_date": m_join,
                        "verified": False,
                        "is_blue_verified": False,
                        "tweets": [],
                        "source": "manual",
                    }
                    render_profile_card(manual_data)
                    if model:
                        analysis = analyze_with_gemini(model, manual_data, "account")
                        st.markdown(analysis)

# ─── تبويب تحليل المنشور ─────────────────────────────────────────────
def tweet_tab(model):
    """واجهة تحليل منشور."""
    st.markdown("## 📝 تحليل منشور X")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        tweet_url = st.text_input(
            "🔗 أدخل رابط المنشور",
            placeholder="مثال: https://x.com/username/status/1234567890",
            label_visibility="collapsed"
        )
    with col2:
        analyze_btn = st.button("🔍 تحليل المنشور", use_container_width=True, type="primary")
    
    # رفع صورة
    uploaded = st.file_uploader(
        "📷 أو ارفع صورة لتحليلها",
        type=["jpg", "jpeg", "png", "webp"],
        help="يمكنك رفع لقطة شاشة للمنشور"
    )
    
    if analyze_btn and (tweet_url or uploaded):
        tweet_id = extract_tweet_id(tweet_url) if tweet_url else None
        
        if tweet_id:
            # استخراج اسم المستخدم من الرابط
            m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/", tweet_url, re.I)
            username = m.group(1) if m else "unknown"
            
            with st.spinner("🔄 جاري جلب بيانات المنشور..."):
                data = fetch_via_fxtwitter(username, tweet_id)
            
            if data:
                st.success("✅ تم جلب المنشور")
                render_profile_card(data)
                
                # عرض المنشور
                tweets = data.get("tweets", [])
                if tweets:
                    tweet = tweets[0]
                    st.markdown(f"""
                    <div style="background:#1a1f2e;border:1px solid #1DA1F2;border-radius:12px;padding:16px;margin:12px 0;direction:rtl;">
                        <p style="color:#e2e8f0;font-size:15px;">{tweet.get('text', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                if model:
                    with st.spinner("⏳ جاري التحليل..."):
                        analysis = analyze_with_gemini(model, data, "tweet")
                    st.markdown(analysis)
            else:
                st.error("❌ تعذر جلب بيانات المنشور.")
        
        elif uploaded:
            # تحليل الصورة المرفوعة
            st.image(uploaded, caption="الصورة المرفوعة", width=400)
            if model:
                with st.spinner("⏳ جاري تحليل الصورة..."):
                    img = Image.open(uploaded)
                    prompt = "حلل هذه الصورة من منشور X وقدم تقريراً مفصلاً بالعربية."
                    response = model.generate_content([prompt, img])
                    st.markdown(response.text)
        else:
            st.warning("⚠️ الرابط لا يحتوي على معرف منشور صحيح.")

# ─── الدالة الرئيسية ─────────────────────────────────────────────────
def main():
    """الدالة الرئيسية للتطبيق."""
    st.markdown("""
    <div style='text-align:center; padding:10px 0; direction:rtl;'>
        <h1 style='color:#1DA1F2;'>🔍 محلل حسابات X</h1>
        <p style='color:#8899a6;'>تحليل استخباراتي متقدم لحسابات X (تويتر)</p>
    </div>
    """, unsafe_allow_html=True)
    
    _, model = setup_sidebar()
    
    tab1, tab2 = st.tabs(["👤 تحليل حساب", "📝 تحليل منشور"])
    
    with tab1:
        account_tab(model)
    
    with tab2:
        tweet_tab(model)


if __name__ == "__main__":
    main()
