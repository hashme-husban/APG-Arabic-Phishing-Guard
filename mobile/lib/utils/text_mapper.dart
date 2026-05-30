import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../theme/app_tokens.dart';

class TextMapper {
  static bool _isArabicLocale(String localeCode) {
    return localeCode.toLowerCase().startsWith('ar');
  }

  static String _localeOf(BuildContext context) {
    return Localizations.localeOf(context).languageCode.toLowerCase();
  }

  static String label(BuildContext context, String value) =>
      _label(_localeOf(context), value);
  static String labelArabic(String value) => _label('ar', value);
  static String labelEnglish(String value) => _label('en', value);

  static String status(BuildContext context, String value) =>
      _status(_localeOf(context), value);
  static String statusArabic(String value) => _status('ar', value);
  static String statusEnglish(String value) => _status('en', value);

  static String channel(BuildContext context, String value) =>
      _channel(_localeOf(context), value);
  static String channelArabic(String value) => _channel('ar', value);
  static String channelEnglish(String value) => _channel('en', value);

  static String layerName(BuildContext context, String value) =>
      _layerName(_localeOf(context), value);
  static String layerDescription(BuildContext context, String value) =>
      _layerDescription(_localeOf(context), value);

  static String _layerDescription(String locale, String value) {
    switch (value.trim().toLowerCase()) {
      case 'sender':
        return _pick(
          locale,
          'يفحص اسم المرسل: هل يبدو موثوقًا، مجهولًا، أو مشابهًا لجهة رسمية؟',
          'Checks whether the sender looks trusted, unknown, or impersonating an official entity.',
        );
      case 'policy':
        return _pick(
          locale,
          'يقيم مدى موثوقية تطابق الجهة المذكورة مع المرسل أو الرابط.',
          'Evaluates how trustworthy the claimed entity match is against the sender or link.',
        );
      case 'text':
        return _pick(
          locale,
          'يفحص النص بحثًا عن استعجال، تهديد، جوائز، أو طلب بيانات حساسة.',
          'Checks the text for urgency, threats, prizes, or sensitive data requests.',
        );
      case 'url':
        return _pick(
          locale,
          'يفحص الرابط أو النطاق: هل يبدو رسميًا أم يحتوي على مؤشرات احتيال؟',
          'Checks whether the link or domain looks official or has scam indicators.',
        );
      default:
        return _pick(
          locale,
          'مؤشر مستخدم في تقييم الرسالة.',
          'A signal used to evaluate the message.',
        );
    }
  }

  static String headline(BuildContext context, String value) =>
      _headline(_localeOf(context), value);
  static String headlineArabic(String value) => _headline('ar', value);
  static String summary(BuildContext context, String value) =>
      _summary(_localeOf(context), value);
  static String summaryArabic(String value) => _summary('ar', value);
  static String reason(BuildContext context, String value) =>
      _reason(_localeOf(context), value);
  static String reasonArabic(String value) => _reason('ar', value);
  static String action(BuildContext context, String value) =>
      _action(_localeOf(context), value);
  static String actionArabic(String value) => _action('ar', value);
  static String recommendation(BuildContext context, String value) =>
      _recommendation(_localeOf(context), value);
  static String recommendationArabic(String value) =>
      _recommendation('ar', value);
  static String error(BuildContext context, String value) =>
      _error(_localeOf(context), value);

  static String formatDateTime(BuildContext context, DateTime value) {
    final locale = _localeOf(context);
    try {
      final format = _isArabicLocale(locale)
          ? DateFormat('d MMM • HH:mm', 'ar')
          : DateFormat('MMM d • HH:mm', 'en');
      return format.format(value);
    } catch (_) {
      final hh = value.hour.toString().padLeft(2, '0');
      final mm = value.minute.toString().padLeft(2, '0');
      final dd = value.day.toString().padLeft(2, '0');
      final mo = value.month.toString().padLeft(2, '0');
      return '$dd/$mo • $hh:$mm';
    }
  }

  static Color riskColor(String label) => AppTokens.riskColor(label);

  static String _pick(String locale, String ar, String en) =>
      _isArabicLocale(locale) ? ar : en;

  static String _label(String locale, String value) {
    final normalized = value.trim().toLowerCase();
    if (normalized == 'url_brand_impersonation') {
      return _pick(locale, 'انتحال جهة في الرابط', 'Brand impersonation');
    }
    if (normalized == 'url_claimed_brand_domain_mismatch') {
      return _pick(locale, 'النطاق لا يطابق الجهة', 'Brand/domain mismatch');
    }
    if (normalized == 'entity_conflict_sender_domain') {
      return _pick(locale, 'تعارض بين المرسل والرابط', 'Sender/domain conflict');
    }
    if (normalized == 'entity_official_domain_alignment') {
      return _pick(locale, 'نطاق رسمي متطابق', 'Official domain match');
    }
    if (normalized.startsWith('entity_policy_forbidden_')) {
      return _pick(
        locale,
        'طلب محظور من جهة معروفة',
        'Forbidden request for claimed entity',
      );
    }
    switch (value.trim().toLowerCase()) {
      case 'phishing':
      case 'dangerous':
      case 'high_risk':
      case 'malicious':
      case 'scam':
        return _pick(locale, 'خطر مرتفع', 'High risk');
      case 'suspicious':
      case 'warning':
        return _pick(locale, 'يحتاج تحققًا', 'Needs verification');
      case 'safe':
      case 'legit':
      case 'benign':
        return _pick(locale, 'مطمئن', 'Reassuring');
      case 'unknown':
        return _pick(locale, 'تعذر التحقق', 'Unknown');
      case 'conflicting':
        return _pick(locale, 'متعارض', 'Conflicting');
      case 'trusted':
        return _pick(locale, 'موثوق', 'Trusted');
      case 'absent':
        return _pick(locale, 'غير موجود', 'Absent');
      case 'not_evaluated':
        return _pick(locale, 'لم يتم التقييم', 'Not evaluated');
      case 'spoof_suspected':
      case 'sender_spoofed':
        return _pick(locale, 'هوية غير موثوقة', 'Untrusted identity');
      case 'compliant':
        return _pick(locale, 'متوافق', 'Consistent');
      case 'non_compliant':
        return _pick(locale, 'غير متوافق', 'Inconsistent');
      case 'low':
      case 'low_risk':
        return _pick(locale, 'منخفض', 'Low');
      case 'medium':
      case 'medium_risk':
        return _pick(locale, 'متوسط', 'Medium');
      case 'high':
        return _pick(locale, 'مرتفع', 'High');
      default:
        return value;
    }
  }

  static String _status(String locale, String value) => _label(locale, value);

  static String _channel(String locale, String value) {
    switch (value.trim().toLowerCase()) {
      case 'sms':
        return _pick(locale, 'رسالة SMS', 'SMS');
      case 'manual':
        return _pick(locale, 'يدوي', 'Manual');
      case 'unknown':
        return _pick(locale, 'تعذر التحقق', 'Unknown');
      case 'text':
        return _pick(locale, 'نص', 'Text');
      case 'url':
      case 'link':
        return _pick(locale, 'رابط', 'URL');
      case 'email':
      case 'mail':
        return _pick(locale, 'بريد إلكتروني', 'Email');
      case 'whatsapp':
      case 'واتساب':
        return _pick(locale, 'واتساب', 'WhatsApp');
      case 'telegram':
      case 'تيليجرام':
        return _pick(locale, 'تيليجرام', 'Telegram');
      case 'messaging':
      case 'notification':
      case 'app_notification':
      case 'إشعار تطبيق':
        return _pick(locale, 'إشعار', 'App notification');
      default:
        return value.isEmpty ? '-' : value;
    }
  }

  static String _layerName(String locale, String value) {
    switch (value.trim().toLowerCase()) {
      case 'sender':
        return _pick(locale, 'هوية المرسل', 'Sender identity');
      case 'policy':
        return _pick(locale, 'موثوقية الجهة المذكورة', 'Claimed entity trust');
      case 'text':
        return _pick(locale, 'محتوى الرسالة', 'Message content');
      case 'url':
        return _pick(locale, 'سلامة الرابط', 'Link safety');
      case 'spoof_suspected':
      case 'sender_spoofed':
        return _pick(locale, 'هوية غير موثوقة', 'Untrusted identity');
      case 'compliant':
        return _pick(locale, 'متوافق', 'Consistent');
      case 'non_compliant':
        return _pick(locale, 'غير متوافق', 'Inconsistent');
      case 'low':
      case 'low_risk':
        return _pick(locale, 'منخفض', 'Low');
      case 'medium':
      case 'medium_risk':
        return _pick(locale, 'متوسط', 'Medium');
      case 'high':
      case 'high_risk':
        return _pick(locale, 'مرتفع', 'High');
      default:
        return value;
    }
  }

  static String _headline(String locale, String value) {
    switch (value.trim()) {
      case 'High phishing risk detected':
        return _pick(
          locale,
          'تم اكتشاف خطر تصيّد مرتفع',
          'High phishing risk detected',
        );
      case 'Suspicious message detected':
        return _pick(
          locale,
          'تم اكتشاف رسالة مشبوهة',
          'Suspicious message detected',
        );
      case 'No strong phishing evidence detected':
      case 'Message appears safe':
        return _pick(
          locale,
          'لا يوجد دليل قوي على التصيّد',
          'No strong phishing evidence detected',
        );
      case 'Message analysis completed':
        return _pick(
          locale,
          'اكتمل تحليل الرسالة',
          'Message analysis completed',
        );
      default:
        return value.isEmpty
            ? _pick(locale, 'اكتمل التحليل', 'Analysis completed')
            : value;
    }
  }

  static String _summary(String locale, String value) {
    switch (value.trim()) {
      case 'The message shows strong phishing indicators across multiple layers.':
        return _pick(
          locale,
          'تظهر الرسالة مؤشرات قوية على التصيّد في أكثر من جانب من جوانب الفحص.',
          'The message shows strong phishing indicators across multiple layers.',
        );
      case 'The message is not clearly safe and should be verified before any action.':
        return _pick(
          locale,
          'الرسالة ليست آمنة بشكل واضح، ويُنصح بالتحقق منها قبل اتخاذ أي إجراء.',
          'The message is not clearly safe and should be verified before any action.',
        );
      case 'No strong phishing indicators were found, but sensitive actions should still use official channels.':
      case 'The message does not show strong phishing indicators at the moment.':
        return _pick(
          locale,
          'لا تظهر الرسالة مؤشرات قوية على التصيّد، لكن الإجراءات الحساسة يجب أن تتم عبر القنوات الرسمية.',
          'No strong phishing indicators were found, but sensitive actions should still use official channels.',
        );
      case 'spoof_suspected':
      case 'sender_spoofed':
        return _pick(locale, 'هوية غير موثوقة', 'Untrusted identity');
      case 'compliant':
        return _pick(locale, 'متوافق', 'Consistent');
      case 'non_compliant':
        return _pick(locale, 'غير متوافق', 'Inconsistent');
      case 'low':
      case 'low_risk':
        return _pick(locale, 'منخفض', 'Low');
      case 'medium':
      case 'medium_risk':
        return _pick(locale, 'متوسط', 'Medium');
      case 'high':
      case 'high_risk':
        return _pick(locale, 'مرتفع', 'High');
      default:
        return value;
    }
  }

  static String _reason(String locale, String value) {
    final key = value.trim();
    final normalized = key.toLowerCase();
    if (normalized == 'url_brand_impersonation') {
      return _pick(
        locale,
        'الرابط يستخدم اسم جهة معروفة خارج نطاقها الرسمي.',
        'The link uses a known brand outside its official domain.',
      );
    }
    if (normalized == 'url_claimed_brand_domain_mismatch') {
      return _pick(
        locale,
        'نطاق الرابط لا يطابق الجهة المذكورة في الرسالة.',
        'The link domain does not match the claimed entity.',
      );
    }
    if (normalized == 'entity_conflict_sender_domain') {
      return _pick(
        locale,
        'يوجد تعارض بين هوية المرسل والجهة المرتبطة بالرابط.',
        'The sender identity conflicts with the linked domain entity.',
      );
    }
    if (normalized == 'entity_official_domain_alignment') {
      return _pick(
        locale,
        'الرابط يتبع نطاقًا رسميًا للجهة المذكورة.',
        'The link belongs to an official domain for the claimed entity.',
      );
    }
    if (normalized.startsWith('entity_policy_forbidden_')) {
      return _pick(
        locale,
        'الرسالة تطلب بيانات حساسة لا تطلبها هذه الجهة عبر الرسائل.',
        'The message asks for sensitive data this entity should not request by message.',
      );
    }
    const map = {
      'Text analysis strongly indicates phishing-like content.':
          'تحليل النص يشير بقوة إلى محتوى شبيه بالتصيّد.',
      'Text analysis leans toward safe content.':
          'تحليل النص يميل إلى أن المحتوى آمن.',
      'URL analysis indicates a high-risk or phishing-like link.':
          'تحليل الرابط يشير إلى رابط عالي الخطورة أو شبيه بالتصيّد.',
      'No URL was available, so the final decision relies on the other layers.':
          'لم يتوفر رابط، لذلك اعتمد التقييم على النص والمرسل وباقي المؤشرات.',
      'The requested behavior conflicts with the expected policy of the claimed entity.':
          'الثقة بالجهة المذكورة منخفضة بسبب تعارضها مع المرسل أو الرابط.',
      'The message behavior is broadly consistent with the claimed policy profile.':
          'الجهة المذكورة تبدو متسقة عمومًا مع هوية المرسل أو الرابط.',
      'Sender verification provides trusted evidence.':
          'التحقق من المرسل يعطي مؤشر ثقة.',
      'Sender identity appears inconsistent with the claimed entity.':
          'هوية المرسل تبدو غير متسقة مع الجهة المدعاة.',
      'Sender verification provides no trust evidence.':
          'التحقق من المرسل لا يوفر دليل ثقة.',
      'Text and URL layers strongly agree on a phishing verdict.':
          'طبقتا النص والرابط تتفقان بقوة على وجود خطر تصيّد.',
      'The layers disagree noticeably, so the final decision stays cautious.':
          'هناك اختلاف واضح بين المؤشرات، لذلك يبقى القرار حذرًا.',
      'The combined risk across the active layers is high enough for a phishing decision.':
          'المؤشرات المجمعة كافية لتصنيف الرسالة كاحتيال.',
      'The combined evidence is low-risk enough for a safe decision.':
          'الأدلة المجمعة منخفضة الخطورة بما يكفي لتصنيف الرسالة كآمنة.',
      'The overall evidence stays in an ambiguous zone, so the message is marked suspicious.':
          'الأدلة العامة لا تزال في منطقة غير حاسمة، لذلك تم تصنيف الرسالة كمشبوهة.',
      'The sender is not recognized.': 'تعذر التحقق من المرسل.',
      'The message contains urgent pressure language.':
          'الرسالة تحتوي على لغة ضغط واستعجال.',
      'The message asks for sensitive credentials or OTP.':
          'الرسالة تطلب بيانات حساسة أو رمز OTP.',
      'The URL appears deceptive or unusual.':
          'الرابط يبدو مخادعًا أو غير معتاد.',
      'The URL domain does not match the claimed brand.':
          'نطاق الرابط لا يطابق الجهة المدعاة.',
      'Multiple layers indicate phishing risk.':
          'عدة مؤشرات تشير إلى خطر تصيّد.',
      'No URL was provided for inspection.': 'لم يتم توفير رابط للفحص.',
      'The content requests verification of banking data.':
          'المحتوى يطلب التحقق من بيانات بنكية.',
      'The content appears promotional or informational without strong abuse indicators.':
          'يبدو المحتوى معلوماتيًا أو ترويجيًا دون مؤشرات إساءة قوية.',
    };

    if (_isArabicLocale(locale) && map.containsKey(key)) return map[key]!;
    return value;
  }

  static String _action(String locale, String value) {
    final key = value.trim();
    const map = {
      'Do not click the link': 'لا تضغط على الرابط.',
      'Do not click the link.': 'لا تضغط على الرابط.',
      'Do not reply with OTPs or credentials':
          'لا ترد بأي رمز تحقق أو بيانات دخول.',
      'Do not share OTP, passwords, or banking details.':
          'لا تشارك OTP أو كلمات المرور أو البيانات البنكية.',
      'Verify through the official website or app':
          'تحقق عبر الموقع أو التطبيق الرسمي.',
      'Verify the message using an official channel.':
          'تحقق من الرسالة عبر قناة رسمية.',
      'Do not take action yet': 'لا تتخذ أي إجراء الآن.',
      'Verify through an official channel': 'تحقق عبر قناة رسمية.',
      'Avoid opening links until verified': 'تجنب فتح الروابط حتى يتم التحقق.',
      'Use the official website or app for sensitive actions':
          'استخدم الموقع أو التطبيق الرسمي للإجراءات الحساسة.',
      'Stay cautious with future messages': 'ابقَ حذرًا مع الرسائل القادمة.',
      'Block or report the sender if the message is malicious.':
          'احظر المرسل أو أبلغ عنه إذا كانت الرسالة خبيثة.',
      'Open the official website manually instead of using the provided link.':
          'افتح الموقع الرسمي يدويًا بدلًا من استخدام الرابط المرسل.',
      'Treat the request with caution until verified.':
          'تعامل مع الطلب بحذر حتى يتم التحقق منه.',
    };

    if (_isArabicLocale(locale) && map.containsKey(key)) return map[key]!;
    return value;
  }

  static String _recommendation(String locale, String value) {
    final key = value.trim();
    const map = {
      'Avoid interacting with this message and verify through official channels.':
          'تجنب التفاعل مع هذه الرسالة وتحقق عبر القنوات الرسمية.',
      'Proceed cautiously and verify the request before taking any action.':
          'تابع بحذر وتحقق من الطلب قبل اتخاذ أي إجراء.',
      'No immediate threat is visible, but continue using normal caution.':
          'لا يوجد تهديد مباشر ظاهر، لكن استمر باتباع الحذر المعتاد.',
      'Do not click the link, do not reply with OTPs or credentials, and verify the request through the official website or app.':
          'لا تضغط على الرابط، ولا ترد بأي رمز تحقق أو بيانات دخول، وتحقق من الطلب عبر الموقع أو التطبيق الرسمي.',
      'Do not take action yet. Verify the message through an official channel before opening links or sharing any sensitive data.':
          'لا تتخذ أي إجراء الآن. تحقق من الرسالة عبر قناة رسمية قبل فتح الروابط أو مشاركة أي بيانات حساسة.',
      'No strong phishing evidence was found. For sensitive actions, it is still safer to use the official website or app directly.':
          'لا يوجد دليل قوي على التصيّد. للإجراءات الحساسة، يبقى من الآمن استخدام الموقع أو التطبيق الرسمي مباشرة.',
      'Do not click the link': 'لا تضغط على الرابط.',
      'Do not take action yet': 'لا تتخذ أي إجراء الآن.',
      'Use the official website or app for sensitive actions':
          'استخدم الموقع أو التطبيق الرسمي للإجراءات الحساسة.',
    };

    if (_isArabicLocale(locale) && map.containsKey(key)) return map[key]!;
    if (key.isEmpty) {
      return _pick(
        locale,
        'راجع الرسالة بحذر واستخدم القنوات الرسمية عند وجود أي إجراء حساس.',
        'Review the message carefully and use official channels for any sensitive action.',
      );
    }
    return value;
  }

  static String _error(String locale, String value) {
    switch (value.trim()) {
      case 'Please enter a message text or URL.':
        return _pick(
          locale,
          'اكتب نص الرسالة أو الرابط على الأقل.',
          'Please enter a message text or URL.',
        );
      case 'Bad request. Make sure to provide message text or a URL.':
        return _pick(
          locale,
          'الطلب غير صحيح. تأكد من إدخال نص الرسالة أو الرابط.',
          'Bad request. Make sure to provide message text or a URL.',
        );
      case 'Unable to connect to the server. Make sure the API is running and the base URL is correct.':
        return _pick(
          locale,
          'تعذر الاتصال بالخادم. تأكد أن الـ API يعمل وأن العنوان صحيح.',
          'Unable to connect to the server. Make sure the API is running and the base URL is correct.',
        );
      case 'Unable to reach the analysis server. Check that the API is running and that the emulator or device can access the backend.':
        return _pick(
          locale,
          'تعذر الوصول إلى خادم التحليل. تأكد أن الـ API يعمل وأن المحاكي أو الجهاز يمكنه الوصول إلى الخادم.',
          'Unable to reach the analysis server. Check that the API is running and that the emulator or device can access the backend.',
        );
      case 'The server took too long to respond.':
        return _pick(
          locale,
          'استغرق الخادم وقتًا طويلًا في الرد.',
          'The server took too long to respond.',
        );
      case 'The analysis server returned an internal error.':
        return _pick(
          locale,
          'أعاد خادم التحليل خطأً داخليًا. جرّب مرة أخرى بعد قليل.',
          'The analysis server returned an internal error.',
        );
      case 'The analysis request failed with status 404.':
        return _pick(
          locale,
          'تعذر العثور على مسار التحليل على الخادم. تحقق من عنوان الـ API.',
          'The analysis request failed with status 404.',
        );
      case 'Unexpected response format from the analysis server.':
        return _pick(
          locale,
          'أعاد خادم التحليل صيغة غير متوقعة. تحقق من إعدادات الـ API أو جرّب مرة أخرى.',
          'Unexpected response format from the analysis server.',
        );
      case 'The server response was not valid JSON.':
        return _pick(
          locale,
          'استجابة الخادم ليست JSON صحيحًا.',
          'The server response was not valid JSON.',
        );
      case 'spoof_suspected':
      case 'sender_spoofed':
        return _pick(locale, 'هوية غير موثوقة', 'Untrusted identity');
      case 'compliant':
        return _pick(locale, 'متوافق', 'Consistent');
      case 'non_compliant':
        return _pick(locale, 'غير متوافق', 'Inconsistent');
      case 'low':
      case 'low_risk':
        return _pick(locale, 'منخفض', 'Low');
      case 'medium':
      case 'medium_risk':
        return _pick(locale, 'متوسط', 'Medium');
      case 'high':
      case 'high_risk':
        return _pick(locale, 'مرتفع', 'High');
      default:
        return value;
    }
  }
}
