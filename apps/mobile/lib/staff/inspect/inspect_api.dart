import 'package:dio/dio.dart';

import 'inspect_models.dart';
import 'inspect_store.dart';

/// The server refused with a code (`detail`), e.g. `activation_refused`, `mission_not_today`.
class InspectError implements Exception {
  const InspectError(this.status, this.code);

  final int status;
  final String code;

  @override
  String toString() => 'InspectError($status, $code)';
}

/// No answer from the server: the phone keeps the work and sends it later.
class InspectOffline implements Exception {
  const InspectOffline();
}

/// The account is closed, blocked (lost phone) or expired: the phone must forget everything.
class InspectGone implements Exception {
  const InspectGone(this.code);
  final String code;
}

/// The tokens cannot be renewed: the inspector activates the phone again (new code).
class InspectSignedOut implements Exception {
  const InspectSignedOut();
}

/// `/api/v1/inspect`: the inspector's app. The access token is renewed shortly before it ends.
class InspectApi {
  InspectApi(this._dio, this._base, this._vault, {DateTime Function()? clock})
    : _clock = clock ?? DateTime.now;

  final Dio _dio;
  final String _base;
  final InspectVault _vault;
  final DateTime Function() _clock;
  Future<InspectTokens>? _refreshing;

  Future<Object?> _send(
    String method,
    String path, {
    Object? body,
    String? token,
  }) async {
    final Response<Object> r;
    try {
      r = await _dio.request<Object>(
        '$_base/api/v1/inspect$path',
        data: body,
        options: Options(
          method: method,
          headers: {if (token != null) 'Authorization': 'Bearer $token'},
          validateStatus: (_) => true,
        ),
      );
    } on DioException {
      throw const InspectOffline();
    }
    final status = r.statusCode ?? 0;
    final data = r.data;
    final detail = data is Map ? data['detail'] : null;
    final code = detail is String ? detail : 'http_$status';
    if (status == 410) throw InspectGone(code);
    if (status >= 400) throw InspectError(status, code);
    return data;
  }

  Future<String> _token() async {
    var t = await _vault.tokens();
    if (t == null) throw const InspectSignedOut();
    if (t.expiresAt.isBefore(_clock().add(const Duration(seconds: 30)))) {
      final pending = _refreshing ??= _refresh(t);
      try {
        t = await pending;
      } finally {
        _refreshing = null;
      }
    }
    return t.accessToken;
  }

  Future<InspectTokens> _refresh(InspectTokens t) async {
    try {
      final j = await _send(
        'POST',
        '/token',
        body: {'refresh_token': t.refreshToken},
      );
      final fresh = InspectTokens.fromJson(j! as Map<String, dynamic>);
      await _vault.saveTokens(fresh);
      return fresh;
    } on InspectError catch (e) {
      if (e.status == 401) throw const InspectSignedOut();
      rethrow;
    }
  }

  Future<Object?> _authed(String method, String path, {Object? body}) async {
    final token = await _token();
    try {
      return await _send(method, path, body: body, token: token);
    } on InspectError catch (e) {
      if (e.status == 401) throw const InspectSignedOut();
      rethrow;
    }
  }

  /// The registration typed on the app; returns where the code will be sent (masked).
  Future<String> register({
    required String kind,
    required String matricule,
    required String name,
    String? organisation,
    String? phone,
    String? email,
    required String via,
    String? deviceModel,
  }) async {
    final j = await _send(
      'POST',
      '/register',
      body: {
        'kind': kind,
        'matricule': matricule.trim(),
        'name': name.trim(),
        if (organisation != null && organisation.trim().isNotEmpty)
          'organisation': organisation.trim(),
        if (phone != null && phone.trim().isNotEmpty) 'phone': phone.trim(),
        if (email != null && email.trim().isNotEmpty) 'email': email.trim(),
        'via': via,
        'device_model': deviceModel,
      },
    );
    return (j as Map?)?['destination'] as String? ?? '';
  }

  /// The code received by SMS or email binds this phone to the account.
  Future<InspectTokens> activate({
    required String matricule,
    required String code,
    required String platform,
    String? model,
  }) async {
    final j = await _send(
      'POST',
      '/activate',
      body: {
        'matricule': matricule.trim(),
        'code': code.trim().toUpperCase(),
        'device': {'platform': platform, 'model': model},
      },
    );
    final t = InspectTokens.fromJson(j! as Map<String, dynamic>);
    await _vault.saveTokens(t);
    return t;
  }

  Future<List<InspectMission>> missions() async {
    final j = await _authed('GET', '/missions');
    return [
      for (final m in (j as List? ?? const []))
        InspectMission.fromJson(m as Map<String, dynamic>),
    ];
  }

  /// Opens (or reopens) the report of a place; returns the server's view of it.
  Future<Map<String, dynamic>> start(
    String siteId, {
    double? lat,
    double? lon,
    DateTime? at,
  }) async =>
      (await _authed(
            'POST',
            '/inspections',
            body: {
              'site_id': siteId,
              'lat': ?lat,
              'lon': ?lon,
              if (at != null) 'started_at': at.toUtc().toIso8601String(),
            },
          ))!
          as Map<String, dynamic>;

  /// «Arrived» or «left» on a place, at the phone's time.
  Future<void> presence(PresenceMark m) =>
      _authed('POST', '/sites/${m.siteId}/presence', body: m.body());

  /// The inspector's own reports, newest first.
  Future<List<InspectHistoryRow>> history() async {
    final j = await _authed('GET', '/inspections');
    return [
      for (final r in (j as List? ?? const []))
        InspectHistoryRow.fromJson(r as Map<String, dynamic>),
    ];
  }

  Future<void> progress(InspectDraft d) =>
      _authed('PUT', '/inspections/${d.serverId}', body: d.progressJson());

  /// The signed report; the server seals it once and answers its receipt.
  Future<Map<String, dynamic>> submit(InspectDraft d) async =>
      (await _authed(
            'POST',
            '/inspections/${d.serverId}/submit',
            body: d.submitJson(),
          ))!
          as Map<String, dynamic>;
}
