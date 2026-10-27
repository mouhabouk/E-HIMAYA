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
  /// **'Terms of use'**
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

  /// No description provided for @charterCheckbox.
  ///
  /// In en, this message translates to:
  /// **'I have read and accept the terms of use, and I understand that a deliberate false report makes me legally liable.'**
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
  /// **'Register your institution from the phone: your number and an SMS code, then your work e-mail and a code sent to it, then the card with the tax ID or the RNE number. The account stays “under review” until the administration confirms it.'**
  String get institutionBody;

  /// No description provided for @institutionLogin.
  ///
  /// In en, this message translates to:
  /// **'My institution has an account: sign in'**
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
  /// **'Terms of use'**
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
  /// **'Please accept the terms of use before reporting.'**
  String get errorConsentRequired;

  /// No description provided for @errorRateLimited.
  ///
  /// In en, this message translates to:
  /// **'Too many requests. Please wait a moment.'**
  String get errorRateLimited;

  /// No description provided for @errorUnknownCharterVersion.
  ///
  /// In en, this message translates to:
  /// **'The terms of use have changed. Please read them again.'**
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

  /// No description provided for @pushSimulationBadge.
  ///
  /// In en, this message translates to:
  /// **'Simulation mode'**
  String get pushSimulationBadge;

  /// No description provided for @pushSimulationHelp.
  ///
  /// In en, this message translates to:
  /// **'Push notifications come from the local simulator, not from Firebase. Nothing is delivered by a real push service.'**
  String get pushSimulationHelp;

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

  /// No description provided for @locationConsentTitle.
  ///
  /// In en, this message translates to:
  /// **'Share your position while ready?'**
  String get locationConsentTitle;

  /// No description provided for @locationConsentBody.
  ///
  /// In en, this message translates to:
  /// **'While you are ready, your position is sent to the Civil Protection of your gouvernorat so that it can call out the volunteers closest to an incident.\n\n• Who sees it: Civil Protection operators, on a map rounded to about 100 m; distances are rounded too.\n• How long: only while you are ready. It is kept in memory, deleted when readiness ends and never archived.\n• You can withdraw this consent at any time in this screen; readiness then ends at once.'**
  String get locationConsentBody;

  /// No description provided for @locationConsentAccept.
  ///
  /// In en, this message translates to:
  /// **'I agree'**
  String get locationConsentAccept;

  /// No description provided for @locationConsentSwitch.
  ///
  /// In en, this message translates to:
  /// **'Share my position while ready'**
  String get locationConsentSwitch;

  /// No description provided for @locationConsentSwitchOn.
  ///
  /// In en, this message translates to:
  /// **'Consent given. Turning it off ends readiness and deletes your position.'**
  String get locationConsentSwitchOn;

  /// No description provided for @locationConsentSwitchOff.
  ///
  /// In en, this message translates to:
  /// **'Required to be ready.'**
  String get locationConsentSwitchOff;

  /// No description provided for @locationConsentWithdrawn.
  ///
  /// In en, this message translates to:
  /// **'Consent withdrawn: your position is deleted.'**
  String get locationConsentWithdrawn;

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

  /// No description provided for @errorLocationConsentRequired.
  ///
  /// In en, this message translates to:
  /// **'Agree to share your position before being ready.'**
  String get errorLocationConsentRequired;

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

  /// No description provided for @actionNotNow.
  ///
  /// In en, this message translates to:
  /// **'Not now'**
  String get actionNotNow;

  /// No description provided for @channelCritical.
  ///
  /// In en, this message translates to:
  /// **'Critical official alerts'**
  String get channelCritical;

  /// No description provided for @channelCriticalDesc.
  ///
  /// In en, this message translates to:
  /// **'The most severe alerts of the civil protection, heard even in Do Not Disturb (only if you allowed it).'**
  String get channelCriticalDesc;

  /// No description provided for @alertCheckTitle.
  ///
  /// In en, this message translates to:
  /// **'Alert delivery check'**
  String get alertCheckTitle;

  /// No description provided for @alertCheckSubtitle.
  ///
  /// In en, this message translates to:
  /// **'What could keep alerts from reaching you'**
  String get alertCheckSubtitle;

  /// No description provided for @alertCheckIntro.
  ///
  /// In en, this message translates to:
  /// **'Official alerts use their own sound, vibration and channel, separate from other apps. Some phone settings can still silence them: check them here.'**
  String get alertCheckIntro;

  /// No description provided for @alertCheckAllGood.
  ///
  /// In en, this message translates to:
  /// **'Nothing blocks official alerts on this phone.'**
  String get alertCheckAllGood;

  /// No description provided for @alertCheckFix.
  ///
  /// In en, this message translates to:
  /// **'Fix'**
  String get alertCheckFix;

  /// No description provided for @alertChannelSettings.
  ///
  /// In en, this message translates to:
  /// **'Alert sound and vibration settings'**
  String get alertChannelSettings;

  /// No description provided for @issueNotificationsOff.
  ///
  /// In en, this message translates to:
  /// **'Notifications are turned off'**
  String get issueNotificationsOff;

  /// No description provided for @issueNotificationsOffHelp.
  ///
  /// In en, this message translates to:
  /// **'Without notifications you will not receive alerts or call-outs.'**
  String get issueNotificationsOffHelp;

  /// No description provided for @issueChannelMuted.
  ///
  /// In en, this message translates to:
  /// **'Official alerts are muted'**
  String get issueChannelMuted;

  /// No description provided for @issueChannelMutedHelp.
  ///
  /// In en, this message translates to:
  /// **'The “Official alerts” category was lowered in the phone settings: it no longer rings nor pops up.'**
  String get issueChannelMutedHelp;

  /// No description provided for @issueDnd.
  ///
  /// In en, this message translates to:
  /// **'Do Not Disturb is on'**
  String get issueDnd;

  /// No description provided for @issueDndHelp.
  ///
  /// In en, this message translates to:
  /// **'Alerts may arrive silently. You can let the most severe official alerts through.'**
  String get issueDndHelp;

  /// No description provided for @issueFullScreen.
  ///
  /// In en, this message translates to:
  /// **'Full-screen alerts are not allowed'**
  String get issueFullScreen;

  /// No description provided for @issueFullScreenHelp.
  ///
  /// In en, this message translates to:
  /// **'The most severe alerts should open over the lock screen. Allow “full-screen notifications” for e-Himaya.'**
  String get issueFullScreenHelp;

  /// No description provided for @issueBatteryOptimized.
  ///
  /// In en, this message translates to:
  /// **'Battery optimisation may delay call-outs'**
  String get issueBatteryOptimized;

  /// No description provided for @issueBatteryOptimizedHelp.
  ///
  /// In en, this message translates to:
  /// **'You are on call: the phone may put the app to sleep and delay call-outs. Exempt e-Himaya while you volunteer.'**
  String get issueBatteryOptimizedHelp;

  /// No description provided for @issuePushUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Push notifications are unavailable'**
  String get issuePushUnavailable;

  /// No description provided for @issuePushUnavailableHelp.
  ///
  /// In en, this message translates to:
  /// **'This phone cannot receive pushes (for example without Google services): alerts are checked only while the app is open.'**
  String get issuePushUnavailableHelp;

  /// No description provided for @testAlertButton.
  ///
  /// In en, this message translates to:
  /// **'Send a test alert'**
  String get testAlertButton;

  /// No description provided for @testAlertTitle.
  ///
  /// In en, this message translates to:
  /// **'Test — official alert'**
  String get testAlertTitle;

  /// No description provided for @testAlertBody.
  ///
  /// In en, this message translates to:
  /// **'This is what an alert from the civil protection looks and sounds like. No action needed.'**
  String get testAlertBody;

  /// No description provided for @testAlertSent.
  ///
  /// In en, this message translates to:
  /// **'Test alert sent.'**
  String get testAlertSent;

  /// No description provided for @criticalAlertsTitle.
  ///
  /// In en, this message translates to:
  /// **'Critical alerts in Do Not Disturb'**
  String get criticalAlertsTitle;

  /// No description provided for @criticalAlertsIntro.
  ///
  /// In en, this message translates to:
  /// **'You can let the most severe official alerts (danger to life: flood, fire, evacuation) ring even when Do Not Disturb is on.'**
  String get criticalAlertsIntro;

  /// No description provided for @criticalAlertsHow.
  ///
  /// In en, this message translates to:
  /// **'Only alerts of the highest severity use this. The phone will ask you to give e-Himaya “Do Not Disturb access”; you can turn this off here at any time.'**
  String get criticalAlertsHow;

  /// No description provided for @criticalAlertsEnable.
  ///
  /// In en, this message translates to:
  /// **'Allow critical alerts'**
  String get criticalAlertsEnable;

  /// No description provided for @criticalAlertsEnabled.
  ///
  /// In en, this message translates to:
  /// **'Critical alerts can ring in Do Not Disturb.'**
  String get criticalAlertsEnabled;

  /// No description provided for @criticalAlertsDisable.
  ///
  /// In en, this message translates to:
  /// **'Turn off'**
  String get criticalAlertsDisable;

  /// No description provided for @batteryExemptTitle.
  ///
  /// In en, this message translates to:
  /// **'Keep call-outs on time'**
  String get batteryExemptTitle;

  /// No description provided for @batteryExemptBody.
  ///
  /// In en, this message translates to:
  /// **'You are on call. To save battery, the phone may put e-Himaya to sleep and deliver call-outs late. Exempting the app from battery optimisation avoids this; e-Himaya itself only uses location while it is open and you are ready.'**
  String get batteryExemptBody;

  /// No description provided for @batteryExemptAllow.
  ///
  /// In en, this message translates to:
  /// **'Exempt the app'**
  String get batteryExemptAllow;

  /// No description provided for @batterySaverTitle.
  ///
  /// In en, this message translates to:
  /// **'Battery saver'**
  String get batterySaverTitle;

  /// No description provided for @batterySaverHelp.
  ///
  /// In en, this message translates to:
  /// **'Checks less often for updates, shares your volunteer position less often and keeps large videos for Wi-Fi. Alerts and SOS are never delayed.'**
  String get batterySaverHelp;

  /// No description provided for @batterySaverAuto.
  ///
  /// In en, this message translates to:
  /// **'Automatic (low battery)'**
  String get batterySaverAuto;

  /// No description provided for @batterySaverOn.
  ///
  /// In en, this message translates to:
  /// **'Always on'**
  String get batterySaverOn;

  /// No description provided for @batterySaverOff.
  ///
  /// In en, this message translates to:
  /// **'Off'**
  String get batterySaverOff;

  /// No description provided for @batterySaverActive.
  ///
  /// In en, this message translates to:
  /// **'active'**
  String get batterySaverActive;

  /// No description provided for @batterySaverInactive.
  ///
  /// In en, this message translates to:
  /// **'inactive'**
  String get batterySaverInactive;

  /// No description provided for @batteryLevel.
  ///
  /// In en, this message translates to:
  /// **'battery {percent}%'**
  String batteryLevel(int percent);

  /// No description provided for @pushCalloutTitle.
  ///
  /// In en, this message translates to:
  /// **'Call-out'**
  String get pushCalloutTitle;

  /// No description provided for @pushOpenToSee.
  ///
  /// In en, this message translates to:
  /// **'Open the app to see the details.'**
  String get pushOpenToSee;

  /// No description provided for @pushReportTitle.
  ///
  /// In en, this message translates to:
  /// **'Report {code}'**
  String pushReportTitle(String code);

  /// No description provided for @myDataTitle.
  ///
  /// In en, this message translates to:
  /// **'My data'**
  String get myDataTitle;

  /// No description provided for @myDataSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Download a copy or delete your account'**
  String get myDataSubtitle;

  /// No description provided for @myDataIntro.
  ///
  /// In en, this message translates to:
  /// **'You can get a copy of all the personal data e-Himaya holds about you (profile, consents, reports, volunteer record, devices), at most 3 times a day. Keep the file private: it contains personal data.'**
  String get myDataIntro;

  /// No description provided for @myDataDownload.
  ///
  /// In en, this message translates to:
  /// **'Download my data'**
  String get myDataDownload;

  /// No description provided for @myDataCopy.
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get myDataCopy;

  /// No description provided for @myDataCopied.
  ///
  /// In en, this message translates to:
  /// **'Copied to the clipboard.'**
  String get myDataCopied;

  /// No description provided for @myDataSave.
  ///
  /// In en, this message translates to:
  /// **'Save as file'**
  String get myDataSave;

  /// No description provided for @myDataSaved.
  ///
  /// In en, this message translates to:
  /// **'Saved: {path}'**
  String myDataSaved(String path);

  /// No description provided for @myDataSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'The file could not be saved.'**
  String get myDataSaveFailed;

  /// No description provided for @deleteAccountTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete my account'**
  String get deleteAccountTitle;

  /// No description provided for @deleteAccountSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Your personal data is erased; this cannot be undone.'**
  String get deleteAccountSubtitle;

  /// No description provided for @deleteAccountExplain.
  ///
  /// In en, this message translates to:
  /// **'Your profile, consents, devices and volunteer record are erased and your account is closed. Reports you sent are kept without your name, as the law requires. Everything stored on this phone is wiped and the app starts again from the beginning.'**
  String get deleteAccountExplain;

  /// No description provided for @deleteAccountExplainAnonymous.
  ///
  /// In en, this message translates to:
  /// **'This phone\'s anonymous identity is deleted on the server. Reports you sent are kept without any link to this phone, as the law requires. Everything stored on this phone is wiped and the app starts again from the beginning.'**
  String get deleteAccountExplainAnonymous;

  /// No description provided for @deleteAccountWord.
  ///
  /// In en, this message translates to:
  /// **'DELETE'**
  String get deleteAccountWord;

  /// No description provided for @deleteAccountTypeWord.
  ///
  /// In en, this message translates to:
  /// **'Type {word} to confirm'**
  String deleteAccountTypeWord(String word);

  /// No description provided for @deleteAccountConfirm.
  ///
  /// In en, this message translates to:
  /// **'Delete permanently'**
  String get deleteAccountConfirm;

  /// No description provided for @deleteAccountDone.
  ///
  /// In en, this message translates to:
  /// **'Your account was deleted.'**
  String get deleteAccountDone;

  /// No description provided for @deleteAccountLastAdmin.
  ///
  /// In en, this message translates to:
  /// **'You are the last administrator of an institution. Hand the administration over to another member first, then delete your account.'**
  String get deleteAccountLastAdmin;

  /// No description provided for @lockedAlertOpenApp.
  ///
  /// In en, this message translates to:
  /// **'Unlock to open the app'**
  String get lockedAlertOpenApp;

  /// No description provided for @liveBadge.
  ///
  /// In en, this message translates to:
  /// **'LIVE'**
  String get liveBadge;

  /// No description provided for @homeLive.
  ///
  /// In en, this message translates to:
  /// **'Go live'**
  String get homeLive;

  /// No description provided for @homeLiveDesc.
  ///
  /// In en, this message translates to:
  /// **'Show the incident live to the Civil Protection.'**
  String get homeLiveDesc;

  /// No description provided for @liveTitle.
  ///
  /// In en, this message translates to:
  /// **'Live stream'**
  String get liveTitle;

  /// No description provided for @liveIntro.
  ///
  /// In en, this message translates to:
  /// **'The camera picture and the microphone sound go live to the Civil Protection operations room, are recorded and linked to your report. Your position is sent for as long as the stream lasts.'**
  String get liveIntro;

  /// No description provided for @livePermissionRationale.
  ///
  /// In en, this message translates to:
  /// **'Streaming needs the camera, the microphone and your location. Your phone asks for permission when you start; they are used only while streaming.'**
  String get livePermissionRationale;

  /// No description provided for @liveCategoryLabel.
  ///
  /// In en, this message translates to:
  /// **'Incident type'**
  String get liveCategoryLabel;

  /// No description provided for @liveStart.
  ///
  /// In en, this message translates to:
  /// **'Start live'**
  String get liveStart;

  /// No description provided for @liveStop.
  ///
  /// In en, this message translates to:
  /// **'Stop live'**
  String get liveStop;

  /// No description provided for @liveMute.
  ///
  /// In en, this message translates to:
  /// **'Mute microphone'**
  String get liveMute;

  /// No description provided for @liveUnmute.
  ///
  /// In en, this message translates to:
  /// **'Unmute microphone'**
  String get liveUnmute;

  /// No description provided for @liveSwitchCamera.
  ///
  /// In en, this message translates to:
  /// **'Switch camera'**
  String get liveSwitchCamera;

  /// No description provided for @livePreparing.
  ///
  /// In en, this message translates to:
  /// **'Preparing the live stream…'**
  String get livePreparing;

  /// No description provided for @liveConnecting.
  ///
  /// In en, this message translates to:
  /// **'Connecting to the video server…'**
  String get liveConnecting;

  /// No description provided for @liveReconnecting.
  ///
  /// In en, this message translates to:
  /// **'Connection lost. Attempt {attempt} of {max}…'**
  String liveReconnecting(int attempt, int max);

  /// No description provided for @liveWeakNetwork.
  ///
  /// In en, this message translates to:
  /// **'The network is too weak for live video. You can record a short clip and send it instead.'**
  String get liveWeakNetwork;

  /// No description provided for @liveLocationOff.
  ///
  /// In en, this message translates to:
  /// **'Location is off: your position is not sent during the stream.'**
  String get liveLocationOff;

  /// No description provided for @liveLocationOn.
  ///
  /// In en, this message translates to:
  /// **'Position shared while live'**
  String get liveLocationOn;

  /// No description provided for @liveEndsIn.
  ///
  /// In en, this message translates to:
  /// **'The stream stops automatically in {time}'**
  String liveEndsIn(String time);

  /// No description provided for @liveReportCode.
  ///
  /// In en, this message translates to:
  /// **'Report {code}'**
  String liveReportCode(String code);

  /// No description provided for @liveSemanticsOnAir.
  ///
  /// In en, this message translates to:
  /// **'Live for {duration}'**
  String liveSemanticsOnAir(String duration);

  /// No description provided for @liveEndedTitle.
  ///
  /// In en, this message translates to:
  /// **'Live stream ended'**
  String get liveEndedTitle;

  /// No description provided for @liveEndedByUser.
  ///
  /// In en, this message translates to:
  /// **'You stopped the stream. The recording is kept with your report.'**
  String get liveEndedByUser;

  /// No description provided for @liveEndedByOperator.
  ///
  /// In en, this message translates to:
  /// **'The operator ended the stream. Thank you, the pictures arrived.'**
  String get liveEndedByOperator;

  /// No description provided for @liveEndedMaxDuration.
  ///
  /// In en, this message translates to:
  /// **'The stream reached its maximum length ({minutes} min).'**
  String liveEndedMaxDuration(int minutes);

  /// No description provided for @liveEndedByServer.
  ///
  /// In en, this message translates to:
  /// **'The platform ended the stream.'**
  String get liveEndedByServer;

  /// No description provided for @liveEndedLocked.
  ///
  /// In en, this message translates to:
  /// **'The stream stopped because the phone went back to the lock screen.'**
  String get liveEndedLocked;

  /// No description provided for @liveDuration.
  ///
  /// In en, this message translates to:
  /// **'Duration: {duration}'**
  String liveDuration(String duration);

  /// No description provided for @liveFailedTitle.
  ///
  /// In en, this message translates to:
  /// **'Live stream not possible'**
  String get liveFailedTitle;

  /// No description provided for @liveFailNoLocation.
  ///
  /// In en, this message translates to:
  /// **'Your position could not be found, so the report cannot be created. Call 198.'**
  String get liveFailNoLocation;

  /// No description provided for @liveFailReportNotSent.
  ///
  /// In en, this message translates to:
  /// **'Your report is saved on the phone and will be sent when the network is back. You can record a clip to attach to it.'**
  String get liveFailReportNotSent;

  /// No description provided for @liveFailPermission.
  ///
  /// In en, this message translates to:
  /// **'Camera or microphone access was refused. Allow it in the phone settings to stream.'**
  String get liveFailPermission;

  /// No description provided for @liveFailCamera.
  ///
  /// In en, this message translates to:
  /// **'The camera is not available (another app may be using it).'**
  String get liveFailCamera;

  /// No description provided for @liveFailConnection.
  ///
  /// In en, this message translates to:
  /// **'The video server could not be reached after several attempts.'**
  String get liveFailConnection;

  /// No description provided for @liveFailLocked.
  ///
  /// In en, this message translates to:
  /// **'Live streaming is not available from the alert over the lock screen. Unlock the phone first.'**
  String get liveFailLocked;

  /// No description provided for @liveFallbackTitle.
  ///
  /// In en, this message translates to:
  /// **'Send a video clip instead'**
  String get liveFallbackTitle;

  /// No description provided for @liveFallbackBody.
  ///
  /// In en, this message translates to:
  /// **'Record a clip of up to 60 seconds: it is uploaded automatically with your report, even on a weak network.'**
  String get liveFallbackBody;

  /// No description provided for @liveRecordClip.
  ///
  /// In en, this message translates to:
  /// **'Record a clip (60 s)'**
  String get liveRecordClip;

  /// No description provided for @liveClipQueued.
  ///
  /// In en, this message translates to:
  /// **'The clip is saved and will be sent with your report.'**
  String get liveClipQueued;

  /// No description provided for @liveClipFailed.
  ///
  /// In en, this message translates to:
  /// **'The clip could not be saved.'**
  String get liveClipFailed;

  /// No description provided for @liveRetry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get liveRetry;

  /// No description provided for @liveOpenSettings.
  ///
  /// In en, this message translates to:
  /// **'Open settings'**
  String get liveOpenSettings;

  /// No description provided for @liveDone.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get liveDone;

  /// No description provided for @liveLeaveTitle.
  ///
  /// In en, this message translates to:
  /// **'Stop the live stream?'**
  String get liveLeaveTitle;

  /// No description provided for @liveLeaveBody.
  ///
  /// In en, this message translates to:
  /// **'The stream is on. Leaving stops sending the picture and your position.'**
  String get liveLeaveBody;

  /// No description provided for @liveSimulationBadge.
  ///
  /// In en, this message translates to:
  /// **'Simulation mode'**
  String get liveSimulationBadge;

  /// No description provided for @liveSimulationHelp.
  ///
  /// In en, this message translates to:
  /// **'This stream goes through the simulation platform and reaches no real operations room.'**
  String get liveSimulationHelp;

  /// No description provided for @reportGoLive.
  ///
  /// In en, this message translates to:
  /// **'Go live for this report'**
  String get reportGoLive;

  /// No description provided for @errorStreamAlreadyActive.
  ///
  /// In en, this message translates to:
  /// **'A live stream is already running for this report.'**
  String get errorStreamAlreadyActive;

  /// No description provided for @errorStreamNotActive.
  ///
  /// In en, this message translates to:
  /// **'This live stream is over.'**
  String get errorStreamNotActive;

  /// No description provided for @errorReportClosed.
  ///
  /// In en, this message translates to:
  /// **'This report is closed: a live stream cannot be opened on it.'**
  String get errorReportClosed;

  /// No description provided for @weatherTitle.
  ///
  /// In en, this message translates to:
  /// **'Weather near you'**
  String get weatherTitle;

  /// No description provided for @weatherLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading the weather…'**
  String get weatherLoading;

  /// No description provided for @weatherNoLocation.
  ///
  /// In en, this message translates to:
  /// **'Allow location access to see the weather where you are.'**
  String get weatherNoLocation;

  /// No description provided for @weatherUseLocation.
  ///
  /// In en, this message translates to:
  /// **'Use my location'**
  String get weatherUseLocation;

  /// No description provided for @weatherOutsideCoverage.
  ///
  /// In en, this message translates to:
  /// **'The weather forecast covers Tunisia only.'**
  String get weatherOutsideCoverage;

  /// No description provided for @weatherOffline.
  ///
  /// In en, this message translates to:
  /// **'No internet: the weather will be shown when the connection is back.'**
  String get weatherOffline;

  /// No description provided for @weatherUnavailable.
  ///
  /// In en, this message translates to:
  /// **'The weather could not be loaded.'**
  String get weatherUnavailable;

  /// No description provided for @weatherRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get weatherRetry;

  /// No description provided for @weatherNotRefreshed.
  ///
  /// In en, this message translates to:
  /// **'Not refreshed: showing the last data received.'**
  String get weatherNotRefreshed;

  /// No description provided for @weatherUpdated.
  ///
  /// In en, this message translates to:
  /// **'Updated {time}'**
  String weatherUpdated(String time);

  /// No description provided for @weatherCachedAt.
  ///
  /// In en, this message translates to:
  /// **'Offline copy from {time}'**
  String weatherCachedAt(String time);

  /// No description provided for @weatherNow.
  ///
  /// In en, this message translates to:
  /// **'Now'**
  String get weatherNow;

  /// No description provided for @weatherNextHours.
  ///
  /// In en, this message translates to:
  /// **'Next hours'**
  String get weatherNextHours;

  /// No description provided for @weatherTemperature.
  ///
  /// In en, this message translates to:
  /// **'{value} °C'**
  String weatherTemperature(String value);

  /// No description provided for @weatherWind.
  ///
  /// In en, this message translates to:
  /// **'Wind {speed} km/h'**
  String weatherWind(String speed);

  /// No description provided for @weatherGusts.
  ///
  /// In en, this message translates to:
  /// **'gusts {speed} km/h'**
  String weatherGusts(String speed);

  /// No description provided for @weatherHumidity.
  ///
  /// In en, this message translates to:
  /// **'Humidity {value}%'**
  String weatherHumidity(String value);

  /// No description provided for @weatherRain.
  ///
  /// In en, this message translates to:
  /// **'Rain {value} mm/h'**
  String weatherRain(String value);

  /// No description provided for @weatherRain24h.
  ///
  /// In en, this message translates to:
  /// **'{value} mm over 24 h'**
  String weatherRain24h(String value);

  /// No description provided for @weatherFireDanger.
  ///
  /// In en, this message translates to:
  /// **'Fire danger: {level}'**
  String weatherFireDanger(String level);

  /// No description provided for @weatherFireLow.
  ///
  /// In en, this message translates to:
  /// **'low'**
  String get weatherFireLow;

  /// No description provided for @weatherFireModerate.
  ///
  /// In en, this message translates to:
  /// **'moderate'**
  String get weatherFireModerate;

  /// No description provided for @weatherFireHigh.
  ///
  /// In en, this message translates to:
  /// **'high'**
  String get weatherFireHigh;

  /// No description provided for @weatherFireVeryHigh.
  ///
  /// In en, this message translates to:
  /// **'very high'**
  String get weatherFireVeryHigh;

  /// No description provided for @weatherFireExtreme.
  ///
  /// In en, this message translates to:
  /// **'extreme'**
  String get weatherFireExtreme;

  /// No description provided for @weatherHeavyRain.
  ///
  /// In en, this message translates to:
  /// **'Heavy rain: {level}'**
  String weatherHeavyRain(String level);

  /// No description provided for @weatherRainWatch.
  ///
  /// In en, this message translates to:
  /// **'watch'**
  String get weatherRainWatch;

  /// No description provided for @weatherRainWarning.
  ///
  /// In en, this message translates to:
  /// **'warning'**
  String get weatherRainWarning;

  /// No description provided for @weatherCondClear.
  ///
  /// In en, this message translates to:
  /// **'Clear sky'**
  String get weatherCondClear;

  /// No description provided for @weatherCondCloudy.
  ///
  /// In en, this message translates to:
  /// **'Cloudy'**
  String get weatherCondCloudy;

  /// No description provided for @weatherCondFog.
  ///
  /// In en, this message translates to:
  /// **'Fog'**
  String get weatherCondFog;

  /// No description provided for @weatherCondRain.
  ///
  /// In en, this message translates to:
  /// **'Rain'**
  String get weatherCondRain;

  /// No description provided for @weatherCondSnow.
  ///
  /// In en, this message translates to:
  /// **'Snow'**
  String get weatherCondSnow;

  /// No description provided for @weatherCondStorm.
  ///
  /// In en, this message translates to:
  /// **'Thunderstorm'**
  String get weatherCondStorm;

  /// No description provided for @weatherAlertsTitle.
  ///
  /// In en, this message translates to:
  /// **'Weather alerts in force'**
  String get weatherAlertsTitle;

  /// No description provided for @weatherSource.
  ///
  /// In en, this message translates to:
  /// **'Data: {source}'**
  String weatherSource(String source);

  /// No description provided for @weatherSimulationBadge.
  ///
  /// In en, this message translates to:
  /// **'Simulation mode'**
  String get weatherSimulationBadge;

  /// No description provided for @weatherSimulationHelp.
  ///
  /// In en, this message translates to:
  /// **'These weather values are simulated, not real measurements.'**
  String get weatherSimulationHelp;

  /// No description provided for @offlineFallbackTitle.
  ///
  /// In en, this message translates to:
  /// **'No internet connection'**
  String get offlineFallbackTitle;

  /// No description provided for @offlineFallbackBody.
  ///
  /// In en, this message translates to:
  /// **'Your report is saved on the phone and will be sent automatically when the internet is back. To alert the civil protection now:'**
  String get offlineFallbackBody;

  /// No description provided for @offlineSendSms.
  ///
  /// In en, this message translates to:
  /// **'Send by SMS'**
  String get offlineSendSms;

  /// No description provided for @offlineSmsHelp.
  ///
  /// In en, this message translates to:
  /// **'Opens your SMS app with a short message (type and position of the report). You press Send yourself.'**
  String get offlineSmsHelp;

  /// No description provided for @offlineSmsFee.
  ///
  /// In en, this message translates to:
  /// **'Your operator may charge the price of a standard SMS.'**
  String get offlineSmsFee;

  /// No description provided for @offlineSmsFailed.
  ///
  /// In en, this message translates to:
  /// **'The SMS app could not be opened. Call 198.'**
  String get offlineSmsFailed;

  /// No description provided for @rewardsTitle.
  ///
  /// In en, this message translates to:
  /// **'My rewards'**
  String get rewardsTitle;

  /// No description provided for @homeRewardsDesc.
  ///
  /// In en, this message translates to:
  /// **'Points, badges and certificates earned by useful reports.'**
  String get homeRewardsDesc;

  /// No description provided for @rewardsBalanceLabel.
  ///
  /// In en, this message translates to:
  /// **'Points balance'**
  String get rewardsBalanceLabel;

  /// No description provided for @rewardsNoBadge.
  ///
  /// In en, this message translates to:
  /// **'No badge yet'**
  String get rewardsNoBadge;

  /// No description provided for @rewardsCurrentBadge.
  ///
  /// In en, this message translates to:
  /// **'Current badge: {badge}'**
  String rewardsCurrentBadge(String badge);

  /// No description provided for @rewardsNextBadge.
  ///
  /// In en, this message translates to:
  /// **'Next badge, {badge}: {points} points to go'**
  String rewardsNextBadge(String badge, int points);

  /// No description provided for @rewardsTopBadge.
  ///
  /// In en, this message translates to:
  /// **'You hold the highest badge. Thank you for your vigilance.'**
  String get rewardsTopBadge;

  /// No description provided for @rewardsConfirmNote.
  ///
  /// In en, this message translates to:
  /// **'Silver, gold and ambassador badges appear once a civil protection officer has confirmed them.'**
  String get rewardsConfirmNote;

  /// No description provided for @badgeBronze.
  ///
  /// In en, this message translates to:
  /// **'Bronze'**
  String get badgeBronze;

  /// No description provided for @badgeSilver.
  ///
  /// In en, this message translates to:
  /// **'Silver'**
  String get badgeSilver;

  /// No description provided for @badgeGold.
  ///
  /// In en, this message translates to:
  /// **'Gold'**
  String get badgeGold;

  /// No description provided for @badgeAmbassador.
  ///
  /// In en, this message translates to:
  /// **'Ambassador'**
  String get badgeAmbassador;

  /// No description provided for @rewardsPausedTitle.
  ///
  /// In en, this message translates to:
  /// **'Points paused'**
  String get rewardsPausedTitle;

  /// No description provided for @rewardsPausedBody.
  ///
  /// In en, this message translates to:
  /// **'A disaster level is in force. New points are kept and will be added when the level drops.'**
  String get rewardsPausedBody;

  /// No description provided for @rewardsPendingPoints.
  ///
  /// In en, this message translates to:
  /// **'Points waiting: {points}'**
  String rewardsPendingPoints(int points);

  /// No description provided for @rewardsHistoryTitle.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get rewardsHistoryTitle;

  /// No description provided for @rewardsHistoryEmpty.
  ///
  /// In en, this message translates to:
  /// **'No points yet. Points are added when a report you sent is verified and closed.'**
  String get rewardsHistoryEmpty;

  /// No description provided for @rewardsShowMore.
  ///
  /// In en, this message translates to:
  /// **'Show more'**
  String get rewardsShowMore;

  /// No description provided for @pointsReasonReportVerified.
  ///
  /// In en, this message translates to:
  /// **'Verified report'**
  String get pointsReasonReportVerified;

  /// No description provided for @pointsReasonHelpedRescue.
  ///
  /// In en, this message translates to:
  /// **'Report that helped a rescue'**
  String get pointsReasonHelpedRescue;

  /// No description provided for @pointsReasonAccurateCategory.
  ///
  /// In en, this message translates to:
  /// **'Right category chosen'**
  String get pointsReasonAccurateCategory;

  /// No description provided for @pointsReasonVolunteerMission.
  ///
  /// In en, this message translates to:
  /// **'Volunteer mission completed'**
  String get pointsReasonVolunteerMission;

  /// No description provided for @pointsReasonManual.
  ///
  /// In en, this message translates to:
  /// **'Adjustment by the civil protection'**
  String get pointsReasonManual;

  /// No description provided for @pointsReasonRevocation.
  ///
  /// In en, this message translates to:
  /// **'Points withdrawn'**
  String get pointsReasonRevocation;

  /// No description provided for @pointsReasonOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get pointsReasonOther;

  /// No description provided for @rewardsCapped.
  ///
  /// In en, this message translates to:
  /// **'daily limit reached'**
  String get rewardsCapped;

  /// No description provided for @rewardsDailyCap.
  ///
  /// In en, this message translates to:
  /// **'At most {points} points can be earned per day.'**
  String rewardsDailyCap(int points);

  /// No description provided for @rewardsCertificatesTitle.
  ///
  /// In en, this message translates to:
  /// **'Certificates'**
  String get rewardsCertificatesTitle;

  /// No description provided for @rewardsCertificatesEmpty.
  ///
  /// In en, this message translates to:
  /// **'No certificate yet.'**
  String get rewardsCertificatesEmpty;

  /// No description provided for @rewardsCertificateYear.
  ///
  /// In en, this message translates to:
  /// **'Year {year}'**
  String rewardsCertificateYear(String year);

  /// No description provided for @distinctionVigilantCitizen.
  ///
  /// In en, this message translates to:
  /// **'Vigilant citizen'**
  String get distinctionVigilantCitizen;

  /// No description provided for @distinctionBraveVolunteer.
  ///
  /// In en, this message translates to:
  /// **'Brave volunteer'**
  String get distinctionBraveVolunteer;

  /// No description provided for @distinctionLeadingInstitution.
  ///
  /// In en, this message translates to:
  /// **'Leading institution'**
  String get distinctionLeadingInstitution;

  /// No description provided for @distinctionBadge.
  ///
  /// In en, this message translates to:
  /// **'{badge} badge'**
  String distinctionBadge(String badge);

  /// No description provided for @distinctionOther.
  ///
  /// In en, this message translates to:
  /// **'Distinction'**
  String get distinctionOther;

  /// No description provided for @rewardsOpenPdf.
  ///
  /// In en, this message translates to:
  /// **'Open the PDF certificate'**
  String get rewardsOpenPdf;

  /// No description provided for @rewardsPdfNoViewer.
  ///
  /// In en, this message translates to:
  /// **'No app on this phone can open the PDF.'**
  String get rewardsPdfNoViewer;

  /// No description provided for @rewardsAnonymousTitle.
  ///
  /// In en, this message translates to:
  /// **'Anonymous reports earn no points'**
  String get rewardsAnonymousTitle;

  /// No description provided for @rewardsAnonymousBody.
  ///
  /// In en, this message translates to:
  /// **'A report sent without an account cannot be linked to a person, so it earns no points, badges or certificates. Create an account to take part; reports already sent anonymously stay anonymous.'**
  String get rewardsAnonymousBody;

  /// No description provided for @rewardsSafetyNotice.
  ///
  /// In en, this message translates to:
  /// **'Never put yourself in danger to report. Your safety comes first: in an emergency, call 198.'**
  String get rewardsSafetyNotice;

  /// No description provided for @rewardsPrizesNotice.
  ///
  /// In en, this message translates to:
  /// **'Points, badges and certificates are a public recognition, not money. Any annual prize is subject to a decision of the competent authority.'**
  String get rewardsPrizesNotice;

  /// No description provided for @rewardsOfflineCopy.
  ///
  /// In en, this message translates to:
  /// **'Offline: copy saved on {date}.'**
  String rewardsOfflineCopy(String date);

  /// No description provided for @rewardsHowTitle.
  ///
  /// In en, this message translates to:
  /// **'How to earn points'**
  String get rewardsHowTitle;

  /// No description provided for @rewardsHowBody.
  ///
  /// In en, this message translates to:
  /// **'Points are added when a report you sent is verified and closed, with more when it helped a rescue or when you chose the right category, and for each volunteer mission completed. No points are given for false or rejected reports.'**
  String get rewardsHowBody;

  /// No description provided for @trackPointsEarned.
  ///
  /// In en, this message translates to:
  /// **'Points earned by this report: {points}'**
  String trackPointsEarned(int points);

  /// No description provided for @trackPointsOpenRewards.
  ///
  /// In en, this message translates to:
  /// **'See my rewards'**
  String get trackPointsOpenRewards;

  /// No description provided for @anonQuotaCardTitle.
  ///
  /// In en, this message translates to:
  /// **'Reports without an account'**
  String get anonQuotaCardTitle;

  /// No description provided for @anonQuotaRemaining.
  ///
  /// In en, this message translates to:
  /// **'{remaining} of {limit} left'**
  String anonQuotaRemaining(int remaining, int limit);

  /// No description provided for @anonQuotaRemainingShort.
  ///
  /// In en, this message translates to:
  /// **'{remaining} left'**
  String anonQuotaRemainingShort(int remaining);

  /// No description provided for @anonQuotaExhaustedHint.
  ///
  /// In en, this message translates to:
  /// **'Limit reached: create an account to keep reporting. SOS and 198 always work.'**
  String get anonQuotaExhaustedHint;

  /// No description provided for @anonQuotaTitle.
  ///
  /// In en, this message translates to:
  /// **'Reporting without an account'**
  String get anonQuotaTitle;

  /// No description provided for @anonQuotaExplanation.
  ///
  /// In en, this message translates to:
  /// **'To prevent abuse, each installation of the app can send a limited number of reports without an account. With a free account you can keep reporting, follow your reports on any device, and your reports carry more weight.'**
  String get anonQuotaExplanation;

  /// No description provided for @anonQuotaEmergencyNote.
  ///
  /// In en, this message translates to:
  /// **'In an emergency, the SOS button and a call to 198 always work, with or without an account.'**
  String get anonQuotaEmergencyNote;

  /// No description provided for @anonQuotaDraftKept.
  ///
  /// In en, this message translates to:
  /// **'Your report {code} is kept on this phone. It will be sent as soon as you create an account or sign in.'**
  String anonQuotaDraftKept(String code);

  /// No description provided for @anonQuotaReportKeptBody.
  ///
  /// In en, this message translates to:
  /// **'The limit of reports without an account is reached. This report is kept on this phone and will be sent as soon as you create an account or sign in.'**
  String get anonQuotaReportKeptBody;

  /// No description provided for @anonQuotaOpen.
  ///
  /// In en, this message translates to:
  /// **'Why a limit?'**
  String get anonQuotaOpen;

  /// No description provided for @errorAnonQuotaExhausted.
  ///
  /// In en, this message translates to:
  /// **'The limit of reports without an account is reached on this device. Please create an account.'**
  String get errorAnonQuotaExhausted;

  /// No description provided for @intro1Title.
  ///
  /// In en, this message translates to:
  /// **'Welcome to e-Himaya'**
  String get intro1Title;

  /// No description provided for @intro1Body.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya finds your position from your phone. In an emergency it sends it with your report straight to the competent Civil Protection operations room, so help reaches you faster and with the right resources.'**
  String get intro1Body;

  /// No description provided for @intro2Title.
  ///
  /// In en, this message translates to:
  /// **'Run by the National Civil Protection Office'**
  String get intro2Title;

  /// No description provided for @intro2Body.
  ///
  /// In en, this message translates to:
  /// **'This app is provided by the National Civil Protection Office, the public body in charge of rescue, firefighting and disaster response across Tunisia, which answers the 198 emergency line.'**
  String get intro2Body;

  /// No description provided for @intro3Title.
  ///
  /// In en, this message translates to:
  /// **'When should I use it?'**
  String get intro3Title;

  /// No description provided for @intro3Body.
  ///
  /// In en, this message translates to:
  /// **'Fire, road accident, a person in danger or injured, drowning, collapse, gas leak, flood, or any situation that threatens lives or property and needs Civil Protection.'**
  String get intro3Body;

  /// No description provided for @intro4Title.
  ///
  /// In en, this message translates to:
  /// **'How does it work?'**
  String get intro4Title;

  /// No description provided for @intro4Body.
  ///
  /// In en, this message translates to:
  /// **'Choose the type of incident, add a photo, video or voice message if you can do so safely, and send. Your report and position reach the operator at once; you can follow it step by step and the operator may call you back. Without internet the report goes by SMS, and calling 198 is always available.'**
  String get intro4Body;

  /// No description provided for @intro5Title.
  ///
  /// In en, this message translates to:
  /// **'Where does it work?'**
  String get intro5Title;

  /// No description provided for @intro5Body.
  ///
  /// In en, this message translates to:
  /// **'Throughout the Republic of Tunisia, in all 24 governorates; your report is routed automatically to the competent regional directorate. Outside Tunisia, call the local emergency number (112 in most countries).'**
  String get intro5Body;

  /// No description provided for @terms1Title.
  ///
  /// In en, this message translates to:
  /// **'1. Purpose'**
  String get terms1Title;

  /// No description provided for @terms1Body.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya is a digital platform of the National Civil Protection Office (\"the Office\") for reporting emergencies and following them up. These terms govern the relationship between the Office and the users of the mobile app and the institutions portal.'**
  String get terms1Body;

  /// No description provided for @terms2Title.
  ///
  /// In en, this message translates to:
  /// **'2. Our mission'**
  String get terms2Title;

  /// No description provided for @terms2Body.
  ///
  /// In en, this message translates to:
  /// **'To protect lives and property, and to rebuild trust between citizens and Civil Protection through direct and open communication. Describing the incident accurately and showing the scene as it is shortens response time and makes the intervention more effective.'**
  String get terms2Body;

  /// No description provided for @terms3Title.
  ///
  /// In en, this message translates to:
  /// **'3. Nature and limits of the service'**
  String get terms3Title;

  /// No description provided for @terms3Body.
  ///
  /// In en, this message translates to:
  /// **'3.1 The app complements 198 and does not replace it. In immediate danger, call 198 directly.\n3.2 The app gives no medical advice; its safety tips are for general awareness and do not replace the instructions of Civil Protection staff.\n3.3 It depends on factors outside the Office\'s control: mobile network and internet coverage, location signal, battery and the condition of the phone. The Office aims for the highest availability and fixes faults as fast as possible.'**
  String get terms3Body;

  /// No description provided for @terms4Title.
  ///
  /// In en, this message translates to:
  /// **'4. User obligations'**
  String get terms4Title;

  /// No description provided for @terms4Body.
  ///
  /// In en, this message translates to:
  /// **'4.1 Use the app in good faith and only for real emergencies; give accurate, up-to-date information, especially your phone number.\n4.2 Keep location turned on and use the latest version of the app.\n4.3 Do not put yourself in danger to film, and follow the instructions of responders.\n4.4 Do not harm, disrupt, bypass the protections of, or reverse-engineer the app.'**
  String get terms4Body;

  /// No description provided for @terms5Title.
  ///
  /// In en, this message translates to:
  /// **'5. False alarms and misuse'**
  String get terms5Title;

  /// No description provided for @terms5Body.
  ///
  /// In en, this message translates to:
  /// **'Every report sends out rescue teams that other lives may need at the same moment. A deliberate false report or any misuse of the app exposes its author to prosecution under Tunisian law, and may lead to temporary or permanent suspension of the account or of reporting from the device concerned.'**
  String get terms5Body;

  /// No description provided for @terms6Title.
  ///
  /// In en, this message translates to:
  /// **'6. Institutions\' obligations'**
  String get terms6Title;

  /// No description provided for @terms6Body.
  ///
  /// In en, this message translates to:
  /// **'A registered institution provides accurate, up-to-date information on its identity, activity, buildings and managers, and is responsible for it. Filing and updating the evacuation plan and building plans makes the intervention easier and shortens search and rescue inside the building. The account is activated only after the Office approves it.'**
  String get terms6Body;

  /// No description provided for @terms7Title.
  ///
  /// In en, this message translates to:
  /// **'7. Volunteers'**
  String get terms7Title;

  /// No description provided for @terms7Body.
  ///
  /// In en, this message translates to:
  /// **'Volunteer status is granted only after the Office approves it. Volunteers follow the operations room\'s instructions and act only within the task assigned to them.'**
  String get terms7Body;

  /// No description provided for @terms8Title.
  ///
  /// In en, this message translates to:
  /// **'8. Personal data protection'**
  String get terms8Title;

  /// No description provided for @terms8Body.
  ///
  /// In en, this message translates to:
  /// **'8.1 Personal data is processed under Organic Law No. 2004-63 of 27 July 2004 on the protection of personal data, under the supervision of the National Authority for the Protection of Personal Data (INPDP), solely to handle emergencies and to keep you informed about your reports.\n8.2 When you send a report, the Office receives your position, the type of incident, the description and attached media, and your account details if you have an account.\n8.3 Emergency contacts and the text of your SOS message are stored encrypted on your phone only and are never sent to the Office.\n8.4 You can report without an account under a pseudonym; your IP address is not recorded.\n8.5 Only authorised staff can access the data, which is kept as long as needed to handle the case and meet legal obligations. You have the right to access, correct and object to the processing of your data.'**
  String get terms8Body;

  /// No description provided for @terms9Title.
  ///
  /// In en, this message translates to:
  /// **'9. Changes to the app and these terms'**
  String get terms9Title;

  /// No description provided for @terms9Body.
  ///
  /// In en, this message translates to:
  /// **'The Office may improve the app or change these terms. You are told about each new version and what it contains, and asked to accept again when the terms change.'**
  String get terms9Body;

  /// No description provided for @terms10Title.
  ///
  /// In en, this message translates to:
  /// **'10. Applicable law'**
  String get terms10Title;

  /// No description provided for @terms10Body.
  ///
  /// In en, this message translates to:
  /// **'These terms are governed by Tunisian law; Tunisian courts have jurisdiction over any dispute.'**
  String get terms10Body;

  /// No description provided for @languageTitle.
  ///
  /// In en, this message translates to:
  /// **'Choose your language'**
  String get languageTitle;

  /// No description provided for @languageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'You can change it at any time from the language bar at the top of every screen.'**
  String get languageSubtitle;

  /// No description provided for @languageMenuTooltip.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get languageMenuTooltip;

  /// No description provided for @introSkip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get introSkip;

  /// No description provided for @introPage.
  ///
  /// In en, this message translates to:
  /// **'Page {current} of {total}'**
  String introPage(int current, int total);

  /// No description provided for @call198.
  ///
  /// In en, this message translates to:
  /// **'Call 198'**
  String get call198;

  /// No description provided for @termsScrollHint.
  ///
  /// In en, this message translates to:
  /// **'Scroll to the end of the terms to accept them.'**
  String get termsScrollHint;

  /// No description provided for @termsAccept.
  ///
  /// In en, this message translates to:
  /// **'I accept'**
  String get termsAccept;

  /// No description provided for @termsDecline.
  ///
  /// In en, this message translates to:
  /// **'I decline'**
  String get termsDecline;

  /// No description provided for @termsDeclinedTitle.
  ///
  /// In en, this message translates to:
  /// **'Terms not accepted'**
  String get termsDeclinedTitle;

  /// No description provided for @termsDeclinedBody.
  ///
  /// In en, this message translates to:
  /// **'Without accepting the terms you cannot use the app, but calling 198 is always available.'**
  String get termsDeclinedBody;

  /// No description provided for @termsReadAgain.
  ///
  /// In en, this message translates to:
  /// **'Read the terms'**
  String get termsReadAgain;

  /// No description provided for @permissionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Permissions'**
  String get permissionsTitle;

  /// No description provided for @permissionsIntro.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya asks only for what it needs to help you. You can change these choices later in your phone settings.'**
  String get permissionsIntro;

  /// No description provided for @permLocationTitle.
  ///
  /// In en, this message translates to:
  /// **'Location'**
  String get permLocationTitle;

  /// No description provided for @permLocationBody.
  ///
  /// In en, this message translates to:
  /// **'Sent with your report so help finds you. Without it you must describe the place and help may take longer.'**
  String get permLocationBody;

  /// No description provided for @permNotificationsTitle.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get permNotificationsTitle;

  /// No description provided for @permNotificationsBody.
  ///
  /// In en, this message translates to:
  /// **'Follow-up of your reports and public alerts near you. Without them you will not be warned of a danger in your area.'**
  String get permNotificationsBody;

  /// No description provided for @permSmsTitle.
  ///
  /// In en, this message translates to:
  /// **'SMS'**
  String get permSmsTitle;

  /// No description provided for @permSmsBody.
  ///
  /// In en, this message translates to:
  /// **'Without internet your report leaves by SMS. No permission is needed: the app opens a ready message that you send yourself.'**
  String get permSmsBody;

  /// No description provided for @permContactsTitle.
  ///
  /// In en, this message translates to:
  /// **'Contacts'**
  String get permContactsTitle;

  /// No description provided for @permContactsBody.
  ///
  /// In en, this message translates to:
  /// **'Asked only when you choose an emergency contact, later.'**
  String get permContactsBody;

  /// No description provided for @permAllow.
  ///
  /// In en, this message translates to:
  /// **'Allow'**
  String get permAllow;

  /// No description provided for @permAllowed.
  ///
  /// In en, this message translates to:
  /// **'Allowed'**
  String get permAllowed;

  /// No description provided for @permRefused.
  ///
  /// In en, this message translates to:
  /// **'Refused: you can allow it in the phone settings'**
  String get permRefused;

  /// No description provided for @permNoneNeeded.
  ///
  /// In en, this message translates to:
  /// **'No permission needed'**
  String get permNoneNeeded;

  /// No description provided for @permLater.
  ///
  /// In en, this message translates to:
  /// **'Later'**
  String get permLater;

  /// No description provided for @signInTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signInTitle;

  /// No description provided for @signInIntro.
  ///
  /// In en, this message translates to:
  /// **'Sign in with your mobile number: we send you a code by SMS. No password.'**
  String get signInIntro;

  /// No description provided for @signInPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Mobile number'**
  String get signInPhoneLabel;

  /// No description provided for @signInPhoneHint.
  ///
  /// In en, this message translates to:
  /// **'8 digits'**
  String get signInPhoneHint;

  /// No description provided for @signInPhoneInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a Tunisian mobile number: 8 digits starting with 2, 3, 4, 5 or 9.'**
  String get signInPhoneInvalid;

  /// No description provided for @signInSendCode.
  ///
  /// In en, this message translates to:
  /// **'Send the code'**
  String get signInSendCode;

  /// No description provided for @signInCodeLabel.
  ///
  /// In en, this message translates to:
  /// **'Code received by SMS'**
  String get signInCodeLabel;

  /// No description provided for @signInCodeSentTo.
  ///
  /// In en, this message translates to:
  /// **'A 6-digit code was sent to {phone}.'**
  String signInCodeSentTo(String phone);

  /// No description provided for @signInVerify.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signInVerify;

  /// No description provided for @signInResendIn.
  ///
  /// In en, this message translates to:
  /// **'Resend the code in {seconds} s'**
  String signInResendIn(int seconds);

  /// No description provided for @signInResend.
  ///
  /// In en, this message translates to:
  /// **'Resend the code'**
  String get signInResend;

  /// No description provided for @signInChangeNumber.
  ///
  /// In en, this message translates to:
  /// **'Change the number'**
  String get signInChangeNumber;

  /// No description provided for @signInWrongCode.
  ///
  /// In en, this message translates to:
  /// **'Wrong code. Tries left: {tries}.'**
  String signInWrongCode(int tries);

  /// No description provided for @signInCodeExpired.
  ///
  /// In en, this message translates to:
  /// **'The code expired or was used up. Ask for a new one.'**
  String get signInCodeExpired;

  /// No description provided for @signInTooSoon.
  ///
  /// In en, this message translates to:
  /// **'Please wait a minute before asking for a new code.'**
  String get signInTooSoon;

  /// No description provided for @signInLimit.
  ///
  /// In en, this message translates to:
  /// **'Too many codes for this number. Try again in an hour.'**
  String get signInLimit;

  /// No description provided for @signInSmsUnavailable.
  ///
  /// In en, this message translates to:
  /// **'The SMS could not be sent. Try again, or continue as a guest.'**
  String get signInSmsUnavailable;

  /// No description provided for @signInNetworkError.
  ///
  /// In en, this message translates to:
  /// **'No connection. Check your internet and try again.'**
  String get signInNetworkError;

  /// No description provided for @signInGuest.
  ///
  /// In en, this message translates to:
  /// **'Continue as a guest'**
  String get signInGuest;

  /// No description provided for @signInGuestDesc.
  ///
  /// In en, this message translates to:
  /// **'Report without an account (a limited number of reports).'**
  String get signInGuestDesc;

  /// No description provided for @signInInstitution.
  ///
  /// In en, this message translates to:
  /// **'Institution account'**
  String get signInInstitution;

  /// No description provided for @signInInstitutionDesc.
  ///
  /// In en, this message translates to:
  /// **'For companies, schools, hotels and administrations.'**
  String get signInInstitutionDesc;

  /// No description provided for @signInEmail.
  ///
  /// In en, this message translates to:
  /// **'Sign in with e-mail and password'**
  String get signInEmail;

  /// No description provided for @signInPrivacyNote.
  ///
  /// In en, this message translates to:
  /// **'Your number is used only to reach you about your reports.'**
  String get signInPrivacyNote;

  /// No description provided for @simBanner.
  ///
  /// In en, this message translates to:
  /// **'[SIM] Simulation: the SMS goes to the test gateway (notify-sim), not to a real phone.'**
  String get simBanner;

  /// No description provided for @homeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Tunisian Civil Protection'**
  String get homeSubtitle;

  /// No description provided for @homeReportCardTitle.
  ///
  /// In en, this message translates to:
  /// **'Report an incident'**
  String get homeReportCardTitle;

  /// No description provided for @homeReportCardDesc.
  ///
  /// In en, this message translates to:
  /// **'Photo, voice or text, with your position automatically'**
  String get homeReportCardDesc;

  /// No description provided for @homeNumbersOffline.
  ///
  /// In en, this message translates to:
  /// **'Work without internet'**
  String get homeNumbersOffline;

  /// No description provided for @homeShortcuts.
  ///
  /// In en, this message translates to:
  /// **'Shortcuts'**
  String get homeShortcuts;

  /// No description provided for @homeMyReports.
  ///
  /// In en, this message translates to:
  /// **'My reports'**
  String get homeMyReports;

  /// No description provided for @homeSosMessage.
  ///
  /// In en, this message translates to:
  /// **'SOS message'**
  String get homeSosMessage;

  /// No description provided for @homeCall198.
  ///
  /// In en, this message translates to:
  /// **'Emergency call 198'**
  String get homeCall198;

  /// No description provided for @locationOn.
  ///
  /// In en, this message translates to:
  /// **'Location on'**
  String get locationOn;

  /// No description provided for @locationOff.
  ///
  /// In en, this message translates to:
  /// **'Location is off: help may take longer to find you.'**
  String get locationOff;

  /// No description provided for @locationTurnOn.
  ///
  /// In en, this message translates to:
  /// **'Turn on'**
  String get locationTurnOn;

  /// No description provided for @locationChecking.
  ///
  /// In en, this message translates to:
  /// **'Checking location…'**
  String get locationChecking;

  /// No description provided for @themeToggleTooltip.
  ///
  /// In en, this message translates to:
  /// **'Light or dark'**
  String get themeToggleTooltip;

  /// No description provided for @settingsColors.
  ///
  /// In en, this message translates to:
  /// **'Colours'**
  String get settingsColors;

  /// No description provided for @colorOffice.
  ///
  /// In en, this message translates to:
  /// **'Civil Protection (logo)'**
  String get colorOffice;

  /// No description provided for @colorRed.
  ///
  /// In en, this message translates to:
  /// **'Red'**
  String get colorRed;

  /// No description provided for @colorBlue.
  ///
  /// In en, this message translates to:
  /// **'Blue'**
  String get colorBlue;

  /// No description provided for @colorGreen.
  ///
  /// In en, this message translates to:
  /// **'Green'**
  String get colorGreen;

  /// No description provided for @updateTitle.
  ///
  /// In en, this message translates to:
  /// **'A new version is available'**
  String get updateTitle;

  /// No description provided for @updateMandatoryTitle.
  ///
  /// In en, this message translates to:
  /// **'Update required'**
  String get updateMandatoryTitle;

  /// No description provided for @updateMandatoryBody.
  ///
  /// In en, this message translates to:
  /// **'This version is no longer supported. Update to keep using e-Himaya. Emergency numbers stay available.'**
  String get updateMandatoryBody;

  /// No description provided for @updateWhatsNew.
  ///
  /// In en, this message translates to:
  /// **'What\'s new in {version}'**
  String updateWhatsNew(String version);

  /// No description provided for @updateDataKept.
  ///
  /// In en, this message translates to:
  /// **'Your reports and settings are kept.'**
  String get updateDataKept;

  /// No description provided for @updateNow.
  ///
  /// In en, this message translates to:
  /// **'Update'**
  String get updateNow;

  /// No description provided for @updateLater.
  ///
  /// In en, this message translates to:
  /// **'Later'**
  String get updateLater;

  /// No description provided for @updateOpenFailed.
  ///
  /// In en, this message translates to:
  /// **'The download page could not be opened.'**
  String get updateOpenFailed;

  /// No description provided for @requiredNote.
  ///
  /// In en, this message translates to:
  /// **'Fields marked * are required.'**
  String get requiredNote;

  /// No description provided for @requiredSemantics.
  ///
  /// In en, this message translates to:
  /// **'required'**
  String get requiredSemantics;

  /// No description provided for @errorOffensiveText.
  ///
  /// In en, this message translates to:
  /// **'This text contains words that are not allowed. Please rephrase it.'**
  String get errorOffensiveText;

  /// No description provided for @guideTitle.
  ///
  /// In en, this message translates to:
  /// **'Emergency guide'**
  String get guideTitle;

  /// No description provided for @guideHubHint.
  ///
  /// In en, this message translates to:
  /// **'Fires, fractures, first aid, breathing problems… Available without connection.'**
  String get guideHubHint;

  /// No description provided for @guideIntro.
  ///
  /// In en, this message translates to:
  /// **'Choose a topic, then the situation. While waiting for help, follow the steps in order.'**
  String get guideIntro;

  /// No description provided for @guideItemsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =0{No item} =1{1 item} other{{count} items}}'**
  String guideItemsCount(int count);

  /// No description provided for @guideEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing is published here at the moment.'**
  String get guideEmpty;

  /// No description provided for @guideCallNow.
  ///
  /// In en, this message translates to:
  /// **'Call 198 at once if'**
  String get guideCallNow;

  /// No description provided for @guideSteps.
  ///
  /// In en, this message translates to:
  /// **'What to do'**
  String get guideSteps;

  /// No description provided for @guideDont.
  ///
  /// In en, this message translates to:
  /// **'Do not'**
  String get guideDont;

  /// No description provided for @guideCall198.
  ///
  /// In en, this message translates to:
  /// **'Call Civil Protection, 198'**
  String get guideCall198;

  /// No description provided for @guideSimBanner.
  ///
  /// In en, this message translates to:
  /// **'[SIM] Content awaiting validation by the medical staff of the Civil Protection. Call 198 first.'**
  String get guideSimBanner;

  /// No description provided for @guideSimTag.
  ///
  /// In en, this message translates to:
  /// **'[SIM] awaiting medical validation'**
  String get guideSimTag;

  /// No description provided for @nearestTitle.
  ///
  /// In en, this message translates to:
  /// **'Nearest to me'**
  String get nearestTitle;

  /// No description provided for @nearestHint.
  ///
  /// In en, this message translates to:
  /// **'Civil Protection centres, hospitals, pharmacies… and your coordinates. Works without connection once downloaded.'**
  String get nearestHint;

  /// No description provided for @nearestMyPosition.
  ///
  /// In en, this message translates to:
  /// **'My position'**
  String get nearestMyPosition;

  /// No description provided for @nearestNoLocation.
  ///
  /// In en, this message translates to:
  /// **'Location is off or not allowed. Turn it on to see the nearest places.'**
  String get nearestNoLocation;

  /// No description provided for @nearestCopy.
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get nearestCopy;

  /// No description provided for @nearestCopied.
  ///
  /// In en, this message translates to:
  /// **'Coordinates copied. You can read them to the operator.'**
  String get nearestCopied;

  /// No description provided for @nearestOffline.
  ///
  /// In en, this message translates to:
  /// **'No connection: showing the copy saved on this phone.'**
  String get nearestOffline;

  /// No description provided for @nearestEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing saved on this phone yet. Connect once to download the places.'**
  String get nearestEmpty;

  /// No description provided for @nearestLoading.
  ///
  /// In en, this message translates to:
  /// **'Downloading the places for offline use…'**
  String get nearestLoading;

  /// No description provided for @nearestUpdated.
  ///
  /// In en, this message translates to:
  /// **'Places updated on {date}'**
  String nearestUpdated(String date);

  /// No description provided for @nearestToVerify.
  ///
  /// In en, this message translates to:
  /// **'To be verified'**
  String get nearestToVerify;

  /// No description provided for @nearestSimBanner.
  ///
  /// In en, this message translates to:
  /// **'[SIM] Some of these places are approximate and invented for a trial: they are not real places. In an emergency, call 198.'**
  String get nearestSimBanner;

  /// No description provided for @nearestSimChip.
  ///
  /// In en, this message translates to:
  /// **'[SIM] Trial'**
  String get nearestSimChip;

  /// No description provided for @nearestNeedPosition.
  ///
  /// In en, this message translates to:
  /// **'Waiting for your position.'**
  String get nearestNeedPosition;

  /// No description provided for @nearestNone.
  ///
  /// In en, this message translates to:
  /// **'No place of this kind is listed yet.'**
  String get nearestNone;

  /// No description provided for @nearestSource.
  ///
  /// In en, this message translates to:
  /// **'Source: {source}'**
  String nearestSource(String source);

  /// No description provided for @nearestCall.
  ///
  /// In en, this message translates to:
  /// **'Call {phone}'**
  String nearestCall(String phone);

  /// No description provided for @nearestRoute.
  ///
  /// In en, this message translates to:
  /// **'Route'**
  String get nearestRoute;

  /// No description provided for @contactTitle.
  ///
  /// In en, this message translates to:
  /// **'Contact us'**
  String get contactTitle;

  /// No description provided for @contactMineTitle.
  ///
  /// In en, this message translates to:
  /// **'My requests'**
  String get contactMineTitle;

  /// No description provided for @contactEmergencyBanner.
  ///
  /// In en, this message translates to:
  /// **'Not for emergencies. For an emergency, call 198.'**
  String get contactEmergencyBanner;

  /// No description provided for @contactIntro.
  ///
  /// In en, this message translates to:
  /// **'Ask a question, request information held by the Civil Protection, report a non-urgent hazard, suggest an idea or report a problem with the app. You get a number to follow your request.'**
  String get contactIntro;

  /// No description provided for @contactKind.
  ///
  /// In en, this message translates to:
  /// **'Kind of request'**
  String get contactKind;

  /// No description provided for @contactKindAccessInfo.
  ///
  /// In en, this message translates to:
  /// **'Access to information (law 2016-22)'**
  String get contactKindAccessInfo;

  /// No description provided for @contactKindHazard.
  ///
  /// In en, this message translates to:
  /// **'Non-urgent hazard'**
  String get contactKindHazard;

  /// No description provided for @contactKindQuestion.
  ///
  /// In en, this message translates to:
  /// **'Question'**
  String get contactKindQuestion;

  /// No description provided for @contactKindSuggestion.
  ///
  /// In en, this message translates to:
  /// **'Suggestion'**
  String get contactKindSuggestion;

  /// No description provided for @contactKindAppProblem.
  ///
  /// In en, this message translates to:
  /// **'Problem with the app'**
  String get contactKindAppProblem;

  /// No description provided for @contactKindPartnership.
  ///
  /// In en, this message translates to:
  /// **'Partnership'**
  String get contactKindPartnership;

  /// No description provided for @contactAccessInfoHint.
  ///
  /// In en, this message translates to:
  /// **'The law asks for your name. The Office answers within the legal deadline (20 days).'**
  String get contactAccessInfoHint;

  /// No description provided for @contactNoGouvernorat.
  ///
  /// In en, this message translates to:
  /// **'Not specific to a gouvernorat'**
  String get contactNoGouvernorat;

  /// No description provided for @contactSubject.
  ///
  /// In en, this message translates to:
  /// **'Subject'**
  String get contactSubject;

  /// No description provided for @contactMessage.
  ///
  /// In en, this message translates to:
  /// **'Your message'**
  String get contactMessage;

  /// No description provided for @contactDetailsHint.
  ///
  /// In en, this message translates to:
  /// **'Contact details are optional: without them, the answer is only shown here in “My requests”.'**
  String get contactDetailsHint;

  /// No description provided for @contactName.
  ///
  /// In en, this message translates to:
  /// **'Full name'**
  String get contactName;

  /// No description provided for @contactEmail.
  ///
  /// In en, this message translates to:
  /// **'E-mail'**
  String get contactEmail;

  /// No description provided for @contactEmailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid e-mail address.'**
  String get contactEmailInvalid;

  /// No description provided for @contactLength.
  ///
  /// In en, this message translates to:
  /// **'Between {min} and {max} characters.'**
  String contactLength(int min, int max);

  /// No description provided for @contactSend.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get contactSend;

  /// No description provided for @contactSentTitle.
  ///
  /// In en, this message translates to:
  /// **'Request sent'**
  String get contactSentTitle;

  /// No description provided for @contactSentBody.
  ///
  /// In en, this message translates to:
  /// **'Keep this number to follow your request:'**
  String get contactSentBody;

  /// No description provided for @contactSeeMine.
  ///
  /// In en, this message translates to:
  /// **'See my requests'**
  String get contactSeeMine;

  /// No description provided for @contactMineEmpty.
  ///
  /// In en, this message translates to:
  /// **'You have not sent any request yet.'**
  String get contactMineEmpty;

  /// No description provided for @contactStatusReceived.
  ///
  /// In en, this message translates to:
  /// **'Received'**
  String get contactStatusReceived;

  /// No description provided for @contactStatusInProgress.
  ///
  /// In en, this message translates to:
  /// **'In progress'**
  String get contactStatusInProgress;

  /// No description provided for @contactStatusAnswered.
  ///
  /// In en, this message translates to:
  /// **'Answered'**
  String get contactStatusAnswered;

  /// No description provided for @contactStatusClosed.
  ///
  /// In en, this message translates to:
  /// **'Closed'**
  String get contactStatusClosed;

  /// No description provided for @contactStatusRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get contactStatusRejected;

  /// No description provided for @contactDue.
  ///
  /// In en, this message translates to:
  /// **'Answer due by {date}'**
  String contactDue(String date);

  /// No description provided for @contactAnswer.
  ///
  /// In en, this message translates to:
  /// **'Answer of the Office'**
  String get contactAnswer;

  /// No description provided for @contactRejectReason.
  ///
  /// In en, this message translates to:
  /// **'Reason given by the Office'**
  String get contactRejectReason;

  /// No description provided for @errorFeatureOff.
  ///
  /// In en, this message translates to:
  /// **'This feature is not available yet.'**
  String get errorFeatureOff;

  /// No description provided for @errorAlreadyLinked.
  ///
  /// In en, this message translates to:
  /// **'You are already linked with this person.'**
  String get errorAlreadyLinked;

  /// No description provided for @errorOwnInvitation.
  ///
  /// In en, this message translates to:
  /// **'This is your own code: give it to the other person.'**
  String get errorOwnInvitation;

  /// No description provided for @errorTooManyLinks.
  ///
  /// In en, this message translates to:
  /// **'You reached the maximum number of linked contacts.'**
  String get errorTooManyLinks;

  /// No description provided for @errorTooManyInvitations.
  ///
  /// In en, this message translates to:
  /// **'Too many open invitations. Use or let one expire first.'**
  String get errorTooManyInvitations;

  /// No description provided for @errorNoLinkedContact.
  ///
  /// In en, this message translates to:
  /// **'No linked contact to alert in the app.'**
  String get errorNoLinkedContact;

  /// No description provided for @errorCheckActive.
  ///
  /// In en, this message translates to:
  /// **'A safety check is already running.'**
  String get errorCheckActive;

  /// No description provided for @errorHistoryOff.
  ///
  /// In en, this message translates to:
  /// **'The location history is off.'**
  String get errorHistoryOff;

  /// No description provided for @errorDurationTooLong.
  ///
  /// In en, this message translates to:
  /// **'This duration is longer than allowed.'**
  String get errorDurationTooLong;

  /// No description provided for @safetyTitle.
  ///
  /// In en, this message translates to:
  /// **'Personal safety'**
  String get safetyTitle;

  /// No description provided for @safetySettingsHint.
  ///
  /// In en, this message translates to:
  /// **'Emergency contacts, SOS message, medical file'**
  String get safetySettingsHint;

  /// No description provided for @safetyIntro.
  ///
  /// In en, this message translates to:
  /// **'Prepare who to warn and what to send if something happens to you. Your contacts, your message and your medical file stay on this phone.'**
  String get safetyIntro;

  /// No description provided for @safetySendSos.
  ///
  /// In en, this message translates to:
  /// **'Send my SOS message'**
  String get safetySendSos;

  /// No description provided for @safetySomeone.
  ///
  /// In en, this message translates to:
  /// **'A contact'**
  String get safetySomeone;

  /// No description provided for @safetyDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get safetyDelete;

  /// No description provided for @safetyEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get safetyEdit;

  /// No description provided for @safetyCopy.
  ///
  /// In en, this message translates to:
  /// **'Copy'**
  String get safetyCopy;

  /// No description provided for @safetyCopied.
  ///
  /// In en, this message translates to:
  /// **'Copied.'**
  String get safetyCopied;

  /// No description provided for @safetyDone.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get safetyDone;

  /// No description provided for @safetySaved.
  ///
  /// In en, this message translates to:
  /// **'Saved.'**
  String get safetySaved;

  /// No description provided for @safetyBySms.
  ///
  /// In en, this message translates to:
  /// **'SMS'**
  String get safetyBySms;

  /// No description provided for @safetyAccuracy.
  ///
  /// In en, this message translates to:
  /// **'± {meters} m'**
  String safetyAccuracy(int meters);

  /// No description provided for @safetyMinutes.
  ///
  /// In en, this message translates to:
  /// **'{minutes} min'**
  String safetyMinutes(int minutes);

  /// No description provided for @safetyHours.
  ///
  /// In en, this message translates to:
  /// **'{hours} h'**
  String safetyHours(int hours);

  /// No description provided for @safetyHoursMinutes.
  ///
  /// In en, this message translates to:
  /// **'{hours} h {minutes} min'**
  String safetyHoursMinutes(int hours, int minutes);

  /// No description provided for @safetyContactsTitle.
  ///
  /// In en, this message translates to:
  /// **'Emergency contacts'**
  String get safetyContactsTitle;

  /// No description provided for @safetyContactsCount.
  ///
  /// In en, this message translates to:
  /// **'Contacts: {count}'**
  String safetyContactsCount(int count);

  /// No description provided for @safetyContactsIntro.
  ///
  /// In en, this message translates to:
  /// **'Up to 10 people who receive your SOS message by SMS or WhatsApp.'**
  String get safetyContactsIntro;

  /// No description provided for @safetyContactsPrivacy.
  ///
  /// In en, this message translates to:
  /// **'Kept on this phone only. The app never reads or uploads your address book: you choose each number.'**
  String get safetyContactsPrivacy;

  /// No description provided for @safetyContactsFull.
  ///
  /// In en, this message translates to:
  /// **'You reached {max} contacts.'**
  String safetyContactsFull(int max);

  /// No description provided for @safetyContactsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No emergency contact yet.'**
  String get safetyContactsEmpty;

  /// No description provided for @safetyContactAdd.
  ///
  /// In en, this message translates to:
  /// **'Add a contact'**
  String get safetyContactAdd;

  /// No description provided for @safetyContactPick.
  ///
  /// In en, this message translates to:
  /// **'Choose from my contacts'**
  String get safetyContactPick;

  /// No description provided for @safetyContactPickHint.
  ///
  /// In en, this message translates to:
  /// **'Only the number you choose reaches the app.'**
  String get safetyContactPickHint;

  /// No description provided for @safetyContactType.
  ///
  /// In en, this message translates to:
  /// **'Type a number'**
  String get safetyContactType;

  /// No description provided for @safetyContactTitle.
  ///
  /// In en, this message translates to:
  /// **'Emergency contact'**
  String get safetyContactTitle;

  /// No description provided for @safetyContactName.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get safetyContactName;

  /// No description provided for @safetyContactNameRequired.
  ///
  /// In en, this message translates to:
  /// **'Enter a name.'**
  String get safetyContactNameRequired;

  /// No description provided for @safetyContactPhone.
  ///
  /// In en, this message translates to:
  /// **'Phone number'**
  String get safetyContactPhone;

  /// No description provided for @safetyContactExists.
  ///
  /// In en, this message translates to:
  /// **'This number is already in your list.'**
  String get safetyContactExists;

  /// No description provided for @safetyContactLinked.
  ///
  /// In en, this message translates to:
  /// **'Linked: receives the alert in the app'**
  String get safetyContactLinked;

  /// No description provided for @safetyContactGroups.
  ///
  /// In en, this message translates to:
  /// **'Groups'**
  String get safetyContactGroups;

  /// No description provided for @safetyContactDeleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete {name}?'**
  String safetyContactDeleteTitle(String name);

  /// No description provided for @safetyGroupsTitle.
  ///
  /// In en, this message translates to:
  /// **'Groups'**
  String get safetyGroupsTitle;

  /// No description provided for @safetyGroupsEmpty.
  ///
  /// In en, this message translates to:
  /// **'Groups let you warn only some people (family, neighbours…).'**
  String get safetyGroupsEmpty;

  /// No description provided for @safetyGroupAdd.
  ///
  /// In en, this message translates to:
  /// **'New group'**
  String get safetyGroupAdd;

  /// No description provided for @safetyGroupName.
  ///
  /// In en, this message translates to:
  /// **'Group name'**
  String get safetyGroupName;

  /// No description provided for @safetyGroupNameHint.
  ///
  /// In en, this message translates to:
  /// **'Family, neighbours, work…'**
  String get safetyGroupNameHint;

  /// No description provided for @safetyGroupDeleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete the group {name}?'**
  String safetyGroupDeleteTitle(String name);

  /// No description provided for @safetyGroupDeleteBody.
  ///
  /// In en, this message translates to:
  /// **'The contacts stay in your list.'**
  String get safetyGroupDeleteBody;

  /// No description provided for @safetyMessageTitle.
  ///
  /// In en, this message translates to:
  /// **'SOS message'**
  String get safetyMessageTitle;

  /// No description provided for @safetyMessageHint.
  ///
  /// In en, this message translates to:
  /// **'Your text, and the 5-second window to cancel'**
  String get safetyMessageHint;

  /// No description provided for @safetyMessageText.
  ///
  /// In en, this message translates to:
  /// **'Your message'**
  String get safetyMessageText;

  /// No description provided for @safetyMessageAdded.
  ///
  /// In en, this message translates to:
  /// **'The app adds the link to your position, its accuracy, the time and your battery level.'**
  String get safetyMessageAdded;

  /// No description provided for @safetyCancelWindow.
  ///
  /// In en, this message translates to:
  /// **'5 seconds to cancel'**
  String get safetyCancelWindow;

  /// No description provided for @safetyCancelWindowHint.
  ///
  /// In en, this message translates to:
  /// **'Avoids a message sent by mistake. Turn it off to send at once.'**
  String get safetyCancelWindowHint;

  /// No description provided for @safetyPreview.
  ///
  /// In en, this message translates to:
  /// **'Preview'**
  String get safetyPreview;

  /// No description provided for @sosDefaultTemplate.
  ///
  /// In en, this message translates to:
  /// **'I need help. This is my position.'**
  String get sosDefaultTemplate;

  /// No description provided for @sosLabelPosition.
  ///
  /// In en, this message translates to:
  /// **'Position'**
  String get sosLabelPosition;

  /// No description provided for @sosLabelAccuracy.
  ///
  /// In en, this message translates to:
  /// **'Accuracy'**
  String get sosLabelAccuracy;

  /// No description provided for @sosLabelTime.
  ///
  /// In en, this message translates to:
  /// **'Time'**
  String get sosLabelTime;

  /// No description provided for @sosLabelBattery.
  ///
  /// In en, this message translates to:
  /// **'Battery'**
  String get sosLabelBattery;

  /// No description provided for @sosLabelNoPosition.
  ///
  /// In en, this message translates to:
  /// **'Position not available.'**
  String get sosLabelNoPosition;

  /// No description provided for @safetySendIntro.
  ///
  /// In en, this message translates to:
  /// **'Your contacts receive your message with your position. Linked contacts are alerted in the app; the SMS app opens with every number, and you press Send.'**
  String get safetySendIntro;

  /// No description provided for @safetyNoContacts.
  ///
  /// In en, this message translates to:
  /// **'Add at least one emergency contact first.'**
  String get safetyNoContacts;

  /// No description provided for @safetySendTo.
  ///
  /// In en, this message translates to:
  /// **'Send to'**
  String get safetySendTo;

  /// No description provided for @safetySendToAll.
  ///
  /// In en, this message translates to:
  /// **'Everyone ({count})'**
  String safetySendToAll(int count);

  /// No description provided for @safetySendChannels.
  ///
  /// In en, this message translates to:
  /// **'Linked contacts alerted in the app: {count}. Then SMS, then WhatsApp.'**
  String safetySendChannels(int count);

  /// No description provided for @safetySendSmsOnly.
  ///
  /// In en, this message translates to:
  /// **'Without an account, the message goes by SMS and WhatsApp only.'**
  String get safetySendSmsOnly;

  /// No description provided for @safetySendNow.
  ///
  /// In en, this message translates to:
  /// **'Send now'**
  String get safetySendNow;

  /// No description provided for @safetySendingIn.
  ///
  /// In en, this message translates to:
  /// **'Sending in {seconds} s…'**
  String safetySendingIn(int seconds);

  /// No description provided for @safetySending.
  ///
  /// In en, this message translates to:
  /// **'Getting your position and sending…'**
  String get safetySending;

  /// No description provided for @safetySentApp.
  ///
  /// In en, this message translates to:
  /// **'Alert received in the app by {count} linked contact(s).'**
  String safetySentApp(int count);

  /// No description provided for @safetySentAppFailed.
  ///
  /// In en, this message translates to:
  /// **'The alert in the app could not be sent (no network?). The SMS still opened.'**
  String get safetySentAppFailed;

  /// No description provided for @safetySentSms.
  ///
  /// In en, this message translates to:
  /// **'SMS ready for {count} number(s): press Send in the SMS app.'**
  String safetySentSms(int count);

  /// No description provided for @safetyWhatsApp.
  ///
  /// In en, this message translates to:
  /// **'Also by WhatsApp'**
  String get safetyWhatsApp;

  /// No description provided for @safetyWhatsAppChoose.
  ///
  /// In en, this message translates to:
  /// **'Choose a WhatsApp chat or group'**
  String get safetyWhatsAppChoose;

  /// No description provided for @safetyLinkedTitle.
  ///
  /// In en, this message translates to:
  /// **'Linked contacts'**
  String get safetyLinkedTitle;

  /// No description provided for @safetyLinkedCount.
  ///
  /// In en, this message translates to:
  /// **'Linked: {count}'**
  String safetyLinkedCount(int count);

  /// No description provided for @safetyLinkedIntro.
  ///
  /// In en, this message translates to:
  /// **'A relative who also uses e-Himaya can be linked to you. Your SOS message then rings on their phone, even in silent mode.'**
  String get safetyLinkedIntro;

  /// No description provided for @safetyLinkedNeedsAccount.
  ///
  /// In en, this message translates to:
  /// **'Links need an e-Himaya account on both phones.'**
  String get safetyLinkedNeedsAccount;

  /// No description provided for @safetyLinkedEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nobody is linked yet.'**
  String get safetyLinkedEmpty;

  /// No description provided for @safetyLinkedPrivacy.
  ///
  /// In en, this message translates to:
  /// **'A linked person sees your first name and number, and your alerts. Either of you can remove the link at any time.'**
  String get safetyLinkedPrivacy;

  /// No description provided for @safetyLinkedDone.
  ///
  /// In en, this message translates to:
  /// **'You are now linked.'**
  String get safetyLinkedDone;

  /// No description provided for @safetyLinkedPush.
  ///
  /// In en, this message translates to:
  /// **'You are now linked with {name}.'**
  String safetyLinkedPush(String name);

  /// No description provided for @safetyInvite.
  ///
  /// In en, this message translates to:
  /// **'Invite'**
  String get safetyInvite;

  /// No description provided for @safetyInviteTitle.
  ///
  /// In en, this message translates to:
  /// **'Your invitation code'**
  String get safetyInviteTitle;

  /// No description provided for @safetyInviteBody.
  ///
  /// In en, this message translates to:
  /// **'Give this code to the person. They enter it in e-Himaya, Personal safety, Linked contacts.'**
  String get safetyInviteBody;

  /// No description provided for @safetyInviteExpires.
  ///
  /// In en, this message translates to:
  /// **'Valid until {time}, once.'**
  String safetyInviteExpires(String time);

  /// No description provided for @safetyInviteText.
  ///
  /// In en, this message translates to:
  /// **'Link with me in e-Himaya so we can alert each other in an emergency. My code: {code}'**
  String safetyInviteText(String code);

  /// No description provided for @safetyEnterCode.
  ///
  /// In en, this message translates to:
  /// **'Enter a code'**
  String get safetyEnterCode;

  /// No description provided for @safetyCodeInvalid.
  ///
  /// In en, this message translates to:
  /// **'This code is wrong, used or expired.'**
  String get safetyCodeInvalid;

  /// No description provided for @safetyLinkConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Link with this person?'**
  String get safetyLinkConfirmTitle;

  /// No description provided for @safetyLinkConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'{who} will receive your alerts and you will receive theirs.'**
  String safetyLinkConfirmBody(String who);

  /// No description provided for @safetyLinkAccept.
  ///
  /// In en, this message translates to:
  /// **'Link'**
  String get safetyLinkAccept;

  /// No description provided for @safetyUnlink.
  ///
  /// In en, this message translates to:
  /// **'Remove the link'**
  String get safetyUnlink;

  /// No description provided for @safetyUnlinkTitle.
  ///
  /// In en, this message translates to:
  /// **'Remove the link with {name}?'**
  String safetyUnlinkTitle(String name);

  /// No description provided for @safetyUnlinkBody.
  ///
  /// In en, this message translates to:
  /// **'Neither of you will receive the other’s alerts.'**
  String get safetyUnlinkBody;

  /// No description provided for @safetyAlertTitle.
  ///
  /// In en, this message translates to:
  /// **'Distress alert'**
  String get safetyAlertTitle;

  /// No description provided for @safetyAlertFrom.
  ///
  /// In en, this message translates to:
  /// **'{name} needs help'**
  String safetyAlertFrom(String name);

  /// No description provided for @safetyAlertCheckFrom.
  ///
  /// In en, this message translates to:
  /// **'{name} did not confirm being safe'**
  String safetyAlertCheckFrom(String name);

  /// No description provided for @safetyAlertMine.
  ///
  /// In en, this message translates to:
  /// **'Your alert'**
  String get safetyAlertMine;

  /// No description provided for @safetyAlertAt.
  ///
  /// In en, this message translates to:
  /// **'Sent at {time}'**
  String safetyAlertAt(String time);

  /// No description provided for @safetyAlertBattery.
  ///
  /// In en, this message translates to:
  /// **'battery {level}%'**
  String safetyAlertBattery(int level);

  /// No description provided for @safetyAlertSeenBy.
  ///
  /// In en, this message translates to:
  /// **'Opened by {seen} of {total}'**
  String safetyAlertSeenBy(int seen, int total);

  /// No description provided for @safetyAlertNoPosition.
  ///
  /// In en, this message translates to:
  /// **'No position was sent.'**
  String get safetyAlertNoPosition;

  /// No description provided for @safetyAlertLive.
  ///
  /// In en, this message translates to:
  /// **'Live position, updated {time}'**
  String safetyAlertLive(String time);

  /// No description provided for @safetyAlertPositionAt.
  ///
  /// In en, this message translates to:
  /// **'Position at {time}'**
  String safetyAlertPositionAt(String time);

  /// No description provided for @safetyAlertCall.
  ///
  /// In en, this message translates to:
  /// **'Call {name}'**
  String safetyAlertCall(String name);

  /// No description provided for @safetyAlertRoute.
  ///
  /// In en, this message translates to:
  /// **'Route'**
  String get safetyAlertRoute;

  /// No description provided for @safetyAlertReportHint.
  ///
  /// In en, this message translates to:
  /// **'If they are in danger, call the Civil Protection and give the position shown above.'**
  String get safetyAlertReportHint;

  /// No description provided for @safetyAlertCall198.
  ///
  /// In en, this message translates to:
  /// **'Call 198 for them'**
  String get safetyAlertCall198;

  /// No description provided for @safetyAlertReport.
  ///
  /// In en, this message translates to:
  /// **'Report it in the app'**
  String get safetyAlertReport;

  /// No description provided for @safetyLiveTitle.
  ///
  /// In en, this message translates to:
  /// **'Live location'**
  String get safetyLiveTitle;

  /// No description provided for @safetyLiveHint.
  ///
  /// In en, this message translates to:
  /// **'A link that shows where you are, for a limited time'**
  String get safetyLiveHint;

  /// No description provided for @safetyLiveRunning.
  ///
  /// In en, this message translates to:
  /// **'Your location is being shared'**
  String get safetyLiveRunning;

  /// No description provided for @safetyLiveIntro.
  ///
  /// In en, this message translates to:
  /// **'Create a link that shows your position as you move. It stops by itself at the end, or when you press Stop. Whoever has the link sees the point on a map, not your name.'**
  String get safetyLiveIntro;

  /// No description provided for @safetyLiveNeedsAccount.
  ///
  /// In en, this message translates to:
  /// **'Live location needs an e-Himaya account.'**
  String get safetyLiveNeedsAccount;

  /// No description provided for @safetyLiveFor.
  ///
  /// In en, this message translates to:
  /// **'Share for'**
  String get safetyLiveFor;

  /// No description provided for @safetyLiveStart.
  ///
  /// In en, this message translates to:
  /// **'Start sharing'**
  String get safetyLiveStart;

  /// No description provided for @safetyLiveStop.
  ///
  /// In en, this message translates to:
  /// **'Stop sharing'**
  String get safetyLiveStop;

  /// No description provided for @safetyLivePrivacy.
  ///
  /// In en, this message translates to:
  /// **'The positions are deleted 24 hours after the share ends. A notification stays visible while it runs.'**
  String get safetyLivePrivacy;

  /// No description provided for @safetyLiveLeft.
  ///
  /// In en, this message translates to:
  /// **'{duration} left'**
  String safetyLiveLeft(String duration);

  /// No description provided for @safetyLiveLastSent.
  ///
  /// In en, this message translates to:
  /// **'last sent {time}'**
  String safetyLiveLastSent(String time);

  /// No description provided for @safetyLiveShareText.
  ///
  /// In en, this message translates to:
  /// **'Follow my position live: {link}'**
  String safetyLiveShareText(String link);

  /// No description provided for @safetyLiveSmsContacts.
  ///
  /// In en, this message translates to:
  /// **'SMS to my contacts'**
  String get safetyLiveSmsContacts;

  /// No description provided for @safetyLiveNoticeTitle.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya: location shared'**
  String get safetyLiveNoticeTitle;

  /// No description provided for @safetyLiveNoticeText.
  ///
  /// In en, this message translates to:
  /// **'Your position is sent while the share or the safety check runs.'**
  String get safetyLiveNoticeText;

  /// No description provided for @safetyCheckTitle.
  ///
  /// In en, this message translates to:
  /// **'Safety check'**
  String get safetyCheckTitle;

  /// No description provided for @safetyCheckHint.
  ///
  /// In en, this message translates to:
  /// **'Linked contacts alerted if you do not confirm in time'**
  String get safetyCheckHint;

  /// No description provided for @safetyCheckRunning.
  ///
  /// In en, this message translates to:
  /// **'A safety check is running'**
  String get safetyCheckRunning;

  /// No description provided for @safetyCheckIntro.
  ///
  /// In en, this message translates to:
  /// **'Going out alone, walking at night, a trip? Set a time. If you have not pressed “I am fine” by then, your linked contacts receive an alert with your last position, even if your phone is off. The Civil Protection is not alerted.'**
  String get safetyCheckIntro;

  /// No description provided for @safetyCheckNeedsAccount.
  ///
  /// In en, this message translates to:
  /// **'The safety check needs an e-Himaya account and linked contacts.'**
  String get safetyCheckNeedsAccount;

  /// No description provided for @safetyCheckNoLinks.
  ///
  /// In en, this message translates to:
  /// **'Link at least one contact first: the alert goes to linked contacts.'**
  String get safetyCheckNoLinks;

  /// No description provided for @safetyCheckIn.
  ///
  /// In en, this message translates to:
  /// **'Check in after'**
  String get safetyCheckIn;

  /// No description provided for @safetyCheckMessage.
  ///
  /// In en, this message translates to:
  /// **'Message for your contacts'**
  String get safetyCheckMessage;

  /// No description provided for @safetyCheckMessageHint.
  ///
  /// In en, this message translates to:
  /// **'I did not confirm that I arrived safely.'**
  String get safetyCheckMessageHint;

  /// No description provided for @safetyCheckStart.
  ///
  /// In en, this message translates to:
  /// **'Start the check'**
  String get safetyCheckStart;

  /// No description provided for @safetyCheckPrivacy.
  ///
  /// In en, this message translates to:
  /// **'Reminders 10 minutes and 1 minute before. The check and its position are deleted 7 days after it ends.'**
  String get safetyCheckPrivacy;

  /// No description provided for @safetyCheckDue.
  ///
  /// In en, this message translates to:
  /// **'Confirm before {time}'**
  String safetyCheckDue(String time);

  /// No description provided for @safetyCheckContacts.
  ///
  /// In en, this message translates to:
  /// **'linked contacts: {count}'**
  String safetyCheckContacts(int count);

  /// No description provided for @safetyCheckOk.
  ///
  /// In en, this message translates to:
  /// **'I am fine'**
  String get safetyCheckOk;

  /// No description provided for @safetyCheckExtend.
  ///
  /// In en, this message translates to:
  /// **'Add {minutes} minutes'**
  String safetyCheckExtend(int minutes);

  /// No description provided for @safetyCheckFired.
  ///
  /// In en, this message translates to:
  /// **'Your contacts were alerted'**
  String get safetyCheckFired;

  /// No description provided for @safetyCheckFiredHint.
  ///
  /// In en, this message translates to:
  /// **'You did not confirm in time. If you are fine, tell them; otherwise send your SOS message.'**
  String get safetyCheckFiredHint;

  /// No description provided for @safetyCheckReminder10.
  ///
  /// In en, this message translates to:
  /// **'Your safety check ends in 10 minutes. Open e-Himaya to confirm.'**
  String get safetyCheckReminder10;

  /// No description provided for @safetyCheckReminder1.
  ///
  /// In en, this message translates to:
  /// **'One minute left: confirm now or your contacts will be alerted.'**
  String get safetyCheckReminder1;

  /// No description provided for @safetyTestTitle.
  ///
  /// In en, this message translates to:
  /// **'Self-test'**
  String get safetyTestTitle;

  /// No description provided for @safetyTestHint.
  ///
  /// In en, this message translates to:
  /// **'Check that everything works, without sending anything'**
  String get safetyTestHint;

  /// No description provided for @safetyTestIntro.
  ///
  /// In en, this message translates to:
  /// **'Checks this phone: alarm sound, position, network, notifications and battery.'**
  String get safetyTestIntro;

  /// No description provided for @safetyTestAlarm.
  ///
  /// In en, this message translates to:
  /// **'Play the alarm'**
  String get safetyTestAlarm;

  /// No description provided for @safetyTestAlarmTitle.
  ///
  /// In en, this message translates to:
  /// **'Test: distress alert'**
  String get safetyTestAlarmTitle;

  /// No description provided for @safetyTestAlarmBody.
  ///
  /// In en, this message translates to:
  /// **'This is how an alert from a linked contact sounds. Nothing was sent.'**
  String get safetyTestAlarmBody;

  /// No description provided for @safetyTestAlarmSent.
  ///
  /// In en, this message translates to:
  /// **'Test alarm shown.'**
  String get safetyTestAlarmSent;

  /// No description provided for @safetyTestRunning.
  ///
  /// In en, this message translates to:
  /// **'Checking…'**
  String get safetyTestRunning;

  /// No description provided for @safetyTestNotificationsOn.
  ///
  /// In en, this message translates to:
  /// **'Notifications allowed'**
  String get safetyTestNotificationsOn;

  /// No description provided for @safetyTestNotificationsOff.
  ///
  /// In en, this message translates to:
  /// **'Notifications are blocked: alerts cannot reach you'**
  String get safetyTestNotificationsOff;

  /// No description provided for @safetyTestCriticalOn.
  ///
  /// In en, this message translates to:
  /// **'Alerts ring even in silent mode'**
  String get safetyTestCriticalOn;

  /// No description provided for @safetyTestCriticalOff.
  ///
  /// In en, this message translates to:
  /// **'Alerts do not ring in silent mode'**
  String get safetyTestCriticalOff;

  /// No description provided for @safetyTestCriticalFix.
  ///
  /// In en, this message translates to:
  /// **'Turn on'**
  String get safetyTestCriticalFix;

  /// No description provided for @safetyTestDnd.
  ///
  /// In en, this message translates to:
  /// **'Do Not Disturb is on right now'**
  String get safetyTestDnd;

  /// No description provided for @safetyTestOnline.
  ///
  /// In en, this message translates to:
  /// **'Network available'**
  String get safetyTestOnline;

  /// No description provided for @safetyTestOffline.
  ///
  /// In en, this message translates to:
  /// **'No network: only SMS and calls work'**
  String get safetyTestOffline;

  /// No description provided for @safetyTestPosition.
  ///
  /// In en, this message translates to:
  /// **'Position found'**
  String get safetyTestPosition;

  /// No description provided for @safetyTestNoPosition.
  ///
  /// In en, this message translates to:
  /// **'No position: turn on location'**
  String get safetyTestNoPosition;

  /// No description provided for @safetyTestBattery.
  ///
  /// In en, this message translates to:
  /// **'Battery {level}%'**
  String safetyTestBattery(int level);

  /// No description provided for @safetyTestBatteryUnknown.
  ///
  /// In en, this message translates to:
  /// **'Battery level unknown'**
  String get safetyTestBatteryUnknown;

  /// No description provided for @safetyTestPowerSave.
  ///
  /// In en, this message translates to:
  /// **'Battery saver is on: alerts may arrive late'**
  String get safetyTestPowerSave;

  /// No description provided for @safetyTestContacts.
  ///
  /// In en, this message translates to:
  /// **'Emergency contacts: {contacts} · linked: {links}'**
  String safetyTestContacts(int contacts, int links);

  /// No description provided for @safetyTestAgain.
  ///
  /// In en, this message translates to:
  /// **'Test again'**
  String get safetyTestAgain;

  /// No description provided for @safetyTestNothingSent.
  ///
  /// In en, this message translates to:
  /// **'Nothing is sent to anyone during the self-test.'**
  String get safetyTestNothingSent;

  /// No description provided for @safetyRecentTitle.
  ///
  /// In en, this message translates to:
  /// **'Recent alerts'**
  String get safetyRecentTitle;

  /// No description provided for @safetyRecentReceived.
  ///
  /// In en, this message translates to:
  /// **'Received (last 24 hours)'**
  String get safetyRecentReceived;

  /// No description provided for @safetyRecentSentTitle.
  ///
  /// In en, this message translates to:
  /// **'Sent from this phone'**
  String get safetyRecentSentTitle;

  /// No description provided for @safetyRecentClear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get safetyRecentClear;

  /// No description provided for @safetyRecentEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing yet.'**
  String get safetyRecentEmpty;

  /// No description provided for @safetyRecentSos.
  ///
  /// In en, this message translates to:
  /// **'SOS message'**
  String get safetyRecentSos;

  /// No description provided for @safetyRecentSent.
  ///
  /// In en, this message translates to:
  /// **'sent'**
  String get safetyRecentSent;

  /// No description provided for @safetyRecentCancelled.
  ///
  /// In en, this message translates to:
  /// **'cancelled'**
  String get safetyRecentCancelled;

  /// No description provided for @safetyRecentOk.
  ///
  /// In en, this message translates to:
  /// **'done'**
  String get safetyRecentOk;

  /// No description provided for @safetyRecentFailed.
  ///
  /// In en, this message translates to:
  /// **'not sent'**
  String get safetyRecentFailed;

  /// No description provided for @safetyRecentRecipients.
  ///
  /// In en, this message translates to:
  /// **'{count} recipient(s)'**
  String safetyRecentRecipients(int count);

  /// No description provided for @safetyChannelApp.
  ///
  /// In en, this message translates to:
  /// **'app'**
  String get safetyChannelApp;

  /// No description provided for @safetyRecentPrivacy.
  ///
  /// In en, this message translates to:
  /// **'This list stays on this phone.'**
  String get safetyRecentPrivacy;

  /// No description provided for @safetyMedicalTitle.
  ///
  /// In en, this message translates to:
  /// **'Medical file'**
  String get safetyMedicalTitle;

  /// No description provided for @safetyMedicalHint.
  ///
  /// In en, this message translates to:
  /// **'Useful information for rescuers, on this phone only'**
  String get safetyMedicalHint;

  /// No description provided for @safetyMedicalSaved.
  ///
  /// In en, this message translates to:
  /// **'Saved on this phone'**
  String get safetyMedicalSaved;

  /// No description provided for @medicalConsentTitle.
  ///
  /// In en, this message translates to:
  /// **'Before you start'**
  String get medicalConsentTitle;

  /// No description provided for @medicalConsentBody.
  ///
  /// In en, this message translates to:
  /// **'Your medical file is health data. It stays encrypted on this phone. It is sent to the Civil Protection only with a report for which you tick “Attach my medical file”, and is then deleted 30 days after the report is closed. You can change or delete it at any time. Every field is optional.'**
  String get medicalConsentBody;

  /// No description provided for @medicalConsentCheck.
  ///
  /// In en, this message translates to:
  /// **'I agree to keep my medical file on this phone under these conditions'**
  String get medicalConsentCheck;

  /// No description provided for @medicalCreate.
  ///
  /// In en, this message translates to:
  /// **'Create my medical file'**
  String get medicalCreate;

  /// No description provided for @medicalIntro.
  ///
  /// In en, this message translates to:
  /// **'Fill in only what you want. Kept encrypted on this phone.'**
  String get medicalIntro;

  /// No description provided for @medicalSex.
  ///
  /// In en, this message translates to:
  /// **'Sex'**
  String get medicalSex;

  /// No description provided for @medicalSexFemale.
  ///
  /// In en, this message translates to:
  /// **'Female'**
  String get medicalSexFemale;

  /// No description provided for @medicalSexMale.
  ///
  /// In en, this message translates to:
  /// **'Male'**
  String get medicalSexMale;

  /// No description provided for @medicalNotSaid.
  ///
  /// In en, this message translates to:
  /// **'Not given'**
  String get medicalNotSaid;

  /// No description provided for @medicalBirthDate.
  ///
  /// In en, this message translates to:
  /// **'Date of birth'**
  String get medicalBirthDate;

  /// No description provided for @medicalBloodGroup.
  ///
  /// In en, this message translates to:
  /// **'Blood group'**
  String get medicalBloodGroup;

  /// No description provided for @medicalAllergies.
  ///
  /// In en, this message translates to:
  /// **'Allergies'**
  String get medicalAllergies;

  /// No description provided for @medicalConditions.
  ///
  /// In en, this message translates to:
  /// **'Chronic conditions'**
  String get medicalConditions;

  /// No description provided for @medicalMedications.
  ///
  /// In en, this message translates to:
  /// **'Regular medicines'**
  String get medicalMedications;

  /// No description provided for @medicalOther.
  ///
  /// In en, this message translates to:
  /// **'Other (pregnancy, device, disability…)'**
  String get medicalOther;

  /// No description provided for @medicalTreatmentCard.
  ///
  /// In en, this message translates to:
  /// **'Treatment card number'**
  String get medicalTreatmentCard;

  /// No description provided for @medicalContactName.
  ///
  /// In en, this message translates to:
  /// **'Person to contact'**
  String get medicalContactName;

  /// No description provided for @medicalContactPhone.
  ///
  /// In en, this message translates to:
  /// **'Their phone number'**
  String get medicalContactPhone;

  /// No description provided for @medicalContact.
  ///
  /// In en, this message translates to:
  /// **'Contact'**
  String get medicalContact;

  /// No description provided for @medicalLock.
  ///
  /// In en, this message translates to:
  /// **'Ask for the phone lock'**
  String get medicalLock;

  /// No description provided for @medicalLockHint.
  ///
  /// In en, this message translates to:
  /// **'Your PIN, pattern or fingerprint before the file opens.'**
  String get medicalLockHint;

  /// No description provided for @medicalLocked.
  ///
  /// In en, this message translates to:
  /// **'Your medical file is locked.'**
  String get medicalLocked;

  /// No description provided for @medicalUnlock.
  ///
  /// In en, this message translates to:
  /// **'Unlock'**
  String get medicalUnlock;

  /// No description provided for @medicalUnlockHint.
  ///
  /// In en, this message translates to:
  /// **'Confirm it is you to open the medical file.'**
  String get medicalUnlockHint;

  /// No description provided for @medicalNoPhoneLock.
  ///
  /// In en, this message translates to:
  /// **'This phone has no screen lock, so the file cannot be locked.'**
  String get medicalNoPhoneLock;

  /// No description provided for @medicalForRescuer.
  ///
  /// In en, this message translates to:
  /// **'Show to a rescuer'**
  String get medicalForRescuer;

  /// No description provided for @medicalCopy.
  ///
  /// In en, this message translates to:
  /// **'Copy as text'**
  String get medicalCopy;

  /// No description provided for @medicalEmpty.
  ///
  /// In en, this message translates to:
  /// **'The medical file is empty.'**
  String get medicalEmpty;

  /// No description provided for @medicalAttachHint.
  ///
  /// In en, this message translates to:
  /// **'In a report, tick “Attach my medical file” to send it with that report only.'**
  String get medicalAttachHint;

  /// No description provided for @medicalDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete my medical file'**
  String get medicalDelete;

  /// No description provided for @medicalDeleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete the medical file?'**
  String get medicalDeleteTitle;

  /// No description provided for @medicalDeleteBody.
  ///
  /// In en, this message translates to:
  /// **'It is erased from this phone. Copies already attached to reports are deleted 30 days after each report is closed.'**
  String get medicalDeleteBody;

  /// No description provided for @medicalDeleted.
  ///
  /// In en, this message translates to:
  /// **'Medical file deleted.'**
  String get medicalDeleted;

  /// No description provided for @reportAttachMedical.
  ///
  /// In en, this message translates to:
  /// **'Attach my medical file to this report'**
  String get reportAttachMedical;

  /// No description provided for @reportAttachMedicalHint.
  ///
  /// In en, this message translates to:
  /// **'The operations room reads your emergency card only. The rest is locked on your phone for the Civil Protection doctors of the area and the medical committee; each opening is recorded and shown in your app.'**
  String get reportAttachMedicalHint;

  /// No description provided for @safetyHistoryTitle.
  ///
  /// In en, this message translates to:
  /// **'Location history (72 h)'**
  String get safetyHistoryTitle;

  /// No description provided for @safetyHistoryOn.
  ///
  /// In en, this message translates to:
  /// **'On'**
  String get safetyHistoryOn;

  /// No description provided for @safetyHistoryOff.
  ///
  /// In en, this message translates to:
  /// **'Off'**
  String get safetyHistoryOff;

  /// No description provided for @safetyHistoryNotice.
  ///
  /// In en, this message translates to:
  /// **'If you go missing, the Civil Protection can see where your phone was during the last 72 hours. They read it only for a report they handle, with a reason, and you are told. Each position is deleted after 72 hours, and all of them at once when you turn it off.'**
  String get safetyHistoryNotice;

  /// No description provided for @safetyHistoryUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Not available yet.'**
  String get safetyHistoryUnavailable;

  /// No description provided for @safetyHistoryConsent.
  ///
  /// In en, this message translates to:
  /// **'I agree that my positions are kept for 72 hours under these conditions'**
  String get safetyHistoryConsent;

  /// No description provided for @safetyHistoryTurnOn.
  ///
  /// In en, this message translates to:
  /// **'Turn on'**
  String get safetyHistoryTurnOn;

  /// No description provided for @safetyHistoryTurnOff.
  ///
  /// In en, this message translates to:
  /// **'Turn off and delete'**
  String get safetyHistoryTurnOff;

  /// No description provided for @safetyHistoryUntil.
  ///
  /// In en, this message translates to:
  /// **'Until {time}'**
  String safetyHistoryUntil(String time);

  /// No description provided for @safetyHistoryViewedTitle.
  ///
  /// In en, this message translates to:
  /// **'Your location history was consulted'**
  String get safetyHistoryViewedTitle;

  /// No description provided for @safetyHistoryViewedBody.
  ///
  /// In en, this message translates to:
  /// **'The Civil Protection consulted it for a report. Open e-Himaya for details.'**
  String get safetyHistoryViewedBody;

  /// No description provided for @doctorTitle.
  ///
  /// In en, this message translates to:
  /// **'Doctors\' space'**
  String get doctorTitle;

  /// No description provided for @doctorIntro.
  ///
  /// In en, this message translates to:
  /// **'Are you a doctor? Register to receive the medical files attached to reports, locked so that only verified doctors can read them. The Civil Protection checks your registration number before any file reaches you.'**
  String get doctorIntro;

  /// No description provided for @doctorChoose.
  ///
  /// In en, this message translates to:
  /// **'Choose your role'**
  String get doctorChoose;

  /// No description provided for @doctorKindVolunteer.
  ///
  /// In en, this message translates to:
  /// **'Volunteer doctor'**
  String get doctorKindVolunteer;

  /// No description provided for @doctorKindVolunteerHelp.
  ///
  /// In en, this message translates to:
  /// **'A specialist who accepts medical files to give an opinion, when a colleague refers them.'**
  String get doctorKindVolunteerHelp;

  /// No description provided for @doctorKindCivilProtection.
  ///
  /// In en, this message translates to:
  /// **'Civil Protection doctor'**
  String get doctorKindCivilProtection;

  /// No description provided for @doctorKindCivilProtectionHelp.
  ///
  /// In en, this message translates to:
  /// **'A doctor of the Civil Protection: receives the medical files of their gouvernorate\'s reports and refers them to specialists.'**
  String get doctorKindCivilProtectionHelp;

  /// No description provided for @doctorApply.
  ///
  /// In en, this message translates to:
  /// **'Register as a doctor'**
  String get doctorApply;

  /// No description provided for @doctorKind.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get doctorKind;

  /// No description provided for @doctorSpecialties.
  ///
  /// In en, this message translates to:
  /// **'Specialties (1 to 4)'**
  String get doctorSpecialties;

  /// No description provided for @doctorSpecialtiesRequired.
  ///
  /// In en, this message translates to:
  /// **'Choose 1 to 4 specialties.'**
  String get doctorSpecialtiesRequired;

  /// No description provided for @doctorLicence.
  ///
  /// In en, this message translates to:
  /// **'Medical council registration number'**
  String get doctorLicence;

  /// No description provided for @doctorNumberInvalid.
  ///
  /// In en, this message translates to:
  /// **'3 to 30 characters: digits, Latin letters, - and /.'**
  String get doctorNumberInvalid;

  /// No description provided for @doctorWorkplace.
  ///
  /// In en, this message translates to:
  /// **'Workplace (institution)'**
  String get doctorWorkplace;

  /// No description provided for @doctorGouvernorat.
  ///
  /// In en, this message translates to:
  /// **'Gouvernorate of the workplace'**
  String get doctorGouvernorat;

  /// No description provided for @doctorGouvernoratHelp.
  ///
  /// In en, this message translates to:
  /// **'It sets your doctors\' group.'**
  String get doctorGouvernoratHelp;

  /// No description provided for @doctorCpUnit.
  ///
  /// In en, this message translates to:
  /// **'Unit or regional directorate'**
  String get doctorCpUnit;

  /// No description provided for @doctorCpStaffNo.
  ///
  /// In en, this message translates to:
  /// **'Staff number'**
  String get doctorCpStaffNo;

  /// No description provided for @doctorTermsTitle.
  ///
  /// In en, this message translates to:
  /// **'Terms of the doctor role'**
  String get doctorTermsTitle;

  /// No description provided for @doctorTermsBody.
  ///
  /// In en, this message translates to:
  /// **'Medical files are confidential: they are opened only to help the person, never copied or shared outside the system, and every opening is recorded. An opinion given remotely is advisory and does not replace an examination. The Civil Protection may suspend your role if these terms are broken.'**
  String get doctorTermsBody;

  /// No description provided for @doctorTermsAccept.
  ///
  /// In en, this message translates to:
  /// **'I have read and accept these terms'**
  String get doctorTermsAccept;

  /// No description provided for @doctorTermsRequired.
  ///
  /// In en, this message translates to:
  /// **'You must accept the terms.'**
  String get doctorTermsRequired;

  /// No description provided for @doctorRecheckNote.
  ///
  /// In en, this message translates to:
  /// **'Changing the role, specialties, numbers or gouvernorate sends your registration back for checking.'**
  String get doctorRecheckNote;

  /// No description provided for @doctorSubmit.
  ///
  /// In en, this message translates to:
  /// **'Send for checking'**
  String get doctorSubmit;

  /// No description provided for @doctorSubmitted.
  ///
  /// In en, this message translates to:
  /// **'Sent. The Civil Protection will check your registration number.'**
  String get doctorSubmitted;

  /// No description provided for @doctorHelpPending.
  ///
  /// In en, this message translates to:
  /// **'Your registration is being checked. No medical file reaches you before.'**
  String get doctorHelpPending;

  /// No description provided for @doctorHelpApproved.
  ///
  /// In en, this message translates to:
  /// **'Your role is verified: you are in your gouvernorate\'s doctors\' group.'**
  String get doctorHelpApproved;

  /// No description provided for @doctorHelpRejected.
  ///
  /// In en, this message translates to:
  /// **'Your registration was not accepted. You can correct it and send it again.'**
  String get doctorHelpRejected;

  /// No description provided for @doctorHelpSuspended.
  ///
  /// In en, this message translates to:
  /// **'Your role is suspended: you will not receive medical files.'**
  String get doctorHelpSuspended;

  /// No description provided for @doctorHelpWithdrawn.
  ///
  /// In en, this message translates to:
  /// **'You gave up the doctor role; your numbers are deleted.'**
  String get doctorHelpWithdrawn;

  /// No description provided for @doctorAvailable.
  ///
  /// In en, this message translates to:
  /// **'Available for requests'**
  String get doctorAvailable;

  /// No description provided for @doctorAvailableUntil.
  ///
  /// In en, this message translates to:
  /// **'Available until {time}'**
  String doctorAvailableUntil(String time);

  /// No description provided for @doctorCommitteeMember.
  ///
  /// In en, this message translates to:
  /// **'Member of the medical committee until {date}'**
  String doctorCommitteeMember(String date);

  /// No description provided for @doctorCommitteeHelp.
  ///
  /// In en, this message translates to:
  /// **'Appointed by the system administrator. From this account you will consult the medical files and the specialists\' opinions of every gouvernorat. Each opening needs a reason and is logged; the citizen sees “Medical committee”, not your name.'**
  String get doctorCommitteeHelp;

  /// No description provided for @doctorAvailableHelp.
  ///
  /// In en, this message translates to:
  /// **'Available doctors come first in the referral list. It ends by itself after 8 hours.'**
  String get doctorAvailableHelp;

  /// No description provided for @doctorAvailableBadge.
  ///
  /// In en, this message translates to:
  /// **'Available'**
  String get doctorAvailableBadge;

  /// No description provided for @medicalCardTitle.
  ///
  /// In en, this message translates to:
  /// **'Emergency card'**
  String get medicalCardTitle;

  /// No description provided for @medicalCardHint.
  ///
  /// In en, this message translates to:
  /// **'What you tick stays readable by the operations room and the rescuers. The other fields are locked for the doctors only.'**
  String get medicalCardHint;

  /// No description provided for @errorDoctorKeyMissing.
  ///
  /// In en, this message translates to:
  /// **'Create your personal key first.'**
  String get errorDoctorKeyMissing;

  /// No description provided for @errorNotCommitteeMember.
  ///
  /// In en, this message translates to:
  /// **'You are no longer on the medical committee.'**
  String get errorNotCommitteeMember;

  /// No description provided for @errorReasonRequired.
  ///
  /// In en, this message translates to:
  /// **'Give a reason.'**
  String get errorReasonRequired;

  /// No description provided for @doctorKeyTitle.
  ///
  /// In en, this message translates to:
  /// **'My personal key'**
  String get doctorKeyTitle;

  /// No description provided for @doctorKeyCreateHelp.
  ///
  /// In en, this message translates to:
  /// **'Medical files are locked for you with a key protected by a code you choose. We do not know your code and cannot recover it.'**
  String get doctorKeyCreateHelp;

  /// No description provided for @doctorKeyReady.
  ///
  /// In en, this message translates to:
  /// **'Your key is ready on this phone.'**
  String get doctorKeyReady;

  /// No description provided for @doctorKeyRestoreHelp.
  ///
  /// In en, this message translates to:
  /// **'Your key is not on this phone. Enter your code to get it back.'**
  String get doctorKeyRestoreHelp;

  /// No description provided for @doctorKeyCreate.
  ///
  /// In en, this message translates to:
  /// **'Create my key'**
  String get doctorKeyCreate;

  /// No description provided for @doctorKeyRestore.
  ///
  /// In en, this message translates to:
  /// **'Get my key back'**
  String get doctorKeyRestore;

  /// No description provided for @doctorKeyForgot.
  ///
  /// In en, this message translates to:
  /// **'I forgot my code'**
  String get doctorKeyForgot;

  /// No description provided for @doctorKeyResetWarning.
  ///
  /// In en, this message translates to:
  /// **'A new key will be created. Files received with the old one can no longer be opened unless a colleague refers them to you again.'**
  String get doctorKeyResetWarning;

  /// No description provided for @doctorKeyNew.
  ///
  /// In en, this message translates to:
  /// **'New key'**
  String get doctorKeyNew;

  /// No description provided for @doctorKeyChooseCode.
  ///
  /// In en, this message translates to:
  /// **'Choose your code'**
  String get doctorKeyChooseCode;

  /// No description provided for @doctorKeyEnterCode.
  ///
  /// In en, this message translates to:
  /// **'Enter your code'**
  String get doctorKeyEnterCode;

  /// No description provided for @doctorKeyCodeHint.
  ///
  /// In en, this message translates to:
  /// **'6 to 12 digits. Keep it safe: it cannot be recovered.'**
  String get doctorKeyCodeHint;

  /// No description provided for @doctorKeyCode.
  ///
  /// In en, this message translates to:
  /// **'Code'**
  String get doctorKeyCode;

  /// No description provided for @doctorKeyCodeAgain.
  ///
  /// In en, this message translates to:
  /// **'Repeat the code'**
  String get doctorKeyCodeAgain;

  /// No description provided for @doctorKeyCodeInvalid.
  ///
  /// In en, this message translates to:
  /// **'The code has 6 to 12 digits.'**
  String get doctorKeyCodeInvalid;

  /// No description provided for @doctorKeyCodeMismatch.
  ///
  /// In en, this message translates to:
  /// **'The two codes differ.'**
  String get doctorKeyCodeMismatch;

  /// No description provided for @doctorKeyWrongCode.
  ///
  /// In en, this message translates to:
  /// **'Wrong code.'**
  String get doctorKeyWrongCode;

  /// No description provided for @doctorFiles.
  ///
  /// In en, this message translates to:
  /// **'Medical files'**
  String get doctorFiles;

  /// No description provided for @doctorFilesEmpty.
  ///
  /// In en, this message translates to:
  /// **'No medical files yet.'**
  String get doctorFilesEmpty;

  /// No description provided for @doctorFileViaGouvernorat.
  ///
  /// In en, this message translates to:
  /// **'Your gouvernorat'**
  String get doctorFileViaGouvernorat;

  /// No description provided for @doctorFileViaCommittee.
  ///
  /// In en, this message translates to:
  /// **'Medical committee'**
  String get doctorFileViaCommittee;

  /// No description provided for @doctorFileViaReferral.
  ///
  /// In en, this message translates to:
  /// **'Referral'**
  String get doctorFileViaReferral;

  /// No description provided for @doctorFileReasonTitle.
  ///
  /// In en, this message translates to:
  /// **'Reason for opening'**
  String get doctorFileReasonTitle;

  /// No description provided for @doctorFileReasonHint.
  ///
  /// In en, this message translates to:
  /// **'The reason is recorded. The citizen sees “Medical committee”, not your name.'**
  String get doctorFileReasonHint;

  /// No description provided for @doctorFileOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get doctorFileOpen;

  /// No description provided for @doctorFileConfidential.
  ///
  /// In en, this message translates to:
  /// **'Confidential file: do not copy or share it. Opened on this phone only, and the opening is recorded.'**
  String get doctorFileConfidential;

  /// No description provided for @doctorFileCannotOpen.
  ///
  /// In en, this message translates to:
  /// **'The file cannot be opened with your key.'**
  String get doctorFileCannotOpen;

  /// No description provided for @doctorDirectory.
  ///
  /// In en, this message translates to:
  /// **'Doctors\' directory'**
  String get doctorDirectory;

  /// No description provided for @doctorSpecialty.
  ///
  /// In en, this message translates to:
  /// **'Specialty'**
  String get doctorSpecialty;

  /// No description provided for @doctorRegion.
  ///
  /// In en, this message translates to:
  /// **'Region'**
  String get doctorRegion;

  /// No description provided for @doctorAllSpecialties.
  ///
  /// In en, this message translates to:
  /// **'All specialties'**
  String get doctorAllSpecialties;

  /// No description provided for @doctorAllGouvernorats.
  ///
  /// In en, this message translates to:
  /// **'All gouvernorates'**
  String get doctorAllGouvernorats;

  /// No description provided for @doctorDirectoryEmpty.
  ///
  /// In en, this message translates to:
  /// **'No verified doctor matches.'**
  String get doctorDirectoryEmpty;

  /// No description provided for @doctorEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit my details'**
  String get doctorEdit;

  /// No description provided for @doctorWithdraw.
  ///
  /// In en, this message translates to:
  /// **'Give up the doctor role'**
  String get doctorWithdraw;

  /// No description provided for @doctorWithdrawConfirm.
  ///
  /// In en, this message translates to:
  /// **'Your registration number will be deleted and no file will reach you. You can register again later.'**
  String get doctorWithdrawConfirm;

  /// No description provided for @doctorJoinTitle.
  ///
  /// In en, this message translates to:
  /// **'Are you a doctor?'**
  String get doctorJoinTitle;

  /// No description provided for @doctorJoinBody.
  ///
  /// In en, this message translates to:
  /// **'Register as a volunteer or Civil Protection doctor.'**
  String get doctorJoinBody;

  /// No description provided for @errorNotDoctor.
  ///
  /// In en, this message translates to:
  /// **'You have not registered as a doctor.'**
  String get errorNotDoctor;

  /// No description provided for @errorDoctorNotApproved.
  ///
  /// In en, this message translates to:
  /// **'Your doctor role is not verified yet.'**
  String get errorDoctorNotApproved;

  /// No description provided for @errorCpDetailsRequired.
  ///
  /// In en, this message translates to:
  /// **'Enter the unit and staff number of a Civil Protection doctor.'**
  String get errorCpDetailsRequired;

  /// No description provided for @errorUnknownTermsVersion.
  ///
  /// In en, this message translates to:
  /// **'The terms changed. Update the app and try again.'**
  String get errorUnknownTermsVersion;

  /// No description provided for @specialtyGeneralPractice.
  ///
  /// In en, this message translates to:
  /// **'General practice'**
  String get specialtyGeneralPractice;

  /// No description provided for @specialtyEmergencyMedicine.
  ///
  /// In en, this message translates to:
  /// **'Emergency medicine'**
  String get specialtyEmergencyMedicine;

  /// No description provided for @specialtyAnesthesiaIcu.
  ///
  /// In en, this message translates to:
  /// **'Anaesthesia and intensive care'**
  String get specialtyAnesthesiaIcu;

  /// No description provided for @specialtyCardiology.
  ///
  /// In en, this message translates to:
  /// **'Cardiology'**
  String get specialtyCardiology;

  /// No description provided for @specialtyPulmonology.
  ///
  /// In en, this message translates to:
  /// **'Pulmonology'**
  String get specialtyPulmonology;

  /// No description provided for @specialtyNeurology.
  ///
  /// In en, this message translates to:
  /// **'Neurology'**
  String get specialtyNeurology;

  /// No description provided for @specialtyPediatrics.
  ///
  /// In en, this message translates to:
  /// **'Paediatrics'**
  String get specialtyPediatrics;

  /// No description provided for @specialtyObstetricsGynecology.
  ///
  /// In en, this message translates to:
  /// **'Obstetrics and gynaecology'**
  String get specialtyObstetricsGynecology;

  /// No description provided for @specialtyInternalMedicine.
  ///
  /// In en, this message translates to:
  /// **'Internal medicine'**
  String get specialtyInternalMedicine;

  /// No description provided for @specialtyEndocrinology.
  ///
  /// In en, this message translates to:
  /// **'Endocrinology and diabetes'**
  String get specialtyEndocrinology;

  /// No description provided for @specialtyNephrology.
  ///
  /// In en, this message translates to:
  /// **'Nephrology'**
  String get specialtyNephrology;

  /// No description provided for @specialtyGastroenterology.
  ///
  /// In en, this message translates to:
  /// **'Gastroenterology'**
  String get specialtyGastroenterology;

  /// No description provided for @specialtyAllergyImmunology.
  ///
  /// In en, this message translates to:
  /// **'Allergy and immunology'**
  String get specialtyAllergyImmunology;

  /// No description provided for @specialtyInfectiousDiseases.
  ///
  /// In en, this message translates to:
  /// **'Infectious diseases'**
  String get specialtyInfectiousDiseases;

  /// No description provided for @specialtyDermatologyBurns.
  ///
  /// In en, this message translates to:
  /// **'Dermatology and burns'**
  String get specialtyDermatologyBurns;

  /// No description provided for @specialtyOrthopedics.
  ///
  /// In en, this message translates to:
  /// **'Orthopaedics and trauma'**
  String get specialtyOrthopedics;

  /// No description provided for @specialtyGeneralSurgery.
  ///
  /// In en, this message translates to:
  /// **'General surgery'**
  String get specialtyGeneralSurgery;

  /// No description provided for @specialtyPsychiatry.
  ///
  /// In en, this message translates to:
  /// **'Psychiatry'**
  String get specialtyPsychiatry;

  /// No description provided for @specialtyToxicology.
  ///
  /// In en, this message translates to:
  /// **'Toxicology'**
  String get specialtyToxicology;

  /// No description provided for @specialtyOphthalmology.
  ///
  /// In en, this message translates to:
  /// **'Ophthalmology'**
  String get specialtyOphthalmology;

  /// No description provided for @specialtyEnt.
  ///
  /// In en, this message translates to:
  /// **'Ear, nose and throat'**
  String get specialtyEnt;

  /// No description provided for @doctorRefer.
  ///
  /// In en, this message translates to:
  /// **'Refer to a specialist'**
  String get doctorRefer;

  /// No description provided for @doctorReferTitle.
  ///
  /// In en, this message translates to:
  /// **'Refer the file'**
  String get doctorReferTitle;

  /// No description provided for @doctorReferHint.
  ///
  /// In en, this message translates to:
  /// **'The file key is locked on your phone for each doctor you choose; the server never sees it. At most five referrals per file.'**
  String get doctorReferHint;

  /// No description provided for @doctorReferPickSpecialty.
  ///
  /// In en, this message translates to:
  /// **'Choose the specialty first.'**
  String get doctorReferPickSpecialty;

  /// No description provided for @doctorReferNoKey.
  ///
  /// In en, this message translates to:
  /// **'Has not set their key yet'**
  String get doctorReferNoKey;

  /// No description provided for @doctorReferReason.
  ///
  /// In en, this message translates to:
  /// **'Reason for the referral'**
  String get doctorReferReason;

  /// No description provided for @doctorReferSend.
  ///
  /// In en, this message translates to:
  /// **'Refer'**
  String get doctorReferSend;

  /// No description provided for @doctorReferDone.
  ///
  /// In en, this message translates to:
  /// **'File referred. The doctor gets a notification without any content.'**
  String get doctorReferDone;

  /// No description provided for @doctorReferrals.
  ///
  /// In en, this message translates to:
  /// **'Referrals'**
  String get doctorReferrals;

  /// No description provided for @doctorReferralsMine.
  ///
  /// In en, this message translates to:
  /// **'Referred by you'**
  String get doctorReferralsMine;

  /// No description provided for @doctorOpinions.
  ///
  /// In en, this message translates to:
  /// **'Medical opinions'**
  String get doctorOpinions;

  /// No description provided for @doctorOpinionsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No opinion yet.'**
  String get doctorOpinionsEmpty;

  /// No description provided for @doctorOpinionWrite.
  ///
  /// In en, this message translates to:
  /// **'Write an opinion'**
  String get doctorOpinionWrite;

  /// No description provided for @doctorOpinionHint.
  ///
  /// In en, this message translates to:
  /// **'An advisory opinion locked on your phone for the gouvernorat and committee doctors holding the file, and for the doctor who referred it.'**
  String get doctorOpinionHint;

  /// No description provided for @doctorOpinionSend.
  ///
  /// In en, this message translates to:
  /// **'Send the opinion'**
  String get doctorOpinionSend;

  /// No description provided for @doctorOpinionSent.
  ///
  /// In en, this message translates to:
  /// **'Opinion sent, locked.'**
  String get doctorOpinionSent;

  /// No description provided for @doctorOpinionMine.
  ///
  /// In en, this message translates to:
  /// **'Your opinion'**
  String get doctorOpinionMine;

  /// No description provided for @doctorOpinionCannotOpen.
  ///
  /// In en, this message translates to:
  /// **'This opinion cannot be opened with your key.'**
  String get doctorOpinionCannotOpen;

  /// No description provided for @doctorPendingTitle.
  ///
  /// In en, this message translates to:
  /// **'Files waiting for a new member'**
  String get doctorPendingTitle;

  /// No description provided for @doctorPendingShare.
  ///
  /// In en, this message translates to:
  /// **'Lock for them'**
  String get doctorPendingShare;

  /// No description provided for @doctorPendingReasonHint.
  ///
  /// In en, this message translates to:
  /// **'Your phone opens each file to lock its key for the new member. Each opening is recorded with the reason.'**
  String get doctorPendingReasonHint;

  /// No description provided for @doctorPendingDone.
  ///
  /// In en, this message translates to:
  /// **'The files are now available to the new member.'**
  String get doctorPendingDone;

  /// No description provided for @medicalOpeningsTitle.
  ///
  /// In en, this message translates to:
  /// **'Who saw my medical file'**
  String get medicalOpeningsTitle;

  /// No description provided for @medicalOpeningsEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nobody has opened the locked part of your file.'**
  String get medicalOpeningsEmpty;

  /// No description provided for @medicalOpeningsNote.
  ///
  /// In en, this message translates to:
  /// **'Only the role is shown, never the doctors\' names.'**
  String get medicalOpeningsNote;

  /// No description provided for @medicalOpeningCommittee.
  ///
  /// In en, this message translates to:
  /// **'The medical committee'**
  String get medicalOpeningCommittee;

  /// No description provided for @medicalOpeningOpened.
  ///
  /// In en, this message translates to:
  /// **'Opened the file'**
  String get medicalOpeningOpened;

  /// No description provided for @pushMedicalReferralTitle.
  ///
  /// In en, this message translates to:
  /// **'A medical file was referred to you'**
  String get pushMedicalReferralTitle;

  /// No description provided for @pushMedicalReferralBody.
  ///
  /// In en, this message translates to:
  /// **'Open it in the doctor\'s space.'**
  String get pushMedicalReferralBody;

  /// No description provided for @pushMedicalOpinionTitle.
  ///
  /// In en, this message translates to:
  /// **'New medical opinion'**
  String get pushMedicalOpinionTitle;

  /// No description provided for @pushMedicalOpinionBody.
  ///
  /// In en, this message translates to:
  /// **'A specialist\'s opinion on a file you follow. Open it in the doctor\'s space.'**
  String get pushMedicalOpinionBody;

  /// No description provided for @errorTooManyReferrals.
  ///
  /// In en, this message translates to:
  /// **'The file reached the maximum number of referrals (5).'**
  String get errorTooManyReferrals;

  /// No description provided for @errorAlreadyHoldsFile.
  ///
  /// In en, this message translates to:
  /// **'One of the chosen doctors already holds the file.'**
  String get errorAlreadyHoldsFile;

  /// No description provided for @errorReferralNotAllowed.
  ///
  /// In en, this message translates to:
  /// **'A specialist cannot refer the file on.'**
  String get errorReferralNotAllowed;

  /// No description provided for @errorRecipientsChanged.
  ///
  /// In en, this message translates to:
  /// **'The list of readers changed. Try again.'**
  String get errorRecipientsChanged;

  /// No description provided for @errorInvalidRecipient.
  ///
  /// In en, this message translates to:
  /// **'The file cannot be locked for this doctor.'**
  String get errorInvalidRecipient;

  /// No description provided for @doctorPendingBody.
  ///
  /// In en, this message translates to:
  /// **'{count} item(s) for {name}'**
  String doctorPendingBody(int count, String name);

  /// No description provided for @doctorOpinionBy.
  ///
  /// In en, this message translates to:
  /// **'Specialist: {specialty}'**
  String doctorOpinionBy(String specialty);

  /// No description provided for @medicalOpeningCp.
  ///
  /// In en, this message translates to:
  /// **'Civil Protection doctor, gouvernorat of {gouvernorat}'**
  String medicalOpeningCp(String gouvernorat);

  /// No description provided for @medicalOpeningSpecialist.
  ///
  /// In en, this message translates to:
  /// **'Specialist: {specialty}, {workplace}'**
  String medicalOpeningSpecialist(String specialty, String workplace);

  /// No description provided for @medicalOpeningReferral.
  ///
  /// In en, this message translates to:
  /// **'Your file was referred to a specialist in {specialty}'**
  String medicalOpeningReferral(String specialty);

  /// No description provided for @medicalOpeningsCount.
  ///
  /// In en, this message translates to:
  /// **'Who saw my medical file ({count})'**
  String medicalOpeningsCount(int count);

  /// Environment strip at the top of every screen (backlog G3).
  ///
  /// In en, this message translates to:
  /// **'[SIM] Development environment: all data is test data'**
  String get envBannerDevelopment;

  /// Environment strip at the top of every screen (backlog G3).
  ///
  /// In en, this message translates to:
  /// **'[SIM] Field pilot environment: test data'**
  String get envBannerPilot;

  /// Environment strip at the top of every screen (backlog G3).
  ///
  /// In en, this message translates to:
  /// **'[SIM] Exercise: test data, not real reports'**
  String get envBannerTraining;

  /// No description provided for @orgReadiness.
  ///
  /// In en, this message translates to:
  /// **'Readiness'**
  String get orgReadiness;

  /// No description provided for @orgReadinessMissing.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 missing requirement} other{{count} missing requirements}}'**
  String orgReadinessMissing(int count);

  /// No description provided for @orgReadinessDone.
  ///
  /// In en, this message translates to:
  /// **'All requirements are met'**
  String get orgReadinessDone;

  /// No description provided for @orgMissingTitle.
  ///
  /// In en, this message translates to:
  /// **'Missing requirements'**
  String get orgMissingTitle;

  /// No description provided for @orgSectionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Sections'**
  String get orgSectionsTitle;

  /// No description provided for @orgSectionCard.
  ///
  /// In en, this message translates to:
  /// **'Card'**
  String get orgSectionCard;

  /// No description provided for @orgSectionEquipment.
  ///
  /// In en, this message translates to:
  /// **'Equipment and maintenance'**
  String get orgSectionEquipment;

  /// No description provided for @orgSectionHazmat.
  ///
  /// In en, this message translates to:
  /// **'Hazardous materials'**
  String get orgSectionHazmat;

  /// No description provided for @orgSectionEvacuation.
  ///
  /// In en, this message translates to:
  /// **'Evacuation'**
  String get orgSectionEvacuation;

  /// No description provided for @orgSectionReports.
  ///
  /// In en, this message translates to:
  /// **'Reports'**
  String get orgSectionReports;

  /// No description provided for @orgSectionCertificates.
  ///
  /// In en, this message translates to:
  /// **'Certificates'**
  String get orgSectionCertificates;

  /// No description provided for @orgSectionMembers.
  ///
  /// In en, this message translates to:
  /// **'Members and roles'**
  String get orgSectionMembers;

  /// No description provided for @orgSectionPortal.
  ///
  /// In en, this message translates to:
  /// **'Portal'**
  String get orgSectionPortal;

  /// No description provided for @orgReportAs.
  ///
  /// In en, this message translates to:
  /// **'Report for the institution'**
  String get orgReportAs;

  /// No description provided for @orgPendingNote.
  ///
  /// In en, this message translates to:
  /// **'Under review: reporting for the institution becomes possible once the Office approves it.'**
  String get orgPendingNote;

  /// No description provided for @orgRegister.
  ///
  /// In en, this message translates to:
  /// **'Register an institution'**
  String get orgRegister;

  /// No description provided for @orgRegisterStep.
  ///
  /// In en, this message translates to:
  /// **'Step {current} of {total}'**
  String orgRegisterStep(int current, int total);

  /// No description provided for @orgRegisterKindTitle.
  ///
  /// In en, this message translates to:
  /// **'What kind is your institution?'**
  String get orgRegisterKindTitle;

  /// No description provided for @orgRegisterIdentityTitle.
  ///
  /// In en, this message translates to:
  /// **'Identifier and contact'**
  String get orgRegisterIdentityTitle;

  /// No description provided for @orgRegisterLocationTitle.
  ///
  /// In en, this message translates to:
  /// **'Location and building'**
  String get orgRegisterLocationTitle;

  /// No description provided for @orgRegisterReviewTitle.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get orgRegisterReviewTitle;

  /// No description provided for @orgName.
  ///
  /// In en, this message translates to:
  /// **'Institution name'**
  String get orgName;

  /// No description provided for @orgIdentifierType.
  ///
  /// In en, this message translates to:
  /// **'Identifier type'**
  String get orgIdentifierType;

  /// No description provided for @orgIdentifierMf.
  ///
  /// In en, this message translates to:
  /// **'Tax identifier'**
  String get orgIdentifierMf;

  /// No description provided for @orgIdentifierRne.
  ///
  /// In en, this message translates to:
  /// **'National business register'**
  String get orgIdentifierRne;

  /// No description provided for @orgIdentifier.
  ///
  /// In en, this message translates to:
  /// **'Identifier'**
  String get orgIdentifier;

  /// No description provided for @orgManagerName.
  ///
  /// In en, this message translates to:
  /// **'Manager: full name'**
  String get orgManagerName;

  /// No description provided for @orgManagerPhone.
  ///
  /// In en, this message translates to:
  /// **'Manager: phone'**
  String get orgManagerPhone;

  /// No description provided for @orgContactEmail.
  ///
  /// In en, this message translates to:
  /// **'Institution e-mail'**
  String get orgContactEmail;

  /// No description provided for @orgUseMyLocation.
  ///
  /// In en, this message translates to:
  /// **'Use my current location'**
  String get orgUseMyLocation;

  /// No description provided for @orgLocationSet.
  ///
  /// In en, this message translates to:
  /// **'Location: {lat}, {lon}'**
  String orgLocationSet(String lat, String lon);

  /// No description provided for @orgLocationUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Location unavailable. Turn on location and try again.'**
  String get orgLocationUnavailable;

  /// No description provided for @orgLocationRequired.
  ///
  /// In en, this message translates to:
  /// **'Set the institution\'s location.'**
  String get orgLocationRequired;

  /// No description provided for @orgReceivesPublic.
  ///
  /// In en, this message translates to:
  /// **'Receives the public'**
  String get orgReceivesPublic;

  /// No description provided for @orgFloors.
  ///
  /// In en, this message translates to:
  /// **'Floors'**
  String get orgFloors;

  /// No description provided for @orgHeight.
  ///
  /// In en, this message translates to:
  /// **'Height (m)'**
  String get orgHeight;

  /// No description provided for @orgNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get orgNext;

  /// No description provided for @orgBack.
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get orgBack;

  /// No description provided for @orgSubmit.
  ///
  /// In en, this message translates to:
  /// **'Send the registration'**
  String get orgSubmit;

  /// No description provided for @orgRegisteredTitle.
  ///
  /// In en, this message translates to:
  /// **'Registration sent'**
  String get orgRegisteredTitle;

  /// No description provided for @orgRegisteredBody.
  ///
  /// In en, this message translates to:
  /// **'The institution stays “under review” until the Office approves it.'**
  String get orgRegisteredBody;

  /// No description provided for @orgOpenInstitution.
  ///
  /// In en, this message translates to:
  /// **'Open “My institution”'**
  String get orgOpenInstitution;

  /// No description provided for @orgInvalidIdentifier.
  ///
  /// In en, this message translates to:
  /// **'Invalid identifier: 7 digits and a letter.'**
  String get orgInvalidIdentifier;

  /// No description provided for @orgInvalidPhone.
  ///
  /// In en, this message translates to:
  /// **'Phone: 8 digits, or +216 followed by 8 digits.'**
  String get orgInvalidPhone;

  /// No description provided for @orgInvalidNumber.
  ///
  /// In en, this message translates to:
  /// **'Enter a whole number within the limits.'**
  String get orgInvalidNumber;

  /// No description provided for @orgInvalidEmail.
  ///
  /// In en, this message translates to:
  /// **'Invalid e-mail.'**
  String get orgInvalidEmail;

  /// No description provided for @orgEmailNotVerified.
  ///
  /// In en, this message translates to:
  /// **'Confirm your e-mail before registering an institution.'**
  String get orgEmailNotVerified;

  /// No description provided for @orgIdentifierTaken.
  ///
  /// In en, this message translates to:
  /// **'This identifier is already registered.'**
  String get orgIdentifierTaken;

  /// No description provided for @orgKindFieldsTitle.
  ///
  /// In en, this message translates to:
  /// **'Kind-specific'**
  String get orgKindFieldsTitle;

  /// No description provided for @orgKindFieldsSim.
  ///
  /// In en, this message translates to:
  /// **'Working list [SIM] pending the Office\'s approval'**
  String get orgKindFieldsSim;

  /// No description provided for @orgKindFieldsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No field specific to this kind.'**
  String get orgKindFieldsEmpty;

  /// No description provided for @orgCardTabIdentity.
  ///
  /// In en, this message translates to:
  /// **'Identity'**
  String get orgCardTabIdentity;

  /// No description provided for @orgCardTabBuilding.
  ///
  /// In en, this message translates to:
  /// **'Building'**
  String get orgCardTabBuilding;

  /// No description provided for @orgEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get orgEdit;

  /// No description provided for @orgSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get orgSave;

  /// No description provided for @orgCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get orgCancel;

  /// No description provided for @orgSaved.
  ///
  /// In en, this message translates to:
  /// **'Saved.'**
  String get orgSaved;

  /// No description provided for @orgVersionConflict.
  ///
  /// In en, this message translates to:
  /// **'Someone else changed the card meanwhile. Reload and try again.'**
  String get orgVersionConflict;

  /// No description provided for @orgYes.
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get orgYes;

  /// No description provided for @orgNo.
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get orgNo;

  /// No description provided for @orgNotSet.
  ///
  /// In en, this message translates to:
  /// **'Not set'**
  String get orgNotSet;

  /// No description provided for @orgEquipmentEmpty.
  ///
  /// In en, this message translates to:
  /// **'No equipment registered.'**
  String get orgEquipmentEmpty;

  /// No description provided for @orgEquipmentCount.
  ///
  /// In en, this message translates to:
  /// **'Count: {count}'**
  String orgEquipmentCount(int count);

  /// No description provided for @orgMaintenanceOk.
  ///
  /// In en, this message translates to:
  /// **'Maintenance up to date'**
  String get orgMaintenanceOk;

  /// No description provided for @orgMaintenanceDueSoon.
  ///
  /// In en, this message translates to:
  /// **'Maintenance due soon'**
  String get orgMaintenanceDueSoon;

  /// No description provided for @orgMaintenanceOverdue.
  ///
  /// In en, this message translates to:
  /// **'Maintenance overdue'**
  String get orgMaintenanceOverdue;

  /// No description provided for @orgMaintenanceUnknown.
  ///
  /// In en, this message translates to:
  /// **'No maintenance date'**
  String get orgMaintenanceUnknown;

  /// No description provided for @orgMaintenanceNext.
  ///
  /// In en, this message translates to:
  /// **'Next maintenance: {date}'**
  String orgMaintenanceNext(String date);

  /// No description provided for @orgLogMaintenance.
  ///
  /// In en, this message translates to:
  /// **'Log a maintenance'**
  String get orgLogMaintenance;

  /// No description provided for @orgMaintenanceLogged.
  ///
  /// In en, this message translates to:
  /// **'Maintenance logged.'**
  String get orgMaintenanceLogged;

  /// No description provided for @orgEvacuationEmpty.
  ///
  /// In en, this message translates to:
  /// **'No point on the map. Points are added on the portal.'**
  String get orgEvacuationEmpty;

  /// No description provided for @orgCertificatesEmpty.
  ///
  /// In en, this message translates to:
  /// **'No certificate yet.'**
  String get orgCertificatesEmpty;

  /// No description provided for @orgCertificateValidUntil.
  ///
  /// In en, this message translates to:
  /// **'Valid until {date}'**
  String orgCertificateValidUntil(String date);

  /// No description provided for @orgMembersEmpty.
  ///
  /// In en, this message translates to:
  /// **'No member.'**
  String get orgMembersEmpty;

  /// No description provided for @orgInvite.
  ///
  /// In en, this message translates to:
  /// **'Invite a member'**
  String get orgInvite;

  /// No description provided for @orgInviteEmail.
  ///
  /// In en, this message translates to:
  /// **'E-mail'**
  String get orgInviteEmail;

  /// No description provided for @orgInviteRole.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get orgInviteRole;

  /// No description provided for @orgInviteSend.
  ///
  /// In en, this message translates to:
  /// **'Send the invitation'**
  String get orgInviteSend;

  /// No description provided for @orgInviteSent.
  ///
  /// In en, this message translates to:
  /// **'Invitation sent to {email}.'**
  String orgInviteSent(String email);

  /// No description provided for @orgAdminOnly.
  ///
  /// In en, this message translates to:
  /// **'Administrator only.'**
  String get orgAdminOnly;

  /// No description provided for @orgKindHealth.
  ///
  /// In en, this message translates to:
  /// **'Health'**
  String get orgKindHealth;

  /// No description provided for @orgKindEnergy.
  ///
  /// In en, this message translates to:
  /// **'Energy and fuel'**
  String get orgKindEnergy;

  /// No description provided for @orgKindTourism.
  ///
  /// In en, this message translates to:
  /// **'Tourism'**
  String get orgKindTourism;

  /// No description provided for @orgKindEducation.
  ///
  /// In en, this message translates to:
  /// **'Education'**
  String get orgKindEducation;

  /// No description provided for @orgKindSocialCare.
  ///
  /// In en, this message translates to:
  /// **'Social care'**
  String get orgKindSocialCare;

  /// No description provided for @orgKindPublicAdmin.
  ///
  /// In en, this message translates to:
  /// **'Public administration'**
  String get orgKindPublicAdmin;

  /// No description provided for @orgKindCultureSport.
  ///
  /// In en, this message translates to:
  /// **'Culture and sport'**
  String get orgKindCultureSport;

  /// No description provided for @orgKindCommercial.
  ///
  /// In en, this message translates to:
  /// **'Commercial'**
  String get orgKindCommercial;

  /// No description provided for @orgKindTransport.
  ///
  /// In en, this message translates to:
  /// **'Transport'**
  String get orgKindTransport;

  /// No description provided for @orgKindReligious.
  ///
  /// In en, this message translates to:
  /// **'Religious'**
  String get orgKindReligious;

  /// No description provided for @kindFieldReceptionPhone.
  ///
  /// In en, this message translates to:
  /// **'Reception number'**
  String get kindFieldReceptionPhone;

  /// No description provided for @kindFieldBeds.
  ///
  /// In en, this message translates to:
  /// **'Beds'**
  String get kindFieldBeds;

  /// No description provided for @kindFieldIcu.
  ///
  /// In en, this message translates to:
  /// **'Intensive care'**
  String get kindFieldIcu;

  /// No description provided for @kindFieldOxygenHours.
  ///
  /// In en, this message translates to:
  /// **'Oxygen reserve (hours)'**
  String get kindFieldOxygenHours;

  /// No description provided for @kindFieldGenerator.
  ///
  /// In en, this message translates to:
  /// **'Generator'**
  String get kindFieldGenerator;

  /// No description provided for @kindFieldHelipad.
  ///
  /// In en, this message translates to:
  /// **'Helipad'**
  String get kindFieldHelipad;

  /// No description provided for @kindFieldNonAmbulatory.
  ///
  /// In en, this message translates to:
  /// **'Non-ambulatory people'**
  String get kindFieldNonAmbulatory;

  /// No description provided for @kindFieldWorkersPerShift.
  ///
  /// In en, this message translates to:
  /// **'Workers per shift'**
  String get kindFieldWorkersPerShift;

  /// No description provided for @kindFieldSelfFireFighting.
  ///
  /// In en, this message translates to:
  /// **'Own fire-fighting means'**
  String get kindFieldSelfFireFighting;

  /// No description provided for @kindFieldTanks.
  ///
  /// In en, this message translates to:
  /// **'Tanks'**
  String get kindFieldTanks;

  /// No description provided for @kindFieldFuelTypes.
  ///
  /// In en, this message translates to:
  /// **'Fuel types'**
  String get kindFieldFuelTypes;

  /// No description provided for @kindFieldStorageM3.
  ///
  /// In en, this message translates to:
  /// **'Storage (m³)'**
  String get kindFieldStorageM3;

  /// No description provided for @kindFieldShutoffValves.
  ///
  /// In en, this message translates to:
  /// **'Shut-off valves'**
  String get kindFieldShutoffValves;

  /// No description provided for @kindFieldRooms.
  ///
  /// In en, this message translates to:
  /// **'Rooms'**
  String get kindFieldRooms;

  /// No description provided for @kindFieldGuestLanguages.
  ///
  /// In en, this message translates to:
  /// **'Guest languages'**
  String get kindFieldGuestLanguages;

  /// No description provided for @kindFieldPoolOrBeach.
  ///
  /// In en, this message translates to:
  /// **'Pool or beach'**
  String get kindFieldPoolOrBeach;

  /// No description provided for @kindFieldOccupancyPct.
  ///
  /// In en, this message translates to:
  /// **'Occupancy (%)'**
  String get kindFieldOccupancyPct;

  /// No description provided for @kindFieldStudents.
  ///
  /// In en, this message translates to:
  /// **'Students'**
  String get kindFieldStudents;

  /// No description provided for @kindFieldAgeRange.
  ///
  /// In en, this message translates to:
  /// **'Age range'**
  String get kindFieldAgeRange;

  /// No description provided for @kindFieldBoarding.
  ///
  /// In en, this message translates to:
  /// **'Boarding'**
  String get kindFieldBoarding;

  /// No description provided for @kindFieldStudentsSpecialNeeds.
  ///
  /// In en, this message translates to:
  /// **'Students with special needs'**
  String get kindFieldStudentsSpecialNeeds;

  /// No description provided for @kindFieldResidents.
  ///
  /// In en, this message translates to:
  /// **'Residents'**
  String get kindFieldResidents;

  /// No description provided for @kindFieldNightWatch.
  ///
  /// In en, this message translates to:
  /// **'Night watch'**
  String get kindFieldNightWatch;

  /// No description provided for @kindFieldStaff.
  ///
  /// In en, this message translates to:
  /// **'Staff'**
  String get kindFieldStaff;

  /// No description provided for @kindFieldArchive.
  ///
  /// In en, this message translates to:
  /// **'Archive'**
  String get kindFieldArchive;

  /// No description provided for @kindFieldSeatedCapacity.
  ///
  /// In en, this message translates to:
  /// **'Seats'**
  String get kindFieldSeatedCapacity;

  /// No description provided for @kindFieldStands.
  ///
  /// In en, this message translates to:
  /// **'Stands'**
  String get kindFieldStands;

  /// No description provided for @kindFieldShops.
  ///
  /// In en, this message translates to:
  /// **'Shops'**
  String get kindFieldShops;

  /// No description provided for @kindFieldUndergroundParking.
  ///
  /// In en, this message translates to:
  /// **'Underground parking'**
  String get kindFieldUndergroundParking;

  /// No description provided for @kindFieldDailyPassengers.
  ///
  /// In en, this message translates to:
  /// **'Daily passengers'**
  String get kindFieldDailyPassengers;

  /// No description provided for @kindFieldEmergencyExits.
  ///
  /// In en, this message translates to:
  /// **'Emergency exits'**
  String get kindFieldEmergencyExits;

  /// No description provided for @kindFieldPeakTimes.
  ///
  /// In en, this message translates to:
  /// **'Peak times'**
  String get kindFieldPeakTimes;

  /// No description provided for @orgVisibilityPublic.
  ///
  /// In en, this message translates to:
  /// **'Public'**
  String get orgVisibilityPublic;

  /// No description provided for @orgVisibilityOrgOffice.
  ///
  /// In en, this message translates to:
  /// **'Institution and Office'**
  String get orgVisibilityOrgOffice;

  /// No description provided for @orgVisibilityIncident.
  ///
  /// In en, this message translates to:
  /// **'On a nearby report'**
  String get orgVisibilityIncident;

  /// No description provided for @orgReqSafetyFile.
  ///
  /// In en, this message translates to:
  /// **'Safety file (stored)'**
  String get orgReqSafetyFile;

  /// No description provided for @orgReqSafetyPlan.
  ///
  /// In en, this message translates to:
  /// **'Safety plan (stored)'**
  String get orgReqSafetyPlan;

  /// No description provided for @orgReqSafetyTeam.
  ///
  /// In en, this message translates to:
  /// **'Safety team: a representative and at least one member'**
  String get orgReqSafetyTeam;

  /// No description provided for @orgReqTraining.
  ///
  /// In en, this message translates to:
  /// **'Every team member has a training date, none expired'**
  String get orgReqTraining;

  /// No description provided for @orgReqHazmatSds.
  ///
  /// In en, this message translates to:
  /// **'A safety data sheet for every hazardous material'**
  String get orgReqHazmatSds;

  /// No description provided for @orgReqEquipment.
  ///
  /// In en, this message translates to:
  /// **'At least one equipment item, none overdue'**
  String get orgReqEquipment;

  /// No description provided for @orgReqEvacuationPoints.
  ///
  /// In en, this message translates to:
  /// **'At least one evacuation point on the map'**
  String get orgReqEvacuationPoints;

  /// No description provided for @orgEquipExtinguisher.
  ///
  /// In en, this message translates to:
  /// **'Fire extinguisher'**
  String get orgEquipExtinguisher;

  /// No description provided for @orgEquipFireHoseReel.
  ///
  /// In en, this message translates to:
  /// **'Fire hose reel'**
  String get orgEquipFireHoseReel;

  /// No description provided for @orgEquipSprinkler.
  ///
  /// In en, this message translates to:
  /// **'Sprinkler'**
  String get orgEquipSprinkler;

  /// No description provided for @orgEquipSmokeDetector.
  ///
  /// In en, this message translates to:
  /// **'Smoke detector'**
  String get orgEquipSmokeDetector;

  /// No description provided for @orgEquipAlarmPanel.
  ///
  /// In en, this message translates to:
  /// **'Alarm panel'**
  String get orgEquipAlarmPanel;

  /// No description provided for @orgEquipEmergencyLighting.
  ///
  /// In en, this message translates to:
  /// **'Emergency lighting'**
  String get orgEquipEmergencyLighting;

  /// No description provided for @orgEquipFireDoor.
  ///
  /// In en, this message translates to:
  /// **'Fire door'**
  String get orgEquipFireDoor;

  /// No description provided for @orgEquipOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get orgEquipOther;

  /// No description provided for @orgFeatureEvacuationPoint.
  ///
  /// In en, this message translates to:
  /// **'Evacuation and assembly point'**
  String get orgFeatureEvacuationPoint;

  /// No description provided for @orgFeatureWaterPoint.
  ///
  /// In en, this message translates to:
  /// **'Water point'**
  String get orgFeatureWaterPoint;

  /// No description provided for @orgFeatureAlarm.
  ///
  /// In en, this message translates to:
  /// **'Alarm'**
  String get orgFeatureAlarm;

  /// No description provided for @orgRoleAdmin.
  ///
  /// In en, this message translates to:
  /// **'Administrator'**
  String get orgRoleAdmin;

  /// No description provided for @orgRoleEditor.
  ///
  /// In en, this message translates to:
  /// **'Editor'**
  String get orgRoleEditor;

  /// No description provided for @orgRoleMember.
  ///
  /// In en, this message translates to:
  /// **'Member'**
  String get orgRoleMember;

  /// No description provided for @orgCertDraft.
  ///
  /// In en, this message translates to:
  /// **'Draft'**
  String get orgCertDraft;

  /// No description provided for @orgCertSubmitted.
  ///
  /// In en, this message translates to:
  /// **'Submitted'**
  String get orgCertSubmitted;

  /// No description provided for @orgCertApproved.
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get orgCertApproved;

  /// No description provided for @orgCertRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get orgCertRejected;

  /// No description provided for @orgCertRevoked.
  ///
  /// In en, this message translates to:
  /// **'Revoked'**
  String get orgCertRevoked;

  /// No description provided for @orgAlertTrainingExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired training in the safety team'**
  String get orgAlertTrainingExpired;

  /// No description provided for @orgAlertTrainingExpiring.
  ///
  /// In en, this message translates to:
  /// **'Training expiring soon in the safety team'**
  String get orgAlertTrainingExpiring;

  /// No description provided for @orgAlertMaintenanceOverdue.
  ///
  /// In en, this message translates to:
  /// **'Equipment maintenance overdue'**
  String get orgAlertMaintenanceOverdue;

  /// No description provided for @orgAlertMaintenanceDueSoon.
  ///
  /// In en, this message translates to:
  /// **'Equipment maintenance due soon'**
  String get orgAlertMaintenanceDueSoon;

  /// No description provided for @orgKindLabelTitle.
  ///
  /// In en, this message translates to:
  /// **'Kind'**
  String get orgKindLabelTitle;

  /// No description provided for @orgSectionMessages.
  ///
  /// In en, this message translates to:
  /// **'Office messages'**
  String get orgSectionMessages;

  /// No description provided for @orgSectionActivities.
  ///
  /// In en, this message translates to:
  /// **'Drills and events'**
  String get orgSectionActivities;

  /// No description provided for @orgSectionAwareness.
  ///
  /// In en, this message translates to:
  /// **'Awareness'**
  String get orgSectionAwareness;

  /// No description provided for @orgMessagesPending.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 Office message awaits your acknowledgement} other{{count} Office messages await your acknowledgement}}'**
  String orgMessagesPending(int count);

  /// No description provided for @orgMessagesPendingHint.
  ///
  /// In en, this message translates to:
  /// **'Open them and confirm you have read them.'**
  String get orgMessagesPendingHint;

  /// No description provided for @orgMessagesEmpty.
  ///
  /// In en, this message translates to:
  /// **'No message from the Office yet.'**
  String get orgMessagesEmpty;

  /// No description provided for @orgMessageAck.
  ///
  /// In en, this message translates to:
  /// **'I have read it'**
  String get orgMessageAck;

  /// No description provided for @orgMessageWaiting.
  ///
  /// In en, this message translates to:
  /// **'Acknowledgement requested'**
  String get orgMessageWaiting;

  /// No description provided for @orgMessageAcked.
  ///
  /// In en, this message translates to:
  /// **'Acknowledged on {date}'**
  String orgMessageAcked(String date);

  /// No description provided for @orgMessageAckDone.
  ///
  /// In en, this message translates to:
  /// **'The Office knows you have read it.'**
  String get orgMessageAckDone;

  /// No description provided for @orgMessageAckEditors.
  ///
  /// In en, this message translates to:
  /// **'An editor or administrator of the institution confirms the reading.'**
  String get orgMessageAckEditors;

  /// No description provided for @orgAwarenessEmpty.
  ///
  /// In en, this message translates to:
  /// **'No awareness tips for your kind of institution yet.'**
  String get orgAwarenessEmpty;

  /// No description provided for @orgAwarenessIntro.
  ///
  /// In en, this message translates to:
  /// **'Tips the Office prepared for institutions of your kind.'**
  String get orgAwarenessIntro;

  /// No description provided for @orgActivitiesEmpty.
  ///
  /// In en, this message translates to:
  /// **'No drill or event recorded yet.'**
  String get orgActivitiesEmpty;

  /// No description provided for @orgActivityDrill.
  ///
  /// In en, this message translates to:
  /// **'Drill'**
  String get orgActivityDrill;

  /// No description provided for @orgActivityEvent.
  ///
  /// In en, this message translates to:
  /// **'Public event'**
  String get orgActivityEvent;

  /// No description provided for @orgActivityAdd.
  ///
  /// In en, this message translates to:
  /// **'Add a drill or event'**
  String get orgActivityAdd;

  /// No description provided for @orgActivityHint.
  ///
  /// In en, this message translates to:
  /// **'A drill is recorded once held; a public event is declared ahead so the Office can prepare.'**
  String get orgActivityHint;

  /// No description provided for @orgActivityTitle.
  ///
  /// In en, this message translates to:
  /// **'Title'**
  String get orgActivityTitle;

  /// No description provided for @orgActivityTitleRequired.
  ///
  /// In en, this message translates to:
  /// **'Enter a title.'**
  String get orgActivityTitleRequired;

  /// No description provided for @orgActivityStarts.
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get orgActivityStarts;

  /// No description provided for @orgActivityEnds.
  ///
  /// In en, this message translates to:
  /// **'End date (optional)'**
  String get orgActivityEnds;

  /// No description provided for @orgActivityParticipants.
  ///
  /// In en, this message translates to:
  /// **'Participants (optional)'**
  String get orgActivityParticipants;

  /// No description provided for @orgActivityParticipantsCount.
  ///
  /// In en, this message translates to:
  /// **'{count} participants'**
  String orgActivityParticipantsCount(int count);

  /// No description provided for @orgActivityNotes.
  ///
  /// In en, this message translates to:
  /// **'Notes (optional)'**
  String get orgActivityNotes;

  /// No description provided for @orgActivityDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get orgActivityDelete;

  /// No description provided for @orgActivityDeleteConfirm.
  ///
  /// In en, this message translates to:
  /// **'Delete “{title}”?'**
  String orgActivityDeleteConfirm(String title);

  /// No description provided for @orgActivityDeleted.
  ///
  /// In en, this message translates to:
  /// **'Deleted.'**
  String get orgActivityDeleted;

  /// No description provided for @orgMaintenanceSheetTitle.
  ///
  /// In en, this message translates to:
  /// **'Log a maintenance'**
  String get orgMaintenanceSheetTitle;

  /// No description provided for @orgMaintenanceDate.
  ///
  /// In en, this message translates to:
  /// **'Done on'**
  String get orgMaintenanceDate;

  /// No description provided for @orgMaintenanceNote.
  ///
  /// In en, this message translates to:
  /// **'Note (optional)'**
  String get orgMaintenanceNote;

  /// No description provided for @orgMaintenancePhoto.
  ///
  /// In en, this message translates to:
  /// **'Take a photo'**
  String get orgMaintenancePhoto;

  /// No description provided for @orgMaintenancePhotoRetake.
  ///
  /// In en, this message translates to:
  /// **'Retake'**
  String get orgMaintenancePhotoRetake;

  /// No description provided for @orgMaintenancePhotoReady.
  ///
  /// In en, this message translates to:
  /// **'Photo attached'**
  String get orgMaintenancePhotoReady;

  /// No description provided for @orgMaintenancePhotoUnsupported.
  ///
  /// In en, this message translates to:
  /// **'Only JPEG or PNG photos.'**
  String get orgMaintenancePhotoUnsupported;

  /// No description provided for @orgMaintenancePhotoTooLarge.
  ///
  /// In en, this message translates to:
  /// **'The photo is larger than 10 MB.'**
  String get orgMaintenancePhotoTooLarge;

  /// No description provided for @orgMaintenancePhotoFailed.
  ///
  /// In en, this message translates to:
  /// **'The photo could not be sent; the maintenance was not recorded.'**
  String get orgMaintenancePhotoFailed;

  /// No description provided for @orgMaintenanceSave.
  ///
  /// In en, this message translates to:
  /// **'Record'**
  String get orgMaintenanceSave;

  /// No description provided for @orgMaintenanceHistory.
  ///
  /// In en, this message translates to:
  /// **'Maintenance log'**
  String get orgMaintenanceHistory;

  /// No description provided for @orgMaintenanceHistoryEmpty.
  ///
  /// In en, this message translates to:
  /// **'No maintenance recorded yet.'**
  String get orgMaintenanceHistoryEmpty;

  /// No description provided for @orgMaintenancePhotoStored.
  ///
  /// In en, this message translates to:
  /// **'Photo kept'**
  String get orgMaintenancePhotoStored;

  /// No description provided for @orgMaintenancePhotoChecking.
  ///
  /// In en, this message translates to:
  /// **'Photo being checked'**
  String get orgMaintenancePhotoChecking;

  /// No description provided for @errorAckNotRequired.
  ///
  /// In en, this message translates to:
  /// **'This message does not ask for an acknowledgement.'**
  String get errorAckNotRequired;

  /// No description provided for @errorDrillInFuture.
  ///
  /// In en, this message translates to:
  /// **'A drill is recorded once held: choose today or an earlier date.'**
  String get errorDrillInFuture;

  /// No description provided for @errorInvalidDates.
  ///
  /// In en, this message translates to:
  /// **'The end date must follow the start date.'**
  String get errorInvalidDates;

  /// No description provided for @errorMaintenanceInFuture.
  ///
  /// In en, this message translates to:
  /// **'A maintenance cannot be dated in the future.'**
  String get errorMaintenanceInFuture;

  /// No description provided for @errorInvalidDocument.
  ///
  /// In en, this message translates to:
  /// **'The photo is not valid for this maintenance.'**
  String get errorInvalidDocument;

  /// No description provided for @orgAlertCertificateExpiring.
  ///
  /// In en, this message translates to:
  /// **'The safety certificate expires soon'**
  String get orgAlertCertificateExpiring;

  /// No description provided for @orgAlertCertificateExpired.
  ///
  /// In en, this message translates to:
  /// **'The safety certificate has expired'**
  String get orgAlertCertificateExpired;

  /// No description provided for @orgAlertCertificateNeedsUpdate.
  ///
  /// In en, this message translates to:
  /// **'The safety certificate needs updating'**
  String get orgAlertCertificateNeedsUpdate;

  /// No description provided for @orgCertNeedsUpdate.
  ///
  /// In en, this message translates to:
  /// **'Needs updating'**
  String get orgCertNeedsUpdate;

  /// No description provided for @orgCertNeedsUpdateBody.
  ///
  /// In en, this message translates to:
  /// **'Changed since approval: {sections}. Generate a new certificate on the portal.'**
  String orgCertNeedsUpdateBody(String sections);

  /// No description provided for @orgCertUpToDate.
  ///
  /// In en, this message translates to:
  /// **'Matches the institution'**
  String get orgCertUpToDate;

  /// No description provided for @orgCertStamped.
  ///
  /// In en, this message translates to:
  /// **'Stamped'**
  String get orgCertStamped;

  /// No description provided for @orgCertSectionIdentity.
  ///
  /// In en, this message translates to:
  /// **'Identity'**
  String get orgCertSectionIdentity;

  /// No description provided for @orgCertSectionBuilding.
  ///
  /// In en, this message translates to:
  /// **'Building'**
  String get orgCertSectionBuilding;

  /// No description provided for @orgCertSectionClassification.
  ///
  /// In en, this message translates to:
  /// **'Classification'**
  String get orgCertSectionClassification;

  /// No description provided for @orgCertSectionHazmat.
  ///
  /// In en, this message translates to:
  /// **'Hazardous materials'**
  String get orgCertSectionHazmat;

  /// No description provided for @orgCertSectionDocuments.
  ///
  /// In en, this message translates to:
  /// **'Documents'**
  String get orgCertSectionDocuments;

  /// No description provided for @orgCertSectionSafetyTeam.
  ///
  /// In en, this message translates to:
  /// **'Safety team'**
  String get orgCertSectionSafetyTeam;

  /// No description provided for @orgCertSectionEvacuation.
  ///
  /// In en, this message translates to:
  /// **'Evacuation'**
  String get orgCertSectionEvacuation;

  /// No description provided for @orgSectionRecords.
  ///
  /// In en, this message translates to:
  /// **'Reports and records'**
  String get orgSectionRecords;

  /// No description provided for @orgRecordsHint.
  ///
  /// In en, this message translates to:
  /// **'Everything the Office recorded about the institution: visit reports, reservations and deadlines, certificates, drills and the annual report. Requests and answers are made on the portal.'**
  String get orgRecordsHint;

  /// No description provided for @orgRecordsVisits.
  ///
  /// In en, this message translates to:
  /// **'Prevention visits'**
  String get orgRecordsVisits;

  /// No description provided for @orgRecordsVisitsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No prevention visit yet.'**
  String get orgRecordsVisitsEmpty;

  /// No description provided for @orgVisitOriginRequest.
  ///
  /// In en, this message translates to:
  /// **'Requested by the institution'**
  String get orgVisitOriginRequest;

  /// No description provided for @orgVisitOriginOffice.
  ///
  /// In en, this message translates to:
  /// **'Scheduled by the Office'**
  String get orgVisitOriginOffice;

  /// No description provided for @orgVisitStatusRequested.
  ///
  /// In en, this message translates to:
  /// **'Requested'**
  String get orgVisitStatusRequested;

  /// No description provided for @orgVisitStatusScheduled.
  ///
  /// In en, this message translates to:
  /// **'Scheduled'**
  String get orgVisitStatusScheduled;

  /// No description provided for @orgVisitStatusInspected.
  ///
  /// In en, this message translates to:
  /// **'Inspected, decision pending'**
  String get orgVisitStatusInspected;

  /// No description provided for @orgVisitStatusDecided.
  ///
  /// In en, this message translates to:
  /// **'Decided'**
  String get orgVisitStatusDecided;

  /// No description provided for @orgVisitStatusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get orgVisitStatusCancelled;

  /// No description provided for @orgVisitDecisionApproved.
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get orgVisitDecisionApproved;

  /// No description provided for @orgVisitDecisionReservations.
  ///
  /// In en, this message translates to:
  /// **'Approved with reservations'**
  String get orgVisitDecisionReservations;

  /// No description provided for @orgVisitDecisionRefused.
  ///
  /// In en, this message translates to:
  /// **'Refused'**
  String get orgVisitDecisionRefused;

  /// No description provided for @orgVisitOn.
  ///
  /// In en, this message translates to:
  /// **'Visit on {date}'**
  String orgVisitOn(String date);

  /// No description provided for @orgVisitInspector.
  ///
  /// In en, this message translates to:
  /// **'Inspector: {name}'**
  String orgVisitInspector(String name);

  /// No description provided for @orgVisitComparison.
  ///
  /// In en, this message translates to:
  /// **'Comparison: {conform} conforming · {nonconform} non-conforming · {notChecked} not checked'**
  String orgVisitComparison(int conform, int nonconform, int notChecked);

  /// No description provided for @orgVisitReason.
  ///
  /// In en, this message translates to:
  /// **'Reason: {reason}'**
  String orgVisitReason(String reason);

  /// No description provided for @orgVisitReport.
  ///
  /// In en, this message translates to:
  /// **'Visit report (PDF)'**
  String get orgVisitReport;

  /// No description provided for @orgCertificatePdf.
  ///
  /// In en, this message translates to:
  /// **'Certificate (PDF)'**
  String get orgCertificatePdf;

  /// No description provided for @orgPdfUnavailable.
  ///
  /// In en, this message translates to:
  /// **'The document could not be opened.'**
  String get orgPdfUnavailable;

  /// No description provided for @orgRecordsReservations.
  ///
  /// In en, this message translates to:
  /// **'Reservations and deadlines'**
  String get orgRecordsReservations;

  /// No description provided for @orgRecordsReservationsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No reservation to address.'**
  String get orgRecordsReservationsEmpty;

  /// No description provided for @orgReservationDue.
  ///
  /// In en, this message translates to:
  /// **'Due by {date}'**
  String orgReservationDue(String date);

  /// No description provided for @orgReservationOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get orgReservationOpen;

  /// No description provided for @orgReservationResponded.
  ///
  /// In en, this message translates to:
  /// **'Answered, awaiting the Office'**
  String get orgReservationResponded;

  /// No description provided for @orgReservationOverdue.
  ///
  /// In en, this message translates to:
  /// **'Overdue'**
  String get orgReservationOverdue;

  /// No description provided for @orgReservationLifted.
  ///
  /// In en, this message translates to:
  /// **'Lifted'**
  String get orgReservationLifted;

  /// No description provided for @orgCertKindSafety.
  ///
  /// In en, this message translates to:
  /// **'Safety certificate'**
  String get orgCertKindSafety;

  /// No description provided for @orgCertKindPrevention.
  ///
  /// In en, this message translates to:
  /// **'Prevention certificate'**
  String get orgCertKindPrevention;

  /// No description provided for @orgCertPreventionSim.
  ///
  /// In en, this message translates to:
  /// **'[SIM] Model awaiting the Office'**
  String get orgCertPreventionSim;

  /// No description provided for @orgRecordsDrills.
  ///
  /// In en, this message translates to:
  /// **'Drill reports'**
  String get orgRecordsDrills;

  /// No description provided for @orgRecordsDrillsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No drill recorded this year.'**
  String get orgRecordsDrillsEmpty;

  /// No description provided for @orgRecordsAnnual.
  ///
  /// In en, this message translates to:
  /// **'Annual report'**
  String get orgRecordsAnnual;

  /// No description provided for @orgRecordsYear.
  ///
  /// In en, this message translates to:
  /// **'Year'**
  String get orgRecordsYear;

  /// No description provided for @orgAnnualDrills.
  ///
  /// In en, this message translates to:
  /// **'{count} drill(s), {participants} participant(s)'**
  String orgAnnualDrills(int count, int participants);

  /// No description provided for @orgAnnualEvents.
  ///
  /// In en, this message translates to:
  /// **'{count} public event(s)'**
  String orgAnnualEvents(int count);

  /// No description provided for @orgAnnualMaintenance.
  ///
  /// In en, this message translates to:
  /// **'{count} maintenance operation(s)'**
  String orgAnnualMaintenance(int count);

  /// No description provided for @orgAnnualTraining.
  ///
  /// In en, this message translates to:
  /// **'Training: {valid} valid · {expiring} expiring · {expired} expired'**
  String orgAnnualTraining(int valid, int expiring, int expired);

  /// No description provided for @orgAnnualVisits.
  ///
  /// In en, this message translates to:
  /// **'{count} prevention visit(s)'**
  String orgAnnualVisits(int count);

  /// No description provided for @orgAnnualReservations.
  ///
  /// In en, this message translates to:
  /// **'Reservations: {opened} issued · {lifted} lifted · {overdue} overdue'**
  String orgAnnualReservations(int opened, int lifted, int overdue);

  /// No description provided for @orgAnnualCertificates.
  ///
  /// In en, this message translates to:
  /// **'{count} certificate(s), {stamps} stamp(s)'**
  String orgAnnualCertificates(int count, int stamps);

  /// No description provided for @orgAnnualReports.
  ///
  /// In en, this message translates to:
  /// **'{count} report(s) sent from the institution'**
  String orgAnnualReports(int count);

  /// No description provided for @orgRecordsReminders.
  ///
  /// In en, this message translates to:
  /// **'Reminders'**
  String get orgRecordsReminders;

  /// No description provided for @orgRecordsRemindersEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing to do for now.'**
  String get orgRecordsRemindersEmpty;

  /// No description provided for @orgAlertVisitScheduled.
  ///
  /// In en, this message translates to:
  /// **'A prevention visit is scheduled'**
  String get orgAlertVisitScheduled;

  /// No description provided for @orgAlertReservationDueSoon.
  ///
  /// In en, this message translates to:
  /// **'A reservation is due soon'**
  String get orgAlertReservationDueSoon;

  /// No description provided for @orgAlertReservationOverdue.
  ///
  /// In en, this message translates to:
  /// **'A reservation is overdue'**
  String get orgAlertReservationOverdue;

  /// No description provided for @orgAlertPreventionExpiring.
  ///
  /// In en, this message translates to:
  /// **'The prevention certificate expires soon'**
  String get orgAlertPreventionExpiring;

  /// No description provided for @orgAlertPreventionExpired.
  ///
  /// In en, this message translates to:
  /// **'The prevention certificate has expired'**
  String get orgAlertPreventionExpired;

  /// No description provided for @listenAction.
  ///
  /// In en, this message translates to:
  /// **'Listen'**
  String get listenAction;

  /// No description provided for @listenStop.
  ///
  /// In en, this message translates to:
  /// **'Stop reading'**
  String get listenStop;

  /// No description provided for @listenNoVoice.
  ///
  /// In en, this message translates to:
  /// **'No voice for this language on your phone. Install one in the phone settings: Accessibility, then “Text-to-speech”.'**
  String get listenNoVoice;

  /// No description provided for @listenFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not read aloud.'**
  String get listenFailed;

  /// No description provided for @a11yTitle.
  ///
  /// In en, this message translates to:
  /// **'Accessibility'**
  String get a11yTitle;

  /// No description provided for @a11ySubtitle.
  ///
  /// In en, this message translates to:
  /// **'Read aloud and flashes for deaf users'**
  String get a11ySubtitle;

  /// No description provided for @a11yUrgentSection.
  ///
  /// In en, this message translates to:
  /// **'When an urgent alert arrives while the app is open'**
  String get a11yUrgentSection;

  /// No description provided for @a11yScreenFlash.
  ///
  /// In en, this message translates to:
  /// **'Screen flash'**
  String get a11yScreenFlash;

  /// No description provided for @a11yScreenFlashHelp.
  ///
  /// In en, this message translates to:
  /// **'Three red flashes, one per second'**
  String get a11yScreenFlashHelp;

  /// No description provided for @a11yTorchFlash.
  ///
  /// In en, this message translates to:
  /// **'Camera light flash'**
  String get a11yTorchFlash;

  /// No description provided for @a11yTorchFlashHelp.
  ///
  /// In en, this message translates to:
  /// **'Three flashes, one per second'**
  String get a11yTorchFlashHelp;

  /// No description provided for @a11yTorchUnavailable.
  ///
  /// In en, this message translates to:
  /// **'No light on this phone'**
  String get a11yTorchUnavailable;

  /// No description provided for @a11yReadAlerts.
  ///
  /// In en, this message translates to:
  /// **'Read the alert aloud'**
  String get a11yReadAlerts;

  /// No description provided for @a11yReadAlertsHelp.
  ///
  /// In en, this message translates to:
  /// **'The title and text, in the app’s language'**
  String get a11yReadAlertsHelp;

  /// No description provided for @a11yTry.
  ///
  /// In en, this message translates to:
  /// **'Try'**
  String get a11yTry;

  /// No description provided for @a11yTrySample.
  ///
  /// In en, this message translates to:
  /// **'Test alert from e-Himaya. There is no danger.'**
  String get a11yTrySample;

  /// No description provided for @a11yTryNothing.
  ///
  /// In en, this message translates to:
  /// **'Choose at least one cue.'**
  String get a11yTryNothing;

  /// No description provided for @a11yAlwaysNote.
  ///
  /// In en, this message translates to:
  /// **'An urgent notification always vibrates (long-short-long) and lights the LED. When the app is closed, turn on “Flash notifications” in the phone’s accessibility settings if it has them.'**
  String get a11yAlwaysNote;

  /// No description provided for @a11yPhoneSection.
  ///
  /// In en, this message translates to:
  /// **'In the phone settings'**
  String get a11yPhoneSection;

  /// No description provided for @a11yPhoneNote.
  ///
  /// In en, this message translates to:
  /// **'Text size and the screen reader (TalkBack or VoiceOver) are set in the phone; the app follows them up to 200%. Guides, tips and alerts have a “Listen” button.'**
  String get a11yPhoneNote;

  /// No description provided for @a11ySimpleSection.
  ///
  /// In en, this message translates to:
  /// **'Simplified mode'**
  String get a11ySimpleSection;

  /// No description provided for @a11ySimpleMode.
  ///
  /// In en, this message translates to:
  /// **'Simplified mode'**
  String get a11ySimpleMode;

  /// No description provided for @a11ySimpleModeHelp.
  ///
  /// In en, this message translates to:
  /// **'A home with five large buttons in plain words, within reach of the thumb.'**
  String get a11ySimpleModeHelp;

  /// No description provided for @simpleCall198.
  ///
  /// In en, this message translates to:
  /// **'Call Civil Protection 198'**
  String get simpleCall198;

  /// No description provided for @simpleReport.
  ///
  /// In en, this message translates to:
  /// **'Report a danger'**
  String get simpleReport;

  /// No description provided for @simpleSosMessage.
  ///
  /// In en, this message translates to:
  /// **'Send a help message to my family'**
  String get simpleSosMessage;

  /// No description provided for @simpleWhatToDo.
  ///
  /// In en, this message translates to:
  /// **'What should I do?'**
  String get simpleWhatToDo;

  /// No description provided for @simpleAlerts.
  ///
  /// In en, this message translates to:
  /// **'Alerts'**
  String get simpleAlerts;

  /// No description provided for @simpleSosHint.
  ///
  /// In en, this message translates to:
  /// **'Emergency: press and hold the red button.'**
  String get simpleSosHint;

  /// No description provided for @simpleShowAll.
  ///
  /// In en, this message translates to:
  /// **'Show all options'**
  String get simpleShowAll;

  /// No description provided for @rateTitle.
  ///
  /// In en, this message translates to:
  /// **'Rate the app'**
  String get rateTitle;

  /// No description provided for @rateSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Your opinion improves the app'**
  String get rateSubtitle;

  /// No description provided for @rateQuestion.
  ///
  /// In en, this message translates to:
  /// **'What do you think of the app?'**
  String get rateQuestion;

  /// No description provided for @rateStar.
  ///
  /// In en, this message translates to:
  /// **'{count} out of 5'**
  String rateStar(int count);

  /// No description provided for @rateRemark.
  ///
  /// In en, this message translates to:
  /// **'Remark (optional)'**
  String get rateRemark;

  /// No description provided for @rateSend.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get rateSend;

  /// No description provided for @rateChooseStars.
  ///
  /// In en, this message translates to:
  /// **'Choose a number of stars.'**
  String get rateChooseStars;

  /// No description provided for @rateThanks.
  ///
  /// In en, this message translates to:
  /// **'Thank you, your rating was sent.'**
  String get rateThanks;

  /// No description provided for @rateContactNote.
  ///
  /// In en, this message translates to:
  /// **'Need an answer? Use “Contact us”.'**
  String get rateContactNote;

  /// No description provided for @introReplayTitle.
  ///
  /// In en, this message translates to:
  /// **'Introduction tour'**
  String get introReplayTitle;

  /// No description provided for @introReplaySubtitle.
  ///
  /// In en, this message translates to:
  /// **'The five cards from the first launch'**
  String get introReplaySubtitle;

  /// No description provided for @institutionRegister.
  ///
  /// In en, this message translates to:
  /// **'Register my institution'**
  String get institutionRegister;

  /// No description provided for @emailConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Work e-mail'**
  String get emailConfirmTitle;

  /// No description provided for @emailConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'To register an institution we need a confirmed e-mail. We send a 6-digit code to it.'**
  String get emailConfirmBody;

  /// No description provided for @emailField.
  ///
  /// In en, this message translates to:
  /// **'E-mail'**
  String get emailField;

  /// No description provided for @emailSendCode.
  ///
  /// In en, this message translates to:
  /// **'Send the code'**
  String get emailSendCode;

  /// No description provided for @emailCodeSent.
  ///
  /// In en, this message translates to:
  /// **'A code was sent to {email}. Valid for 10 minutes.'**
  String emailCodeSent(String email);

  /// No description provided for @emailCodeField.
  ///
  /// In en, this message translates to:
  /// **'Code'**
  String get emailCodeField;

  /// No description provided for @emailVerify.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get emailVerify;

  /// No description provided for @emailConfirmed.
  ///
  /// In en, this message translates to:
  /// **'E-mail confirmed: {email}'**
  String emailConfirmed(String email);

  /// No description provided for @emailChange.
  ///
  /// In en, this message translates to:
  /// **'Change e-mail'**
  String get emailChange;

  /// No description provided for @emailCodeInvalid.
  ///
  /// In en, this message translates to:
  /// **'Wrong code.'**
  String get emailCodeInvalid;

  /// No description provided for @emailCodeExpired.
  ///
  /// In en, this message translates to:
  /// **'The code expired. Ask for a new one.'**
  String get emailCodeExpired;

  /// No description provided for @staffAppTitle.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya Crew'**
  String get staffAppTitle;

  /// No description provided for @staffSignInTitle.
  ///
  /// In en, this message translates to:
  /// **'Team leader sign-in'**
  String get staffSignInTitle;

  /// No description provided for @staffSignInBody.
  ///
  /// In en, this message translates to:
  /// **'You sign in on this phone\'s browser with your staff account and your second factor. No password is typed in this app.'**
  String get staffSignInBody;

  /// No description provided for @staffSignIn.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get staffSignIn;

  /// No description provided for @staffCodeIntro.
  ///
  /// In en, this message translates to:
  /// **'Check that the sign-in page shows this code:'**
  String get staffCodeIntro;

  /// No description provided for @staffCodeSemantics.
  ///
  /// In en, this message translates to:
  /// **'Sign-in code {code}'**
  String staffCodeSemantics(String code);

  /// No description provided for @staffOpenSignInPage.
  ///
  /// In en, this message translates to:
  /// **'Open the sign-in page'**
  String get staffOpenSignInPage;

  /// No description provided for @staffWaitingSignIn.
  ///
  /// In en, this message translates to:
  /// **'Waiting for the sign-in…'**
  String get staffWaitingSignIn;

  /// No description provided for @staffSignInRefused.
  ///
  /// In en, this message translates to:
  /// **'Sign-in refused. Check that your account has the team leader role.'**
  String get staffSignInRefused;

  /// No description provided for @staffSignInExpired.
  ///
  /// In en, this message translates to:
  /// **'The code expired. Sign in again.'**
  String get staffSignInExpired;

  /// No description provided for @staffWiped.
  ///
  /// In en, this message translates to:
  /// **'This phone was withdrawn from the team leaders\' phones. Its data was erased.'**
  String get staffWiped;

  /// No description provided for @staffPinWiped.
  ///
  /// In en, this message translates to:
  /// **'Five wrong PINs: the data on this phone was erased. Sign in again.'**
  String get staffPinWiped;

  /// No description provided for @staffOffline.
  ///
  /// In en, this message translates to:
  /// **'No connection to the operations room. What you see is the last copy.'**
  String get staffOffline;

  /// No description provided for @staffPinCreate.
  ///
  /// In en, this message translates to:
  /// **'Choose a 6-digit PIN'**
  String get staffPinCreate;

  /// No description provided for @staffPinConfirm.
  ///
  /// In en, this message translates to:
  /// **'Type the PIN again'**
  String get staffPinConfirm;

  /// No description provided for @staffPinEnter.
  ///
  /// In en, this message translates to:
  /// **'Enter your PIN'**
  String get staffPinEnter;

  /// No description provided for @staffPinHelp.
  ///
  /// In en, this message translates to:
  /// **'It is asked after 5 minutes away from the app. Five wrong PINs erase the phone.'**
  String get staffPinHelp;

  /// No description provided for @staffPinLabel.
  ///
  /// In en, this message translates to:
  /// **'PIN'**
  String get staffPinLabel;

  /// No description provided for @staffPinMismatch.
  ///
  /// In en, this message translates to:
  /// **'The two PINs differ. Start again.'**
  String get staffPinMismatch;

  /// No description provided for @staffPinWrong.
  ///
  /// In en, this message translates to:
  /// **'Wrong PIN. {left} tries left.'**
  String staffPinWrong(int left);

  /// No description provided for @staffSignOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out and erase'**
  String get staffSignOut;

  /// No description provided for @staffShiftTitle.
  ///
  /// In en, this message translates to:
  /// **'Start of shift'**
  String get staffShiftTitle;

  /// No description provided for @staffHello.
  ///
  /// In en, this message translates to:
  /// **'Hello {name}'**
  String staffHello(String name);

  /// No description provided for @staffChooseVehicle.
  ///
  /// In en, this message translates to:
  /// **'Your vehicle'**
  String get staffChooseVehicle;

  /// No description provided for @staffNoVehicles.
  ///
  /// In en, this message translates to:
  /// **'No vehicle in your gouvernorat. Ask the operations room.'**
  String get staffNoVehicles;

  /// No description provided for @staffVehicleTaken.
  ///
  /// In en, this message translates to:
  /// **'already on shift'**
  String get staffVehicleTaken;

  /// No description provided for @staffCrewSize.
  ///
  /// In en, this message translates to:
  /// **'Crew on board'**
  String get staffCrewSize;

  /// No description provided for @staffCrewCount.
  ///
  /// In en, this message translates to:
  /// **'{count} crew'**
  String staffCrewCount(int count);

  /// No description provided for @staffLess.
  ///
  /// In en, this message translates to:
  /// **'Less'**
  String get staffLess;

  /// No description provided for @staffMore.
  ///
  /// In en, this message translates to:
  /// **'More'**
  String get staffMore;

  /// No description provided for @staffCrewNames.
  ///
  /// In en, this message translates to:
  /// **'Crew names'**
  String get staffCrewNames;

  /// No description provided for @staffOptional.
  ///
  /// In en, this message translates to:
  /// **'Optional'**
  String get staffOptional;

  /// No description provided for @staffStartShift.
  ///
  /// In en, this message translates to:
  /// **'Start the shift'**
  String get staffStartShift;

  /// No description provided for @staffEndShift.
  ///
  /// In en, this message translates to:
  /// **'End the shift'**
  String get staffEndShift;

  /// No description provided for @staffEndShiftConfirm.
  ///
  /// In en, this message translates to:
  /// **'The vehicle will no longer receive missions on this phone.'**
  String get staffEndShiftConfirm;

  /// No description provided for @staffOnShift.
  ///
  /// In en, this message translates to:
  /// **'On shift'**
  String get staffOnShift;

  /// No description provided for @staffActiveMissions.
  ///
  /// In en, this message translates to:
  /// **'Missions'**
  String get staffActiveMissions;

  /// No description provided for @staffRecentMissions.
  ///
  /// In en, this message translates to:
  /// **'Finished in the last hours'**
  String get staffRecentMissions;

  /// No description provided for @staffNoMission.
  ///
  /// In en, this message translates to:
  /// **'No mission. The phone rings when the room orders the vehicle.'**
  String get staffNoMission;

  /// No description provided for @staffNewMission.
  ///
  /// In en, this message translates to:
  /// **'New mission'**
  String get staffNewMission;

  /// No description provided for @staffOrder.
  ///
  /// In en, this message translates to:
  /// **'Order'**
  String get staffOrder;

  /// No description provided for @staffAcknowledge.
  ///
  /// In en, this message translates to:
  /// **'Received'**
  String get staffAcknowledge;

  /// No description provided for @staffMissionGone.
  ///
  /// In en, this message translates to:
  /// **'This mission is no longer on the vehicle.'**
  String get staffMissionGone;

  /// No description provided for @staffStatusOrdered.
  ///
  /// In en, this message translates to:
  /// **'Ordered'**
  String get staffStatusOrdered;

  /// No description provided for @staffStatusEnRoute.
  ///
  /// In en, this message translates to:
  /// **'En route'**
  String get staffStatusEnRoute;

  /// No description provided for @staffStatusOnScene.
  ///
  /// In en, this message translates to:
  /// **'On scene'**
  String get staffStatusOnScene;

  /// No description provided for @staffStatusReleased.
  ///
  /// In en, this message translates to:
  /// **'Released'**
  String get staffStatusReleased;

  /// No description provided for @staffStatusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get staffStatusCancelled;

  /// No description provided for @staffNearScene.
  ///
  /// In en, this message translates to:
  /// **'You are {meters} m from the incident. Arrived?'**
  String staffNearScene(int meters);

  /// No description provided for @staffSeverity.
  ///
  /// In en, this message translates to:
  /// **'Severity'**
  String get staffSeverity;

  /// No description provided for @staffSeverity1.
  ///
  /// In en, this message translates to:
  /// **'1 · Minor'**
  String get staffSeverity1;

  /// No description provided for @staffSeverity2.
  ///
  /// In en, this message translates to:
  /// **'2 · Moderate'**
  String get staffSeverity2;

  /// No description provided for @staffSeverity3.
  ///
  /// In en, this message translates to:
  /// **'3 · Serious'**
  String get staffSeverity3;

  /// No description provided for @staffSeverity4.
  ///
  /// In en, this message translates to:
  /// **'4 · Critical'**
  String get staffSeverity4;

  /// No description provided for @staffCrewDanger.
  ///
  /// In en, this message translates to:
  /// **'Danger to the crew'**
  String get staffCrewDanger;

  /// No description provided for @staffSend.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get staffSend;

  /// No description provided for @staffDeceased.
  ///
  /// In en, this message translates to:
  /// **'Deceased'**
  String get staffDeceased;

  /// No description provided for @staffRescued.
  ///
  /// In en, this message translates to:
  /// **'Survivors'**
  String get staffRescued;

  /// No description provided for @staffTrapped.
  ///
  /// In en, this message translates to:
  /// **'Trapped'**
  String get staffTrapped;

  /// No description provided for @staffAddTransport.
  ///
  /// In en, this message translates to:
  /// **'Transfer a patient'**
  String get staffAddTransport;

  /// No description provided for @staffTriage.
  ///
  /// In en, this message translates to:
  /// **'Triage'**
  String get staffTriage;

  /// No description provided for @staffTriageRed.
  ///
  /// In en, this message translates to:
  /// **'Red · immediate'**
  String get staffTriageRed;

  /// No description provided for @staffTriageYellow.
  ///
  /// In en, this message translates to:
  /// **'Yellow · urgent'**
  String get staffTriageYellow;

  /// No description provided for @staffTriageGreen.
  ///
  /// In en, this message translates to:
  /// **'Green · minor'**
  String get staffTriageGreen;

  /// No description provided for @staffTriageBlack.
  ///
  /// In en, this message translates to:
  /// **'Black · deceased'**
  String get staffTriageBlack;

  /// No description provided for @staffAge.
  ///
  /// In en, this message translates to:
  /// **'Age'**
  String get staffAge;

  /// No description provided for @staffSex.
  ///
  /// In en, this message translates to:
  /// **'Sex'**
  String get staffSex;

  /// No description provided for @staffSexFemale.
  ///
  /// In en, this message translates to:
  /// **'Female'**
  String get staffSexFemale;

  /// No description provided for @staffSexMale.
  ///
  /// In en, this message translates to:
  /// **'Male'**
  String get staffSexMale;

  /// No description provided for @staffUnknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown'**
  String get staffUnknown;

  /// No description provided for @staffHospital.
  ///
  /// In en, this message translates to:
  /// **'Hospital'**
  String get staffHospital;

  /// No description provided for @staffKindFireEngine.
  ///
  /// In en, this message translates to:
  /// **'Fire engine'**
  String get staffKindFireEngine;

  /// No description provided for @staffKindWaterTanker.
  ///
  /// In en, this message translates to:
  /// **'Water tanker'**
  String get staffKindWaterTanker;

  /// No description provided for @staffKindAmbulance.
  ///
  /// In en, this message translates to:
  /// **'Ambulance'**
  String get staffKindAmbulance;

  /// No description provided for @staffKindRescue.
  ///
  /// In en, this message translates to:
  /// **'Rescue vehicle'**
  String get staffKindRescue;

  /// No description provided for @staffKindHeavy.
  ///
  /// In en, this message translates to:
  /// **'Heavy equipment'**
  String get staffKindHeavy;

  /// No description provided for @staffKindDrone.
  ///
  /// In en, this message translates to:
  /// **'Drone'**
  String get staffKindDrone;

  /// No description provided for @staffKindExtinguisher.
  ///
  /// In en, this message translates to:
  /// **'Large extinguisher'**
  String get staffKindExtinguisher;

  /// No description provided for @staffKindBoat.
  ///
  /// In en, this message translates to:
  /// **'Boat'**
  String get staffKindBoat;

  /// No description provided for @staffKindCommand.
  ///
  /// In en, this message translates to:
  /// **'Command vehicle'**
  String get staffKindCommand;

  /// No description provided for @staffKindOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get staffKindOther;

  /// No description provided for @staffErrVehicleTaken.
  ///
  /// In en, this message translates to:
  /// **'Another leader already holds this vehicle.'**
  String get staffErrVehicleTaken;

  /// No description provided for @staffErrShiftOpen.
  ///
  /// In en, this message translates to:
  /// **'You already have a shift open.'**
  String get staffErrShiftOpen;

  /// No description provided for @staffErrMissionActive.
  ///
  /// In en, this message translates to:
  /// **'A mission is still in progress: finish it first.'**
  String get staffErrMissionActive;

  /// No description provided for @staffErrNotOnScene.
  ///
  /// In en, this message translates to:
  /// **'Mark the arrival on scene first.'**
  String get staffErrNotOnScene;

  /// No description provided for @staffErrNoShift.
  ///
  /// In en, this message translates to:
  /// **'No shift open on this phone.'**
  String get staffErrNoShift;

  /// No description provided for @staffErrGeneric.
  ///
  /// In en, this message translates to:
  /// **'The room refused this action. Try again or call the room.'**
  String get staffErrGeneric;

  /// No description provided for @staffOnline.
  ///
  /// In en, this message translates to:
  /// **'Connected · updated {seconds} s ago'**
  String staffOnline(int seconds);

  /// No description provided for @staffOnlineMinutes.
  ///
  /// In en, this message translates to:
  /// **'Connected · updated {minutes} min ago'**
  String staffOnlineMinutes(int minutes);

  /// No description provided for @staffMission.
  ///
  /// In en, this message translates to:
  /// **'Mission'**
  String get staffMission;

  /// No description provided for @staffHighPriority.
  ///
  /// In en, this message translates to:
  /// **'High priority'**
  String get staffHighPriority;

  /// No description provided for @staffRoomNote.
  ///
  /// In en, this message translates to:
  /// **'Room\'s note'**
  String get staffRoomNote;

  /// No description provided for @staffDistanceKm.
  ///
  /// In en, this message translates to:
  /// **'{km} km away'**
  String staffDistanceKm(String km);

  /// No description provided for @staffStepReceived.
  ///
  /// In en, this message translates to:
  /// **'Mission received'**
  String get staffStepReceived;

  /// No description provided for @staffStepLeft.
  ///
  /// In en, this message translates to:
  /// **'We left'**
  String get staffStepLeft;

  /// No description provided for @staffStepOnTheWay.
  ///
  /// In en, this message translates to:
  /// **'On the way'**
  String get staffStepOnTheWay;

  /// No description provided for @staffStepArrived.
  ///
  /// In en, this message translates to:
  /// **'Arrived'**
  String get staffStepArrived;

  /// No description provided for @staffStepOver.
  ///
  /// In en, this message translates to:
  /// **'Intervention over'**
  String get staffStepOver;

  /// No description provided for @staffAwayFrom.
  ///
  /// In en, this message translates to:
  /// **'You are {meters} m from the scene'**
  String staffAwayFrom(int meters);

  /// No description provided for @staffRoute.
  ///
  /// In en, this message translates to:
  /// **'Route'**
  String get staffRoute;

  /// No description provided for @staffRoom.
  ///
  /// In en, this message translates to:
  /// **'Room'**
  String get staffRoom;

  /// No description provided for @staffReporter.
  ///
  /// In en, this message translates to:
  /// **'Reporter'**
  String get staffReporter;

  /// No description provided for @staffAskBackup.
  ///
  /// In en, this message translates to:
  /// **'Request backup'**
  String get staffAskBackup;

  /// No description provided for @staffAlertSent.
  ///
  /// In en, this message translates to:
  /// **'Sent to the room.'**
  String get staffAlertSent;

  /// No description provided for @staffAlertSeen.
  ///
  /// In en, this message translates to:
  /// **'Room saw it at {time}'**
  String staffAlertSeen(String time);

  /// No description provided for @staffAlertWaiting.
  ///
  /// In en, this message translates to:
  /// **'Waiting for the room'**
  String get staffAlertWaiting;

  /// No description provided for @staffAlertChoose.
  ///
  /// In en, this message translates to:
  /// **'Tap what applies, then send.'**
  String get staffAlertChoose;

  /// No description provided for @staffBackupFireEngine.
  ///
  /// In en, this message translates to:
  /// **'Fire engine'**
  String get staffBackupFireEngine;

  /// No description provided for @staffBackupAmbulance.
  ///
  /// In en, this message translates to:
  /// **'Ambulance'**
  String get staffBackupAmbulance;

  /// No description provided for @staffBackupExtrication.
  ///
  /// In en, this message translates to:
  /// **'Rescue (cutting)'**
  String get staffBackupExtrication;

  /// No description provided for @staffBackupLadder.
  ///
  /// In en, this message translates to:
  /// **'Ladder'**
  String get staffBackupLadder;

  /// No description provided for @staffBackupWaterTanker.
  ///
  /// In en, this message translates to:
  /// **'Water tanker'**
  String get staffBackupWaterTanker;

  /// No description provided for @staffBackupHazmat.
  ///
  /// In en, this message translates to:
  /// **'Hazardous materials'**
  String get staffBackupHazmat;

  /// No description provided for @staffBackupPolice.
  ///
  /// In en, this message translates to:
  /// **'Security'**
  String get staffBackupPolice;

  /// No description provided for @staffBackupHeavy.
  ///
  /// In en, this message translates to:
  /// **'Heavy equipment'**
  String get staffBackupHeavy;

  /// No description provided for @staffDangerFireSpread.
  ///
  /// In en, this message translates to:
  /// **'Fire spreading'**
  String get staffDangerFireSpread;

  /// No description provided for @staffDangerCollapse.
  ///
  /// In en, this message translates to:
  /// **'Collapse'**
  String get staffDangerCollapse;

  /// No description provided for @staffDangerGas.
  ///
  /// In en, this message translates to:
  /// **'Gas or hazardous materials'**
  String get staffDangerGas;

  /// No description provided for @staffDangerElectricity.
  ///
  /// In en, this message translates to:
  /// **'Electricity'**
  String get staffDangerElectricity;

  /// No description provided for @staffDangerViolence.
  ///
  /// In en, this message translates to:
  /// **'Assault'**
  String get staffDangerViolence;

  /// No description provided for @staffDangerTraffic.
  ///
  /// In en, this message translates to:
  /// **'Traffic'**
  String get staffDangerTraffic;

  /// No description provided for @staffSituation.
  ///
  /// In en, this message translates to:
  /// **'Situation report'**
  String get staffSituation;

  /// No description provided for @staffSituationDue.
  ///
  /// In en, this message translates to:
  /// **'First report: under 30 seconds'**
  String get staffSituationDue;

  /// No description provided for @staffSituationLast.
  ///
  /// In en, this message translates to:
  /// **'Last report {time} · {severity}'**
  String staffSituationLast(String time, String severity);

  /// No description provided for @staffType.
  ///
  /// In en, this message translates to:
  /// **'Type'**
  String get staffType;

  /// No description provided for @staffConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Confirmed: {type}'**
  String staffConfirmed(String type);

  /// No description provided for @staffDifferent.
  ///
  /// In en, this message translates to:
  /// **'Different'**
  String get staffDifferent;

  /// No description provided for @staffNeedBackup.
  ///
  /// In en, this message translates to:
  /// **'Backup needed?'**
  String get staffNeedBackup;

  /// No description provided for @staffNo.
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get staffNo;

  /// No description provided for @staffYes.
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get staffYes;

  /// No description provided for @staffLiveCounts.
  ///
  /// In en, this message translates to:
  /// **'Live counts'**
  String get staffLiveCounts;

  /// No description provided for @staffInjuredLight.
  ///
  /// In en, this message translates to:
  /// **'Lightly injured'**
  String get staffInjuredLight;

  /// No description provided for @staffInjuredSerious.
  ///
  /// In en, this message translates to:
  /// **'Seriously injured'**
  String get staffInjuredSerious;

  /// No description provided for @staffTransported.
  ///
  /// In en, this message translates to:
  /// **'Transported'**
  String get staffTransported;

  /// No description provided for @staffAttachments.
  ///
  /// In en, this message translates to:
  /// **'Attachments'**
  String get staffAttachments;

  /// No description provided for @staffPhoto.
  ///
  /// In en, this message translates to:
  /// **'Photo'**
  String get staffPhoto;

  /// No description provided for @staffVoice.
  ///
  /// In en, this message translates to:
  /// **'Voice note'**
  String get staffVoice;

  /// No description provided for @staffText.
  ///
  /// In en, this message translates to:
  /// **'Text'**
  String get staffText;

  /// No description provided for @staffSendReport.
  ///
  /// In en, this message translates to:
  /// **'Send the report'**
  String get staffSendReport;

  /// No description provided for @staffTransportTitle.
  ///
  /// In en, this message translates to:
  /// **'Patients transported (no names)'**
  String get staffTransportTitle;

  /// No description provided for @staffTransportsCount.
  ///
  /// In en, this message translates to:
  /// **'Transported ({count})'**
  String staffTransportsCount(int count);

  /// No description provided for @staffHospitalOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get staffHospitalOther;

  /// No description provided for @staffHospitalName.
  ///
  /// In en, this message translates to:
  /// **'Hospital name'**
  String get staffHospitalName;

  /// No description provided for @staffTimeAuto.
  ///
  /// In en, this message translates to:
  /// **'The time is recorded automatically.'**
  String get staffTimeAuto;

  /// No description provided for @staffSendNow.
  ///
  /// In en, this message translates to:
  /// **'Send now'**
  String get staffSendNow;

  /// No description provided for @staffAgeUnder12.
  ///
  /// In en, this message translates to:
  /// **'Under 12'**
  String get staffAgeUnder12;

  /// No description provided for @staffAge12.
  ///
  /// In en, this message translates to:
  /// **'12–17'**
  String get staffAge12;

  /// No description provided for @staffAge18.
  ///
  /// In en, this message translates to:
  /// **'18–29'**
  String get staffAge18;

  /// No description provided for @staffAge30.
  ///
  /// In en, this message translates to:
  /// **'30–44'**
  String get staffAge30;

  /// No description provided for @staffAge45.
  ///
  /// In en, this message translates to:
  /// **'45–59'**
  String get staffAge45;

  /// No description provided for @staffAge60.
  ///
  /// In en, this message translates to:
  /// **'60 and over'**
  String get staffAge60;

  /// No description provided for @staffDetailedReport.
  ///
  /// In en, this message translates to:
  /// **'Detailed report'**
  String get staffDetailedReport;

  /// No description provided for @staffDetailedDue.
  ///
  /// In en, this message translates to:
  /// **'Answers by tapping, from the approved template'**
  String get staffDetailedDue;

  /// No description provided for @staffDetailedSent.
  ///
  /// In en, this message translates to:
  /// **'Sent at {time} · template v{version}'**
  String staffDetailedSent(String time, int version);

  /// No description provided for @staffTemplateVersion.
  ///
  /// In en, this message translates to:
  /// **'Template version {version}'**
  String staffTemplateVersion(int version);

  /// No description provided for @staffNote.
  ///
  /// In en, this message translates to:
  /// **'Note'**
  String get staffNote;

  /// No description provided for @staffNoteHint.
  ///
  /// In en, this message translates to:
  /// **'500 characters at most'**
  String get staffNoteHint;

  /// No description provided for @staffRequired.
  ///
  /// In en, this message translates to:
  /// **'Required'**
  String get staffRequired;

  /// No description provided for @staffRecord.
  ///
  /// In en, this message translates to:
  /// **'Record'**
  String get staffRecord;

  /// No description provided for @staffRecordStop.
  ///
  /// In en, this message translates to:
  /// **'Stop'**
  String get staffRecordStop;

  /// No description provided for @staffRecordAgain.
  ///
  /// In en, this message translates to:
  /// **'Record again'**
  String get staffRecordAgain;

  /// No description provided for @staffVoiceMax.
  ///
  /// In en, this message translates to:
  /// **'60 seconds at most.'**
  String get staffVoiceMax;

  /// No description provided for @staffSent.
  ///
  /// In en, this message translates to:
  /// **'Sent.'**
  String get staffSent;

  /// No description provided for @staffErrTooLarge.
  ///
  /// In en, this message translates to:
  /// **'The file is too large.'**
  String get staffErrTooLarge;

  /// No description provided for @staffErrTooMany.
  ///
  /// In en, this message translates to:
  /// **'This mission already has 20 attachments.'**
  String get staffErrTooMany;

  /// No description provided for @staffErrBadMedia.
  ///
  /// In en, this message translates to:
  /// **'This file type is not accepted.'**
  String get staffErrBadMedia;

  /// No description provided for @staffErrTemplateChanged.
  ///
  /// In en, this message translates to:
  /// **'The template changed: open the report again.'**
  String get staffErrTemplateChanged;

  /// No description provided for @staffSimTemplate.
  ///
  /// In en, this message translates to:
  /// **'[SIM] Model template, until the Office approves it'**
  String get staffSimTemplate;

  /// No description provided for @staffSimHospital.
  ///
  /// In en, this message translates to:
  /// **'[SIM]'**
  String get staffSimHospital;

  /// No description provided for @staffTriageGreenShort.
  ///
  /// In en, this message translates to:
  /// **'Green'**
  String get staffTriageGreenShort;

  /// No description provided for @staffTriageYellowShort.
  ///
  /// In en, this message translates to:
  /// **'Yellow'**
  String get staffTriageYellowShort;

  /// No description provided for @staffTriageRedShort.
  ///
  /// In en, this message translates to:
  /// **'Red'**
  String get staffTriageRedShort;

  /// No description provided for @staffTriageBlackShort.
  ///
  /// In en, this message translates to:
  /// **'Black'**
  String get staffTriageBlackShort;

  /// No description provided for @staffTransportShort.
  ///
  /// In en, this message translates to:
  /// **'Patients transported'**
  String get staffTransportShort;

  /// No description provided for @staffNoNames.
  ///
  /// In en, this message translates to:
  /// **'no names'**
  String get staffNoNames;

  /// No description provided for @prevVisitsTitle.
  ///
  /// In en, this message translates to:
  /// **'Prevention visits'**
  String get prevVisitsTitle;

  /// No description provided for @prevVisitsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No visit scheduled in your governorate.'**
  String get prevVisitsEmpty;

  /// No description provided for @prevMine.
  ///
  /// In en, this message translates to:
  /// **'Mine'**
  String get prevMine;

  /// No description provided for @prevTakenByOther.
  ///
  /// In en, this message translates to:
  /// **'Taken by another inspector'**
  String get prevTakenByOther;

  /// No description provided for @prevOnPhone.
  ///
  /// In en, this message translates to:
  /// **'On the phone'**
  String get prevOnPhone;

  /// No description provided for @prevScheduledOn.
  ///
  /// In en, this message translates to:
  /// **'On {date}'**
  String prevScheduledOn(String date);

  /// No description provided for @prevNoDate.
  ///
  /// In en, this message translates to:
  /// **'No date'**
  String get prevNoDate;

  /// No description provided for @prevTake.
  ///
  /// In en, this message translates to:
  /// **'I take it'**
  String get prevTake;

  /// No description provided for @prevTakeHelp.
  ///
  /// In en, this message translates to:
  /// **'The visit is kept encrypted on your phone: you can work on site without a network.'**
  String get prevTakeHelp;

  /// No description provided for @prevStartGrid.
  ///
  /// In en, this message translates to:
  /// **'Start the inspection'**
  String get prevStartGrid;

  /// No description provided for @prevContinueGrid.
  ///
  /// In en, this message translates to:
  /// **'Continue the inspection'**
  String get prevContinueGrid;

  /// No description provided for @prevGridTitle.
  ///
  /// In en, this message translates to:
  /// **'Inspection grid'**
  String get prevGridTitle;

  /// No description provided for @prevSignTitle.
  ///
  /// In en, this message translates to:
  /// **'Attendees and signatures'**
  String get prevSignTitle;

  /// No description provided for @prevDecisionTitle.
  ///
  /// In en, this message translates to:
  /// **'Decision'**
  String get prevDecisionTitle;

  /// No description provided for @prevPending.
  ///
  /// In en, this message translates to:
  /// **'{count} waiting to be sent'**
  String prevPending(int count);

  /// No description provided for @prevSendNow.
  ///
  /// In en, this message translates to:
  /// **'Send now'**
  String get prevSendNow;

  /// No description provided for @prevSavedOffline.
  ///
  /// In en, this message translates to:
  /// **'Kept on the phone, sent when the network is back.'**
  String get prevSavedOffline;

  /// No description provided for @prevDeclared.
  ///
  /// In en, this message translates to:
  /// **'Declared: {value}'**
  String prevDeclared(String value);

  /// No description provided for @prevAllConform.
  ///
  /// In en, this message translates to:
  /// **'All conforming'**
  String get prevAllConform;

  /// No description provided for @prevObserved.
  ///
  /// In en, this message translates to:
  /// **'Observed'**
  String get prevObserved;

  /// No description provided for @prevResultConform.
  ///
  /// In en, this message translates to:
  /// **'Conforming'**
  String get prevResultConform;

  /// No description provided for @prevResultNonconform.
  ///
  /// In en, this message translates to:
  /// **'Non-conforming'**
  String get prevResultNonconform;

  /// No description provided for @prevResultNotChecked.
  ///
  /// In en, this message translates to:
  /// **'Not checked'**
  String get prevResultNotChecked;

  /// No description provided for @prevReasonMissing.
  ///
  /// In en, this message translates to:
  /// **'Missing'**
  String get prevReasonMissing;

  /// No description provided for @prevReasonBroken.
  ///
  /// In en, this message translates to:
  /// **'Out of order'**
  String get prevReasonBroken;

  /// No description provided for @prevReasonExpired.
  ///
  /// In en, this message translates to:
  /// **'Expired'**
  String get prevReasonExpired;

  /// No description provided for @prevReasonBlocked.
  ///
  /// In en, this message translates to:
  /// **'Blocked'**
  String get prevReasonBlocked;

  /// No description provided for @prevReasonInsufficient.
  ///
  /// In en, this message translates to:
  /// **'Insufficient'**
  String get prevReasonInsufficient;

  /// No description provided for @prevReasonNotAsPlan.
  ///
  /// In en, this message translates to:
  /// **'Not as on the plan'**
  String get prevReasonNotAsPlan;

  /// No description provided for @prevNeedsDetail.
  ///
  /// In en, this message translates to:
  /// **'Choose a reason or correct the count'**
  String get prevNeedsDetail;

  /// No description provided for @prevNoteOptional.
  ///
  /// In en, this message translates to:
  /// **'Note (optional)'**
  String get prevNoteOptional;

  /// No description provided for @prevPhoto.
  ///
  /// In en, this message translates to:
  /// **'Photo'**
  String get prevPhoto;

  /// No description provided for @prevPhotos.
  ///
  /// In en, this message translates to:
  /// **'Photos: {count}'**
  String prevPhotos(int count);

  /// No description provided for @prevPhotoLimit.
  ///
  /// In en, this message translates to:
  /// **'20 photos at most per visit.'**
  String get prevPhotoLimit;

  /// No description provided for @prevGeneral.
  ///
  /// In en, this message translates to:
  /// **'General photo'**
  String get prevGeneral;

  /// No description provided for @prevSummary.
  ///
  /// In en, this message translates to:
  /// **'{conform} conforming · {nonconform} non-conforming · {notChecked} not checked'**
  String prevSummary(int conform, int nonconform, int notChecked);

  /// No description provided for @prevSuggested.
  ///
  /// In en, this message translates to:
  /// **'Suggested decision: {decision}'**
  String prevSuggested(String decision);

  /// No description provided for @prevNextSign.
  ///
  /// In en, this message translates to:
  /// **'Next: signatures'**
  String get prevNextSign;

  /// No description provided for @prevAttendees.
  ///
  /// In en, this message translates to:
  /// **'Attendees'**
  String get prevAttendees;

  /// No description provided for @prevRepresentative.
  ///
  /// In en, this message translates to:
  /// **'Institution’s representative'**
  String get prevRepresentative;

  /// No description provided for @prevRepresentativeName.
  ///
  /// In en, this message translates to:
  /// **'Representative’s name'**
  String get prevRepresentativeName;

  /// No description provided for @prevRoleDirector.
  ///
  /// In en, this message translates to:
  /// **'Director'**
  String get prevRoleDirector;

  /// No description provided for @prevRoleSafetyOfficer.
  ///
  /// In en, this message translates to:
  /// **'Safety officer'**
  String get prevRoleSafetyOfficer;

  /// No description provided for @prevRoleManager.
  ///
  /// In en, this message translates to:
  /// **'Manager'**
  String get prevRoleManager;

  /// No description provided for @prevRoleGuard.
  ///
  /// In en, this message translates to:
  /// **'Security guard'**
  String get prevRoleGuard;

  /// No description provided for @prevRoleTechnician.
  ///
  /// In en, this message translates to:
  /// **'Technician'**
  String get prevRoleTechnician;

  /// No description provided for @prevSignInspector.
  ///
  /// In en, this message translates to:
  /// **'Inspector’s signature'**
  String get prevSignInspector;

  /// No description provided for @prevSignRepresentative.
  ///
  /// In en, this message translates to:
  /// **'Representative’s signature'**
  String get prevSignRepresentative;

  /// No description provided for @prevSignHere.
  ///
  /// In en, this message translates to:
  /// **'Sign here with your finger'**
  String get prevSignHere;

  /// No description provided for @prevClear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get prevClear;

  /// No description provided for @prevSigned.
  ///
  /// In en, this message translates to:
  /// **'Signed'**
  String get prevSigned;

  /// No description provided for @prevSignOff.
  ///
  /// In en, this message translates to:
  /// **'Close and send the inspection'**
  String get prevSignOff;

  /// No description provided for @prevSignMissing.
  ///
  /// In en, this message translates to:
  /// **'Both signatures and the representative’s name are needed.'**
  String get prevSignMissing;

  /// No description provided for @prevDetailMissing.
  ///
  /// In en, this message translates to:
  /// **'Non-conforming items without a reason: {count}'**
  String prevDetailMissing(int count);

  /// No description provided for @prevInspectionSent.
  ///
  /// In en, this message translates to:
  /// **'Inspection sent, report issued.'**
  String get prevInspectionSent;

  /// No description provided for @prevInspectionQueued.
  ///
  /// In en, this message translates to:
  /// **'Inspection kept, sent when the network is back.'**
  String get prevInspectionQueued;

  /// No description provided for @prevValidFor.
  ///
  /// In en, this message translates to:
  /// **'Valid for'**
  String get prevValidFor;

  /// No description provided for @prevYears.
  ///
  /// In en, this message translates to:
  /// **'{years, plural, =1{1 year} other{{years} years}}'**
  String prevYears(int years);

  /// No description provided for @prevReservations.
  ///
  /// In en, this message translates to:
  /// **'Reservations'**
  String get prevReservations;

  /// No description provided for @prevReservationsHelp.
  ///
  /// In en, this message translates to:
  /// **'Proposed from the non-conforming items; remove what does not apply.'**
  String get prevReservationsHelp;

  /// No description provided for @prevDueIn.
  ///
  /// In en, this message translates to:
  /// **'Deadline'**
  String get prevDueIn;

  /// No description provided for @prevMonths.
  ///
  /// In en, this message translates to:
  /// **'{months, plural, =1{1 month} other{{months} months}}'**
  String prevMonths(int months);

  /// No description provided for @prevRefusalReason.
  ///
  /// In en, this message translates to:
  /// **'Reason for refusal'**
  String get prevRefusalReason;

  /// No description provided for @prevRefuseDanger.
  ///
  /// In en, this message translates to:
  /// **'Serious danger to people'**
  String get prevRefuseDanger;

  /// No description provided for @prevRefuseExits.
  ///
  /// In en, this message translates to:
  /// **'Exits unusable'**
  String get prevRefuseExits;

  /// No description provided for @prevRefuseEquipment.
  ///
  /// In en, this message translates to:
  /// **'Fire equipment insufficient'**
  String get prevRefuseEquipment;

  /// No description provided for @prevRefuseDocuments.
  ///
  /// In en, this message translates to:
  /// **'Safety documents missing'**
  String get prevRefuseDocuments;

  /// No description provided for @prevSendDecision.
  ///
  /// In en, this message translates to:
  /// **'Send the decision'**
  String get prevSendDecision;

  /// No description provided for @prevDecisionSent.
  ///
  /// In en, this message translates to:
  /// **'Decision sent.'**
  String get prevDecisionSent;

  /// No description provided for @prevDecisionQueued.
  ///
  /// In en, this message translates to:
  /// **'Decision kept, sent after the inspection when the network is back.'**
  String get prevDecisionQueued;

  /// No description provided for @prevDecisionAfterInspection.
  ///
  /// In en, this message translates to:
  /// **'The decision comes after the inspection is closed.'**
  String get prevDecisionAfterInspection;

  /// No description provided for @prevCertificate.
  ///
  /// In en, this message translates to:
  /// **'Certificate {code}'**
  String prevCertificate(String code);

  /// No description provided for @prevErrTaken.
  ///
  /// In en, this message translates to:
  /// **'Another inspector took this visit.'**
  String get prevErrTaken;

  /// No description provided for @prevErrTooManyPhotos.
  ///
  /// In en, this message translates to:
  /// **'This visit already has 20 photos.'**
  String get prevErrTooManyPhotos;

  /// No description provided for @prevErrSignature.
  ///
  /// In en, this message translates to:
  /// **'Invalid signature, sign again.'**
  String get prevErrSignature;

  /// No description provided for @prevErrValidUntil.
  ///
  /// In en, this message translates to:
  /// **'Validity period refused.'**
  String get prevErrValidUntil;

  /// No description provided for @prevErrState.
  ///
  /// In en, this message translates to:
  /// **'The visit changed on the dashboard.'**
  String get prevErrState;

  /// No description provided for @prevSectionEquipment.
  ///
  /// In en, this message translates to:
  /// **'Safety equipment'**
  String get prevSectionEquipment;

  /// No description provided for @prevSectionSite.
  ///
  /// In en, this message translates to:
  /// **'On-site checks'**
  String get prevSectionSite;

  /// No description provided for @prevSimGrid.
  ///
  /// In en, this message translates to:
  /// **'[SIM] On-site checks: model until the Office’s official grid'**
  String get prevSimGrid;

  /// No description provided for @prevItemHazmat.
  ///
  /// In en, this message translates to:
  /// **'Hazardous material {n}'**
  String prevItemHazmat(int n);

  /// No description provided for @prevItemCapacity.
  ///
  /// In en, this message translates to:
  /// **'Capacity'**
  String get prevItemCapacity;

  /// No description provided for @prevItemFloors.
  ///
  /// In en, this message translates to:
  /// **'Floors'**
  String get prevItemFloors;

  /// No description provided for @prevItemHeight.
  ///
  /// In en, this message translates to:
  /// **'Height (m)'**
  String get prevItemHeight;

  /// No description provided for @prevItemAddress.
  ///
  /// In en, this message translates to:
  /// **'Address'**
  String get prevItemAddress;

  /// No description provided for @prevItemFamily.
  ///
  /// In en, this message translates to:
  /// **'Family'**
  String get prevItemFamily;

  /// No description provided for @prevItemCategory.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get prevItemCategory;

  /// No description provided for @prevItemEvacuation.
  ///
  /// In en, this message translates to:
  /// **'Assembly points'**
  String get prevItemEvacuation;

  /// No description provided for @prevItemRepresentative.
  ///
  /// In en, this message translates to:
  /// **'Team representative'**
  String get prevItemRepresentative;

  /// No description provided for @prevItemMembers.
  ///
  /// In en, this message translates to:
  /// **'Team members'**
  String get prevItemMembers;

  /// No description provided for @prevItemSafetyFile.
  ///
  /// In en, this message translates to:
  /// **'Safety file'**
  String get prevItemSafetyFile;

  /// No description provided for @prevItemSafetyPlan.
  ///
  /// In en, this message translates to:
  /// **'Safety plan'**
  String get prevItemSafetyPlan;

  /// No description provided for @prevItemExits.
  ///
  /// In en, this message translates to:
  /// **'Exits clear'**
  String get prevItemExits;

  /// No description provided for @prevItemSignage.
  ///
  /// In en, this message translates to:
  /// **'Signage'**
  String get prevItemSignage;

  /// No description provided for @prevItemLighting.
  ///
  /// In en, this message translates to:
  /// **'Emergency lighting works'**
  String get prevItemLighting;

  /// No description provided for @prevItemAlarm.
  ///
  /// In en, this message translates to:
  /// **'Alarm test'**
  String get prevItemAlarm;

  /// No description provided for @prevItemExtinguishers.
  ///
  /// In en, this message translates to:
  /// **'Extinguishers within reach'**
  String get prevItemExtinguishers;

  /// No description provided for @prevItemElectrical.
  ///
  /// In en, this message translates to:
  /// **'Electrical installations'**
  String get prevItemElectrical;

  /// No description provided for @prevDeclaredNone.
  ///
  /// In en, this message translates to:
  /// **'None'**
  String get prevDeclaredNone;

  /// No description provided for @prevYes.
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get prevYes;

  /// No description provided for @prevNo.
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get prevNo;

  /// No description provided for @staffPending.
  ///
  /// In en, this message translates to:
  /// **'{count} waiting, sent when the network is back'**
  String staffPending(int count);

  /// No description provided for @staffSendSms.
  ///
  /// In en, this message translates to:
  /// **'Send by SMS'**
  String get staffSendSms;

  /// No description provided for @staffSmsOpened.
  ///
  /// In en, this message translates to:
  /// **'The SMS app is open: press Send.'**
  String get staffSmsOpened;

  /// No description provided for @staffTrackingTitle.
  ///
  /// In en, this message translates to:
  /// **'e-Himaya: mission under way'**
  String get staffTrackingTitle;

  /// No description provided for @staffTrackingText.
  ///
  /// In en, this message translates to:
  /// **'The vehicle\'s position goes to the operations room until the mission ends.'**
  String get staffTrackingText;

  /// No description provided for @staffMissionChannel.
  ///
  /// In en, this message translates to:
  /// **'Missions'**
  String get staffMissionChannel;

  /// No description provided for @staffWaitingBadge.
  ///
  /// In en, this message translates to:
  /// **'Waiting'**
  String get staffWaitingBadge;

  /// No description provided for @teamEnRoute.
  ///
  /// In en, this message translates to:
  /// **'The team is on its way'**
  String get teamEnRoute;

  /// No description provided for @teamOnScene.
  ///
  /// In en, this message translates to:
  /// **'The team has arrived'**
  String get teamOnScene;

  /// No description provided for @teamNoticesSetting.
  ///
  /// In en, this message translates to:
  /// **'Tell me when the team is coming'**
  String get teamNoticesSetting;

  /// No description provided for @teamNoticesHint.
  ///
  /// In en, this message translates to:
  /// **'A notification when the team leaves, then when it arrives.'**
  String get teamNoticesHint;

  /// No description provided for @staffKept.
  ///
  /// In en, this message translates to:
  /// **'Kept on the phone: sent when the network is back.'**
  String get staffKept;
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
