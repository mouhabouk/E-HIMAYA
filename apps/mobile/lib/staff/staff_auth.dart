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
  });

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
  );

  final String accessToken;
  final String refreshToken;
  final DateTime expiresAt;

  Map<String, dynamic> toJson() => {
    'a': accessToken,
    'r': refreshToken,
    'e': expiresAt.toUtc().toIso8601String(),
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

  /// A fresh access token. Throws [StaffSignedOut] when the server refuses the refresh token;
  /// a network error is rethrown as is (the shift goes on with the last missions).
  Future<StaffTokens> refresh(StaffTokens tokens) async {
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
  static const keys = [_tokens, _device, _pin, _failures];

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
