import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

import 'mission_box.dart';
import 'prevention/prevention_models.dart';
import 'staff_auth.dart';
import 'staff_models.dart';

/// The phone was revoked from the dashboard: everything on it must be erased (remote wipe).
class DeviceRevoked implements Exception {
  const DeviceRevoked();
}

/// The server answered with an error code (`detail`), e.g. `not_on_scene`, `resource_on_shift`.
class CrewError implements Exception {
  const CrewError(this.status, this.code);

  final int status;
  final String code;

  @override
  String toString() => 'CrewError($status, $code)';
}

/// `/api/v1/crew` with the leader's token and the phone's id. Tokens are refreshed shortly before
/// they expire; every write carries an id generated here, so a write retried after a dropped
/// connection is applied once by the server.
class StaffApi {
  StaffApi(
    this._dio,
    this._auth,
    this._vault, {
    DateTime Function()? clock,
    String Function()? newId,
  }) : _clock = clock ?? DateTime.now,
       _newId = newId ?? const Uuid().v4;

  final Dio _dio;
  final StaffAuth _auth;
  final StaffVault _vault;
  final DateTime Function() _clock;
  final String Function() _newId;
  Future<StaffTokens>? _refreshing;

  String get _base => _auth.config.apiBaseUrl;

  Future<String> _token() async {
    var t = await _vault.tokens();
    if (t == null) throw const StaffSignedOut();
    if (t.expiresAt.isBefore(_clock().add(const Duration(seconds: 30)))) {
      final pending = _refreshing ??= _auth.refresh(t);
      try {
        t = await pending;
        await _vault.saveTokens(t);
      } finally {
        _refreshing = null;
      }
    }
    return t.accessToken;
  }

  Future<Map<String, dynamic>> _call(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
    String? contentType,
    bool withDevice = true,
  }) async {
    final headers = {'Authorization': 'Bearer ${await _token()}'};
    if (withDevice) {
      final device = await _vault.deviceId();
      if (device != null) headers['X-Staff-Device'] = device;
    }
    final r = await _dio.request<Object>(
      '$_base/api/v1/crew$path',
      data: body,
      queryParameters: query,
      options: Options(
        method: method,
        headers: headers,
        contentType: contentType,
        validateStatus: (_) => true,
      ),
    );
    final status = r.statusCode ?? 0;
    final data = r.data;
    if (status == 410) throw const DeviceRevoked();
    if (status == 401) throw const StaffSignedOut();
    if (status >= 400) {
      final detail = data is Map ? data['detail'] : null;
      throw CrewError(status, detail is String ? detail : 'http_$status');
    }
    return data is Map<String, dynamic> ? data : {'items': data};
  }

  Map<String, dynamic> _write([Map<String, dynamic> body = const {}]) => {
    'client_id': _newId(),
    'device_at': _clock().toUtc().toIso8601String(),
    ...body,
  };

  Future<String> registerDevice({
    required String platform,
    String? label,
    int? appBuild,
    String? pushToken,
  }) async {
    final j = await _call(
      'POST',
      '/devices',
      withDevice: false,
      body: {
        'platform': platform,
        'label': ?label,
        'app_build': ?appBuild,
        'push_token': ?pushToken,
      },
    );
    return j['id'] as String;
  }

  Future<void> updatePushToken(String token) =>
      _call('PATCH', '/devices/current', body: {'push_token': token});

  Future<CrewMe> me() async => CrewMe.fromJson(await _call('GET', '/me'));

  Future<List<CrewVehicle>> vehicles() async {
    final j = await _call('GET', '/resources');
    return [
      for (final v in j['items'] as List)
        CrewVehicle.fromJson(v as Map<String, dynamic>),
    ];
  }

  Future<CrewShift> startShift(
    String vehicleId,
    int crewSize,
    String? crewNames,
  ) async => CrewShift.fromJson(
    await _call(
      'POST',
      '/shifts',
      body: _write({
        'resource_id': vehicleId,
        'crew_size': crewSize,
        if (crewNames != null && crewNames.trim().isNotEmpty)
          'crew_names': crewNames.trim(),
      }),
    ),
  );

  Future<void> endShift() => _call('POST', '/shifts/current/end');

  Future<List<Mission>> missions() async {
    final j = await _call('GET', '/missions');
    return [
      for (final m in j['items'] as List)
        Mission.fromJson(m as Map<String, dynamic>),
    ];
  }

  /// A write of a mission, stamped now: it keeps its id and time however late it is sent
  /// (phase P4d, design §9.1).
  MissionWrite write(
    String missionId,
    String action,
    Map<String, dynamic> body, {
    String? mediaType,
    Map<String, dynamic> shown = const {},
  }) => MissionWrite(
    missionId: missionId,
    action: action,
    body: _write(body),
    mediaType: mediaType,
    shown: shown,
  );

  /// Sends a write kept on the phone; an attachment's [media] goes as the raw body with its
  /// type and the write's fields as the query.
  Future<Mission> send(MissionWrite w, {Uint8List? media}) async {
    final path = '/missions/${w.missionId}/${w.action}';
    return Mission.fromJson(
      media == null
          ? await _call('POST', path, body: w.body)
          : await _call(
              'POST',
              path,
              body: media,
              contentType: w.mediaType,
              query: w.body,
            ),
    );
  }

  /// The vehicle's positions during a mission (design §9.2); the number the server kept.
  Future<int> positions(String missionId, List<QueuedPosition> points) async {
    final j = await _call(
      'POST',
      '/missions/$missionId/positions',
      body: {
        'points': [for (final p in points) p.wire],
      },
    );
    return j['accepted'] as int? ?? 0;
  }

  /// The phone's own key that signs its text messages (design §9.3).
  Future<String> smsKey() async =>
      (await _call('POST', '/devices/current/sms-key'))['key'] as String;

  Future<List<Hospital>> hospitals(String id) async {
    final j = await _call('GET', '/missions/$id/hospitals');
    return [
      for (final h in j['items'] as List)
        Hospital.fromJson(h as Map<String, dynamic>),
    ];
  }

  // ---------------------------------------------------------------- prevention (phase P4c)

  Future<List<FieldVisit>> visits() async {
    final j = await _call('GET', '/prevention/visits');
    return [
      for (final v in j['items'] as List) FieldVisit(v as Map<String, dynamic>),
    ];
  }

  Future<FieldVisit> visit(String id) async =>
      FieldVisit(await _call('GET', '/prevention/visits/$id'));

  /// «آخذها»: the visit is the inspector's, on this phone.
  Future<FieldVisit> claimVisit(String id) async =>
      FieldVisit(await _call('POST', '/prevention/visits/$id/claim'));

  /// A photo of the visit kept on the phone; [photo]'s id is its `client_id`.
  Future<FieldVisit> visitPhoto(
    String id,
    DraftPhoto photo,
    Uint8List bytes,
  ) async => FieldVisit(
    await _call(
      'POST',
      '/prevention/visits/$id/photos',
      body: bytes,
      contentType: photo.contentType,
      query: {
        'client_id': photo.id,
        'device_at': photo.takenAt.toUtc().toIso8601String(),
        'item_key': ?photo.itemKey,
      },
    ),
  );

  /// The inspection with both signatures, built on the phone (it carries its own `client_id`).
  Future<FieldVisit> visitInspection(
    String id,
    Map<String, dynamic> body,
  ) async => FieldVisit(
    await _call('POST', '/prevention/visits/$id/inspection', body: body),
  );

  Future<FieldVisit> visitDecision(
    String id,
    Map<String, dynamic> body,
  ) async => FieldVisit(
    await _call('POST', '/prevention/visits/$id/decision', body: body),
  );
}
