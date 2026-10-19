import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'api_error.dart';
import 'models.dart';
import 'notify_models.dart';
import 'volunteer_models.dart';

/// Result of `POST /api/v1/reports`: 201 (new) and 200 (same `client_uuid` replayed) are
/// handled the same way by the sync engine.
class CreateReportResult {
  const CreateReportResult(this.report, {required this.created});
  final ServerReport report;
  final bool created;
}

/// `GET /api/v1/safety-tips` answer: [tips] is null when the copy identified by the sent ETag is
/// still current (304).
class TipsFetch {
  const TipsFetch(this.tips, this.etag);
  final SafetyTips? tips;
  final String? etag;
}

/// Typed access to the phase-2 API (plus the phase-4 institution and phase-5 volunteer,
/// notification and safety-tip endpoints used by the app). Every method throws [ApiException] on failure.
class EHimayaApi {
  EHimayaApi(this._dio);

  final Dio _dio;

  Future<String> charterVersion() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/charter',
      options: Options(extra: {kPublicEndpoint: true}),
    );
    return r.data!['version']! as String;
  });

  Future<void> postConsent({
    required String charterVersion,
    required String locale,
    required String platform,
  }) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/consents',
      data: {
        'charter_version': charterVersion,
        'locale': locale,
        'platform': platform,
      },
    );
  });

  Future<CreateReportResult> createReport(Map<String, Object?> body) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '/api/v1/reports',
          data: body,
        );
        return CreateReportResult(
          ServerReport.fromJson(r.data!),
          created: r.statusCode == 201,
        );
      });

  Future<ReportsPage> myReports({int limit = 50, String? before}) =>
      guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>(
          '/api/v1/reports/mine',
          queryParameters: {'limit': limit, 'before': ?before},
        );
        final data = r.data!;
        return ReportsPage([
          for (final item in (data['items'] as List? ?? const []))
            ServerReport.fromJson(item as Map<String, Object?>),
        ], data['next_before'] as String?);
      });

  Future<TrackingResult> track(String trackingCode) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/reports/track/${Uri.encodeComponent(trackingCode)}',
      options: Options(extra: {kPublicEndpoint: true}),
    );
    return TrackingResult.fromJson(r.data!);
  });

  Future<List<Gouvernorat>> gouvernorats(String lang) => guardApi(() async {
    final r = await _dio.get<List<Object?>>(
      '/api/v1/geo/gouvernorats',
      queryParameters: {'lang': lang},
    );
    return [
      for (final g in r.data!) Gouvernorat.fromJson(g! as Map<String, Object?>),
    ];
  });

  Future<List<Delegation>> delegations(int gouvernoratCode, String lang) =>
      guardApi(() async {
        final r = await _dio.get<List<Object?>>(
          '/api/v1/geo/gouvernorats/$gouvernoratCode/delegations',
          queryParameters: {'lang': lang},
        );
        return [
          for (final d in r.data!)
            Delegation.fromJson(d! as Map<String, Object?>),
        ];
      });

  /// Fields are null until the profile was filled.
  Future<Profile> getProfile() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/me/profile');
    return Profile.fromJson(r.data!);
  });

  Future<Profile> putProfile(ProfileInput profile) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '/api/v1/me/profile',
      data: profile.toJson(),
    );
    return Profile.fromJson(r.data!);
  });

  /// Institutions of the signed-in account (phase 4 §1), any status.
  Future<List<MyOrg>> myOrgs() => guardApi(() async {
    final r = await _dio.get<List<Object?>>('/api/v1/orgs/mine');
    return [
      for (final o in r.data!)
        if (o is Map<String, Object?>) MyOrg.fromJson(o),
    ];
  });

  /// Short card of an institution for the app (phase 4 §8, FR-A-081).
  Future<OrgSummary> orgSummary(String orgId) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/orgs/${Uri.encodeComponent(orgId)}/summary',
    );
    return OrgSummary.fromJson(r.data!);
  });

  /// Reports sent on behalf of an institution, newest first (phase 4 §8).
  Future<OrgReportsPage> orgReports(
    String orgId, {
    int limit = 50,
    String? cursor,
  }) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/orgs/${Uri.encodeComponent(orgId)}/reports',
      queryParameters: {'limit': limit, 'cursor': ?cursor},
    );
    final data = r.data!;
    return OrgReportsPage([
      for (final item in (data['items'] as List? ?? const []))
        if (item is Map<String, Object?>) OrgReport.fromJson(item),
    ], data['next_cursor'] as String?);
  });

  // ---------------------------------------------------------------- volunteers (phase 5 §5)

  /// The account's application, or null when it never applied (`404 not_volunteer`).
  Future<Volunteer?> myVolunteer() async {
    try {
      return await guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>('/api/v1/me/volunteer');
        return Volunteer.fromJson(r.data!);
      });
    } on ApiException catch (e) {
      if (e.code == ApiErrorCode.notVolunteer) return null;
      rethrow;
    }
  }

  Future<Volunteer> putVolunteer(VolunteerInput input) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '/api/v1/me/volunteer',
      data: input.toJson(),
    );
    return Volunteer.fromJson(r.data!);
  });

  Future<void> withdrawVolunteer() => guardApi(() async {
    await _dio.delete<Object?>('/api/v1/me/volunteer');
  });

  /// Readiness on (with the current position and a duration in hours) or off.
  Future<Volunteer> setReadiness({
    required bool ready,
    GeoPoint? position,
    int hours = 8,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/me/volunteer/readiness',
      data: {
        'ready': ready,
        if (ready) ...?position?.toJson(),
        'hours': ?(ready ? hours : null),
      },
    );
    return Volunteer.fromJson(r.data!);
  });

  /// Live position while ready (kept by the server in memory only, never archived).
  Future<void> putVolunteerLocation(GeoPoint position) => guardApi(() async {
    await _dio.put<Object?>(
      '/api/v1/me/volunteer/location',
      data: position.toJson(),
    );
  });

  Future<List<MyCallout>> myCallouts({bool active = true}) =>
      guardApi(() async {
        final r = await _dio.get<List<Object?>>(
          '/api/v1/me/callouts',
          queryParameters: {'active': active},
        );
        return [
          for (final c in r.data!)
            if (c is Map<String, Object?>) MyCallout.fromJson(c),
        ];
      });

  Future<MyCallout> respondCallout(
    String id, {
    required bool accept,
    int? etaMinutes,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/me/callouts/${Uri.encodeComponent(id)}/respond',
      data: {
        'response': accept ? 'accept' : 'decline',
        'eta_minutes': ?(accept ? etaMinutes : null),
      },
    );
    return MyCallout.fromJson(r.data!);
  });

  Future<MyCallout> calloutArrived(String id) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/me/callouts/${Uri.encodeComponent(id)}/arrived',
    );
    return MyCallout.fromJson(r.data!);
  });

  // ---------------------------------------------------------------- push, inbox, alerts (§6, §7)

  /// Registers (or refreshes) this phone's push token. [position] is sent only when the user
  /// allows alerts for their current location; the server rounds it to about 1 km.
  Future<void> putDevice({
    required String token,
    required String platform,
    required String locale,
    required bool locationAlerts,
    GeoPoint? position,
  }) => guardApi(() async {
    await _dio.put<Object?>(
      '/api/v1/devices',
      data: {
        'token': token,
        'platform': platform,
        'locale': locale,
        'location_alerts': locationAlerts,
        if (locationAlerts && position != null) ...{
          'lat': position.lat,
          'lon': position.lon,
        },
      },
    );
  });

  Future<void> deleteDevice(String token) => guardApi(() async {
    await _dio.delete<Object?>('/api/v1/devices/${Uri.encodeComponent(token)}');
  });

  Future<InboxPage> inbox({int limit = 30, String? cursor}) =>
      guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>(
          '/api/v1/notifications',
          queryParameters: {'limit': limit, 'cursor': ?cursor},
        );
        final data = r.data!;
        return InboxPage([
          for (final item in (data['items'] as List? ?? const []))
            if (item is Map<String, Object?>) InboxItem.fromJson(item),
        ], data['next_cursor'] as String?);
      });

  /// Public: active alerts covering a point or a gouvernorat (all of them without either).
  Future<List<ActiveAlert>> activeAlerts({
    GeoPoint? position,
    int? gouvernoratCode,
  }) => guardApi(() async {
    final r = await _dio.get<List<Object?>>(
      '/api/v1/alerts/active',
      queryParameters: {
        if (position != null && position.isInTunisiaBox) ...{
          'lat': position.lat,
          'lon': position.lon,
        },
        'gouvernorat_code': ?gouvernoratCode,
      },
      options: Options(extra: {kPublicEndpoint: true}),
    );
    return [
      for (final a in r.data!)
        if (a is Map<String, Object?>) ActiveAlert.fromJson(a),
    ];
  });

  // ---------------------------------------------------------------- safety tips (§8)

  Future<TipsFetch> safetyTips({String? etag}) => guardApi(() async {
    final r = await _dio.get<Object?>(
      '/api/v1/safety-tips',
      options: Options(
        extra: {kPublicEndpoint: true},
        headers: {'If-None-Match': ?etag},
        validateStatus: (s) => s == 200 || s == 304,
      ),
    );
    final newEtag = r.headers.value('etag') ?? etag;
    if (r.statusCode == 304) return TipsFetch(null, newEtag);
    return TipsFetch(SafetyTips.fromJson(r.data), newEtag);
  });
}

final apiProvider = Provider<EHimayaApi>(
  (ref) => EHimayaApi(ref.watch(apiDioProvider)),
);
