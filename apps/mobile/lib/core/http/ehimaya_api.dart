import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/contact/contact_models.dart';
import '../../features/guide/guide_models.dart';
import '../../features/places/places_models.dart';
import '../quota/anon_quota.dart';
import 'api_client.dart';
import 'api_error.dart';
import 'models.dart';
import 'notify_models.dart';
import 'rewards_models.dart';
import 'stream_models.dart';
import 'volunteer_models.dart';
import 'weather_models.dart';

/// Result of `POST /api/v1/reports`: 201 (new) and 200 (same `client_uuid` replayed) are
/// handled the same way by the sync engine.
class CreateReportResult {
  const CreateReportResult(this.report, {required this.created, this.quota});
  final ServerReport report;
  final bool created;

  /// Quota left to this anonymous installation after the report (phase 9 §3); null for
  /// registered accounts.
  final AnonQuota? quota;
}

/// `GET /api/v1/safety-tips` answer: [tips] is null when the copy identified by the sent ETag is
/// still current (304).
class TipsFetch {
  const TipsFetch(this.tips, this.etag);
  final SafetyTips? tips;
  final String? etag;
}

/// Result of a conditional fetch of the emergency guide: [guide] is null when unchanged (`304`).
class GuideFetch {
  const GuideFetch(this.guide, this.etag);
  final EmergencyGuide? guide;
  final String? etag;
}

/// Conditional fetch of the public layers or of one layer's package: null body when unchanged.
class LayersFetch {
  const LayersFetch(this.layers, this.etag);
  final List<PlaceLayer>? layers;
  final String? etag;
}

class PackageFetch {
  const PackageFetch(this.package, this.etag);
  final PlacePackage? package;
  final String? etag;
}

/// `POST /api/v1/me/delete` refused: the caller is the last admin of an institution.
class LastAdminException implements Exception {
  const LastAdminException();
}

/// Typed access to the phase-2 API (plus the phase-4 institution and phase-5 volunteer,
/// notification and safety-tip endpoints, and the phase-6 live streams used by the app). Every method throws [ApiException] on failure.
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
          quota: AnonQuota.fromHeaders(r.headers),
        );
      });

  /// `GET /api/v1/reports/quota` (phase 9 §3): null for a registered account (no quota).
  Future<AnonQuota?> reportQuota() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/reports/quota');
    return AnonQuota.fromJson(r.data!);
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

  /// Consent to share the position while ready, after reading notice [version] (phase 10 §4.2).
  Future<void> giveLocationConsent({
    required String version,
    required String locale,
    required String platform,
  }) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/me/consents',
      data: {
        'purpose': 'volunteer_location',
        'version': version,
        'locale': locale,
        'platform': platform,
      },
    );
  });

  /// Withdraws it: the server drops the position and ends readiness at once.
  Future<void> withdrawLocationConsent() => guardApi(() async {
    await _dio.delete<Object?>('/api/v1/me/consents/volunteer_location');
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

  // ---------------------------------------------------------------- citizen rights (A6)

  /// Every personal datum the server holds on the caller (profile, consents, reports with
  /// media metadata, volunteer record, devices), as indented JSON text. Rate limited by the
  /// server (3 a day).
  Future<String> exportMyData() => guardApi(() async {
    final r = await _dio.get<Object?>('/api/v1/me/export');
    final data = r.data;
    return data is String
        ? data
        : const JsonEncoder.withIndent('  ').convert(data);
  });

  /// Deletes the account (or this device's anonymous identity): the server anonymises the
  /// profile at once and keeps reports detached from the person (legal retention).
  /// Throws [LastAdminException] when the caller is the last admin of an institution (409
  /// `last_admin`): they must hand the administration over first.
  Future<void> deleteMyAccount() async {
    try {
      await _dio.post<Object?>(
        '/api/v1/me/delete',
        data: {'confirm': 'DELETE'},
      );
    } on DioException catch (e) {
      final data = e.response?.data;
      if (e.response?.statusCode == 409 &&
          data is Map &&
          (data['code'] == 'last_admin' || data['detail'] == 'last_admin')) {
        throw const LastAdminException();
      }
      throw ApiException.fromDio(e);
    }
  }

  // ---------------------------------------------------------------- live streams (phase 6 §2)

  /// Opens a live stream on one of the caller's reports (FR-A-050). `409 stream_already_active`
  /// when the report already has a pending or live stream; `429` past 6 an hour.
  Future<LiveStreamGrant> startStream(String reportId) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/reports/${Uri.encodeComponent(reportId)}/streams',
    );
    return LiveStreamGrant.fromJson(r.data!);
  });

  /// Position while live (FR-A-052). The server ignores calls closer than 3 s (still `204`) and
  /// answers `409 stream_not_active` once the stream is over.
  Future<void> postStreamLocation(String streamId, GeoPoint position) =>
      guardApi(() async {
        await _dio.post<Object?>(
          '/api/v1/streams/${Uri.encodeComponent(streamId)}/location',
          data: {
            'lat': position.lat,
            'lon': position.lon,
            'accuracy_m': ?position.accuracyM,
          },
        );
      });

  /// Idempotent; kicks the publisher through the MediaMTX API.
  Future<LiveStreamInfo?> stopStream(String streamId) => guardApi(() async {
    final r = await _dio.post<Object?>(
      '/api/v1/streams/${Uri.encodeComponent(streamId)}/stop',
    );
    final data = r.data;
    return data is Map<String, Object?> ? LiveStreamInfo.fromJson(data) : null;
  });

  /// Polled while live to learn that an operator ended the stream.
  Future<LiveStreamInfo> getStream(String streamId) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/streams/${Uri.encodeComponent(streamId)}',
    );
    return LiveStreamInfo.fromJson(r.data!);
  });

  // ---------------------------------------------------------------- weather (phase 7 §1)

  /// Public: current weather, the next hours and the weather alerts at [position] (the caller
  /// rounds it). An answer that cannot be read is reported as a server error.
  Future<WeatherReport> weather(GeoPoint position) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/weather',
      queryParameters: {'lat': position.lat, 'lon': position.lon},
      options: Options(extra: {kPublicEndpoint: true}),
    );
    final report = WeatherReport.fromJson(r.data);
    if (report == null) {
      throw ApiException(ApiErrorCode.server, statusCode: r.statusCode);
    }
    return report;
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

  /// Emergency hub topics and items (phase B1), public and kept offline like the tips.
  Future<GuideFetch> emergencyGuide({String? etag}) => guardApi(() async {
    final r = await _dio.get<Object?>(
      '/api/v1/emergency-guide',
      options: Options(
        extra: {kPublicEndpoint: true},
        headers: {'If-None-Match': ?etag},
        validateStatus: (s) => s == 200 || s == 304,
      ),
    );
    final newEtag = r.headers.value('etag') ?? etag;
    if (r.statusCode == 304) return GuideFetch(null, newEtag);
    return GuideFetch(EmergencyGuide.fromJson(r.data), newEtag);
  });

  /// Public map layers (phase B1): their names in every language, so one copy serves all.
  Future<LayersFetch> publicLayers({String? etag}) => guardApi(() async {
    final r = await _dio.get<Object?>(
      '/api/v1/layers',
      options: Options(
        extra: {kPublicEndpoint: true},
        headers: {'If-None-Match': ?etag},
        validateStatus: (s) => s == 200 || s == 304,
      ),
    );
    final newEtag = r.headers.value('etag') ?? etag;
    if (r.statusCode == 304) return LayersFetch(null, newEtag);
    final items = (r.data! as Map)['items']! as List;
    return LayersFetch([
      for (final i in items) PlaceLayer.fromJson(i as Map<String, Object?>),
    ], newEtag);
  });

  /// The whole country's places of a layer, kept offline for "nearest to me".
  Future<PackageFetch> layerPackage(
    String key, {
    required String lang,
    String? etag,
  }) => guardApi(() async {
    final r = await _dio.get<Object?>(
      '/api/v1/layers/${Uri.encodeComponent(key)}/package',
      queryParameters: {'lang': lang},
      options: Options(
        extra: {kPublicEndpoint: true},
        headers: {'If-None-Match': ?etag},
        validateStatus: (s) => s == 200 || s == 304,
      ),
    );
    final newEtag = r.headers.value('etag') ?? etag;
    if (r.statusCode == 304) return PackageFetch(null, newEtag);
    return PackageFetch(
      PlacePackage.fromJson(r.data! as Map<String, Object?>, etag: newEtag),
      newEtag,
    );
  });

  /// "Contact us" (phase B1): sends a request; the answer carries its number.
  Future<MyContactRequest> sendContact(Map<String, Object?> body) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '/api/v1/contact',
          data: body,
        );
        return MyContactRequest.fromJson(r.data!);
      });

  /// The caller's own requests, newest first, with their status and the Office's answer.
  Future<List<MyContactRequest>> myContactRequests() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/me/contact');
    return [
      for (final i in r.data!['items']! as List)
        MyContactRequest.fromJson(i as Map<String, Object?>),
    ];
  });

  // ---------------------------------------------------------------- rewards (phase 8 §3)

  /// Balance, badges, latest history and certificates of the caller. An anonymous identity gets
  /// zeros with `anonymous: true` (anonymous reports earn no points).
  Future<RewardsSummary> myRewards() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/me/rewards');
    return RewardsSummary.fromJson(r.data!);
  });

  /// Older ledger rows, after the first page carried by [myRewards].
  Future<PointsHistoryPage> rewardsHistory({
    required String cursor,
    int limit = 50,
  }) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/me/rewards/history',
      queryParameters: {'cursor': cursor, 'limit': limit},
    );
    return PointsHistoryPage.fromJson(r.data!);
  });

  /// The PDF of one of the caller's certificates. The API answers with a redirect to a
  /// short-lived presigned storage URL, fetched without any identity header (the Bearer token
  /// never leaves the API); an inline PDF answer is accepted too.
  Future<Uint8List> rewardCertificatePdf(String id) => guardApi(() async {
    final r = await _dio.get<List<int>>(
      '/api/v1/me/rewards/certificates/${Uri.encodeComponent(id)}',
      options: Options(
        responseType: ResponseType.bytes,
        followRedirects: false,
        validateStatus: (s) => s != null && s >= 200 && s < 400,
      ),
    );
    if (r.statusCode == 200) return Uint8List.fromList(r.data ?? const []);
    final location = r.headers.value('location');
    if (location == null) {
      throw ApiException(ApiErrorCode.server, statusCode: r.statusCode);
    }
    final target = Uri.parse(_dio.options.baseUrl).resolve(location);
    final pdf = await _dio.getUri<List<int>>(
      target,
      options: Options(
        responseType: ResponseType.bytes,
        headers: {'Accept': 'application/pdf'},
        extra: {kPublicEndpoint: true},
      ),
    );
    return Uint8List.fromList(pdf.data ?? const []);
  });
}

final apiProvider = Provider<EHimayaApi>(
  (ref) => EHimayaApi(ref.watch(apiDioProvider)),
);
