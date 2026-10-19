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
  String get charterTitle =>
      'Charte de confidentialité et des données personnelles';

  @override
  String charterVersionLabel(String version) {
    return 'Version $version';
  }

  @override
  String get charterIntro =>
      'e-Himaya est la plateforme nationale de signalement des urgences à la Protection civile. Avant de l’utiliser, lisez comment vos données sont traitées et quelles sont vos obligations.';

  @override
  String get charterDataTitle => 'Données collectées et finalité';

  @override
  String get charterDataBody =>
      'Pour chaque signalement : sa catégorie, votre description, la position de l’incident et les photos, vidéos ou messages vocaux joints. Si vous créez un compte : vos nom et prénom, numéro de CIN, numéro de téléphone et région. Ces données servent uniquement au traitement des urgences et à vous informer du suivi de vos signalements.';

  @override
  String get charterLawTitle => 'Cadre légal';

  @override
  String get charterLawBody =>
      'Vos données personnelles sont traitées conformément à la loi organique n° 2004-63 du 27 juillet 2004 portant sur la protection des données à caractère personnel et à ses textes d’application, sous le contrôle de l’Instance nationale de protection des données personnelles (INPDP).';

  @override
  String get charterAnonymousTitle => 'Signaler sans compte';

  @override
  String get charterAnonymousBody =>
      'Vous pouvez signaler sans compte. L’application utilise alors une clé aléatoire créée sur ce téléphone ; la plateforme n’en conserve qu’un pseudonyme et n’enregistre pas votre adresse IP. Le signalement anonyme depuis un appareil peut être suspendu après des faux signalements avérés.';

  @override
  String get charterRightsTitle => 'Vos droits';

  @override
  String get charterRightsBody =>
      'Vous disposez d’un droit d’accès, de rectification et d’opposition au traitement de vos données dans les conditions prévues par la loi. Vous pouvez les exercer auprès de l’exploitant de la plateforme et saisir l’INPDP.';

  @override
  String get charterRetentionTitle => 'Sécurité et conservation';

  @override
  String get charterRetentionBody =>
      'Les signalements en attente d’envoi sont stockés chiffrés sur votre téléphone. Sur la plateforme, les données ne sont conservées que le temps nécessaire au traitement de l’urgence et au respect des obligations légales, et ne sont accessibles qu’aux agents habilités.';

  @override
  String get charterLiabilityTitle =>
      'Responsabilité en cas de faux signalement';

  @override
  String get charterLiabilityBody =>
      'Chaque signalement mobilise des équipes de secours qui peuvent manquer ailleurs. Faire sciemment un faux signalement ou une fausse alerte engage votre responsabilité légale et vous expose à des poursuites conformément à la loi tunisienne.';

  @override
  String get charterCheckbox =>
      'J’ai lu et j’accepte la charte, et je comprends qu’un faux signalement volontaire engage ma responsabilité légale.';

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
  String get settingsCharter => 'Relire la charte';

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
      'Veuillez accepter la charte avant de signaler.';

  @override
  String get errorRateLimited => 'Trop de requêtes. Patientez un instant.';

  @override
  String get errorUnknownCharterVersion =>
      'La charte a changé. Veuillez la relire.';

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
}
