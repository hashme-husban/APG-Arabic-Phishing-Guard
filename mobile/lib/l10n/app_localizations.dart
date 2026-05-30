import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

class AppLocalizations {
  const AppLocalizations(this.locale);

  final Locale locale;

  static AppLocalizations of(BuildContext context) {
    final value = Localizations.of<AppLocalizations>(context, AppLocalizations);
    assert(value != null, 'AppLocalizations not found in context.');
    return value!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
  ];

  bool get isArabic => locale.languageCode.toLowerCase() == 'ar';

  String _t(String ar, String en) => isArabic ? ar : en;

  String get appTitle => 'Arabic Phishing Guard';
  String get home => _t('الرئيسية', 'Home');
  String get analyze => _t('التحليل', 'Analyze');
  String get notifications => _t('الإشعارات', 'Notifications');
  String get inboxNav => _t('الإشعارات', 'Inbox');
  String get history => _t('السجل', 'History');
  String get settings => _t('الإعدادات', 'Settings');
  String get quickScan => _t('تحليل سريع', 'Quick Scan');
  String get quickScanFab => _t('تحليل سريع', 'Quick Scan');
  String get fullAnalysis => _t('تحليل كامل', 'Full Analysis');
  String get securityDashboard => _t('لوحة الأمان', 'Security Dashboard');
  String get securityDashboardSubtitle => _t(
    'نظرة سريعة على التحليلات، الإشعارات، وحالة الحماية.',
    'A clean overview of analyses, alerts, and protection status.',
  );
  String get quickActions => _t('إجراءات سريعة', 'Quick actions');
  String get quickScanSubtitle => _t(
    'افحص رسالة بسرعة من أسفل الشاشة.',
    'Run a fast scan from the bottom sheet.',
  );
  String get fullAnalysisSubtitle => _t(
    'افتح شاشة التحليل الكاملة مع تفاصيل أوضح.',
    'Open the full analysis screen with richer details.',
  );
  String get notificationsSubtitle => _t(
    'راجع الإشعارات الملتقطة والمحللة.',
    'Review captured and analyzed notifications.',
  );
  String get historySubtitle => _t(
    'ابحث وفلتر وافتح التفاصيل بسرعة.',
    'Search, filter, and inspect past analyses quickly.',
  );
  String get settingsSubtitle => _t(
    'تحكم بالمظهر، اللغة، الحفظ، والربط مع الإشعارات.',
    'Manage appearance, language, storage, and notification access.',
  );
  String get latestResult => _t('آخر نتيجة', 'Latest result');
  String get recentAnalyses => _t('أحدث التحليلات', 'Recent analyses');
  String get securitySummary => _t('الملخص الأمني', 'Security summary');
  String get averageRisk => _t('متوسط الخطر', 'Average risk');
  String get analyses => _t('التحليلات', 'Analyses');
  String get monitoredApps => _t('التطبيقات المراقبة', 'Monitored apps');
  String get notificationAccess =>
      _t('صلاحية الإشعارات', 'Notification access');
  String get serverConnection => _t('اتصال الخادم', 'Server connection');
  String get checkConnection => _t('فحص الاتصال', 'Check connection');
  String get checkingConnection =>
      _t('جارٍ فحص الاتصال...', 'Checking connection...');
  String get accessGranted => _t('تم منح الصلاحية', 'Access granted');
  String get accessRequired => _t('الصلاحية مطلوبة', 'Access required');
  String get serverOnline => _t('الخادم متصل', 'Server online');
  String get serverOffline => _t('الخادم غير متصل', 'Server offline');
  String serverConnectionOnline(String address) =>
      _t('تم الاتصال بخادم التحليل', 'Connected to the analysis server');
  String serverConnectionOffline(String address) => _t(
    'تعذر الوصول إلى خادم التحليل الآن.',
    'The analysis server could not be reached right now.',
  );
  String get serverConnectionHelp => _t(
    'استخدم فحص الاتصال للتأكد من أن خادم التحليل متاح.',
    'Use Check connection to verify that the analysis server is reachable.',
  );
  String get startAnalysis => _t('ابدأ التحليل', 'Start analysis');
  String get startAnalysisHint => _t(
    'الصق رسالة أو رابطًا، أو استخدم مثالًا جاهزًا لتجربة سريعة.',
    'Paste a message or URL, or use a ready sample for a quick test.',
  );
  String get sender => _t('المرسل', 'Sender');
  String get senderOptional => _t('المرسل (اختياري)', 'Sender (optional)');
  String get messageText => _t('نص الرسالة', 'Message text');
  String get messageHint => _t(
    'الصق الرسالة أو اكتبها هنا...',
    'Paste the message or type it here...',
  );
  String get pasteText => _t('لصق النص', 'Paste text');
  String get url => _t('الرابط', 'URL');
  String get urlOptional => _t('الرابط (اختياري)', 'URL (optional)');
  String get pasteUrl => _t('لصق الرابط', 'Paste URL');
  String get analyzeMessage => _t('تحليل الرسالة', 'Analyze message');
  String get analyzing => _t('جاري التحليل...', 'Analyzing...');
  String get clear => _t('مسح', 'Clear');
  String get copy => _t('نسخ', 'Copy');
  String get copied => _t('تم النسخ.', 'Copied.');
  String get share => _t('مشاركة', 'Share');
  String get shareOpened => _t('تم فتح نافذة المشاركة.', 'Share sheet opened.');
  String get details => _t('التفاصيل', 'Details');
  String get openDetails => _t('فتح التفاصيل', 'Open details');
  String get delete => _t('حذف', 'Delete');
  String get deleteFromHistory => _t('حذف من السجل', 'Delete from history');
  String get cancel => _t('إلغاء', 'Cancel');
  String get actions => _t('إجراءات', 'Actions');
  String get reasons =>
      _t('لماذا ظهرت هذه النتيجة؟', 'Why did this result appear?');
  String get recommendedActions =>
      _t('ماذا أفعل الآن؟', 'What should I do now?');
  String get layerBreakdown => _t('منهجية التقييم', 'Evaluation methodology');
  String get finalRecommendation =>
      _t('التوصية النهائية', 'Final recommendation');
  String get quickInfo => _t('معلومات سريعة', 'Quick info');
  String get label => _t('التصنيف', 'Label');
  String get score => _t('درجة الخطورة', 'Risk score');
  String get confidence => _t('مستوى الثقة', 'Confidence level');
  String get channel => _t('القناة', 'Channel');
  String get claimedEntity => _t('الجهة المذكورة', 'Mentioned entity');
  String get inputData => _t('بيانات الإدخال', 'Input data');
  String get noTextAvailable => _t('لا يوجد نص متاح', 'No text available');
  String get noContentAvailable => _t('لا يوجد محتوى', 'No content available');
  String get clipboardEmpty => _t('الحافظة فارغة.', 'Clipboard is empty.');
  String get textPasted => _t('تم لصق النص.', 'Text pasted.');
  String get urlPasted => _t('تم لصق الرابط.', 'URL pasted.');
  String get fieldsCleared => _t('تم مسح الحقول.', 'Fields cleared.');
  String get resultCopied => _t('تم نسخ النتيجة.', 'Result copied.');
  String get detailsCopied => _t('تم نسخ التفاصيل.', 'Details copied.');
  String get enterMessageOrUrl => _t(
    'اكتب نص الرسالة أو الرابط على الأقل.',
    'Enter message text or a URL at minimum.',
  );
  String get examplePhishing => _t('مثال احتيال', 'Phishing sample');
  String get exampleSuspicious => _t('مثال مشبوه', 'Suspicious sample');
  String get exampleSafe => _t('مثال آمن', 'Safe sample');
  String get analyzingTitle =>
      _t('جاري تحليل الرسالة...', 'Analyzing the message...');
  String get analyzingSubtitle => _t(
    'نراجع النص والرابط والمرسل لإنتاج قرار واضح للمستخدم.',
    'We are checking the text, URL, and sender to build a clear user-facing verdict.',
  );
  String get historyEmptyTitle => _t('لا يوجد سجل بعد', 'No history yet');
  String get historyEmptySubtitle => _t(
    'بعد تنفيذ أول تحليل، ستظهر النتائج هنا لتراجعها لاحقًا.',
    'Your saved analyses will appear here after the first scan.',
  );
  String get matchingResultsTitle =>
      _t('لا توجد نتائج مطابقة', 'No matching results');
  String get matchingResultsSubtitle => _t(
    'جرّب تغيير الفلتر أو تعديل عبارة البحث.',
    'Try changing the filter or editing the search phrase.',
  );
  String get searchHistory => _t('بحث داخل السجل', 'Search history');
  String get searchHistoryHint => _t(
    'ابحث بالمرسل أو النص أو الرابط...',
    'Search by sender, text, or URL...',
  );
  String get searchNotifications =>
      _t('بحث داخل الإشعارات', 'Search notifications');
  String get searchNotificationsHint => _t(
    'ابحث بالتطبيق أو العنوان أو المحتوى...',
    'Search by app, title, or content...',
  );
  String get all => _t('الكل', 'All');
  String get phishing => _t('خطر مرتفع', 'High risk');
  String get suspicious => _t('مشبوه', 'Suspicious');
  String get safe => _t('آمن', 'Safe');
  String get analyzed => _t('محلّل', 'Analyzed');
  String get highRisk => _t('خطر مرتفع', 'High risk');
  String get raw => _t('خام', 'Raw');
  String get total => _t('الإجمالي', 'Total');
  String get shown => _t('المعروض', 'Shown');
  String get notAnalyzed => _t('غير محلّل', 'Not analyzed');
  String get noAnalysisToShare => _t(
    'لا توجد نتيجة تحليل لمشاركتها بعد.',
    'No analysis result is available to share yet.',
  );
  String get notificationsInbox => _t('صندوق الإشعارات', 'Notifications Inbox');
  String get notificationsInboxSubtitle => _t(
    'التقاط الإشعارات، تحليلها، ثم مراجعتها من مكان واحد.',
    'Capture notifications, analyze them, and review everything in one place.',
  );
  String get permissionCardTitle =>
      _t('حالة الربط مع النظام', 'System connection');
  String get permissionCardGranted => _t(
    'تم منح التطبيق صلاحية الوصول إلى الوصول للإشعارات.',
    'Notification access is already granted for the app.',
  );
  String get permissionCardRequired => _t(
    'لم يتم منح صلاحية الوصول للإشعارات بعد. افتح الإعدادات وفعّلها.',
    'Notification access has not been granted yet. Open settings and enable it.',
  );
  String get autoAnalyzeOn =>
      _t('التحليل التلقائي مفعّل', 'Auto-analysis is on');
  String get autoAnalyzeOff =>
      _t('التحليل التلقائي متوقف', 'Auto-analysis is off');
  String get grantPermission => _t('منح الصلاحية', 'Grant access');
  String get recheckPermission => _t('إعادة التحقق', 'Check again');
  String get openSettings => _t('الإعدادات', 'Settings');
  String get notificationsEmptyTitle =>
      _t('لا توجد إشعارات مطابقة', 'No matching notifications');
  String get notificationsEmptySubtitle => _t(
    'جرّب تغيير الفلتر أو عبارة البحث، أو فعّل الوصول للإشعارات أولًا.',
    'Try changing the filter or search, or enable notification access first.',
  );
  String get notificationDeleted =>
      _t('تم حذف الإشعار.', 'Notification deleted.');
  String get historyDeleted =>
      _t('تم حذف العنصر من السجل.', 'History item deleted.');
  String get confirmDeleteHistoryItemTitle => _t('حذف العنصر', 'Delete item');
  String get confirmDeleteHistoryItemMessage => _t(
    'هل تريد حذف هذا العنصر من السجل؟',
    'Do you want to delete this item from history?',
  );
  String get confirmDeleteNotificationTitle =>
      _t('حذف الإشعار', 'Delete notification');
  String get confirmDeleteNotificationMessage => _t(
    'هل تريد حذف هذا الإشعار من صندوق الإشعارات؟',
    'Do you want to delete this notification from the inbox?',
  );
  String get analysisDetails => _t('نتيجة التحليل', 'Analysis result');
  String get clearHistory => _t('مسح السجل', 'Clear history');
  String get clearNotifications => _t('مسح الإشعارات', 'Clear notifications');
  String get confirmClearHistoryTitle => _t('مسح السجل', 'Clear history');
  String get confirmClearHistoryEmpty =>
      _t('السجل فارغ بالفعل.', 'History is already empty.');
  String get confirmClearHistoryPrompt => _t(
    'هل تريد حذف كل عناصر السجل المحلية؟',
    'Do you want to delete all local history items?',
  );
  String get confirmClearNotificationsTitle =>
      _t('مسح صندوق الإشعارات', 'Clear notifications inbox');
  String get confirmClearNotificationsEmpty => _t(
    'صندوق الإشعارات فارغ بالفعل.',
    'The notifications inbox is already empty.',
  );
  String get confirmClearNotificationsPrompt => _t(
    'هل تريد حذف كل عناصر صندوق الإشعارات المحلية؟',
    'Do you want to delete all local notification inbox items?',
  );
  String get historyCleared => _t('تم مسح السجل بالكامل.', 'History cleared.');
  String get notificationsCleared =>
      _t('تم مسح صندوق الإشعارات بالكامل.', 'Notifications inbox cleared.');
  String get darkMode => _t('الوضع الداكن', 'Dark mode');
  String get darkModeSubtitle => _t(
    'تبديل مظهر التطبيق بين الفاتح والداكن.',
    'Switch between the light and dark appearance.',
  );
  String get saveHistory => _t('حفظ السجل محليًا', 'Save history locally');
  String get autoAnalyzeNotifications =>
      _t('التحليل التلقائي للإشعارات', 'Auto-analyze notifications');
  String saveHistorySubtitle(int count) => _t(
    'الاحتفاظ بنتائج التحليل داخل الجهاز. العناصر الحالية: $count',
    'Keep analysis results on the device. Current items: $count',
  );
  String get autoAnalyzeNotificationsSubtitle => _t(
    'عند التفعيل، سيحلل التطبيق الإشعارات الملتقطة ويضيفها إلى صندوق الإشعارات.',
    'When enabled, captured notifications are analyzed and added to the inbox.',
  );
  String get language => _t('اللغة', 'Language');
  String get arabic => _t('العربية', 'Arabic');
  String get english => _t('الإنجليزية', 'English');
  String get monitoredAppsTitle => _t('التطبيقات المراقبة', 'Monitored apps');
  String get monitoredAppsSubtitle => _t(
    'اختر التطبيقات التي تريد مراقبة إشعاراتها وتحليلها.',
    'Choose which apps should be monitored and analyzed.',
  );
  String get restoreDefault => _t('استعادة الافتراضي', 'Restore defaults');
  String get dataManagement => _t('إدارة البيانات', 'Data management');
  String dataManagementSubtitle(int historyCount, int notificationCount) => _t(
    'السجل الحالي: $historyCount عنصر\nصندوق الإشعارات الحالي: $notificationCount عنصر',
    'Current history: $historyCount items\nCurrent notifications inbox: $notificationCount items',
  );
  String get aboutAppTitle => _t('حول التطبيق', 'About the app');
  String get aboutAppDescription => _t(
    'Arabic Phishing Guard يركز على تحليل الرسائل والروابط والإشعارات المشتبه بها مع تفسير واضح وواجهة أخف وأسهل.',
    'Arabic Phishing Guard focuses on analyzing suspicious messages, links, and notifications with clear explanations and a cleaner interface.',
  );
  String get onboardingTitle1 => _t(
    'مرحبًا بك في Arabic Phishing Guard',
    'Welcome to Arabic Phishing Guard',
  );
  String get onboardingDesc1 => _t(
    'حلّل الرسائل المشبوهة بسرعة وافهم القرار النهائي من دون تعقيد.',
    'Analyze suspicious messages quickly and understand the final decision without clutter.',
  );
  String get onboardingTitle2 =>
      _t('تحليل سريع وتحليل كامل', 'Quick scan and full analysis');
  String get onboardingDesc2 => _t(
    'ابدأ بـ Quick Scan للسرعة، أو افتح التحليل الكامل للمراجعة التفصيلية.',
    'Start with Quick Scan for speed, or open the full screen for deeper review.',
  );
  String get onboardingTitle3 => _t('صندوق الإشعارات', 'Notifications inbox');
  String get onboardingDesc3 => _t(
    'التقط إشعارات أندرويد وراجعها أو حللها تلقائيًا من مكان واحد.',
    'Capture Android notifications and review or analyze them from one place.',
  );
  String get next => _t('التالي', 'Next');
  String get skip => _t('تخطي', 'Skip');
  String get startNow => _t('ابدأ الآن', 'Start now');
  String get ready => _t('جاهز للفحص', 'Ready to scan');
  String get highRiskStatus => _t('خطر مرتفع', 'High risk');
  String get attentionStatus => _t('يحتاج انتباه', 'Needs attention');
  String get reassuringStatus => _t('مطمئن', 'Reassuring');
  String get readyHint => _t(
    'ابدأ أول تحليل لرؤية المؤشرات العامة هنا.',
    'Run your first analysis to populate the dashboard.',
  );
  String get highRiskHint => _t(
    'يوجد نشاط عالي الخطورة في النتائج الأخيرة. راجع السجل والتوصيات.',
    'Recent results show high-risk activity. Review history and recommendations.',
  );
  String get attentionHint => _t(
    'هناك نتائج تحتاج مراجعة، لكن الخطر ليس في أعلى مستوياته.',
    'Some results need review, but the risk is not at its highest level.',
  );
  String get reassuringHint => _t(
    'الوضع العام مطمئن نسبيًا بناءً على النتائج الأخيرة.',
    'The overall situation looks relatively reassuring based on recent results.',
  );
  String get goToAnalyze => _t('اذهب إلى التحليل', 'Go to analysis');
  String get latestResultEmpty => _t(
    'لا توجد نتائج محفوظة بعد. ابدأ أول تحليل من شاشة التحليل.',
    'No analysis has been saved yet. Start your first scan from the analysis screen.',
  );
  String get shareSubject => _t('نتيجة تحليل الرسالة', 'Analysis result');
  String get itemsWord => _t('عناصر', 'items');
  String get scoreShort => _t('خطورة', 'Risk');
  String get confidenceShort => _t('ثقة', 'Trust');
  String get overview => _t('نظرة عامة', 'Overview');

  // Navigation / app shell
  String get monitoring => _t('المراقبة', 'Monitoring');
  String get monitoringSubtitle => _t(
    'تحليل الإشعارات الواردة تلقائيًا من التطبيقات المحددة.',
    'Auto-analyze incoming notifications from selected apps.',
  );
  String get localDataUpdated =>
      _t('تم تحديث بيانات التطبيق المحلية', 'Local app data updated');
  String get historyUpdatedFromServer =>
      _t('تم تحديث السجل من الخادم', 'History synced from server');
  String get notificationPermUnavailable => _t(
    'صلاحية الإشعارات غير متاحة على هذا الجهاز حاليًا.',
    'Notification access is unavailable on this device.',
  );
  String get pressBackToExit =>
      _t('اضغط رجوع مرة أخرى للخروج', 'Press back again to exit');

  // Home screen
  String get overallProtectionStatus =>
      _t('الحالة العامة للحماية', 'Overall protection status');
  String get readyToStart => _t('جاهز للبدء', 'Ready to start');
  String get readyToStartHint => _t(
    'ابدأ بتحليل رسالة أو رابط للحصول على تقييم الحماية.',
    'Start by analyzing a message or URL for a protection assessment.',
  );
  String get protectionMonitoringActive =>
      _t('المراقبة مفعّلة', 'Monitoring active');
  String get monitoringAwaitingPermissionBadge =>
      _t('المراقبة بانتظار الصلاحية', 'Monitoring needs permission');
  String get enableAutoMonitorHint => _t(
    'فعّل صلاحية الإشعارات لتفعيل المراقبة التلقائية.',
    'Enable notification access to activate auto-monitoring.',
  );
  String monitoredAppsCountLabel(int count) =>
      _t('$count تطبيقات مراقبة', '$count apps monitored');
  String get startFirstAnalysisCta =>
      _t('ابدأ بأول تحليل', 'Start your first analysis');
  String get pasteMessageOrUrlHint => _t(
    'الصق رسالة أو رابطًا للحصول على تقييم واضح.',
    'Paste a message or URL for a clear assessment.',
  );
  String get todaysTip => _t('نصيحة اليوم', "Today's tip");
  String get anotherTip => _t('نصيحة أخرى', 'Another tip');
  String get noAnalysisYetTitle =>
      _t('لم يتم تحليل أي رسالة بعد', 'No messages analyzed yet');
  String get noAnalysisYetSubtitle => _t(
    'ابدأ بأول تحليل ليظهر ملخص النتيجة هنا.',
    'Start your first analysis to see a result summary here.',
  );
  String riskScoreLabel(int score) =>
      _t('درجة الخطورة: $score/100', 'Risk score: $score/100');
  String get viewDetailsLabel => _t('عرض التفاصيل', 'View details');

  // Analyze screen
  String get analyzePageSubtitle => _t(
    'الصق رسالة أو رابطًا وسيقوم APG بتقييم مستوى الخطورة.',
    'Paste a message or URL and APG will assess the risk level.',
  );
  String get analysisResult => _t('نتيجة التحليل', 'Analysis result');
  String get detectedReasons => _t('الأسباب المكتشفة', 'Detected reasons');
  String get savedToHistory =>
      _t('أضيفت النتيجة إلى السجل', 'Saved to history');
  String get copyResultLabel => _t('نسخ النتيجة', 'Copy result');
  String get analyzeAnother => _t('تحليل رسالة أخرى', 'Analyze another');
  String get scanningMessage => _t('جارِ فحص الرسالة', 'Scanning message');
  String get scanningSubtitle => _t(
    'APG يحلل النص والرابط والمؤشرات المتاحة الآن.',
    'APG is analyzing the text, URL, and available indicators.',
  );
  String get analyzeFailedTitle =>
      _t('تعذر إكمال التحليل', 'Could not complete analysis');
  String get retryLabel => _t('إعادة المحاولة', 'Retry');
  String get sessionExpiredError => _t(
    'انتهت الجلسة، يرجى تسجيل الدخول مجددًا',
    'Session expired, please log in again',
  );
  String get connectionError => _t(
    'تعذر الاتصال بالخادم\nتحقق من اتصال الإنترنت وحاول مرة أخرى',
    'Could not connect to server\nCheck your internet and try again',
  );
  String get emptyInputError => _t(
    'الرسالة فارغة أو غير صالحة للتحليل',
    'Message is empty or invalid for analysis',
  );
  String get noContentTitle =>
      _t('لا يوجد محتوى للتحليل', 'No content to analyze');
  String get textTooLongTitle =>
      _t('النص أطول من الحد المسموح', 'Text exceeds the allowed limit');
  String get invalidUrlTitle => _t('الرابط غير صالح', 'Invalid URL');
  String textTooLongMessage(int max) => _t(
    'النص طويل جدًا. اختصر الرسالة إلى $max حرفًا أو أقل ثم حاول مرة أخرى.',
    'Text is too long. Shorten it to $max characters or fewer and try again.',
  );

  // Monitoring screen
  String get readyForProtection => _t('جاهز للحماية', 'Ready for protection');
  String get autoMonitoringActive =>
      _t('المراقبة التلقائية مفعّلة.', 'Auto-monitoring is active.');
  String get noCheckRecordedYet =>
      _t('لا يوجد فحص مسجل بعد', 'No check recorded yet');
  String lastCheckLabel(String time) =>
      _t('آخر فحص: $time', 'Last check: $time');
  String get runningInBackground =>
      _t('يعمل في الخلفية', 'Running in background');
  String get setupRequired => _t('إعداد مطلوب', 'Setup required');
  String get monitoringChipActive => _t('المراقبة مفعلة', 'Monitoring active');
  String get awaitingPermission =>
      _t('بانتظار الصلاحية', 'Awaiting permission');
  String get managePermission => _t('إدارة الصلاحية', 'Manage permission');
  String get activatePermission => _t('تفعيل الصلاحية', 'Activate permission');
  String get manageApps => _t('إدارة التطبيقات', 'Manage apps');
  String get monitoringStatusUpdated =>
      _t('تم تحديث حالة المراقبة', 'Monitoring status updated');
  String get howMonitoringWorks =>
      _t('كيف تعمل المراقبة؟', 'How monitoring works?');
  String get monitoringHowPoint1 => _t(
    'يفحص الإشعارات من التطبيقات التي تختارها.',
    'Inspects notifications from apps you choose.',
  );
  String get monitoringHowPoint2 => _t(
    'يركز على مؤشرات التصيد والروابط والطلبات الحساسة.',
    'Focuses on phishing indicators, links, and sensitive requests.',
  );
  String get monitoringHowPoint3 => _t(
    'تُحفظ النتائج داخل التطبيق عند تفعيل السجل.',
    'Results are saved in the app when history is enabled.',
  );
  String get monitoringPrivacyNote => _t(
    'يفحص APG الإشعارات من التطبيقات التي تختارها فقط، ويمكنك إيقاف المراقبة في أي وقت.',
    'APG only checks notifications from apps you choose, and you can stop monitoring anytime.',
  );
  String get protectionPulse => _t('نبض الحماية', 'Protection pulse');
  String get lastAlertLabel => _t('آخر تنبيه', 'Last alert');
  String get noRecentAlerts => _t('لا توجد تنبيهات حديثة', 'No recent alerts');
  String get noAlertsTodayHint => _t(
    'لم تظهر مؤشرات تحتاج انتباهًا حتى الآن.',
    'No indicators of concern so far.',
  );
  String get suspiciousTodayLabel =>
      _t('الرسائل المشبوهة اليوم', 'Suspicious messages today');
  String get noSuspiciousToday =>
      _t('لا توجد رسائل مقلقة اليوم.', 'No concerning messages today.');
  String get checkRecentHistoryHint =>
      _t('راجع العناصر الأخيرة في السجل.', 'Review recent items in history.');
  String get linksNeedReviewLabel =>
      _t('الروابط التي تحتاج تحقق', 'Links that need review');
  String get noLinksNeedReview =>
      _t('لا توجد روابط تحتاج مراجعة الآن.', 'No links need review right now.');
  String get checkDomainHint => _t(
    'افتح التفاصيل لفحص النطاق قبل المتابعة.',
    'Open details to check the domain before proceeding.',
  );
  String get monitoringReadyTitle => _t('المراقبة جاهزة', 'Monitoring ready');
  String get notificationsWillAppear => _t(
    'ستظهر نتائج الإشعارات هنا عند وصولها.',
    'Notification results will appear here when they arrive.',
  );
  String get activateMonitoring => _t('تفعيل المراقبة', 'Activate monitoring');
  String get safeCountLabel => _t('آمنة', 'Safe');
  String get needsVerification => _t('تحتاج تحققًا', 'Needs verification');
  String get filterOther => _t('أخرى', 'Other');

  // History screen
  String get analyzeMessageButton => _t('تحليل رسالة', 'Analyze message');
  String get textCopied => _t('تم نسخ النص', 'Text copied');
  String get urlCopied => _t('تم نسخ الرابط', 'URL copied');

  // Settings screen
  String get appearanceAndLanguage =>
      _t('المظهر واللغة', 'Appearance & Language');
  String get notificationMonitoring =>
      _t('مراقبة الإشعارات', 'Notification monitoring');
  String get storageSection => _t('التخزين', 'Storage');
  String get analysisSection => _t('التحليل', 'Analysis');
  String get logoutLabel => _t('تسجيل الخروج', 'Log out');
  String get confirmLogoutTitle => _t('هل تريد تسجيل الخروج؟', 'Log out?');
  String get confirmLogoutMessage => _t(
    'سيتم إنهاء الجلسة والعودة إلى شاشة تسجيل الدخول.',
    'Your session will end and you will return to the login screen.',
  );
  String get settingsUpdated => _t('تم تحديث الإعدادات', 'Settings updated');
  String get languageUpdated => _t('تم تحديث اللغة', 'Language updated');
  String get clearHistoryLabel => _t('مسح السجل', 'Clear history');
  String get historyEmpty => _t('لا يوجد سجل لمسحه.', 'Nothing to clear.');
  String get confirmClearAllPrompt => _t(
    'هل تريد مسح كل نتائج التحليل المحفوظة؟',
    'Delete all saved analysis results?',
  );
  String get historyClearedSnack => _t('تم مسح السجل', 'History cleared');
  String get notificationPermEnabled =>
      _t('صلاحية الإشعارات مفعّلة', 'Notification access enabled');
  String get notificationPermDisabled =>
      _t('صلاحية الإشعارات غير مفعّلة', 'Notification access disabled');
  String get notificationPermEnabledHint => _t(
    'تُستخدم الصلاحية لفحص الإشعارات من التطبيقات التي تختارها فقط.',
    'Used to check notifications only from apps you choose.',
  );
  String get autoAnalyzeEnabledSnack =>
      _t('تم تفعيل التحليل التلقائي', 'Auto-analysis enabled');
  String get autoAnalyzeDisabledSnack =>
      _t('تم إيقاف التحليل التلقائي', 'Auto-analysis disabled');
  String get floatingAlertsTitle => _t('التنبيهات العائمة', 'Floating alerts');
  String get floatingAlertsEnabledSnack =>
      _t('تم تفعيل التنبيهات العائمة', 'Floating alerts enabled');
  String get floatingAlertsDisabledSnack =>
      _t('تم إيقاف التنبيهات العائمة', 'Floating alerts disabled');
  String get permEnabledLabel => _t('الصلاحية مفعلة', 'Permission enabled');
  String get permDisabledLabel =>
      _t('الصلاحية غير مفعلة', 'Permission not enabled');
  String saveHistorySubtitleLocal(int count) => _t(
    'يحفظ نتائج التحليل داخل التطبيق. عدد العناصر الحالية: $count',
    'Keep analysis results on the device. Current items: $count',
  );
  String get serverConnectedLabel => _t('الخادم متصل', 'Server connected');
  String get serverDisconnectedLabel =>
      _t('الخادم غير متصل', 'Server disconnected');
  String get checkingServerLabel => _t('جارِ الاختبار...', 'Testing...');
  String get recheckLabel => _t('إعادة الفحص', 'Recheck');
  String get retryConnectionLabel => _t('إعادة المحاولة', 'Retry');
  String get serverConnectedText =>
      _t('تم الاتصال بخادم التحليل', 'Connected to the analysis server');
  String get serverOfflineText => _t(
    'تعذر الوصول إلى خادم التحليل. تحقق من الاتصال وحاول مرة أخرى.',
    'Cannot reach the analysis server. Check your connection and try again.',
  );
  String get connectionSecureLabel => _t('الاتصال آمن', 'Connection secure');
  String get accentColorTitle => _t('لون الواجهة', 'Interface color');
  String get accentColorCurrentPrefix => _t('اللون الحالي: ', 'Current: ');
  String get accentColorApplyHint => _t(
    'يطبّق على الأزرار والتنقل والعناصر النشطة فقط.',
    'Applied to buttons, navigation, and active elements only.',
  );
  String get accentColorSheetTitle =>
      _t('اختيار لون الواجهة', 'Choose interface color');
  String get accentColorSheetSubtitle => _t(
    'يغيّر لون الأزرار والعناصر النشطة فقط، ولا يغيّر ألوان الخطورة.',
    'Changes button and active element colors only, not risk level colors.',
  );
  String get accentColorCurrentLabel => _t('محدد حاليًا', 'Currently selected');
  String get accentColorApplyLabel => _t(
    'تطبيق هذا اللون على الأزرار والعناصر النشطة',
    'Apply this color to buttons and active elements',
  );
  String get accentColorCurrent => _t('الحالي', 'Current');
  String get accentColorChanged =>
      _t('تم تغيير لون الواجهة', 'Interface color changed');
  String get doneLabel => _t('تم', 'Done');
  String get settingsPageTitle => _t('الإعدادات', 'Settings');
  String get settingsPageSubtitle => _t(
    'تحكم بالمظهر، الخصوصية، الحفظ، ومراقبة الإشعارات.',
    'Manage appearance, privacy, storage, and notification monitoring.',
  );
  String get saveHistorySection =>
      _t('حفظ السجل محليًا', 'Save history locally');
  String get openPermissionSettings =>
      _t('فتح إعدادات الصلاحية', 'Open permission settings');
  String get openPermissionSettingsSnack =>
      _t('تم فتح إعداد الصلاحية', 'Permission settings opened');
  String monitoredAppsCountSubtitle(int count) =>
      '$count ${_t('تطبيقات محددة', 'apps selected')}';
  String get analysisLinksSectionTitle => _t('تحليل الروابط', 'Link analysis');
  String get analysisSmsTitle => _t('تحليل الرسائل SMS', 'SMS analysis');
  String get analysisEmailTitle => _t('تحليل البريد Email', 'Email analysis');
  String get alwaysEnabledLabel => _t('مفعّل دائمًا', 'Always enabled');

  // Result details screen — static UI labels
  String get messageCopied => _t('تم نسخ النص.', 'Message text copied.');
  String get urlPresent => _t('موجود', 'Present');
  String get urlAbsent => _t('غير موجود', 'Not present');
  String get mainClassificationReason =>
      _t('السبب الرئيسي للتصنيف', 'Main classification reason');
  String get originalMessage => _t('الرسالة الأصلية', 'Original message');
  String get copyMessageText => _t('نسخ النص', 'Copy text');
  String get detectedLink => _t('الرابط المكتشف', 'Detected link');
  String get copyLink => _t('نسخ الرابط', 'Copy link');
  String get analysisInfo => _t('معلومات التحليل', 'Analysis info');
  String get messageType => _t('نوع الرسالة', 'Message type');
  String get virusTotalScan => _t('فحص VirusTotal', 'VirusTotal scan');
  String get feedbackQuestion =>
      _t('هل تعتقد أن النتيجة غير صحيحة؟', 'Think the result is incorrect?');
  String get feedbackSubtitle => _t(
    'أرسل ملاحظة قصيرة لتحسين APG في النسخ القادمة.',
    'Send a short note to help improve APG in future versions.',
  );
  String get sendFeedback => _t('إرسال ملاحظة', 'Send feedback');
  String get layerBreakdownSubtitle => _t(
    'يوضح هذا القسم كيف جمع APG المؤشرات لتكوين النتيجة.',
    'This section explains how APG combined signals into the result.',
  );
  String get entityConflictWarning => _t(
    'يوجد تعارض بين الجهة المذكورة وهوية المرسل أو الرابط.',
    'There is a conflict between the mentioned entity and the sender or link.',
  );
  String get unknownLabel => _t('تعذر التحقق', 'Unknown');
  String get unspecifiedLabel => _t('غير محددة', 'Unspecified');
  String get manualChannel => _t('يدوي', 'Manual');
  String get possibleImpersonation =>
      _t('انتحال محتمل', 'Possible impersonation');
  String get highRiskTitle =>
      _t('تحذير: خطر تصيد مرتفع', 'Warning: High phishing risk');
  String get safeResultTitle =>
      _t('الرسالة تبدو مطمئنة', 'The message looks safe');
  String get suspiciousResultTitle =>
      _t('رسالة تحتاج تحققًا', 'Message needs verification');
  String get highRiskDesc => _t(
    'توجد مؤشرات قوية على تصيد أو انتحال.',
    'Strong indicators of phishing or impersonation were detected.',
  );
  String get safeResultDesc => _t(
    'لم تظهر مؤشرات خطورة واضحة.',
    'No clear risk indicators were detected.',
  );
  String get suspiciousResultDesc => _t(
    'توجد مؤشرات تستحق التحقق قبل المتابعة.',
    'Indicators found that are worth verifying before proceeding.',
  );
  String get deleteFromHistoryContent => _t(
    'سيتم حذف النتيجة محليًا من سجل APG.',
    'The result will be removed from the local APG history.',
  );
  String get accentColorSubtitle => _t(
    'اختر لون الأزرار والعناصر النشطة.',
    'Choose the color used for buttons and active elements.',
  );
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) {
    return <String>['ar', 'en'].contains(locale.languageCode.toLowerCase());
  }

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(AppLocalizations(locale));
  }

  @override
  bool shouldReload(covariant LocalizationsDelegate<AppLocalizations> old) {
    return false;
  }
}
