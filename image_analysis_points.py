```python
# -*- coding: utf-8 -*-
"""
محلل حسابات X (تويتر) — الإصدار 8.0
X Account & Post Analyzer v8.0
"""

import streamlit as st
import requests
import re
import json
import random
import base64
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
import google.generativeai as genai

# ════════════════════════════════════════════════════════════════════
# إعدادات الصفحة — يجب أن تكون أول أمر Streamlit
# ════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="محلل حسابات X",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ════════════════════════════════════════════════════════════════════
# بيانات نقاط التحليل (Image Analysis Points)
# ════════════════════════════════════════════════════════════════════
IMAGE_ANALYSIS_POINTS: List[Dict[str, Any]] = [
    {
        "section": "الهوية البصرية العامة",
        "points": [
            "وصف المشهد العام للصورة بشكل مختصر ودقيق",
            "تحديد نوع الصورة: شخصية، خبرية، دعائية، ميدانية، رسم بياني، لقطة شاشة، أو غير ذلك",
            "تقدير جودة الصورة ووضوحها وما إذا كانت معدلة أو مضغوطة بشكل كبير",
            "تحديد ما إذا كانت الصورة أصلية أو تبدو إعادة نشر أو إعادة تدوير"
        ]
    },
    {
        "section": "العناصر البشرية",
        "points": [
            "رصد الأشخاص الظاهرين في الصورة وعددهم التقريبي",
            "تقدير الفئة العمرية والجنس بشكل غير جازم عند الإمكان",
            "تحليل اللباس والمظهر العام وما إذا كان رسميًا أو عسكريًا أو مدنيًا أو رمزيًا",
            "تحليل لغة الجسد وتعابير الوجه والانفعالات العامة",
            "رصد أي إشارات إلى انتماء تنظيمي أو مؤسسي أو أمني"
        ]
    },
    {
        "section": "العناصر المادية والمكانية",
        "points": [
            "تحديد الموقع الظاهر بصريًا إن أمكن: شارع، مكتب، منشأة، ساحة، بيئة صحراوية، منطقة حضرية",
            "وصف الأشياء البارزة مثل المركبات، الأجهزة، الأسلحة، اللافتات، المباني، الشاشات",
            "تحليل الخلفية والعناصر الثانوية التي قد تحمل مؤشرات مهمة",
            "رصد أي معالم جغرافية أو عمرانية أو لوجستية"
        ]
    },
    {
        "section": "النصوص والشعارات والرموز",
        "points": [
            "استخراج أي نص ظاهر داخل الصورة بشكل حرفي قدر الإمكان",
            "تحديد اللغة المستخدمة في النصوص أو اللافتات",
            "رصد الشعارات والرموز والأعلام والهوية المؤسسية أو السياسية أو العسكرية",
            "تحليل دلالة النص أو الشعار في سياق الرسالة العامة للصورة"
        ]
    },
    {
        "section": "السياق الإعلامي والدعائي",
        "points": [
            "تقدير الهدف المرجح من نشر الصورة: إخباري، تعبوي، ترويجي، تشويه، توثيق، تضليل",
            "تحليل الرسالة المركزية التي تحاول الصورة إيصالها",
            "تحديد الجمهور المستهدف المحتمل",
            "تقييم ما إذا كانت الصورة مصممة للتأثير النفسي أو العاطفي أو السياسي"
        ]
    },
    {
        "section": "المؤشرات الاستخباراتية",
        "points": [
            "استخراج المؤشرات السلوكية أو الأمنية أو العملياتية الظاهرة في الصورة",
            "تحديد أي مؤشرات على نشاط منظم أو تنسيق جماعي",
            "رصد ما إذا كانت الصورة تحتوي على دلالات زمنية أو مكانية قابلة للاستثمار التحليلي",
            "تقييم احتمالية ارتباط الصورة بحدث حقيقي أو حملة معلوماتية"
        ]
    },
    {
        "section": "مؤشرات التلاعب والمصداقية",
        "points": [
            "البحث عن مؤشرات التعديل أو القص أو الإخفاء أو التركيب",
            "تقييم اتساق الظلال والإضاءة والعناصر البصرية",
            "تحديد ما إذا كانت الصورة قديمة أُعيد استخدامها في سياق جديد",
            "تقدير مستوى الثقة البصري في الصورة من 1 إلى 10"
        ]
    },
    {
        "section": "التقييم النهائي",
        "points": [
            "تقديم خلاصة تنفيذية قصيرة للصورة",
            "تحديد مستوى الخطورة أو الحساسية إن وجد",
            "اقتراح التوصيات التحليلية أو التحقق الإضافي المطلوب",
            "تحديد الكلمات المفتاحية المناسبة للأرشفة أو المتابعة"
        ]
    }
]

IMAGE_ANALYSIS_SCHEMA: Dict[str, Any] = {
    "ملخص_تنفيذي": "خلاصة مركزة عن الصورة ورسالتها العامة",
    "وصف_بصري_عام": {
        "نوع_الصورة": "شخصية/خبرية/دعائية/ميدانية/لقطة شاشة/غير ذلك",
        "وصف_المشهد": "وصف مختصر للمشهد",
        "جودة_الصورة": "مرتفعة/متوسطة/منخفضة"
    },
    "العناصر_المرصودة": {
        "أشخاص": [],
        "أشياء_ومعدات": [],
        "نصوص_ظاهرة": [],
        "شعارات_ورموز": [],
        "مؤشرات_مكانية": []
    },
    "التحليل_الدلالي": {
        "الرسالة_المحتملة": "",
        "الهدف_المرجح": "إخباري/دعائي/تحريضي/توثيقي/ترويجي",
        "الجمهور_المستهدف": "",
        "الأثر_النفسي": ""
    },
    "المؤشرات_استخباراتية": {
        "مؤشرات_أمنية": [],
        "مؤشرات_تنظيمية": [],
        "مؤشرات_زمنية_ومكانية": [],
        "احتمال_الارتباط_بحملة_معلوماتية": "مرتفع/متوسط/منخفض"
    },
    "تقييم_المصداقية": {
        "مؤشرات_التلاعب": [],
        "احتمال_إعادة_الاستخدام": "مرتفع/متوسط/منخفض",
        "مستوى_الثقة_البصري": 7
    },
    "مستوى_الخطورة": "منخفض/متوسط/مرتفع",
    "توصيات": [],
    "كلمات_مفتاحية": []
}


def format_analysis_points_for_prompt(points=None) -> str:
    source = points if points is not None else IMAGE_ANALYSIS_POINTS
    blocks = []
    for section in source:
        name = section.get("section", "")
        bullets = "\n".join([f"- {p}" for p in section.get("points", [])])
        blocks.append(f"### {name}\n{bullets}")
    return "\n\n".join(blocks)


def build_image_analysis_prompt(
    post_text: str = "",
    account_name: str = "",
    account_username: str = "",
    extra_context: str = "",
    strict_json: bool = True
) -> str:
    points_text = format_analysis_points_for_prompt()
    schema_text = json.dumps(IMAGE_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2)
    identity_lines = []
    if account_name:
        identity_lines.append(f"- اسم الحساب: {account_name}")
    if account_username:
        identity_lines.append(f"- المعرف: @{account_username}")
    if post_text:
        identity_lines.append(f"- نص المنشور: {post_text}")
    if extra_context:
        identity_lines.append(f"- سياق إضافي: {extra_context}")
    identity_text = "\n".join(identity_lines) if identity_lines else "- لا توجد بيانات إضافية"

    prompt = f"""أنت محلل استخباراتي متخصص في تحليل الصور المنشورة على منصة X.

## البيانات المساندة
{identity_text}

## نقاط التحليل
{points_text}

## تعليمات
- اكتب التحليل باللغة العربية
- كن دقيقاً ومهنياً
- ميّز بين الحقائق المرئية والتقديرات التحليلية

## صيغة الإخراج
{schema_text}
""".strip()

    if strict_json:
        prompt += "\n\nأعد النتيجة بصيغة JSON فقط."
    return prompt


# ════════════════════════════════════════════════════════════════════
# CSS مخصص
# ════════════════════════════════════════════════════════════════════
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
        color: #8899a6;
        font-size: 15px;
    }
    .stat-box {
        background: rgba(29,161,242,0.1);
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
    .stTabs [data-baseweb="tab-list"] { direction: rtl; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# ثوابت
# ════════════════════════════════════════════════════════════════════
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

TWEET_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/(\d+)(?:[/?#].*)?$", re.I
)
PROFILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/(@?\w+)(?:[/?#].*)?$", re.I
)


# ════════════════════════════════════════════════════════════════════
# دوال مساعدة
# ════════════════════════════════════════════════════════════════════
def format_number(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except (ValueError, TypeError):
        return "0"


def extract_username_from_url(url: str):
    if not url:
        return None
    url_clean = re.sub(r'[?#].*$', '', url.strip())
    if TWEET_URL_RE.search(url_clean):
        return None
    m = PROFILE_URL_RE.search(url_clean)
    if m:
        return m.group(1).lstrip("@").strip()
    for domain in ["x.com/", "twitter.com/"]:
        if domain in url_clean:
            parts = url_clean.split(domain)
            if len(parts) > 1:
                candidate = parts[1].split("/")[0].strip()
                if candidate and re.match(r'^\w+$', candidate):
                    return candidate
    clean = url.lstrip("@").strip()
    if re.match(r'^\w+$', clean):
        return clean
    return None


def extract_tweet_id(url: str):
    m = TWEET_URL_RE.search(url)
    return m.group(1) if m else None


def image_to_base64(url: str):
    if not url:
        return None
    try:
        url_hq = re.sub(r'_normal|_bigger|_mini', '_400x400', url)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        for try_url in [url_hq, url]:
            try:
                resp = requests.get(try_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    return base64.b64encode(buf.getvalue()).decode()
            except Exception:
                continue
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════════════
# جلب البيانات: Twitter Guest API
# ════════════════════════════════════════════════════════════════════
def get_guest_token():
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": random.choice(USER_AGENTS),
    }
    try:
        resp = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json",
            headers=headers, timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("guest_token")
    except Exception:
        pass
    return None


def fetch_via_guest_api(username: str):
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

    variables = json.dumps({"screen_name": username, "withSafetyModeUserFields": True})
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
            resp = requests.get(
                url, headers=headers,
                params={"variables": variables, "features": features},
                timeout=12
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            user = data.get("data", {}).get("user", {}).get("result", {})
            if not user:
                continue
            legacy = user.get("legacy", {})
            if not legacy:
                continue

            created_raw = legacy.get("created_at", "")
            join_date = ""
            if created_raw:
                try:
                    dt = datetime.strptime(created_raw, "%a %b %d %H:%M:%S +0000 %Y")
                    join_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    join_date = created_raw

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


# ════════════════════════════════════════════════════════════════════
# جلب البيانات: FxTwitter
# ════════════════════════════════════════════════════════════════════
def fetch_via_fxtwitter(username: str, tweet_id=None):
    if not tweet_id:
        return None
    try:
        url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
        resp = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=12)
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


# ════════════════════════════════════════════════════════════════════
# جلب البيانات: Nitter
# ════════════════════════════════════════════════════════════════════
def fetch_via_nitter(username: str):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }
    mirrors = NITTER_MIRRORS[:]
    random.shuffle(mirrors)
    for mirror in mirrors:
        try:
            resp = requests.get(f"{mirror}/{username}", headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                continue
            if "captcha" in resp.text.lower() or "rate limit" in resp.text.lower():
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            name_el = soup.select_one(".profile-card-fullname, .fullname")
            display_name = name_el.get_text(strip=True) if name_el else ""

            bio_el = soup.select_one(".profile-bio, .bio")
            bio = bio_el.get_text(strip=True) if bio_el else ""

            loc_el = soup.select_one(".profile-location span")
            location = loc_el.get_text(strip=True) if loc_el else ""

            join_el = soup.select_one(".profile-joindate span[title]")
            join_date = join_el.get("title", "") if join_el else ""

            avatar_el = soup.select_one(".profile-card-avatar img, .avatar img")
            avatar_url = ""
            if avatar_el:
                src = avatar_el.get("src", "")
                avatar_url = src if src.startswith("http") else mirror + src

            def get_stat(sel):
                el = soup.select_one(sel)
                if el:
                    val = re.sub(r'[^\d]', '', el.get_text())
                    return int(val) if val else 0
                return 0

            followers = get_stat(".followers .profile-stat-num")
            following = get_stat(".following .profile-stat-num")
            posts = get_stat(".tweets .profile-stat-num")

            if not display_name and followers == 0 and not bio:
                continue

            tweets = []
            for item in soup.select(".timeline-item")[:20]:
                text_el = item.select_one(".tweet-content")
                if text_el:
                    date_el = item.select_one(".tweet-date a")
                    tweets.append({
                        "text": text_el.get_text(strip=True),
                        "date": date_el.get_text(strip=True) if date_el else "",
                    })

            return {
                "username": username,
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


# ════════════════════════════════════════════════════════════════════
# الدالة الرئيسية للجلب
# ════════════════════════════════════════════════════════════════════
def fetch_user_data(username: str, tweet_id=None):
    username = username.replace("@", "").strip()

    with st.spinner("جاري البحث عبر Twitter API..."):
        data = fetch_via_guest_api(username)
        if data and (data.get("followers_count", 0) > 0 or data.get("display_name")):
            return data, data.get("source", "guest_api")

    if tweet_id:
        with st.spinner("جاري البحث عبر FxTwitter..."):
            data = fetch_via_fxtwitter(username, tweet_id)
            if data:
                return data, "fxtwitter"

    with st.spinner("جاري البحث عبر Nitter..."):
        data = fetch_via_nitter(username)
        if data:
            return data, data.get("source", "nitter")

    return None, "failed"


# ════════════════════════════════════════════════════════════════════
# عرض بطاقة الحساب
# ════════════════════════════════════════════════════════════════════
def render_profile_card(data: dict):
    username = data.get("username", "")
    display_name = data.get("display_name", username)
    bio = data.get("bio", "")
    location = data.get("location", "")
    join_date = data.get("join_date", "")
    followers = data.get("followers_count", 0)
    following = data.get("following_count", 0)
    posts = data.get("posts_count", 0)
    is_blue = data.get("is_blue_verified", False)
    verified = data.get("verified", False)
    profile_img_url = data.get("profile_image_url", "")
    source = data.get("source", "")

    # صورة الحساب
    if profile_img_url:
        b64 = image_to_base64(profile_img_url)
        if b64:
            img_html = f'<img class="profile-avatar" src="data:image/jpeg;base64,{b64}" alt="avatar"/>'
        else:
            img_html = f'<img class="profile-avatar" src="{profile_img_url}" alt="avatar"/>'
    else:
        img_html = '<div style="width:80px;height:80px;border-radius:50%;background:#1DA1F2;display:flex;align-items:center;justify-content:center;font-size:36px;">👤</div>'

    # شارة
    badge = ""
    if is_blue:
        badge = ' <span style="color:#1DA1F2;font-size:16px;">✓</span>'
    elif verified:
        badge = ' <span style="color:#FFD700;font-size:16px;">★</span>'

    # مصدر البيانات
    if "guest" in source or "api" in source.lower():
        src_label = "Twitter API"
    elif "fxtwitter" in source:
        src_label = "FxTwitter"
    elif "nitter" in source:
        src_label = "Nitter"
    elif "manual" in source:
        src_label = "يدوي"
    else:
        src_label = source

    # بناء معلومات إضافية
    extra_rows = ""
    if bio:
        extra_rows += f'<div class="info-row">📄 {bio}</div>'
    if location:
        extra_rows += f'<div class="info-row">📍 {location}</div>'
    if join_date:
        extra_rows += f'<div class="info-row">📅 تاريخ الانضمام: {join_date}</div>'

    card_html = f"""
<div class="profile-card">
  <div class="profile-header">
    {img_html}
    <div>
      <div class="profile-name">{display_name}{badge}</div>
      <div class="profile-username">@{username}</div>
      <span class="source-badge">📡 {src_label}</span>
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
  {extra_rows}
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# تحليل Gemini
# ════════════════════════════════════════════════════════════════════
def analyze_with_gemini(model, data: dict, mode: str = "account") -> str:
    if mode == "account":
        prompt = f"""أنت محلل OSINT متخصص. حلل الحساب التالي وقدم تقريراً مفصلاً بالعربية:

- المعرف: @{data.get('username','')}
- الاسم: {data.get('display_name','')}
- الوصف: {data.get('bio','')}
- الموقع: {data.get('location','')}
- المتابعون: {format_number(data.get('followers_count',0))}
- يتابع: {format_number(data.get('following_count',0))}
- المنشورات: {format_number(data.get('posts_count',0))}
- تاريخ الانضمام: {data.get('join_date','')}
- موثق: {'نعم' if data.get('is_blue_verified') or data.get('verified') else 'لا'}

التغريدات الأخيرة:
{chr(10).join([f"- {t.get('text','')[:200]}" for t in data.get('tweets',[])[:10]])}

قدم تحليلاً يشمل: نظرة عامة، أنماط النشر، المحتوى والاهتمامات، مؤشرات المصداقية، التوصيات."""
    elif mode == "image":
        points_text = format_analysis_points_for_prompt()
        schema_text = json.dumps(IMAGE_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2)
        prompt = f"""أنت محلل استخباراتي متخصص في تحليل الصور.

## نقاط التحليل
{points_text}

## صيغة الإخراج
{schema_text}

أعد النتيجة بصيغة JSON فقط."""
    else:
        prompt = f"حلل هذا المنشور:\n\n{json.dumps(data, ensure_ascii=False, indent=2)}"

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطأ في التحليل: {str(e)}"


# ════════════════════════════════════════════════════════════════════
# الشريط الجانبي
# ════════════════════════════════════════════════════════════════════
def setup_sidebar():
    with st.sidebar:
        st.title("⚙️ الإعدادات")
        st.markdown("---")

        api_key = st.text_input(
            "🔑 مفتاح Gemini API",
            type="password",
            help="احصل عليه من: https://aistudio.google.com/apikey"
        )

        model = None
        if api_key:
            try:
                genai.configure(api_key=api_key)
                model_name = st.selectbox(
                    "🤖 النموذج",
                    ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
                    index=0
                )
                model = genai.GenerativeModel(model_name)
                st.success("✅ مفتاح صحيح")
            except Exception as e:
                st.error(f"❌ {e}")
        else:
            st.info("أدخل مفتاح API للتحليل الذكي")

        st.markdown("---")
        st.caption("محلل حسابات X — v8.0")
    return model


# ════════════════════════════════════════════════════════════════════
# تبويب تحليل الحساب
# ════════════════════════════════════════════════════════════════════
def account_tab(model):
    st.markdown("## 👤 تحليل حساب X")

    col1, col2 = st.columns([3, 1])
    with col1:
        profile_input = st.text_input(
            "رابط",
            placeholder="https://x.com/username أو @username",
            label_visibility="collapsed"
        )
    with col2:
        btn = st.button("🔍 تحليل", use_container_width=True, type="primary")

    if btn and profile_input:
        username = extract_username_from_url(profile_input)
        if not username:
            clean = profile_input.lstrip("@").strip()
            username = clean if re.match(r'^\w+$', clean) else None
        if not username:
            st.error("⚠️ تعذر استخراج اسم المستخدم.")
            return

        st.info(f"🔍 جاري تحليل: **@{username}**")
        tweet_id = extract_tweet_id(profile_input)
        data, source = fetch_user_data(username, tweet_id)

        if data:
            st.success(f"✅ تم الجلب من: **{source}**")
            render_profile_card(data)
            if model:
                st.markdown("---")
                st.markdown("### 🤖 التحليل الذكي")
                with st.spinner("جاري التحليل..."):
                    st.markdown(analyze_with_gemini(model, data, "account"))
            else:
                st.info("أدخل مفتاح Gemini API للتحليل المفصل.")
        else:
            st.error("❌ تعذر جلب البيانات من جميع المصادر.")
            with st.expander("📝 أدخل البيانات يدوياً"):
                c1, c2 = st.columns(2)
                with c1:
                    mf = st.number_input("المتابعون", 0)
                    mfg = st.number_input("يتابع", 0)
                    mp = st.number_input("المنشورات", 0)
                with c2:
                    mn = st.text_input("الاسم")
                    mb = st.text_area("الوصف")
                    ml = st.text_input("الموقع")
                    mj = st.text_input("تاريخ الانضمام")
                if st.button("✅ تطبيق"):
                    md = {
                        "username": username, "display_name": mn, "bio": mb,
                        "location": ml, "followers_count": mf, "following_count": mfg,
                        "posts_count": mp, "profile_image_url": "", "join_date": mj,
                        "verified": False, "is_blue_verified": False, "tweets": [], "source": "manual"
                    }
                    render_profile_card(md)
                    if model:
                        st.markdown(analyze_with_gemini(model, md, "account"))


# ════════════════════════════════════════════════════════════════════
# تبويب تحليل المنشور والصورة
# ════════════════════════════════════════════════════════════════════
def tweet_tab(model):
    st.markdown("## 📝 تحليل منشور / صورة")

    col1, col2 = st.columns([3, 1])
    with col1:
        tweet_url = st.text_input(
            "رابط المنشور",
            placeholder="https://x.com/username/status/...",
            label_visibility="collapsed"
        )
    with col2:
        btn = st.button("🔍 تحليل المنشور", use_container_width=True, type="primary")

    uploaded = st.file_uploader(
        "📷 أو ارفع صورة",
        type=["jpg", "jpeg", "png", "webp"]
    )

    if btn and tweet_url:
        tweet_id = extract_tweet_id(tweet_url)
        if tweet_id:
            m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/", tweet_url, re.I)
            uname = m.group(1) if m else "unknown"
            with st.spinner("جاري جلب المنشور..."):
                data = fetch_via_fxtwitter(uname, tweet_id)
            if data:
                st.success("✅ تم جلب المنشور")
                render_profile_card(data)
                tweets = data.get("tweets", [])
                if tweets:
                    st.markdown(f"""
<div style="background:#1a1f2e;border:1px solid #1DA1F2;border-radius:12px;
padding:16px;margin:12px 0;direction:rtl;">
<p style="color:#e2e8f0;">{tweets[0].get('text','')}</p>
</div>""", unsafe_allow_html=True)
                if model:
                    with st.spinner("جاري التحليل..."):
                        st.markdown(analyze_with_gemini(model, data, "tweet"))
            else:
                st.error("❌ تعذر جلب المنشور.")
        else:
            st.warning("⚠️ الرابط لا يحتوي على معرف منشور.")

    if uploaded:
        st.image(uploaded, caption="الصورة المرفوعة", width=450)
        if model:
            with st.spinner("جاري تحليل الصورة..."):
                img = Image.open(uploaded)
                prompt = build_image_analysis_prompt(strict_json=False)
                try:
                    result = model.generate_content([prompt, img])
                    st.markdown(result.text)
                except Exception as e:
                    st.error(f"خطأ: {e}")
        else:
            st.info("أدخل مفتاح Gemini API لتحليل الصورة.")


# ════════════════════════════════════════════════════════════════════
# نقطة الدخول الرئيسية
# ════════════════════════════════════════════════════════════════════
st.markdown("""
<div style='text-align:center;padding:8px 0;direction:rtl;'>
<h1 style='color:#1DA1F2;margin:0;'>🔍 محلل حسابات X</h1>
<p style='color:#8899a6;margin:0;'>تحليل استخباراتي متقدم لحسابات X (تويتر)</p>
</div>
""", unsafe_allow_html=True)

model = setup_sidebar()

tab1, tab2 = st.tabs(["👤 تحليل حساب", "📝 تحليل منشور / صورة"])

with tab1:
    account_tab(model)

with tab2:
    tweet_tab(model)
```
