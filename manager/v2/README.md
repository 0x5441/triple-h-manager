# Triple H Manager V2

إعادة بناء مستقلة لتطبيق Triple H Manager. النسخة الحالية في المجلد الأب تبقى
مرجعًا قديمًا ولا تعتمد عليها حزم V2 وقت التشغيل.

## حالة المرحلة الحالية

تحتوي المراحل المنفذة على أساس المشروع والتخزين وإدارة جلسات Chrome:

- مسارات مركزية لملفات وبيانات V2.
- نماذج `Account` و`Advertisement` و`JobResult`.
- حالات موحدة للحسابات والوظائف باستخدام `Enum`.
- تسجيل إلى الكونسول وملف دوّار داخل `data/logs`.
- تخزين حسابات مشفر باستخدام Fernet خلف `AccountStore` و`AccountService`.
- قارئ مستقل لتجهيز معاينة migration للبيانات القديمة دون نقلها.
- Chrome profile مستقل لكل `account_id` مع فحص وتجديد جلسة حراج.
- Page object لمحددات الدخول وسكربت اختبار يدوي لا ينشر ولا يحدث إعلانًا.
- خدمة منظمة لتحديث إعلان واحد أو حساب كامل أو جميع الحسابات، مع استمرار الأخطاء.
- CLI آمن يبدأ بوضع dry-run ولا ينقر زر التحديث إلا بخيار صريح.
- قارئ Google Sheets عام يعرض التبويبات ويحوّل الصفوف المطابقة إلى `Advertisement`.
- سجل محلي لمفاتيح الصفوف المعالجة عندما لا توجد صلاحية كتابة على الشيت.
- اختبارات وحدات للنماذج.

لا تحتوي المراحل المنفذة حتى الآن على Tkinter أو سير نشر. تكامل Google Sheets
للقراءة فقط، وهو مستقل عن Selenium وخدمات المتصفح.

## التشغيل

يتطلب المشروع Python 3.10 أو أحدث. من داخل مجلد `v2`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

على Windows استبدل أمر التفعيل بـ:

```powershell
.venv\Scripts\activate
```

تشغيل الاختبارات:

```bash
python -m pytest
```

## الهيكلة

```text
v2/
├── main.py                  نقطة التشغيل
├── requirements.txt        اعتماديات المرحلة
├── pytest.ini              إعدادات الاختبارات
├── app/
│   ├── config.py           المسارات وإنشاء مجلدات التشغيل
│   ├── logging_config.py   إعداد التسجيل
│   ├── models/             نماذج المجال والحالات
│   ├── services/           خدمات الحسابات والبروفايلات
│   ├── browser/            مصنع Chrome وHaraj page object والمحددات
│   ├── storage/            تخزين الحسابات المشفر وأدوات migration
│   └── ui/                 الواجهة في المراحل اللاحقة
├── data/                   بيانات تشغيل محلية غير متتبعة
└── tests/                  اختبارات pytest
```

`data/.gitkeep` فقط هو المتتبع داخل `data`. الحسابات والمفاتيح والبروفايلات
والسجلات وصور الأخطاء مستبعدة بواسطة `.gitignore`.

طبقة `AccountService` هي المدخل لبقية التطبيق لإضافة الحسابات وتعديلها وحذفها
وإيقافها أو تفعيلها. لا ينبغي للواجهة المستقبلية قراءة `accounts.enc` أو المفتاح
مباشرة. دوال `app.storage.migration` تقرأ legacy وتبني معاينة في الذاكرة فقط؛
ولا تنفذ أي نقل تلقائي.

## اختبار Chrome profile يدويًا

أغلق أي نافذة Chrome تستخدم بروفايل الحساب نفسه، ثم نفذ من داخل `v2`:

```bash
python -m scripts.test_profile \
  --account-id ACCOUNT_ID \
  --username HARAJ_USERNAME
```

تُطلب كلمة المرور عبر `getpass` ولا تظهر في الطرفية. يفتح السكربت فقط الصفحة
الرئيسية ويتحقق من الجلسة أو يسجل الدخول. إذا ظهر تحقق إضافي، يترك Chrome ظاهرًا
حتى خمس دقائق افتراضيًا لإكمال التحقق يدويًا. لا يحتوي السكربت على أي نشر أو
تحديث. يمكن تعديل المهلة عبر `--manual-timeout 600`.

استخدام `--headless` مناسب فقط عندما لا يُتوقع تحقق يدوي. يستخدم Chrome الملف:

```text
v2/data/profiles/{account_id}
```

ولا يستخدم بروفايل Chrome الشخصي أو مسار ChromeDriver ثابتًا؛ Selenium Manager
هو المسؤول عن اختيار برنامج التشغيل المتوافق.

## اختبار تحديث إعلان موجود

يجب أن يكون الحساب موجودًا مسبقًا في مخزن V2 المشفر. ابدأ دائمًا بفحص إعلان
واحد دون تنفيذ التحديث:

```bash
python -m scripts.update_account \
  --account-id ACCOUNT_ID \
  --url https://haraj.com.sa/AD_URL
```

هذا هو الوضع الافتراضي الآمن: يفتح بروفايل الحساب، يتأكد من الجلسة، ويفحص وجود
زر التحديث دون النقر عليه. بعد مراجعة النتيجة، يمكن تنفيذ التحديث الحقيقي لنفس
الرابط بإضافة `--execute`:

```bash
python -m scripts.update_account \
  --account-id ACCOUNT_ID \
  --url https://haraj.com.sa/AD_URL \
  --execute
```

ولتشغيل جميع الروابط المحفوظة للحساب، احذف `--url`. يفضّل إبقاء Chrome ظاهرًا
أول مرة حتى يمكن إكمال أي تحقق يدوي. لا تشغّل البروفايل نفسه في نافذة Chrome
أخرى أثناء الاختبار. صور الأخطاء تحفظ محليًا تحت `v2/data/errors`.

## قراءة Google Sheets دون نشر

لعرض أسماء التبويبات في Sheet عام:

```bash
python -m scripts.read_sheet --url "PUBLIC_GOOGLE_SHEET_URL"
```

لقراءة تبويب محدد ومطابقة صفوفه مع حسابات V2 المشفرة:

```bash
python -m scripts.read_sheet \
  --url "PUBLIC_GOOGLE_SHEET_URL" \
  --worksheet "Ads"
```

الأعمدة الإلزامية هي `account`, و`title`, و`body`. الأعمدة `phone`, و`image`,
و`status` اختيارية. الصف ذو الحالة `تم` لا يعاد، كما يمكن حفظ `source_key`
محليًا في `v2/data/published_rows.json` عبر `GoogleSheetService.mark_processed()`
بعد أن تنفذ مرحلة نشر لاحقة بنجاح. CLI الحالي للقراءة والعرض فقط ولا يستدعي
Selenium أو ينشر أي إعلان.
