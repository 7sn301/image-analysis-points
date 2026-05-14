def analyze_with_gemini(image, api_key):
    """تحليل الصورة باستخدام Gemini مع Fallback تلقائي بين النماذج"""
    try:
        genai.configure(api_key=api_key.strip())

        # ✅ قائمة النماذج من الأحدث للأقدم
        models_to_try = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro",
        ]

        prompt = """
أنت محلل متخصص في تحليل منشورات تويتر/اكس (X).
قم بتحليل الصورة المرفقة واستخراج المعلومات التالية بدقة تامة.

أعد JSON فقط بدون أي نص إضافي أو علامات markdown:
{
    "معرف_المنشور": "معرف صاحب المنشور الأصلي كاملاً مثل @username",
    "معرف_التعليق": "معرف صاحب التعليق أو المنشور المقتبس إن وجد",
    "المدعو": "اسم أو معرف الشخص المدعو أو المقتبس منه المنشور",
    "محتوى_المنشور": "نص المنشور الأصلي كاملاً أو باختصار مفيد",
    "المقطع": "وصف المقطع المرئي أو الفيديو المرفق إن وجد",
    "التعليق": "نص التعليق على المنشور",
    "الرأي": "الرأي أو التحليل أو الاستنتاج المقدم",
    "الملخص_التنفيذي": "ملخص تنفيذي كامل جملة واحدة لا تقل عن 80 كلمة"
}

قواعد صارمة:
- أعد JSON فقط، لا نص قبله ولا بعده
- استخدم غير مُحدد لأي حقل غير موجود في الصورة
- الملخص_التنفيذي جملة متصلة لا تقل عن 80 كلمة
- استخرج المعرفات بدقة كاملة
- حلل وجود أي تهكم أو سخرية بعمق

مثال الملخص_التنفيذي:
نشر صاحب المعرف @username منشوراً يتضمن [المحتوى]، مقتبساً من المدعو [المدعو]، مرفقاً مقطع فيديو يظهر فيه [المقطع]، حيث علّق صاحب المعرف @commenter بأن [التعليق]، مستنتجاً أن [الرأي]، في إشارة تنطوي على تهكم بشأن [الموضوع].
"""

        last_error = ""

        # ✅ الحل الرئيسي: تجربة كل نموذج عند generate_content أيضاً
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt, image])
                raw = response.text.strip()

                # تنظيف markdown
                cleaned = re.sub(r'^```(json)?\s*', '', raw)
                cleaned = re.sub(r'\s*```$', '', cleaned).strip()

                match = re.search(r'\{[\s\S]*\}', cleaned)
                if match:
                    result = json.loads(match.group())
                    for field in ["معرف_المنشور", "معرف_التعليق", "المدعو",
                                  "محتوى_المنشور", "المقطع", "التعليق",
                                  "الرأي", "الملخص_التنفيذي"]:
                        if field not in result:
                            result[field] = "غير مُحدد"
                    return result, None, model_name  # ✅ نجح
                else:
                    last_error = f"النموذج {model_name}: لم يُرجع JSON صالح"
                    continue  # جرب النموذج التالي

            except Exception as model_error:
                err_str = str(model_error)

                # ✅ إذا كان خطأ quota أو 429 → جرب النموذج التالي
                if any(x in err_str for x in ["QUOTA_EXCEEDED", "429", "quota", "rate_limit", "ResourceExhausted"]):
                    last_error = f"⚠️ النموذج {model_name}: تجاوز الحصة، جاري تجربة نموذج آخر..."
                    continue  # ← هذا هو الإصلاح الأساسي

                # ✅ إذا كان النموذج غير موجود → جرب التالي
                elif any(x in err_str for x in ["404", "not found", "NOT_FOUND"]):
                    last_error = f"⚠️ النموذج {model_name}: غير متاح"
                    continue

                # ❌ أخطاء أخرى خطيرة → أوقف وأرجع الخطأ
                elif "API_KEY_INVALID" in err_str:
                    return None, "❌ مفتاح API غير صالح. تأكد من صحة المفتاح.", ""
                elif "PERMISSION_DENIED" in err_str:
                    return None, "❌ لا توجد صلاحية. تأكد من تفعيل Gemini API.", ""
                else:
                    last_error = f"❌ خطأ في {model_name}: {err_str[:100]}"
                    continue

        # إذا فشلت كل النماذج
        return None, (
            f"❌ فشلت جميع نماذج Gemini المتاحة.\n\n"
            f"آخر خطأ: {last_error}\n\n"
            f"💡 الحلول المقترحة:\n"
            f"• انتظر 60 ثانية وأعد المحاولة\n"
            f"• استخدم مفتاح API مختلف\n"
            f"• استخدم OCR كبديل مجاني"
        ), ""

    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err:
            return None, "❌ مفتاح API غير صالح.", ""
        elif "PERMISSION_DENIED" in err:
            return None, "❌ لا توجد صلاحية للوصول.", ""
        else:
            return None, f"❌ خطأ عام: {err}", ""
