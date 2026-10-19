import 'package:dio/dio.dart';

/// Stable machine codes of the phase-2 contract (plus client-side categories).
enum ApiErrorCode {
  authenticationRequired('authentication_required'),
  invalidDeviceKey('invalid_device_key'),
  anonBlocked('anon_blocked'),
  accountSuspended('account_suspended'),
  consentRequired('consent_required'),
  rateLimited('rate_limited'),
  unknownCharterVersion('unknown_charter_version'),
  clientUuidConflict('client_uuid_conflict'),
  notFound('not_found'),
  // tus upload creation refusals (contract §4): permanent for that file.
  reportNotFound('report_not_found'),
  invalidSha256('invalid_sha256'),
  invalidReportId('invalid_report_id'),
  uploadLengthRequired('upload_length_required'),
  concatenationNotSupported('concatenation_not_supported'),
  mediaTooLarge('media_too_large'),
  unsupportedMediaType('unsupported_media_type'),
  tooManyMedia('too_many_media'),
  uploadWindowClosed('upload_window_closed'),
  // Local: checksum mismatch detected by the server after upload.
  mediaRejected('media_rejected'),
  validation('validation_error'),
  network('network'),
  server('server'),
  unknown('unknown');

  const ApiErrorCode(this.wire);
  final String wire;

  static ApiErrorCode? fromWire(String? value) {
    for (final c in values) {
      if (c.wire == value) return c;
    }
    return null;
  }
}

class ApiException implements Exception {
  const ApiException(this.code, {this.statusCode, this.retryAfter});

  final ApiErrorCode code;
  final int? statusCode;

  /// From `Retry-After` on 429/503.
  final Duration? retryAfter;

  /// Errors worth retrying later without user action.
  bool get isTransient =>
      code == ApiErrorCode.network ||
      code == ApiErrorCode.server ||
      code == ApiErrorCode.rateLimited;

  @override
  String toString() => 'ApiException(${code.wire}, $statusCode)';

  static ApiException fromDio(DioException e) {
    final response = e.response;
    if (response == null) {
      return const ApiException(ApiErrorCode.network);
    }
    return fromResponse(
      response.statusCode ?? 0,
      response.data,
      response.headers,
    );
  }

  static ApiException fromResponse(int status, Object? data, Headers headers) {
    final detail = data is Map ? data['detail'] : null;
    final code = ApiErrorCode.fromWire(detail is String ? detail : null);
    final retryAfter = _parseRetryAfter(headers.value('retry-after'));
    if (code != null) {
      return ApiException(code, statusCode: status, retryAfter: retryAfter);
    }
    final fallback = switch (status) {
      401 => ApiErrorCode.authenticationRequired,
      404 => ApiErrorCode.notFound,
      409 => ApiErrorCode.clientUuidConflict,
      422 => ApiErrorCode.validation,
      428 => ApiErrorCode.consentRequired,
      429 => ApiErrorCode.rateLimited,
      >= 500 => ApiErrorCode.server,
      408 => ApiErrorCode.network,
      _ => ApiErrorCode.unknown,
    };
    return ApiException(fallback, statusCode: status, retryAfter: retryAfter);
  }

  static Duration? _parseRetryAfter(String? value) {
    if (value == null) return null;
    final seconds = int.tryParse(value.trim());
    if (seconds != null) return Duration(seconds: seconds);
    return null;
  }
}
