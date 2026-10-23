import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../config/providers.dart';
import '../http/api_client.dart';
import 'auth_session.dart';

/// Tunisian mobile number typed by the person (8 digits, spaces allowed) → `+216XXXXXXXX`, or null.
String? normalizeTunisianMobile(String raw) {
  var digits = raw.replaceAll(RegExp(r'[\s.\-()]'), '');
  if (digits.startsWith('+216')) digits = digits.substring(4);
  if (digits.startsWith('00216')) digits = digits.substring(5);
  return RegExp(r'^[23459]\d{7}$').hasMatch(digits) ? '+216$digits' : null;
}

/// A code was sent by SMS.
class PhoneCodeSent {
  const PhoneCodeSent({
    required this.expiresIn,
    required this.resendAfter,
    required this.simulated,
  });

  final Duration expiresIn;
  final Duration resendAfter;

  /// SIMULATION: the SMS went to the development gateway notify-sim (shown as an amber [SIM] strip).
  final bool simulated;
}

enum PhoneOtpError {
  invalidPhone,
  tooSoon,
  limit,
  smsUnavailable,
  wrongCode,
  expired,
  network,
  unknown,
}

class PhoneOtpException implements Exception {
  const PhoneOtpException(this.error, {this.triesLeft});
  final PhoneOtpError error;
  final int? triesLeft;
  @override
  String toString() => 'PhoneOtpException($error)';
}

/// Sign-in with a phone number and an SMS code (phase A, addition 6) against the Keycloak provider
/// `ehimaya-phone-otp` bound to the direct grant of the client `ehimaya-mobile`
/// (infra/keycloak/providers/phone-otp). Keycloak stays the only token issuer; refreshing the
/// tokens later uses the normal OIDC client.
class PhoneOtpClient {
  PhoneOtpClient(this._config, this._dio);

  final AppConfig _config;
  final Dio _dio;

  String get _tokenUrl => '${_config.oidcIssuer}/protocol/openid-connect/token';

  Future<Response<Object?>> _post(Map<String, String> form) async {
    try {
      return await _dio.post<Object?>(
        _tokenUrl,
        data: {
          'grant_type': 'password',
          'client_id': _config.oidcClientId,
          'scope': 'openid offline_access',
          ...form,
        },
        options: Options(
          contentType: Headers.formUrlEncodedContentType,
          validateStatus: (_) => true,
        ),
      );
    } on DioException {
      throw const PhoneOtpException(PhoneOtpError.network);
    }
  }

  static Map<String, Object?> _body(Response<Object?> r) =>
      r.data is Map ? (r.data! as Map).cast<String, Object?>() : const {};

  static PhoneOtpException _error(Response<Object?> r) {
    final body = _body(r);
    final error = switch (body['error']) {
      'invalid_phone' => PhoneOtpError.invalidPhone,
      'otp_too_soon' => PhoneOtpError.tooSoon,
      'otp_limit' => PhoneOtpError.limit,
      'sms_unavailable' => PhoneOtpError.smsUnavailable,
      'otp_expired' => PhoneOtpError.expired,
      'invalid_grant' when body['tries_left'] != null =>
        PhoneOtpError.wrongCode,
      _ => PhoneOtpError.unknown,
    };
    return PhoneOtpException(
      error,
      triesLeft: (body['tries_left'] as num?)?.toInt(),
    );
  }

  /// Step 1: Keycloak sends a code by SMS (it answers 400 `otp_sent`).
  Future<PhoneCodeSent> requestCode(String phone, String locale) async {
    final r = await _post({'phone': phone, 'ui_locales': locale});
    final body = _body(r);
    if (r.statusCode == 400 && body['error'] == 'otp_sent') {
      return PhoneCodeSent(
        expiresIn: Duration(
          seconds: (body['expires_in'] as num? ?? 300).toInt(),
        ),
        resendAfter: Duration(
          seconds: (body['resend_after'] as num? ?? 60).toInt(),
        ),
        simulated: body['sms_simulated'] == true,
      );
    }
    throw _error(r);
  }

  /// Step 2: the right code gives the tokens.
  Future<AuthSession> verify(String phone, String code, {DateTime? now}) async {
    final r = await _post({'phone': phone, 'otp': code});
    final body = _body(r);
    if (r.statusCode == 200 && body['access_token'] is String) {
      final expiresIn = (body['expires_in'] as num? ?? 300).toInt();
      return AuthSession(
        accessToken: body['access_token']! as String,
        expiresAt: (now ?? DateTime.now()).add(Duration(seconds: expiresIn)),
        refreshToken: body['refresh_token'] as String?,
        idToken: body['id_token'] as String?,
      );
    }
    throw _error(r);
  }
}

final phoneOtpClientProvider = Provider<PhoneOtpClient>((ref) {
  final config = ref.watch(appConfigProvider);
  // No identity headers: the token endpoint is public; only the test adapter is shared.
  final dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 20),
    ),
  );
  final adapter = ref.watch(httpAdapterProvider);
  if (adapter != null) dio.httpClientAdapter = adapter;
  return PhoneOtpClient(config, dio);
});
