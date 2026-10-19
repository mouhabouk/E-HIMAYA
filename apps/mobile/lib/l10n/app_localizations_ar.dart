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
  String get charterTitle => 'ميثاق الخصوصية وحماية المعطيات الشخصية';

  @override
  String charterVersionLabel(String version) {
    return 'الإصدار $version';
  }

  @override
  String get charterIntro =>
      'ء-حماية هي المنصة الوطنية للتبليغ عن حالات الطوارئ لدى الحماية المدنية. قبل استعمالها، يُرجى الاطلاع على كيفية معالجة معطياتك وعلى التزاماتك.';

  @override
  String get charterDataTitle => 'المعطيات التي نجمعها والغاية منها';

  @override
  String get charterDataBody =>
      'لكل بلاغ: صنفه، والوصف الذي تكتبه، وموقع الحادثة، والصور أو مقاطع الفيديو أو الرسائل الصوتية المرفقة. وإن أنشأت حسابا: اسمك ولقبك، ورقم بطاقة التعريف الوطنية، ورقم الهاتف، والجهة. تُستعمل هذه المعطيات حصريا لمعالجة حالات الطوارئ ولإعلامك بمآل بلاغاتك.';

  @override
  String get charterLawTitle => 'الإطار القانوني';

  @override
  String get charterLawBody =>
      'تُعالَج معطياتك الشخصية طبقا للقانون الأساسي عدد 63 لسنة 2004 المؤرخ في 27 جويلية 2004 المتعلق بحماية المعطيات الشخصية ونصوصه التطبيقية، وتحت رقابة الهيئة الوطنية لحماية المعطيات الشخصية.';

  @override
  String get charterAnonymousTitle => 'التبليغ دون حساب';

  @override
  String get charterAnonymousBody =>
      'يمكنك التبليغ دون حساب. يستعمل التطبيق عندها مفتاحا عشوائيا يُنشأ على هذا الهاتف، ولا تحتفظ المنصة إلا باسم مستعار مشتق منه ولا تسجّل عنوان IP الخاص بك. يمكن تعليق التبليغ دون حساب من جهاز ما بعد ثبوت بلاغات كاذبة.';

  @override
  String get charterRightsTitle => 'حقوقك';

  @override
  String get charterRightsBody =>
      'لك حق النفاذ إلى معطياتك وتصحيحها والاعتراض على معالجتها وفق الشروط التي يضبطها القانون. يمكنك ممارسة هذه الحقوق لدى مستغل المنصة واللجوء إلى الهيئة الوطنية لحماية المعطيات الشخصية.';

  @override
  String get charterRetentionTitle => 'التأمين ومدة الحفظ';

  @override
  String get charterRetentionBody =>
      'تُحفظ البلاغات التي لم تُرسل بعد مشفّرة على هاتفك. وعلى المنصة، لا تُحفظ المعطيات إلا للمدة اللازمة لمعالجة الحالة الطارئة والوفاء بالالتزامات القانونية، ولا يطّلع عليها إلا الأعوان المرخّص لهم.';

  @override
  String get charterLiabilityTitle => 'المسؤولية عن البلاغات الكاذبة';

  @override
  String get charterLiabilityBody =>
      'كل بلاغ يُسخّر فرق نجدة قد تكون في حاجة إليها حالات أخرى. إن تقديم بلاغ كاذب أو إنذار زائف عن قصد يُرتّب مسؤوليتك القانونية ويعرّضك للتتبعات طبقا للقانون التونسي.';

  @override
  String get charterCheckbox =>
      'اطّلعت على الميثاق وأوافق عليه، وأدرك أن البلاغ الكاذب عن قصد يُرتّب مسؤوليتي القانونية.';

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
  String get settingsCharter => 'إعادة قراءة الميثاق';

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
  String get errorConsentRequired => 'يُرجى الموافقة على الميثاق قبل التبليغ.';

  @override
  String get errorRateLimited => 'طلبات كثيرة جدا. يُرجى الانتظار قليلا.';

  @override
  String get errorUnknownCharterVersion => 'تغيّر الميثاق. يُرجى قراءته مجددا.';

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
}
