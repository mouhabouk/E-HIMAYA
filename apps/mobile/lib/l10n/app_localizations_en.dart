// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'e-Himaya';

  @override
  String get actionContinue => 'Continue';

  @override
  String get actionCancel => 'Cancel';

  @override
  String get actionSave => 'Save';

  @override
  String get actionLater => 'Later';

  @override
  String get actionRetry => 'Retry';

  @override
  String get copied => 'Tracking code copied.';

  @override
  String get copyTrackingCode => 'Copy tracking code';

  @override
  String callNumber(String number) {
    return 'Call $number';
  }

  @override
  String get charterTitle => 'Privacy & personal data charter';

  @override
  String charterVersionLabel(String version) {
    return 'Version $version';
  }

  @override
  String get charterIntro =>
      'e-Himaya is the national platform for reporting emergencies to the Civil Protection. Before using it, please read how your data is handled and what your obligations are.';

  @override
  String get charterDataTitle => 'Data we collect and why';

  @override
  String get charterDataBody =>
      'For each report: its category, your description, the position of the incident and the photos, videos or voice messages you attach. If you create an account: your name, national ID card (CIN) number, phone number and region. This data is used only to handle emergencies and to inform you of the follow-up of your reports.';

  @override
  String get charterLawTitle => 'Legal framework';

  @override
  String get charterLawBody =>
      'Your personal data is processed in accordance with Organic Law No. 2004-63 of 27 July 2004 on the protection of personal data and its implementing texts, under the supervision of the National Authority for the Protection of Personal Data (INPDP).';

  @override
  String get charterAnonymousTitle => 'Reporting without an account';

  @override
  String get charterAnonymousBody =>
      'You may report without an account. The app then uses a random key created on this phone; the platform keeps only a pseudonym derived from it and does not store your IP address. Anonymous reporting from a device can be suspended after confirmed false reports.';

  @override
  String get charterRightsTitle => 'Your rights';

  @override
  String get charterRightsBody =>
      'You have the right to access, rectify and object to the processing of your data under the conditions set by law. You can exercise these rights with the platform operator and refer the matter to the INPDP.';

  @override
  String get charterRetentionTitle => 'Security and retention';

  @override
  String get charterRetentionBody =>
      'Reports waiting to be sent are stored encrypted on your phone. On the platform, data is kept only as long as needed to handle the emergency and to meet legal obligations, and is accessible only to authorised staff.';

  @override
  String get charterLiabilityTitle => 'Responsibility for false reports';

  @override
  String get charterLiabilityBody =>
      'Every report mobilises rescue teams that may be needed elsewhere. Knowingly making a false report or a false alert engages your legal liability and exposes you to prosecution under Tunisian law.';

  @override
  String get charterCheckbox =>
      'I have read and accept the charter, and I understand that a knowingly false report engages my legal liability.';

  @override
  String charterAcceptedOn(String date) {
    return 'Accepted on $date';
  }

  @override
  String get roleTitle => 'Who are you?';

  @override
  String get roleCitizen => 'Citizen';

  @override
  String get roleCitizenDesc =>
      'Report an emergency, send an SOS and follow your reports.';

  @override
  String get roleInstitution => 'Institution';

  @override
  String get roleInstitutionDesc =>
      'Public or private institution with a registered account.';

  @override
  String get institutionTitle => 'Institutions';

  @override
  String get institutionBody =>
      'Registration is mandatory for institutions and is done through the institutions portal, not in this app. If your institution already has an account, sign in below.';

  @override
  String get institutionLogin => 'Sign in';

  @override
  String get citizenModeTitle => 'How do you want to report?';

  @override
  String get citizenAnonymous => 'Continue without an account';

  @override
  String get citizenAnonymousDesc =>
      'Fastest. No personal information is asked.';

  @override
  String get citizenRegister => 'Create an account';

  @override
  String get citizenRegisterDesc =>
      'Follow your reports on any device; your reports carry more weight.';

  @override
  String get citizenLogin => 'I already have an account';

  @override
  String get citizenLoginDesc => 'Sign in with your e-Himaya account.';

  @override
  String get changeRole => 'Change role';

  @override
  String get loginCancelled => 'Sign-in cancelled.';

  @override
  String get loginFailed =>
      'Sign-in failed. Check your connection and try again.';

  @override
  String get profileTitle => 'Complete your profile';

  @override
  String get profileIntro =>
      'This information will be used to verify your reports. You can complete it later from the settings.';

  @override
  String get profileFirstName => 'First name';

  @override
  String get profileLastName => 'Last name';

  @override
  String get profileCin => 'National ID card (CIN) number';

  @override
  String get profileCinHint => '8 digits';

  @override
  String profileCinStored(String last4) {
    return 'Saved CIN ends with $last4; enter it again to save changes.';
  }

  @override
  String get profilePhone => 'Phone number';

  @override
  String get profileGouvernorat => 'Gouvernorat';

  @override
  String get profileDelegation => 'Délégation';

  @override
  String get profileAddress => 'Address (optional)';

  @override
  String get profileSaved => 'Profile saved.';

  @override
  String get validationRequired => 'Required.';

  @override
  String get validationCin => 'The CIN has exactly 8 digits.';

  @override
  String get validationPhone => 'Enter the 8 digits after +216.';

  @override
  String get geoLoadFailed => 'Could not load the list.';

  @override
  String get navHome => 'Home';

  @override
  String get navReports => 'My reports';

  @override
  String get navSettings => 'Settings';

  @override
  String get homeTagline => 'In an emergency, every second counts.';

  @override
  String get homeNewReport => 'New report';

  @override
  String get homeNewReportDesc =>
      'Fire, flood, accident… with photos, video or voice.';

  @override
  String get homeEmergencyDesc =>
      'Call 198, 190, 197 or 193 directly, even offline.';

  @override
  String get homeTrackDesc => 'Follow a report with its tracking code.';

  @override
  String pendingSyncBanner(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count reports waiting to be sent',
      one: '1 report waiting to be sent',
    );
    return '$_temp0';
  }

  @override
  String get sosButtonLabel => 'SOS';

  @override
  String get sosHint => 'Tap twice or hold to send your position.';

  @override
  String get sosArmed => 'Tap again to send the SOS.';

  @override
  String get sosSending => 'Sending SOS…';

  @override
  String get sosConfirmTitle => 'Send an SOS?';

  @override
  String get sosConfirmBody =>
      'Your current position will be sent to the Civil Protection.';

  @override
  String get sosConfirmAction => 'Send SOS';

  @override
  String get sosNoLocation =>
      'Your position is not available. Enable location, or call the Civil Protection.';

  @override
  String get sosQueuedTitle => 'SOS saved';

  @override
  String get anonBlockedBody =>
      'Reporting without an account is suspended on this device. Create an account to keep reporting.';

  @override
  String get emergencyTitle => 'Emergency numbers';

  @override
  String get emergencyIntro =>
      'Calls go directly through your SIM card, even without internet.';

  @override
  String get emergencyCivilProtection => 'Civil Protection';

  @override
  String get emergencySamu => 'Emergency medical service (SAMU)';

  @override
  String get emergencyPolice => 'Police emergency';

  @override
  String get emergencyNationalGuard => 'National Guard';

  @override
  String emergencyCallSemantics(String name, String number) {
    return 'Call $name, $number';
  }

  @override
  String get dialFailed => 'This device cannot place calls.';

  @override
  String get categorySos => 'SOS';

  @override
  String get categoryFire => 'Fire';

  @override
  String get categoryFlood => 'Flood';

  @override
  String get categoryTrafficAccident => 'Traffic accident';

  @override
  String get categoryDrowning => 'Drowning';

  @override
  String get categoryLandslide => 'Landslide';

  @override
  String get categoryChemicalLeak => 'Chemical leak';

  @override
  String get categoryMedical => 'Medical emergency';

  @override
  String get categoryOther => 'Other';

  @override
  String get statusReceived => 'Received';

  @override
  String get statusInProgress => 'Being processed';

  @override
  String get statusIntervened => 'Intervened';

  @override
  String get statusOngoing => 'Intervention ongoing';

  @override
  String get statusClosed => 'Closed';

  @override
  String get statusRejected => 'Rejected';

  @override
  String get statusUnknown => 'Unknown status';

  @override
  String get newReportTitle => 'New report';

  @override
  String get chooseCategory => 'What is happening?';

  @override
  String get reportLocation => 'Location';

  @override
  String get locationLocating => 'Locating…';

  @override
  String locationAccuracy(int meters) {
    return 'Position found, accuracy ±$meters m';
  }

  @override
  String get locationManual => 'Position set on the map';

  @override
  String get locationAdjustHint =>
      'Move the map to place the pin exactly on the incident.';

  @override
  String get locationUnavailable =>
      'No GPS position yet. Place the pin on the map or try again.';

  @override
  String get locationPermissionDenied =>
      'Location is off or not allowed. Place the pin on the map.';

  @override
  String get locationOutsideTunisia => 'The location must be in Tunisia.';

  @override
  String get locationRefresh => 'Use my position';

  @override
  String get mapPinSemantics => 'Report location pin';

  @override
  String get reportDescription => 'Description (optional)';

  @override
  String get reportDescriptionHint =>
      'What do you see? Are there injured people?';

  @override
  String get reportAttachments => 'Photos, videos and voice message';

  @override
  String get attachTakePhoto => 'Take a photo';

  @override
  String get attachPickPhoto => 'Photo gallery';

  @override
  String get attachRecordVideo => 'Record a video';

  @override
  String get attachPickVideo => 'Choose a video';

  @override
  String attachmentPhoto(int n) {
    return 'Photo $n';
  }

  @override
  String attachmentVideo(int n) {
    return 'Video $n';
  }

  @override
  String attachmentTooLarge(int maxMb) {
    return 'This file is too large (maximum $maxMb MB).';
  }

  @override
  String get attachmentUnsupported => 'This file format is not accepted.';

  @override
  String attachmentLimit(int max) {
    return 'At most $max files per report.';
  }

  @override
  String get removeAttachment => 'Remove attachment';

  @override
  String get pickerFailed => 'Could not open the camera or the gallery.';

  @override
  String get audioTitle => 'Voice message';

  @override
  String get audioMaxDuration => '5 minutes max.';

  @override
  String get audioRecord => 'Record';

  @override
  String get audioStop => 'Stop';

  @override
  String get audioPlay => 'Play the recording';

  @override
  String get audioPause => 'Pause';

  @override
  String get audioReRecord => 'Record again';

  @override
  String get audioDelete => 'Delete the recording';

  @override
  String audioRecording(String duration) {
    return 'Recording… $duration';
  }

  @override
  String get audioPermissionDenied => 'Microphone access was refused.';

  @override
  String get audioFailed => 'The recording could not start.';

  @override
  String get reportSubmit => 'Send report';

  @override
  String get reportNeedsLocation =>
      'Wait for your position or place the pin on the map.';

  @override
  String get reportOfflineNote =>
      'Without network, the report is saved encrypted on the phone and sent automatically later.';

  @override
  String get reportSaveFailed => 'The report could not be saved. Try again.';

  @override
  String get reportQueuedTitle => 'Report saved';

  @override
  String get reportTempCodeLabel => 'Temporary code';

  @override
  String get reportQueuedBody =>
      'Keep this code. It will be replaced by the final tracking code as soon as the Civil Protection receives your report.';

  @override
  String get reportReceivedBody =>
      'Your report was received by the Civil Protection. Use this code to follow it.';

  @override
  String get reportBackHome => 'Back to home';

  @override
  String get temporaryCodeNote => 'Temporary code, waiting to be sent';

  @override
  String get myReportsTitle => 'My reports';

  @override
  String get myReportsEmpty => 'No reports yet.';

  @override
  String get myReportsOffline => 'Could not refresh from the server.';

  @override
  String get reportPendingSync => 'Waiting to be sent';

  @override
  String get reportConflict => 'Server version kept';

  @override
  String get reportFailed => 'Not accepted';

  @override
  String get reportBlocked => 'Account required';

  @override
  String reportUploadingMedia(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count attachments being sent',
      one: '1 attachment being sent',
    );
    return '$_temp0';
  }

  @override
  String reportMediaRejected(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count attachments refused',
      one: '1 attachment refused',
    );
    return '$_temp0';
  }

  @override
  String get trackTitle => 'Track a report';

  @override
  String get trackingCodeLabel => 'Tracking code';

  @override
  String get trackHint => 'EH-26-61-0004821';

  @override
  String get trackAction => 'Track';

  @override
  String get trackInvalid => 'Enter a code like EH-26-61-0004821.';

  @override
  String get trackHistory => 'History';

  @override
  String receivedAt(String date) {
    return 'Received on $date';
  }

  @override
  String get settingsTitle => 'Settings';

  @override
  String get settingsLanguage => 'Language';

  @override
  String get languageArabic => 'العربية';

  @override
  String get languageFrench => 'Français';

  @override
  String get languageEnglish => 'English';

  @override
  String get settingsTheme => 'Appearance';

  @override
  String get themeSystem => 'Same as the phone';

  @override
  String get themeLight => 'Light';

  @override
  String get themeDark => 'Dark';

  @override
  String get settingsIdentity => 'Identity';

  @override
  String get identityAnonymous => 'Without account (this device)';

  @override
  String get identityRegistered => 'Signed in';

  @override
  String identityRegisteredAs(String name) {
    return 'Signed in as $name';
  }

  @override
  String get identityNone => 'Not signed in';

  @override
  String get settingsRegister => 'Create an account';

  @override
  String get settingsProfile => 'My profile';

  @override
  String get settingsLogout => 'Sign out';

  @override
  String get logoutConfirmTitle => 'Sign out?';

  @override
  String get logoutConfirmBody =>
      'Reports waiting to be sent stay on this phone and will be sent after you sign in again or choose to continue without an account.';

  @override
  String get settingsCharter => 'Read the charter again';

  @override
  String get errorAuthenticationRequired =>
      'Your session has expired. Please sign in again.';

  @override
  String get errorInvalidDeviceKey =>
      'This device could not be identified. Restart the app.';

  @override
  String get errorAnonBlocked =>
      'Reporting without an account is suspended on this device. Please create an account.';

  @override
  String get errorAccountSuspended => 'Your account is suspended.';

  @override
  String get errorConsentRequired =>
      'Please accept the charter before reporting.';

  @override
  String get errorRateLimited => 'Too many requests. Please wait a moment.';

  @override
  String get errorUnknownCharterVersion =>
      'The charter has changed. Please read it again.';

  @override
  String get errorClientUuidConflict =>
      'This report conflicts with another one on the server.';

  @override
  String get errorNotFound => 'Not found. Check the code.';

  @override
  String get errorValidation => 'Some information is invalid.';

  @override
  String get errorNetwork =>
      'No connection to the server. It will be retried automatically.';

  @override
  String get errorServer => 'The service is temporarily unavailable.';

  @override
  String get errorUnknown => 'Something went wrong.';

  @override
  String get errorMediaRefused => 'The attachment was refused.';

  @override
  String get errorMediaTooLarge => 'The attachment is too large.';

  @override
  String get errorUnsupportedMediaType =>
      'This attachment format is not accepted.';

  @override
  String get errorTooManyMedia =>
      'This report already has the maximum number of attachments.';

  @override
  String get errorUploadWindowClosed =>
      'Attachments can only be added within 24 hours of the report.';

  @override
  String get errorMediaRejected =>
      'The attachment was damaged in transfer and was refused.';
}
