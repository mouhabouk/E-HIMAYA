import '../../l10n/app_localizations.dart';
import 'api_error.dart';

/// Contract error codes are never shown raw: each maps to a translated message.
String apiErrorMessage(AppLocalizations l10n, ApiErrorCode code) =>
    switch (code) {
      ApiErrorCode.authenticationRequired => l10n.errorAuthenticationRequired,
      ApiErrorCode.invalidDeviceKey => l10n.errorInvalidDeviceKey,
      ApiErrorCode.anonBlocked => l10n.errorAnonBlocked,
      ApiErrorCode.accountSuspended => l10n.errorAccountSuspended,
      ApiErrorCode.consentRequired => l10n.errorConsentRequired,
      ApiErrorCode.rateLimited => l10n.errorRateLimited,
      ApiErrorCode.unknownCharterVersion => l10n.errorUnknownCharterVersion,
      ApiErrorCode.clientUuidConflict => l10n.errorClientUuidConflict,
      ApiErrorCode.notFound => l10n.errorNotFound,
      ApiErrorCode.orgNotFound => l10n.errorOrgNotFound,
      ApiErrorCode.orgNotActive => l10n.errorOrgNotActive,
      ApiErrorCode.orgRoleRequired => l10n.errorOrgRoleRequired,
      ApiErrorCode.reportNotFound => l10n.errorNotFound,
      ApiErrorCode.registrationRequired => l10n.errorRegistrationRequired,
      ApiErrorCode.notVolunteer => l10n.errorNotVolunteer,
      ApiErrorCode.profileIncomplete => l10n.errorProfileIncomplete,
      ApiErrorCode.invalidPeriod => l10n.errorInvalidPeriod,
      ApiErrorCode.volunteerNotApproved => l10n.errorVolunteerNotApproved,
      ApiErrorCode.outsidePeriod => l10n.errorOutsidePeriod,
      ApiErrorCode.notReady => l10n.errorNotReady,
      ApiErrorCode.locationRequired => l10n.errorLocationRequired,
      ApiErrorCode.calloutClosed => l10n.errorCalloutClosed,
      ApiErrorCode.etaRequired => l10n.errorEtaRequired,
      ApiErrorCode.invalidTransition => l10n.errorInvalidTransition,
      ApiErrorCode.versionConflict => l10n.errorVersionConflict,
      ApiErrorCode.invalidSha256 ||
      ApiErrorCode.invalidReportId ||
      ApiErrorCode.uploadLengthRequired ||
      ApiErrorCode.concatenationNotSupported => l10n.errorMediaRefused,
      ApiErrorCode.mediaTooLarge => l10n.errorMediaTooLarge,
      ApiErrorCode.unsupportedMediaType => l10n.errorUnsupportedMediaType,
      ApiErrorCode.tooManyMedia => l10n.errorTooManyMedia,
      ApiErrorCode.uploadWindowClosed => l10n.errorUploadWindowClosed,
      ApiErrorCode.mediaRejected => l10n.errorMediaRejected,
      ApiErrorCode.streamAlreadyActive => l10n.errorStreamAlreadyActive,
      ApiErrorCode.streamNotActive => l10n.errorStreamNotActive,
      ApiErrorCode.reportClosed => l10n.errorReportClosed,
      ApiErrorCode.validation => l10n.errorValidation,
      ApiErrorCode.network => l10n.errorNetwork,
      ApiErrorCode.server => l10n.errorServer,
      ApiErrorCode.unknown => l10n.errorUnknown,
    };

String errorMessageFor(AppLocalizations l10n, Object error) =>
    error is ApiException
    ? apiErrorMessage(l10n, error.code)
    : l10n.errorUnknown;
