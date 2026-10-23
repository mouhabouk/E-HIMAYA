// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitle => 'ء-حماية';

  @override
  String get actionContinue => 'مواصلة';

  @override
  String get actionCancel => 'إلغاء';

  @override
  String get actionSave => 'حفظ';

  @override
  String get actionLater => 'لاحقا';

  @override
  String get actionRetry => 'إعادة المحاولة';

  @override
  String get copied => 'تم نسخ رمز المتابعة.';

  @override
  String get copyTrackingCode => 'نسخ رمز المتابعة';

  @override
  String callNumber(String number) {
    return 'الاتصال بـ $number';
  }

  @override
  String get charterTitle => 'شروط الاستخدام';

  @override
  String charterVersionLabel(String version) {
    return 'الإصدار $version';
  }

  @override
  String get charterIntro =>
      'ء-حماية هي المنصة الوطنية للتبليغ عن حالات الطوارئ لدى الحماية المدنية. قبل استعمالها، يُرجى الاطلاع على كيفية معالجة معطياتك وعلى التزاماتك.';

  @override
  String get charterCheckbox =>
      'اطّلعت على شروط الاستخدام وأوافق عليها، وأدرك أن البلاغ الكاذب عن قصد يُرتّب مسؤوليتي القانونية.';

  @override
  String charterAcceptedOn(String date) {
    return 'تمت الموافقة بتاريخ $date';
  }

  @override
  String get roleTitle => 'من أنت؟';

  @override
  String get roleCitizen => 'مواطن';

  @override
  String get roleCitizenDesc =>
      'التبليغ عن حالة طارئة وإرسال نداء استغاثة ومتابعة بلاغاتك.';

  @override
  String get roleInstitution => 'مؤسسة';

  @override
  String get roleInstitutionDesc => 'مؤسسة عمومية أو خاصة لها حساب مسجّل.';

  @override
  String get institutionTitle => 'المؤسسات';

  @override
  String get institutionBody =>
      'التسجيل وجوبي بالنسبة إلى المؤسسات ويتم عبر بوابة المؤسسات وليس عبر هذا التطبيق. إن كان لمؤسستك حساب، يمكنك الدخول أسفله.';

  @override
  String get institutionLogin => 'الدخول';

  @override
  String get citizenModeTitle => 'كيف تريد التبليغ؟';

  @override
  String get citizenAnonymous => 'المواصلة دون حساب';

  @override
  String get citizenAnonymousDesc => 'الأسرع. لا تُطلب أي معطيات شخصية.';

  @override
  String get citizenRegister => 'إنشاء حساب';

  @override
  String get citizenRegisterDesc =>
      'تابع بلاغاتك من أي جهاز، وتحظى بلاغاتك بمصداقية أكبر.';

  @override
  String get citizenLogin => 'لديّ حساب';

  @override
  String get citizenLoginDesc => 'ادخل بحسابك في ء-حماية.';

  @override
  String get changeRole => 'تغيير الصفة';

  @override
  String get loginCancelled => 'تم إلغاء الدخول.';

  @override
  String get loginFailed => 'تعذّر الدخول. تثبّت من الاتصال وأعد المحاولة.';

  @override
  String get profileTitle => 'استكمال ملفك الشخصي';

  @override
  String get profileIntro =>
      'ستُستعمل هذه المعطيات للتثبت من بلاغاتك. يمكنك استكمالها لاحقا من الإعدادات.';

  @override
  String get profileFirstName => 'الاسم';

  @override
  String get profileLastName => 'اللقب';

  @override
  String get profileCin => 'رقم بطاقة التعريف الوطنية';

  @override
  String get profileCinHint => '8 أرقام';

  @override
  String profileCinStored(String last4) {
    return 'رقم البطاقة المسجّل ينتهي بـ $last4؛ أعد إدخاله لحفظ التغييرات.';
  }

  @override
  String get profilePhone => 'رقم الهاتف';

  @override
  String get profileGouvernorat => 'الولاية';

  @override
  String get profileDelegation => 'المعتمدية';

  @override
  String get profileAddress => 'العنوان (اختياري)';

  @override
  String get profileSaved => 'تم حفظ الملف الشخصي.';

  @override
  String get validationRequired => 'حقل وجوبي.';

  @override
  String get validationCin => 'يتكوّن رقم بطاقة التعريف من 8 أرقام بالضبط.';

  @override
  String get validationPhone => 'أدخل الأرقام الثمانية بعد ‎+216.';

  @override
  String get geoLoadFailed => 'تعذّر تحميل القائمة.';

  @override
  String get navHome => 'الرئيسية';

  @override
  String get navReports => 'بلاغاتي';

  @override
  String get navSettings => 'الإعدادات';

  @override
  String get homeTagline => 'في حالات الطوارئ، كل ثانية مهمة.';

  @override
  String get homeNewReport => 'بلاغ جديد';

  @override
  String get homeNewReportDesc =>
      'حريق، فيضان، حادث... مع صور أو فيديو أو رسالة صوتية.';

  @override
  String get homeEmergencyDesc =>
      'اتصل مباشرة بالرقم 198 أو 190 أو 197 أو 193، حتى دون إنترنت.';

  @override
  String get homeTrackDesc => 'تابع بلاغا برمز المتابعة.';

  @override
  String pendingSyncBanner(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count بلاغا في انتظار الإرسال',
      few: '$count بلاغات في انتظار الإرسال',
      two: 'بلاغان في انتظار الإرسال',
      one: 'بلاغ واحد في انتظار الإرسال',
    );
    return '$_temp0';
  }

  @override
  String get sosButtonLabel => 'نجدة';

  @override
  String get sosHint => 'انقر مرتين أو اضغط مطوّلا لإرسال موقعك.';

  @override
  String get sosArmed => 'انقر مرة أخرى لإرسال نداء الاستغاثة.';

  @override
  String get sosSending => 'جارٍ إرسال نداء الاستغاثة...';

  @override
  String get sosConfirmTitle => 'إرسال نداء استغاثة؟';

  @override
  String get sosConfirmBody => 'سيُرسل موقعك الحالي إلى الحماية المدنية.';

  @override
  String get sosConfirmAction => 'إرسال نداء الاستغاثة';

  @override
  String get sosNoLocation =>
      'موقعك غير متوفر. فعّل خدمة تحديد الموقع أو اتصل بالحماية المدنية.';

  @override
  String get sosQueuedTitle => 'تم تسجيل نداء الاستغاثة';

  @override
  String get anonBlockedBody =>
      'التبليغ دون حساب معلّق على هذا الجهاز. أنشئ حسابا لمواصلة التبليغ.';

  @override
  String get emergencyTitle => 'أرقام الطوارئ';

  @override
  String get emergencyIntro =>
      'تمرّ المكالمات مباشرة عبر شريحة هاتفك، حتى دون إنترنت.';

  @override
  String get emergencyCivilProtection => 'الحماية المدنية';

  @override
  String get emergencySamu => 'الإسعاف الطبي الاستعجالي';

  @override
  String get emergencyPolice => 'شرطة النجدة';

  @override
  String get emergencyNationalGuard => 'الحرس الوطني';

  @override
  String emergencyCallSemantics(String name, String number) {
    return 'الاتصال بـ$name، $number';
  }

  @override
  String get dialFailed => 'لا يمكن لهذا الجهاز إجراء مكالمات.';

  @override
  String get categorySos => 'نداء استغاثة';

  @override
  String get categoryFire => 'حريق';

  @override
  String get categoryFlood => 'فيضان';

  @override
  String get categoryTrafficAccident => 'حادث مرور';

  @override
  String get categoryDrowning => 'غرق';

  @override
  String get categoryLandslide => 'انزلاق أرضي';

  @override
  String get categoryChemicalLeak => 'تسرّب مواد كيميائية';

  @override
  String get categoryMedical => 'حالة صحية طارئة';

  @override
  String get categoryOther => 'أخرى';

  @override
  String get statusReceived => 'مستلم';

  @override
  String get statusInProgress => 'قيد المعالجة';

  @override
  String get statusIntervened => 'تم التدخل';

  @override
  String get statusOngoing => 'التدخل متواصل';

  @override
  String get statusClosed => 'أُغلق التدخل';

  @override
  String get statusRejected => 'مرفوض';

  @override
  String get statusUnknown => 'حالة غير معروفة';

  @override
  String get newReportTitle => 'بلاغ جديد';

  @override
  String get chooseCategory => 'ماذا يحدث؟';

  @override
  String get reportLocation => 'الموقع';

  @override
  String get locationLocating => 'جارٍ تحديد الموقع...';

  @override
  String locationAccuracy(int meters) {
    return 'تم تحديد الموقع، الدقة ±$meters م';
  }

  @override
  String get locationManual => 'موقع محدّد على الخريطة';

  @override
  String get locationAdjustHint =>
      'حرّك الخريطة لوضع الدبوس على مكان الحادثة بدقة.';

  @override
  String get locationUnavailable =>
      'لا يتوفر موقع GPS بعد. ضع الدبوس على الخريطة أو أعد المحاولة.';

  @override
  String get locationPermissionDenied =>
      'خدمة الموقع معطّلة أو غير مسموح بها. ضع الدبوس على الخريطة.';

  @override
  String get locationOutsideTunisia => 'يجب أن يكون الموقع داخل تونس.';

  @override
  String get locationRefresh => 'استعمال موقعي';

  @override
  String get mapPinSemantics => 'دبوس موقع البلاغ';

  @override
  String get reportDescription => 'الوصف (اختياري)';

  @override
  String get reportDescriptionHint => 'ماذا ترى؟ هل هناك مصابون؟';

  @override
  String get reportAttachments => 'صور وفيديو ورسالة صوتية';

  @override
  String get attachTakePhoto => 'التقاط صورة';

  @override
  String get attachPickPhoto => 'معرض الصور';

  @override
  String get attachRecordVideo => 'تصوير فيديو';

  @override
  String get attachPickVideo => 'اختيار فيديو';

  @override
  String attachmentPhoto(int n) {
    return 'صورة $n';
  }

  @override
  String attachmentVideo(int n) {
    return 'فيديو $n';
  }

  @override
  String attachmentTooLarge(int maxMb) {
    return 'هذا الملف كبير جدا (الحد الأقصى $maxMb م.ب).';
  }

  @override
  String get attachmentUnsupported => 'صيغة هذا الملف غير مقبولة.';

  @override
  String attachmentLimit(int max) {
    return 'لا يتجاوز عدد الملفات $max في البلاغ الواحد.';
  }

  @override
  String get removeAttachment => 'حذف المرفق';

  @override
  String get pickerFailed => 'تعذّر فتح الكاميرا أو معرض الصور.';

  @override
  String get audioTitle => 'رسالة صوتية';

  @override
  String get audioMaxDuration => '5 دقائق كحد أقصى';

  @override
  String get audioRecord => 'تسجيل';

  @override
  String get audioStop => 'إيقاف';

  @override
  String get audioPlay => 'الاستماع إلى التسجيل';

  @override
  String get audioPause => 'إيقاف مؤقت';

  @override
  String get audioReRecord => 'إعادة التسجيل';

  @override
  String get audioDelete => 'حذف التسجيل';

  @override
  String audioRecording(String duration) {
    return 'جارٍ التسجيل... $duration';
  }

  @override
  String get audioPermissionDenied => 'تم رفض النفاذ إلى الميكروفون.';

  @override
  String get audioFailed => 'تعذّر بدء التسجيل.';

  @override
  String get reportSubmit => 'إرسال البلاغ';

  @override
  String get reportNeedsLocation =>
      'انتظر تحديد موقعك أو ضع الدبوس على الخريطة.';

  @override
  String get reportOfflineNote =>
      'في غياب الشبكة، يُحفظ البلاغ مشفّرا على الهاتف ويُرسل آليا لاحقا.';

  @override
  String get reportSaveFailed => 'تعذّر حفظ البلاغ. أعد المحاولة.';

  @override
  String get reportQueuedTitle => 'تم تسجيل البلاغ';

  @override
  String get reportTempCodeLabel => 'رمز مؤقت';

  @override
  String get reportQueuedBody =>
      'احتفظ بهذا الرمز. سيُعوّض برمز المتابعة النهائي حال تلقي الحماية المدنية لبلاغك.';

  @override
  String get reportReceivedBody =>
      'تلقّت الحماية المدنية بلاغك. استعمل هذا الرمز لمتابعته.';

  @override
  String get reportBackHome => 'العودة إلى الرئيسية';

  @override
  String get temporaryCodeNote => 'رمز مؤقت، في انتظار الإرسال';

  @override
  String get myReportsTitle => 'بلاغاتي';

  @override
  String get myReportsEmpty => 'لا توجد بلاغات بعد.';

  @override
  String get myReportsOffline => 'تعذّر التحديث من الخادم.';

  @override
  String get reportPendingSync => 'في انتظار الإرسال';

  @override
  String get reportConflict => 'تم اعتماد نسخة الخادم';

  @override
  String get reportFailed => 'غير مقبول';

  @override
  String get reportBlocked => 'يتطلب حسابا';

  @override
  String reportUploadingMedia(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count مرفقا قيد الإرسال',
      few: '$count مرفقات قيد الإرسال',
      two: 'مرفقان قيد الإرسال',
      one: 'مرفق واحد قيد الإرسال',
    );
    return '$_temp0';
  }

  @override
  String reportMediaRejected(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count مرفقا مرفوضا',
      few: '$count مرفقات مرفوضة',
      two: 'مرفقان مرفوضان',
      one: 'مرفق واحد مرفوض',
    );
    return '$_temp0';
  }

  @override
  String get trackTitle => 'متابعة بلاغ';

  @override
  String get trackingCodeLabel => 'رمز المتابعة';

  @override
  String get trackHint => 'EH-26-61-0004821';

  @override
  String get trackAction => 'متابعة';

  @override
  String get trackInvalid => 'أدخل رمزا مثل EH-26-61-0004821.';

  @override
  String get trackHistory => 'السجل';

  @override
  String receivedAt(String date) {
    return 'استُلم بتاريخ $date';
  }

  @override
  String get settingsTitle => 'الإعدادات';

  @override
  String get settingsLanguage => 'اللغة';

  @override
  String get languageArabic => 'العربية';

  @override
  String get languageFrench => 'Français';

  @override
  String get languageEnglish => 'English';

  @override
  String get settingsTheme => 'المظهر';

  @override
  String get themeSystem => 'حسب إعدادات الهاتف';

  @override
  String get themeLight => 'فاتح';

  @override
  String get themeDark => 'داكن';

  @override
  String get settingsIdentity => 'الهوية';

  @override
  String get identityAnonymous => 'دون حساب (هذا الجهاز)';

  @override
  String get identityRegistered => 'متصل بحسابك';

  @override
  String identityRegisteredAs(String name) {
    return 'متصل باسم $name';
  }

  @override
  String get identityNone => 'غير متصل';

  @override
  String get settingsRegister => 'إنشاء حساب';

  @override
  String get settingsProfile => 'ملفي الشخصي';

  @override
  String get settingsLogout => 'الخروج';

  @override
  String get logoutConfirmTitle => 'الخروج من الحساب؟';

  @override
  String get logoutConfirmBody =>
      'تبقى البلاغات غير المرسلة على هذا الهاتف وتُرسل بعد الدخول مجددا أو عند اختيار المواصلة دون حساب.';

  @override
  String get settingsCharter => 'شروط الاستخدام';

  @override
  String get errorAuthenticationRequired =>
      'انتهت صلاحية جلستك. يُرجى الدخول مجددا.';

  @override
  String get errorInvalidDeviceKey =>
      'تعذّر التعرف على هذا الجهاز. أعد تشغيل التطبيق.';

  @override
  String get errorAnonBlocked =>
      'التبليغ دون حساب معلّق على هذا الجهاز. يُرجى إنشاء حساب.';

  @override
  String get errorAccountSuspended => 'حسابك معلّق.';

  @override
  String get errorConsentRequired =>
      'يرجى الموافقة على شروط الاستخدام قبل التبليغ.';

  @override
  String get errorRateLimited => 'طلبات كثيرة جدا. يُرجى الانتظار قليلا.';

  @override
  String get errorUnknownCharterVersion =>
      'تغيّرت شروط الاستخدام. يرجى قراءتها من جديد.';

  @override
  String get errorClientUuidConflict =>
      'هذا البلاغ يتعارض مع بلاغ آخر على الخادم.';

  @override
  String get errorNotFound => 'غير موجود. تثبّت من الرمز.';

  @override
  String get errorValidation => 'بعض المعطيات غير صحيحة.';

  @override
  String get errorNetwork => 'لا يوجد اتصال بالخادم. ستُعاد المحاولة آليا.';

  @override
  String get errorServer => 'الخدمة غير متوفرة مؤقتا.';

  @override
  String get errorUnknown => 'حدث خطأ.';

  @override
  String get errorMediaRefused => 'تم رفض المرفق.';

  @override
  String get errorMediaTooLarge => 'المرفق كبير جدا.';

  @override
  String get errorUnsupportedMediaType => 'صيغة المرفق غير مقبولة.';

  @override
  String get errorTooManyMedia => 'بلغ هذا البلاغ العدد الأقصى من المرفقات.';

  @override
  String get errorUploadWindowClosed =>
      'لا يمكن إضافة المرفقات إلا خلال 24 ساعة من البلاغ.';

  @override
  String get errorMediaRejected => 'تلف المرفق أثناء الإرسال فتم رفضه.';

  @override
  String get errorOrgNotFound => 'المؤسسة غير موجودة أو لم تعد عضوا فيها.';

  @override
  String get errorOrgNotActive =>
      'هذه المؤسسة غير نشطة (قيد المراجعة أو مرفوضة أو معلّقة): لا يمكنها التبليغ.';

  @override
  String get errorOrgRoleRequired =>
      'دورك في هذه المؤسسة لا يسمح بهذا الإجراء.';

  @override
  String get reportAsTitle => 'التبليغ بصفة';

  @override
  String get reportAsSelf => 'بصفتي الشخصية';

  @override
  String get reportAsInstitutionUnnamed => 'مؤسسة';

  @override
  String get reportOrgRefused => 'مرفوض باسم المؤسسة';

  @override
  String get reportOrgNotFoundBody =>
      'تعذّر إرسال هذا البلاغ باسم المؤسسة: المؤسسة غير موجودة أو لم تعد عضوا فيها. البلاغ محفوظ في هذا الهاتف ويمكنك إرساله بصفتك الشخصية.';

  @override
  String get reportOrgNotActiveBody =>
      'تعذّر إرسال هذا البلاغ باسم المؤسسة لأنها غير نشطة. البلاغ محفوظ في هذا الهاتف ويمكنك إرساله بصفتك الشخصية.';

  @override
  String get reportResendAsSelf => 'الإرسال بصفتي الشخصية';

  @override
  String get reportResentAsSelf => 'سيُرسل البلاغ بصفتك الشخصية.';

  @override
  String get settingsSosReportAs => 'نداء النجدة';

  @override
  String get settingsSosReportAsHint => 'زر النجدة يرسل النداء بصفة:';

  @override
  String get myInstitutionTitle => 'مؤسستي';

  @override
  String get myInstitutionsTitle => 'مؤسساتي';

  @override
  String get myInstitutionsEmpty => 'لست عضوا في أي مؤسسة.';

  @override
  String get homeInstitutionDesc => 'بطاقة السلامة والفريق وبلاغات مؤسستك';

  @override
  String get orgKindIndustrial => 'صناعية';

  @override
  String get orgKindEducational => 'تعليمية';

  @override
  String get orgKindHotel => 'نزل';

  @override
  String get orgKindGovernment => 'حكومية';

  @override
  String get orgKindPrivate => 'خاصة';

  @override
  String get orgKindOther => 'أخرى';

  @override
  String get orgStatusPendingReview => 'قيد المراجعة';

  @override
  String get orgStatusActive => 'نشطة';

  @override
  String get orgStatusRejected => 'مرفوضة';

  @override
  String get orgStatusSuspended => 'معلّقة';

  @override
  String get orgFamilyHighRise => 'بناية شاهقة';

  @override
  String get orgFamilyIndustrial => 'منشأة صناعية';

  @override
  String get orgFamilyErp => 'مؤسسة مفتوحة للعموم';

  @override
  String get orgFamilyWorkplace => 'مكان عمل';

  @override
  String orgErpCategory(int category) {
    return 'الصنف $category';
  }

  @override
  String get orgTeamRepresentative => 'الممثل';

  @override
  String get orgTeamMember => 'عضو';

  @override
  String get trainingValid => 'سارٍ';

  @override
  String get trainingExpiring => 'ينتهي قريبا';

  @override
  String get trainingExpired => 'منتهٍ';

  @override
  String get trainingUnknown => 'غير معروف';

  @override
  String orgTraining(String status) {
    return 'التكوين: $status';
  }

  @override
  String get orgCapacity => 'الطاقة الاستيعابية (أقصى عدد من الأشخاص)';

  @override
  String get orgAddress => 'العنوان';

  @override
  String get orgClassification => 'التصنيف';

  @override
  String get orgClassificationProvisional =>
      'تصنيف مؤقت: محسوب بعتبات لم تصادق عليها الحماية المدنية بعد.';

  @override
  String get orgAlerts => 'التنبيهات';

  @override
  String orgAlertsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count تنبيها',
      few: '$count تنبيهات',
      two: 'تنبيهان',
      one: 'تنبيه واحد',
    );
    return '$_temp0';
  }

  @override
  String get orgNoAlerts => 'لا توجد تنبيهات';

  @override
  String get orgSafetyTeam => 'فريق السلامة';

  @override
  String get orgTeamEmpty => 'لم يُسجَّل فريق سلامة.';

  @override
  String orgCallMember(String name) {
    return 'الاتصال بـ$name';
  }

  @override
  String orgHazmatTitle(int count) {
    return 'المواد الخطرة ($count)';
  }

  @override
  String get orgHazmatEmpty => 'لا توجد مواد خطرة مسجّلة.';

  @override
  String orgUnNumber(String number) {
    return 'UN $number';
  }

  @override
  String orgOfflineCopy(String date) {
    return 'دون اتصال: نسخة محفوظة بتاريخ $date.';
  }

  @override
  String get orgPortalNote =>
      'التعديل المفصّل لبيانات المؤسسة (البطاقة، الفريق، المواد الخطرة، الوثائق، الشهادة) يتم عبر بوابة المؤسسات.';

  @override
  String get orgOpenPortal => 'فتح البوابة';

  @override
  String get orgPortalUnavailable => 'تعذّر فتح البوابة على هذا الهاتف.';

  @override
  String get orgRecentReports => 'آخر بلاغات المؤسسة';

  @override
  String get orgReportsEmpty => 'لا توجد بلاغات بعد.';

  @override
  String orgReportBy(String name) {
    return 'من $name';
  }

  @override
  String get notificationsTitle => 'الإشعارات';

  @override
  String get activeAlertsTitle => 'التنبيهات السارية';

  @override
  String get activeAlertsNone => 'لا يوجد تنبيه سارٍ في منطقتك.';

  @override
  String get inboxTitle => 'الرسائل';

  @override
  String get inboxEmpty => 'لا توجد رسائل بعد.';

  @override
  String get inboxNoIdentity => 'اختر طريقة استعمال التطبيق لتلقي الرسائل.';

  @override
  String get inboxLoadMore => 'عرض الرسائل الأقدم';

  @override
  String get inboxAlertActive => 'تنبيه سارٍ';

  @override
  String get inboxAlertEnded => 'تنبيه منتهٍ';

  @override
  String get alertTitle => 'تنبيه';

  @override
  String get alertOpen => 'فتح التنبيه';

  @override
  String alertUntil(String time) {
    return 'إلى غاية $time';
  }

  @override
  String alertPublishedAt(String time) {
    return 'صدر في $time';
  }

  @override
  String get alertNotActive => 'انتهى هذا التنبيه أو تم رفعه.';

  @override
  String get alertAreaNational => 'كامل البلاد';

  @override
  String get alertAreaZone => 'منطقة محددة على الخريطة';

  @override
  String alertAreaGouvernorats(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ولاية',
      few: '$count ولايات',
      two: 'ولايتان',
      one: 'ولاية واحدة',
    );
    return '$_temp0';
  }

  @override
  String get severityHigh => 'إنذار أحمر';

  @override
  String get severityMedium => 'إنذار برتقالي';

  @override
  String get severityLow => 'إنذار أصفر';

  @override
  String get hazardHeavyRain => 'أمطار غزيرة';

  @override
  String get hazardFlood => 'فيضان';

  @override
  String get hazardStorm => 'عاصفة';

  @override
  String get hazardWind => 'رياح قوية';

  @override
  String get hazardHeatWave => 'موجة حر';

  @override
  String get hazardColdWave => 'موجة برد';

  @override
  String get hazardSea => 'اضطراب البحر';

  @override
  String get hazardForestFire => 'حريق غابات';

  @override
  String get hazardChemical => 'خطر كيميائي';

  @override
  String get hazardOther => 'خطر آخر';

  @override
  String get topicActivity => 'نشاط';

  @override
  String get topicAwareness => 'توعية';

  @override
  String get topicTraining => 'تكوين';

  @override
  String get topicWorldDay => 'يوم عالمي';

  @override
  String get topicOther => 'معلومة';

  @override
  String get settingsAlerts => 'التنبيهات والإشعارات';

  @override
  String get settingsLocationAlerts => 'تنبيهات حيث أكون';

  @override
  String get settingsLocationAlertsHelp =>
      'يستعمل الموقع التقريبي للهاتف (حوالي 1 كم) لإرسال تنبيهات المنطقة التي توجد فيها.';

  @override
  String get channelAlerts => 'التنبيهات العاجلة';

  @override
  String get channelAlertsDesc => 'تنبيهات الحماية المدنية واستنفار المتطوعين.';

  @override
  String get channelGeneral => 'المعلومات';

  @override
  String get channelGeneralDesc => 'متابعة بلاغاتك والرسائل الإعلامية.';

  @override
  String get pushSimulationBadge => 'وضع المحاكاة';

  @override
  String get pushSimulationHelp =>
      'الإشعارات صادرة عن المحاكي المحلي وليس عن Firebase. لا يُسلَّم أي إشعار عبر خدمة دفع حقيقية.';

  @override
  String get tipsTitle => 'نصائح السلامة';

  @override
  String get tipsIntro => 'ما يجب فعله وما يجب تجنبه. متاحة دون اتصال.';

  @override
  String get tipsDo => 'ما يجب فعله';

  @override
  String get tipsDont => 'ما يجب تجنبه';

  @override
  String get tipEarthquake => 'زلزال';

  @override
  String get homeTipsDesc => 'التصرفات الصحيحة عند الطوارئ، حتى دون اتصال.';

  @override
  String get volunteerTitle => 'التطوع';

  @override
  String get homeVolunteerDesc =>
      'انضم إلى المتطوعين واستجب للاستنفار القريب منك.';

  @override
  String get volunteerIntro =>
      'يساعد المتطوعون فرق الحماية المدنية في حالات الطوارئ حسب اختصاصاتهم. تتم دراسة طلبك قبل أي استنفار.';

  @override
  String get volunteerApply => 'التسجيل كمتطوع';

  @override
  String get volunteerApplication => 'طلبي';

  @override
  String get volunteerStatusPending => 'قيد الدراسة';

  @override
  String get volunteerStatusApproved => 'مقبول';

  @override
  String get volunteerStatusRejected => 'مرفوض';

  @override
  String get volunteerStatusSuspended => 'موقوف';

  @override
  String get volunteerStatusWithdrawn => 'منسحب';

  @override
  String get volunteerPendingHelp =>
      'ستدرس الحماية المدنية طلبك وستتلقى القرار عبر البريد الإلكتروني.';

  @override
  String get volunteerApprovedHelp =>
      'يمكنك التصريح بجاهزيتك وتلقي الاستنفار القريب منك.';

  @override
  String get volunteerRejectedHelp =>
      'لم يُقبل طلبك. يمكنك تعديله وإعادة تقديمه.';

  @override
  String get volunteerSuspendedHelp => 'تطوعك موقوف: لن تتلقى أي استنفار.';

  @override
  String get volunteerWithdrawnHelp =>
      'لقد انسحبت. يمكنك التسجيل من جديد في أي وقت.';

  @override
  String volunteerReason(String reason) {
    return 'السبب: $reason';
  }

  @override
  String volunteerPeriodFrom(String from) {
    return 'ابتداءً من $from';
  }

  @override
  String volunteerPeriodRange(String from, String to) {
    return 'من $from إلى $to';
  }

  @override
  String get availabilityContinuous => 'مباشر';

  @override
  String get availabilityIntermittent => 'منقطع';

  @override
  String get volunteerEdit => 'تعديل طلبي';

  @override
  String get volunteerResubmit => 'إعادة التقديم';

  @override
  String get volunteerWithdraw => 'الانسحاب';

  @override
  String get volunteerWithdrawConfirm =>
      'لن تتلقى أي استنفار ولن تتم مشاركة موقعك بعد الآن.';

  @override
  String get volunteerReady => 'جاهز للتدخل';

  @override
  String get volunteerReadyHelp =>
      'طوال فترة جاهزيتك، ترى الحماية المدنية موقعك لاستنفارك.';

  @override
  String volunteerReadyUntil(String time) {
    return 'جاهز إلى غاية $time';
  }

  @override
  String get volunteerReadyFor => 'لمدة';

  @override
  String hoursShort(int hours) {
    return '$hours س';
  }

  @override
  String get volunteerLocationPrivacy =>
      'لا تتم مشاركة موقعك إلا خلال فترة الجاهزية، ويُحذف عند انتهائها ولا يُؤرشف أبدا.';

  @override
  String get locationConsentTitle =>
      'هل توافق على مشاركة موقعك خلال فترة الجاهزية؟';

  @override
  String get locationConsentBody =>
      'خلال فترة جاهزيتك، يُرسل موقعك إلى الحماية المدنية في ولايتك لتستنفر المتطوعين الأقرب إلى الحادث.\n\n• من يراه: أعوان الحماية المدنية، على خريطة مقرّبة إلى حوالي 100 متر، والمسافات مقرّبة أيضا.\n• إلى متى: خلال فترة الجاهزية فقط. يُحفظ في الذاكرة ويُحذف عند انتهائها ولا يُؤرشف أبدا.\n• يمكنك سحب هذه الموافقة في أي وقت من هذه الشاشة، وتنتهي الجاهزية فورا.';

  @override
  String get locationConsentAccept => 'أوافق';

  @override
  String get locationConsentSwitch => 'مشاركة موقعي خلال الجاهزية';

  @override
  String get locationConsentSwitchOn =>
      'الموافقة مسجّلة. سحبها يُنهي الجاهزية ويحذف موقعك.';

  @override
  String get locationConsentSwitchOff => 'ضرورية للتصريح بالجاهزية.';

  @override
  String get locationConsentWithdrawn => 'سُحبت الموافقة وحُذف موقعك.';

  @override
  String get volunteerNoFix => 'تعذر تحديد موقعك. أعد المحاولة في مكان مفتوح.';

  @override
  String get volunteerSkills => 'الاختصاصات';

  @override
  String get volunteerSkillsRequired => 'اختر اختصاصا واحدا على الأقل.';

  @override
  String get volunteerOtherSkill => 'اختصاص آخر';

  @override
  String get volunteerAvailability => 'نوع التوفر';

  @override
  String get volunteerPeriod => 'فترة التطوع';

  @override
  String get volunteerFrom => 'البداية';

  @override
  String get volunteerTo => 'النهاية';

  @override
  String get volunteerNoEnd => 'دون تاريخ نهاية';

  @override
  String get volunteerNotes => 'ملاحظات (اختياري)';

  @override
  String get volunteerProfileNote =>
      'يتم أخذ اسمك وهاتفك وولايتك من ملفك الشخصي.';

  @override
  String get volunteerSubmit => 'إرسال طلبي';

  @override
  String get volunteerSubmitted => 'تم إرسال الطلب.';

  @override
  String get fieldRequired => 'إجباري';

  @override
  String get skillFirstAid => 'الإسعافات الأولية';

  @override
  String get skillDiving => 'الغوص';

  @override
  String get skillHeavyVehicles => 'قيادة العربات الثقيلة';

  @override
  String get skillFirefighting => 'إطفاء الحرائق';

  @override
  String get skillSearchRescue => 'البحث والإنقاذ';

  @override
  String get skillLogistics => 'الإمداد والتموين';

  @override
  String get skillMedical => 'طبي';

  @override
  String get skillOther => 'أخرى';

  @override
  String get calloutsTitle => 'الاستنفار';

  @override
  String get calloutsDesc => 'طلبات المساعدة القريبة منك.';

  @override
  String get calloutsEmpty => 'لا يوجد استنفار حاليا.';

  @override
  String get calloutAccept => 'سأتوجه';

  @override
  String get calloutDecline => 'غير متاح';

  @override
  String get calloutArrived => 'وصلت إلى المكان';

  @override
  String get calloutEtaLabel => 'الوصول خلال (دقائق)';

  @override
  String calloutEta(int minutes) {
    return 'الوصول خلال $minutes د';
  }

  @override
  String calloutSkill(String skill) {
    return 'الاختصاص: $skill';
  }

  @override
  String calloutDistance(String distance) {
    return 'على بعد $distance';
  }

  @override
  String get calloutAnswerSent => 'في انتظار ردك';

  @override
  String get calloutAnswerAccepted => 'في الطريق';

  @override
  String get calloutAnswerDeclined => 'معتذر';

  @override
  String get calloutAnswerExpired => 'منتهي';

  @override
  String get calloutAnswerArrived => 'في المكان';

  @override
  String distanceMeters(int meters) {
    return '$meters م';
  }

  @override
  String distanceKm(String km) {
    return '$km كم';
  }

  @override
  String get errorRegistrationRequired => 'يلزمك حساب للتطوع.';

  @override
  String get errorNotVolunteer => 'لم تسجل كمتطوع.';

  @override
  String get errorProfileIncomplete =>
      'أكمل ملفك الشخصي أولا (الهاتف والولاية).';

  @override
  String get errorInvalidPeriod =>
      'الفترة غير صالحة (النهاية قبل البداية أو بعد أكثر من سنتين).';

  @override
  String get errorVolunteerNotApproved => 'طلب تطوعك غير مقبول.';

  @override
  String get errorOutsidePeriod => 'اليوم خارج فترة تطوعك.';

  @override
  String get errorNotReady => 'لم تعد في وضع الجاهزية.';

  @override
  String get errorLocationRequired => 'موقعك ضروري للتصريح بالجاهزية.';

  @override
  String get errorLocationConsentRequired =>
      'وافق على مشاركة موقعك قبل التصريح بالجاهزية.';

  @override
  String get errorCalloutClosed => 'تم إغلاق هذا الاستنفار.';

  @override
  String get errorEtaRequired => 'أدخل مدة بين 1 و600 دقيقة.';

  @override
  String get errorInvalidTransition => 'لم يعد هذا الإجراء ممكنا.';

  @override
  String get errorVersionConflict =>
      'تغيرت بياناتك في الأثناء. أعد التحميل وحاول مجددا.';

  @override
  String get locationServiceDisabled => 'خدمة الموقع معطلة على هذا الهاتف.';

  @override
  String get volunteerLocationDenied =>
      'اسمح بالوصول إلى الموقع للتصريح بجاهزيتك.';

  @override
  String get actionNotNow => 'ليس الآن';

  @override
  String get channelCritical => 'التنبيهات الرسمية الحرجة';

  @override
  String get channelCriticalDesc =>
      'أخطر تنبيهات الحماية المدنية، تُسمع حتى في وضع «عدم الإزعاج» (فقط إن سمحت بذلك).';

  @override
  String get alertCheckTitle => 'التحقق من وصول التنبيهات';

  @override
  String get alertCheckSubtitle => 'ما قد يمنع التنبيهات من الوصول إليك';

  @override
  String get alertCheckIntro =>
      'للتنبيهات الرسمية صوتها واهتزازها وقناتها الخاصة، منفصلة عن التطبيقات الأخرى. لكن بعض إعدادات الهاتف قد تُسكتها: تحقق منها هنا.';

  @override
  String get alertCheckAllGood =>
      'لا شيء يمنع التنبيهات الرسمية على هذا الهاتف.';

  @override
  String get alertCheckFix => 'إصلاح';

  @override
  String get alertChannelSettings => 'إعدادات صوت التنبيهات واهتزازها';

  @override
  String get issueNotificationsOff => 'الإشعارات معطلة';

  @override
  String get issueNotificationsOffHelp =>
      'دون إشعارات لن تصلك التنبيهات ولا نداءات التدخل.';

  @override
  String get issueChannelMuted => 'التنبيهات الرسمية مكتومة';

  @override
  String get issueChannelMutedHelp =>
      'تم تخفيض فئة «التنبيهات الرسمية» في إعدادات الهاتف: لم تعد ترنّ ولا تظهر أعلى الشاشة.';

  @override
  String get issueDnd => 'وضع «عدم الإزعاج» مفعّل';

  @override
  String get issueDndHelp =>
      'قد تصل التنبيهات دون صوت. يمكنك السماح بمرور أخطر التنبيهات الرسمية.';

  @override
  String get issueFullScreen => 'التنبيهات بملء الشاشة غير مسموح بها';

  @override
  String get issueFullScreenHelp =>
      'يجب أن تظهر أخطر التنبيهات فوق شاشة القفل. اسمح بـ«الإشعارات بملء الشاشة» لتطبيق ء-حماية.';

  @override
  String get issueBatteryOptimized => 'قد يؤخر تحسين البطارية نداءات التدخل';

  @override
  String get issueBatteryOptimizedHelp =>
      'أنت في حالة جاهزية: قد يُنيم الهاتف التطبيق ويؤخر نداءات التدخل. استثنِ ء-حماية من تحسين البطارية طوال تطوعك.';

  @override
  String get issuePushUnavailable => 'إشعارات الدفع غير متوفرة';

  @override
  String get issuePushUnavailableHelp =>
      'لا يستطيع هذا الهاتف استقبال إشعارات الدفع (مثلا دون خدمات Google): لا يتم التحقق من التنبيهات إلا والتطبيق مفتوح.';

  @override
  String get testAlertButton => 'إرسال تنبيه تجريبي';

  @override
  String get testAlertTitle => 'تجربة — تنبيه رسمي';

  @override
  String get testAlertBody =>
      'هكذا يبدو تنبيه الحماية المدنية ويُسمع. لا حاجة لأي إجراء.';

  @override
  String get testAlertSent => 'تم إرسال التنبيه التجريبي.';

  @override
  String get criticalAlertsTitle => 'التنبيهات الحرجة في وضع «عدم الإزعاج»';

  @override
  String get criticalAlertsIntro =>
      'يمكنك السماح لأخطر التنبيهات الرسمية (خطر على الأرواح: فيضان، حريق، إخلاء) بأن ترنّ حتى في وضع «عدم الإزعاج».';

  @override
  String get criticalAlertsHow =>
      'لا تستعمل هذا إلا التنبيهات ذات الخطورة القصوى. سيطلب منك الهاتف منح ء-حماية «صلاحية الوصول إلى عدم الإزعاج»؛ ويمكنك إيقاف ذلك من هنا في أي وقت.';

  @override
  String get criticalAlertsEnable => 'السماح بالتنبيهات الحرجة';

  @override
  String get criticalAlertsEnabled =>
      'يمكن للتنبيهات الحرجة أن ترنّ في وضع «عدم الإزعاج».';

  @override
  String get criticalAlertsDisable => 'إيقاف';

  @override
  String get batteryExemptTitle => 'استقبال نداءات التدخل في وقتها';

  @override
  String get batteryExemptBody =>
      'أنت في حالة جاهزية. لتوفير البطارية قد يُنيم الهاتف ء-حماية فتصلك نداءات التدخل متأخرة. استثناء التطبيق من تحسين البطارية يجنّب ذلك؛ ولا يستعمل ء-حماية الموقع إلا وهو مفتوح وأنت جاهز.';

  @override
  String get batteryExemptAllow => 'استثناء التطبيق';

  @override
  String get batterySaverTitle => 'توفير البطارية';

  @override
  String get batterySaverHelp =>
      'يقلّل من تواتر التحقق من التحديثات ومن مشاركة موقعك كمتطوع، ويؤجل الفيديوهات الكبيرة إلى شبكة Wi-Fi. لا تتأخر التنبيهات ونداءات الاستغاثة أبدا.';

  @override
  String get batterySaverAuto => 'تلقائي (عند ضعف البطارية)';

  @override
  String get batterySaverOn => 'مفعّل دائما';

  @override
  String get batterySaverOff => 'معطّل';

  @override
  String get batterySaverActive => 'نشط';

  @override
  String get batterySaverInactive => 'غير نشط';

  @override
  String batteryLevel(int percent) {
    return 'البطارية $percent%';
  }

  @override
  String get pushCalloutTitle => 'نداء تدخل';

  @override
  String get pushOpenToSee => 'افتح التطبيق للاطلاع على التفاصيل.';

  @override
  String pushReportTitle(String code) {
    return 'البلاغ $code';
  }

  @override
  String get myDataTitle => 'بياناتي';

  @override
  String get myDataSubtitle => 'تنزيل نسخة أو حذف حسابك';

  @override
  String get myDataIntro =>
      'يمكنك الحصول على نسخة من كل البيانات الشخصية التي يحتفظ بها ء-حماية عنك (الملف الشخصي، الموافقات، البلاغات، ملف التطوع، الأجهزة)، 3 مرات في اليوم على الأكثر. احتفظ بالملف لنفسك: فهو يحتوي على بيانات شخصية.';

  @override
  String get myDataDownload => 'تنزيل بياناتي';

  @override
  String get myDataCopy => 'نسخ';

  @override
  String get myDataCopied => 'تم النسخ إلى الحافظة.';

  @override
  String get myDataSave => 'حفظ كملف';

  @override
  String myDataSaved(String path) {
    return 'تم الحفظ: $path';
  }

  @override
  String get myDataSaveFailed => 'تعذّر حفظ الملف.';

  @override
  String get deleteAccountTitle => 'حذف حسابي';

  @override
  String get deleteAccountSubtitle =>
      'تُمحى بياناتك الشخصية؛ ولا يمكن التراجع عن ذلك.';

  @override
  String get deleteAccountExplain =>
      'يُمحى ملفك الشخصي وموافقاتك وأجهزتك وملف تطوعك ويُغلق حسابك. تُحفظ البلاغات التي أرسلتها دون اسمك كما يقتضي القانون. ويُمسح كل ما هو مخزّن على هذا الهاتف ويعود التطبيق إلى البداية.';

  @override
  String get deleteAccountExplainAnonymous =>
      'تُحذف الهوية المجهولة لهذا الهاتف من الخادم. تُحفظ البلاغات التي أرسلتها دون أي صلة بهذا الهاتف كما يقتضي القانون. ويُمسح كل ما هو مخزّن على هذا الهاتف ويعود التطبيق إلى البداية.';

  @override
  String get deleteAccountWord => 'حذف';

  @override
  String deleteAccountTypeWord(String word) {
    return 'اكتب «$word» للتأكيد';
  }

  @override
  String get deleteAccountConfirm => 'حذف نهائي';

  @override
  String get deleteAccountDone => 'تم حذف حسابك.';

  @override
  String get deleteAccountLastAdmin =>
      'أنت آخر مسؤول عن إحدى المؤسسات. انقل صلاحية الإدارة إلى عضو آخر أولا، ثم احذف حسابك.';

  @override
  String get lockedAlertOpenApp => 'افتح قفل الهاتف لفتح التطبيق';

  @override
  String get liveBadge => 'مباشر';

  @override
  String get homeLive => 'بث مباشر';

  @override
  String get homeLiveDesc => 'صوّر الحادثة مباشرة لأعوان الحماية المدنية.';

  @override
  String get liveTitle => 'بث مباشر';

  @override
  String get liveIntro =>
      'تُبث صورة الكاميرا وصوت الميكروفون مباشرة إلى قاعة العمليات بالحماية المدنية، وتُسجَّل وتُربط ببلاغك. يُرسل موقعك طوال مدة البث.';

  @override
  String get livePermissionRationale =>
      'يحتاج البث إلى الكاميرا والميكروفون وإلى موقعك. سيطلب الهاتف إذنك عند البدء، ولا تُستعمل إلا أثناء البث.';

  @override
  String get liveCategoryLabel => 'نوع الحادثة';

  @override
  String get liveStart => 'ابدأ البث';

  @override
  String get liveStop => 'إيقاف البث';

  @override
  String get liveMute => 'كتم الميكروفون';

  @override
  String get liveUnmute => 'تشغيل الميكروفون';

  @override
  String get liveSwitchCamera => 'تبديل الكاميرا';

  @override
  String get livePreparing => 'جارٍ تحضير البث…';

  @override
  String get liveConnecting => 'جارٍ الاتصال بخادم البث…';

  @override
  String liveReconnecting(int attempt, int max) {
    return 'انقطع الاتصال. محاولة $attempt من $max…';
  }

  @override
  String get liveWeakNetwork =>
      'الشبكة ضعيفة جدا للبث. يمكنك تسجيل مقطع قصير وإرساله بدلا من ذلك.';

  @override
  String get liveLocationOff => 'الموقع غير مفعّل: لن يُرسل موقعك أثناء البث.';

  @override
  String get liveLocationOn => 'يُرسل موقعك أثناء البث';

  @override
  String liveEndsIn(String time) {
    return 'ينتهي البث آليا خلال $time';
  }

  @override
  String liveReportCode(String code) {
    return 'البلاغ $code';
  }

  @override
  String liveSemanticsOnAir(String duration) {
    return 'البث جارٍ منذ $duration';
  }

  @override
  String get liveEndedTitle => 'انتهى البث';

  @override
  String get liveEndedByUser => 'أوقفت البث. التسجيل محفوظ مع بلاغك.';

  @override
  String get liveEndedByOperator =>
      'أنهى عون قاعة العمليات البث. شكرا، الصور وصلت.';

  @override
  String liveEndedMaxDuration(int minutes) {
    return 'بلغ البث مدته القصوى ($minutes دقيقة).';
  }

  @override
  String get liveEndedByServer => 'أنهت المنصة البث.';

  @override
  String get liveEndedLocked => 'توقف البث لأن الهاتف عاد إلى شاشة القفل.';

  @override
  String liveDuration(String duration) {
    return 'المدة: $duration';
  }

  @override
  String get liveFailedTitle => 'تعذّر البث المباشر';

  @override
  String get liveFailNoLocation =>
      'تعذّر تحديد موقعك، فلا يمكن إنشاء البلاغ. اتصل بالرقم 198.';

  @override
  String get liveFailReportNotSent =>
      'بلاغك محفوظ على الهاتف وسيُرسل عند عودة الشبكة. يمكنك تسجيل مقطع يُرفق به.';

  @override
  String get liveFailPermission =>
      'رُفض الوصول إلى الكاميرا أو الميكروفون. فعّله من إعدادات الهاتف لاستعمال البث.';

  @override
  String get liveFailCamera => 'الكاميرا غير متاحة (قد يستعملها تطبيق آخر).';

  @override
  String get liveFailConnection => 'تعذّر الاتصال بخادم البث رغم عدة محاولات.';

  @override
  String get liveFailLocked =>
      'البث غير متاح من شاشة التنبيه فوق القفل. افتح قفل الهاتف أولا.';

  @override
  String get liveFallbackTitle => 'إرسال مقطع فيديو بدلا من البث';

  @override
  String get liveFallbackBody =>
      'سجّل مقطعا لا يتجاوز 60 ثانية، يُرفع آليا مع بلاغك ولو كانت الشبكة ضعيفة.';

  @override
  String get liveRecordClip => 'تسجيل مقطع (60 ثانية)';

  @override
  String get liveClipQueued => 'المقطع محفوظ وسيُرسل مع بلاغك.';

  @override
  String get liveClipFailed => 'تعذّر حفظ المقطع.';

  @override
  String get liveRetry => 'إعادة المحاولة';

  @override
  String get liveOpenSettings => 'فتح الإعدادات';

  @override
  String get liveDone => 'تم';

  @override
  String get liveLeaveTitle => 'إيقاف البث؟';

  @override
  String get liveLeaveBody => 'البث جارٍ. الخروج يوقف إرسال الصورة والموقع.';

  @override
  String get liveSimulationBadge => 'وضع المحاكاة';

  @override
  String get liveSimulationHelp =>
      'هذا البث يمر بمنظومة المحاكاة ولا يصل إلى قاعة عمليات حقيقية.';

  @override
  String get reportGoLive => 'بث مباشر لهذا البلاغ';

  @override
  String get errorStreamAlreadyActive => 'بث مباشر جارٍ بالفعل لهذا البلاغ.';

  @override
  String get errorStreamNotActive => 'انتهى هذا البث.';

  @override
  String get errorReportClosed => 'هذا البلاغ مغلق: لا يمكن فتح بث مباشر له.';

  @override
  String get weatherTitle => 'الطقس قربك';

  @override
  String get weatherLoading => 'جارٍ تحميل حالة الطقس…';

  @override
  String get weatherNoLocation =>
      'اسمح بالوصول إلى الموقع لعرض حالة الطقس حيث أنت.';

  @override
  String get weatherUseLocation => 'استعمال موقعي';

  @override
  String get weatherOutsideCoverage => 'تغطي توقعات الطقس التراب التونسي فقط.';

  @override
  String get weatherOffline =>
      'لا يوجد اتصال بالإنترنت: ستُعرض حالة الطقس عند عودة الاتصال.';

  @override
  String get weatherUnavailable => 'تعذّر تحميل حالة الطقس.';

  @override
  String get weatherRetry => 'إعادة المحاولة';

  @override
  String get weatherNotRefreshed =>
      'لم يتم التحديث: تُعرض آخر المعطيات المستلمة.';

  @override
  String weatherUpdated(String time) {
    return 'آخر تحديث $time';
  }

  @override
  String weatherCachedAt(String time) {
    return 'نسخة محفوظة من $time';
  }

  @override
  String get weatherNow => 'الآن';

  @override
  String get weatherNextHours => 'الساعات القادمة';

  @override
  String weatherTemperature(String value) {
    return '$value درجة مئوية';
  }

  @override
  String weatherWind(String speed) {
    return 'الرياح $speed كم/س';
  }

  @override
  String weatherGusts(String speed) {
    return 'هبّات $speed كم/س';
  }

  @override
  String weatherHumidity(String value) {
    return 'الرطوبة $value%';
  }

  @override
  String weatherRain(String value) {
    return 'الأمطار $value مم/س';
  }

  @override
  String weatherRain24h(String value) {
    return '$value مم خلال 24 ساعة';
  }

  @override
  String weatherFireDanger(String level) {
    return 'خطر الحرائق: $level';
  }

  @override
  String get weatherFireLow => 'ضعيف';

  @override
  String get weatherFireModerate => 'معتدل';

  @override
  String get weatherFireHigh => 'مرتفع';

  @override
  String get weatherFireVeryHigh => 'مرتفع جدا';

  @override
  String get weatherFireExtreme => 'قصوى';

  @override
  String weatherHeavyRain(String level) {
    return 'أمطار غزيرة: $level';
  }

  @override
  String get weatherRainWatch => 'يقظة';

  @override
  String get weatherRainWarning => 'إنذار';

  @override
  String get weatherCondClear => 'سماء صافية';

  @override
  String get weatherCondCloudy => 'غائم';

  @override
  String get weatherCondFog => 'ضباب';

  @override
  String get weatherCondRain => 'أمطار';

  @override
  String get weatherCondSnow => 'ثلوج';

  @override
  String get weatherCondStorm => 'عاصفة رعدية';

  @override
  String get weatherAlertsTitle => 'تنبيهات جوية سارية';

  @override
  String weatherSource(String source) {
    return 'المعطيات: $source';
  }

  @override
  String get weatherSimulationBadge => 'وضع المحاكاة';

  @override
  String get weatherSimulationHelp =>
      'قيم الطقس هذه محاكاة وليست قياسات حقيقية.';

  @override
  String get offlineFallbackTitle => 'لا يوجد اتصال بالإنترنت';

  @override
  String get offlineFallbackBody =>
      'بلاغك محفوظ في الهاتف وسيُرسل آليا عند عودة الإنترنت. لإعلام الحماية المدنية الآن:';

  @override
  String get offlineSendSms => 'الإرسال عبر رسالة قصيرة';

  @override
  String get offlineSmsHelp =>
      'يفتح تطبيق الرسائل برسالة قصيرة (نوع البلاغ وموقعه). أنت من يضغط على «إرسال».';

  @override
  String get offlineSmsFee => 'قد يحتسب مشغّل الهاتف ثمن رسالة قصيرة عادية.';

  @override
  String get offlineSmsFailed => 'تعذّر فتح تطبيق الرسائل. اتصل بالرقم 198.';

  @override
  String get rewardsTitle => 'مكافآتي';

  @override
  String get homeRewardsDesc =>
      'النقاط والشارات والشهادات المكتسبة بفضل البلاغات المفيدة.';

  @override
  String get rewardsBalanceLabel => 'رصيد النقاط';

  @override
  String get rewardsNoBadge => 'لا شارة بعد';

  @override
  String rewardsCurrentBadge(String badge) {
    return 'الشارة الحالية: $badge';
  }

  @override
  String rewardsNextBadge(String badge, int points) {
    return 'الشارة التالية، $badge: بقيت $points نقطة';
  }

  @override
  String get rewardsTopBadge => 'لديك أعلى شارة. شكرا على يقظتك.';

  @override
  String get rewardsConfirmNote =>
      'تظهر الشارات الفضية والذهبية وشارة السفير بعد أن يؤكدها عون من الحماية المدنية.';

  @override
  String get badgeBronze => 'برونزية';

  @override
  String get badgeSilver => 'فضية';

  @override
  String get badgeGold => 'ذهبية';

  @override
  String get badgeAmbassador => 'سفير';

  @override
  String get rewardsPausedTitle => 'النقاط موقوفة مؤقتا';

  @override
  String get rewardsPausedBody =>
      'مستوى الكارثة سارٍ حاليا. تُحفظ النقاط الجديدة وتُضاف عند انخفاض المستوى.';

  @override
  String rewardsPendingPoints(int points) {
    return 'نقاط في الانتظار: $points';
  }

  @override
  String get rewardsHistoryTitle => 'السجل';

  @override
  String get rewardsHistoryEmpty =>
      'لا نقاط بعد. تُضاف النقاط عندما يتم التحقق من بلاغ أرسلته ثم غلقه.';

  @override
  String get rewardsShowMore => 'عرض المزيد';

  @override
  String get pointsReasonReportVerified => 'بلاغ تم التحقق منه';

  @override
  String get pointsReasonHelpedRescue => 'بلاغ ساعد في إنقاذ';

  @override
  String get pointsReasonAccurateCategory => 'اختيار الصنف الصحيح';

  @override
  String get pointsReasonVolunteerMission => 'مهمة تطوعية منجزة';

  @override
  String get pointsReasonManual => 'تعديل من الحماية المدنية';

  @override
  String get pointsReasonRevocation => 'نقاط مسحوبة';

  @override
  String get pointsReasonOther => 'أخرى';

  @override
  String get rewardsCapped => 'تم بلوغ الحد اليومي';

  @override
  String rewardsDailyCap(int points) {
    return 'الحد الأقصى للنقاط في اليوم الواحد: $points.';
  }

  @override
  String get rewardsCertificatesTitle => 'الشهادات';

  @override
  String get rewardsCertificatesEmpty => 'لا شهادة بعد.';

  @override
  String rewardsCertificateYear(String year) {
    return 'سنة $year';
  }

  @override
  String get distinctionVigilantCitizen => 'المواطن اليقظ';

  @override
  String get distinctionBraveVolunteer => 'المتطوع الشجاع';

  @override
  String get distinctionLeadingInstitution => 'المؤسسة الرائدة';

  @override
  String distinctionBadge(String badge) {
    return 'شارة $badge';
  }

  @override
  String get distinctionOther => 'تميّز';

  @override
  String get rewardsOpenPdf => 'فتح الشهادة بصيغة PDF';

  @override
  String get rewardsPdfNoViewer =>
      'لا يوجد تطبيق على هذا الهاتف يمكنه فتح ملف PDF.';

  @override
  String get rewardsAnonymousTitle => 'البلاغات المجهولة لا تمنح نقاطا';

  @override
  String get rewardsAnonymousBody =>
      'البلاغ المرسل دون حساب لا يمكن ربطه بأي شخص، لذلك لا يمنح نقاطا ولا شارات ولا شهادات. أنشئ حسابا للمشاركة؛ وتبقى البلاغات المرسلة سابقا دون هوية مجهولة.';

  @override
  String get rewardsSafetyNotice =>
      'لا تعرّض نفسك أبدا للخطر من أجل التبليغ. سلامتك أولا: في حالة الطوارئ اتصل بالرقم 198.';

  @override
  String get rewardsPrizesNotice =>
      'النقاط والشارات والشهادات اعتراف علني وليست مالا. وتخضع أي جائزة سنوية لقرار من السلطة المختصة.';

  @override
  String rewardsOfflineCopy(String date) {
    return 'دون اتصال: نسخة محفوظة بتاريخ $date.';
  }

  @override
  String get rewardsHowTitle => 'كيف تكسب النقاط';

  @override
  String get rewardsHowBody =>
      'تُضاف النقاط عندما يتم التحقق من بلاغ أرسلته ثم غلقه، وتكون أكثر إذا ساعد في إنقاذ أو إذا اخترت الصنف الصحيح، وعن كل مهمة تطوعية منجزة. لا نقاط للبلاغات الكاذبة أو المرفوضة.';

  @override
  String trackPointsEarned(int points) {
    return 'النقاط المكتسبة بفضل هذا البلاغ: $points';
  }

  @override
  String get trackPointsOpenRewards => 'عرض مكافآتي';

  @override
  String get anonQuotaCardTitle => 'البلاغات دون حساب';

  @override
  String anonQuotaRemaining(int remaining, int limit) {
    return 'تبقّى $remaining من $limit';
  }

  @override
  String anonQuotaRemainingShort(int remaining) {
    return 'تبقّى $remaining';
  }

  @override
  String get anonQuotaExhaustedHint =>
      'تمّ بلوغ الحدّ: أنشئ حسابا لمواصلة التبليغ. زرّ النجدة والرقم 198 متاحان دائما.';

  @override
  String get anonQuotaTitle => 'التبليغ دون حساب';

  @override
  String get anonQuotaExplanation =>
      'لتفادي الاستعمال المسيء، يمكن لكل تثبيت للتطبيق إرسال عدد محدود من البلاغات دون حساب. بحساب مجاني تواصل التبليغ وتتابع بلاغاتك من أي جهاز ويكون لبلاغاتك وزن أكبر.';

  @override
  String get anonQuotaEmergencyNote =>
      'في حالة الطوارئ، يعمل زرّ النجدة والاتصال بالرقم 198 دائما، بحساب أو دونه.';

  @override
  String anonQuotaDraftKept(String code) {
    return 'بلاغك $code محفوظ على هذا الهاتف. سيُرسل فور إنشاء حساب أو تسجيل الدخول.';
  }

  @override
  String get anonQuotaReportKeptBody =>
      'تمّ بلوغ حدّ البلاغات دون حساب. هذا البلاغ محفوظ على هذا الهاتف وسيُرسل فور إنشاء حساب أو تسجيل الدخول.';

  @override
  String get anonQuotaOpen => 'لماذا هذا الحدّ؟';

  @override
  String get errorAnonQuotaExhausted =>
      'تمّ بلوغ حدّ البلاغات دون حساب على هذا الجهاز. يُرجى إنشاء حساب.';

  @override
  String get intro1Title => 'مرحبا بكم في ء-حماية';

  @override
  String get intro1Body =>
      'تطبيق ء-حماية يحدّد موقعك من هاتفك، وعند الطارئ يرسله مع بلاغك مباشرة إلى قاعة العمليات المختصة بالحماية المدنية، لتصلك النجدة أسرع وبالوسائل المناسبة.';

  @override
  String get intro2Title => 'بإشراف الديوان الوطني للحماية المدنية';

  @override
  String get intro2Body =>
      'يقدّم هذا التطبيقَ الديوانُ الوطني للحماية المدنية، المؤسسة العمومية المكلفة بالنجدة والإنقاذ ومجابهة الحرائق والكوارث على كامل التراب التونسي، والمستقبِلة لنداءات الرقم 198.';

  @override
  String get intro3Title => 'متى أستعمله؟';

  @override
  String get intro3Body =>
      'عند حريق، أو حادث مرور، أو شخص في خطر أو مصاب، أو غرق، أو انهيار، أو تسرب غاز، أو فيضان، أو أي وضع يهدّد الأرواح والممتلكات ويستوجب تدخل الحماية المدنية.';

  @override
  String get intro4Title => 'كيف يعمل؟';

  @override
  String get intro4Body =>
      'اختر نوع الحادث، والتقط صورة أو فيديو أو رسالة صوتية إن أمكن دون أن تعرّض نفسك للخطر، ثم أرسل. يصل بلاغك وموقعك فورا إلى المشغّل، وتتابع مآله خطوة بخطوة، وقد يتصل بك المشغّل لاستكمال المعطيات. وإن انقطع الإنترنت يُرسل البلاغ برسالة قصيرة، ويبقى الاتصال بالرقم 198 متاحا في كل لحظة.';

  @override
  String get intro5Title => 'أين يعمل؟';

  @override
  String get intro5Body =>
      'على كامل تراب الجمهورية التونسية، في الولايات الأربع والعشرين، ويُوجَّه بلاغك آليا إلى الإدارة الجهوية المختصة بمكان الحادث. خارج تونس اتصل برقم الطوارئ المحلي (112 في أغلب الدول).';

  @override
  String get terms1Title => '1. التعريف';

  @override
  String get terms1Body =>
      'ء-حماية منصة رقمية للديوان الوطني للحماية المدنية (يُشار إليه بـ «الديوان») للتبليغ عن حالات الطوارئ ومتابعتها. تضبط هذه الشروط العلاقة بين الديوان ومستعملي تطبيق الهاتف وبوابة المؤسسات.';

  @override
  String get terms2Title => '2. غايتنا';

  @override
  String get terms2Body =>
      'الغاية السامية لهذه المنصة حماية الأرواح والممتلكات، وإعادة بناء جسور الثقة بين المواطن والحماية المدنية عبر تواصل مباشر وشفاف. وصفُ الحادث بدقة ونقلُ المشهد كما هو يقلّصان زمن الاستجابة ويرفعان نجاعة التدخل.';

  @override
  String get terms3Title => '3. طبيعة الخدمة وحدودها';

  @override
  String get terms3Body =>
      '3.1 التطبيق وسيلة مكمّلة للرقم 198 ولا يعوّضه. في الخطر الداهم اتصل بالرقم 198 مباشرة.\n3.2 لا يقدّم التطبيق استشارة طبية، والإرشادات المعروضة فيه للتوعية العامة ولا تعوّض تعليمات أعوان الحماية المدنية.\n3.3 يتوقف عمل التطبيق على عوامل خارجة عن سيطرة الديوان: تغطية شبكة الهاتف والإنترنت، وإشارة تحديد الموقع، وشحن البطارية، وسلامة الهاتف. يعمل الديوان على أعلى درجات التوفر وإصلاح الأعطال في أقرب الآجال.';

  @override
  String get terms4Title => '4. التزامات المستعمل';

  @override
  String get terms4Body =>
      '4.1 استعمال التطبيق بحسن نية وللطوارئ الحقيقية فقط، وتقديم معطيات صحيحة ومحيّنة، خاصة رقم الهاتف.\n4.2 إبقاء خدمة تحديد الموقع مفعّلة واستعمال آخر إصدار من التطبيق.\n4.3 عدم تعريض النفس للخطر من أجل التصوير، واحترام تعليمات أعوان التدخل.\n4.4 عدم المساس بسلامة التطبيق أو تعطيله أو محاولة تجاوز وسائل حمايته أو إعادة هندسته.';

  @override
  String get terms5Title => '5. البلاغات الكاذبة وسوء الاستعمال';

  @override
  String get terms5Body =>
      'كل بلاغ يُسخّر فرق نجدة قد تحتاجها أرواح أخرى في اللحظة نفسها. إن تقديم بلاغ كاذب أو إنذار زائف عن قصد، أو أي استعمال تعسفي للتطبيق، يعرّض صاحبه للمساءلة والتتبعات طبقا للتشريع التونسي الجاري به العمل، ويمكن أن يؤدي إلى تعليق الحساب أو التبليغ من الجهاز المعني مؤقتا أو نهائيا.';

  @override
  String get terms6Title => '6. التزامات المؤسسات';

  @override
  String get terms6Body =>
      'تلتزم المؤسسة المسجلة بتقديم معطيات صحيحة ومحيّنة عن هويتها ونشاطها ومبانيها والمسؤولين عنها، وتتحمّل مسؤولية صحتها. إيداع مخطط الإخلاء ومخططات المبنى وتحيينها يسهّل التدخل ويختصر زمن البحث والإنقاذ. لا يُفعَّل حساب المؤسسة إلا بعد مصادقة الديوان.';

  @override
  String get terms7Title => '7. المتطوعون';

  @override
  String get terms7Body =>
      'لا تُمنح صفة المتطوع إلا بعد مصادقة الديوان. يلتزم المتطوع بتعليمات قاعة العمليات ولا يتدخل إلا في حدود المهمة المسندة إليه.';

  @override
  String get terms8Title => '8. حماية المعطيات الشخصية';

  @override
  String get terms8Body =>
      '8.1 تُعالَج المعطيات الشخصية طبقا للقانون الأساسي عدد 63 لسنة 2004 المؤرخ في 27 جويلية 2004 المتعلق بحماية المعطيات الشخصية، وتحت رقابة الهيئة الوطنية لحماية المعطيات الشخصية، وللغاية الوحيدة المتمثلة في معالجة حالات الطوارئ وإعلامك بمآل بلاغاتك.\n8.2 عند إرسال بلاغ تُنقل إلى الديوان: موقعك، ونوع الحادث، والوصف والوسائط المرفقة، ومعطيات حسابك إن وُجد.\n8.3 جهات اتصال الطوارئ ونص رسالة النجدة تُحفظ مشفّرة على هاتفك فقط ولا تُرسل إلى الديوان.\n8.4 يمكن التبليغ دون حساب باسم مستعار، دون تسجيل عنوان IP.\n8.5 لا يطّلع على المعطيات إلا الأعوان المرخّص لهم، وتُحفظ للمدة اللازمة لمعالجة الحالة والوفاء بالالتزامات القانونية. ولك حق النفاذ إليها وتصحيحها والاعتراض على معالجتها.';

  @override
  String get terms9Title => '9. تحديث التطبيق والشروط';

  @override
  String get terms9Body =>
      'يمكن للديوان تطوير التطبيق أو تعديل هذه الشروط. يُعلَم المستعمل بكل إصدار جديد وبما يتضمنه، ويُطلب منه الموافقة من جديد عند تغيير الشروط.';

  @override
  String get terms10Title => '10. القانون المنطبق';

  @override
  String get terms10Body =>
      'تخضع هذه الشروط للقانون التونسي، وتختص المحاكم التونسية بالنظر في كل نزاع يتعلق بها.';

  @override
  String get languageTitle => 'اختر لغتك';

  @override
  String get languageSubtitle =>
      'يمكنك تغييرها في أي وقت من شريط اللغة أعلى كل شاشة.';

  @override
  String get languageMenuTooltip => 'اللغة';

  @override
  String get introSkip => 'تخطٍّ';

  @override
  String introPage(int current, int total) {
    return 'الصفحة $current من $total';
  }

  @override
  String get call198 => 'اتصل بالرقم 198';

  @override
  String get termsScrollHint => 'مرّر حتى نهاية الشروط لتتمكن من الموافقة.';

  @override
  String get termsAccept => 'أوافق';

  @override
  String get termsDecline => 'لا أوافق';

  @override
  String get termsDeclinedTitle => 'لم تتم الموافقة على الشروط';

  @override
  String get termsDeclinedBody =>
      'لا يمكنك استعمال التطبيق دون الموافقة على الشروط، لكن الاتصال بالرقم 198 متاح دائما.';

  @override
  String get termsReadAgain => 'قراءة الشروط';

  @override
  String get permissionsTitle => 'الأذونات';

  @override
  String get permissionsIntro =>
      'لا يطلب ء-حماية إلا ما يحتاجه لمساعدتك. يمكنك تغيير هذه الاختيارات لاحقا من إعدادات الهاتف.';

  @override
  String get permLocationTitle => 'الموقع';

  @override
  String get permLocationBody =>
      'يُرسل مع بلاغك لتصل إليك النجدة. بدونه يجب أن تصف المكان وقد يتأخر الوصول إليك.';

  @override
  String get permNotificationsTitle => 'الإشعارات';

  @override
  String get permNotificationsBody =>
      'متابعة بلاغاتك والتنبيهات العامة قربك. بدونها لن تُنبَّه إلى خطر في منطقتك.';

  @override
  String get permSmsTitle => 'الرسائل القصيرة';

  @override
  String get permSmsBody =>
      'دون إنترنت يُرسل بلاغك برسالة قصيرة. لا حاجة لأي إذن: يفتح التطبيق رسالة جاهزة ترسلها بنفسك.';

  @override
  String get permContactsTitle => 'جهات الاتصال';

  @override
  String get permContactsBody =>
      'يُطلب فقط عندما تختار جهة اتصال للطوارئ، لاحقا.';

  @override
  String get permAllow => 'السماح';

  @override
  String get permAllowed => 'مسموح';

  @override
  String get permRefused => 'مرفوض: يمكنك السماح به من إعدادات الهاتف';

  @override
  String get permNoneNeeded => 'لا حاجة لإذن';

  @override
  String get permLater => 'لاحقا';

  @override
  String get signInTitle => 'الدخول';

  @override
  String get signInIntro =>
      'ادخل برقم هاتفك الجوال: نرسل لك رمزا برسالة قصيرة. دون كلمة سر.';

  @override
  String get signInPhoneLabel => 'رقم الهاتف الجوال';

  @override
  String get signInPhoneHint => '8 أرقام';

  @override
  String get signInPhoneInvalid =>
      'أدخل رقما جوالا تونسيا: 8 أرقام تبدأ بـ 2 أو 3 أو 4 أو 5 أو 9.';

  @override
  String get signInSendCode => 'أرسل الرمز';

  @override
  String get signInCodeLabel => 'الرمز الوارد في الرسالة';

  @override
  String signInCodeSentTo(String phone) {
    return 'أُرسل رمز من 6 أرقام إلى $phone.';
  }

  @override
  String get signInVerify => 'دخول';

  @override
  String signInResendIn(int seconds) {
    return 'إعادة إرسال الرمز بعد $seconds ث';
  }

  @override
  String get signInResend => 'أعد إرسال الرمز';

  @override
  String get signInChangeNumber => 'تغيير الرقم';

  @override
  String signInWrongCode(int tries) {
    return 'رمز خاطئ. المحاولات المتبقية: $tries.';
  }

  @override
  String get signInCodeExpired =>
      'انتهت صلاحية الرمز أو استُنفدت محاولاته. اطلب رمزا جديدا.';

  @override
  String get signInTooSoon => 'انتظر دقيقة قبل طلب رمز جديد.';

  @override
  String get signInLimit => 'طلبات كثيرة لهذا الرقم. أعد المحاولة بعد ساعة.';

  @override
  String get signInSmsUnavailable =>
      'تعذّر إرسال الرسالة. أعد المحاولة أو واصل كزائر.';

  @override
  String get signInNetworkError =>
      'لا يوجد اتصال. تحقّق من الإنترنت وأعد المحاولة.';

  @override
  String get signInGuest => 'المواصلة كزائر';

  @override
  String get signInGuestDesc => 'التبليغ دون حساب (عدد محدود من البلاغات).';

  @override
  String get signInInstitution => 'حساب مؤسسة';

  @override
  String get signInInstitutionDesc => 'للشركات والمدارس والنزل والإدارات.';

  @override
  String get signInEmail => 'الدخول بالبريد الإلكتروني وكلمة السر';

  @override
  String get signInPrivacyNote => 'يُستعمل رقمك فقط للاتصال بك بخصوص بلاغاتك.';

  @override
  String get simBanner =>
      '[SIM] محاكاة: تذهب الرسالة إلى بوابة الاختبار (notify-sim) لا إلى هاتف حقيقي.';

  @override
  String get homeSubtitle => 'الحماية المدنية التونسية';

  @override
  String get homeReportCardTitle => 'أبلغ عن حادث';

  @override
  String get homeReportCardDesc => 'صورة أو صوت أو نص، مع موقعك آليا';

  @override
  String get homeNumbersOffline => 'تعمل دون إنترنت';

  @override
  String get homeShortcuts => 'اختصارات';

  @override
  String get homeMyReports => 'بلاغاتي';

  @override
  String get homeSosMessage => 'رسالة النجدة';

  @override
  String get homeCall198 => 'مكالمة النجدة 198';

  @override
  String get locationOn => 'الموقع مفعّل';

  @override
  String get locationOff => 'الموقع غير مفعّل: قد يتأخر وصول النجدة إليك.';

  @override
  String get locationTurnOn => 'تفعيل';

  @override
  String get locationChecking => 'جارٍ التحقق من الموقع…';

  @override
  String get themeToggleTooltip => 'فاتح أو داكن';

  @override
  String get settingsColors => 'الألوان';

  @override
  String get colorOffice => 'الحماية المدنية (الشعار)';

  @override
  String get colorRed => 'أحمر';

  @override
  String get colorBlue => 'أزرق';

  @override
  String get colorGreen => 'أخضر';

  @override
  String get updateTitle => 'إصدار جديد متاح';

  @override
  String get updateMandatoryTitle => 'التحديث ضروري';

  @override
  String get updateMandatoryBody =>
      'هذا الإصدار لم يعد مدعوما. حدّث التطبيق لمواصلة استعمال ء-حماية. تبقى أرقام الطوارئ متاحة.';

  @override
  String updateWhatsNew(String version) {
    return 'الجديد في الإصدار $version';
  }

  @override
  String get updateDataKept => 'تُحفظ بلاغاتك وإعداداتك.';

  @override
  String get updateNow => 'تحديث';

  @override
  String get updateLater => 'لاحقا';

  @override
  String get updateOpenFailed => 'تعذّر فتح صفحة التنزيل.';

  @override
  String get requiredNote => 'الحقول المعلّمة بـ * إجبارية.';

  @override
  String get requiredSemantics => 'إجباري';

  @override
  String get errorOffensiveText =>
      'يحتوي النص على ألفاظ غير مسموح بها. يرجى إعادة صياغته.';

  @override
  String get guideTitle => 'دليل الطوارئ';

  @override
  String get guideHubHint =>
      'الحرائق، الكسور، الإسعافات الأولية، مشاكل التنفس… متوفر دون اتصال.';

  @override
  String get guideIntro =>
      'اختر المحور ثم الحالة. في انتظار وصول النجدة، اتبع الخطوات بالترتيب.';

  @override
  String guideItemsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count عنصرا',
      few: '$count عناصر',
      two: 'عنصران',
      one: 'عنصر واحد',
      zero: 'لا عناصر',
    );
    return '$_temp0';
  }

  @override
  String get guideEmpty => 'لا يوجد محتوى منشور هنا حاليا.';

  @override
  String get guideCallNow => 'اتصل فورا بالرقم 198 إذا';

  @override
  String get guideSteps => 'ماذا تفعل';

  @override
  String get guideDont => 'لا تفعل';

  @override
  String get guideCall198 => 'اتصل بالحماية المدنية، 198';

  @override
  String get guideSimBanner =>
      '[SIM] محتوى في انتظار المصادقة من الإطار الطبي للحماية المدنية. اتصل أولا بالرقم 198.';

  @override
  String get guideSimTag => '[SIM] في انتظار المصادقة الطبية';

  @override
  String get nearestTitle => 'الأقرب إليّ';

  @override
  String get nearestHint =>
      'مراكز الحماية المدنية، المستشفيات، الصيدليات… وإحداثياتك. يعمل دون اتصال بعد التنزيل.';

  @override
  String get nearestMyPosition => 'موقعي';

  @override
  String get nearestNoLocation =>
      'تحديد الموقع متوقف أو غير مسموح. فعّله لترى الأماكن الأقرب.';

  @override
  String get nearestCopy => 'نسخ';

  @override
  String get nearestCopied =>
      'نُسخت الإحداثيات. يمكنك قراءتها على عون الاستقبال.';

  @override
  String get nearestOffline =>
      'لا يوجد اتصال: تُعرض النسخة المحفوظة على هذا الهاتف.';

  @override
  String get nearestEmpty =>
      'لا شيء محفوظ على هذا الهاتف بعد. اتصل بالإنترنت مرة واحدة لتنزيل الأماكن.';

  @override
  String get nearestLoading => 'جارٍ تنزيل الأماكن للاستعمال دون اتصال…';

  @override
  String nearestUpdated(String date) {
    return 'حُدّثت الأماكن في $date';
  }

  @override
  String get nearestToVerify => 'للتثبت';

  @override
  String get nearestSimBanner =>
      '[SIM] بعض هذه الأماكن وهمية تقريبية للتجربة وليست أماكن حقيقية. في الطوارئ اتصل بـ 198.';

  @override
  String get nearestSimChip => '[SIM] تجربة';

  @override
  String get nearestNeedPosition => 'في انتظار تحديد موقعك.';

  @override
  String get nearestNone => 'لا يوجد مكان من هذا النوع مسجل بعد.';

  @override
  String nearestSource(String source) {
    return 'المصدر: $source';
  }

  @override
  String nearestCall(String phone) {
    return 'اتصل بالرقم $phone';
  }

  @override
  String get nearestRoute => 'المسار';

  @override
  String get contactTitle => 'اتصل بنا';

  @override
  String get contactMineTitle => 'طلباتي';

  @override
  String get contactEmergencyBanner =>
      'ليست للطوارئ. في حالة الطوارئ، اتصل بالرقم 198.';

  @override
  String get contactIntro =>
      'اطرح سؤالا، اطلب معلومة لدى الحماية المدنية، أبلغ عن خطر غير عاجل، اقترح فكرة أو أبلغ عن مشكلة في التطبيق. ستحصل على رقم لمتابعة طلبك.';

  @override
  String get contactKind => 'نوع الطلب';

  @override
  String get contactKindAccessInfo => 'النفاذ إلى المعلومة (القانون 2016-22)';

  @override
  String get contactKindHazard => 'خطر غير عاجل';

  @override
  String get contactKindQuestion => 'سؤال';

  @override
  String get contactKindSuggestion => 'مقترح';

  @override
  String get contactKindAppProblem => 'مشكلة في التطبيق';

  @override
  String get contactKindPartnership => 'شراكة';

  @override
  String get contactAccessInfoHint =>
      'يشترط القانون ذكر اسمك. يرد الديوان في الأجل القانوني (20 يوما).';

  @override
  String get contactNoGouvernorat => 'غير مرتبط بولاية';

  @override
  String get contactSubject => 'الموضوع';

  @override
  String get contactMessage => 'رسالتك';

  @override
  String get contactDetailsHint =>
      'معطيات الاتصال اختيارية: بدونها يظهر الرد هنا فقط في «طلباتي».';

  @override
  String get contactName => 'الاسم واللقب';

  @override
  String get contactEmail => 'البريد الإلكتروني';

  @override
  String get contactEmailInvalid => 'أدخل بريدا إلكترونيا صحيحا.';

  @override
  String contactLength(int min, int max) {
    return 'بين $min و$max حرفا.';
  }

  @override
  String get contactSend => 'إرسال';

  @override
  String get contactSentTitle => 'تمّ إرسال الطلب';

  @override
  String get contactSentBody => 'احتفظ بهذا الرقم لمتابعة طلبك:';

  @override
  String get contactSeeMine => 'عرض طلباتي';

  @override
  String get contactMineEmpty => 'لم ترسل أي طلب بعد.';

  @override
  String get contactStatusReceived => 'وارد';

  @override
  String get contactStatusInProgress => 'قيد المعالجة';

  @override
  String get contactStatusAnswered => 'تمّ الرد';

  @override
  String get contactStatusClosed => 'مغلق';

  @override
  String get contactStatusRejected => 'مرفوض';

  @override
  String contactDue(String date) {
    return 'الرد متوقع قبل $date';
  }

  @override
  String get contactAnswer => 'رد الديوان';

  @override
  String get contactRejectReason => 'السبب المبلّغ من الديوان';
}
