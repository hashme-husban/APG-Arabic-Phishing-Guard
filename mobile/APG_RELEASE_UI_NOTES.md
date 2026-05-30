# APG Release UI Update

هذه النسخة مبنية على `apg_ui_v2_final_demo_hotfix_icons_confirmed` وتم تعديلها لتكون أكثر هدوءًا وجاهزية للإطلاق مع الحفاظ على هوية Dark Cybersecurity وواجهة RTL.

## أهم الملفات المعدلة

- `lib/theme/app_tokens.dart`
- `lib/screens/home_screen.dart`
- `lib/screens/analyze_screen.dart`
- `lib/widgets/analyze_form_card.dart`
- `lib/widgets/apg_header_card.dart`
- `lib/screens/result_details_screen.dart`
- `lib/screens/notifications_screen.dart`
- `lib/utils/text_mapper.dart`
- `lib/widgets/apg_ui.dart`
- `lib/l10n/app_localizations.dart`
- `lib/l10n/generated/app_localizations.dart`

## ما تم تحسينه

- تهدئة الألوان والتوهج والظلال لتبدو الواجهة أقرب لمنتج نهائي.
- ترتيب الصفحة الرئيسية: حالة الحماية، التحليل، النصيحة، الإحصائيات، آخر نتيجة، أحدث التحليلات.
- اختصار شارات كرت الحالة العامة إلى شارتين فقط.
- تحسين كرت نصيحة اليوم بنص أقصر.
- جعل صفحة التحليل أوضح بعنوان ووصف مباشر.
- تحويل خيارات التحليل إلى: SMS، Email، رابط، نص.
- تحسين placeholders في حقول التحليل.
- تغيير زر التحليل إلى “تحليل الرسالة”.
- إزالة النص التقني الخاص بعقد API من الواجهة.
- تحسين شاشة نتيجة التحليل بإضافة:
  - الرسالة الأصلية مع زر نسخ النص.
  - الرابط المكتشف مع زر نسخ الرابط.
  - معلومات التحليل: التاريخ، نوع الرسالة، المصدر، وحالة الحفظ.
- تحسين Empty State في الإشعارات ونصوص الوصول للإشعارات بالعربية.
- إبقاء ميزة الإبلاغ عن نتيجة غير دقيقة كما هي.
- التأكد من إزالة `Icons.shield_search_rounded` نهائيًا.

## ملاحظات تشغيل

لم يتم تغيير backend أو API contract. لم تتم إضافة packages جديدة أو صور خارجية.

بيئة ChatGPT لا تحتوي على Flutter/Dart، لذلك لم يتم تشغيل `flutter analyze` هنا. تم إجراء فحص ثابت للملفات والتأكد من عدم وجود الأيقونة غير المدعومة السابقة.
