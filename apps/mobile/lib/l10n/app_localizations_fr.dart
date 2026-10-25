// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get appTitle => 'e-Himaya';

  @override
  String get actionContinue => 'Continuer';

  @override
  String get actionCancel => 'Annuler';

  @override
  String get actionSave => 'Enregistrer';

  @override
  String get actionLater => 'Plus tard';

  @override
  String get actionRetry => 'Réessayer';

  @override
  String get copied => 'Code de suivi copié.';

  @override
  String get copyTrackingCode => 'Copier le code de suivi';

  @override
  String callNumber(String number) {
    return 'Appeler le $number';
  }

  @override
  String get charterTitle => 'Conditions d\'utilisation';

  @override
  String charterVersionLabel(String version) {
    return 'Version $version';
  }

  @override
  String get charterIntro =>
      'e-Himaya est la plateforme nationale de signalement des urgences à la Protection civile. Avant de l’utiliser, lisez comment vos données sont traitées et quelles sont vos obligations.';

  @override
  String get charterCheckbox =>
      'J\'ai lu les conditions d\'utilisation et je les accepte ; je sais qu\'une fausse alerte volontaire engage ma responsabilité.';

  @override
  String charterAcceptedOn(String date) {
    return 'Acceptée le $date';
  }

  @override
  String get roleTitle => 'Qui êtes-vous ?';

  @override
  String get roleCitizen => 'Citoyen';

  @override
  String get roleCitizenDesc =>
      'Signaler une urgence, envoyer un SOS et suivre vos signalements.';

  @override
  String get roleInstitution => 'Institution';

  @override
  String get roleInstitutionDesc =>
      'Institution publique ou privée disposant d’un compte enregistré.';

  @override
  String get institutionTitle => 'Institutions';

  @override
  String get institutionBody =>
      'L’inscription est obligatoire pour les institutions et se fait via le portail des institutions, pas dans cette application. Si votre institution dispose déjà d’un compte, connectez-vous ci-dessous.';

  @override
  String get institutionLogin => 'Se connecter';

  @override
  String get citizenModeTitle => 'Comment souhaitez-vous signaler ?';

  @override
  String get citizenAnonymous => 'Continuer sans compte';

  @override
  String get citizenAnonymousDesc =>
      'Le plus rapide. Aucune information personnelle n’est demandée.';

  @override
  String get citizenRegister => 'Créer un compte';

  @override
  String get citizenRegisterDesc =>
      'Suivez vos signalements sur tout appareil ; vos signalements sont mieux qualifiés.';

  @override
  String get citizenLogin => 'J’ai déjà un compte';

  @override
  String get citizenLoginDesc => 'Connectez-vous avec votre compte e-Himaya.';

  @override
  String get changeRole => 'Changer de profil';

  @override
  String get loginCancelled => 'Connexion annulée.';

  @override
  String get loginFailed =>
      'Échec de la connexion. Vérifiez votre connexion et réessayez.';

  @override
  String get profileTitle => 'Compléter votre profil';

  @override
  String get profileIntro =>
      'Ces informations serviront à vérifier vos signalements. Vous pouvez les compléter plus tard depuis les paramètres.';

  @override
  String get profileFirstName => 'Prénom';

  @override
  String get profileLastName => 'Nom';

  @override
  String get profileCin => 'Numéro de CIN';

  @override
  String get profileCinHint => '8 chiffres';

  @override
  String profileCinStored(String last4) {
    return 'La CIN enregistrée se termine par $last4 ; ressaisissez-la pour enregistrer.';
  }

  @override
  String get profilePhone => 'Numéro de téléphone';

  @override
  String get profileGouvernorat => 'Gouvernorat';

  @override
  String get profileDelegation => 'Délégation';

  @override
  String get profileAddress => 'Adresse (facultatif)';

  @override
  String get profileSaved => 'Profil enregistré.';

  @override
  String get validationRequired => 'Obligatoire.';

  @override
  String get validationCin => 'La CIN comporte exactement 8 chiffres.';

  @override
  String get validationPhone => 'Saisissez les 8 chiffres après +216.';

  @override
  String get geoLoadFailed => 'Impossible de charger la liste.';

  @override
  String get navHome => 'Accueil';

  @override
  String get navReports => 'Mes signalements';

  @override
  String get navSettings => 'Paramètres';

  @override
  String get homeTagline => 'En cas d’urgence, chaque seconde compte.';

  @override
  String get homeNewReport => 'Nouveau signalement';

  @override
  String get homeNewReportDesc =>
      'Incendie, inondation, accident… avec photos, vidéo ou voix.';

  @override
  String get homeEmergencyDesc =>
      'Appeler directement le 198, 190, 197 ou 193, même hors ligne.';

  @override
  String get homeTrackDesc => 'Suivre un signalement avec son code.';

  @override
  String pendingSyncBanner(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count signalements en attente d’envoi',
      one: '1 signalement en attente d’envoi',
    );
    return '$_temp0';
  }

  @override
  String get sosButtonLabel => 'SOS';

  @override
  String get sosHint =>
      'Touchez deux fois ou maintenez pour envoyer votre position.';

  @override
  String get sosArmed => 'Touchez encore pour envoyer le SOS.';

  @override
  String get sosSending => 'Envoi du SOS…';

  @override
  String get sosConfirmTitle => 'Envoyer un SOS ?';

  @override
  String get sosConfirmBody =>
      'Votre position actuelle sera envoyée à la Protection civile.';

  @override
  String get sosConfirmAction => 'Envoyer le SOS';

  @override
  String get sosNoLocation =>
      'Votre position n’est pas disponible. Activez la localisation ou appelez la Protection civile.';

  @override
  String get sosQueuedTitle => 'SOS enregistré';

  @override
  String get anonBlockedBody =>
      'Le signalement sans compte est suspendu sur cet appareil. Créez un compte pour continuer à signaler.';

  @override
  String get emergencyTitle => 'Numéros d’urgence';

  @override
  String get emergencyIntro =>
      'Les appels passent directement par votre carte SIM, même sans internet.';

  @override
  String get emergencyCivilProtection => 'Protection civile';

  @override
  String get emergencySamu => 'SAMU (aide médicale urgente)';

  @override
  String get emergencyPolice => 'Police secours';

  @override
  String get emergencyNationalGuard => 'Garde nationale';

  @override
  String emergencyCallSemantics(String name, String number) {
    return 'Appeler $name, $number';
  }

  @override
  String get dialFailed => 'Cet appareil ne peut pas passer d’appels.';

  @override
  String get categorySos => 'SOS';

  @override
  String get categoryFire => 'Incendie';

  @override
  String get categoryFlood => 'Inondation';

  @override
  String get categoryTrafficAccident => 'Accident de la route';

  @override
  String get categoryDrowning => 'Noyade';

  @override
  String get categoryLandslide => 'Glissement de terrain';

  @override
  String get categoryChemicalLeak => 'Fuite chimique';

  @override
  String get categoryMedical => 'Urgence médicale';

  @override
  String get categoryOther => 'Autre';

  @override
  String get statusReceived => 'Reçu';

  @override
  String get statusInProgress => 'En cours de traitement';

  @override
  String get statusIntervened => 'Intervention effectuée';

  @override
  String get statusOngoing => 'Intervention en cours';

  @override
  String get statusClosed => 'Intervention clôturée';

  @override
  String get statusRejected => 'Rejeté';

  @override
  String get statusUnknown => 'Statut inconnu';

  @override
  String get newReportTitle => 'Nouveau signalement';

  @override
  String get chooseCategory => 'Que se passe-t-il ?';

  @override
  String get reportLocation => 'Localisation';

  @override
  String get locationLocating => 'Localisation en cours…';

  @override
  String locationAccuracy(int meters) {
    return 'Position trouvée, précision ±$meters m';
  }

  @override
  String get locationManual => 'Position placée sur la carte';

  @override
  String get locationAdjustHint =>
      'Déplacez la carte pour placer l’épingle sur l’incident.';

  @override
  String get locationUnavailable =>
      'Pas encore de position GPS. Placez l’épingle sur la carte ou réessayez.';

  @override
  String get locationPermissionDenied =>
      'La localisation est désactivée ou refusée. Placez l’épingle sur la carte.';

  @override
  String get locationOutsideTunisia =>
      'La position doit se trouver en Tunisie.';

  @override
  String get locationRefresh => 'Utiliser ma position';

  @override
  String get mapPinSemantics => 'Épingle de la position du signalement';

  @override
  String get reportDescription => 'Description (facultatif)';

  @override
  String get reportDescriptionHint => 'Que voyez-vous ? Y a-t-il des blessés ?';

  @override
  String get reportAttachments => 'Photos, vidéos et message vocal';

  @override
  String get attachTakePhoto => 'Prendre une photo';

  @override
  String get attachPickPhoto => 'Galerie photos';

  @override
  String get attachRecordVideo => 'Filmer une vidéo';

  @override
  String get attachPickVideo => 'Choisir une vidéo';

  @override
  String attachmentPhoto(int n) {
    return 'Photo $n';
  }

  @override
  String attachmentVideo(int n) {
    return 'Vidéo $n';
  }

  @override
  String attachmentTooLarge(int maxMb) {
    return 'Ce fichier est trop volumineux (maximum $maxMb Mo).';
  }

  @override
  String get attachmentUnsupported => 'Ce format de fichier n’est pas accepté.';

  @override
  String attachmentLimit(int max) {
    return 'Au maximum $max fichiers par signalement.';
  }

  @override
  String get removeAttachment => 'Retirer la pièce jointe';

  @override
  String get pickerFailed =>
      'Impossible d’ouvrir l’appareil photo ou la galerie.';

  @override
  String get audioTitle => 'Message vocal';

  @override
  String get audioMaxDuration => '5 minutes max.';

  @override
  String get audioRecord => 'Enregistrer';

  @override
  String get audioStop => 'Arrêter';

  @override
  String get audioPlay => 'Écouter l’enregistrement';

  @override
  String get audioPause => 'Pause';

  @override
  String get audioReRecord => 'Réenregistrer';

  @override
  String get audioDelete => 'Supprimer l’enregistrement';

  @override
  String audioRecording(String duration) {
    return 'Enregistrement… $duration';
  }

  @override
  String get audioPermissionDenied => 'L’accès au microphone a été refusé.';

  @override
  String get audioFailed => 'L’enregistrement n’a pas pu démarrer.';

  @override
  String get reportSubmit => 'Envoyer le signalement';

  @override
  String get reportNeedsLocation =>
      'Attendez votre position ou placez l’épingle sur la carte.';

  @override
  String get reportOfflineNote =>
      'Sans réseau, le signalement est enregistré chiffré sur le téléphone et envoyé automatiquement plus tard.';

  @override
  String get reportSaveFailed =>
      'Le signalement n’a pas pu être enregistré. Réessayez.';

  @override
  String get reportQueuedTitle => 'Signalement enregistré';

  @override
  String get reportTempCodeLabel => 'Code provisoire';

  @override
  String get reportQueuedBody =>
      'Conservez ce code. Il sera remplacé par le code de suivi définitif dès que la Protection civile aura reçu votre signalement.';

  @override
  String get reportReceivedBody =>
      'Votre signalement a été reçu par la Protection civile. Utilisez ce code pour le suivre.';

  @override
  String get reportBackHome => 'Retour à l’accueil';

  @override
  String get temporaryCodeNote => 'Code provisoire, en attente d’envoi';

  @override
  String get myReportsTitle => 'Mes signalements';

  @override
  String get myReportsEmpty => 'Aucun signalement pour le moment.';

  @override
  String get myReportsOffline => 'Actualisation impossible depuis le serveur.';

  @override
  String get reportPendingSync => 'En attente d’envoi';

  @override
  String get reportConflict => 'Version du serveur conservée';

  @override
  String get reportFailed => 'Non accepté';

  @override
  String get reportBlocked => 'Compte requis';

  @override
  String reportUploadingMedia(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count pièces jointes en cours d’envoi',
      one: '1 pièce jointe en cours d’envoi',
    );
    return '$_temp0';
  }

  @override
  String reportMediaRejected(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count pièces jointes refusées',
      one: '1 pièce jointe refusée',
    );
    return '$_temp0';
  }

  @override
  String get trackTitle => 'Suivre un signalement';

  @override
  String get trackingCodeLabel => 'Code de suivi';

  @override
  String get trackHint => 'EH-26-61-0004821';

  @override
  String get trackAction => 'Suivre';

  @override
  String get trackInvalid => 'Saisissez un code comme EH-26-61-0004821.';

  @override
  String get trackHistory => 'Historique';

  @override
  String receivedAt(String date) {
    return 'Reçu le $date';
  }

  @override
  String get settingsTitle => 'Paramètres';

  @override
  String get settingsLanguage => 'Langue';

  @override
  String get languageArabic => 'العربية';

  @override
  String get languageFrench => 'Français';

  @override
  String get languageEnglish => 'English';

  @override
  String get settingsTheme => 'Apparence';

  @override
  String get themeSystem => 'Comme le téléphone';

  @override
  String get themeLight => 'Clair';

  @override
  String get themeDark => 'Sombre';

  @override
  String get settingsIdentity => 'Identité';

  @override
  String get identityAnonymous => 'Sans compte (cet appareil)';

  @override
  String get identityRegistered => 'Connecté';

  @override
  String identityRegisteredAs(String name) {
    return 'Connecté en tant que $name';
  }

  @override
  String get identityNone => 'Non connecté';

  @override
  String get settingsRegister => 'Créer un compte';

  @override
  String get settingsProfile => 'Mon profil';

  @override
  String get settingsLogout => 'Se déconnecter';

  @override
  String get logoutConfirmTitle => 'Se déconnecter ?';

  @override
  String get logoutConfirmBody =>
      'Les signalements en attente restent sur ce téléphone et seront envoyés après une nouvelle connexion ou si vous continuez sans compte.';

  @override
  String get settingsCharter => 'Conditions d\'utilisation';

  @override
  String get errorAuthenticationRequired =>
      'Votre session a expiré. Veuillez vous reconnecter.';

  @override
  String get errorInvalidDeviceKey =>
      'Cet appareil n’a pas pu être identifié. Redémarrez l’application.';

  @override
  String get errorAnonBlocked =>
      'Le signalement sans compte est suspendu sur cet appareil. Veuillez créer un compte.';

  @override
  String get errorAccountSuspended => 'Votre compte est suspendu.';

  @override
  String get errorConsentRequired =>
      'Veuillez accepter les conditions d\'utilisation avant de signaler.';

  @override
  String get errorRateLimited => 'Trop de requêtes. Patientez un instant.';

  @override
  String get errorUnknownCharterVersion =>
      'Les conditions d\'utilisation ont changé. Merci de les relire.';

  @override
  String get errorClientUuidConflict =>
      'Ce signalement est en conflit avec un autre sur le serveur.';

  @override
  String get errorNotFound => 'Introuvable. Vérifiez le code.';

  @override
  String get errorValidation => 'Certaines informations sont invalides.';

  @override
  String get errorNetwork =>
      'Pas de connexion au serveur. Nouvel essai automatique.';

  @override
  String get errorServer => 'Le service est momentanément indisponible.';

  @override
  String get errorUnknown => 'Une erreur est survenue.';

  @override
  String get errorMediaRefused => 'La pièce jointe a été refusée.';

  @override
  String get errorMediaTooLarge => 'La pièce jointe est trop volumineuse.';

  @override
  String get errorUnsupportedMediaType =>
      'Ce format de pièce jointe n’est pas accepté.';

  @override
  String get errorTooManyMedia =>
      'Ce signalement a déjà le nombre maximal de pièces jointes.';

  @override
  String get errorUploadWindowClosed =>
      'Les pièces jointes ne peuvent être ajoutées que dans les 24 heures suivant le signalement.';

  @override
  String get errorMediaRejected =>
      'La pièce jointe a été altérée pendant l’envoi et refusée.';

  @override
  String get errorOrgNotFound =>
      'Établissement introuvable, ou vous n’en êtes plus membre.';

  @override
  String get errorOrgNotActive =>
      'Cet établissement n’est pas actif (en cours d’examen, rejeté ou suspendu) : il ne peut pas signaler.';

  @override
  String get errorOrgRoleRequired =>
      'Votre rôle dans cet établissement ne permet pas cette action.';

  @override
  String get reportAsTitle => 'Signaler en tant que';

  @override
  String get reportAsSelf => 'Moi-même';

  @override
  String get reportAsInstitutionUnnamed => 'Établissement';

  @override
  String get reportOrgRefused => 'Refusé pour l’établissement';

  @override
  String get reportOrgNotFoundBody =>
      'Ce signalement n’a pas pu être envoyé au nom de l’établissement : il est introuvable ou vous n’en êtes plus membre. Il est conservé sur ce téléphone. Vous pouvez l’envoyer en votre nom.';

  @override
  String get reportOrgNotActiveBody =>
      'Ce signalement n’a pas pu être envoyé au nom de l’établissement car celui-ci n’est pas actif. Il est conservé sur ce téléphone. Vous pouvez l’envoyer en votre nom.';

  @override
  String get reportResendAsSelf => 'Envoyer en mon nom';

  @override
  String get reportResentAsSelf => 'Le signalement sera envoyé en votre nom.';

  @override
  String get settingsSosReportAs => 'SOS';

  @override
  String get settingsSosReportAsHint =>
      'Le bouton SOS envoie l’alerte en tant que :';

  @override
  String get myInstitutionTitle => 'Mon établissement';

  @override
  String get myInstitutionsTitle => 'Mes établissements';

  @override
  String get myInstitutionsEmpty => 'Vous n’êtes membre d’aucun établissement.';

  @override
  String get homeInstitutionDesc =>
      'Fiche de sécurité, équipe et signalements de votre établissement';

  @override
  String get orgKindIndustrial => 'Industrielle';

  @override
  String get orgKindEducational => 'Éducative';

  @override
  String get orgKindHotel => 'Hôtel';

  @override
  String get orgKindGovernment => 'Administration publique';

  @override
  String get orgKindPrivate => 'Privée';

  @override
  String get orgKindOther => 'Autre';

  @override
  String get orgStatusPendingReview => 'En cours d’examen';

  @override
  String get orgStatusActive => 'Active';

  @override
  String get orgStatusRejected => 'Rejetée';

  @override
  String get orgStatusSuspended => 'Suspendue';

  @override
  String get orgFamilyHighRise => 'Immeuble de grande hauteur';

  @override
  String get orgFamilyIndustrial => 'Établissement industriel';

  @override
  String get orgFamilyErp => 'Établissement recevant du public';

  @override
  String get orgFamilyWorkplace => 'Lieu de travail';

  @override
  String orgErpCategory(int category) {
    return 'catégorie $category';
  }

  @override
  String get orgTeamRepresentative => 'Représentant';

  @override
  String get orgTeamMember => 'Membre';

  @override
  String get trainingValid => 'valide';

  @override
  String get trainingExpiring => 'expire bientôt';

  @override
  String get trainingExpired => 'expirée';

  @override
  String get trainingUnknown => 'inconnue';

  @override
  String orgTraining(String status) {
    return 'Formation : $status';
  }

  @override
  String get orgCapacity => 'Capacité (nombre maximal de personnes)';

  @override
  String get orgAddress => 'Adresse';

  @override
  String get orgClassification => 'Classement';

  @override
  String get orgClassificationProvisional =>
      'Provisoire : calculé avec des seuils encore à valider par la Protection civile.';

  @override
  String get orgAlerts => 'Alertes';

  @override
  String orgAlertsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count alertes',
      one: '1 alerte',
    );
    return '$_temp0';
  }

  @override
  String get orgNoAlerts => 'Aucune alerte';

  @override
  String get orgSafetyTeam => 'Équipe de sécurité';

  @override
  String get orgTeamEmpty => 'Aucune équipe de sécurité enregistrée.';

  @override
  String orgCallMember(String name) {
    return 'Appeler $name';
  }

  @override
  String orgHazmatTitle(int count) {
    return 'Matières dangereuses ($count)';
  }

  @override
  String get orgHazmatEmpty => 'Aucune matière dangereuse enregistrée.';

  @override
  String orgUnNumber(String number) {
    return 'ONU $number';
  }

  @override
  String orgOfflineCopy(String date) {
    return 'Hors ligne : copie enregistrée le $date.';
  }

  @override
  String get orgPortalNote =>
      'La modification détaillée de l’établissement (fiche, équipe, matières dangereuses, documents, certificat) se fait sur le portail des établissements.';

  @override
  String get orgOpenPortal => 'Ouvrir le portail';

  @override
  String get orgPortalUnavailable =>
      'Impossible d’ouvrir le portail sur ce téléphone.';

  @override
  String get orgRecentReports => 'Signalements récents de l’établissement';

  @override
  String get orgReportsEmpty => 'Aucun signalement pour le moment.';

  @override
  String orgReportBy(String name) {
    return 'Par $name';
  }

  @override
  String get notificationsTitle => 'Notifications';

  @override
  String get activeAlertsTitle => 'Alertes en cours';

  @override
  String get activeAlertsNone => 'Aucune alerte en cours pour votre zone.';

  @override
  String get inboxTitle => 'Messages';

  @override
  String get inboxEmpty => 'Aucun message pour l’instant.';

  @override
  String get inboxNoIdentity =>
      'Choisissez comment utiliser l’application pour recevoir des messages.';

  @override
  String get inboxLoadMore => 'Afficher les messages plus anciens';

  @override
  String get inboxAlertActive => 'Alerte en cours';

  @override
  String get inboxAlertEnded => 'Alerte terminée';

  @override
  String get alertTitle => 'Alerte';

  @override
  String get alertOpen => 'Ouvrir l’alerte';

  @override
  String alertUntil(String time) {
    return 'Jusqu’au $time';
  }

  @override
  String alertPublishedAt(String time) {
    return 'Émise le $time';
  }

  @override
  String get alertNotActive => 'Cette alerte est terminée ou a été levée.';

  @override
  String get alertAreaNational => 'Tout le pays';

  @override
  String get alertAreaZone => 'Zone délimitée sur la carte';

  @override
  String alertAreaGouvernorats(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count gouvernorats',
      one: '1 gouvernorat',
    );
    return '$_temp0';
  }

  @override
  String get severityHigh => 'Alerte rouge';

  @override
  String get severityMedium => 'Alerte orange';

  @override
  String get severityLow => 'Alerte jaune';

  @override
  String get hazardHeavyRain => 'Fortes pluies';

  @override
  String get hazardFlood => 'Inondation';

  @override
  String get hazardStorm => 'Tempête';

  @override
  String get hazardWind => 'Vent violent';

  @override
  String get hazardHeatWave => 'Canicule';

  @override
  String get hazardColdWave => 'Vague de froid';

  @override
  String get hazardSea => 'Mer agitée';

  @override
  String get hazardForestFire => 'Feu de forêt';

  @override
  String get hazardChemical => 'Risque chimique';

  @override
  String get hazardOther => 'Autre risque';

  @override
  String get topicActivity => 'Activité';

  @override
  String get topicAwareness => 'Sensibilisation';

  @override
  String get topicTraining => 'Formation';

  @override
  String get topicWorldDay => 'Journée mondiale';

  @override
  String get topicOther => 'Information';

  @override
  String get settingsAlerts => 'Alertes et notifications';

  @override
  String get settingsLocationAlerts => 'Alertes là où je suis';

  @override
  String get settingsLocationAlertsHelp =>
      'Utilise la position approximative du téléphone (environ 1 km) pour vous envoyer les alertes de la zone où vous êtes.';

  @override
  String get channelAlerts => 'Alertes urgentes';

  @override
  String get channelAlertsDesc =>
      'Alertes de la Protection civile et appels aux volontaires.';

  @override
  String get channelGeneral => 'Informations';

  @override
  String get channelGeneralDesc =>
      'Suivi de vos signalements et messages d’information.';

  @override
  String get pushSimulationBadge => 'Mode simulation';

  @override
  String get pushSimulationHelp =>
      'Les notifications proviennent du simulateur local, pas de Firebase. Aucune livraison par un vrai service push.';

  @override
  String get tipsTitle => 'Conseils de sécurité';

  @override
  String get tipsIntro =>
      'Les bons gestes et ce qu’il faut éviter. Disponibles sans connexion.';

  @override
  String get tipsDo => 'À faire';

  @override
  String get tipsDont => 'À éviter';

  @override
  String get tipEarthquake => 'Séisme';

  @override
  String get homeTipsDesc =>
      'Les bons gestes en cas d’urgence, même hors ligne.';

  @override
  String get volunteerTitle => 'Volontariat';

  @override
  String get homeVolunteerDesc =>
      'Rejoignez les volontaires et répondez aux appels près de chez vous.';

  @override
  String get volunteerIntro =>
      'Les volontaires aident les équipes de la Protection civile lors des urgences, selon leurs compétences. Votre candidature est examinée avant tout appel.';

  @override
  String get volunteerApply => 'Devenir volontaire';

  @override
  String get volunteerApplication => 'Ma candidature';

  @override
  String get volunteerStatusPending => 'En cours d’examen';

  @override
  String get volunteerStatusApproved => 'Acceptée';

  @override
  String get volunteerStatusRejected => 'Refusée';

  @override
  String get volunteerStatusSuspended => 'Suspendue';

  @override
  String get volunteerStatusWithdrawn => 'Retirée';

  @override
  String get volunteerPendingHelp =>
      'Votre candidature sera examinée par la Protection civile. Vous recevrez la décision par e-mail.';

  @override
  String get volunteerApprovedHelp =>
      'Vous pouvez vous déclarer disponible et recevoir des appels près de chez vous.';

  @override
  String get volunteerRejectedHelp =>
      'Votre candidature n’a pas été acceptée. Vous pouvez la corriger et la soumettre à nouveau.';

  @override
  String get volunteerSuspendedHelp =>
      'Votre volontariat est suspendu : vous ne recevrez pas d’appels.';

  @override
  String get volunteerWithdrawnHelp =>
      'Vous vous êtes retiré. Vous pouvez postuler à nouveau à tout moment.';

  @override
  String volunteerReason(String reason) {
    return 'Motif : $reason';
  }

  @override
  String volunteerPeriodFrom(String from) {
    return 'À partir du $from';
  }

  @override
  String volunteerPeriodRange(String from, String to) {
    return 'Du $from au $to';
  }

  @override
  String get availabilityContinuous => 'Continue';

  @override
  String get availabilityIntermittent => 'Intermittente';

  @override
  String get volunteerEdit => 'Modifier ma candidature';

  @override
  String get volunteerResubmit => 'Postuler à nouveau';

  @override
  String get volunteerWithdraw => 'Me retirer';

  @override
  String get volunteerWithdrawConfirm =>
      'Vous ne recevrez plus d’appels et votre position ne sera plus partagée.';

  @override
  String get volunteerReady => 'Disponible pour intervenir';

  @override
  String get volunteerReadyHelp =>
      'Tant que vous êtes disponible, la Protection civile voit votre position pour vous appeler.';

  @override
  String volunteerReadyUntil(String time) {
    return 'Disponible jusqu’au $time';
  }

  @override
  String get volunteerReadyFor => 'Pendant';

  @override
  String hoursShort(int hours) {
    return '$hours h';
  }

  @override
  String get volunteerLocationPrivacy =>
      'Votre position n’est partagée que pendant votre disponibilité, est effacée à sa fin et n’est jamais archivée.';

  @override
  String get locationConsentTitle =>
      'Partager votre position pendant votre disponibilité ?';

  @override
  String get locationConsentBody =>
      'Pendant votre disponibilité, votre position est transmise à la Protection civile de votre gouvernorat pour qu’elle appelle les volontaires les plus proches d’un incident.\n\n• Qui la voit : les opérateurs de la Protection civile, sur une carte arrondie à environ 100 m ; les distances sont arrondies aussi.\n• Combien de temps : seulement pendant votre disponibilité. Elle est gardée en mémoire, effacée à la fin de la disponibilité et jamais archivée.\n• Vous pouvez retirer ce consentement à tout moment sur cet écran ; la disponibilité prend alors fin aussitôt.';

  @override
  String get locationConsentAccept => 'J’accepte';

  @override
  String get locationConsentSwitch =>
      'Partager ma position pendant ma disponibilité';

  @override
  String get locationConsentSwitchOn =>
      'Consentement donné. Le retirer met fin à la disponibilité et efface votre position.';

  @override
  String get locationConsentSwitchOff => 'Nécessaire pour être disponible.';

  @override
  String get locationConsentWithdrawn =>
      'Consentement retiré : votre position est effacée.';

  @override
  String get volunteerNoFix =>
      'Votre position n’a pas pu être déterminée. Réessayez à l’extérieur.';

  @override
  String get volunteerSkills => 'Compétences';

  @override
  String get volunteerSkillsRequired => 'Choisissez au moins une compétence.';

  @override
  String get volunteerOtherSkill => 'Autre compétence';

  @override
  String get volunteerAvailability => 'Disponibilité';

  @override
  String get volunteerPeriod => 'Période de volontariat';

  @override
  String get volunteerFrom => 'Début';

  @override
  String get volunteerTo => 'Fin';

  @override
  String get volunteerNoEnd => 'Sans date de fin';

  @override
  String get volunteerNotes => 'Remarques (facultatif)';

  @override
  String get volunteerProfileNote =>
      'Vos nom, téléphone et gouvernorat sont repris de votre profil.';

  @override
  String get volunteerSubmit => 'Envoyer ma candidature';

  @override
  String get volunteerSubmitted => 'Candidature envoyée.';

  @override
  String get fieldRequired => 'Obligatoire';

  @override
  String get skillFirstAid => 'Secourisme';

  @override
  String get skillDiving => 'Plongée';

  @override
  String get skillHeavyVehicles => 'Véhicules lourds';

  @override
  String get skillFirefighting => 'Lutte contre l’incendie';

  @override
  String get skillSearchRescue => 'Recherche et sauvetage';

  @override
  String get skillLogistics => 'Logistique';

  @override
  String get skillMedical => 'Médical';

  @override
  String get skillOther => 'Autre';

  @override
  String get calloutsTitle => 'Appels d’intervention';

  @override
  String get calloutsDesc => 'Demandes d’aide près de chez vous.';

  @override
  String get calloutsEmpty => 'Aucun appel pour le moment.';

  @override
  String get calloutAccept => 'J’y vais';

  @override
  String get calloutDecline => 'Indisponible';

  @override
  String get calloutArrived => 'Je suis sur place';

  @override
  String get calloutEtaLabel => 'Arrivée dans (minutes)';

  @override
  String calloutEta(int minutes) {
    return 'Arrivée dans $minutes min';
  }

  @override
  String calloutSkill(String skill) {
    return 'Compétence : $skill';
  }

  @override
  String calloutDistance(String distance) {
    return 'À $distance';
  }

  @override
  String get calloutAnswerSent => 'En attente de réponse';

  @override
  String get calloutAnswerAccepted => 'En route';

  @override
  String get calloutAnswerDeclined => 'Décliné';

  @override
  String get calloutAnswerExpired => 'Expiré';

  @override
  String get calloutAnswerArrived => 'Sur place';

  @override
  String distanceMeters(int meters) {
    return '$meters m';
  }

  @override
  String distanceKm(String km) {
    return '$km km';
  }

  @override
  String get errorRegistrationRequired =>
      'Un compte est nécessaire pour devenir volontaire.';

  @override
  String get errorNotVolunteer => 'Vous n’avez pas postulé comme volontaire.';

  @override
  String get errorProfileIncomplete =>
      'Complétez d’abord votre profil (téléphone et gouvernorat).';

  @override
  String get errorInvalidPeriod =>
      'La période est invalide (fin avant le début ou au-delà de deux ans).';

  @override
  String get errorVolunteerNotApproved =>
      'Votre candidature de volontaire n’est pas acceptée.';

  @override
  String get errorOutsidePeriod =>
      'Aujourd’hui est hors de votre période de volontariat.';

  @override
  String get errorNotReady => 'Vous n’êtes plus disponible.';

  @override
  String get errorLocationRequired =>
      'Votre position est nécessaire pour être disponible.';

  @override
  String get errorLocationConsentRequired =>
      'Acceptez de partager votre position avant d’être disponible.';

  @override
  String get errorCalloutClosed => 'Cet appel est clos.';

  @override
  String get errorEtaRequired => 'Indiquez une durée entre 1 et 600 minutes.';

  @override
  String get errorInvalidTransition => 'Cette action n’est plus possible.';

  @override
  String get errorVersionConflict =>
      'Vos données ont changé entre-temps. Rechargez et réessayez.';

  @override
  String get locationServiceDisabled =>
      'La localisation est désactivée sur ce téléphone.';

  @override
  String get volunteerLocationDenied =>
      'Autorisez l’accès à la localisation pour vous déclarer disponible.';

  @override
  String get actionNotNow => 'Pas maintenant';

  @override
  String get channelCritical => 'Alertes officielles critiques';

  @override
  String get channelCriticalDesc =>
      'Les alertes les plus graves de la protection civile, entendues même en mode Ne pas déranger (seulement si vous l\'avez autorisé).';

  @override
  String get alertCheckTitle => 'Vérifier la réception des alertes';

  @override
  String get alertCheckSubtitle =>
      'Ce qui pourrait empêcher les alertes de vous parvenir';

  @override
  String get alertCheckIntro =>
      'Les alertes officielles ont leur propre son, vibration et canal, séparés des autres applications. Certains réglages du téléphone peuvent tout de même les faire taire : vérifiez-les ici.';

  @override
  String get alertCheckAllGood =>
      'Rien ne bloque les alertes officielles sur ce téléphone.';

  @override
  String get alertCheckFix => 'Corriger';

  @override
  String get alertChannelSettings =>
      'Réglages du son et de la vibration des alertes';

  @override
  String get issueNotificationsOff => 'Les notifications sont désactivées';

  @override
  String get issueNotificationsOffHelp =>
      'Sans notifications, vous ne recevrez ni alertes ni sollicitations.';

  @override
  String get issueChannelMuted => 'Les alertes officielles sont en sourdine';

  @override
  String get issueChannelMutedHelp =>
      'La catégorie « Alertes officielles » a été réduite dans les réglages du téléphone : elle ne sonne plus et ne s\'affiche plus en haut de l\'écran.';

  @override
  String get issueDnd => 'Le mode Ne pas déranger est activé';

  @override
  String get issueDndHelp =>
      'Les alertes peuvent arriver sans son. Vous pouvez laisser passer les alertes officielles les plus graves.';

  @override
  String get issueFullScreen =>
      'Les alertes plein écran ne sont pas autorisées';

  @override
  String get issueFullScreenHelp =>
      'Les alertes les plus graves doivent s\'ouvrir par-dessus l\'écran de verrouillage. Autorisez les « notifications plein écran » pour e-Himaya.';

  @override
  String get issueBatteryOptimized =>
      'L\'optimisation de la batterie peut retarder les sollicitations';

  @override
  String get issueBatteryOptimizedHelp =>
      'Vous êtes de garde : le téléphone peut mettre l\'application en veille et retarder les sollicitations. Exemptez e-Himaya pendant votre volontariat.';

  @override
  String get issuePushUnavailable =>
      'Les notifications push sont indisponibles';

  @override
  String get issuePushUnavailableHelp =>
      'Ce téléphone ne peut pas recevoir de push (par exemple sans services Google) : les alertes ne sont vérifiées que lorsque l\'application est ouverte.';

  @override
  String get testAlertButton => 'Envoyer une alerte de test';

  @override
  String get testAlertTitle => 'Test — alerte officielle';

  @override
  String get testAlertBody =>
      'Voici à quoi ressemble une alerte de la protection civile. Aucune action n\'est nécessaire.';

  @override
  String get testAlertSent => 'Alerte de test envoyée.';

  @override
  String get criticalAlertsTitle => 'Alertes critiques en mode Ne pas déranger';

  @override
  String get criticalAlertsIntro =>
      'Vous pouvez laisser sonner les alertes officielles les plus graves (danger de mort : inondation, incendie, évacuation) même en mode Ne pas déranger.';

  @override
  String get criticalAlertsHow =>
      'Seules les alertes de gravité maximale l\'utilisent. Le téléphone vous demandera d\'accorder à e-Himaya l\'« accès à Ne pas déranger » ; vous pouvez le désactiver ici à tout moment.';

  @override
  String get criticalAlertsEnable => 'Autoriser les alertes critiques';

  @override
  String get criticalAlertsEnabled =>
      'Les alertes critiques peuvent sonner en mode Ne pas déranger.';

  @override
  String get criticalAlertsDisable => 'Désactiver';

  @override
  String get batteryExemptTitle => 'Recevoir les sollicitations à temps';

  @override
  String get batteryExemptBody =>
      'Vous êtes de garde. Pour économiser la batterie, le téléphone peut mettre e-Himaya en veille et livrer les sollicitations en retard. Exempter l\'application de l\'optimisation de la batterie l\'évite ; e-Himaya n\'utilise la localisation que lorsqu\'elle est ouverte et que vous êtes disponible.';

  @override
  String get batteryExemptAllow => 'Exempter l\'application';

  @override
  String get batterySaverTitle => 'Économiseur de batterie';

  @override
  String get batterySaverHelp =>
      'Vérifie moins souvent les mises à jour, partage moins souvent votre position de volontaire et garde les grandes vidéos pour le Wi-Fi. Les alertes et les SOS ne sont jamais retardés.';

  @override
  String get batterySaverAuto => 'Automatique (batterie faible)';

  @override
  String get batterySaverOn => 'Toujours activé';

  @override
  String get batterySaverOff => 'Désactivé';

  @override
  String get batterySaverActive => 'actif';

  @override
  String get batterySaverInactive => 'inactif';

  @override
  String batteryLevel(int percent) {
    return 'batterie $percent %';
  }

  @override
  String get pushCalloutTitle => 'Sollicitation';

  @override
  String get pushOpenToSee => 'Ouvrez l\'application pour voir le détail.';

  @override
  String pushReportTitle(String code) {
    return 'Signalement $code';
  }

  @override
  String get myDataTitle => 'Mes données';

  @override
  String get myDataSubtitle =>
      'Télécharger une copie ou supprimer votre compte';

  @override
  String get myDataIntro =>
      'Vous pouvez obtenir une copie de toutes les données personnelles qu\'e-Himaya détient sur vous (profil, consentements, signalements, dossier de volontaire, appareils), au plus 3 fois par jour. Gardez ce fichier privé : il contient des données personnelles.';

  @override
  String get myDataDownload => 'Télécharger mes données';

  @override
  String get myDataCopy => 'Copier';

  @override
  String get myDataCopied => 'Copié dans le presse-papiers.';

  @override
  String get myDataSave => 'Enregistrer le fichier';

  @override
  String myDataSaved(String path) {
    return 'Enregistré : $path';
  }

  @override
  String get myDataSaveFailed => 'Le fichier n\'a pas pu être enregistré.';

  @override
  String get deleteAccountTitle => 'Supprimer mon compte';

  @override
  String get deleteAccountSubtitle =>
      'Vos données personnelles sont effacées ; c\'est irréversible.';

  @override
  String get deleteAccountExplain =>
      'Votre profil, vos consentements, vos appareils et votre dossier de volontaire sont effacés et votre compte est fermé. Les signalements envoyés sont conservés sans votre nom, comme l\'exige la loi. Tout ce qui est stocké sur ce téléphone est effacé et l\'application recommence depuis le début.';

  @override
  String get deleteAccountExplainAnonymous =>
      'L\'identité anonyme de ce téléphone est supprimée sur le serveur. Les signalements envoyés sont conservés sans lien avec ce téléphone, comme l\'exige la loi. Tout ce qui est stocké sur ce téléphone est effacé et l\'application recommence depuis le début.';

  @override
  String get deleteAccountWord => 'SUPPRIMER';

  @override
  String deleteAccountTypeWord(String word) {
    return 'Tapez $word pour confirmer';
  }

  @override
  String get deleteAccountConfirm => 'Supprimer définitivement';

  @override
  String get deleteAccountDone => 'Votre compte a été supprimé.';

  @override
  String get deleteAccountLastAdmin =>
      'Vous êtes le dernier administrateur d\'une institution. Confiez d\'abord l\'administration à un autre membre, puis supprimez votre compte.';

  @override
  String get lockedAlertOpenApp => 'Déverrouiller pour ouvrir l\'application';

  @override
  String get liveBadge => 'EN DIRECT';

  @override
  String get homeLive => 'Direct vidéo';

  @override
  String get homeLiveDesc =>
      'Filmez l’incident en direct pour la Protection civile.';

  @override
  String get liveTitle => 'Diffusion en direct';

  @override
  String get liveIntro =>
      'L’image de la caméra et le son du micro sont transmis en direct à la salle des opérations de la Protection civile, enregistrés et liés à votre signalement. Votre position est envoyée pendant toute la diffusion.';

  @override
  String get livePermissionRationale =>
      'La diffusion a besoin de la caméra, du micro et de votre position. Le téléphone vous demandera l’autorisation au démarrage ; ils ne servent que pendant la diffusion.';

  @override
  String get liveCategoryLabel => 'Type d’incident';

  @override
  String get liveStart => 'Démarrer le direct';

  @override
  String get liveStop => 'Arrêter le direct';

  @override
  String get liveMute => 'Couper le micro';

  @override
  String get liveUnmute => 'Activer le micro';

  @override
  String get liveSwitchCamera => 'Changer de caméra';

  @override
  String get livePreparing => 'Préparation du direct…';

  @override
  String get liveConnecting => 'Connexion au serveur vidéo…';

  @override
  String liveReconnecting(int attempt, int max) {
    return 'Connexion perdue. Tentative $attempt sur $max…';
  }

  @override
  String get liveWeakNetwork =>
      'Le réseau est trop faible pour le direct. Vous pouvez enregistrer un court clip et l’envoyer à la place.';

  @override
  String get liveLocationOff =>
      'Localisation désactivée : votre position n’est pas envoyée pendant le direct.';

  @override
  String get liveLocationOn => 'Position envoyée pendant le direct';

  @override
  String liveEndsIn(String time) {
    return 'Le direct s’arrête automatiquement dans $time';
  }

  @override
  String liveReportCode(String code) {
    return 'Signalement $code';
  }

  @override
  String liveSemanticsOnAir(String duration) {
    return 'Direct en cours depuis $duration';
  }

  @override
  String get liveEndedTitle => 'Direct terminé';

  @override
  String get liveEndedByUser =>
      'Vous avez arrêté le direct. L’enregistrement est conservé avec votre signalement.';

  @override
  String get liveEndedByOperator =>
      'L’opérateur a mis fin au direct. Merci, les images sont bien arrivées.';

  @override
  String liveEndedMaxDuration(int minutes) {
    return 'Le direct a atteint sa durée maximale ($minutes min).';
  }

  @override
  String get liveEndedByServer => 'La plateforme a mis fin au direct.';

  @override
  String get liveEndedLocked =>
      'Le direct s’est arrêté car le téléphone est revenu à l’écran verrouillé.';

  @override
  String liveDuration(String duration) {
    return 'Durée : $duration';
  }

  @override
  String get liveFailedTitle => 'Direct impossible';

  @override
  String get liveFailNoLocation =>
      'Votre position est introuvable, le signalement ne peut pas être créé. Appelez le 198.';

  @override
  String get liveFailReportNotSent =>
      'Votre signalement est enregistré sur le téléphone et partira dès le retour du réseau. Vous pouvez enregistrer un clip qui y sera joint.';

  @override
  String get liveFailPermission =>
      'L’accès à la caméra ou au micro a été refusé. Autorisez-le dans les réglages du téléphone pour diffuser.';

  @override
  String get liveFailCamera =>
      'La caméra n’est pas disponible (une autre application l’utilise peut-être).';

  @override
  String get liveFailConnection =>
      'Impossible de joindre le serveur vidéo malgré plusieurs tentatives.';

  @override
  String get liveFailLocked =>
      'Le direct n’est pas disponible depuis l’alerte sur écran verrouillé. Déverrouillez d’abord le téléphone.';

  @override
  String get liveFallbackTitle => 'Envoyer un clip vidéo à la place';

  @override
  String get liveFallbackBody =>
      'Enregistrez un clip de 60 secondes au plus : il est envoyé automatiquement avec votre signalement, même sur un réseau faible.';

  @override
  String get liveRecordClip => 'Enregistrer un clip (60 s)';

  @override
  String get liveClipQueued =>
      'Le clip est enregistré et sera envoyé avec votre signalement.';

  @override
  String get liveClipFailed => 'Le clip n’a pas pu être enregistré.';

  @override
  String get liveRetry => 'Réessayer';

  @override
  String get liveOpenSettings => 'Ouvrir les réglages';

  @override
  String get liveDone => 'Terminé';

  @override
  String get liveLeaveTitle => 'Arrêter le direct ?';

  @override
  String get liveLeaveBody =>
      'Le direct est en cours. Quitter arrête l’envoi de l’image et de la position.';

  @override
  String get liveSimulationBadge => 'Mode simulation';

  @override
  String get liveSimulationHelp =>
      'Ce direct passe par la plateforme de simulation et n’atteint aucune vraie salle des opérations.';

  @override
  String get reportGoLive => 'Direct pour ce signalement';

  @override
  String get errorStreamAlreadyActive =>
      'Un direct est déjà en cours pour ce signalement.';

  @override
  String get errorStreamNotActive => 'Ce direct est terminé.';

  @override
  String get errorReportClosed =>
      'Ce signalement est clôturé : impossible d’y ouvrir un direct.';

  @override
  String get weatherTitle => 'Météo près de vous';

  @override
  String get weatherLoading => 'Chargement de la météo…';

  @override
  String get weatherNoLocation =>
      'Autorisez l’accès à la position pour voir la météo là où vous êtes.';

  @override
  String get weatherUseLocation => 'Utiliser ma position';

  @override
  String get weatherOutsideCoverage =>
      'Les prévisions météo ne couvrent que la Tunisie.';

  @override
  String get weatherOffline =>
      'Pas d’internet : la météo s’affichera au retour de la connexion.';

  @override
  String get weatherUnavailable => 'La météo n’a pas pu être chargée.';

  @override
  String get weatherRetry => 'Réessayer';

  @override
  String get weatherNotRefreshed =>
      'Non actualisée : dernières données reçues.';

  @override
  String weatherUpdated(String time) {
    return 'Mise à jour $time';
  }

  @override
  String weatherCachedAt(String time) {
    return 'Copie hors ligne du $time';
  }

  @override
  String get weatherNow => 'Maintenant';

  @override
  String get weatherNextHours => 'Prochaines heures';

  @override
  String weatherTemperature(String value) {
    return '$value °C';
  }

  @override
  String weatherWind(String speed) {
    return 'Vent $speed km/h';
  }

  @override
  String weatherGusts(String speed) {
    return 'rafales $speed km/h';
  }

  @override
  String weatherHumidity(String value) {
    return 'Humidité $value %';
  }

  @override
  String weatherRain(String value) {
    return 'Pluie $value mm/h';
  }

  @override
  String weatherRain24h(String value) {
    return '$value mm sur 24 h';
  }

  @override
  String weatherFireDanger(String level) {
    return 'Danger d’incendie : $level';
  }

  @override
  String get weatherFireLow => 'faible';

  @override
  String get weatherFireModerate => 'modéré';

  @override
  String get weatherFireHigh => 'élevé';

  @override
  String get weatherFireVeryHigh => 'très élevé';

  @override
  String get weatherFireExtreme => 'extrême';

  @override
  String weatherHeavyRain(String level) {
    return 'Fortes pluies : $level';
  }

  @override
  String get weatherRainWatch => 'vigilance';

  @override
  String get weatherRainWarning => 'alerte';

  @override
  String get weatherCondClear => 'Ciel dégagé';

  @override
  String get weatherCondCloudy => 'Nuageux';

  @override
  String get weatherCondFog => 'Brouillard';

  @override
  String get weatherCondRain => 'Pluie';

  @override
  String get weatherCondSnow => 'Neige';

  @override
  String get weatherCondStorm => 'Orage';

  @override
  String get weatherAlertsTitle => 'Alertes météo en vigueur';

  @override
  String weatherSource(String source) {
    return 'Données : $source';
  }

  @override
  String get weatherSimulationBadge => 'Mode simulation';

  @override
  String get weatherSimulationHelp =>
      'Ces valeurs météo sont simulées, ce ne sont pas des mesures réelles.';

  @override
  String get offlineFallbackTitle => 'Pas de connexion internet';

  @override
  String get offlineFallbackBody =>
      'Votre signalement est enregistré sur le téléphone et sera envoyé automatiquement au retour d’internet. Pour alerter la protection civile dès maintenant :';

  @override
  String get offlineSendSms => 'Envoyer par SMS';

  @override
  String get offlineSmsHelp =>
      'Ouvre votre application SMS avec un court message (type et position du signalement). C’est vous qui appuyez sur Envoyer.';

  @override
  String get offlineSmsFee =>
      'Votre opérateur peut facturer le prix d’un SMS normal.';

  @override
  String get offlineSmsFailed =>
      'L’application SMS n’a pas pu être ouverte. Appelez le 198.';

  @override
  String get rewardsTitle => 'Mes récompenses';

  @override
  String get homeRewardsDesc =>
      'Points, badges et certificats obtenus grâce aux signalements utiles.';

  @override
  String get rewardsBalanceLabel => 'Solde de points';

  @override
  String get rewardsNoBadge => 'Pas encore de badge';

  @override
  String rewardsCurrentBadge(String badge) {
    return 'Badge actuel : $badge';
  }

  @override
  String rewardsNextBadge(String badge, int points) {
    return 'Prochain badge, $badge : encore $points points';
  }

  @override
  String get rewardsTopBadge =>
      'Vous avez le badge le plus élevé. Merci pour votre vigilance.';

  @override
  String get rewardsConfirmNote =>
      'Les badges argent, or et ambassadeur apparaissent après confirmation par un agent de la protection civile.';

  @override
  String get badgeBronze => 'Bronze';

  @override
  String get badgeSilver => 'Argent';

  @override
  String get badgeGold => 'Or';

  @override
  String get badgeAmbassador => 'Ambassadeur';

  @override
  String get rewardsPausedTitle => 'Points suspendus';

  @override
  String get rewardsPausedBody =>
      'Un niveau de catastrophe est en vigueur. Les nouveaux points sont conservés et seront ajoutés quand le niveau baissera.';

  @override
  String rewardsPendingPoints(int points) {
    return 'Points en attente : $points';
  }

  @override
  String get rewardsHistoryTitle => 'Historique';

  @override
  String get rewardsHistoryEmpty =>
      'Pas encore de points. Ils sont ajoutés quand un de vos signalements est vérifié puis clôturé.';

  @override
  String get rewardsShowMore => 'Afficher plus';

  @override
  String get pointsReasonReportVerified => 'Signalement vérifié';

  @override
  String get pointsReasonHelpedRescue => 'Signalement ayant aidé un sauvetage';

  @override
  String get pointsReasonAccurateCategory => 'Bonne catégorie choisie';

  @override
  String get pointsReasonVolunteerMission => 'Mission bénévole accomplie';

  @override
  String get pointsReasonManual => 'Ajustement par la protection civile';

  @override
  String get pointsReasonRevocation => 'Points retirés';

  @override
  String get pointsReasonOther => 'Autre';

  @override
  String get rewardsCapped => 'plafond journalier atteint';

  @override
  String rewardsDailyCap(int points) {
    return 'Au plus $points points peuvent être gagnés par jour.';
  }

  @override
  String get rewardsCertificatesTitle => 'Certificats';

  @override
  String get rewardsCertificatesEmpty => 'Pas encore de certificat.';

  @override
  String rewardsCertificateYear(String year) {
    return 'Année $year';
  }

  @override
  String get distinctionVigilantCitizen => 'Citoyen vigilant';

  @override
  String get distinctionBraveVolunteer => 'Bénévole courageux';

  @override
  String get distinctionLeadingInstitution => 'Institution exemplaire';

  @override
  String distinctionBadge(String badge) {
    return 'Badge $badge';
  }

  @override
  String get distinctionOther => 'Distinction';

  @override
  String get rewardsOpenPdf => 'Ouvrir le certificat PDF';

  @override
  String get rewardsPdfNoViewer =>
      'Aucune application de ce téléphone ne peut ouvrir le PDF.';

  @override
  String get rewardsAnonymousTitle =>
      'Les signalements anonymes ne rapportent pas de points';

  @override
  String get rewardsAnonymousBody =>
      'Un signalement envoyé sans compte ne peut être rattaché à personne : il ne rapporte ni points, ni badges, ni certificats. Créez un compte pour participer ; les signalements déjà envoyés anonymement restent anonymes.';

  @override
  String get rewardsSafetyNotice =>
      'Ne vous mettez jamais en danger pour signaler. Votre sécurité passe avant tout : en cas d’urgence, appelez le 198.';

  @override
  String get rewardsPrizesNotice =>
      'Les points, badges et certificats sont une reconnaissance publique, pas de l’argent. Tout prix annuel est soumis à une décision de l’autorité compétente.';

  @override
  String rewardsOfflineCopy(String date) {
    return 'Hors ligne : copie enregistrée le $date.';
  }

  @override
  String get rewardsHowTitle => 'Comment gagner des points';

  @override
  String get rewardsHowBody =>
      'Des points sont ajoutés quand un de vos signalements est vérifié puis clôturé, davantage s’il a aidé un sauvetage ou si vous avez choisi la bonne catégorie, et pour chaque mission bénévole accomplie. Aucun point pour un signalement faux ou rejeté.';

  @override
  String trackPointsEarned(int points) {
    return 'Points obtenus grâce à ce signalement : $points';
  }

  @override
  String get trackPointsOpenRewards => 'Voir mes récompenses';

  @override
  String get anonQuotaCardTitle => 'Signalements sans compte';

  @override
  String anonQuotaRemaining(int remaining, int limit) {
    return 'Encore $remaining sur $limit';
  }

  @override
  String anonQuotaRemainingShort(int remaining) {
    return 'Encore $remaining';
  }

  @override
  String get anonQuotaExhaustedHint =>
      'Limite atteinte : créez un compte pour continuer à signaler. Le SOS et le 198 fonctionnent toujours.';

  @override
  String get anonQuotaTitle => 'Signaler sans compte';

  @override
  String get anonQuotaExplanation =>
      'Pour éviter les abus, chaque installation de l’application peut envoyer un nombre limité de signalements sans compte. Avec un compte gratuit, vous continuez à signaler, vous suivez vos signalements sur tout appareil et ils ont plus de poids.';

  @override
  String get anonQuotaEmergencyNote =>
      'En cas d’urgence, le bouton SOS et l’appel au 198 fonctionnent toujours, avec ou sans compte.';

  @override
  String anonQuotaDraftKept(String code) {
    return 'Votre signalement $code est conservé sur ce téléphone. Il sera envoyé dès que vous créerez un compte ou vous connecterez.';
  }

  @override
  String get anonQuotaReportKeptBody =>
      'La limite de signalements sans compte est atteinte. Ce signalement est conservé sur ce téléphone et sera envoyé dès que vous créerez un compte ou vous connecterez.';

  @override
  String get anonQuotaOpen => 'Pourquoi une limite ?';

  @override
  String get errorAnonQuotaExhausted =>
      'La limite de signalements sans compte est atteinte sur cet appareil. Veuillez créer un compte.';

  @override
  String get intro1Title => 'Bienvenue sur e-Himaya';

  @override
  String get intro1Body =>
      'e-Himaya détermine votre position grâce à votre téléphone. En cas d\'urgence, il l\'envoie avec votre signalement directement à la salle des opérations compétente de la Protection civile, pour que les secours arrivent plus vite et avec les moyens adaptés.';

  @override
  String get intro2Title =>
      'Sous l\'égide de l\'Office National de la Protection Civile';

  @override
  String get intro2Body =>
      'Cette application est fournie par l\'Office National de la Protection Civile, établissement public chargé du secours, du sauvetage, de la lutte contre les incendies et de la gestion des catastrophes sur tout le territoire tunisien, qui reçoit les appels du 198.';

  @override
  String get intro3Title => 'Quand l\'utiliser ?';

  @override
  String get intro3Body =>
      'Incendie, accident de la circulation, personne en danger ou blessée, noyade, effondrement, fuite de gaz, inondation, ou toute situation menaçant des vies ou des biens et nécessitant l\'intervention de la Protection civile.';

  @override
  String get intro4Title => 'Comment ça marche ?';

  @override
  String get intro4Body =>
      'Choisissez le type d\'incident, prenez si possible une photo, une vidéo ou un message vocal sans vous mettre en danger, puis envoyez. Votre signalement et votre position parviennent immédiatement à l\'opérateur ; vous suivez son traitement étape par étape et l\'opérateur peut vous rappeler. Sans Internet, le signalement part par SMS, et l\'appel au 198 reste disponible à tout moment.';

  @override
  String get intro5Title => 'Où fonctionne-t-elle ?';

  @override
  String get intro5Body =>
      'Sur tout le territoire de la République tunisienne, dans les 24 gouvernorats ; votre signalement est orienté automatiquement vers la direction régionale compétente. Hors de Tunisie, appelez le numéro d\'urgence local (le 112 dans la plupart des pays).';

  @override
  String get terms1Title => '1. Objet';

  @override
  String get terms1Body =>
      'e-Himaya est une plateforme numérique de l\'Office National de la Protection Civile (« l\'Office ») pour signaler les situations d\'urgence et en suivre le traitement. Les présentes conditions régissent la relation entre l\'Office et les utilisateurs de l\'application mobile et du portail des établissements.';

  @override
  String get terms2Title => '2. Notre mission';

  @override
  String get terms2Body =>
      'Protéger les vies et les biens, et rétablir la confiance entre les citoyens et la Protection civile par une communication directe et transparente. Décrire l\'incident avec précision et montrer la scène telle qu\'elle est réduit le délai d\'intervention et en améliore l\'efficacité.';

  @override
  String get terms3Title => '3. Nature et limites du service';

  @override
  String get terms3Body =>
      '3.1 L\'application complète le 198 et ne le remplace pas. En cas de danger immédiat, appelez directement le 198.\n3.2 L\'application ne fournit aucun avis médical ; ses conseils sont donnés à titre de sensibilisation et ne remplacent pas les consignes des agents de la Protection civile.\n3.3 Son fonctionnement dépend de facteurs hors du contrôle de l\'Office : couverture du réseau mobile et d\'Internet, signal de localisation, batterie et état du téléphone. L\'Office s\'efforce d\'assurer la meilleure disponibilité et de corriger les dysfonctionnements dans les meilleurs délais.';

  @override
  String get terms4Title => '4. Obligations de l\'utilisateur';

  @override
  String get terms4Body =>
      '4.1 Utiliser l\'application de bonne foi et uniquement pour de vraies urgences ; fournir des informations exactes et à jour, notamment le numéro de téléphone.\n4.2 Laisser la localisation activée et utiliser la dernière version de l\'application.\n4.3 Ne pas se mettre en danger pour filmer et respecter les consignes des intervenants.\n4.4 Ne pas porter atteinte à l\'application, la perturber, contourner ses protections ni en faire de l\'ingénierie inverse.';

  @override
  String get terms5Title => '5. Fausses alertes et usage abusif';

  @override
  String get terms5Body =>
      'Chaque signalement mobilise des équipes de secours dont d\'autres vies peuvent avoir besoin au même moment. Toute fausse alerte volontaire ou tout usage abusif expose son auteur à des poursuites conformément à la législation tunisienne en vigueur, et peut entraîner la suspension temporaire ou définitive du compte ou du signalement depuis l\'appareil concerné.';

  @override
  String get terms6Title => '6. Obligations des établissements';

  @override
  String get terms6Body =>
      'L\'établissement inscrit fournit des informations exactes et à jour sur son identité, son activité, ses bâtiments et ses responsables, et en répond. Le dépôt et la mise à jour du plan d\'évacuation et des plans du bâtiment facilitent l\'intervention et réduisent le temps de recherche et de sauvetage. Le compte n\'est activé qu\'après validation par l\'Office.';

  @override
  String get terms7Title => '7. Volontaires';

  @override
  String get terms7Body =>
      'Le statut de volontaire n\'est accordé qu\'après validation par l\'Office. Le volontaire suit les instructions de la salle des opérations et n\'intervient que dans la limite de la mission confiée.';

  @override
  String get terms8Title => '8. Protection des données personnelles';

  @override
  String get terms8Body =>
      '8.1 Les données personnelles sont traitées conformément à la loi organique n° 2004-63 du 27 juillet 2004 portant sur la protection des données à caractère personnel, sous le contrôle de l\'Instance Nationale de Protection des Données Personnelles (INPDP), dans le seul but de traiter les urgences et de vous informer du suivi de vos signalements.\n8.2 Lors d\'un signalement sont transmis à l\'Office : votre position, le type d\'incident, la description et les médias joints, et les données de votre compte le cas échéant.\n8.3 Les contacts d\'urgence et le texte du message de détresse sont conservés chiffrés sur votre téléphone uniquement et ne sont pas transmis à l\'Office.\n8.4 Le signalement sans compte est possible sous pseudonyme, sans enregistrement de l\'adresse IP.\n8.5 Seuls les agents habilités accèdent aux données, conservées pendant la durée nécessaire au traitement et aux obligations légales. Vous disposez d\'un droit d\'accès, de rectification et d\'opposition.';

  @override
  String get terms9Title => '9. Évolution de l\'application et des conditions';

  @override
  String get terms9Body =>
      'L\'Office peut faire évoluer l\'application ou modifier ces conditions. L\'utilisateur est informé de chaque nouvelle version et de son contenu, et son accord est de nouveau demandé lorsque les conditions changent.';

  @override
  String get terms10Title => '10. Droit applicable';

  @override
  String get terms10Body =>
      'Les présentes conditions sont régies par le droit tunisien ; les tribunaux tunisiens sont compétents pour tout litige.';

  @override
  String get languageTitle => 'Choisissez votre langue';

  @override
  String get languageSubtitle =>
      'Vous pouvez la changer à tout moment avec la barre de langue en haut de chaque écran.';

  @override
  String get languageMenuTooltip => 'Langue';

  @override
  String get introSkip => 'Passer';

  @override
  String introPage(int current, int total) {
    return 'Page $current sur $total';
  }

  @override
  String get call198 => 'Appeler le 198';

  @override
  String get termsScrollHint =>
      'Faites défiler jusqu\'à la fin des conditions pour les accepter.';

  @override
  String get termsAccept => 'J\'accepte';

  @override
  String get termsDecline => 'Je refuse';

  @override
  String get termsDeclinedTitle => 'Conditions non acceptées';

  @override
  String get termsDeclinedBody =>
      'Sans accepter les conditions vous ne pouvez pas utiliser l\'application, mais l\'appel au 198 reste toujours disponible.';

  @override
  String get termsReadAgain => 'Lire les conditions';

  @override
  String get permissionsTitle => 'Autorisations';

  @override
  String get permissionsIntro =>
      'e-Himaya ne demande que ce qui est nécessaire pour vous aider. Vous pourrez changer ces choix dans les réglages du téléphone.';

  @override
  String get permLocationTitle => 'Localisation';

  @override
  String get permLocationBody =>
      'Envoyée avec votre signalement pour que les secours vous trouvent. Sans elle, il faudra décrire le lieu et les secours risquent d\'arriver plus tard.';

  @override
  String get permNotificationsTitle => 'Notifications';

  @override
  String get permNotificationsBody =>
      'Suivi de vos signalements et alertes publiques près de vous. Sans elles, vous ne serez pas prévenu d\'un danger dans votre zone.';

  @override
  String get permSmsTitle => 'SMS';

  @override
  String get permSmsBody =>
      'Sans Internet, votre signalement part par SMS. Aucune autorisation n\'est nécessaire : l\'application ouvre un message prêt que vous envoyez vous-même.';

  @override
  String get permContactsTitle => 'Contacts';

  @override
  String get permContactsBody =>
      'Demandés seulement quand vous choisirez un contact d\'urgence, plus tard.';

  @override
  String get permAllow => 'Autoriser';

  @override
  String get permAllowed => 'Autorisé';

  @override
  String get permRefused =>
      'Refusé : vous pouvez l\'autoriser dans les réglages';

  @override
  String get permNoneNeeded => 'Aucune autorisation nécessaire';

  @override
  String get permLater => 'Plus tard';

  @override
  String get signInTitle => 'Connexion';

  @override
  String get signInIntro =>
      'Connectez-vous avec votre numéro de mobile : nous vous envoyons un code par SMS. Pas de mot de passe.';

  @override
  String get signInPhoneLabel => 'Numéro de mobile';

  @override
  String get signInPhoneHint => '8 chiffres';

  @override
  String get signInPhoneInvalid =>
      'Saisissez un numéro mobile tunisien : 8 chiffres commençant par 2, 3, 4, 5 ou 9.';

  @override
  String get signInSendCode => 'Envoyer le code';

  @override
  String get signInCodeLabel => 'Code reçu par SMS';

  @override
  String signInCodeSentTo(String phone) {
    return 'Un code à 6 chiffres a été envoyé au $phone.';
  }

  @override
  String get signInVerify => 'Se connecter';

  @override
  String signInResendIn(int seconds) {
    return 'Renvoyer le code dans $seconds s';
  }

  @override
  String get signInResend => 'Renvoyer le code';

  @override
  String get signInChangeNumber => 'Changer de numéro';

  @override
  String signInWrongCode(int tries) {
    return 'Code erroné. Essais restants : $tries.';
  }

  @override
  String get signInCodeExpired =>
      'Le code a expiré ou est épuisé. Demandez-en un nouveau.';

  @override
  String get signInTooSoon =>
      'Patientez une minute avant de demander un nouveau code.';

  @override
  String get signInLimit =>
      'Trop de codes pour ce numéro. Réessayez dans une heure.';

  @override
  String get signInSmsUnavailable =>
      'Le SMS n\'a pas pu être envoyé. Réessayez ou continuez en invité.';

  @override
  String get signInNetworkError =>
      'Pas de connexion. Vérifiez Internet et réessayez.';

  @override
  String get signInGuest => 'Continuer en invité';

  @override
  String get signInGuestDesc =>
      'Signaler sans compte (nombre de signalements limité).';

  @override
  String get signInInstitution => 'Compte établissement';

  @override
  String get signInInstitutionDesc =>
      'Pour les entreprises, écoles, hôtels et administrations.';

  @override
  String get signInEmail => 'Se connecter avec e-mail et mot de passe';

  @override
  String get signInPrivacyNote =>
      'Votre numéro sert uniquement à vous joindre au sujet de vos signalements.';

  @override
  String get simBanner =>
      '[SIM] Simulation : le SMS part vers la passerelle de test (notify-sim), pas vers un vrai téléphone.';

  @override
  String get homeSubtitle => 'Protection civile tunisienne';

  @override
  String get homeReportCardTitle => 'Signaler un incident';

  @override
  String get homeReportCardDesc =>
      'Photo, voix ou texte, avec votre position automatiquement';

  @override
  String get homeNumbersOffline => 'Fonctionnent sans Internet';

  @override
  String get homeShortcuts => 'Raccourcis';

  @override
  String get homeMyReports => 'Mes signalements';

  @override
  String get homeSosMessage => 'Message de détresse';

  @override
  String get homeCall198 => 'Appel d\'urgence 198';

  @override
  String get locationOn => 'Localisation activée';

  @override
  String get locationOff =>
      'Localisation désactivée : les secours risquent de mettre plus de temps à vous trouver.';

  @override
  String get locationTurnOn => 'Activer';

  @override
  String get locationChecking => 'Vérification de la localisation…';

  @override
  String get themeToggleTooltip => 'Clair ou sombre';

  @override
  String get settingsColors => 'Couleurs';

  @override
  String get colorOffice => 'Protection civile (logo)';

  @override
  String get colorRed => 'Rouge';

  @override
  String get colorBlue => 'Bleu';

  @override
  String get colorGreen => 'Vert';

  @override
  String get updateTitle => 'Une nouvelle version est disponible';

  @override
  String get updateMandatoryTitle => 'Mise à jour obligatoire';

  @override
  String get updateMandatoryBody =>
      'Cette version n\'est plus prise en charge. Mettez à jour pour continuer à utiliser e-Himaya. Les numéros d\'urgence restent disponibles.';

  @override
  String updateWhatsNew(String version) {
    return 'Nouveautés de la version $version';
  }

  @override
  String get updateDataKept => 'Vos signalements et réglages sont conservés.';

  @override
  String get updateNow => 'Mettre à jour';

  @override
  String get updateLater => 'Plus tard';

  @override
  String get updateOpenFailed =>
      'La page de téléchargement n\'a pas pu être ouverte.';

  @override
  String get requiredNote => 'Les champs marqués * sont obligatoires.';

  @override
  String get requiredSemantics => 'obligatoire';

  @override
  String get errorOffensiveText =>
      'Ce texte contient des mots interdits. Merci de le reformuler.';

  @override
  String get guideTitle => 'Guide des urgences';

  @override
  String get guideHubHint =>
      'Incendies, fractures, premiers secours, problèmes respiratoires… Disponible sans connexion.';

  @override
  String get guideIntro =>
      'Choisissez un thème, puis la situation. En attendant les secours, suivez les étapes dans l’ordre.';

  @override
  String guideItemsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count éléments',
      one: '1 élément',
      zero: 'Aucun élément',
    );
    return '$_temp0';
  }

  @override
  String get guideEmpty => 'Rien n’est publié ici pour le moment.';

  @override
  String get guideCallNow => 'Appelez tout de suite le 198 si';

  @override
  String get guideSteps => 'Que faire';

  @override
  String get guideDont => 'À ne pas faire';

  @override
  String get guideCall198 => 'Appeler la Protection civile, 198';

  @override
  String get guideSimBanner =>
      '[SIM] Contenu en attente de validation par le service médical de la Protection civile. Appelez d’abord le 198.';

  @override
  String get guideSimTag => '[SIM] en attente de validation médicale';

  @override
  String get nearestTitle => 'Le plus proche de moi';

  @override
  String get nearestHint =>
      'Centres de la Protection civile, hôpitaux, pharmacies… et vos coordonnées. Fonctionne sans connexion une fois téléchargé.';

  @override
  String get nearestMyPosition => 'Ma position';

  @override
  String get nearestNoLocation =>
      'La localisation est coupée ou refusée. Activez-la pour voir les lieux les plus proches.';

  @override
  String get nearestCopy => 'Copier';

  @override
  String get nearestCopied =>
      'Coordonnées copiées. Vous pouvez les lire à l’opérateur.';

  @override
  String get nearestOffline =>
      'Pas de connexion : copie enregistrée sur ce téléphone.';

  @override
  String get nearestEmpty =>
      'Rien n’est encore enregistré sur ce téléphone. Connectez-vous une fois pour télécharger les lieux.';

  @override
  String get nearestLoading =>
      'Téléchargement des lieux pour l’usage hors connexion…';

  @override
  String nearestUpdated(String date) {
    return 'Lieux mis à jour le $date';
  }

  @override
  String get nearestToVerify => 'À vérifier';

  @override
  String get nearestSimBanner =>
      '[SIM] Certains de ces lieux sont fictifs et approximatifs, pour un essai : ce ne sont pas des lieux réels. En cas d’urgence, appelez le 198.';

  @override
  String get nearestSimChip => '[SIM] Essai';

  @override
  String get nearestNeedPosition => 'En attente de votre position.';

  @override
  String get nearestNone => 'Aucun lieu de ce type n’est encore répertorié.';

  @override
  String nearestSource(String source) {
    return 'Source : $source';
  }

  @override
  String nearestCall(String phone) {
    return 'Appeler le $phone';
  }

  @override
  String get nearestRoute => 'Itinéraire';

  @override
  String get contactTitle => 'Nous contacter';

  @override
  String get contactMineTitle => 'Mes demandes';

  @override
  String get contactEmergencyBanner =>
      'Pas pour les urgences. En cas d’urgence, appelez le 198.';

  @override
  String get contactIntro =>
      'Posez une question, demandez une information détenue par la Protection civile, signalez un danger non urgent, proposez une idée ou signalez un problème de l’application. Vous recevez un numéro pour suivre votre demande.';

  @override
  String get contactKind => 'Type de demande';

  @override
  String get contactKindAccessInfo => 'Accès à l’information (loi 2016-22)';

  @override
  String get contactKindHazard => 'Danger non urgent';

  @override
  String get contactKindQuestion => 'Question';

  @override
  String get contactKindSuggestion => 'Suggestion';

  @override
  String get contactKindAppProblem => 'Problème de l’application';

  @override
  String get contactKindPartnership => 'Partenariat';

  @override
  String get contactAccessInfoHint =>
      'La loi demande votre nom. L’Office répond dans le délai légal (20 jours).';

  @override
  String get contactNoGouvernorat => 'Pas lié à un gouvernorat';

  @override
  String get contactSubject => 'Objet';

  @override
  String get contactMessage => 'Votre message';

  @override
  String get contactDetailsHint =>
      'Les coordonnées sont facultatives : sans elles, la réponse s’affiche seulement ici, dans « Mes demandes ».';

  @override
  String get contactName => 'Nom et prénom';

  @override
  String get contactEmail => 'E-mail';

  @override
  String get contactEmailInvalid => 'Saisissez une adresse e-mail valide.';

  @override
  String contactLength(int min, int max) {
    return 'Entre $min et $max caractères.';
  }

  @override
  String get contactSend => 'Envoyer';

  @override
  String get contactSentTitle => 'Demande envoyée';

  @override
  String get contactSentBody => 'Gardez ce numéro pour suivre votre demande :';

  @override
  String get contactSeeMine => 'Voir mes demandes';

  @override
  String get contactMineEmpty => 'Vous n’avez encore envoyé aucune demande.';

  @override
  String get contactStatusReceived => 'Reçue';

  @override
  String get contactStatusInProgress => 'En cours';

  @override
  String get contactStatusAnswered => 'Répondue';

  @override
  String get contactStatusClosed => 'Clôturée';

  @override
  String get contactStatusRejected => 'Rejetée';

  @override
  String contactDue(String date) {
    return 'Réponse attendue avant le $date';
  }

  @override
  String get contactAnswer => 'Réponse de l’Office';

  @override
  String get contactRejectReason => 'Motif communiqué par l’Office';

  @override
  String get errorFeatureOff => 'Cette fonction n\'est pas encore disponible.';

  @override
  String get errorAlreadyLinked => 'Vous êtes déjà lié(e) à cette personne.';

  @override
  String get errorOwnInvitation =>
      'C\'est votre propre code : donnez-le à l\'autre personne.';

  @override
  String get errorTooManyLinks =>
      'Vous avez atteint le nombre maximal de contacts liés.';

  @override
  String get errorTooManyInvitations =>
      'Trop d\'invitations en cours. Utilisez-en une ou attendez qu\'elle expire.';

  @override
  String get errorNoLinkedContact =>
      'Aucun contact lié à alerter dans l\'application.';

  @override
  String get errorCheckActive =>
      'Une vérification de sécurité est déjà en cours.';

  @override
  String get errorHistoryOff => 'L\'historique des positions est désactivé.';

  @override
  String get errorDurationTooLong => 'Cette durée dépasse le maximum autorisé.';

  @override
  String get safetyTitle => 'Sécurité personnelle';

  @override
  String get safetySettingsHint =>
      'Contacts d’urgence, message SOS, fiche médicale';

  @override
  String get safetyIntro =>
      'Préparez qui prévenir et quoi envoyer s’il vous arrive quelque chose. Vos contacts, votre message et votre fiche médicale restent sur ce téléphone.';

  @override
  String get safetySendSos => 'Envoyer mon message SOS';

  @override
  String get safetySomeone => 'Un proche';

  @override
  String get safetyDelete => 'Supprimer';

  @override
  String get safetyEdit => 'Modifier';

  @override
  String get safetyCopy => 'Copier';

  @override
  String get safetyCopied => 'Copié.';

  @override
  String get safetyDone => 'Terminé';

  @override
  String get safetySaved => 'Enregistré.';

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
  String get safetyContactsTitle => 'Contacts d’urgence';

  @override
  String safetyContactsCount(int count) {
    return 'Contacts : $count';
  }

  @override
  String get safetyContactsIntro =>
      'Jusqu’à 10 personnes qui reçoivent votre message SOS par SMS ou WhatsApp.';

  @override
  String get safetyContactsPrivacy =>
      'Gardés sur ce téléphone uniquement. L’application ne lit ni n’envoie jamais votre répertoire : vous choisissez chaque numéro.';

  @override
  String safetyContactsFull(int max) {
    return 'Vous avez atteint $max contacts.';
  }

  @override
  String get safetyContactsEmpty => 'Aucun contact d’urgence pour l’instant.';

  @override
  String get safetyContactAdd => 'Ajouter un contact';

  @override
  String get safetyContactPick => 'Choisir dans mes contacts';

  @override
  String get safetyContactPickHint =>
      'Seul le numéro choisi arrive dans l’application.';

  @override
  String get safetyContactType => 'Saisir un numéro';

  @override
  String get safetyContactTitle => 'Contact d’urgence';

  @override
  String get safetyContactName => 'Nom';

  @override
  String get safetyContactNameRequired => 'Saisissez un nom.';

  @override
  String get safetyContactPhone => 'Numéro de téléphone';

  @override
  String get safetyContactExists => 'Ce numéro est déjà dans votre liste.';

  @override
  String get safetyContactLinked => 'Lié : reçoit l’alerte dans l’application';

  @override
  String get safetyContactGroups => 'Groupes';

  @override
  String safetyContactDeleteTitle(String name) {
    return 'Supprimer $name ?';
  }

  @override
  String get safetyGroupsTitle => 'Groupes';

  @override
  String get safetyGroupsEmpty =>
      'Les groupes permettent de prévenir seulement certaines personnes (famille, voisins…).';

  @override
  String get safetyGroupAdd => 'Nouveau groupe';

  @override
  String get safetyGroupName => 'Nom du groupe';

  @override
  String get safetyGroupNameHint => 'Famille, voisins, travail…';

  @override
  String safetyGroupDeleteTitle(String name) {
    return 'Supprimer le groupe $name ?';
  }

  @override
  String get safetyGroupDeleteBody => 'Les contacts restent dans votre liste.';

  @override
  String get safetyMessageTitle => 'Message SOS';

  @override
  String get safetyMessageHint => 'Votre texte, et les 5 secondes pour annuler';

  @override
  String get safetyMessageText => 'Votre message';

  @override
  String get safetyMessageAdded =>
      'L’application ajoute le lien de votre position, sa précision, l’heure et le niveau de batterie.';

  @override
  String get safetyCancelWindow => '5 secondes pour annuler';

  @override
  String get safetyCancelWindowHint =>
      'Évite un envoi par erreur. Désactivez-le pour envoyer tout de suite.';

  @override
  String get safetyPreview => 'Aperçu';

  @override
  String get sosDefaultTemplate => 'J’ai besoin d’aide. Voici ma position.';

  @override
  String get sosLabelPosition => 'Position';

  @override
  String get sosLabelAccuracy => 'Précision';

  @override
  String get sosLabelTime => 'Heure';

  @override
  String get sosLabelBattery => 'Batterie';

  @override
  String get sosLabelNoPosition => 'Position indisponible.';

  @override
  String get safetySendIntro =>
      'Vos contacts reçoivent votre message avec votre position. Les contacts liés sont alertés dans l’application ; l’application SMS s’ouvre avec tous les numéros et vous appuyez sur Envoyer.';

  @override
  String get safetyNoContacts =>
      'Ajoutez d’abord au moins un contact d’urgence.';

  @override
  String get safetySendTo => 'Envoyer à';

  @override
  String safetySendToAll(int count) {
    return 'Tout le monde ($count)';
  }

  @override
  String safetySendChannels(int count) {
    return 'Contacts liés alertés dans l’application : $count. Puis SMS, puis WhatsApp.';
  }

  @override
  String get safetySendSmsOnly =>
      'Sans compte, le message part uniquement par SMS et WhatsApp.';

  @override
  String get safetySendNow => 'Envoyer maintenant';

  @override
  String safetySendingIn(int seconds) {
    return 'Envoi dans $seconds s…';
  }

  @override
  String get safetySending => 'Récupération de la position et envoi…';

  @override
  String safetySentApp(int count) {
    return 'Alerte reçue dans l’application par $count contact(s) lié(s).';
  }

  @override
  String get safetySentAppFailed =>
      'L’alerte dans l’application n’a pas pu partir (pas de réseau ?). Le SMS s’est quand même ouvert.';

  @override
  String safetySentSms(int count) {
    return 'SMS prêt pour $count numéro(s) : appuyez sur Envoyer dans l’application SMS.';
  }

  @override
  String get safetyWhatsApp => 'Aussi par WhatsApp';

  @override
  String get safetyWhatsAppChoose =>
      'Choisir une discussion ou un groupe WhatsApp';

  @override
  String get safetyLinkedTitle => 'Contacts liés';

  @override
  String safetyLinkedCount(int count) {
    return 'Liés : $count';
  }

  @override
  String get safetyLinkedIntro =>
      'Un proche qui utilise aussi e-Himaya peut être lié à vous. Votre message SOS sonne alors sur son téléphone, même en mode silencieux.';

  @override
  String get safetyLinkedNeedsAccount =>
      'Les liens nécessitent un compte e-Himaya sur les deux téléphones.';

  @override
  String get safetyLinkedEmpty => 'Personne n’est encore lié.';

  @override
  String get safetyLinkedPrivacy =>
      'Une personne liée voit votre prénom, votre numéro et vos alertes. Chacun peut supprimer le lien à tout moment.';

  @override
  String get safetyLinkedDone => 'Vous êtes maintenant liés.';

  @override
  String safetyLinkedPush(String name) {
    return 'Vous êtes maintenant lié(e) à $name.';
  }

  @override
  String get safetyInvite => 'Inviter';

  @override
  String get safetyInviteTitle => 'Votre code d’invitation';

  @override
  String get safetyInviteBody =>
      'Donnez ce code à la personne. Elle le saisit dans e-Himaya, Sécurité personnelle, Contacts liés.';

  @override
  String safetyInviteExpires(String time) {
    return 'Valable jusqu’à $time, une seule fois.';
  }

  @override
  String safetyInviteText(String code) {
    return 'Liez-vous à moi dans e-Himaya pour qu’on puisse s’alerter en cas d’urgence. Mon code : $code';
  }

  @override
  String get safetyEnterCode => 'Saisir un code';

  @override
  String get safetyCodeInvalid => 'Ce code est faux, déjà utilisé ou expiré.';

  @override
  String get safetyLinkConfirmTitle => 'Se lier à cette personne ?';

  @override
  String safetyLinkConfirmBody(String who) {
    return '$who recevra vos alertes et vous recevrez les siennes.';
  }

  @override
  String get safetyLinkAccept => 'Lier';

  @override
  String get safetyUnlink => 'Supprimer le lien';

  @override
  String safetyUnlinkTitle(String name) {
    return 'Supprimer le lien avec $name ?';
  }

  @override
  String get safetyUnlinkBody =>
      'Aucun de vous ne recevra plus les alertes de l’autre.';

  @override
  String get safetyAlertTitle => 'Alerte de détresse';

  @override
  String safetyAlertFrom(String name) {
    return '$name a besoin d’aide';
  }

  @override
  String safetyAlertCheckFrom(String name) {
    return '$name n’a pas confirmé être en sécurité';
  }

  @override
  String get safetyAlertMine => 'Votre alerte';

  @override
  String safetyAlertAt(String time) {
    return 'Envoyée à $time';
  }

  @override
  String safetyAlertBattery(int level) {
    return 'batterie $level %';
  }

  @override
  String safetyAlertSeenBy(int seen, int total) {
    return 'Ouverte par $seen sur $total';
  }

  @override
  String get safetyAlertNoPosition => 'Aucune position n’a été envoyée.';

  @override
  String safetyAlertLive(String time) {
    return 'Position en direct, mise à jour à $time';
  }

  @override
  String safetyAlertPositionAt(String time) {
    return 'Position à $time';
  }

  @override
  String safetyAlertCall(String name) {
    return 'Appeler $name';
  }

  @override
  String get safetyAlertRoute => 'Itinéraire';

  @override
  String get safetyAlertReportHint =>
      'S’il ou elle est en danger, appelez la Protection civile et donnez la position ci-dessus.';

  @override
  String get safetyAlertCall198 => 'Appeler le 198 pour lui ou elle';

  @override
  String get safetyAlertReport => 'Le signaler dans l’application';

  @override
  String get safetyLiveTitle => 'Position en direct';

  @override
  String get safetyLiveHint =>
      'Un lien qui montre où vous êtes, pour une durée limitée';

  @override
  String get safetyLiveRunning => 'Votre position est partagée';

  @override
  String get safetyLiveIntro =>
      'Créez un lien qui montre votre position pendant vos déplacements. Il s’arrête tout seul à la fin, ou quand vous appuyez sur Arrêter. Qui a le lien voit le point sur une carte, pas votre nom.';

  @override
  String get safetyLiveNeedsAccount =>
      'La position en direct nécessite un compte e-Himaya.';

  @override
  String get safetyLiveFor => 'Partager pendant';

  @override
  String get safetyLiveStart => 'Commencer le partage';

  @override
  String get safetyLiveStop => 'Arrêter le partage';

  @override
  String get safetyLivePrivacy =>
      'Les positions sont effacées 24 heures après la fin du partage. Une notification reste visible pendant le partage.';

  @override
  String safetyLiveLeft(String duration) {
    return 'Encore $duration';
  }

  @override
  String safetyLiveLastSent(String time) {
    return 'dernier envoi à $time';
  }

  @override
  String safetyLiveShareText(String link) {
    return 'Suivez ma position en direct : $link';
  }

  @override
  String get safetyLiveSmsContacts => 'SMS à mes contacts';

  @override
  String get safetyLiveNoticeTitle => 'e-Himaya : position partagée';

  @override
  String get safetyLiveNoticeText =>
      'Votre position est envoyée pendant le partage ou la vérification.';

  @override
  String get safetyCheckTitle => 'Vérification de sécurité';

  @override
  String get safetyCheckHint =>
      'Contacts liés alertés si vous ne confirmez pas à temps';

  @override
  String get safetyCheckRunning => 'Une vérification est en cours';

  @override
  String get safetyCheckIntro =>
      'Sortie seul(e), marche de nuit, trajet ? Fixez une heure. Si vous n’avez pas appuyé sur « Je vais bien » à temps, vos contacts liés reçoivent une alerte avec votre dernière position, même si votre téléphone est éteint. La Protection civile n’est pas alertée.';

  @override
  String get safetyCheckNeedsAccount =>
      'La vérification nécessite un compte e-Himaya et des contacts liés.';

  @override
  String get safetyCheckNoLinks =>
      'Liez d’abord au moins un contact : l’alerte part vers les contacts liés.';

  @override
  String get safetyCheckIn => 'Confirmer dans';

  @override
  String get safetyCheckMessage => 'Message pour vos contacts';

  @override
  String get safetyCheckMessageHint =>
      'Je n’ai pas confirmé être bien arrivé(e).';

  @override
  String get safetyCheckStart => 'Lancer la vérification';

  @override
  String get safetyCheckPrivacy =>
      'Rappels 10 minutes et 1 minute avant. La vérification et sa position sont effacées 7 jours après la fin.';

  @override
  String safetyCheckDue(String time) {
    return 'À confirmer avant $time';
  }

  @override
  String safetyCheckContacts(int count) {
    return 'contacts liés : $count';
  }

  @override
  String get safetyCheckOk => 'Je vais bien';

  @override
  String safetyCheckExtend(int minutes) {
    return 'Ajouter $minutes minutes';
  }

  @override
  String get safetyCheckFired => 'Vos contacts ont été alertés';

  @override
  String get safetyCheckFiredHint =>
      'Vous n’avez pas confirmé à temps. Si tout va bien, dites-le-leur ; sinon envoyez votre message SOS.';

  @override
  String get safetyCheckReminder10 =>
      'Votre vérification se termine dans 10 minutes. Ouvrez e-Himaya pour confirmer.';

  @override
  String get safetyCheckReminder1 =>
      'Plus qu’une minute : confirmez maintenant ou vos contacts seront alertés.';

  @override
  String get safetyTestTitle => 'Autotest';

  @override
  String get safetyTestHint =>
      'Vérifier que tout fonctionne, sans rien envoyer';

  @override
  String get safetyTestIntro =>
      'Vérifie ce téléphone : son d’alarme, position, réseau, notifications et batterie.';

  @override
  String get safetyTestAlarm => 'Faire sonner l’alarme';

  @override
  String get safetyTestAlarmTitle => 'Test : alerte de détresse';

  @override
  String get safetyTestAlarmBody =>
      'Voici le son d’une alerte d’un contact lié. Rien n’a été envoyé.';

  @override
  String get safetyTestAlarmSent => 'Alarme de test affichée.';

  @override
  String get safetyTestRunning => 'Vérification…';

  @override
  String get safetyTestNotificationsOn => 'Notifications autorisées';

  @override
  String get safetyTestNotificationsOff =>
      'Notifications bloquées : les alertes ne vous parviennent pas';

  @override
  String get safetyTestCriticalOn =>
      'Les alertes sonnent même en mode silencieux';

  @override
  String get safetyTestCriticalOff =>
      'Les alertes ne sonnent pas en mode silencieux';

  @override
  String get safetyTestCriticalFix => 'Activer';

  @override
  String get safetyTestDnd => 'Ne pas déranger est activé en ce moment';

  @override
  String get safetyTestOnline => 'Réseau disponible';

  @override
  String get safetyTestOffline =>
      'Pas de réseau : seuls les SMS et appels fonctionnent';

  @override
  String get safetyTestPosition => 'Position trouvée';

  @override
  String get safetyTestNoPosition =>
      'Pas de position : activez la localisation';

  @override
  String safetyTestBattery(int level) {
    return 'Batterie $level %';
  }

  @override
  String get safetyTestBatteryUnknown => 'Niveau de batterie inconnu';

  @override
  String get safetyTestPowerSave =>
      'Économiseur de batterie activé : les alertes peuvent arriver en retard';

  @override
  String safetyTestContacts(int contacts, int links) {
    return 'Contacts d’urgence : $contacts · liés : $links';
  }

  @override
  String get safetyTestAgain => 'Refaire le test';

  @override
  String get safetyTestNothingSent =>
      'Rien n’est envoyé à personne pendant l’autotest.';

  @override
  String get safetyRecentTitle => 'Alertes récentes';

  @override
  String get safetyRecentReceived => 'Reçues (dernières 24 heures)';

  @override
  String get safetyRecentSentTitle => 'Envoyées depuis ce téléphone';

  @override
  String get safetyRecentClear => 'Effacer';

  @override
  String get safetyRecentEmpty => 'Rien pour l’instant.';

  @override
  String get safetyRecentSos => 'Message SOS';

  @override
  String get safetyRecentSent => 'envoyé';

  @override
  String get safetyRecentCancelled => 'annulé';

  @override
  String get safetyRecentOk => 'terminé';

  @override
  String get safetyRecentFailed => 'non envoyé';

  @override
  String safetyRecentRecipients(int count) {
    return '$count destinataire(s)';
  }

  @override
  String get safetyChannelApp => 'application';

  @override
  String get safetyRecentPrivacy => 'Cette liste reste sur ce téléphone.';

  @override
  String get safetyMedicalTitle => 'Fiche médicale';

  @override
  String get safetyMedicalHint =>
      'Informations utiles aux secours, sur ce téléphone uniquement';

  @override
  String get safetyMedicalSaved => 'Enregistrée sur ce téléphone';

  @override
  String get medicalConsentTitle => 'Avant de commencer';

  @override
  String get medicalConsentBody =>
      'Votre fiche médicale contient des données de santé. Elle reste chiffrée sur ce téléphone. Elle n’est envoyée à la Protection civile qu’avec un signalement pour lequel vous cochez « Joindre ma fiche médicale », puis effacée 30 jours après la clôture du signalement. Vous pouvez la modifier ou la supprimer à tout moment. Tous les champs sont facultatifs.';

  @override
  String get medicalConsentCheck =>
      'J’accepte de garder ma fiche médicale sur ce téléphone dans ces conditions';

  @override
  String get medicalCreate => 'Créer ma fiche médicale';

  @override
  String get medicalIntro =>
      'Remplissez seulement ce que vous voulez. Gardée chiffrée sur ce téléphone.';

  @override
  String get medicalSex => 'Sexe';

  @override
  String get medicalSexFemale => 'Femme';

  @override
  String get medicalSexMale => 'Homme';

  @override
  String get medicalNotSaid => 'Non renseigné';

  @override
  String get medicalBirthDate => 'Date de naissance';

  @override
  String get medicalBloodGroup => 'Groupe sanguin';

  @override
  String get medicalAllergies => 'Allergies';

  @override
  String get medicalConditions => 'Maladies chroniques';

  @override
  String get medicalMedications => 'Médicaments habituels';

  @override
  String get medicalOther => 'Autre (grossesse, appareil, handicap…)';

  @override
  String get medicalTreatmentCard => 'Numéro de carte de soins';

  @override
  String get medicalContactName => 'Personne à prévenir';

  @override
  String get medicalContactPhone => 'Son numéro de téléphone';

  @override
  String get medicalContact => 'À prévenir';

  @override
  String get medicalLock => 'Demander le verrouillage du téléphone';

  @override
  String get medicalLockHint =>
      'Votre code, schéma ou empreinte avant d’ouvrir la fiche.';

  @override
  String get medicalLocked => 'Votre fiche médicale est verrouillée.';

  @override
  String get medicalUnlock => 'Déverrouiller';

  @override
  String get medicalUnlockHint =>
      'Confirmez que c’est vous pour ouvrir la fiche médicale.';

  @override
  String get medicalNoPhoneLock =>
      'Ce téléphone n’a pas de verrouillage d’écran : la fiche ne peut pas être verrouillée.';

  @override
  String get medicalForRescuer => 'Montrer aux secours';

  @override
  String get medicalCopy => 'Copier en texte';

  @override
  String get medicalEmpty => 'La fiche médicale est vide.';

  @override
  String get medicalAttachHint =>
      'Dans un signalement, cochez « Joindre ma fiche médicale » pour l’envoyer avec ce signalement seulement.';

  @override
  String get medicalDelete => 'Supprimer ma fiche médicale';

  @override
  String get medicalDeleteTitle => 'Supprimer la fiche médicale ?';

  @override
  String get medicalDeleteBody =>
      'Elle est effacée de ce téléphone. Les copies déjà jointes à des signalements sont effacées 30 jours après leur clôture.';

  @override
  String get medicalDeleted => 'Fiche médicale supprimée.';

  @override
  String get reportAttachMedical =>
      'Joindre ma fiche médicale à ce signalement';

  @override
  String get reportAttachMedicalHint =>
      'La salle des opérations ne lit que votre carte d’urgence. Le reste est verrouillé sur votre téléphone pour les médecins de la Protection civile de la région et le comité médical ; chaque ouverture est enregistrée et visible dans votre application.';

  @override
  String get safetyHistoryTitle => 'Historique des positions (72 h)';

  @override
  String get safetyHistoryOn => 'Activé';

  @override
  String get safetyHistoryOff => 'Désactivé';

  @override
  String get safetyHistoryNotice =>
      'Si vous disparaissez, la Protection civile peut voir où était votre téléphone pendant les 72 dernières heures. Elle ne le consulte que pour un signalement qu’elle traite, avec un motif, et vous êtes prévenu(e). Chaque position est effacée après 72 heures, et toutes d’un coup quand vous désactivez.';

  @override
  String get safetyHistoryUnavailable => 'Pas encore disponible.';

  @override
  String get safetyHistoryConsent =>
      'J’accepte que mes positions soient gardées 72 heures dans ces conditions';

  @override
  String get safetyHistoryTurnOn => 'Activer';

  @override
  String get safetyHistoryTurnOff => 'Désactiver et effacer';

  @override
  String safetyHistoryUntil(String time) {
    return 'Jusqu’à $time';
  }

  @override
  String get safetyHistoryViewedTitle =>
      'Votre historique de positions a été consulté';

  @override
  String get safetyHistoryViewedBody =>
      'La Protection civile l’a consulté pour un signalement. Ouvrez e-Himaya pour en savoir plus.';

  @override
  String get doctorTitle => 'Espace médecins';

  @override
  String get doctorIntro =>
      'Vous êtes médecin ? Déclarez-vous pour recevoir les dossiers médicaux joints aux signalements, verrouillés et lisibles uniquement par les médecins vérifiés. La Protection civile vérifie votre numéro d\'inscription avant tout dossier.';

  @override
  String get doctorChoose => 'Choisissez votre statut';

  @override
  String get doctorKindVolunteer => 'Médecin volontaire';

  @override
  String get doctorKindVolunteerHelp =>
      'Médecin spécialiste qui accepte de recevoir des dossiers médicaux pour donner son avis, quand un confrère les lui adresse.';

  @override
  String get doctorKindCivilProtection => 'Médecin de la Protection civile';

  @override
  String get doctorKindCivilProtectionHelp =>
      'Médecin de la Protection civile : reçoit les dossiers médicaux des signalements de son gouvernorat et les adresse aux spécialistes.';

  @override
  String get doctorApply => 'S\'inscrire comme médecin';

  @override
  String get doctorKind => 'Statut';

  @override
  String get doctorSpecialties => 'Spécialités (1 à 4)';

  @override
  String get doctorSpecialtiesRequired => 'Choisissez de 1 à 4 spécialités.';

  @override
  String get doctorLicence => 'N° d\'inscription au Conseil de l\'Ordre';

  @override
  String get doctorNumberInvalid =>
      'De 3 à 30 caractères : chiffres, lettres latines, - et /.';

  @override
  String get doctorWorkplace => 'Lieu d\'exercice (établissement)';

  @override
  String get doctorGouvernorat => 'Gouvernorat du lieu d\'exercice';

  @override
  String get doctorGouvernoratHelp =>
      'Elle détermine votre groupe de médecins.';

  @override
  String get doctorCpUnit => 'Unité ou direction régionale';

  @override
  String get doctorCpStaffNo => 'Matricule';

  @override
  String get doctorTermsTitle => 'Conditions du statut de médecin';

  @override
  String get doctorTermsBody =>
      'Les dossiers médicaux sont confidentiels : ils ne s\'ouvrent que pour secourir la personne, ne se copient ni ne se partagent hors du système, et chaque ouverture est enregistrée. Un avis donné à distance est consultatif et ne remplace pas l\'examen. La Protection civile peut suspendre votre statut en cas de manquement.';

  @override
  String get doctorTermsAccept => 'J\'ai lu et j\'accepte ces conditions';

  @override
  String get doctorTermsRequired => 'Vous devez accepter les conditions.';

  @override
  String get doctorRecheckNote =>
      'Changer de statut, de spécialités, de numéros ou de gouvernorat renvoie votre demande en vérification.';

  @override
  String get doctorSubmit => 'Envoyer pour vérification';

  @override
  String get doctorSubmitted =>
      'Demande envoyée. La Protection civile va vérifier votre numéro d\'inscription.';

  @override
  String get doctorHelpPending =>
      'Votre demande est en cours de vérification. Aucun dossier médical avant la vérification.';

  @override
  String get doctorHelpApproved =>
      'Votre statut est vérifié : vous faites partie du groupe de médecins de votre gouvernorat.';

  @override
  String get doctorHelpRejected =>
      'Votre demande n\'a pas été retenue. Vous pouvez la corriger et la renvoyer.';

  @override
  String get doctorHelpSuspended =>
      'Votre statut est suspendu : vous ne recevez plus de dossiers médicaux.';

  @override
  String get doctorHelpWithdrawn =>
      'Vous avez renoncé au statut de médecin ; vos numéros sont supprimés.';

  @override
  String get doctorAvailable => 'Disponible pour les demandes';

  @override
  String doctorAvailableUntil(String time) {
    return 'Disponible jusqu\'à $time';
  }

  @override
  String doctorCommitteeMember(String date) {
    return 'Membre du comité médical jusqu\'au $date';
  }

  @override
  String get doctorCommitteeHelp =>
      'Nommé(e) par l\'administrateur système. Depuis ce compte, vous consulterez les dossiers médicaux et les avis des spécialistes de tous les gouvernorats. Chaque ouverture demande un motif et est journalisée ; le citoyen voit « Comité médical », pas votre nom.';

  @override
  String get doctorAvailableHelp =>
      'Les médecins disponibles apparaissent en premier dans la liste. La disponibilité s\'arrête seule après 8 heures.';

  @override
  String get doctorAvailableBadge => 'Disponible';

  @override
  String get medicalCardTitle => 'Carte d’urgence';

  @override
  String get medicalCardHint =>
      'Ce que vous cochez reste lisible par la salle des opérations et les secouristes. Les autres champs sont verrouillés pour les médecins seulement.';

  @override
  String get errorDoctorKeyMissing => 'Créez d’abord votre clé personnelle.';

  @override
  String get errorNotCommitteeMember =>
      'Vous n’êtes plus membre du comité médical.';

  @override
  String get errorReasonRequired => 'Indiquez un motif.';

  @override
  String get doctorKeyTitle => 'Ma clé personnelle';

  @override
  String get doctorKeyCreateHelp =>
      'Les dossiers médicaux sont verrouillés pour vous avec une clé protégée par un code que vous choisissez. Nous ne connaissons pas votre code et ne pouvons pas le récupérer.';

  @override
  String get doctorKeyReady => 'Votre clé est prête sur ce téléphone.';

  @override
  String get doctorKeyRestoreHelp =>
      'Votre clé n’est pas sur ce téléphone. Saisissez votre code pour la récupérer.';

  @override
  String get doctorKeyCreate => 'Créer ma clé';

  @override
  String get doctorKeyRestore => 'Récupérer ma clé';

  @override
  String get doctorKeyForgot => 'J’ai oublié mon code';

  @override
  String get doctorKeyResetWarning =>
      'Une nouvelle clé sera créée. Les dossiers reçus avec l’ancienne ne pourront plus être ouverts, sauf si un confrère vous les transmet à nouveau.';

  @override
  String get doctorKeyNew => 'Nouvelle clé';

  @override
  String get doctorKeyChooseCode => 'Choisissez votre code';

  @override
  String get doctorKeyEnterCode => 'Saisissez votre code';

  @override
  String get doctorKeyCodeHint =>
      'De 6 à 12 chiffres. Gardez-le bien : il ne peut pas être récupéré.';

  @override
  String get doctorKeyCode => 'Code';

  @override
  String get doctorKeyCodeAgain => 'Confirmez le code';

  @override
  String get doctorKeyCodeInvalid => 'Le code compte de 6 à 12 chiffres.';

  @override
  String get doctorKeyCodeMismatch => 'Les deux codes diffèrent.';

  @override
  String get doctorKeyWrongCode => 'Code incorrect.';

  @override
  String get doctorFiles => 'Dossiers médicaux';

  @override
  String get doctorFilesEmpty => 'Aucun dossier médical pour l’instant.';

  @override
  String get doctorFileViaGouvernorat => 'Votre gouvernorat';

  @override
  String get doctorFileViaCommittee => 'Comité médical';

  @override
  String get doctorFileViaReferral => 'Transmis par un confrère';

  @override
  String get doctorFileReasonTitle => 'Motif de l’ouverture';

  @override
  String get doctorFileReasonHint =>
      'Le motif est enregistré. Le citoyen voit « Comité médical », pas votre nom.';

  @override
  String get doctorFileOpen => 'Ouvrir';

  @override
  String get doctorFileConfidential =>
      'Dossier confidentiel : ne le copiez pas, ne le partagez pas. Ouvert sur ce téléphone seulement, et l’ouverture est enregistrée.';

  @override
  String get doctorFileCannotOpen =>
      'Impossible d’ouvrir le dossier avec votre clé.';

  @override
  String get doctorDirectory => 'Annuaire des médecins';

  @override
  String get doctorSpecialty => 'Spécialité';

  @override
  String get doctorRegion => 'Région';

  @override
  String get doctorAllSpecialties => 'Toutes les spécialités';

  @override
  String get doctorAllGouvernorats => 'Tous les gouvernorats';

  @override
  String get doctorDirectoryEmpty => 'Aucun médecin vérifié pour ces critères.';

  @override
  String get doctorEdit => 'Modifier mes informations';

  @override
  String get doctorWithdraw => 'Renoncer au statut de médecin';

  @override
  String get doctorWithdrawConfirm =>
      'Votre numéro d\'inscription sera supprimé et vous ne recevrez plus de dossiers. Vous pourrez vous réinscrire.';

  @override
  String get doctorJoinTitle => 'Vous êtes médecin ?';

  @override
  String get doctorJoinBody =>
      'Inscrivez-vous comme médecin volontaire ou de la Protection civile.';

  @override
  String get errorNotDoctor => 'Vous n\'êtes pas inscrit comme médecin.';

  @override
  String get errorDoctorNotApproved =>
      'Votre statut de médecin n\'est pas encore vérifié.';

  @override
  String get errorCpDetailsRequired =>
      'Indiquez l\'unité et le matricule du médecin de la Protection civile.';

  @override
  String get errorUnknownTermsVersion =>
      'Les conditions ont changé. Mettez l\'application à jour puis réessayez.';

  @override
  String get specialtyGeneralPractice => 'Médecine générale';

  @override
  String get specialtyEmergencyMedicine => 'Médecine d\'urgence';

  @override
  String get specialtyAnesthesiaIcu => 'Anesthésie-réanimation';

  @override
  String get specialtyCardiology => 'Cardiologie';

  @override
  String get specialtyPulmonology => 'Pneumologie';

  @override
  String get specialtyNeurology => 'Neurologie';

  @override
  String get specialtyPediatrics => 'Pédiatrie';

  @override
  String get specialtyObstetricsGynecology => 'Gynécologie-obstétrique';

  @override
  String get specialtyInternalMedicine => 'Médecine interne';

  @override
  String get specialtyEndocrinology => 'Endocrinologie-diabétologie';

  @override
  String get specialtyNephrology => 'Néphrologie';

  @override
  String get specialtyGastroenterology => 'Gastro-entérologie';

  @override
  String get specialtyAllergyImmunology => 'Allergologie-immunologie';

  @override
  String get specialtyInfectiousDiseases => 'Maladies infectieuses';

  @override
  String get specialtyDermatologyBurns => 'Dermatologie et brûlures';

  @override
  String get specialtyOrthopedics => 'Orthopédie-traumatologie';

  @override
  String get specialtyGeneralSurgery => 'Chirurgie générale';

  @override
  String get specialtyPsychiatry => 'Psychiatrie';

  @override
  String get specialtyToxicology => 'Toxicologie';

  @override
  String get specialtyOphthalmology => 'Ophtalmologie';

  @override
  String get specialtyEnt => 'ORL';

  @override
  String get doctorRefer => 'Adresser à un spécialiste';

  @override
  String get doctorReferTitle => 'Adresser le dossier';

  @override
  String get doctorReferHint =>
      'La clé du dossier est verrouillée sur votre téléphone pour chaque médecin choisi ; le serveur ne la voit pas. Cinq adressages au plus par dossier.';

  @override
  String get doctorReferPickSpecialty => 'Choisissez d’abord la spécialité.';

  @override
  String get doctorReferNoKey => 'N’a pas encore créé sa clé';

  @override
  String get doctorReferReason => 'Motif de l’adressage';

  @override
  String get doctorReferSend => 'Adresser';

  @override
  String get doctorReferDone =>
      'Dossier adressé. Le médecin reçoit une notification sans contenu.';

  @override
  String get doctorReferrals => 'Adressages';

  @override
  String get doctorReferralsMine => 'Adressé par vous';

  @override
  String get doctorOpinions => 'Avis médicaux';

  @override
  String get doctorOpinionsEmpty => 'Aucun avis pour l’instant.';

  @override
  String get doctorOpinionWrite => 'Rédiger un avis';

  @override
  String get doctorOpinionHint =>
      'Avis consultatif verrouillé sur votre téléphone pour les médecins du gouvernorat et du comité qui détiennent le dossier, et pour celui qui vous l’a adressé.';

  @override
  String get doctorOpinionSend => 'Envoyer l’avis';

  @override
  String get doctorOpinionSent => 'Avis envoyé, verrouillé.';

  @override
  String get doctorOpinionMine => 'Votre avis';

  @override
  String get doctorOpinionCannotOpen =>
      'Impossible d’ouvrir cet avis avec votre clé.';

  @override
  String get doctorPendingTitle => 'Dossiers en attente pour un nouveau membre';

  @override
  String get doctorPendingShare => 'Verrouiller pour lui';

  @override
  String get doctorPendingReasonHint =>
      'Votre téléphone ouvre chaque dossier pour en verrouiller la clé pour le nouveau membre. Chaque ouverture est enregistrée avec le motif.';

  @override
  String get doctorPendingDone =>
      'Les dossiers sont accessibles au nouveau membre.';

  @override
  String get medicalOpeningsTitle => 'Qui a consulté mon dossier médical';

  @override
  String get medicalOpeningsEmpty =>
      'Personne n’a consulté la partie verrouillée de votre dossier.';

  @override
  String get medicalOpeningsNote =>
      'Seule la qualité est affichée, sans le nom des médecins.';

  @override
  String get medicalOpeningCommittee => 'Le comité médical';

  @override
  String get medicalOpeningOpened => 'A consulté le dossier';

  @override
  String get pushMedicalReferralTitle => 'Un dossier médical vous est adressé';

  @override
  String get pushMedicalReferralBody => 'Ouvrez-le dans l’espace médecin.';

  @override
  String get pushMedicalOpinionTitle => 'Nouvel avis médical';

  @override
  String get pushMedicalOpinionBody =>
      'Avis d’un spécialiste sur un dossier que vous suivez. Ouvrez-le dans l’espace médecin.';

  @override
  String get errorTooManyReferrals =>
      'Le dossier a atteint le nombre maximal d’adressages (5).';

  @override
  String get errorAlreadyHoldsFile =>
      'Un des médecins choisis détient déjà le dossier.';

  @override
  String get errorReferralNotAllowed =>
      'Un spécialiste ne peut pas adresser le dossier à son tour.';

  @override
  String get errorRecipientsChanged =>
      'La liste des destinataires a changé. Réessayez.';

  @override
  String get errorInvalidRecipient =>
      'Le dossier ne peut pas être verrouillé pour ce médecin.';

  @override
  String doctorPendingBody(int count, String name) {
    return '$count élément(s) pour $name';
  }

  @override
  String doctorOpinionBy(String specialty) {
    return 'Médecin spécialiste : $specialty';
  }

  @override
  String medicalOpeningCp(String gouvernorat) {
    return 'Médecin de la Protection civile, gouvernorat de $gouvernorat';
  }

  @override
  String medicalOpeningSpecialist(String specialty, String workplace) {
    return 'Médecin spécialiste : $specialty, $workplace';
  }

  @override
  String medicalOpeningReferral(String specialty) {
    return 'Votre dossier a été adressé à un spécialiste en $specialty';
  }

  @override
  String medicalOpeningsCount(int count) {
    return 'Qui a consulté mon dossier médical ($count)';
  }

  @override
  String get envBannerDevelopment =>
      '[SIM] Environnement de développement : toutes les données sont fictives';

  @override
  String get envBannerPilot => '[SIM] Environnement pilote : données de test';

  @override
  String get envBannerTraining =>
      '[SIM] Exercice : données fictives, pas de vrais signalements';
}
