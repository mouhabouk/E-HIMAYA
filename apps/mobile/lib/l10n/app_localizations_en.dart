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

  @override
  String get errorOrgNotFound =>
      'This institution was not found or you are no longer one of its members.';

  @override
  String get errorOrgNotActive =>
      'This institution is not active (under review, rejected or suspended): it cannot report.';

  @override
  String get errorOrgRoleRequired =>
      'Your role in this institution does not allow this action.';

  @override
  String get reportAsTitle => 'Report as';

  @override
  String get reportAsSelf => 'Myself';

  @override
  String get reportAsInstitutionUnnamed => 'Institution';

  @override
  String get reportOrgRefused => 'Refused for the institution';

  @override
  String get reportOrgNotFoundBody =>
      'This report could not be sent on behalf of the institution: it was not found or you are no longer one of its members. It is kept on this phone. You can send it as yourself.';

  @override
  String get reportOrgNotActiveBody =>
      'This report could not be sent on behalf of the institution because it is not active. It is kept on this phone. You can send it as yourself.';

  @override
  String get reportResendAsSelf => 'Send as myself';

  @override
  String get reportResentAsSelf => 'The report will be sent as yourself.';

  @override
  String get settingsSosReportAs => 'SOS';

  @override
  String get settingsSosReportAsHint => 'The SOS button sends the alert as:';

  @override
  String get myInstitutionTitle => 'My institution';

  @override
  String get myInstitutionsTitle => 'My institutions';

  @override
  String get myInstitutionsEmpty => 'You do not belong to any institution.';

  @override
  String get homeInstitutionDesc =>
      'Safety card, team and reports of your institution';

  @override
  String get orgKindIndustrial => 'Industrial';

  @override
  String get orgKindEducational => 'Educational';

  @override
  String get orgKindHotel => 'Hotel';

  @override
  String get orgKindGovernment => 'Government';

  @override
  String get orgKindPrivate => 'Private';

  @override
  String get orgKindOther => 'Other';

  @override
  String get orgStatusPendingReview => 'Under review';

  @override
  String get orgStatusActive => 'Active';

  @override
  String get orgStatusRejected => 'Rejected';

  @override
  String get orgStatusSuspended => 'Suspended';

  @override
  String get orgFamilyHighRise => 'High-rise building';

  @override
  String get orgFamilyIndustrial => 'Industrial establishment';

  @override
  String get orgFamilyErp => 'Building open to the public';

  @override
  String get orgFamilyWorkplace => 'Workplace';

  @override
  String orgErpCategory(int category) {
    return 'category $category';
  }

  @override
  String get orgTeamRepresentative => 'Representative';

  @override
  String get orgTeamMember => 'Member';

  @override
  String get trainingValid => 'valid';

  @override
  String get trainingExpiring => 'expiring soon';

  @override
  String get trainingExpired => 'expired';

  @override
  String get trainingUnknown => 'unknown';

  @override
  String orgTraining(String status) {
    return 'Training: $status';
  }

  @override
  String get orgCapacity => 'Capacity (maximum number of people)';

  @override
  String get orgAddress => 'Address';

  @override
  String get orgClassification => 'Classification';

  @override
  String get orgClassificationProvisional =>
      'Provisional: computed with thresholds still to be validated by the Civil Protection.';

  @override
  String get orgAlerts => 'Alerts';

  @override
  String orgAlertsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count alerts',
      one: '1 alert',
    );
    return '$_temp0';
  }

  @override
  String get orgNoAlerts => 'No alert';

  @override
  String get orgSafetyTeam => 'Safety team';

  @override
  String get orgTeamEmpty => 'No safety team registered.';

  @override
  String orgCallMember(String name) {
    return 'Call $name';
  }

  @override
  String orgHazmatTitle(int count) {
    return 'Hazardous materials ($count)';
  }

  @override
  String get orgHazmatEmpty => 'No hazardous material registered.';

  @override
  String orgUnNumber(String number) {
    return 'UN $number';
  }

  @override
  String orgOfflineCopy(String date) {
    return 'Offline: copy saved on $date.';
  }

  @override
  String get orgPortalNote =>
      'Detailed editing of the institution (card, team, hazardous materials, documents, certificate) is done on the institutions portal.';

  @override
  String get orgOpenPortal => 'Open the portal';

  @override
  String get orgPortalUnavailable =>
      'The portal could not be opened on this phone.';

  @override
  String get orgRecentReports => 'Recent reports of the institution';

  @override
  String get orgReportsEmpty => 'No report yet.';

  @override
  String orgReportBy(String name) {
    return 'By $name';
  }

  @override
  String get notificationsTitle => 'Notifications';

  @override
  String get activeAlertsTitle => 'Alerts in force';

  @override
  String get activeAlertsNone => 'No alert in force for your area.';

  @override
  String get inboxTitle => 'Messages';

  @override
  String get inboxEmpty => 'No message yet.';

  @override
  String get inboxNoIdentity =>
      'Choose how to use the app to receive messages.';

  @override
  String get inboxLoadMore => 'Show older messages';

  @override
  String get inboxAlertActive => 'Alert in force';

  @override
  String get inboxAlertEnded => 'Alert ended';

  @override
  String get alertTitle => 'Alert';

  @override
  String get alertOpen => 'Open the alert';

  @override
  String alertUntil(String time) {
    return 'Until $time';
  }

  @override
  String alertPublishedAt(String time) {
    return 'Issued $time';
  }

  @override
  String get alertNotActive => 'This alert has ended or was lifted.';

  @override
  String get alertAreaNational => 'Whole country';

  @override
  String get alertAreaZone => 'Zone drawn on the map';

  @override
  String alertAreaGouvernorats(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count gouvernorates',
      one: '1 gouvernorate',
    );
    return '$_temp0';
  }

  @override
  String get severityHigh => 'Red alert';

  @override
  String get severityMedium => 'Orange alert';

  @override
  String get severityLow => 'Yellow alert';

  @override
  String get hazardHeavyRain => 'Heavy rain';

  @override
  String get hazardFlood => 'Flood';

  @override
  String get hazardStorm => 'Storm';

  @override
  String get hazardWind => 'Strong wind';

  @override
  String get hazardHeatWave => 'Heat wave';

  @override
  String get hazardColdWave => 'Cold wave';

  @override
  String get hazardSea => 'Rough sea';

  @override
  String get hazardForestFire => 'Forest fire';

  @override
  String get hazardChemical => 'Chemical hazard';

  @override
  String get hazardOther => 'Other hazard';

  @override
  String get topicActivity => 'Activity';

  @override
  String get topicAwareness => 'Awareness';

  @override
  String get topicTraining => 'Training';

  @override
  String get topicWorldDay => 'World day';

  @override
  String get topicOther => 'Information';

  @override
  String get settingsAlerts => 'Alerts and notifications';

  @override
  String get settingsLocationAlerts => 'Alerts where I am';

  @override
  String get settingsLocationAlertsHelp =>
      'Uses the phone’s approximate position (about 1 km) to send you alerts for the area you are in.';

  @override
  String get channelAlerts => 'Urgent alerts';

  @override
  String get channelAlertsDesc =>
      'Civil Protection alerts and volunteer call-outs.';

  @override
  String get channelGeneral => 'Information';

  @override
  String get channelGeneralDesc =>
      'Follow-up of your reports and information messages.';

  @override
  String get pushSimulationBadge => 'Simulation mode';

  @override
  String get pushSimulationHelp =>
      'Push notifications come from the local simulator, not from Firebase. Nothing is delivered by a real push service.';

  @override
  String get tipsTitle => 'Safety tips';

  @override
  String get tipsIntro =>
      'What to do and what to avoid. Available without connection.';

  @override
  String get tipsDo => 'Do';

  @override
  String get tipsDont => 'Don’t';

  @override
  String get tipEarthquake => 'Earthquake';

  @override
  String get homeTipsDesc => 'The right actions in an emergency, even offline.';

  @override
  String get volunteerTitle => 'Volunteering';

  @override
  String get homeVolunteerDesc =>
      'Join the volunteers and answer call-outs near you.';

  @override
  String get volunteerIntro =>
      'Volunteers help the Civil Protection teams in emergencies, according to their skills. Your application is reviewed before you can be called out.';

  @override
  String get volunteerApply => 'Apply as a volunteer';

  @override
  String get volunteerApplication => 'My application';

  @override
  String get volunteerStatusPending => 'Under review';

  @override
  String get volunteerStatusApproved => 'Approved';

  @override
  String get volunteerStatusRejected => 'Rejected';

  @override
  String get volunteerStatusSuspended => 'Suspended';

  @override
  String get volunteerStatusWithdrawn => 'Withdrawn';

  @override
  String get volunteerPendingHelp =>
      'Your application will be reviewed by the Civil Protection. You will receive an e-mail with the decision.';

  @override
  String get volunteerApprovedHelp =>
      'You can declare yourself ready and receive call-outs near you.';

  @override
  String get volunteerRejectedHelp =>
      'Your application was not accepted. You can correct it and apply again.';

  @override
  String get volunteerSuspendedHelp =>
      'Your volunteering is suspended: you will not receive call-outs.';

  @override
  String get volunteerWithdrawnHelp =>
      'You have withdrawn. You can apply again at any time.';

  @override
  String volunteerReason(String reason) {
    return 'Reason: $reason';
  }

  @override
  String volunteerPeriodFrom(String from) {
    return 'From $from';
  }

  @override
  String volunteerPeriodRange(String from, String to) {
    return 'From $from to $to';
  }

  @override
  String get availabilityContinuous => 'Continuous';

  @override
  String get availabilityIntermittent => 'Intermittent';

  @override
  String get volunteerEdit => 'Edit my application';

  @override
  String get volunteerResubmit => 'Apply again';

  @override
  String get volunteerWithdraw => 'Withdraw';

  @override
  String get volunteerWithdrawConfirm =>
      'You will no longer receive call-outs and your position will no longer be shared.';

  @override
  String get volunteerReady => 'Ready to help';

  @override
  String get volunteerReadyHelp =>
      'While you are ready, the Civil Protection sees your position to call you out.';

  @override
  String volunteerReadyUntil(String time) {
    return 'Ready until $time';
  }

  @override
  String get volunteerReadyFor => 'For';

  @override
  String hoursShort(int hours) {
    return '$hours h';
  }

  @override
  String get volunteerLocationPrivacy =>
      'Your position is shared only while you are ready, is deleted when readiness ends and is never archived.';

  @override
  String get volunteerNoFix =>
      'Your position could not be determined. Try again outdoors.';

  @override
  String get volunteerSkills => 'Skills';

  @override
  String get volunteerSkillsRequired => 'Choose at least one skill.';

  @override
  String get volunteerOtherSkill => 'Other skill';

  @override
  String get volunteerAvailability => 'Availability';

  @override
  String get volunteerPeriod => 'Volunteering period';

  @override
  String get volunteerFrom => 'Start';

  @override
  String get volunteerTo => 'End';

  @override
  String get volunteerNoEnd => 'No end date';

  @override
  String get volunteerNotes => 'Notes (optional)';

  @override
  String get volunteerProfileNote =>
      'Your name, phone and gouvernorate are taken from your profile.';

  @override
  String get volunteerSubmit => 'Send my application';

  @override
  String get volunteerSubmitted => 'Application sent.';

  @override
  String get fieldRequired => 'Required';

  @override
  String get skillFirstAid => 'First aid';

  @override
  String get skillDiving => 'Diving';

  @override
  String get skillHeavyVehicles => 'Heavy vehicles';

  @override
  String get skillFirefighting => 'Firefighting';

  @override
  String get skillSearchRescue => 'Search and rescue';

  @override
  String get skillLogistics => 'Logistics';

  @override
  String get skillMedical => 'Medical';

  @override
  String get skillOther => 'Other';

  @override
  String get calloutsTitle => 'Call-outs';

  @override
  String get calloutsDesc => 'Requests for help near you.';

  @override
  String get calloutsEmpty => 'No call-out at the moment.';

  @override
  String get calloutAccept => 'I’m going';

  @override
  String get calloutDecline => 'Not available';

  @override
  String get calloutArrived => 'I’m on site';

  @override
  String get calloutEtaLabel => 'Arrival in (minutes)';

  @override
  String calloutEta(int minutes) {
    return 'Arrival in $minutes min';
  }

  @override
  String calloutSkill(String skill) {
    return 'Skill: $skill';
  }

  @override
  String calloutDistance(String distance) {
    return 'At $distance';
  }

  @override
  String get calloutAnswerSent => 'Awaiting your answer';

  @override
  String get calloutAnswerAccepted => 'On the way';

  @override
  String get calloutAnswerDeclined => 'Declined';

  @override
  String get calloutAnswerExpired => 'Expired';

  @override
  String get calloutAnswerArrived => 'On site';

  @override
  String distanceMeters(int meters) {
    return '$meters m';
  }

  @override
  String distanceKm(String km) {
    return '$km km';
  }

  @override
  String get errorRegistrationRequired => 'You need an account to volunteer.';

  @override
  String get errorNotVolunteer => 'You have not applied as a volunteer.';

  @override
  String get errorProfileIncomplete =>
      'Complete your profile (phone and gouvernorate) first.';

  @override
  String get errorInvalidPeriod =>
      'The period is invalid (end before start or more than two years ahead).';

  @override
  String get errorVolunteerNotApproved =>
      'Your volunteer application is not approved.';

  @override
  String get errorOutsidePeriod => 'Today is outside your volunteering period.';

  @override
  String get errorNotReady => 'You are no longer ready.';

  @override
  String get errorLocationRequired => 'Your position is needed to be ready.';

  @override
  String get errorCalloutClosed => 'This call-out is closed.';

  @override
  String get errorEtaRequired => 'Enter a time between 1 and 600 minutes.';

  @override
  String get errorInvalidTransition => 'This action is no longer possible.';

  @override
  String get errorVersionConflict =>
      'Your data changed meanwhile. Reload and try again.';

  @override
  String get locationServiceDisabled => 'Location is turned off on this phone.';

  @override
  String get volunteerLocationDenied =>
      'Allow location access to declare yourself ready.';

  @override
  String get actionNotNow => 'Not now';

  @override
  String get channelCritical => 'Critical official alerts';

  @override
  String get channelCriticalDesc =>
      'The most severe alerts of the civil protection, heard even in Do Not Disturb (only if you allowed it).';

  @override
  String get alertCheckTitle => 'Alert delivery check';

  @override
  String get alertCheckSubtitle => 'What could keep alerts from reaching you';

  @override
  String get alertCheckIntro =>
      'Official alerts use their own sound, vibration and channel, separate from other apps. Some phone settings can still silence them: check them here.';

  @override
  String get alertCheckAllGood =>
      'Nothing blocks official alerts on this phone.';

  @override
  String get alertCheckFix => 'Fix';

  @override
  String get alertChannelSettings => 'Alert sound and vibration settings';

  @override
  String get issueNotificationsOff => 'Notifications are turned off';

  @override
  String get issueNotificationsOffHelp =>
      'Without notifications you will not receive alerts or call-outs.';

  @override
  String get issueChannelMuted => 'Official alerts are muted';

  @override
  String get issueChannelMutedHelp =>
      'The “Official alerts” category was lowered in the phone settings: it no longer rings nor pops up.';

  @override
  String get issueDnd => 'Do Not Disturb is on';

  @override
  String get issueDndHelp =>
      'Alerts may arrive silently. You can let the most severe official alerts through.';

  @override
  String get issueFullScreen => 'Full-screen alerts are not allowed';

  @override
  String get issueFullScreenHelp =>
      'The most severe alerts should open over the lock screen. Allow “full-screen notifications” for e-Himaya.';

  @override
  String get issueBatteryOptimized =>
      'Battery optimisation may delay call-outs';

  @override
  String get issueBatteryOptimizedHelp =>
      'You are on call: the phone may put the app to sleep and delay call-outs. Exempt e-Himaya while you volunteer.';

  @override
  String get issuePushUnavailable => 'Push notifications are unavailable';

  @override
  String get issuePushUnavailableHelp =>
      'This phone cannot receive pushes (for example without Google services): alerts are checked only while the app is open.';

  @override
  String get testAlertButton => 'Send a test alert';

  @override
  String get testAlertTitle => 'Test — official alert';

  @override
  String get testAlertBody =>
      'This is what an alert from the civil protection looks and sounds like. No action needed.';

  @override
  String get testAlertSent => 'Test alert sent.';

  @override
  String get criticalAlertsTitle => 'Critical alerts in Do Not Disturb';

  @override
  String get criticalAlertsIntro =>
      'You can let the most severe official alerts (danger to life: flood, fire, evacuation) ring even when Do Not Disturb is on.';

  @override
  String get criticalAlertsHow =>
      'Only alerts of the highest severity use this. The phone will ask you to give e-Himaya “Do Not Disturb access”; you can turn this off here at any time.';

  @override
  String get criticalAlertsEnable => 'Allow critical alerts';

  @override
  String get criticalAlertsEnabled =>
      'Critical alerts can ring in Do Not Disturb.';

  @override
  String get criticalAlertsDisable => 'Turn off';

  @override
  String get batteryExemptTitle => 'Keep call-outs on time';

  @override
  String get batteryExemptBody =>
      'You are on call. To save battery, the phone may put e-Himaya to sleep and deliver call-outs late. Exempting the app from battery optimisation avoids this; e-Himaya itself only uses location while it is open and you are ready.';

  @override
  String get batteryExemptAllow => 'Exempt the app';

  @override
  String get batterySaverTitle => 'Battery saver';

  @override
  String get batterySaverHelp =>
      'Checks less often for updates, shares your volunteer position less often and keeps large videos for Wi-Fi. Alerts and SOS are never delayed.';

  @override
  String get batterySaverAuto => 'Automatic (low battery)';

  @override
  String get batterySaverOn => 'Always on';

  @override
  String get batterySaverOff => 'Off';

  @override
  String get batterySaverActive => 'active';

  @override
  String get batterySaverInactive => 'inactive';

  @override
  String batteryLevel(int percent) {
    return 'battery $percent%';
  }

  @override
  String get pushCalloutTitle => 'Call-out';

  @override
  String get pushOpenToSee => 'Open the app to see the details.';

  @override
  String pushReportTitle(String code) {
    return 'Report $code';
  }

  @override
  String get myDataTitle => 'My data';

  @override
  String get myDataSubtitle => 'Download a copy or delete your account';

  @override
  String get myDataIntro =>
      'You can get a copy of all the personal data e-Himaya holds about you (profile, consents, reports, volunteer record, devices), at most 3 times a day. Keep the file private: it contains personal data.';

  @override
  String get myDataDownload => 'Download my data';

  @override
  String get myDataCopy => 'Copy';

  @override
  String get myDataCopied => 'Copied to the clipboard.';

  @override
  String get myDataSave => 'Save as file';

  @override
  String myDataSaved(String path) {
    return 'Saved: $path';
  }

  @override
  String get myDataSaveFailed => 'The file could not be saved.';

  @override
  String get deleteAccountTitle => 'Delete my account';

  @override
  String get deleteAccountSubtitle =>
      'Your personal data is erased; this cannot be undone.';

  @override
  String get deleteAccountExplain =>
      'Your profile, consents, devices and volunteer record are erased and your account is closed. Reports you sent are kept without your name, as the law requires. Everything stored on this phone is wiped and the app starts again from the beginning.';

  @override
  String get deleteAccountExplainAnonymous =>
      'This phone\'s anonymous identity is deleted on the server. Reports you sent are kept without any link to this phone, as the law requires. Everything stored on this phone is wiped and the app starts again from the beginning.';

  @override
  String get deleteAccountWord => 'DELETE';

  @override
  String deleteAccountTypeWord(String word) {
    return 'Type $word to confirm';
  }

  @override
  String get deleteAccountConfirm => 'Delete permanently';

  @override
  String get deleteAccountDone => 'Your account was deleted.';

  @override
  String get deleteAccountLastAdmin =>
      'You are the last administrator of an institution. Hand the administration over to another member first, then delete your account.';

  @override
  String get lockedAlertOpenApp => 'Unlock to open the app';

  @override
  String get liveBadge => 'LIVE';

  @override
  String get homeLive => 'Go live';

  @override
  String get homeLiveDesc => 'Show the incident live to the Civil Protection.';

  @override
  String get liveTitle => 'Live stream';

  @override
  String get liveIntro =>
      'The camera picture and the microphone sound go live to the Civil Protection operations room, are recorded and linked to your report. Your position is sent for as long as the stream lasts.';

  @override
  String get livePermissionRationale =>
      'Streaming needs the camera, the microphone and your location. Your phone asks for permission when you start; they are used only while streaming.';

  @override
  String get liveCategoryLabel => 'Incident type';

  @override
  String get liveStart => 'Start live';

  @override
  String get liveStop => 'Stop live';

  @override
  String get liveMute => 'Mute microphone';

  @override
  String get liveUnmute => 'Unmute microphone';

  @override
  String get liveSwitchCamera => 'Switch camera';

  @override
  String get livePreparing => 'Preparing the live stream…';

  @override
  String get liveConnecting => 'Connecting to the video server…';

  @override
  String liveReconnecting(int attempt, int max) {
    return 'Connection lost. Attempt $attempt of $max…';
  }

  @override
  String get liveWeakNetwork =>
      'The network is too weak for live video. You can record a short clip and send it instead.';

  @override
  String get liveLocationOff =>
      'Location is off: your position is not sent during the stream.';

  @override
  String get liveLocationOn => 'Position shared while live';

  @override
  String liveEndsIn(String time) {
    return 'The stream stops automatically in $time';
  }

  @override
  String liveReportCode(String code) {
    return 'Report $code';
  }

  @override
  String liveSemanticsOnAir(String duration) {
    return 'Live for $duration';
  }

  @override
  String get liveEndedTitle => 'Live stream ended';

  @override
  String get liveEndedByUser =>
      'You stopped the stream. The recording is kept with your report.';

  @override
  String get liveEndedByOperator =>
      'The operator ended the stream. Thank you, the pictures arrived.';

  @override
  String liveEndedMaxDuration(int minutes) {
    return 'The stream reached its maximum length ($minutes min).';
  }

  @override
  String get liveEndedByServer => 'The platform ended the stream.';

  @override
  String get liveEndedLocked =>
      'The stream stopped because the phone went back to the lock screen.';

  @override
  String liveDuration(String duration) {
    return 'Duration: $duration';
  }

  @override
  String get liveFailedTitle => 'Live stream not possible';

  @override
  String get liveFailNoLocation =>
      'Your position could not be found, so the report cannot be created. Call 198.';

  @override
  String get liveFailReportNotSent =>
      'Your report is saved on the phone and will be sent when the network is back. You can record a clip to attach to it.';

  @override
  String get liveFailPermission =>
      'Camera or microphone access was refused. Allow it in the phone settings to stream.';

  @override
  String get liveFailCamera =>
      'The camera is not available (another app may be using it).';

  @override
  String get liveFailConnection =>
      'The video server could not be reached after several attempts.';

  @override
  String get liveFailLocked =>
      'Live streaming is not available from the alert over the lock screen. Unlock the phone first.';

  @override
  String get liveFallbackTitle => 'Send a video clip instead';

  @override
  String get liveFallbackBody =>
      'Record a clip of up to 60 seconds: it is uploaded automatically with your report, even on a weak network.';

  @override
  String get liveRecordClip => 'Record a clip (60 s)';

  @override
  String get liveClipQueued =>
      'The clip is saved and will be sent with your report.';

  @override
  String get liveClipFailed => 'The clip could not be saved.';

  @override
  String get liveRetry => 'Try again';

  @override
  String get liveOpenSettings => 'Open settings';

  @override
  String get liveDone => 'Done';

  @override
  String get liveLeaveTitle => 'Stop the live stream?';

  @override
  String get liveLeaveBody =>
      'The stream is on. Leaving stops sending the picture and your position.';

  @override
  String get liveSimulationBadge => 'Simulation mode';

  @override
  String get liveSimulationHelp =>
      'This stream goes through the simulation platform and reaches no real operations room.';

  @override
  String get reportGoLive => 'Go live for this report';

  @override
  String get errorStreamAlreadyActive =>
      'A live stream is already running for this report.';

  @override
  String get errorStreamNotActive => 'This live stream is over.';

  @override
  String get errorReportClosed =>
      'This report is closed: a live stream cannot be opened on it.';

  @override
  String get weatherTitle => 'Weather near you';

  @override
  String get weatherLoading => 'Loading the weather…';

  @override
  String get weatherNoLocation =>
      'Allow location access to see the weather where you are.';

  @override
  String get weatherUseLocation => 'Use my location';

  @override
  String get weatherOutsideCoverage =>
      'The weather forecast covers Tunisia only.';

  @override
  String get weatherOffline =>
      'No internet: the weather will be shown when the connection is back.';

  @override
  String get weatherUnavailable => 'The weather could not be loaded.';

  @override
  String get weatherRetry => 'Retry';

  @override
  String get weatherNotRefreshed =>
      'Not refreshed: showing the last data received.';

  @override
  String weatherUpdated(String time) {
    return 'Updated $time';
  }

  @override
  String weatherCachedAt(String time) {
    return 'Offline copy from $time';
  }

  @override
  String get weatherNow => 'Now';

  @override
  String get weatherNextHours => 'Next hours';

  @override
  String weatherTemperature(String value) {
    return '$value °C';
  }

  @override
  String weatherWind(String speed) {
    return 'Wind $speed km/h';
  }

  @override
  String weatherGusts(String speed) {
    return 'gusts $speed km/h';
  }

  @override
  String weatherHumidity(String value) {
    return 'Humidity $value%';
  }

  @override
  String weatherRain(String value) {
    return 'Rain $value mm/h';
  }

  @override
  String weatherRain24h(String value) {
    return '$value mm over 24 h';
  }

  @override
  String weatherFireDanger(String level) {
    return 'Fire danger: $level';
  }

  @override
  String get weatherFireLow => 'low';

  @override
  String get weatherFireModerate => 'moderate';

  @override
  String get weatherFireHigh => 'high';

  @override
  String get weatherFireVeryHigh => 'very high';

  @override
  String get weatherFireExtreme => 'extreme';

  @override
  String weatherHeavyRain(String level) {
    return 'Heavy rain: $level';
  }

  @override
  String get weatherRainWatch => 'watch';

  @override
  String get weatherRainWarning => 'warning';

  @override
  String get weatherCondClear => 'Clear sky';

  @override
  String get weatherCondCloudy => 'Cloudy';

  @override
  String get weatherCondFog => 'Fog';

  @override
  String get weatherCondRain => 'Rain';

  @override
  String get weatherCondSnow => 'Snow';

  @override
  String get weatherCondStorm => 'Thunderstorm';

  @override
  String get weatherAlertsTitle => 'Weather alerts in force';

  @override
  String weatherSource(String source) {
    return 'Data: $source';
  }

  @override
  String get weatherSimulationBadge => 'Simulation mode';

  @override
  String get weatherSimulationHelp =>
      'These weather values are simulated, not real measurements.';

  @override
  String get offlineFallbackTitle => 'No internet connection';

  @override
  String get offlineFallbackBody =>
      'Your report is saved on the phone and will be sent automatically when the internet is back. To alert the civil protection now:';

  @override
  String get offlineSendSms => 'Send by SMS';

  @override
  String get offlineSmsHelp =>
      'Opens your SMS app with a short message (type and position of the report). You press Send yourself.';

  @override
  String get offlineSmsFee =>
      'Your operator may charge the price of a standard SMS.';

  @override
  String get offlineSmsFailed => 'The SMS app could not be opened. Call 198.';

  @override
  String get rewardsTitle => 'My rewards';

  @override
  String get homeRewardsDesc =>
      'Points, badges and certificates earned by useful reports.';

  @override
  String get rewardsBalanceLabel => 'Points balance';

  @override
  String get rewardsNoBadge => 'No badge yet';

  @override
  String rewardsCurrentBadge(String badge) {
    return 'Current badge: $badge';
  }

  @override
  String rewardsNextBadge(String badge, int points) {
    return 'Next badge, $badge: $points points to go';
  }

  @override
  String get rewardsTopBadge =>
      'You hold the highest badge. Thank you for your vigilance.';

  @override
  String get rewardsConfirmNote =>
      'Silver, gold and ambassador badges appear once a civil protection officer has confirmed them.';

  @override
  String get badgeBronze => 'Bronze';

  @override
  String get badgeSilver => 'Silver';

  @override
  String get badgeGold => 'Gold';

  @override
  String get badgeAmbassador => 'Ambassador';

  @override
  String get rewardsPausedTitle => 'Points paused';

  @override
  String get rewardsPausedBody =>
      'A disaster level is in force. New points are kept and will be added when the level drops.';

  @override
  String rewardsPendingPoints(int points) {
    return 'Points waiting: $points';
  }

  @override
  String get rewardsHistoryTitle => 'History';

  @override
  String get rewardsHistoryEmpty =>
      'No points yet. Points are added when a report you sent is verified and closed.';

  @override
  String get rewardsShowMore => 'Show more';

  @override
  String get pointsReasonReportVerified => 'Verified report';

  @override
  String get pointsReasonHelpedRescue => 'Report that helped a rescue';

  @override
  String get pointsReasonAccurateCategory => 'Right category chosen';

  @override
  String get pointsReasonVolunteerMission => 'Volunteer mission completed';

  @override
  String get pointsReasonManual => 'Adjustment by the civil protection';

  @override
  String get pointsReasonRevocation => 'Points withdrawn';

  @override
  String get pointsReasonOther => 'Other';

  @override
  String get rewardsCapped => 'daily limit reached';

  @override
  String rewardsDailyCap(int points) {
    return 'At most $points points can be earned per day.';
  }

  @override
  String get rewardsCertificatesTitle => 'Certificates';

  @override
  String get rewardsCertificatesEmpty => 'No certificate yet.';

  @override
  String rewardsCertificateYear(String year) {
    return 'Year $year';
  }

  @override
  String get distinctionVigilantCitizen => 'Vigilant citizen';

  @override
  String get distinctionBraveVolunteer => 'Brave volunteer';

  @override
  String get distinctionLeadingInstitution => 'Leading institution';

  @override
  String distinctionBadge(String badge) {
    return '$badge badge';
  }

  @override
  String get distinctionOther => 'Distinction';

  @override
  String get rewardsOpenPdf => 'Open the PDF certificate';

  @override
  String get rewardsPdfNoViewer => 'No app on this phone can open the PDF.';

  @override
  String get rewardsAnonymousTitle => 'Anonymous reports earn no points';

  @override
  String get rewardsAnonymousBody =>
      'A report sent without an account cannot be linked to a person, so it earns no points, badges or certificates. Create an account to take part; reports already sent anonymously stay anonymous.';

  @override
  String get rewardsSafetyNotice =>
      'Never put yourself in danger to report. Your safety comes first: in an emergency, call 198.';

  @override
  String get rewardsPrizesNotice =>
      'Points, badges and certificates are a public recognition, not money. Any annual prize is subject to a decision of the competent authority.';

  @override
  String rewardsOfflineCopy(String date) {
    return 'Offline: copy saved on $date.';
  }

  @override
  String get rewardsHowTitle => 'How to earn points';

  @override
  String get rewardsHowBody =>
      'Points are added when a report you sent is verified and closed, with more when it helped a rescue or when you chose the right category, and for each volunteer mission completed. No points are given for false or rejected reports.';

  @override
  String trackPointsEarned(int points) {
    return 'Points earned by this report: $points';
  }

  @override
  String get trackPointsOpenRewards => 'See my rewards';

  @override
  String get anonQuotaCardTitle => 'Reports without an account';

  @override
  String anonQuotaRemaining(int remaining, int limit) {
    return '$remaining of $limit left';
  }

  @override
  String anonQuotaRemainingShort(int remaining) {
    return '$remaining left';
  }

  @override
  String get anonQuotaExhaustedHint =>
      'Limit reached: create an account to keep reporting. SOS and 198 always work.';

  @override
  String get anonQuotaTitle => 'Reporting without an account';

  @override
  String get anonQuotaExplanation =>
      'To prevent abuse, each installation of the app can send a limited number of reports without an account. With a free account you can keep reporting, follow your reports on any device, and your reports carry more weight.';

  @override
  String get anonQuotaEmergencyNote =>
      'In an emergency, the SOS button and a call to 198 always work, with or without an account.';

  @override
  String anonQuotaDraftKept(String code) {
    return 'Your report $code is kept on this phone. It will be sent as soon as you create an account or sign in.';
  }

  @override
  String get anonQuotaReportKeptBody =>
      'The limit of reports without an account is reached. This report is kept on this phone and will be sent as soon as you create an account or sign in.';

  @override
  String get anonQuotaOpen => 'Why a limit?';

  @override
  String get errorAnonQuotaExhausted =>
      'The limit of reports without an account is reached on this device. Please create an account.';
}
