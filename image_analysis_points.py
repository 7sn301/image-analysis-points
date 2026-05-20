async def _twikit_login_test(username, email, password):
    """اختبار تسجيل الدخول عبر twikit"""
    try:
        from twikit import Client
        client = Client('ar')
        cookies_path = '/tmp/twikit_cookies.json'
        
        if os.path.exists(cookies_path):
            try:
                client.load_cookies(cookies_path)
                return True, "✅ تم تحميل الجلسة المحفوظة بنجاح"
            except Exception:
                os.remove(cookies_path)
        
        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password
        )
        client.save_cookies(cookies_path)
        return True, f"✅ تم تسجيل الدخول بنجاح كـ @{username}"
        
    except Exception as e:
        err = str(e)
        # ⬇️ معالجة خاصة لخطأ twikit المعروف
        if "KEY_BYTE" in err:
            return False, (
                "❌ خطأ في مكتبة twikit (KEY_BYTE)\n\n"
                "🔧 الحل: عدّل requirements.txt واستبدل:\n"
                "`twikit>=2.0.0`\n"
                "بـ:\n"
                "`twikit @ git+https://github.com/d60/twikit.git`\n\n"
                "ثم أعد نشر التطبيق على Streamlit Cloud."
            )
        elif "Could not authenticate" in err or "Wrong password" in err:
            return False, "❌ بيانات الدخول خاطئة — تحقق من اسم المستخدم وكلمة المرور"
        elif "suspicious" in err.lower() or "unusual" in err.lower():
            return False, "⚠️ تويتر اكتشف دخولاً غير معتاد — انتظر قليلاً ثم أعد المحاولة"
        else:
            return False, f"❌ فشل تسجيل الدخول: {err}"
