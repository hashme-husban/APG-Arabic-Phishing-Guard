import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In ar, this message translates to:
  /// **'Arabic Phishing Guard'**
  String get appTitle;

  /// No description provided for @home.
  ///
  /// In ar, this message translates to:
  /// **'الرئيسية'**
  String get home;

  /// No description provided for @analyze.
  ///
  /// In ar, this message translates to:
  /// **'تحليل'**
  String get analyze;

  /// No description provided for @notifications.
  ///
  /// In ar, this message translates to:
  /// **'الإشعارات'**
  String get notifications;

  /// No description provided for @history.
  ///
  /// In ar, this message translates to:
  /// **'السجل'**
  String get history;

  /// No description provided for @settings.
  ///
  /// In ar, this message translates to:
  /// **'الإعدادات'**
  String get settings;

  /// No description provided for @themeDark.
  ///
  /// In ar, this message translates to:
  /// **'الوضع الداكن'**
  String get themeDark;

  /// No description provided for @saveHistory.
  ///
  /// In ar, this message translates to:
  /// **'حفظ السجل محليًا'**
  String get saveHistory;

  /// No description provided for @autoAnalyzeNotifications.
  ///
  /// In ar, this message translates to:
  /// **'التحليل التلقائي للإشعارات'**
  String get autoAnalyzeNotifications;

  /// No description provided for @language.
  ///
  /// In ar, this message translates to:
  /// **'اللغة'**
  String get language;

  /// No description provided for @arabic.
  ///
  /// In ar, this message translates to:
  /// **'العربية'**
  String get arabic;

  /// No description provided for @english.
  ///
  /// In ar, this message translates to:
  /// **'الإنجليزية'**
  String get english;

  /// No description provided for @quickScan.
  ///
  /// In ar, this message translates to:
  /// **'تحليل سريع'**
  String get quickScan;

  /// No description provided for @fullAnalysis.
  ///
  /// In ar, this message translates to:
  /// **'تحليل كامل'**
  String get fullAnalysis;

  /// No description provided for @securityDashboard.
  ///
  /// In ar, this message translates to:
  /// **'لوحة الأمان'**
  String get securityDashboard;

  /// No description provided for @securityDashboardSubtitle.
  ///
  /// In ar, this message translates to:
  /// **'نظرة سريعة على نشاط التحليل والتنبيهات وحالة الحماية.'**
  String get securityDashboardSubtitle;

  /// No description provided for @analyzeMessages.
  ///
  /// In ar, this message translates to:
  /// **'تحليل الرسائل'**
  String get analyzeMessages;

  /// No description provided for @notificationsInbox.
  ///
  /// In ar, this message translates to:
  /// **'صندوق الإشعارات'**
  String get notificationsInbox;

  /// No description provided for @historyTitle.
  ///
  /// In ar, this message translates to:
  /// **'السجل'**
  String get historyTitle;

  /// No description provided for @settingsTitle.
  ///
  /// In ar, this message translates to:
  /// **'الإعدادات'**
  String get settingsTitle;

  /// No description provided for @senderOptional.
  ///
  /// In ar, this message translates to:
  /// **'المرسل (اختياري)'**
  String get senderOptional;

  /// No description provided for @messageText.
  ///
  /// In ar, this message translates to:
  /// **'نص الرسالة'**
  String get messageText;

  /// No description provided for @pasteText.
  ///
  /// In ar, this message translates to:
  /// **'لصق النص'**
  String get pasteText;

  /// No description provided for @urlOptional.
  ///
  /// In ar, this message translates to:
  /// **'الرابط (اختياري)'**
  String get urlOptional;

  /// No description provided for @pasteUrl.
  ///
  /// In ar, this message translates to:
  /// **'لصق الرابط'**
  String get pasteUrl;

  /// No description provided for @analyzeMessage.
  ///
  /// In ar, this message translates to:
  /// **'تحليل الرسالة'**
  String get analyzeMessage;

  /// No description provided for @analyzing.
  ///
  /// In ar, this message translates to:
  /// **'جاري التحليل...'**
  String get analyzing;

  /// No description provided for @clear.
  ///
  /// In ar, this message translates to:
  /// **'مسح'**
  String get clear;

  /// No description provided for @startAnalysis.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ التحليل'**
  String get startAnalysis;

  /// No description provided for @latestResult.
  ///
  /// In ar, this message translates to:
  /// **'آخر نتيجة'**
  String get latestResult;

  /// No description provided for @openDetails.
  ///
  /// In ar, this message translates to:
  /// **'عرض التفاصيل'**
  String get openDetails;

  /// No description provided for @copy.
  ///
  /// In ar, this message translates to:
  /// **'نسخ'**
  String get copy;

  /// No description provided for @share.
  ///
  /// In ar, this message translates to:
  /// **'مشاركة'**
  String get share;

  /// No description provided for @finalRecommendation.
  ///
  /// In ar, this message translates to:
  /// **'التوصية النهائية'**
  String get finalRecommendation;

  /// No description provided for @reasons.
  ///
  /// In ar, this message translates to:
  /// **'لماذا ظهرت هذه النتيجة؟'**
  String get reasons;

  /// No description provided for @recommendedActions.
  ///
  /// In ar, this message translates to:
  /// **'ماذا أفعل الآن؟'**
  String get recommendedActions;

  /// No description provided for @layerBreakdown.
  ///
  /// In ar, this message translates to:
  /// **'منهجية التقييم'**
  String get layerBreakdown;

  /// No description provided for @noResultsYet.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد تحليل محفوظ بعد.'**
  String get noResultsYet;

  /// No description provided for @clipboardEmpty.
  ///
  /// In ar, this message translates to:
  /// **'الحافظة فارغة.'**
  String get clipboardEmpty;

  /// No description provided for @textPasted.
  ///
  /// In ar, this message translates to:
  /// **'تم لصق النص.'**
  String get textPasted;

  /// No description provided for @urlPasted.
  ///
  /// In ar, this message translates to:
  /// **'تم لصق الرابط.'**
  String get urlPasted;

  /// No description provided for @fieldsCleared.
  ///
  /// In ar, this message translates to:
  /// **'تم مسح الحقول.'**
  String get fieldsCleared;

  /// No description provided for @resultCopied.
  ///
  /// In ar, this message translates to:
  /// **'تم نسخ النتيجة.'**
  String get resultCopied;

  /// No description provided for @detailsCopied.
  ///
  /// In ar, this message translates to:
  /// **'تم نسخ التفاصيل.'**
  String get detailsCopied;

  /// No description provided for @shareOpened.
  ///
  /// In ar, this message translates to:
  /// **'تم فتح نافذة المشاركة.'**
  String get shareOpened;

  /// No description provided for @enterMessageOrUrl.
  ///
  /// In ar, this message translates to:
  /// **'اكتب نص الرسالة أو الرابط على الأقل.'**
  String get enterMessageOrUrl;

  /// No description provided for @onboardingTitle1.
  ///
  /// In ar, this message translates to:
  /// **'مرحبًا بك في Arabic Phishing Guard'**
  String get onboardingTitle1;

  /// No description provided for @onboardingDesc1.
  ///
  /// In ar, this message translates to:
  /// **'حلّل الرسائل المشبوهة وافهم القرار النهائي بشكل واضح.'**
  String get onboardingDesc1;

  /// No description provided for @onboardingTitle2.
  ///
  /// In ar, this message translates to:
  /// **'تحليل سريع وتحليل كامل'**
  String get onboardingTitle2;

  /// No description provided for @onboardingDesc2.
  ///
  /// In ar, this message translates to:
  /// **'استخدم التحليل السريع للسرعة، أو الشاشة الكاملة للمراجعة التفصيلية.'**
  String get onboardingDesc2;

  /// No description provided for @onboardingTitle3.
  ///
  /// In ar, this message translates to:
  /// **'صندوق الإشعارات'**
  String get onboardingTitle3;

  /// No description provided for @onboardingDesc3.
  ///
  /// In ar, this message translates to:
  /// **'التقط إشعارات أندرويد وراجعها من مكان واحد.'**
  String get onboardingDesc3;

  /// No description provided for @next.
  ///
  /// In ar, this message translates to:
  /// **'التالي'**
  String get next;

  /// No description provided for @skip.
  ///
  /// In ar, this message translates to:
  /// **'تخطي'**
  String get skip;

  /// No description provided for @startNow.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ الآن'**
  String get startNow;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
