import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'models.dart';

/// Result of `POST /api/v1/reports`: 201 (new) and 200 (same `client_uuid` replayed) are
/// handled the same way by the sync engine.
class CreateReportResult {
  const CreateReportResult(this.report, {required this.created});
  final ServerReport report;
  final bool created;
}

/// Typed access to the phase-2 API. Every method throws [ApiException] on failure.
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
}

final apiProvider = Provider<EHimayaApi>(
  (ref) => EHimayaApi(ref.watch(apiDioProvider)),
);
