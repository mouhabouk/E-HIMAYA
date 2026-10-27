import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

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

  Future<Mission> _mission(
    String id,
    String action,
    Map<String, dynamic> b,
  ) async => Mission.fromJson(
    await _call('POST', '/missions/$id/$action', body: _write(b)),
  );

  Future<Mission> acknowledge(String id) => _mission(id, 'ack', const {});

  Future<Mission> step(String id, String status, {double? lat, double? lon}) =>
      _mission(id, 'status', {'status': status, 'lat': ?lat, 'lon': ?lon});

  /// A situation report: the first one, then updates (design §5.5).
  Future<Mission> situation(
    String id, {
    required String category,
    required int severity,
    List<String> backupKinds = const [],
    bool crewDanger = false,
  }) => _mission(id, 'situation', {
    'category': category,
    'severity': severity,
    'backup_needed': backupKinds.isNotEmpty,
    'backup_kinds': backupKinds,
    'crew_danger': crewDanger,
  });

  Future<Mission> casualties(String id, Map<CasualtyCounter, int> deltas) =>
      _mission(id, 'casualties', {
        for (final e in deltas.entries) e.key.wire: e.value,
      });

  /// One person taken to hospital: a hospital of the map ([hospitalRef]) or a typed name.
  Future<Mission> transport(
    String id, {
    required Triage triage,
    required AgeBand ageBand,
    required Sex sex,
    String? hospitalRef,
    String? hospital,
  }) => _mission(id, 'transports', {
    'triage': triage.name,
    'age_band': ageBand.wire,
    'sex': sex.name,
    'hospital_ref': ?hospitalRef,
    if (hospitalRef == null) 'hospital': hospital?.trim(),
  });

  /// "Backup" or "danger to the crew", with the chips chosen (design §5.4).
  Future<Mission> alert(String id, String kind, List<String> items) =>
      _mission(id, 'alerts', {'kind': kind, 'items': items});

  Future<Mission> note(String id, String body) =>
      _mission(id, 'notes', {'body': body.trim()});

  /// A photo or a voice note, sent as the raw body with its type.
  Future<Mission> upload(String id, String kind, CapturedMedia media) async =>
      Mission.fromJson(
        await _call(
          'POST',
          '/missions/$id/attachments',
          body: media.bytes,
          contentType: media.contentType,
          query: {
            'kind': kind,
            'client_id': _newId(),
            'device_at': _clock().toUtc().toIso8601String(),
            'duration_s': ?media.durationS,
          },
        ),
      );

  Future<Mission> detailedReport(
    String id,
    String templateId,
    Map<String, Object> answers,
    String? note,
  ) => _mission(id, 'detailed-report', {
    'template_id': templateId,
    'answers': answers,
    if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
  });

  Future<List<Hospital>> hospitals(String id) async {
    final j = await _call('GET', '/missions/$id/hospitals');
    return [
      for (final h in j['items'] as List)
        Hospital.fromJson(h as Map<String, dynamic>),
    ];
  }
}
