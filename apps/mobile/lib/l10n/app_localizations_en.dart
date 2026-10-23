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
  String get charterTitle => 'Terms of use';

  @override
  String charterVersionLabel(String version) {
    return 'Version $version';
  }

  @override
  String get charterIntro =>
      'e-Himaya is the national platform for reporting emergencies to the Civil Protection. Before using it, please read how your data is handled and what your obligations are.';

  @override
  String get charterCheckbox =>
      'I have read and accept the terms of use, and I understand that a deliberate false report makes me legally liable.';

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
  String get settingsCharter => 'Terms of use';

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
      'Please accept the terms of use before reporting.';

  @override
  String get errorRateLimited => 'Too many requests. Please wait a moment.';

  @override
  String get errorUnknownCharterVersion =>
      'The terms of use have changed. Please read them again.';

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
  String get locationConsentTitle => 'Share your position while ready?';

  @override
  String get locationConsentBody =>
      'While you are ready, your position is sent to the Civil Protection of your gouvernorat so that it can call out the volunteers closest to an incident.\n\n• Who sees it: Civil Protection operators, on a map rounded to about 100 m; distances are rounded too.\n• How long: only while you are ready. It is kept in memory, deleted when readiness ends and never archived.\n• You can withdraw this consent at any time in this screen; readiness then ends at once.';

  @override
  String get locationConsentAccept => 'I agree';

  @override
  String get locationConsentSwitch => 'Share my position while ready';

  @override
  String get locationConsentSwitchOn =>
      'Consent given. Turning it off ends readiness and deletes your position.';

  @override
  String get locationConsentSwitchOff => 'Required to be ready.';

  @override
  String get locationConsentWithdrawn =>
      'Consent withdrawn: your position is deleted.';

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
  String get errorLocationConsentRequired =>
      'Agree to share your position before being ready.';

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

  @override
  String get intro1Title => 'Welcome to e-Himaya';

  @override
  String get intro1Body =>
      'e-Himaya finds your position from your phone. In an emergency it sends it with your report straight to the competent Civil Protection operations room, so help reaches you faster and with the right resources.';

  @override
  String get intro2Title => 'Run by the National Civil Protection Office';

  @override
  String get intro2Body =>
      'This app is provided by the National Civil Protection Office, the public body in charge of rescue, firefighting and disaster response across Tunisia, which answers the 198 emergency line.';

  @override
  String get intro3Title => 'When should I use it?';

  @override
  String get intro3Body =>
      'Fire, road accident, a person in danger or injured, drowning, collapse, gas leak, flood, or any situation that threatens lives or property and needs Civil Protection.';

  @override
  String get intro4Title => 'How does it work?';

  @override
  String get intro4Body =>
      'Choose the type of incident, add a photo, video or voice message if you can do so safely, and send. Your report and position reach the operator at once; you can follow it step by step and the operator may call you back. Without internet the report goes by SMS, and calling 198 is always available.';

  @override
  String get intro5Title => 'Where does it work?';

  @override
  String get intro5Body =>
      'Throughout the Republic of Tunisia, in all 24 governorates; your report is routed automatically to the competent regional directorate. Outside Tunisia, call the local emergency number (112 in most countries).';

  @override
  String get terms1Title => '1. Purpose';

  @override
  String get terms1Body =>
      'e-Himaya is a digital platform of the National Civil Protection Office (\"the Office\") for reporting emergencies and following them up. These terms govern the relationship between the Office and the users of the mobile app and the institutions portal.';

  @override
  String get terms2Title => '2. Our mission';

  @override
  String get terms2Body =>
      'To protect lives and property, and to rebuild trust between citizens and Civil Protection through direct and open communication. Describing the incident accurately and showing the scene as it is shortens response time and makes the intervention more effective.';

  @override
  String get terms3Title => '3. Nature and limits of the service';

  @override
  String get terms3Body =>
      '3.1 The app complements 198 and does not replace it. In immediate danger, call 198 directly.\n3.2 The app gives no medical advice; its safety tips are for general awareness and do not replace the instructions of Civil Protection staff.\n3.3 It depends on factors outside the Office\'s control: mobile network and internet coverage, location signal, battery and the condition of the phone. The Office aims for the highest availability and fixes faults as fast as possible.';

  @override
  String get terms4Title => '4. User obligations';

  @override
  String get terms4Body =>
      '4.1 Use the app in good faith and only for real emergencies; give accurate, up-to-date information, especially your phone number.\n4.2 Keep location turned on and use the latest version of the app.\n4.3 Do not put yourself in danger to film, and follow the instructions of responders.\n4.4 Do not harm, disrupt, bypass the protections of, or reverse-engineer the app.';

  @override
  String get terms5Title => '5. False alarms and misuse';

  @override
  String get terms5Body =>
      'Every report sends out rescue teams that other lives may need at the same moment. A deliberate false report or any misuse of the app exposes its author to prosecution under Tunisian law, and may lead to temporary or permanent suspension of the account or of reporting from the device concerned.';

  @override
  String get terms6Title => '6. Institutions\' obligations';

  @override
  String get terms6Body =>
      'A registered institution provides accurate, up-to-date information on its identity, activity, buildings and managers, and is responsible for it. Filing and updating the evacuation plan and building plans makes the intervention easier and shortens search and rescue inside the building. The account is activated only after the Office approves it.';

  @override
  String get terms7Title => '7. Volunteers';

  @override
  String get terms7Body =>
      'Volunteer status is granted only after the Office approves it. Volunteers follow the operations room\'s instructions and act only within the task assigned to them.';

  @override
  String get terms8Title => '8. Personal data protection';

  @override
  String get terms8Body =>
      '8.1 Personal data is processed under Organic Law No. 2004-63 of 27 July 2004 on the protection of personal data, under the supervision of the National Authority for the Protection of Personal Data (INPDP), solely to handle emergencies and to keep you informed about your reports.\n8.2 When you send a report, the Office receives your position, the type of incident, the description and attached media, and your account details if you have an account.\n8.3 Emergency contacts and the text of your SOS message are stored encrypted on your phone only and are never sent to the Office.\n8.4 You can report without an account under a pseudonym; your IP address is not recorded.\n8.5 Only authorised staff can access the data, which is kept as long as needed to handle the case and meet legal obligations. You have the right to access, correct and object to the processing of your data.';

  @override
  String get terms9Title => '9. Changes to the app and these terms';

  @override
  String get terms9Body =>
      'The Office may improve the app or change these terms. You are told about each new version and what it contains, and asked to accept again when the terms change.';

  @override
  String get terms10Title => '10. Applicable law';

  @override
  String get terms10Body =>
      'These terms are governed by Tunisian law; Tunisian courts have jurisdiction over any dispute.';

  @override
  String get languageTitle => 'Choose your language';

  @override
  String get languageSubtitle =>
      'You can change it at any time from the language bar at the top of every screen.';

  @override
  String get languageMenuTooltip => 'Language';

  @override
  String get introSkip => 'Skip';

  @override
  String introPage(int current, int total) {
    return 'Page $current of $total';
  }

  @override
  String get call198 => 'Call 198';

  @override
  String get termsScrollHint =>
      'Scroll to the end of the terms to accept them.';

  @override
  String get termsAccept => 'I accept';

  @override
  String get termsDecline => 'I decline';

  @override
  String get termsDeclinedTitle => 'Terms not accepted';

  @override
  String get termsDeclinedBody =>
      'Without accepting the terms you cannot use the app, but calling 198 is always available.';

  @override
  String get termsReadAgain => 'Read the terms';

  @override
  String get permissionsTitle => 'Permissions';

  @override
  String get permissionsIntro =>
      'e-Himaya asks only for what it needs to help you. You can change these choices later in your phone settings.';

  @override
  String get permLocationTitle => 'Location';

  @override
  String get permLocationBody =>
      'Sent with your report so help finds you. Without it you must describe the place and help may take longer.';

  @override
  String get permNotificationsTitle => 'Notifications';

  @override
  String get permNotificationsBody =>
      'Follow-up of your reports and public alerts near you. Without them you will not be warned of a danger in your area.';

  @override
  String get permSmsTitle => 'SMS';

  @override
  String get permSmsBody =>
      'Without internet your report leaves by SMS. No permission is needed: the app opens a ready message that you send yourself.';

  @override
  String get permContactsTitle => 'Contacts';

  @override
  String get permContactsBody =>
      'Asked only when you choose an emergency contact, later.';

  @override
  String get permAllow => 'Allow';

  @override
  String get permAllowed => 'Allowed';

  @override
  String get permRefused => 'Refused: you can allow it in the phone settings';

  @override
  String get permNoneNeeded => 'No permission needed';

  @override
  String get permLater => 'Later';

  @override
  String get signInTitle => 'Sign in';

  @override
  String get signInIntro =>
      'Sign in with your mobile number: we send you a code by SMS. No password.';

  @override
  String get signInPhoneLabel => 'Mobile number';

  @override
  String get signInPhoneHint => '8 digits';

  @override
  String get signInPhoneInvalid =>
      'Enter a Tunisian mobile number: 8 digits starting with 2, 3, 4, 5 or 9.';

  @override
  String get signInSendCode => 'Send the code';

  @override
  String get signInCodeLabel => 'Code received by SMS';

  @override
  String signInCodeSentTo(String phone) {
    return 'A 6-digit code was sent to $phone.';
  }

  @override
  String get signInVerify => 'Sign in';

  @override
  String signInResendIn(int seconds) {
    return 'Resend the code in $seconds s';
  }

  @override
  String get signInResend => 'Resend the code';

  @override
  String get signInChangeNumber => 'Change the number';

  @override
  String signInWrongCode(int tries) {
    return 'Wrong code. Tries left: $tries.';
  }

  @override
  String get signInCodeExpired =>
      'The code expired or was used up. Ask for a new one.';

  @override
  String get signInTooSoon =>
      'Please wait a minute before asking for a new code.';

  @override
  String get signInLimit =>
      'Too many codes for this number. Try again in an hour.';

  @override
  String get signInSmsUnavailable =>
      'The SMS could not be sent. Try again, or continue as a guest.';

  @override
  String get signInNetworkError =>
      'No connection. Check your internet and try again.';

  @override
  String get signInGuest => 'Continue as a guest';

  @override
  String get signInGuestDesc =>
      'Report without an account (a limited number of reports).';

  @override
  String get signInInstitution => 'Institution account';

  @override
  String get signInInstitutionDesc =>
      'For companies, schools, hotels and administrations.';

  @override
  String get signInEmail => 'Sign in with e-mail and password';

  @override
  String get signInPrivacyNote =>
      'Your number is used only to reach you about your reports.';

  @override
  String get simBanner =>
      '[SIM] Simulation: the SMS goes to the test gateway (notify-sim), not to a real phone.';

  @override
  String get homeSubtitle => 'Tunisian Civil Protection';

  @override
  String get homeReportCardTitle => 'Report an incident';

  @override
  String get homeReportCardDesc =>
      'Photo, voice or text, with your position automatically';

  @override
  String get homeNumbersOffline => 'Work without internet';

  @override
  String get homeShortcuts => 'Shortcuts';

  @override
  String get homeMyReports => 'My reports';

  @override
  String get homeSosMessage => 'SOS message';

  @override
  String get homeCall198 => 'Emergency call 198';

  @override
  String get locationOn => 'Location on';

  @override
  String get locationOff =>
      'Location is off: help may take longer to find you.';

  @override
  String get locationTurnOn => 'Turn on';

  @override
  String get locationChecking => 'Checking location…';

  @override
  String get themeToggleTooltip => 'Light or dark';

  @override
  String get settingsColors => 'Colours';

  @override
  String get colorOffice => 'Civil Protection (logo)';

  @override
  String get colorRed => 'Red';

  @override
  String get colorBlue => 'Blue';

  @override
  String get colorGreen => 'Green';

  @override
  String get updateTitle => 'A new version is available';

  @override
  String get updateMandatoryTitle => 'Update required';

  @override
  String get updateMandatoryBody =>
      'This version is no longer supported. Update to keep using e-Himaya. Emergency numbers stay available.';

  @override
  String updateWhatsNew(String version) {
    return 'What\'s new in $version';
  }

  @override
  String get updateDataKept => 'Your reports and settings are kept.';

  @override
  String get updateNow => 'Update';

  @override
  String get updateLater => 'Later';

  @override
  String get updateOpenFailed => 'The download page could not be opened.';

  @override
  String get requiredNote => 'Fields marked * are required.';

  @override
  String get requiredSemantics => 'required';

  @override
  String get errorOffensiveText =>
      'This text contains words that are not allowed. Please rephrase it.';

  @override
  String get guideTitle => 'Emergency guide';

  @override
  String get guideHubHint =>
      'Fires, fractures, first aid, breathing problems… Available without connection.';

  @override
  String get guideIntro =>
      'Choose a topic, then the situation. While waiting for help, follow the steps in order.';

  @override
  String guideItemsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count items',
      one: '1 item',
      zero: 'No item',
    );
    return '$_temp0';
  }

  @override
  String get guideEmpty => 'Nothing is published here at the moment.';

  @override
  String get guideCallNow => 'Call 198 at once if';

  @override
  String get guideSteps => 'What to do';

  @override
  String get guideDont => 'Do not';

  @override
  String get guideCall198 => 'Call Civil Protection, 198';

  @override
  String get guideSimBanner =>
      '[SIM] Content awaiting validation by the medical staff of the Civil Protection. Call 198 first.';

  @override
  String get guideSimTag => '[SIM] awaiting medical validation';

  @override
  String get nearestTitle => 'Nearest to me';

  @override
  String get nearestHint =>
      'Civil Protection centres, hospitals, pharmacies… and your coordinates. Works without connection once downloaded.';

  @override
  String get nearestMyPosition => 'My position';

  @override
  String get nearestNoLocation =>
      'Location is off or not allowed. Turn it on to see the nearest places.';

  @override
  String get nearestCopy => 'Copy';

  @override
  String get nearestCopied =>
      'Coordinates copied. You can read them to the operator.';

  @override
  String get nearestOffline =>
      'No connection: showing the copy saved on this phone.';

  @override
  String get nearestEmpty =>
      'Nothing saved on this phone yet. Connect once to download the places.';

  @override
  String get nearestLoading => 'Downloading the places for offline use…';

  @override
  String nearestUpdated(String date) {
    return 'Places updated on $date';
  }

  @override
  String get nearestToVerify => 'To be verified';

  @override
  String get nearestSimBanner =>
      '[SIM] Some of these places are approximate and invented for a trial: they are not real places. In an emergency, call 198.';

  @override
  String get nearestSimChip => '[SIM] Trial';

  @override
  String get nearestNeedPosition => 'Waiting for your position.';

  @override
  String get nearestNone => 'No place of this kind is listed yet.';

  @override
  String nearestSource(String source) {
    return 'Source: $source';
  }

  @override
  String nearestCall(String phone) {
    return 'Call $phone';
  }

  @override
  String get nearestRoute => 'Route';

  @override
  String get contactTitle => 'Contact us';

  @override
  String get contactMineTitle => 'My requests';

  @override
  String get contactEmergencyBanner =>
      'Not for emergencies. For an emergency, call 198.';

  @override
  String get contactIntro =>
      'Ask a question, request information held by the Civil Protection, report a non-urgent hazard, suggest an idea or report a problem with the app. You get a number to follow your request.';

  @override
  String get contactKind => 'Kind of request';

  @override
  String get contactKindAccessInfo => 'Access to information (law 2016-22)';

  @override
  String get contactKindHazard => 'Non-urgent hazard';

  @override
  String get contactKindQuestion => 'Question';

  @override
  String get contactKindSuggestion => 'Suggestion';

  @override
  String get contactKindAppProblem => 'Problem with the app';

  @override
  String get contactKindPartnership => 'Partnership';

  @override
  String get contactAccessInfoHint =>
      'The law asks for your name. The Office answers within the legal deadline (20 days).';

  @override
  String get contactNoGouvernorat => 'Not specific to a gouvernorat';

  @override
  String get contactSubject => 'Subject';

  @override
  String get contactMessage => 'Your message';

  @override
  String get contactDetailsHint =>
      'Contact details are optional: without them, the answer is only shown here in “My requests”.';

  @override
  String get contactName => 'Full name';

  @override
  String get contactEmail => 'E-mail';

  @override
  String get contactEmailInvalid => 'Enter a valid e-mail address.';

  @override
  String contactLength(int min, int max) {
    return 'Between $min and $max characters.';
  }

  @override
  String get contactSend => 'Send';

  @override
  String get contactSentTitle => 'Request sent';

  @override
  String get contactSentBody => 'Keep this number to follow your request:';

  @override
  String get contactSeeMine => 'See my requests';

  @override
  String get contactMineEmpty => 'You have not sent any request yet.';

  @override
  String get contactStatusReceived => 'Received';

  @override
  String get contactStatusInProgress => 'In progress';

  @override
  String get contactStatusAnswered => 'Answered';

  @override
  String get contactStatusClosed => 'Closed';

  @override
  String get contactStatusRejected => 'Rejected';

  @override
  String contactDue(String date) {
    return 'Answer due by $date';
  }

  @override
  String get contactAnswer => 'Answer of the Office';

  @override
  String get contactRejectReason => 'Reason given by the Office';

  @override
  String get errorFeatureOff => 'This feature is not available yet.';

  @override
  String get errorAlreadyLinked => 'You are already linked with this person.';

  @override
  String get errorOwnInvitation =>
      'This is your own code: give it to the other person.';

  @override
  String get errorTooManyLinks =>
      'You reached the maximum number of linked contacts.';

  @override
  String get errorTooManyInvitations =>
      'Too many open invitations. Use or let one expire first.';

  @override
  String get errorNoLinkedContact => 'No linked contact to alert in the app.';

  @override
  String get errorCheckActive => 'A safety check is already running.';

  @override
  String get errorHistoryOff => 'The location history is off.';

  @override
  String get errorDurationTooLong => 'This duration is longer than allowed.';

  @override
  String get safetyTitle => 'Personal safety';

  @override
  String get safetySettingsHint =>
      'Emergency contacts, SOS message, medical file';

  @override
  String get safetyIntro =>
      'Prepare who to warn and what to send if something happens to you. Your contacts, your message and your medical file stay on this phone.';

  @override
  String get safetySendSos => 'Send my SOS message';

  @override
  String get safetySomeone => 'A contact';

  @override
  String get safetyDelete => 'Delete';

  @override
  String get safetyEdit => 'Edit';

  @override
  String get safetyCopy => 'Copy';

  @override
  String get safetyCopied => 'Copied.';

  @override
  String get safetyDone => 'Done';

  @override
  String get safetySaved => 'Saved.';

  @override
  String get safetyBySms => 'SMS';

  @override
  String safetyAccuracy(int meters) {
    return '± $meters m';
  }

  @override
  String safetyMinutes(int minutes) {
    return '$minutes min';
  }

  @override
  String safetyHours(int hours) {
    return '$hours h';
  }

  @override
  String safetyHoursMinutes(int hours, int minutes) {
    return '$hours h $minutes min';
  }

  @override
  String get safetyContactsTitle => 'Emergency contacts';

  @override
  String safetyContactsCount(int count) {
    return 'Contacts: $count';
  }

  @override
  String get safetyContactsIntro =>
      'Up to 10 people who receive your SOS message by SMS or WhatsApp.';

  @override
  String get safetyContactsPrivacy =>
      'Kept on this phone only. The app never reads or uploads your address book: you choose each number.';

  @override
  String safetyContactsFull(int max) {
    return 'You reached $max contacts.';
  }

  @override
  String get safetyContactsEmpty => 'No emergency contact yet.';

  @override
  String get safetyContactAdd => 'Add a contact';

  @override
  String get safetyContactPick => 'Choose from my contacts';

  @override
  String get safetyContactPickHint =>
      'Only the number you choose reaches the app.';

  @override
  String get safetyContactType => 'Type a number';

  @override
  String get safetyContactTitle => 'Emergency contact';

  @override
  String get safetyContactName => 'Name';

  @override
  String get safetyContactNameRequired => 'Enter a name.';

  @override
  String get safetyContactPhone => 'Phone number';

  @override
  String get safetyContactExists => 'This number is already in your list.';

  @override
  String get safetyContactLinked => 'Linked: receives the alert in the app';

  @override
  String get safetyContactGroups => 'Groups';

  @override
  String safetyContactDeleteTitle(String name) {
    return 'Delete $name?';
  }

  @override
  String get safetyGroupsTitle => 'Groups';

  @override
  String get safetyGroupsEmpty =>
      'Groups let you warn only some people (family, neighbours…).';

  @override
  String get safetyGroupAdd => 'New group';

  @override
  String get safetyGroupName => 'Group name';

  @override
  String get safetyGroupNameHint => 'Family, neighbours, work…';

  @override
  String safetyGroupDeleteTitle(String name) {
    return 'Delete the group $name?';
  }

  @override
  String get safetyGroupDeleteBody => 'The contacts stay in your list.';

  @override
  String get safetyMessageTitle => 'SOS message';

  @override
  String get safetyMessageHint =>
      'Your text, and the 5-second window to cancel';

  @override
  String get safetyMessageText => 'Your message';

  @override
  String get safetyMessageAdded =>
      'The app adds the link to your position, its accuracy, the time and your battery level.';

  @override
  String get safetyCancelWindow => '5 seconds to cancel';

  @override
  String get safetyCancelWindowHint =>
      'Avoids a message sent by mistake. Turn it off to send at once.';

  @override
  String get safetyPreview => 'Preview';

  @override
  String get sosDefaultTemplate => 'I need help. This is my position.';

  @override
  String get sosLabelPosition => 'Position';

  @override
  String get sosLabelAccuracy => 'Accuracy';

  @override
  String get sosLabelTime => 'Time';

  @override
  String get sosLabelBattery => 'Battery';

  @override
  String get sosLabelNoPosition => 'Position not available.';

  @override
  String get safetySendIntro =>
      'Your contacts receive your message with your position. Linked contacts are alerted in the app; the SMS app opens with every number, and you press Send.';

  @override
  String get safetyNoContacts => 'Add at least one emergency contact first.';

  @override
  String get safetySendTo => 'Send to';

  @override
  String safetySendToAll(int count) {
    return 'Everyone ($count)';
  }

  @override
  String safetySendChannels(int count) {
    return 'Linked contacts alerted in the app: $count. Then SMS, then WhatsApp.';
  }

  @override
  String get safetySendSmsOnly =>
      'Without an account, the message goes by SMS and WhatsApp only.';

  @override
  String get safetySendNow => 'Send now';

  @override
  String safetySendingIn(int seconds) {
    return 'Sending in $seconds s…';
  }

  @override
  String get safetySending => 'Getting your position and sending…';

  @override
  String safetySentApp(int count) {
    return 'Alert received in the app by $count linked contact(s).';
  }

  @override
  String get safetySentAppFailed =>
      'The alert in the app could not be sent (no network?). The SMS still opened.';

  @override
  String safetySentSms(int count) {
    return 'SMS ready for $count number(s): press Send in the SMS app.';
  }

  @override
  String get safetyWhatsApp => 'Also by WhatsApp';

  @override
  String get safetyWhatsAppChoose => 'Choose a WhatsApp chat or group';

  @override
  String get safetyLinkedTitle => 'Linked contacts';

  @override
  String safetyLinkedCount(int count) {
    return 'Linked: $count';
  }

  @override
  String get safetyLinkedIntro =>
      'A relative who also uses e-Himaya can be linked to you. Your SOS message then rings on their phone, even in silent mode.';

  @override
  String get safetyLinkedNeedsAccount =>
      'Links need an e-Himaya account on both phones.';

  @override
  String get safetyLinkedEmpty => 'Nobody is linked yet.';

  @override
  String get safetyLinkedPrivacy =>
      'A linked person sees your first name and number, and your alerts. Either of you can remove the link at any time.';

  @override
  String get safetyLinkedDone => 'You are now linked.';

  @override
  String safetyLinkedPush(String name) {
    return 'You are now linked with $name.';
  }

  @override
  String get safetyInvite => 'Invite';

  @override
  String get safetyInviteTitle => 'Your invitation code';

  @override
  String get safetyInviteBody =>
      'Give this code to the person. They enter it in e-Himaya, Personal safety, Linked contacts.';

  @override
  String safetyInviteExpires(String time) {
    return 'Valid until $time, once.';
  }

  @override
  String safetyInviteText(String code) {
    return 'Link with me in e-Himaya so we can alert each other in an emergency. My code: $code';
  }

  @override
  String get safetyEnterCode => 'Enter a code';

  @override
  String get safetyCodeInvalid => 'This code is wrong, used or expired.';

  @override
  String get safetyLinkConfirmTitle => 'Link with this person?';

  @override
  String safetyLinkConfirmBody(String who) {
    return '$who will receive your alerts and you will receive theirs.';
  }

  @override
  String get safetyLinkAccept => 'Link';

  @override
  String get safetyUnlink => 'Remove the link';

  @override
  String safetyUnlinkTitle(String name) {
    return 'Remove the link with $name?';
  }

  @override
  String get safetyUnlinkBody =>
      'Neither of you will receive the other’s alerts.';

  @override
  String get safetyAlertTitle => 'Distress alert';

  @override
  String safetyAlertFrom(String name) {
    return '$name needs help';
  }

  @override
  String safetyAlertCheckFrom(String name) {
    return '$name did not confirm being safe';
  }

  @override
  String get safetyAlertMine => 'Your alert';

  @override
  String safetyAlertAt(String time) {
    return 'Sent at $time';
  }

  @override
  String safetyAlertBattery(int level) {
    return 'battery $level%';
  }

  @override
  String safetyAlertSeenBy(int seen, int total) {
    return 'Opened by $seen of $total';
  }

  @override
  String get safetyAlertNoPosition => 'No position was sent.';

  @override
  String safetyAlertLive(String time) {
    return 'Live position, updated $time';
  }

  @override
  String safetyAlertPositionAt(String time) {
    return 'Position at $time';
  }

  @override
  String safetyAlertCall(String name) {
    return 'Call $name';
  }

  @override
  String get safetyAlertRoute => 'Route';

  @override
  String get safetyAlertReportHint =>
      'If they are in danger, call the Civil Protection and give the position shown above.';

  @override
  String get safetyAlertCall198 => 'Call 198 for them';

  @override
  String get safetyAlertReport => 'Report it in the app';

  @override
  String get safetyLiveTitle => 'Live location';

  @override
  String get safetyLiveHint =>
      'A link that shows where you are, for a limited time';

  @override
  String get safetyLiveRunning => 'Your location is being shared';

  @override
  String get safetyLiveIntro =>
      'Create a link that shows your position as you move. It stops by itself at the end, or when you press Stop. Whoever has the link sees the point on a map, not your name.';

  @override
  String get safetyLiveNeedsAccount =>
      'Live location needs an e-Himaya account.';

  @override
  String get safetyLiveFor => 'Share for';

  @override
  String get safetyLiveStart => 'Start sharing';

  @override
  String get safetyLiveStop => 'Stop sharing';

  @override
  String get safetyLivePrivacy =>
      'The positions are deleted 24 hours after the share ends. A notification stays visible while it runs.';

  @override
  String safetyLiveLeft(String duration) {
    return '$duration left';
  }

  @override
  String safetyLiveLastSent(String time) {
    return 'last sent $time';
  }

  @override
  String safetyLiveShareText(String link) {
    return 'Follow my position live: $link';
  }

  @override
  String get safetyLiveSmsContacts => 'SMS to my contacts';

  @override
  String get safetyLiveNoticeTitle => 'e-Himaya: location shared';

  @override
  String get safetyLiveNoticeText =>
      'Your position is sent while the share or the safety check runs.';

  @override
  String get safetyCheckTitle => 'Safety check';

  @override
  String get safetyCheckHint =>
      'Linked contacts alerted if you do not confirm in time';

  @override
  String get safetyCheckRunning => 'A safety check is running';

  @override
  String get safetyCheckIntro =>
      'Going out alone, walking at night, a trip? Set a time. If you have not pressed “I am fine” by then, your linked contacts receive an alert with your last position, even if your phone is off. The Civil Protection is not alerted.';

  @override
  String get safetyCheckNeedsAccount =>
      'The safety check needs an e-Himaya account and linked contacts.';

  @override
  String get safetyCheckNoLinks =>
      'Link at least one contact first: the alert goes to linked contacts.';

  @override
  String get safetyCheckIn => 'Check in after';

  @override
  String get safetyCheckMessage => 'Message for your contacts';

  @override
  String get safetyCheckMessageHint =>
      'I did not confirm that I arrived safely.';

  @override
  String get safetyCheckStart => 'Start the check';

  @override
  String get safetyCheckPrivacy =>
      'Reminders 10 minutes and 1 minute before. The check and its position are deleted 7 days after it ends.';

  @override
  String safetyCheckDue(String time) {
    return 'Confirm before $time';
  }

  @override
  String safetyCheckContacts(int count) {
    return 'linked contacts: $count';
  }

  @override
  String get safetyCheckOk => 'I am fine';

  @override
  String safetyCheckExtend(int minutes) {
    return 'Add $minutes minutes';
  }

  @override
  String get safetyCheckFired => 'Your contacts were alerted';

  @override
  String get safetyCheckFiredHint =>
      'You did not confirm in time. If you are fine, tell them; otherwise send your SOS message.';

  @override
  String get safetyCheckReminder10 =>
      'Your safety check ends in 10 minutes. Open e-Himaya to confirm.';

  @override
  String get safetyCheckReminder1 =>
      'One minute left: confirm now or your contacts will be alerted.';

  @override
  String get safetyTestTitle => 'Self-test';

  @override
  String get safetyTestHint =>
      'Check that everything works, without sending anything';

  @override
  String get safetyTestIntro =>
      'Checks this phone: alarm sound, position, network, notifications and battery.';

  @override
  String get safetyTestAlarm => 'Play the alarm';

  @override
  String get safetyTestAlarmTitle => 'Test: distress alert';

  @override
  String get safetyTestAlarmBody =>
      'This is how an alert from a linked contact sounds. Nothing was sent.';

  @override
  String get safetyTestAlarmSent => 'Test alarm shown.';

  @override
  String get safetyTestRunning => 'Checking…';

  @override
  String get safetyTestNotificationsOn => 'Notifications allowed';

  @override
  String get safetyTestNotificationsOff =>
      'Notifications are blocked: alerts cannot reach you';

  @override
  String get safetyTestCriticalOn => 'Alerts ring even in silent mode';

  @override
  String get safetyTestCriticalOff => 'Alerts do not ring in silent mode';

  @override
  String get safetyTestCriticalFix => 'Turn on';

  @override
  String get safetyTestDnd => 'Do Not Disturb is on right now';

  @override
  String get safetyTestOnline => 'Network available';

  @override
  String get safetyTestOffline => 'No network: only SMS and calls work';

  @override
  String get safetyTestPosition => 'Position found';

  @override
  String get safetyTestNoPosition => 'No position: turn on location';

  @override
  String safetyTestBattery(int level) {
    return 'Battery $level%';
  }

  @override
  String get safetyTestBatteryUnknown => 'Battery level unknown';

  @override
  String get safetyTestPowerSave =>
      'Battery saver is on: alerts may arrive late';

  @override
  String safetyTestContacts(int contacts, int links) {
    return 'Emergency contacts: $contacts · linked: $links';
  }

  @override
  String get safetyTestAgain => 'Test again';

  @override
  String get safetyTestNothingSent =>
      'Nothing is sent to anyone during the self-test.';

  @override
  String get safetyRecentTitle => 'Recent alerts';

  @override
  String get safetyRecentReceived => 'Received (last 24 hours)';

  @override
  String get safetyRecentSentTitle => 'Sent from this phone';

  @override
  String get safetyRecentClear => 'Clear';

  @override
  String get safetyRecentEmpty => 'Nothing yet.';

  @override
  String get safetyRecentSos => 'SOS message';

  @override
  String get safetyRecentSent => 'sent';

  @override
  String get safetyRecentCancelled => 'cancelled';

  @override
  String get safetyRecentOk => 'done';

  @override
  String get safetyRecentFailed => 'not sent';

  @override
  String safetyRecentRecipients(int count) {
    return '$count recipient(s)';
  }

  @override
  String get safetyChannelApp => 'app';

  @override
  String get safetyRecentPrivacy => 'This list stays on this phone.';

  @override
  String get safetyMedicalTitle => 'Medical file';

  @override
  String get safetyMedicalHint =>
      'Useful information for rescuers, on this phone only';

  @override
  String get safetyMedicalSaved => 'Saved on this phone';

  @override
  String get medicalConsentTitle => 'Before you start';

  @override
  String get medicalConsentBody =>
      'Your medical file is health data. It stays encrypted on this phone. It is sent to the Civil Protection only with a report for which you tick “Attach my medical file”, and is then deleted 30 days after the report is closed. You can change or delete it at any time. Every field is optional.';

  @override
  String get medicalConsentCheck =>
      'I agree to keep my medical file on this phone under these conditions';

  @override
  String get medicalCreate => 'Create my medical file';

  @override
  String get medicalIntro =>
      'Fill in only what you want. Kept encrypted on this phone.';

  @override
  String get medicalSex => 'Sex';

  @override
  String get medicalSexFemale => 'Female';

  @override
  String get medicalSexMale => 'Male';

  @override
  String get medicalNotSaid => 'Not given';

  @override
  String get medicalBirthDate => 'Date of birth';

  @override
  String get medicalBloodGroup => 'Blood group';

  @override
  String get medicalAllergies => 'Allergies';

  @override
  String get medicalConditions => 'Chronic conditions';

  @override
  String get medicalMedications => 'Regular medicines';

  @override
  String get medicalOther => 'Other (pregnancy, device, disability…)';

  @override
  String get medicalTreatmentCard => 'Treatment card number';

  @override
  String get medicalContactName => 'Person to contact';

  @override
  String get medicalContactPhone => 'Their phone number';

  @override
  String get medicalContact => 'Contact';

  @override
  String get medicalLock => 'Ask for the phone lock';

  @override
  String get medicalLockHint =>
      'Your PIN, pattern or fingerprint before the file opens.';

  @override
  String get medicalLocked => 'Your medical file is locked.';

  @override
  String get medicalUnlock => 'Unlock';

  @override
  String get medicalUnlockHint => 'Confirm it is you to open the medical file.';

  @override
  String get medicalNoPhoneLock =>
      'This phone has no screen lock, so the file cannot be locked.';

  @override
  String get medicalForRescuer => 'Show to a rescuer';

  @override
  String get medicalCopy => 'Copy as text';

  @override
  String get medicalEmpty => 'The medical file is empty.';

  @override
  String get medicalAttachHint =>
      'In a report, tick “Attach my medical file” to send it with that report only.';

  @override
  String get medicalDelete => 'Delete my medical file';

  @override
  String get medicalDeleteTitle => 'Delete the medical file?';

  @override
  String get medicalDeleteBody =>
      'It is erased from this phone. Copies already attached to reports are deleted 30 days after each report is closed.';

  @override
  String get medicalDeleted => 'Medical file deleted.';

  @override
  String get reportAttachMedical => 'Attach my medical file to this report';

  @override
  String get reportAttachMedicalHint =>
      'Only the team handling this report can open it, and each opening is recorded.';

  @override
  String get safetyHistoryTitle => 'Location history (72 h)';

  @override
  String get safetyHistoryOn => 'On';

  @override
  String get safetyHistoryOff => 'Off';

  @override
  String get safetyHistoryNotice =>
      'If you go missing, the Civil Protection can see where your phone was during the last 72 hours. They read it only for a report they handle, with a reason, and you are told. Each position is deleted after 72 hours, and all of them at once when you turn it off.';

  @override
  String get safetyHistoryUnavailable => 'Not available yet.';

  @override
  String get safetyHistoryConsent =>
      'I agree that my positions are kept for 72 hours under these conditions';

  @override
  String get safetyHistoryTurnOn => 'Turn on';

  @override
  String get safetyHistoryTurnOff => 'Turn off and delete';

  @override
  String safetyHistoryUntil(String time) {
    return 'Until $time';
  }

  @override
  String get safetyHistoryViewedTitle => 'Your location history was consulted';

  @override
  String get safetyHistoryViewedBody =>
      'The Civil Protection consulted it for a report. Open e-Himaya for details.';
}
