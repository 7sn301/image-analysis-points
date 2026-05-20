import base64
import io
import os
import random
import re
import time
from datetime import datetime

import requests
import streamlit as st
from PIL import Image

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches as DocxInches
    from docx.shared import Pt as DocxPt
except Exception:
    Document = None
    WD_ALIGN_PARAGRAPH = None
    OxmlElement = None
    qn = None
    DocxInches = None
    DocxPt = None

try:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Inches as PptxInches
    from pptx.util import Pt as PptxPt
except Exception:
    Presentation = None
    RGBColor = None
    MSO_ANCHOR = None
    PP_ALIGN = None
    PptxInches = None
    PptxPt = None

try:
    from Scweet.scweet import scrape as scweet_scrape
except Exception:
    scweet_scrape = None


VERSION = "v10.3.5"
PAGE_TITLE = "محلل حسابات X الاستخباراتي"
PAGE_ICON = "🔍"
FXTWITTER_TWEET = "https://api.fxtwitter.com/status/{tweet_id}"
FXTWITTER_USER = "https://api.fxtwitter.com/{username}"
TWITTERAPI_BASE = "https://api.twitterapi.io"

GEMINI_MODELS = {
    "gemini-2.5-flash (سريع - موصى به)": "gemini-2.5-flash",
    "gemini-2.5-pro (متقدم)": "gemini-2.5-pro",
    "gemini-2.0-flash (اقتصادي)": "gemini-2.0-flash",
    "gemini-1.5-flash (احتياطي)": "gemini-1.5-flash",
}

INTEL_KEYWORDS = {
    "العداء المباشر للسعودية": [
        "ارض الحرمين",
        "المهلكة",
        "ال سلول",
        "شولوم",
        "البقرة",
        "الحلوب",
        "قمع",
        "فساد",
        "إسقاط النظام",
        "تكميم الأفواه",
        "اعتقالات سياسية",
        "معتقل",
        "العدائية",
        "مقاطعة السعودية",
        "حملة ضد السعودية",
        "فضائح السعودية",
        "فشل سعودي",
        "استهداف السعودية",
    ],
    "التحريض السياسي": [
        "زعزعة الأمن",
        "إسقاط الحكم",
        "التحريض ضد الدولة",
        "الفوضى",
        "العصيان",
        "التجنيد ضد السعودية",
        "ثورة",
        "الدعوة للتظاهر",
        "مظاهرة",
        "انتفاضة",
        "تمرد",
        "عصيان مدني",
    ],
    "الحملات الإعلامية المعادية": [
        "الذباب الإلكتروني",
        "غسيل سمعة",
        "حراك شعبي",
        "انفجار شعبي",
        "الغضب الشعبي",
        "الشارع يغلي",
        "قمع حريات",
    ],
    "الإساءة للهوية الوطنية": [
        "العاطلين",
        "البطالة",
        "العنصرية ضد السعوديين",
        "كراهية السعوديين",
        "التشكيك بالوطنية",
        "إهانة رموز الدولة",
    ],
}

IMAGE_ANALYSIS_POINTS = {
    "📍 تحليل الموقع الجغرافي": "حدد الموقع الجغرافي والمعالم والدولة والمدينة المحتملة.",
    "👥 تحليل الأشخاص": "صف الأشخاص في الصورة: الجنس، العمر، الملابس، الهوية.",
    "🚗 تحليل المركبات": "حدد أي مركبات مع نوعها ولونها وأي معلومات مميزة.",
    "📄 تحليل المستندات": "استخرج أي نصوص أو معلومات من مستندات أو لافتات.",
    "⚠️ تحليل التهديدات": "حدد أي محتوى مثير للقلق أو تهديدات أو محتوى عنيف.",
    "🏛️ تحليل البنية التحتية": "صف أي مبانٍ أو منشآت أو بنية تحتية مرئية.",
    "🕐 تحليل التوقيت": "قدّر الوقت من الإضاءة والظلال.",
    "🎭 تحليل الأحداث": "صف أي حدث أو اجتماع أو نشاط يجري.",
    "🔍 كشف التزوير": "قيّم مدى أصالة الصورة وابحث عن علامات التلاعب.",
    "📊 تحليل شامل": "قدم تحليلاً شاملاً من منظور استخباراتي.",
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IntelXAnalyzer/10.3.5; +https://streamlit.io)",
    "Accept": "application/json, text/plain, */*",
}
REQUEST_TIMEOUT = 25


def _clean_html_text(value):
    text = str(value if value is not None else "")
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#39;")
    return text


def _display_html(html_block):
    try:
        st.html(html_block)
    except Exception:
        try:
            st.markdown(html_block, unsafe_allow_html=True)
        except Exception as error:
            st.error(f"تعذر عرض المكون المرئي: {error}")


def _extract_media_urls(source):
    media_urls = []
    if not isinstance(source, dict):
        return media_urls

    possible_lists = []

    if isinstance(source.get("media"), list):
        possible_lists.append(source.get("media"))
    if isinstance(source.get("photos"), list):
        possible_lists.append(source.get("photos"))
    if isinstance(source.get("images"), list):
        possible_lists.append(source.get("images"))

    entities = source.get("entities", {})
    if isinstance(entities, dict) and isinstance(entities.get("media"), list):
        possible_lists.append(entities.get("media"))

    ext_entities = source.get("extended_entities", {})
    if isinstance(ext_entities, dict) and isinstance(ext_entities.get("media"), list):
        possible_lists.append(ext_entities.get("media"))

    for media_list in possible_lists:
        for item in media_list:
            if isinstance(item, str):
                media_urls.append(item)
                continue

            if not isinstance(item, dict):
                continue

            candidates = [
                item.get("url"),
                item.get("media_url"),
                item.get("media_url_https"),
                item.get("mediaUrl"),
                item.get("image"),
                item.get("image_url"),
                item.get("thumbnail_url"),
                item.get("thumbnailUrl"),
            ]
            for candidate in candidates:
                if isinstance(candidate, str) and candidate.startswith("http"):
                    media_urls.append(candidate)

    unique_urls = []
    seen = set()
    for url in media_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return unique_urls


def _normalize_user_obj(source):
    if not isinstance(source, dict):
        return {
            "name": "غير متوفر",
            "username": "",
            "description": "",
            "followers": 0,
            "following": 0,
            "tweets_count": 0,
            "avatar": "",
            "banner": "",
            "verified": False,
            "created_at": "",
            "location": "",
            "url": "",
            "raw": source,
            "error": "بيانات المستخدم غير صالحة",
        }

    username = (
        source.get("screen_name")
        or source.get("username")
        or source.get("user_name")
        or source.get("handle")
        or ""
    )
    username = str(username).replace("@", "").strip()

    followers = (
        source.get("followers_count")
        or source.get("followers")
        or source.get("followersCount")
        or 0
    )
    following = (
        source.get("friends_count")
        or source.get("following")
        or source.get("followingCount")
        or source.get("friends")
        or 0
    )
    tweets_count = (
        source.get("statuses_count")
        or source.get("tweets_count")
        or source.get("tweetCount")
        or source.get("statusesCount")
        or 0
    )

    avatar = (
        source.get("profile_image_url_https")
        or source.get("profile_image_url")
        or source.get("avatar")
        or source.get("profilePicture")
        or ""
    )
    banner = (
        source.get("profile_banner_url")
        or source.get("banner")
        or source.get("profileBanner")
        or ""
    )

    return {
        "name": source.get("name") or source.get("display_name") or username or "غير متوفر",
        "username": username,
        "description": source.get("description") or source.get("bio") or "",
        "followers": followers,
        "following": following,
        "tweets_count": tweets_count,
        "avatar": avatar,
        "banner": banner,
        "verified": bool(source.get("verified") or source.get("is_blue_verified") or source.get("isVerified")),
        "created_at": source.get("created_at") or source.get("createdAt") or "",
        "location": source.get("location") or "",
        "url": source.get("url") or "",
        "raw": source,
        "error": None,
    }


def _normalize_tweet_obj(source):
    if not isinstance(source, dict):
        return {
            "id": "",
            "text": "",
            "created_at": "",
            "likes": 0,
            "retweets": 0,
            "replies": 0,
            "views": 0,
            "url": "",
            "author_name": "",
            "author_username": "",
            "media_urls": [],
            "raw": source,
        }

    tweet_id = str(
        source.get("id")
        or source.get("tweet_id")
        or source.get("tweetId")
        or source.get("rest_id")
        or ""
    )
    text = (
        source.get("full_text")
        or source.get("text")
        or source.get("content")
        or source.get("tweetText")
        or ""
    )
    created_at = source.get("created_at") or source.get("createdAt") or source.get("date") or ""
    likes = source.get("favorite_count") or source.get("likes") or source.get("likeCount") or 0
    retweets = source.get("retweet_count") or source.get("retweets") or source.get("retweetCount") or 0
    replies = source.get("reply_count") or source.get("replies") or source.get("replyCount") or 0
    views = source.get("views") or source.get("viewCount") or source.get("quote_views") or 0
    media_urls = _extract_media_urls(source)

    author = source.get("user") or source.get("author") or source.get("account") or {}
    if not isinstance(author, dict):
        author = {}

    author_username = (
        author.get("screen_name")
        or author.get("username")
        or author.get("user_name")
        or source.get("author_username")
        or source.get("username")
        or ""
    )
    author_username = str(author_username).replace("@", "").strip()

    author_name = (
        author.get("name")
        or author.get("display_name")
        or source.get("author_name")
        or author_username
    )

    url = source.get("url") or source.get("tweetUrl") or ""
    if not url and tweet_id and author_username:
        url = f"https://x.com/{author_username}/status/{tweet_id}"

    return {
        "id": tweet_id,
        "text": text,
        "created_at": created_at,
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "views": views,
        "url": url,
        "author_name": author_name,
        "author_username": author_username,
        "media_urls": media_urls,
        "raw": source,
    }


def _extract_tweet_list(data):
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in ["tweets", "statuses", "items", "timeline", "data", "entries", "results"]:
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_tweet_list(value)
            if nested:
                return nested

    for _, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
        if isinstance(value, dict):
            nested = _extract_tweet_list(value)
            if nested:
                return nested

    return []


def _collect_images_from_tweets(tweets, max_images=4):
    images_data = []
    seen = set()

    for tweet in tweets:
        media_urls = tweet.get("media_urls", [])
        for media_url in media_urls:
            if media_url in seen:
                continue
            seen.add(media_url)
            img_info = download_image_b64(media_url)
            if img_info:
                images_data.append(img_info)
            if len(images_data) >= max_images:
                return images_data
    return images_data


def _keyword_hits_to_text(keyword_hits):
    if not isinstance(keyword_hits, dict):
        return "لا توجد نتائج تحليل نصي."

    lines = []
    lines.append(f"إجمالي درجة المخاطر: {keyword_hits.get('score', 0)}")
    lines.append(f"إجمالي النصوص المفحوصة: {keyword_hits.get('total_texts', 0)}")
    lines.append("")

    categories = keyword_hits.get("categories", {})
    if not categories:
        lines.append("لم يتم رصد كلمات مفتاحية حساسة ضمن القاموس الحالي.")
        return "\n".join(lines)

    lines.append("تفصيل الفئات المرصودة:")
    for category, info in categories.items():
        lines.append(f"- {category}: {info.get('count', 0)} تطابق")
        matched_keywords = info.get("keywords", [])
        if matched_keywords:
            lines.append(f"  الكلمات: {', '.join(matched_keywords)}")
        examples = info.get("examples", [])
        if examples:
            for example in examples[:2]:
                lines.append(f"  مثال: {example[:180]}")
    return "\n".join(lines)


# 1
def safe_text(val, default="غير متوفر"):
    try:
        if val is None:
            return default
        if isinstance(val, str):
            cleaned = val.strip()
            return cleaned if cleaned else default
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, (list, dict)):
            text = str(val).strip()
            return text if text else default
        text = str(val).strip()
        return text if text else default
    except Exception:
        return default


# 2
def format_number(n):
    try:
        if n is None:
            return "0"
        if isinstance(n, str):
            n = n.replace(",", "").strip()
        value = float(n)
        abs_value = abs(value)

        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f}K".replace(".0K", "K")
        return str(int(value))
    except Exception:
        return "0"


# 3
def format_date(s):
    try:
        text = safe_text(s, "")
        if not text:
            return "غير متوفر"

        possible_formats = [
            "%a %b %d %H:%M:%S %z %Y",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in possible_formats:
            try:
                dt = datetime.strptime(text, fmt)
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                continue

        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text
    except Exception:
        return "غير متوفر"


# 4
def extract_tweet_id(url):
    try:
        text = safe_text(url, "")
        if not text:
            return ""

        match = re.search(r"/status/(\d+)", text)
        if match:
            return match.group(1)

        match = re.search(r"\b(\d{8,25})\b", text)
        if match:
            return match.group(1)

        return ""
    except Exception:
        return ""


# 5
def extract_username(text):
    try:
        value = safe_text(text, "")
        if not value:
            return ""

        value = value.strip()

        url_match = re.search(r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})", value, re.IGNORECASE)
        if url_match:
            return url_match.group(1)

        at_match = re.search(r"@?([A-Za-z0-9_]{1,15})$", value)
        if at_match:
            return at_match.group(1)

        any_match = re.search(r"@([A-Za-z0-9_]{1,15})", value)
        if any_match:
            return any_match.group(1)

        return ""
    except Exception:
        return ""


# 6
def image_to_base64(img, fmt="PNG"):
    try:
        if img is None:
            return ""
        buffer = io.BytesIO()
        img.save(buffer, format=fmt)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        return ""


# 7
def base64_to_bytesio(b64):
    try:
        if not b64:
            return io.BytesIO()
        clean_b64 = b64.split(",", 1)[1] if "base64," in b64 else b64
        raw = base64.b64decode(clean_b64)
        return io.BytesIO(raw)
    except Exception:
        return io.BytesIO()


# 8
def download_image_b64(url):
    try:
        if not url or not str(url).startswith("http"):
            return None

        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        image = Image.open(io.BytesIO(response.content))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        fmt = image.format or "PNG"
        b64 = image_to_base64(image, fmt=fmt)

        return {
            "url": url,
            "b64": b64,
            "format": fmt,
            "width": image.size[0],
            "height": image.size[1],
        }
    except Exception:
        return None


# 9
def calc_image_size_word(b64, max_w=6.0, max_h=4.5):
    try:
        bio = base64_to_bytesio(b64)
        img = Image.open(bio)
        width_px, height_px = img.size
        if width_px <= 0 or height_px <= 0:
            return max_w, max_h

        ratio = min(max_w / width_px, max_h / height_px)
        width_in = width_px * ratio
        height_in = height_px * ratio
        return width_in, height_in
    except Exception:
        return max_w, max_h


# 10
def calc_image_size_pptx(b64, sw=13.333, sh=7.5, mg=0.4):
    try:
        bio = base64_to_bytesio(b64)
        img = Image.open(bio)
        width_px, height_px = img.size
        if width_px <= 0 or height_px <= 0:
            return sw - (mg * 2), sh - (mg * 2)

        max_w = sw - (mg * 2)
        max_h = sh - (mg * 2)
        ratio = min(max_w / width_px, max_h / height_px)
        width_in = width_px * ratio
        height_in = height_px * ratio
        return width_in, height_in
    except Exception:
        return sw - (mg * 2), sh - (mg * 2)


# 11
def fetch_fxtwitter_tweet(tweet_id):
    try:
        if not tweet_id:
            return {"error": "معرف التغريدة غير صالح"}

        url = FXTWITTER_TWEET.format(tweet_id=tweet_id)
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        source = data.get("tweet") or data.get("status") or data
        tweet = _normalize_tweet_obj(source)
        tweet["error"] = None
        tweet["raw_response"] = data
        return tweet
    except Exception as error:
        return {"error": f"تعذر جلب التغريدة: {error}"}


# 12
def fetch_fxtwitter_user(username):
    try:
        if not username:
            return {"error": "اسم المستخدم غير صالح"}

        url = FXTWITTER_USER.format(username=username)
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        source = data.get("user") or data.get("author") or data
        user_data = _normalize_user_obj(source)
        user_data["raw_response"] = data
        user_data["error"] = None
        return user_data
    except Exception as error:
        return {"error": f"تعذر جلب بيانات الحساب: {error}"}


# 13
def fetch_user_tweets_twitterapi(username, api_key, limit=20):
    try:
        if not username:
            return {"tweets": [], "error": "اسم المستخدم غير صالح", "source": "TwitterAPI.io"}
        if not api_key:
            return {"tweets": [], "error": "مفتاح TwitterAPI.io غير متوفر", "source": "TwitterAPI.io"}

        endpoints = [
            f"{TWITTERAPI_BASE}/twitter/user/last_tweets",
            f"{TWITTERAPI_BASE}/twitter/user/tweets",
            f"{TWITTERAPI_BASE}/twitter/user/recent_tweets",
        ]

        header_variants = [
            {"X-API-Key": api_key, **REQUEST_HEADERS},
            {"x-api-key": api_key, **REQUEST_HEADERS},
            {"Authorization": f"Bearer {api_key}", **REQUEST_HEADERS},
        ]

        params = {
            "userName": username,
            "username": username,
            "limit": int(limit),
        }

        last_error = "لم تنجح أي محاولة للاتصال بـ TwitterAPI.io"

        for endpoint in endpoints:
            for headers in header_variants:
                try:
                    response = requests.get(
                        endpoint,
                        params=params,
                        headers=headers,
                        timeout=REQUEST_TIMEOUT,
                    )
                    if response.status_code >= 400:
                        last_error = f"HTTP {response.status_code}"
                        continue

                    data = response.json()
                    raw_tweets = _extract_tweet_list(data)
                    tweets = [_normalize_tweet_obj(item) for item in raw_tweets][: int(limit)]
                    if tweets:
                        return {"tweets": tweets, "error": None, "source": "TwitterAPI.io"}

                    if isinstance(data, dict):
                        single_tweet = data.get("tweet")
                        if isinstance(single_tweet, dict):
                            return {
                                "tweets": [_normalize_tweet_obj(single_tweet)],
                                "error": None,
                                "source": "TwitterAPI.io",
                            }
                except Exception as inner_error:
                    last_error = str(inner_error)

        return {"tweets": [], "error": f"تعذر جلب التغريدات: {last_error}", "source": "TwitterAPI.io"}
    except Exception as error:
        return {"tweets": [], "error": f"خطأ غير متوقع أثناء جلب التغريدات: {error}", "source": "TwitterAPI.io"}


# 14
def fetch_tweets_scweet(username, auth_token, limit=20):
    try:
        if not username:
            return {"tweets": [], "error": "اسم المستخدم غير صالح", "source": "Scweet"}
        if not auth_token:
            return {"tweets": [], "error": "X auth_token غير متوفر", "source": "Scweet"}
        if scweet_scrape is None:
            return {"tweets": [], "error": "مكتبة Scweet غير مثبتة", "source": "Scweet"}

        until_date = datetime.utcnow().strftime("%Y-%m-%d")
        since_date = "2020-01-01"

        result = scweet_scrape(
            words=[f"from:{username}"],
            since=since_date,
            until=until_date,
            from_account=username,
            interval=1,
            headless=True,
            display_type="Latest",
            save_images=False,
            filter_replies=False,
            proximity=False,
            lang="ar",
        )

        tweets = []

        if hasattr(result, "to_dict"):
            rows = result.to_dict("records")
            for row in rows[: int(limit)]:
                tweet = {
                    "id": safe_text(row.get("tweetId") or row.get("tweet_id"), ""),
                    "text": safe_text(row.get("text") or row.get("tweet"), ""),
                    "created_at": safe_text(row.get("date"), ""),
                    "likes": row.get("likes") or 0,
                    "retweets": row.get("retweets") or 0,
                    "replies": row.get("replies") or 0,
                    "views": row.get("views") or 0,
                    "url": safe_text(row.get("permalink"), ""),
                    "author_name": username,
                    "author_username": username,
                    "media_urls": [],
                    "raw": row,
                }
                tweets.append(tweet)
        elif isinstance(result, list):
            tweets = [_normalize_tweet_obj(item) for item in result[: int(limit)]]
        else:
            return {"tweets": [], "error": "لم تُرجع Scweet بيانات قابلة للقراءة", "source": "Scweet"}

        return {"tweets": tweets[: int(limit)], "error": None, "source": "Scweet"}
    except Exception as error:
        return {"tweets": [], "error": f"تعذر جلب التغريدات عبر Scweet: {error}", "source": "Scweet"}


# 15
def scan_keywords(texts):
    try:
        results = {
            "score": 0,
            "total_texts": len(texts) if isinstance(texts, list) else 0,
            "categories": {},
        }

        if not isinstance(texts, list):
            return results

        for raw_text in texts:
            text = safe_text(raw_text, "")
            if not text:
                continue

            lowered = text.lower()

            for category, keywords in INTEL_KEYWORDS.items():
                matched = []
                for keyword in keywords:
                    if keyword.lower() in lowered:
                        matched.append(keyword)

                if matched:
                    unique_matched = sorted(set(matched))
                    if category not in results["categories"]:
                        results["categories"][category] = {
                            "count": 0,
                            "keywords": [],
                            "examples": [],
                        }

                    results["categories"][category]["count"] += len(unique_matched)
                    results["categories"][category]["keywords"].extend(unique_matched)
                    results["categories"][category]["examples"].append(text[:220])
                    results["score"] += len(unique_matched)

        for category, info in results["categories"].items():
            info["keywords"] = sorted(set(info["keywords"]))
            unique_examples = []
            for example in info["examples"]:
                if example not in unique_examples:
                    unique_examples.append(example)
            info["examples"] = unique_examples[:3]

        return results
    except Exception:
        return {"score": 0, "total_texts": 0, "categories": {}}


# 16
def get_threat_info(score):
    try:
        value = int(score or 0)

        if value >= 12:
            return {
                "level": "حرج",
                "label": "تهديد حرج",
                "description": "المحتوى يتضمن إشارات متكررة وحساسة تستدعي تصعيدًا فوريًا.",
                "recommendation": "التوصية: مراجعة بشرية عاجلة، وتوسيع الرصد، وربط الحسابات ذات الصلة.",
            }
        if value >= 7:
            return {
                "level": "مرتفع",
                "label": "تهديد مرتفع",
                "description": "تم رصد مؤشرات لخطاب عدائي أو تحريضي بشكل واضح.",
                "recommendation": "التوصية: مراقبة مستمرة، وتحليل الشبكة المحيطة، وتوثيق المحتوى.",
            }
        if value >= 3:
            return {
                "level": "متوسط",
                "label": "تهديد متوسط",
                "description": "هناك بعض المؤشرات النصية التي تتطلب متابعة وتحليلًا إضافيًا.",
                "recommendation": "التوصية: التحقق من السياق، ومراجعة نشاط الحساب الأوسع زمنيًا.",
            }
        return {
            "level": "منخفض",
            "label": "تهديد منخفض",
            "description": "لا توجد مؤشرات كافية ضمن القاموس الحالي لاعتبار الحساب عالي المخاطر.",
            "recommendation": "التوصية: حفظ النتيجة مع متابعة دورية فقط.",
        }
    except Exception:
        return {
            "level": "غير معروف",
            "label": "غير معروف",
            "description": "تعذر حساب مستوى التهديد.",
            "recommendation": "التوصية: إعادة المحاولة أو مراجعة البيانات يدويًا.",
        }


# 17
def gemini_text(prompt, model_id):
    try:
        if genai is None:
            return "تعذر تنفيذ تحليل Gemini: المكتبة غير متوفرة."

        api_key = (
            st.session_state.get("gemini_api_key")
            or os.getenv("GEMINI_API_KEY")
            or ""
        )
        if not api_key:
            return "تعذر تنفيذ تحليل Gemini: مفتاح API غير متوفر."

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)

        text = ""
        if hasattr(response, "text") and response.text:
            text = response.text

        if not text and hasattr(response, "candidates") and response.candidates:
            try:
                parts = response.candidates[0].content.parts
                text = "\n".join([safe_text(part.text, "") for part in parts if hasattr(part, "text")])
            except Exception:
                text = ""

        return safe_text(text, "لم يُرجع النموذج أي نص.")
    except Exception as error:
        return f"تعذر تنفيذ تحليل Gemini: {error}"


# 18
def gemini_with_images(prompt, images_b64, model_id):
    try:
        if genai is None:
            return "تعذر تنفيذ تحليل الصور: مكتبة Gemini غير متوفرة."

        api_key = (
            st.session_state.get("gemini_api_key")
            or os.getenv("GEMINI_API_KEY")
            or ""
        )
        if not api_key:
            return "تعذر تنفيذ تحليل الصور: مفتاح API غير متوفر."

        if not images_b64:
            return "
