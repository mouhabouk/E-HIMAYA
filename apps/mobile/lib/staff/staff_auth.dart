import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';

import '../core/storage/secure_store.dart';
import 'staff_config.dart';

/// Code shown to the team leader while the phone waits for the sign-in (RFC 8628 §3.2).
class DeviceCode {
  const DeviceCode({
    required this.deviceCode,
    required this.userCode,
    required this.verificationUri,
    required this.verificationUriComplete,
    required this.interval,
    required this.expiresAt,
  });

  final String deviceCode;
  final String userCode;
  final String verificationUri;
  final String? verificationUriComplete;
  final Duration interval;
  final DateTime expiresAt;
}

/// Tokens of the team leader. The refresh token is an offline one: a shift outlives the staff
/// realm's 15-minute idle limit, and the PIN guards the phone in between.
class StaffTokens {
  const StaffTokens({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
    this.field = false,
  });

  /// Tokens the platform issued to an agent activated with a code (phase F): renewed at
  /// `/api/v1/field/token`, not at the identity provider.
  factory StaffTokens.fromField(Map<String, dynamic> json) => StaffTokens(
    accessToken: json['access_token'] as String,
    refreshToken: json['refresh_token'] as String,
    expiresAt: DateTime.parse(json['expires_at'] as String),
    field: true,
  );

  factory StaffTokens.fromToken(Map<String, dynamic> json, DateTime now) =>
      StaffTokens(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
        expiresAt: now.add(
          Duration(seconds: (json['expires_in'] as num?)?.toInt() ?? 300),
        ),
      );

  factory StaffTokens.fromJson(Map<String, dynamic> json) => StaffTokens(
    accessToken: json['a'] as String,
    refreshToken: json['r'] as String,
    expiresAt: DateTime.parse(json['e'] as String),
    field: json['f'] == true,
  );

  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;
  final bool field;

  Map<String, dynamic> toJson() => {
    'a': accessToken,
    'r': refreshToken,
    'e': expiresAt.toUtc().toIso8601String(),
    if (field) 'f': true,
  };
}

enum PollOutcome { pending, slowDown, granted, denied, expired }

class PollResult {
  const PollResult(this.outcome, [this.tokens]);

  final PollOutcome outcome;
  final StaffTokens? tokens;
}

/// The sign-in is refused for good (refresh token revoked, account disabled).
class StaffSignedOut implements Exception {
  const StaffSignedOut();
}

/// The room disabled the agent's phone (phase F): the app erases everything it holds.
class FieldDeviceRevoked implements Exception {
  const FieldDeviceRevoked();
}

/// The activation was refused: `activation_refused` (wrong number or code) or
/// `activation_expired`; [code] is `network` when the server could not be reached.
class ActivationRefused implements Exception {
  const ActivationRefused(this.code);

  final String code;
}

/// What the server answers to an activation: the tokens and the phone's id.
class Activation {
  const Activation({required this.tokens, required this.deviceId});

  final StaffTokens tokens;
  final String deviceId;
}

/// Device authorization grant against the staff realm, over plain HTTP (no browser plugin).
class StaffAuth {
  StaffAuth(this.config, this._dio, {DateTime Function()? clock})
    : _clock = clock ?? DateTime.now;

  final StaffConfig config;
  final Dio _dio;
  final DateTime Function() _clock;

  static final _form = Options(
    contentType: Headers.formUrlEncodedContentType,
    validateStatus: (_) => true,
  );

  Future<DeviceCode> start() async {
    final r = await _dio.post<Map<String, dynamic>>(
      config.deviceEndpoint,
      data: {'client_id': config.clientId, 'scope': 'openid offline_access'},
      options: _form,
    );
    final json = r.data;
    if (r.statusCode != 200 || json == null) {
      throw DioException(
        requestOptions: r.requestOptions,
        response: r,
        message: 'device authorization refused',
      );
    }
    return DeviceCode(
      deviceCode: json['device_code'] as String,
      userCode: json['user_code'] as String,
      verificationUri: json['verification_uri'] as String,
      verificationUriComplete: json['verification_uri_complete'] as String?,
      interval: Duration(seconds: (json['interval'] as num?)?.toInt() ?? 5),
      expiresAt: _clock().add(
        Duration(seconds: (json['expires_in'] as num?)?.toInt() ?? 600),
      ),
    );
  }

  Future<PollResult> poll(DeviceCode code) async {
    final r = await _dio.post<Map<String, dynamic>>(
      config.tokenEndpoint,
      data: {
        'client_id': config.clientId,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
        'device_code': code.deviceCode,
      },
      options: _form,
    );
    final json = r.data ?? const {};
    if (r.statusCode == 200) {
      return PollResult(
        PollOutcome.granted,
        StaffTokens.fromToken(json, _clock()),
      );
    }
    return PollResult(switch (json['error']) {
      'authorization_pending' => PollOutcome.pending,
      'slow_down' => PollOutcome.slowDown,
      'access_denied' => PollOutcome.denied,
      _ => PollOutcome.expired,
    });
  }

  /// Phase F: the agent types the professional number and the one-time code the room chief gave;
  /// the phone is registered to them and receives the platform's own tokens.
  Future<Activation> activate({
    required String matricule,
    required String code,
    required String platform,
    String? pushToken,
  }) async {
    final Response<Map<String, dynamic>> r;
    try {
      r = await _dio.post<Map<String, dynamic>>(
        '${config.apiBaseUrl}/api/v1/field/activate',
        data: {
          'matricule': matricule.trim(),
          'code': code.trim(),
          'device': {'platform': platform, 'push_token': ?pushToken},
        },
        options: Options(validateStatus: (_) => true),
      );
    } on DioException {
      throw const ActivationRefused('network');
    }
    final json = r.data;
    if (r.statusCode == 200 && json != null) {
      return Activation(
        tokens: StaffTokens.fromField(json),
        deviceId: json['device_id'] as String,
      );
    }
    final detail = json?['detail'];
    throw ActivationRefused(
      detail is String
          ? detail
          : (r.statusCode == 429 ? 'rate_limited' : 'activation_refused'),
    );
  }

  /// A fresh access token. Throws [StaffSignedOut] when the server refuses the refresh token;
  /// a network error is rethrown as is (the shift goes on with the last missions).
  Future<StaffTokens> refresh(StaffTokens tokens) async {
    if (tokens.field) return _refreshField(tokens);
    final r = await _dio.post<Map<String, dynamic>>(
      config.tokenEndpoint,
      data: {
        'client_id': config.clientId,
        'grant_type': 'refresh_token',
        'refresh_token': tokens.refreshToken,
      },
      options: _form,
    );
    if (r.statusCode == 200 && r.data != null) {
      return StaffTokens.fromToken(r.data!, _clock());
    }
    if (r.statusCode == 400 || r.statusCode == 401) {
      throw const StaffSignedOut();
    }
    throw DioException(requestOptions: r.requestOptions, response: r);
  }

  Future<StaffTokens> _refreshField(StaffTokens tokens) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '${config.apiBaseUrl}/api/v1/field/token',
      data: {'refresh_token': tokens.refreshToken},
      options: Options(validateStatus: (_) => true),
    );
    if (r.statusCode == 200 && r.data != null) {
      return StaffTokens.fromField(r.data!);
    }
    if (r.statusCode == 410) throw const FieldDeviceRevoked();
    if (r.statusCode == 401) throw const StaffSignedOut();
    throw DioException(requestOptions: r.requestOptions, response: r);
  }
}

/// What the staff app keeps on the phone, all in the platform keystore, and the one place that
/// erases it (sign-out, five wrong PINs, remote wipe).
class StaffVault {
  StaffVault(this._store);

  final SecureStore _store;

  static const _tokens = 'staff_tokens_v1';
  static const _device = 'staff_device_v1';
  static const _pin = 'staff_pin_v1';
  static const _failures = 'staff_pin_failures_v1';
  static const _roles = 'staff_roles_v1';

  /// The key of the visits kept on the phone (phase P4c): erased with the rest, nothing stays
  /// readable.
  static const _visits = 'staff_visits_key_v1';

  /// The missions kept on the phone and the writes that wait (phase P4d).
  static const _box = 'staff_box_key_v1';

  /// The phone's own key that signs its text messages (phase P4d, design §9.3).
  static const _smsKey = 'staff_sms_key_v1';
  static const keys = [
    _tokens,
    _device,
    _pin,
    _failures,
    _roles,
    _visits,
    _box,
    _smsKey,
  ];

  Future<StaffTokens?> tokens() async {
    final raw = await _store.read(_tokens);
    if (raw == null) return null;
    try {
      return StaffTokens.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } on Object {
      return null;
    }
  }

  Future<void> saveTokens(StaffTokens t) =>
      _store.write(_tokens, jsonEncode(t.toJson()));

  Future<String?> deviceId() => _store.read(_device);
  Future<void> saveDeviceId(String id) => _store.write(_device, id);

  /// The account's field roles from the last `/me`, to open the right home without network.
  Future<List<String>> roles() async =>
      (await _store.read(_roles))
          ?.split(',')
          .where((r) => r.isNotEmpty)
          .toList() ??
      const [];
  Future<void> saveRoles(List<String> roles) =>
      _store.write(_roles, roles.join(','));

  Future<String?> smsKey() => _store.read(_smsKey);
  Future<void> saveSmsKey(String key) => _store.write(_smsKey, key);

  Future<bool> hasPin() async => await _store.read(_pin) != null;

  /// Stores a salted SHA-256 of the PIN; the PIN itself never leaves the screen.
  Future<void> setPin(String pin, String salt) async {
    await _store.write(_pin, '$salt:${pinHash(salt, pin)}');
    await _store.write(_failures, '0');
  }

  /// True when [pin] is right. Wrong PINs are counted; [StaffConfig.maxPinFailures] in a row wipe
  /// the phone (returns false and [failures] reads 0 again on an empty vault).
  Future<bool> checkPin(String pin) async {
    final stored = await _store.read(_pin);
    if (stored == null) return false;
    final i = stored.indexOf(':');
    if (pinHash(stored.substring(0, i), pin) == stored.substring(i + 1)) {
      await _store.write(_failures, '0');
      return true;
    }
    final n = await failures() + 1;
    if (n >= StaffConfig.maxPinFailures) {
      await wipe();
    } else {
      await _store.write(_failures, '$n');
    }
    return false;
  }

  Future<int> failures() async =>
      int.tryParse(await _store.read(_failures) ?? '') ?? 0;

  Future<void> wipe() async {
    for (final k in keys) {
      await _store.delete(k);
    }
  }
}

String pinHash(String salt, String pin) =>
    sha256.convert(utf8.encode('ehimaya-staff-pin:$salt:$pin')).toString();
