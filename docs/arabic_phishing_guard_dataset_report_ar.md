# تقرير تجهيز Dataset مشروع Arabic Phishing Guard

## 1) الهدف
تجهيز Dataset عربية **احترافية ومناسبة لمشروع كشف التصيّد** مع:
- تنظيف النصوص وتوحيدها
- إزالة/تقليل التكرار
- تحليل المصادر والجودة
- فصل البيانات الرئيسية عن البيانات المساعدة
- إنتاج ملفات جاهزة للتدريب والتقييم

## 2) القرار النهائي بخصوص المصادر
تم استخدام المصادر الأقرب للمهمة الأساسية (**رسائل/إيميلات عربية**) في الـ main dataset، بينما تم حفظ المصادر الأقل ملاءمة كبيانات مساعدة فقط.

### المصادر المستخدمة في الـ main dataset
- `Arabic Phishing and Legitimate emails - Fully Dataset.xlsx`
- `phishing-bilingual.csv`
- `legit-bilingual.csv`
- `arabic_dataset_core_sms_email_balanced.csv` **لكن تم استخدام صفوف SMS فقط**، وتمت فلترة الرسائل الإيجابية للاحتفاظ فقط بالعينات الأقرب للتصيّد الحقيقي (حساب/بنك/OTP/تحديث/حظر/استثمار احتيالي...)

### المصادر غير المستخدمة في الـ main dataset
- `Arabic Phishing Sentences - Fully Dataset.xlsx`  
  تم حفظها كـ **augmentation-only** لأنها جمل قصيرة وليست رسائل كاملة، وهذا قد يرفع الأداء بشكل غير واقعي إذا دخلت في الاختبار النهائي.
- `HSC-Training.csv` + `HSC-Testing.csv`  
  تم حفظها كـ **auxiliary** فقط لأنها تغريدات Spam تسويقية/اجتماعية في الغالب، وليست dataset مثالية لمهمة phishing text detection في الرسائل والإيميل.

## 3) التنظيف المطبق
تم تطبيق تنظيف خفيف مناسب لـ AraBERT:
- استبدال الروابط بـ `<URL>`
- استبدال الإيميلات بـ `<EMAIL>`
- استبدال أرقام الهاتف بـ `<PHONE>`
- استبدال أنماط OTP بـ `<OTP>`
- إزالة التشكيل والتطويل
- توحيد بعض الحروف العربية: أ/إ/آ -> ا ، ى -> ي
- ضغط الفراغات وإزالة الضجيج الزائد
- فلترة النصوص غير العربية أو النصوص القصيرة جدًا

> ملاحظة: تم اعتماد **تنظيف خفيف** وليس تنظيفًا عنيفًا، لأن نماذج Transformer مثل AraBERT تستفيد من بقاء بنية النص قريبة من الطبيعي.

## 4) الملفات الناتجة
### الملفات الأساسية
- `arabic_phishing_guard_project_ready_full.csv`  
  Dataset الرئيسية بعد التنظيف
- `arabic_phishing_guard_project_ready_balanced.csv`  
  نسخة متوازنة (phishing = legit) لتجارب baseline السريعة
- `arabic_phishing_guard_train.csv`
- `arabic_phishing_guard_val.csv`
- `arabic_phishing_guard_test.csv`

### ملفات مبسطة للتدريب
- `arabic_phishing_guard_train_simple.csv`
- `arabic_phishing_guard_val_simple.csv`
- `arabic_phishing_guard_test_simple.csv`

### ملفات مساعدة
- `arabic_phishing_guard_positive_phrases_aug.csv`
- `arabic_auxiliary_hsc_tweets_clean.csv`

## 5) أرقام dataset الرئيسية
- **Project-ready full**: 1710 سطر
- **Legit**: 1298
- **Phishing**: 412
- **Channels**: email:1500, sms:210

- **Project-ready balanced**: 824 سطر
- **Legit = Phishing =** 412

## 6) لماذا أوصي بنسختين؟
### النسخة الكاملة
مفيدة عندما تريد تدريب جاد مع class weights أو weighted loss.

### النسخة المتوازنة
ممتازة كنسخة بداية للتجارب الأولى أو baseline أو fine-tuning سريع.

## 7) أي ملف أنصحك به الآن؟
### إذا كنت ستبدأ AraBERT لأول مرة:
ابدأ بـ:
- `arabic_phishing_guard_train_simple.csv`
- `arabic_phishing_guard_val_simple.csv`
- `arabic_phishing_guard_test_simple.csv`

وهذه الملفات مبنية من **النسخة المتوازنة** لتسهيل أول تجربة.

## 8) توصية تدريب AraBERT
- استخدم **binary classification**
- labels:
  - legit = 0
  - phishing = 1
- ابدأ بـ `max_length = 256`
- `batch_size = 8` أو `16` بحسب ذاكرة GPU
- `epochs = 3` كبداية
- راقب:
  - F1-score
  - Recall for phishing

## 9) ملاحظات مهمة
- Dataset الـ HSC ليست سيئة، لكنها **أقرب إلى spam/promotional tweets** من كونها phishing رسائل حقيقي.
- جمل `Arabic Phishing Sentences` ممتازة كتعزيز training فقط، لكنها **لا يجب أن تدخل الاختبار النهائي**.
- تم استبعاد رسائل SMS التسويقية العامة من الإيجابيات كلما أمكن، والإبقاء على العينات الأقرب للتصيّد الحقيقي.

## 10) الخلاصة
الملف الأنسب للمشروع الآن هو:
**`arabic_phishing_guard_project_ready_full.csv`**  
وللتدريب الأول السريع:
**`arabic_phishing_guard_train_simple.csv` / `val` / `test`**
