import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';
import 'app_localizations_fr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
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

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
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
    Locale('fr'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya'**
  String get appTitle;

  /// No description provided for @actionContinue.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get actionContinue;

  /// No description provided for @actionCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get actionCancel;

  /// No description provided for @actionSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get actionSave;

  /// No description provided for @actionLater.
  ///
  /// In en, this message translates to:
  /// **'Later'**
  String get actionLater;

  /// No description provided for @actionRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get actionRetry;

  /// No description provided for @copied.
  ///
  /// In en, this message translates to:
  /// **'Tracking code copied.'**
  String get copied;

  /// No description provided for @copyTrackingCode.
  ///
  /// In en, this message translates to:
  /// **'Copy tracking code'**
  String get copyTrackingCode;

  /// No description provided for @callNumber.
  ///
  /// In en, this message translates to:
  /// **'Call {number}'**
  String callNumber(String number);

  /// No description provided for @charterTitle.
  ///
  /// In en, this message translates to:
  /// **'Privacy & personal data charter'**
  String get charterTitle;

  /// No description provided for @charterVersionLabel.
  ///
  /// In en, this message translates to:
  /// **'Version {version}'**
  String charterVersionLabel(String version);

  /// No description provided for @charterIntro.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya is the national platform for reporting emergencies to the Civil Protection. Before using it, please read how your data is handled and what your obligations are.'**
  String get charterIntro;

  /// No description provided for @charterDataTitle.
  ///
  /// In en, this message translates to:
  /// **'Data we collect and why'**
  String get charterDataTitle;

  /// No description provided for @charterDataBody.
  ///
  /// In en, this message translates to:
  /// **'For each report: its category, your description, the position of the incident and the photos, videos or voice messages you attach. If you create an account: your name, national ID card (CIN) number, phone number and region. This data is used only to handle emergencies and to inform you of the follow-up of your reports.'**
  String get charterDataBody;

  /// No description provided for @charterLawTitle.
  ///
  /// In en, this message translates to:
  /// **'Legal framework'**
  String get charterLawTitle;

  /// No description provided for @charterLawBody.
  ///
  /// In en, this message translates to:
  /// **'Your personal data is processed in accordance with Organic Law No. 2004-63 of 27 July 2004 on the protection of personal data and its implementing texts, under the supervision of the National Authority for the Protection of Personal Data (INPDP).'**
  String get charterLawBody;

  /// No description provided for @charterAnonymousTitle.
  ///
  /// In en, this message translates to:
  /// **'Reporting without an account'**
  String get charterAnonymousTitle;

  /// No description provided for @charterAnonymousBody.
  ///
  /// In en, this message translates to:
  /// **'You may report without an account. The app then uses a random key created on this phone; the platform keeps only a pseudonym derived from it and does not store your IP address. Anonymous reporting from a device can be suspended after confirmed false reports.'**
  String get charterAnonymousBody;

  /// No description provided for @charterRightsTitle.
  ///
  /// In en, this message translates to:
  /// **'Your rights'**
  String get charterRightsTitle;

  /// No description provided for @charterRightsBody.
  ///
  /// In en, this message translates to:
  /// **'You have the right to access, rectify and object to the processing of your data under the conditions set by law. You can exercise these rights with the platform operator and refer the matter to the INPDP.'**
  String get charterRightsBody;

  /// No description provided for @charterRetentionTitle.
  ///
  /// In en, this message translates to:
  /// **'Security and retention'**
  String get charterRetentionTitle;

  /// No description provided for @charterRetentionBody.
  ///
  /// In en, this message translates to:
  /// **'Reports waiting to be sent are stored encrypted on your phone. On the platform, data is kept only as long as needed to handle the emergency and to meet legal obligations, and is accessible only to authorised staff.'**
  String get charterRetentionBody;

  /// No description provided for @charterLiabilityTitle.
  ///
  /// In en, this message translates to:
  /// **'Responsibility for false reports'**
  String get charterLiabilityTitle;

  /// No description provided for @charterLiabilityBody.
  ///
  /// In en, this message translates to:
  /// **'Every report mobilises rescue teams that may be needed elsewhere. Knowingly making a false report or a false alert engages your legal liability and exposes you to prosecution under Tunisian law.'**
  String get charterLiabilityBody;

  /// No description provided for @charterCheckbox.
  ///
  /// In en, this message translates to:
  /// **'I have read and accept the charter, and I understand that a knowingly false report engages my legal liability.'**
  String get charterCheckbox;

  /// No description provided for @charterAcceptedOn.
  ///
  /// In en, this message translates to:
  /// **'Accepted on {date}'**
  String charterAcceptedOn(String date);

  /// No description provided for @roleTitle.
  ///
  /// In en, this message translates to:
  /// **'Who are you?'**
  String get roleTitle;

  /// No description provided for @roleCitizen.
  ///
  /// In en, this message translates to:
  /// **'Citizen'**
  String get roleCitizen;

  /// No description provided for @roleCitizenDesc.
  ///
  /// In en, this message translates to:
  /// **'Report an emergency, send an SOS and follow your reports.'**
  String get roleCitizenDesc;

  /// No description provided for @roleInstitution.
  ///
  /// In en, this message translates to:
  /// **'Institution'**
  String get roleInstitution;

  /// No description provided for @roleInstitutionDesc.
  ///
  /// In en, this message translates to:
  /// **'Public or private institution with a registered account.'**
  String get roleInstitutionDesc;

  /// No description provided for @institutionTitle.
  ///
  /// In en, this message translates to:
  /// **'Institutions'**
  String get institutionTitle;

  /// No description provided for @institutionBody.
  ///
  /// In en, this message translates to:
  /// **'Registration is mandatory for institutions and is done through the institutions portal, not in this app. If your institution already has an account, sign in below.'**
  String get institutionBody;

  /// No description provided for @institutionLogin.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get institutionLogin;

  /// No description provided for @citizenModeTitle.
  ///
  /// In en, this message translates to:
  /// **'How do you want to report?'**
  String get citizenModeTitle;

  /// No description provided for @citizenAnonymous.
  ///
  /// In en, this message translates to:
  /// **'Continue without an account'**
  String get citizenAnonymous;

  /// No description provided for @citizenAnonymousDesc.
  ///
  /// In en, this message translates to:
  /// **'Fastest. No personal information is asked.'**
  String get citizenAnonymousDesc;

  /// No description provided for @citizenRegister.
  ///
  /// In en, this message translates to:
  /// **'Create an account'**
  String get citizenRegister;

  /// No description provided for @citizenRegisterDesc.
  ///
  /// In en, this message translates to:
  /// **'Follow your reports on any device; your reports carry more weight.'**
  String get citizenRegisterDesc;

  /// No description provided for @citizenLogin.
  ///
  /// In en, this message translates to:
  /// **'I already have an account'**
  String get citizenLogin;

  /// No description provided for @citizenLoginDesc.
  ///
  /// In en, this message translates to:
  /// **'Sign in with your e-Himaya account.'**
  String get citizenLoginDesc;

  /// No description provided for @changeRole.
  ///
  /// In en, this message translates to:
  /// **'Change role'**
  String get changeRole;

  /// No description provided for @loginCancelled.
  ///
  /// In en, this message translates to:
  /// **'Sign-in cancelled.'**
  String get loginCancelled;

  /// No description provided for @loginFailed.
  ///
  /// In en, this message translates to:
  /// **'Sign-in failed. Check your connection and try again.'**
  String get loginFailed;

  /// No description provided for @profileTitle.
  ///
  /// In en, this message translates to:
  /// **'Complete your profile'**
  String get profileTitle;

  /// No description provided for @profileIntro.
  ///
  /// In en, this message translates to:
  /// **'This information will be used to verify your reports. You can complete it later from the settings.'**
  String get profileIntro;

  /// No description provided for @profileFirstName.
  ///
  /// In en, this message translates to:
  /// **'First name'**
  String get profileFirstName;

  /// No description provided for @profileLastName.
  ///
  /// In en, this message translates to:
  /// **'Last name'**
  String get profileLastName;

  /// No description provided for @profileCin.
  ///
  /// In en, this message translates to:
  /// **'National ID card (CIN) number'**
  String get profileCin;

  /// No description provided for @profileCinHint.
  ///
  /// In en, this message translates to:
  /// **'8 digits'**
  String get profileCinHint;

  /// No description provided for @profileCinStored.
  ///
  /// In en, this message translates to:
  /// **'Saved CIN ends with {last4}; enter it again to save changes.'**
  String profileCinStored(String last4);

  /// No description provided for @profilePhone.
  ///
  /// In en, this message translates to:
  /// **'Phone number'**
  String get profilePhone;

  /// No description provided for @profileGouvernorat.
  ///
  /// In en, this message translates to:
  /// **'Gouvernorat'**
  String get profileGouvernorat;

  /// No description provided for @profileDelegation.
  ///
  /// In en, this message translates to:
  /// **'Délégation'**
  String get profileDelegation;

  /// No description provided for @profileAddress.
  ///
  /// In en, this message translates to:
  /// **'Address (optional)'**
  String get profileAddress;

  /// No description provided for @profileSaved.
  ///
  /// In en, this message translates to:
  /// **'Profile saved.'**
  String get profileSaved;

  /// No description provided for @validationRequired.
  ///
  /// In en, this message translates to:
  /// **'Required.'**
  String get validationRequired;

  /// No description provided for @validationCin.
  ///
  /// In en, this message translates to:
  /// **'The CIN has exactly 8 digits.'**
  String get validationCin;

  /// No description provided for @validationPhone.
  ///
  /// In en, this message translates to:
  /// **'Enter the 8 digits after +216.'**
  String get validationPhone;

  /// No description provided for @geoLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load the list.'**
  String get geoLoadFailed;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navReports.
  ///
  /// In en, this message translates to:
  /// **'My reports'**
  String get navReports;

  /// No description provided for @navSettings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get navSettings;

  /// No description provided for @homeTagline.
  ///
  /// In en, this message translates to:
  /// **'In an emergency, every second counts.'**
  String get homeTagline;

  /// No description provided for @homeNewReport.
  ///
  /// In en, this message translates to:
  /// **'New report'**
  String get homeNewReport;

  /// No description provided for @homeNewReportDesc.
  ///
  /// In en, this message translates to:
  /// **'Fire, flood, accident… with photos, video or voice.'**
  String get homeNewReportDesc;

  /// No description provided for @homeEmergencyDesc.
  ///
  /// In en, this message translates to:
  /// **'Call 198, 190, 197 or 193 directly, even offline.'**
  String get homeEmergencyDesc;

  /// No description provided for @homeTrackDesc.
  ///
  /// In en, this message translates to:
  /// **'Follow a report with its tracking code.'**
  String get homeTrackDesc;

  /// No description provided for @pendingSyncBanner.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 report waiting to be sent} other{{count} reports waiting to be sent}}'**
  String pendingSyncBanner(int count);

  /// No description provided for @sosButtonLabel.
  ///
  /// In en, this message translates to:
  /// **'SOS'**
  String get sosButtonLabel;

  /// No description provided for @sosHint.
  ///
  /// In en, this message translates to:
  /// **'Tap twice or hold to send your position.'**
  String get sosHint;

  /// No description provided for @sosArmed.
  ///
  /// In en, this message translates to:
  /// **'Tap again to send the SOS.'**
  String get sosArmed;

  /// No description provided for @sosSending.
  ///
  /// In en, this message translates to:
  /// **'Sending SOS…'**
  String get sosSending;

  /// No description provided for @sosConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Send an SOS?'**
  String get sosConfirmTitle;

  /// No description provided for @sosConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'Your current position will be sent to the Civil Protection.'**
  String get sosConfirmBody;

  /// No description provided for @sosConfirmAction.
  ///
  /// In en, this message translates to:
  /// **'Send SOS'**
  String get sosConfirmAction;

  /// No description provided for @sosNoLocation.
  ///
  /// In en, this message translates to:
  /// **'Your position is not available. Enable location, or call the Civil Protection.'**
  String get sosNoLocation;

  /// No description provided for @sosQueuedTitle.
  ///
  /// In en, this message translates to:
  /// **'SOS saved'**
  String get sosQueuedTitle;

  /// No description provided for @anonBlockedBody.
  ///
  /// In en, this message translates to:
  /// **'Reporting without an account is suspended on this device. Create an account to keep reporting.'**
  String get anonBlockedBody;

  /// No description provided for @emergencyTitle.
  ///
  /// In en, this message translates to:
  /// **'Emergency numbers'**
  String get emergencyTitle;

  /// No description provided for @emergencyIntro.
  ///
  /// In en, this message translates to:
  /// **'Calls go directly through your SIM card, even without internet.'**
  String get emergencyIntro;

  /// No description provided for @emergencyCivilProtection.
  ///
  /// In en, this message translates to:
  /// **'Civil Protection'**
  String get emergencyCivilProtection;

  /// No description provided for @emergencySamu.
  ///
  /// In en, this message translates to:
  /// **'Emergency medical service (SAMU)'**
  String get emergencySamu;

  /// No description provided for @emergencyPolice.
  ///
  /// In en, this message translates to:
  /// **'Police emergency'**
  String get emergencyPolice;

  /// No description provided for @emergencyNationalGuard.
  ///
  /// In en, this message translates to:
  /// **'National Guard'**
  String get emergencyNationalGuard;

  /// No description provided for @emergencyCallSemantics.
  ///
  /// In en, this message translates to:
  /// **'Call {name}, {number}'**
  String emergencyCallSemantics(String name, String number);

  /// No description provided for @dialFailed.
  ///
  /// In en, this message translates to:
  /// **'This device cannot place calls.'**
  String get dialFailed;

  /// No description provided for @categorySos.
  ///
  /// In en, this message translates to:
  /// **'SOS'**
  String get categorySos;

  /// No description provided for @categoryFire.
  ///
  /// In en, this message translates to:
  /// **'Fire'**
  String get categoryFire;

  /// No description provided for @categoryFlood.
  ///
  /// In en, this message translates to:
  /// **'Flood'**
  String get categoryFlood;

  /// No description provided for @categoryTrafficAccident.
  ///
  /// In en, this message translates to:
  /// **'Traffic accident'**
  String get categoryTrafficAccident;

  /// No description provided for @categoryDrowning.
  ///
  /// In en, this message translates to:
  /// **'Drowning'**
  String get categoryDrowning;

  /// No description provided for @categoryLandslide.
  ///
  /// In en, this message translates to:
  /// **'Landslide'**
  String get categoryLandslide;

  /// No description provided for @categoryChemicalLeak.
  ///
  /// In en, this message translates to:
  /// **'Chemical leak'**
  String get categoryChemicalLeak;

  /// No description provided for @categoryMedical.
  ///
  /// In en, this message translates to:
  /// **'Medical emergency'**
  String get categoryMedical;

  /// No description provided for @categoryOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get categoryOther;

  /// No description provided for @statusReceived.
  ///
  /// In en, this message translates to:
  /// **'Received'**
  String get statusReceived;

  /// No description provided for @statusInProgress.
  ///
  /// In en, this message translates to:
  /// **'Being processed'**
  String get statusInProgress;

  /// No description provided for @statusIntervened.
  ///
  /// In en, this message translates to:
  /// **'Intervened'**
  String get statusIntervened;

  /// No description provided for @statusOngoing.
  ///
  /// In en, this message translates to:
  /// **'Intervention ongoing'**
  String get statusOngoing;

  /// No description provided for @statusClosed.
  ///
  /// In en, this message translates to:
  /// **'Closed'**
  String get statusClosed;

  /// No description provided for @statusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get statusRejected;

  /// No description provided for @statusUnknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown status'**
  String get statusUnknown;

  /// No description provided for @newReportTitle.
  ///
  /// In en, this message translates to:
  /// **'New report'**
  String get newReportTitle;

  /// No description provided for @chooseCategory.
  ///
  /// In en, this message translates to:
  /// **'What is happening?'**
  String get chooseCategory;

  /// No description provided for @reportLocation.
  ///
  /// In en, this message translates to:
  /// **'Location'**
  String get reportLocation;

  /// No description provided for @locationLocating.
  ///
  /// In en, this message translates to:
  /// **'Locating…'**
  String get locationLocating;

  /// No description provided for @locationAccuracy.
  ///
  /// In en, this message translates to:
  /// **'Position found, accuracy ±{meters} m'**
  String locationAccuracy(int meters);

  /// No description provided for @locationManual.
  ///
  /// In en, this message translates to:
  /// **'Position set on the map'**
  String get locationManual;

  /// No description provided for @locationAdjustHint.
  ///
  /// In en, this message translates to:
  /// **'Move the map to place the pin exactly on the incident.'**
  String get locationAdjustHint;

  /// No description provided for @locationUnavailable.
  ///
  /// In en, this message translates to:
  /// **'No GPS position yet. Place the pin on the map or try again.'**
  String get locationUnavailable;

  /// No description provided for @locationPermissionDenied.
  ///
  /// In en, this message translates to:
  /// **'Location is off or not allowed. Place the pin on the map.'**
  String get locationPermissionDenied;

  /// No description provided for @locationOutsideTunisia.
  ///
  /// In en, this message translates to:
  /// **'The location must be in Tunisia.'**
  String get locationOutsideTunisia;

  /// No description provided for @locationRefresh.
  ///
  /// In en, this message translates to:
  /// **'Use my position'**
  String get locationRefresh;

  /// No description provided for @mapPinSemantics.
  ///
  /// In en, this message translates to:
  /// **'Report location pin'**
  String get mapPinSemantics;

  /// No description provided for @reportDescription.
  ///
  /// In en, this message translates to:
  /// **'Description (optional)'**
  String get reportDescription;

  /// No description provided for @reportDescriptionHint.
  ///
  /// In en, this message translates to:
  /// **'What do you see? Are there injured people?'**
  String get reportDescriptionHint;

  /// No description provided for @reportAttachments.
  ///
  /// In en, this message translates to:
  /// **'Photos, videos and voice message'**
  String get reportAttachments;

  /// No description provided for @attachTakePhoto.
  ///
  /// In en, this message translates to:
  /// **'Take a photo'**
  String get attachTakePhoto;

  /// No description provided for @attachPickPhoto.
  ///
  /// In en, this message translates to:
  /// **'Photo gallery'**
  String get attachPickPhoto;

  /// No description provided for @attachRecordVideo.
  ///
  /// In en, this message translates to:
  /// **'Record a video'**
  String get attachRecordVideo;

  /// No description provided for @attachPickVideo.
  ///
  /// In en, this message translates to:
  /// **'Choose a video'**
  String get attachPickVideo;

  /// No description provided for @attachmentPhoto.
  ///
  /// In en, this message translates to:
  /// **'Photo {n}'**
  String attachmentPhoto(int n);

  /// No description provided for @attachmentVideo.
  ///
  /// In en, this message translates to:
  /// **'Video {n}'**
  String attachmentVideo(int n);

  /// No description provided for @attachmentTooLarge.
  ///
  /// In en, this message translates to:
  /// **'This file is too large (maximum {maxMb} MB).'**
  String attachmentTooLarge(int maxMb);

  /// No description provided for @attachmentUnsupported.
  ///
  /// In en, this message translates to:
  /// **'This file format is not accepted.'**
  String get attachmentUnsupported;

  /// No description provided for @attachmentLimit.
  ///
  /// In en, this message translates to:
  /// **'At most {max} files per report.'**
  String attachmentLimit(int max);

  /// No description provided for @removeAttachment.
  ///
  /// In en, this message translates to:
  /// **'Remove attachment'**
  String get removeAttachment;

  /// No description provided for @pickerFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not open the camera or the gallery.'**
  String get pickerFailed;

  /// No description provided for @audioTitle.
  ///
  /// In en, this message translates to:
  /// **'Voice message'**
  String get audioTitle;

  /// No description provided for @audioMaxDuration.
  ///
  /// In en, this message translates to:
  /// **'5 minutes max.'**
  String get audioMaxDuration;

  /// No description provided for @audioRecord.
  ///
  /// In en, this message translates to:
  /// **'Record'**
  String get audioRecord;

  /// No description provided for @audioStop.
  ///
  /// In en, this message translates to:
  /// **'Stop'**
  String get audioStop;

  /// No description provided for @audioPlay.
  ///
  /// In en, this message translates to:
  /// **'Play the recording'**
  String get audioPlay;

  /// No description provided for @audioPause.
  ///
  /// In en, this message translates to:
  /// **'Pause'**
  String get audioPause;

  /// No description provided for @audioReRecord.
  ///
  /// In en, this message translates to:
  /// **'Record again'**
  String get audioReRecord;

  /// No description provided for @audioDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete the recording'**
  String get audioDelete;

  /// No description provided for @audioRecording.
  ///
  /// In en, this message translates to:
  /// **'Recording… {duration}'**
  String audioRecording(String duration);

  /// No description provided for @audioPermissionDenied.
  ///
  /// In en, this message translates to:
  /// **'Microphone access was refused.'**
  String get audioPermissionDenied;

  /// No description provided for @audioFailed.
  ///
  /// In en, this message translates to:
  /// **'The recording could not start.'**
  String get audioFailed;

  /// No description provided for @reportSubmit.
  ///
  /// In en, this message translates to:
  /// **'Send report'**
  String get reportSubmit;

  /// No description provided for @reportNeedsLocation.
  ///
  /// In en, this message translates to:
  /// **'Wait for your position or place the pin on the map.'**
  String get reportNeedsLocation;

  /// No description provided for @reportOfflineNote.
  ///
  /// In en, this message translates to:
  /// **'Without network, the report is saved encrypted on the phone and sent automatically later.'**
  String get reportOfflineNote;

  /// No description provided for @reportSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'The report could not be saved. Try again.'**
  String get reportSaveFailed;

  /// No description provided for @reportQueuedTitle.
  ///
  /// In en, this message translates to:
  /// **'Report saved'**
  String get reportQueuedTitle;

  /// No description provided for @reportTempCodeLabel.
  ///
  /// In en, this message translates to:
  /// **'Temporary code'**
  String get reportTempCodeLabel;

  /// No description provided for @reportQueuedBody.
  ///
  /// In en, this message translates to:
  /// **'Keep this code. It will be replaced by the final tracking code as soon as the Civil Protection receives your report.'**
  String get reportQueuedBody;

  /// No description provided for @reportReceivedBody.
  ///
  /// In en, this message translates to:
  /// **'Your report was received by the Civil Protection. Use this code to follow it.'**
  String get reportReceivedBody;

  /// No description provided for @reportBackHome.
  ///
  /// In en, this message translates to:
  /// **'Back to home'**
  String get reportBackHome;

  /// No description provided for @temporaryCodeNote.
  ///
  /// In en, this message translates to:
  /// **'Temporary code, waiting to be sent'**
  String get temporaryCodeNote;

  /// No description provided for @myReportsTitle.
  ///
  /// In en, this message translates to:
  /// **'My reports'**
  String get myReportsTitle;

  /// No description provided for @myReportsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No reports yet.'**
  String get myReportsEmpty;

  /// No description provided for @myReportsOffline.
  ///
  /// In en, this message translates to:
  /// **'Could not refresh from the server.'**
  String get myReportsOffline;

  /// No description provided for @reportPendingSync.
  ///
  /// In en, this message translates to:
  /// **'Waiting to be sent'**
  String get reportPendingSync;

  /// No description provided for @reportConflict.
  ///
  /// In en, this message translates to:
  /// **'Server version kept'**
  String get reportConflict;

  /// No description provided for @reportFailed.
  ///
  /// In en, this message translates to:
  /// **'Not accepted'**
  String get reportFailed;

  /// No description provided for @reportBlocked.
  ///
  /// In en, this message translates to:
  /// **'Account required'**
  String get reportBlocked;

  /// No description provided for @reportUploadingMedia.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 attachment being sent} other{{count} attachments being sent}}'**
  String reportUploadingMedia(int count);

  /// No description provided for @reportMediaRejected.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 attachment refused} other{{count} attachments refused}}'**
  String reportMediaRejected(int count);

  /// No description provided for @trackTitle.
  ///
  /// In en, this message translates to:
  /// **'Track a report'**
  String get trackTitle;

  /// No description provided for @trackingCodeLabel.
  ///
  /// In en, this message translates to:
  /// **'Tracking code'**
  String get trackingCodeLabel;

  /// No description provided for @trackHint.
  ///
  /// In en, this message translates to:
  /// **'EH-26-61-0004821'**
  String get trackHint;

  /// No description provided for @trackAction.
  ///
  /// In en, this message translates to:
  /// **'Track'**
  String get trackAction;

  /// No description provided for @trackInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a code like EH-26-61-0004821.'**
  String get trackInvalid;

  /// No description provided for @trackHistory.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get trackHistory;

  /// No description provided for @receivedAt.
  ///
  /// In en, this message translates to:
  /// **'Received on {date}'**
  String receivedAt(String date);

  /// No description provided for @settingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settingsTitle;

  /// No description provided for @settingsLanguage.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get settingsLanguage;

  /// No description provided for @languageArabic.
  ///
  /// In en, this message translates to:
  /// **'العربية'**
  String get languageArabic;

  /// No description provided for @languageFrench.
  ///
  /// In en, this message translates to:
  /// **'Français'**
  String get languageFrench;

  /// No description provided for @languageEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get languageEnglish;

  /// No description provided for @settingsTheme.
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get settingsTheme;

  /// No description provided for @themeSystem.
  ///
  /// In en, this message translates to:
  /// **'Same as the phone'**
  String get themeSystem;

  /// No description provided for @themeLight.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In en, this message translates to:
  /// **'Dark'**
  String get themeDark;

  /// No description provided for @settingsIdentity.
  ///
  /// In en, this message translates to:
  /// **'Identity'**
  String get settingsIdentity;

  /// No description provided for @identityAnonymous.
  ///
  /// In en, this message translates to:
  /// **'Without account (this device)'**
  String get identityAnonymous;

  /// No description provided for @identityRegistered.
  ///
  /// In en, this message translates to:
  /// **'Signed in'**
  String get identityRegistered;

  /// No description provided for @identityRegisteredAs.
  ///
  /// In en, this message translates to:
  /// **'Signed in as {name}'**
  String identityRegisteredAs(String name);

  /// No description provided for @identityNone.
  ///
  /// In en, this message translates to:
  /// **'Not signed in'**
  String get identityNone;

  /// No description provided for @settingsRegister.
  ///
  /// In en, this message translates to:
  /// **'Create an account'**
  String get settingsRegister;

  /// No description provided for @settingsProfile.
  ///
  /// In en, this message translates to:
  /// **'My profile'**
  String get settingsProfile;

  /// No description provided for @settingsLogout.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get settingsLogout;

  /// No description provided for @logoutConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign out?'**
  String get logoutConfirmTitle;

  /// No description provided for @logoutConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'Reports waiting to be sent stay on this phone and will be sent after you sign in again or choose to continue without an account.'**
  String get logoutConfirmBody;

  /// No description provided for @settingsCharter.
  ///
  /// In en, this message translates to:
  /// **'Read the charter again'**
  String get settingsCharter;

  /// No description provided for @errorAuthenticationRequired.
  ///
  /// In en, this message translates to:
  /// **'Your session has expired. Please sign in again.'**
  String get errorAuthenticationRequired;

  /// No description provided for @errorInvalidDeviceKey.
  ///
  /// In en, this message translates to:
  /// **'This device could not be identified. Restart the app.'**
  String get errorInvalidDeviceKey;

  /// No description provided for @errorAnonBlocked.
  ///
  /// In en, this message translates to:
  /// **'Reporting without an account is suspended on this device. Please create an account.'**
  String get errorAnonBlocked;

  /// No description provided for @errorAccountSuspended.
  ///
  /// In en, this message translates to:
  /// **'Your account is suspended.'**
  String get errorAccountSuspended;

  /// No description provided for @errorConsentRequired.
  ///
  /// In en, this message translates to:
  /// **'Please accept the charter before reporting.'**
  String get errorConsentRequired;

  /// No description provided for @errorRateLimited.
  ///
  /// In en, this message translates to:
  /// **'Too many requests. Please wait a moment.'**
  String get errorRateLimited;

  /// No description provided for @errorUnknownCharterVersion.
  ///
  /// In en, this message translates to:
  /// **'The charter has changed. Please read it again.'**
  String get errorUnknownCharterVersion;

  /// No description provided for @errorClientUuidConflict.
  ///
  /// In en, this message translates to:
  /// **'This report conflicts with another one on the server.'**
  String get errorClientUuidConflict;

  /// No description provided for @errorNotFound.
  ///
  /// In en, this message translates to:
  /// **'Not found. Check the code.'**
  String get errorNotFound;

  /// No description provided for @errorValidation.
  ///
  /// In en, this message translates to:
  /// **'Some information is invalid.'**
  String get errorValidation;

  /// No description provided for @errorNetwork.
  ///
  /// In en, this message translates to:
  /// **'No connection to the server. It will be retried automatically.'**
  String get errorNetwork;

  /// No description provided for @errorServer.
  ///
  /// In en, this message translates to:
  /// **'The service is temporarily unavailable.'**
  String get errorServer;

  /// No description provided for @errorUnknown.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong.'**
  String get errorUnknown;

  /// No description provided for @errorMediaRefused.
  ///
  /// In en, this message translates to:
  /// **'The attachment was refused.'**
  String get errorMediaRefused;

  /// No description provided for @errorMediaTooLarge.
  ///
  /// In en, this message translates to:
  /// **'The attachment is too large.'**
  String get errorMediaTooLarge;

  /// No description provided for @errorUnsupportedMediaType.
  ///
  /// In en, this message translates to:
  /// **'This attachment format is not accepted.'**
  String get errorUnsupportedMediaType;

  /// No description provided for @errorTooManyMedia.
  ///
  /// In en, this message translates to:
  /// **'This report already has the maximum number of attachments.'**
  String get errorTooManyMedia;

  /// No description provided for @errorUploadWindowClosed.
  ///
  /// In en, this message translates to:
  /// **'Attachments can only be added within 24 hours of the report.'**
  String get errorUploadWindowClosed;

  /// No description provided for @errorMediaRejected.
  ///
  /// In en, this message translates to:
  /// **'The attachment was damaged in transfer and was refused.'**
  String get errorMediaRejected;

  /// No description provided for @errorOrgNotFound.
  ///
  /// In en, this message translates to:
  /// **'This institution was not found or you are no longer one of its members.'**
  String get errorOrgNotFound;

  /// No description provided for @errorOrgNotActive.
  ///
  /// In en, this message translates to:
  /// **'This institution is not active (under review, rejected or suspended): it cannot report.'**
  String get errorOrgNotActive;

  /// No description provided for @errorOrgRoleRequired.
  ///
  /// In en, this message translates to:
  /// **'Your role in this institution does not allow this action.'**
  String get errorOrgRoleRequired;

  /// No description provided for @reportAsTitle.
  ///
  /// In en, this message translates to:
  /// **'Report as'**
  String get reportAsTitle;

  /// No description provided for @reportAsSelf.
  ///
  /// In en, this message translates to:
  /// **'Myself'**
  String get reportAsSelf;

  /// No description provided for @reportAsInstitutionUnnamed.
  ///
  /// In en, this message translates to:
  /// **'Institution'**
  String get reportAsInstitutionUnnamed;

  /// No description provided for @reportOrgRefused.
  ///
  /// In en, this message translates to:
  /// **'Refused for the institution'**
  String get reportOrgRefused;

  /// No description provided for @reportOrgNotFoundBody.
  ///
  /// In en, this message translates to:
  /// **'This report could not be sent on behalf of the institution: it was not found or you are no longer one of its members. It is kept on this phone. You can send it as yourself.'**
  String get reportOrgNotFoundBody;

  /// No description provided for @reportOrgNotActiveBody.
  ///
  /// In en, this message translates to:
  /// **'This report could not be sent on behalf of the institution because it is not active. It is kept on this phone. You can send it as yourself.'**
  String get reportOrgNotActiveBody;

  /// No description provided for @reportResendAsSelf.
  ///
  /// In en, this message translates to:
  /// **'Send as myself'**
  String get reportResendAsSelf;

  /// No description provided for @reportResentAsSelf.
  ///
  /// In en, this message translates to:
  /// **'The report will be sent as yourself.'**
  String get reportResentAsSelf;

  /// No description provided for @settingsSosReportAs.
  ///
  /// In en, this message translates to:
  /// **'SOS'**
  String get settingsSosReportAs;

  /// No description provided for @settingsSosReportAsHint.
  ///
  /// In en, this message translates to:
  /// **'The SOS button sends the alert as:'**
  String get settingsSosReportAsHint;

  /// No description provided for @myInstitutionTitle.
  ///
  /// In en, this message translates to:
  /// **'My institution'**
  String get myInstitutionTitle;

  /// No description provided for @myInstitutionsTitle.
  ///
  /// In en, this message translates to:
  /// **'My institutions'**
  String get myInstitutionsTitle;

  /// No description provided for @myInstitutionsEmpty.
  ///
  /// In en, this message translates to:
  /// **'You do not belong to any institution.'**
  String get myInstitutionsEmpty;

  /// No description provided for @homeInstitutionDesc.
  ///
  /// In en, this message translates to:
  /// **'Safety card, team and reports of your institution'**
  String get homeInstitutionDesc;

  /// No description provided for @orgKindIndustrial.
  ///
  /// In en, this message translates to:
  /// **'Industrial'**
  String get orgKindIndustrial;

  /// No description provided for @orgKindEducational.
  ///
  /// In en, this message translates to:
  /// **'Educational'**
  String get orgKindEducational;

  /// No description provided for @orgKindHotel.
  ///
  /// In en, this message translates to:
  /// **'Hotel'**
  String get orgKindHotel;

  /// No description provided for @orgKindGovernment.
  ///
  /// In en, this message translates to:
  /// **'Government'**
  String get orgKindGovernment;

  /// No description provided for @orgKindPrivate.
  ///
  /// In en, this message translates to:
  /// **'Private'**
  String get orgKindPrivate;

  /// No description provided for @orgKindOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get orgKindOther;

  /// No description provided for @orgStatusPendingReview.
  ///
  /// In en, this message translates to:
  /// **'Under review'**
  String get orgStatusPendingReview;

  /// No description provided for @orgStatusActive.
  ///
  /// In en, this message translates to:
  /// **'Active'**
  String get orgStatusActive;

  /// No description provided for @orgStatusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get orgStatusRejected;

  /// No description provided for @orgStatusSuspended.
  ///
  /// In en, this message translates to:
  /// **'Suspended'**
  String get orgStatusSuspended;

  /// No description provided for @orgFamilyHighRise.
  ///
  /// In en, this message translates to:
  /// **'High-rise building'**
  String get orgFamilyHighRise;

  /// No description provided for @orgFamilyIndustrial.
  ///
  /// In en, this message translates to:
  /// **'Industrial establishment'**
  String get orgFamilyIndustrial;

  /// No description provided for @orgFamilyErp.
  ///
  /// In en, this message translates to:
  /// **'Building open to the public'**
  String get orgFamilyErp;

  /// No description provided for @orgFamilyWorkplace.
  ///
  /// In en, this message translates to:
  /// **'Workplace'**
  String get orgFamilyWorkplace;

  /// No description provided for @orgErpCategory.
  ///
  /// In en, this message translates to:
  /// **'category {category}'**
  String orgErpCategory(int category);

  /// No description provided for @orgTeamRepresentative.
  ///
  /// In en, this message translates to:
  /// **'Representative'**
  String get orgTeamRepresentative;

  /// No description provided for @orgTeamMember.
  ///
  /// In en, this message translates to:
  /// **'Member'**
  String get orgTeamMember;

  /// No description provided for @trainingValid.
  ///
  /// In en, this message translates to:
  /// **'valid'**
  String get trainingValid;

  /// No description provided for @trainingExpiring.
  ///
  /// In en, this message translates to:
  /// **'expiring soon'**
  String get trainingExpiring;

  /// No description provided for @trainingExpired.
  ///
  /// In en, this message translates to:
  /// **'expired'**
  String get trainingExpired;

  /// No description provided for @trainingUnknown.
  ///
  /// In en, this message translates to:
  /// **'unknown'**
  String get trainingUnknown;

  /// No description provided for @orgTraining.
  ///
  /// In en, this message translates to:
  /// **'Training: {status}'**
  String orgTraining(String status);

  /// No description provided for @orgCapacity.
  ///
  /// In en, this message translates to:
  /// **'Capacity (maximum number of people)'**
  String get orgCapacity;

  /// No description provided for @orgAddress.
  ///
  /// In en, this message translates to:
  /// **'Address'**
  String get orgAddress;

  /// No description provided for @orgClassification.
  ///
  /// In en, this message translates to:
  /// **'Classification'**
  String get orgClassification;

  /// No description provided for @orgClassificationProvisional.
  ///
  /// In en, this message translates to:
  /// **'Provisional: computed with thresholds still to be validated by the Civil Protection.'**
  String get orgClassificationProvisional;

  /// No description provided for @orgAlerts.
  ///
  /// In en, this message translates to:
  /// **'Alerts'**
  String get orgAlerts;

  /// No description provided for @orgAlertsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 alert} other{{count} alerts}}'**
  String orgAlertsCount(int count);

  /// No description provided for @orgNoAlerts.
  ///
  /// In en, this message translates to:
  /// **'No alert'**
  String get orgNoAlerts;

  /// No description provided for @orgSafetyTeam.
  ///
  /// In en, this message translates to:
  /// **'Safety team'**
  String get orgSafetyTeam;

  /// No description provided for @orgTeamEmpty.
  ///
  /// In en, this message translates to:
  /// **'No safety team registered.'**
  String get orgTeamEmpty;

  /// No description provided for @orgCallMember.
  ///
  /// In en, this message translates to:
  /// **'Call {name}'**
  String orgCallMember(String name);

  /// No description provided for @orgHazmatTitle.
  ///
  /// In en, this message translates to:
  /// **'Hazardous materials ({count})'**
  String orgHazmatTitle(int count);

  /// No description provided for @orgHazmatEmpty.
  ///
  /// In en, this message translates to:
  /// **'No hazardous material registered.'**
  String get orgHazmatEmpty;

  /// No description provided for @orgUnNumber.
  ///
  /// In en, this message translates to:
  /// **'UN {number}'**
  String orgUnNumber(String number);

  /// No description provided for @orgOfflineCopy.
  ///
  /// In en, this message translates to:
  /// **'Offline: copy saved on {date}.'**
  String orgOfflineCopy(String date);

  /// No description provided for @orgPortalNote.
  ///
  /// In en, this message translates to:
  /// **'Detailed editing of the institution (card, team, hazardous materials, documents, certificate) is done on the institutions portal.'**
  String get orgPortalNote;

  /// No description provided for @orgOpenPortal.
  ///
  /// In en, this message translates to:
  /// **'Open the portal'**
  String get orgOpenPortal;

  /// No description provided for @orgPortalUnavailable.
  ///
  /// In en, this message translates to:
  /// **'The portal could not be opened on this phone.'**
  String get orgPortalUnavailable;

  /// No description provided for @orgRecentReports.
  ///
  /// In en, this message translates to:
  /// **'Recent reports of the institution'**
  String get orgRecentReports;

  /// No description provided for @orgReportsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No report yet.'**
  String get orgReportsEmpty;

  /// No description provided for @orgReportBy.
  ///
  /// In en, this message translates to:
  /// **'By {name}'**
  String orgReportBy(String name);

  /// No description provided for @notificationsTitle.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notificationsTitle;

  /// No description provided for @activeAlertsTitle.
  ///
  /// In en, this message translates to:
  /// **'Alerts in force'**
  String get activeAlertsTitle;

  /// No description provided for @activeAlertsNone.
  ///
  /// In en, this message translates to:
  /// **'No alert in force for your area.'**
  String get activeAlertsNone;

  /// No description provided for @inboxTitle.
  ///
  /// In en, this message translates to:
  /// **'Messages'**
  String get inboxTitle;

  /// No description provided for @inboxEmpty.
  ///
  /// In en, this message translates to:
  /// **'No message yet.'**
  String get inboxEmpty;

  /// No description provided for @inboxNoIdentity.
  ///
  /// In en, this message translates to:
  /// **'Choose how to use the app to receive messages.'**
  String get inboxNoIdentity;

  /// No description provided for @inboxLoadMore.
  ///
  /// In en, this message translates to:
  /// **'Show older messages'**
  String get inboxLoadMore;

  /// No description provided for @inboxAlertActive.
  ///
  /// In en, this message translates to:
  /// **'Alert in force'**
  String get inboxAlertActive;

  /// No description provided for @inboxAlertEnded.
  ///
  /// In en, this message translates to:
  /// **'Alert ended'**
  String get inboxAlertEnded;

  /// No description provided for @alertTitle.
  ///
  /// In en, this message translates to:
  /// **'Alert'**
  String get alertTitle;

  /// No description provided for @alertOpen.
  ///
  /// In en, this message translates to:
  /// **'Open the alert'**
  String get alertOpen;

  /// No description provided for @alertUntil.
  ///
  /// In en, this message translates to:
  /// **'Until {time}'**
  String alertUntil(String time);

  /// No description provided for @alertPublishedAt.
  ///
  /// In en, this message translates to:
  /// **'Issued {time}'**
  String alertPublishedAt(String time);

  /// No description provided for @alertNotActive.
  ///
  /// In en, this message translates to:
  /// **'This alert has ended or was lifted.'**
  String get alertNotActive;

  /// No description provided for @alertAreaNational.
  ///
  /// In en, this message translates to:
  /// **'Whole country'**
  String get alertAreaNational;

  /// No description provided for @alertAreaZone.
  ///
  /// In en, this message translates to:
  /// **'Zone drawn on the map'**
  String get alertAreaZone;

  /// No description provided for @alertAreaGouvernorats.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 gouvernorate} other{{count} gouvernorates}}'**
  String alertAreaGouvernorats(int count);

  /// No description provided for @severityHigh.
  ///
  /// In en, this message translates to:
  /// **'Red alert'**
  String get severityHigh;

  /// No description provided for @severityMedium.
  ///
  /// In en, this message translates to:
  /// **'Orange alert'**
  String get severityMedium;

  /// No description provided for @severityLow.
  ///
  /// In en, this message translates to:
  /// **'Yellow alert'**
  String get severityLow;

  /// No description provided for @hazardHeavyRain.
  ///
  /// In en, this message translates to:
  /// **'Heavy rain'**
  String get hazardHeavyRain;

  /// No description provided for @hazardFlood.
  ///
  /// In en, this message translates to:
  /// **'Flood'**
  String get hazardFlood;

  /// No description provided for @hazardStorm.
  ///
  /// In en, this message translates to:
  /// **'Storm'**
  String get hazardStorm;

  /// No description provided for @hazardWind.
  ///
  /// In en, this message translates to:
  /// **'Strong wind'**
  String get hazardWind;

  /// No description provided for @hazardHeatWave.
  ///
  /// In en, this message translates to:
  /// **'Heat wave'**
  String get hazardHeatWave;

  /// No description provided for @hazardColdWave.
  ///
  /// In en, this message translates to:
  /// **'Cold wave'**
  String get hazardColdWave;

  /// No description provided for @hazardSea.
  ///
  /// In en, this message translates to:
  /// **'Rough sea'**
  String get hazardSea;

  /// No description provided for @hazardForestFire.
  ///
  /// In en, this message translates to:
  /// **'Forest fire'**
  String get hazardForestFire;

  /// No description provided for @hazardChemical.
  ///
  /// In en, this message translates to:
  /// **'Chemical hazard'**
  String get hazardChemical;

  /// No description provided for @hazardOther.
  ///
  /// In en, this message translates to:
  /// **'Other hazard'**
  String get hazardOther;

  /// No description provided for @topicActivity.
  ///
  /// In en, this message translates to:
  /// **'Activity'**
  String get topicActivity;

  /// No description provided for @topicAwareness.
  ///
  /// In en, this message translates to:
  /// **'Awareness'**
  String get topicAwareness;

  /// No description provided for @topicTraining.
  ///
  /// In en, this message translates to:
  /// **'Training'**
  String get topicTraining;

  /// No description provided for @topicWorldDay.
  ///
  /// In en, this message translates to:
  /// **'World day'**
  String get topicWorldDay;

  /// No description provided for @topicOther.
  ///
  /// In en, this message translates to:
  /// **'Information'**
  String get topicOther;

  /// No description provided for @settingsAlerts.
  ///
  /// In en, this message translates to:
  /// **'Alerts and notifications'**
  String get settingsAlerts;

  /// No description provided for @settingsLocationAlerts.
  ///
  /// In en, this message translates to:
  /// **'Alerts where I am'**
  String get settingsLocationAlerts;

  /// No description provided for @settingsLocationAlertsHelp.
  ///
  /// In en, this message translates to:
  /// **'Uses the phone’s approximate position (about 1 km) to send you alerts for the area you are in.'**
  String get settingsLocationAlertsHelp;

  /// No description provided for @channelAlerts.
  ///
  /// In en, this message translates to:
  /// **'Urgent alerts'**
  String get channelAlerts;

  /// No description provided for @channelAlertsDesc.
  ///
  /// In en, this message translates to:
  /// **'Civil Protection alerts and volunteer call-outs.'**
  String get channelAlertsDesc;

  /// No description provided for @channelGeneral.
  ///
  /// In en, this message translates to:
  /// **'Information'**
  String get channelGeneral;

  /// No description provided for @channelGeneralDesc.
  ///
  /// In en, this message translates to:
  /// **'Follow-up of your reports and information messages.'**
  String get channelGeneralDesc;

  /// No description provided for @tipsTitle.
  ///
  /// In en, this message translates to:
  /// **'Safety tips'**
  String get tipsTitle;

  /// No description provided for @tipsIntro.
  ///
  /// In en, this message translates to:
  /// **'What to do and what to avoid. Available without connection.'**
  String get tipsIntro;

  /// No description provided for @tipsDo.
  ///
  /// In en, this message translates to:
  /// **'Do'**
  String get tipsDo;

  /// No description provided for @tipsDont.
  ///
  /// In en, this message translates to:
  /// **'Don’t'**
  String get tipsDont;

  /// No description provided for @tipEarthquake.
  ///
  /// In en, this message translates to:
  /// **'Earthquake'**
  String get tipEarthquake;

  /// No description provided for @homeTipsDesc.
  ///
  /// In en, this message translates to:
  /// **'The right actions in an emergency, even offline.'**
  String get homeTipsDesc;

  /// No description provided for @volunteerTitle.
  ///
  /// In en, this message translates to:
  /// **'Volunteering'**
  String get volunteerTitle;

  /// No description provided for @homeVolunteerDesc.
  ///
  /// In en, this message translates to:
  /// **'Join the volunteers and answer call-outs near you.'**
  String get homeVolunteerDesc;

  /// No description provided for @volunteerIntro.
  ///
  /// In en, this message translates to:
  /// **'Volunteers help the Civil Protection teams in emergencies, according to their skills. Your application is reviewed before you can be called out.'**
  String get volunteerIntro;

  /// No description provided for @volunteerApply.
  ///
  /// In en, this message translates to:
  /// **'Apply as a volunteer'**
  String get volunteerApply;

  /// No description provided for @volunteerApplication.
  ///
  /// In en, this message translates to:
  /// **'My application'**
  String get volunteerApplication;

  /// No description provided for @volunteerStatusPending.
  ///
  /// In en, this message translates to:
  /// **'Under review'**
  String get volunteerStatusPending;

  /// No description provided for @volunteerStatusApproved.
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get volunteerStatusApproved;

  /// No description provided for @volunteerStatusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get volunteerStatusRejected;

  /// No description provided for @volunteerStatusSuspended.
  ///
  /// In en, this message translates to:
  /// **'Suspended'**
  String get volunteerStatusSuspended;

  /// No description provided for @volunteerStatusWithdrawn.
  ///
  /// In en, this message translates to:
  /// **'Withdrawn'**
  String get volunteerStatusWithdrawn;

  /// No description provided for @volunteerPendingHelp.
  ///
  /// In en, this message translates to:
  /// **'Your application will be reviewed by the Civil Protection. You will receive an e-mail with the decision.'**
  String get volunteerPendingHelp;

  /// No description provided for @volunteerApprovedHelp.
  ///
  /// In en, this message translates to:
  /// **'You can declare yourself ready and receive call-outs near you.'**
  String get volunteerApprovedHelp;

  /// No description provided for @volunteerRejectedHelp.
  ///
  /// In en, this message translates to:
  /// **'Your application was not accepted. You can correct it and apply again.'**
  String get volunteerRejectedHelp;

  /// No description provided for @volunteerSuspendedHelp.
  ///
  /// In en, this message translates to:
  /// **'Your volunteering is suspended: you will not receive call-outs.'**
  String get volunteerSuspendedHelp;

  /// No description provided for @volunteerWithdrawnHelp.
  ///
  /// In en, this message translates to:
  /// **'You have withdrawn. You can apply again at any time.'**
  String get volunteerWithdrawnHelp;

  /// No description provided for @volunteerReason.
  ///
  /// In en, this message translates to:
  /// **'Reason: {reason}'**
  String volunteerReason(String reason);

  /// No description provided for @volunteerPeriodFrom.
  ///
  /// In en, this message translates to:
  /// **'From {from}'**
  String volunteerPeriodFrom(String from);

  /// No description provided for @volunteerPeriodRange.
  ///
  /// In en, this message translates to:
  /// **'From {from} to {to}'**
  String volunteerPeriodRange(String from, String to);

  /// No description provided for @availabilityContinuous.
  ///
  /// In en, this message translates to:
  /// **'Continuous'**
  String get availabilityContinuous;

  /// No description provided for @availabilityIntermittent.
  ///
  /// In en, this message translates to:
  /// **'Intermittent'**
  String get availabilityIntermittent;

  /// No description provided for @volunteerEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit my application'**
  String get volunteerEdit;

  /// No description provided for @volunteerResubmit.
  ///
  /// In en, this message translates to:
  /// **'Apply again'**
  String get volunteerResubmit;

  /// No description provided for @volunteerWithdraw.
  ///
  /// In en, this message translates to:
  /// **'Withdraw'**
  String get volunteerWithdraw;

  /// No description provided for @volunteerWithdrawConfirm.
  ///
  /// In en, this message translates to:
  /// **'You will no longer receive call-outs and your position will no longer be shared.'**
  String get volunteerWithdrawConfirm;

  /// No description provided for @volunteerReady.
  ///
  /// In en, this message translates to:
  /// **'Ready to help'**
  String get volunteerReady;

  /// No description provided for @volunteerReadyHelp.
  ///
  /// In en, this message translates to:
  /// **'While you are ready, the Civil Protection sees your position to call you out.'**
  String get volunteerReadyHelp;

  /// No description provided for @volunteerReadyUntil.
  ///
  /// In en, this message translates to:
  /// **'Ready until {time}'**
  String volunteerReadyUntil(String time);

  /// No description provided for @volunteerReadyFor.
  ///
  /// In en, this message translates to:
  /// **'For'**
  String get volunteerReadyFor;

  /// No description provided for @hoursShort.
  ///
  /// In en, this message translates to:
  /// **'{hours} h'**
  String hoursShort(int hours);

  /// No description provided for @volunteerLocationPrivacy.
  ///
  /// In en, this message translates to:
  /// **'Your position is shared only while you are ready, is deleted when readiness ends and is never archived.'**
  String get volunteerLocationPrivacy;

  /// No description provided for @volunteerNoFix.
  ///
  /// In en, this message translates to:
  /// **'Your position could not be determined. Try again outdoors.'**
  String get volunteerNoFix;

  /// No description provided for @volunteerSkills.
  ///
  /// In en, this message translates to:
  /// **'Skills'**
  String get volunteerSkills;

  /// No description provided for @volunteerSkillsRequired.
  ///
  /// In en, this message translates to:
  /// **'Choose at least one skill.'**
  String get volunteerSkillsRequired;

  /// No description provided for @volunteerOtherSkill.
  ///
  /// In en, this message translates to:
  /// **'Other skill'**
  String get volunteerOtherSkill;

  /// No description provided for @volunteerAvailability.
  ///
  /// In en, this message translates to:
  /// **'Availability'**
  String get volunteerAvailability;

  /// No description provided for @volunteerPeriod.
  ///
  /// In en, this message translates to:
  /// **'Volunteering period'**
  String get volunteerPeriod;

  /// No description provided for @volunteerFrom.
  ///
  /// In en, this message translates to:
  /// **'Start'**
  String get volunteerFrom;

  /// No description provided for @volunteerTo.
  ///
  /// In en, this message translates to:
  /// **'End'**
  String get volunteerTo;

  /// No description provided for @volunteerNoEnd.
  ///
  /// In en, this message translates to:
  /// **'No end date'**
  String get volunteerNoEnd;

  /// No description provided for @volunteerNotes.
  ///
  /// In en, this message translates to:
  /// **'Notes (optional)'**
  String get volunteerNotes;

  /// No description provided for @volunteerProfileNote.
  ///
  /// In en, this message translates to:
  /// **'Your name, phone and gouvernorate are taken from your profile.'**
  String get volunteerProfileNote;

  /// No description provided for @volunteerSubmit.
  ///
  /// In en, this message translates to:
  /// **'Send my application'**
  String get volunteerSubmit;

  /// No description provided for @volunteerSubmitted.
  ///
  /// In en, this message translates to:
  /// **'Application sent.'**
  String get volunteerSubmitted;

  /// No description provided for @fieldRequired.
  ///
  /// In en, this message translates to:
  /// **'Required'**
  String get fieldRequired;

  /// No description provided for @skillFirstAid.
  ///
  /// In en, this message translates to:
  /// **'First aid'**
  String get skillFirstAid;

  /// No description provided for @skillDiving.
  ///
  /// In en, this message translates to:
  /// **'Diving'**
  String get skillDiving;

  /// No description provided for @skillHeavyVehicles.
  ///
  /// In en, this message translates to:
  /// **'Heavy vehicles'**
  String get skillHeavyVehicles;

  /// No description provided for @skillFirefighting.
  ///
  /// In en, this message translates to:
  /// **'Firefighting'**
  String get skillFirefighting;

  /// No description provided for @skillSearchRescue.
  ///
  /// In en, this message translates to:
  /// **'Search and rescue'**
  String get skillSearchRescue;

  /// No description provided for @skillLogistics.
  ///
  /// In en, this message translates to:
  /// **'Logistics'**
  String get skillLogistics;

  /// No description provided for @skillMedical.
  ///
  /// In en, this message translates to:
  /// **'Medical'**
  String get skillMedical;

  /// No description provided for @skillOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get skillOther;

  /// No description provided for @calloutsTitle.
  ///
  /// In en, this message translates to:
  /// **'Call-outs'**
  String get calloutsTitle;

  /// No description provided for @calloutsDesc.
  ///
  /// In en, this message translates to:
  /// **'Requests for help near you.'**
  String get calloutsDesc;

  /// No description provided for @calloutsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No call-out at the moment.'**
  String get calloutsEmpty;

  /// No description provided for @calloutAccept.
  ///
  /// In en, this message translates to:
  /// **'I’m going'**
  String get calloutAccept;

  /// No description provided for @calloutDecline.
  ///
  /// In en, this message translates to:
  /// **'Not available'**
  String get calloutDecline;

  /// No description provided for @calloutArrived.
  ///
  /// In en, this message translates to:
  /// **'I’m on site'**
  String get calloutArrived;

  /// No description provided for @calloutEtaLabel.
  ///
  /// In en, this message translates to:
  /// **'Arrival in (minutes)'**
  String get calloutEtaLabel;

  /// No description provided for @calloutEta.
  ///
  /// In en, this message translates to:
  /// **'Arrival in {minutes} min'**
  String calloutEta(int minutes);

  /// No description provided for @calloutSkill.
  ///
  /// In en, this message translates to:
  /// **'Skill: {skill}'**
  String calloutSkill(String skill);

  /// No description provided for @calloutDistance.
  ///
  /// In en, this message translates to:
  /// **'At {distance}'**
  String calloutDistance(String distance);

  /// No description provided for @calloutAnswerSent.
  ///
  /// In en, this message translates to:
  /// **'Awaiting your answer'**
  String get calloutAnswerSent;

  /// No description provided for @calloutAnswerAccepted.
  ///
  /// In en, this message translates to:
  /// **'On the way'**
  String get calloutAnswerAccepted;

  /// No description provided for @calloutAnswerDeclined.
  ///
  /// In en, this message translates to:
  /// **'Declined'**
  String get calloutAnswerDeclined;

  /// No description provided for @calloutAnswerExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired'**
  String get calloutAnswerExpired;

  /// No description provided for @calloutAnswerArrived.
  ///
  /// In en, this message translates to:
  /// **'On site'**
  String get calloutAnswerArrived;

  /// No description provided for @distanceMeters.
  ///
  /// In en, this message translates to:
  /// **'{meters} m'**
  String distanceMeters(int meters);

  /// No description provided for @distanceKm.
  ///
  /// In en, this message translates to:
  /// **'{km} km'**
  String distanceKm(String km);

  /// No description provided for @errorRegistrationRequired.
  ///
  /// In en, this message translates to:
  /// **'You need an account to volunteer.'**
  String get errorRegistrationRequired;

  /// No description provided for @errorNotVolunteer.
  ///
  /// In en, this message translates to:
  /// **'You have not applied as a volunteer.'**
  String get errorNotVolunteer;

  /// No description provided for @errorProfileIncomplete.
  ///
  /// In en, this message translates to:
  /// **'Complete your profile (phone and gouvernorate) first.'**
  String get errorProfileIncomplete;

  /// No description provided for @errorInvalidPeriod.
  ///
  /// In en, this message translates to:
  /// **'The period is invalid (end before start or more than two years ahead).'**
  String get errorInvalidPeriod;

  /// No description provided for @errorVolunteerNotApproved.
  ///
  /// In en, this message translates to:
  /// **'Your volunteer application is not approved.'**
  String get errorVolunteerNotApproved;

  /// No description provided for @errorOutsidePeriod.
  ///
  /// In en, this message translates to:
  /// **'Today is outside your volunteering period.'**
  String get errorOutsidePeriod;

  /// No description provided for @errorNotReady.
  ///
  /// In en, this message translates to:
  /// **'You are no longer ready.'**
  String get errorNotReady;

  /// No description provided for @errorLocationRequired.
  ///
  /// In en, this message translates to:
  /// **'Your position is needed to be ready.'**
  String get errorLocationRequired;

  /// No description provided for @errorCalloutClosed.
  ///
  /// In en, this message translates to:
  /// **'This call-out is closed.'**
  String get errorCalloutClosed;

  /// No description provided for @errorEtaRequired.
  ///
  /// In en, this message translates to:
  /// **'Enter a time between 1 and 600 minutes.'**
  String get errorEtaRequired;

  /// No description provided for @errorInvalidTransition.
  ///
  /// In en, this message translates to:
  /// **'This action is no longer possible.'**
  String get errorInvalidTransition;

  /// No description provided for @errorVersionConflict.
  ///
  /// In en, this message translates to:
  /// **'Your data changed meanwhile. Reload and try again.'**
  String get errorVersionConflict;

  /// No description provided for @locationServiceDisabled.
  ///
  /// In en, this message translates to:
  /// **'Location is turned off on this phone.'**
  String get locationServiceDisabled;

  /// No description provided for @volunteerLocationDenied.
  ///
  /// In en, this message translates to:
  /// **'Allow location access to declare yourself ready.'**
  String get volunteerLocationDenied;
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
      <String>['ar', 'en', 'fr'].contains(locale.languageCode);

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
    case 'fr':
      return AppLocalizationsFr();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
