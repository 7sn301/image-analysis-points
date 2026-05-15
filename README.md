🐦 X (Twitter) Analysis App — v7.0
تطبيق Streamlit لتحليل حسابات ومنشورات منصة X باستخدام الذكاء الاصطناعي (Google Gemini API).
---
✨ المميزات
✅ تحليل ذكي: استخدام Gemini AI لتحليل الحسابات والمنشورات
✅ آلية Fallback ثلاثية: Twitter Guest API → FxTwitter → Nitter
✅ دعم الصور: تحليل صور الملف الشخصي والمنشورات
✅ واجهة عربية كاملة: دعم RTL مع ثيم داكن
✅ 4 نماذج Gemini مدعومة: التبديل التلقائي حسب الحاجة
✅ تقارير JSON منظمة: قابلة للتنزيل والتحليل اللاحق
---
🛠️ التقنيات المستخدمة
المكتبة	الإصدار	الاستخدام
Streamlit	>=1.28.0	واجهة المستخدم
Google Generative AI	>=0.3.0	تحليل الذكاء الاصطناعي
Requests	>=2.31.0	طلبات HTTP
BeautifulSoup4	>=4.12.0	معالجة HTML
Pillow	>=10.0.1	معالجة الصور
NumPy	>=1.24.0	عمليات حسابية
---
🚀 التثبيت والتشغيل
1. استنسخ المشروع
```bash
git clone <repo-url>
cd streamlit_x_project_v7
```
2. أنشئ بيئة افتراضية (اختياري)
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```
3. ثبّت المتطلبات
```bash
pip install -r requirements.txt
```
4. (اختياري) ثبّت حزم النظام
```bash
sudo apt-get install -y tesseract-ocr ffmpeg
```
5. شغّل التطبيق
```bash
streamlit run app.py
```
ثم افتح المتصفح على: `http://localhost:8501`
---
🔑 الحصول على مفتاح Gemini API
اذهب إلى Google AI Studio
سجّل دخولك بحساب Google
اضغط على "Create API Key"
انسخ المفتاح وألصقه في الشريط الجانبي للتطبيق
---
📦 هيكل المشروع
```
streamlit_x_project_v7/
├── app.py                    # الملف الرئيسي
├── requirements.txt          # مكتبات Python
├── packages.txt              # حزم نظام التشغيل
├── README.md                 # هذا الملف
└── .streamlit/
    └── config.toml           # إعدادات المظهر
```
---
🎨 ألوان الثيم
اللون الأساسي: `#1DA1F2` (أزرق X/Twitter)
لون الخلفية: `#0f1117` (داكن)
الخلفية الثانوية: `#1a1d24`
---
📊 هيكل تقرير التحليل (JSON)
```json
{
  "executive_summary": "ملخص تنفيذي...",
  "account_pattern": {
    "type": "نوع الحساب",
    "activity_level": "مستوى النشاط",
    "main_topics": ["موضوع 1", "موضوع 2"]
  },
  "credibility_indicators": {
    "score": "0-100",
    "positive_signals": [...],
    "red_flags": [...]
  },
  "intelligence_profile": {
    "language": "...",
    "geographic_indicators": "...",
    "active_hours": "...",
    "engagement_style": "..."
  },
  "political_orientation": "...",
  "observed_patterns": [...],
  "recommendations": [...]
}
```
---
⚙️ إعدادات الأداء
تأخير بين الطلبات: 1.5 ثانية
محاولات إعادة الاتصال: 3
مهلة الانتظار: 12 ثانية
حجم الصور: 400x400 px
---
🤖 نماذج Gemini المدعومة
النموذج	RPM	RPD	رؤية
gemini-1.5-flash	15	1500	✅
gemini-2.0-flash	15	1500	✅
gemini-1.5-flash-8b	15	1500	✅
gemini-1.0-pro	15	1500	❌
---
📝 الترخيص
MIT License — استخدم بحرية مع الإشارة للمصدر.
---
⚠️ تنبيه
هذا التطبيق لأغراض البحث والتحليل التعليمي. التزم دائماً بـ:
شروط استخدام منصة X
حقوق الخصوصية للمستخدمين
القوانين المحلية لبلدك
---
الإصدار: 7.0  
تاريخ التحديث: مايو 2026
