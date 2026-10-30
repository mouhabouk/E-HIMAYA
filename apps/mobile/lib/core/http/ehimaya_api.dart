import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/beaches/beach_models.dart';
import '../../features/contact/contact_models.dart';
import '../../features/guide/guide_models.dart';
import '../../features/places/places_models.dart';
import '../../features/safety/safety_models.dart';
import '../quota/anon_quota.dart';
import 'api_client.dart';
import 'api_error.dart';
import 'availability_models.dart';
import 'doctor_models.dart';
import 'email_status.dart';
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

/// A place timed on the road (phase L1b): metres, seconds and the engine (`fallback`: estimate).
class RoadTime {
  const RoadTime(this.metres, this.seconds, this.engine);
  final int metres;
  final int seconds;
  final String? engine;

  bool get estimated => engine == null || engine == 'fallback';
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

  /// Registers an institution (phase 4 §1, from the app since P2a): it stays under review.
  Future<OrgCardData> registerOrg(Map<String, Object?> card) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '/api/v1/orgs',
          data: card,
        );
        return OrgCardData(r.data!);
      });

  /// The full card (any member), with `version` for the next edit.
  Future<OrgCardData> orgCard(String orgId) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(_org(orgId));
    return OrgCardData(r.data!);
  });

  /// Saves the card (admin or editor); `409 version_conflict` when someone saved in between.
  Future<OrgCardData> updateOrg(String orgId, Map<String, Object?> body) =>
      guardApi(() async {
        final r = await _dio.put<Map<String, Object?>>(_org(orgId), data: body);
        return OrgCardData(r.data!);
      });

  Future<List<OrgEquipment>> orgEquipment(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/equipment');
    return [
      for (final e in r.data!)
        if (e is Map<String, Object?>) OrgEquipment(e),
    ];
  });

  Future<OrgEquipment> updateEquipment(
    String orgId,
    String itemId,
    Map<String, Object?> body,
  ) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '${_org(orgId)}/equipment/${Uri.encodeComponent(itemId)}',
      data: body,
    );
    return OrgEquipment(r.data!);
  });

  Future<List<OrgFeature>> orgFeatures(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/features');
    return [
      for (final f in r.data!)
        if (f is Map<String, Object?>) OrgFeature.fromJson(f),
    ];
  });

  Future<List<OrgCertificate>> orgCertificates(String orgId) =>
      guardApi(() async {
        final r = await _dio.get<List<Object?>>('${_org(orgId)}/certificates');
        return [
          for (final c in r.data!)
            if (c is Map<String, Object?>) OrgCertificate.fromJson(c),
        ];
      });

  Future<List<OrgMember>> orgMembers(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/members');
    return [
      for (final m in r.data!)
        if (m is Map<String, Object?>) OrgMember.fromJson(m),
    ];
  });

  /// Invites a member by e-mail (admin only).
  Future<void> inviteOrgMember(String orgId, String email, String role) =>
      guardApi(() async {
        await _dio.post<Object?>(
          '${_org(orgId)}/invitations',
          data: {'email': email, 'role': role},
        );
      });

  // ---- Phase P2b: Office messages, awareness, drills and events, maintenance log ----

  Future<List<OrgMessage>> orgMessages(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/messages');
    return [
      for (final m in r.data!)
        if (m is Map<String, Object?>) OrgMessage.fromJson(m),
    ];
  });

  Future<OrgMessage> ackOrgMessage(String orgId, String messageId) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '${_org(orgId)}/messages/${Uri.encodeComponent(messageId)}/ack',
        );
        return OrgMessage.fromJson(r.data!);
      });

  Future<List<SafetyTip>> orgAwareness(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/awareness');
    return [
      for (final t in r.data!)
        if (t is Map<String, Object?>) SafetyTip.fromJson(t),
    ];
  });

  Future<List<OrgActivity>> orgActivities(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/activities');
    return [
      for (final a in r.data!)
        if (a is Map<String, Object?>) OrgActivity.fromJson(a),
    ];
  });

  Future<OrgActivity> addOrgActivity(String orgId, Map<String, Object?> body) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '${_org(orgId)}/activities',
          data: body,
        );
        return OrgActivity.fromJson(r.data!);
      });

  Future<void> deleteOrgActivity(String orgId, String activityId) =>
      guardApi(() async {
        await _dio.delete<Object?>(
          '${_org(orgId)}/activities/${Uri.encodeComponent(activityId)}',
        );
      });

  Future<List<OrgMaintenance>> equipmentMaintenance(
    String orgId,
    String itemId,
  ) => guardApi(() async {
    final r = await _dio.get<List<Object?>>(
      '${_org(orgId)}/equipment/${Uri.encodeComponent(itemId)}/maintenance',
    );
    return [
      for (final m in r.data!)
        if (m is Map<String, Object?>) OrgMaintenance.fromJson(m),
    ];
  });

  Future<OrgMaintenance> addMaintenance(
    String orgId,
    String itemId, {
    required DateTime doneOn,
    String? note,
    String? documentId,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '${_org(orgId)}/equipment/${Uri.encodeComponent(itemId)}/maintenance',
      data: {
        'done_on': isoDay(doneOn),
        'note': note,
        'document_id': documentId,
      },
    );
    return OrgMaintenance.fromJson(r.data!);
  });

  /// Creates an institution document (here a `maintenance_photo`) and returns its id; the
  /// file itself goes through tus with `target=org_document`.
  Future<String> createOrgDocument(String orgId, String kind, String title) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '${_org(orgId)}/documents',
          data: {'kind': kind, 'title': title},
        );
        return r.data!['id']! as String;
      });

  /// Prevention visits of the institution, newest first (phase P3b).
  Future<List<PreventionVisit>> orgVisits(String orgId) => guardApi(() async {
    final r = await _dio.get<List<Object?>>('${_org(orgId)}/prevention/visits');
    return [
      for (final v in r.data!)
        if (v is Map<String, Object?>) PreventionVisit.fromJson(v),
    ];
  });

  /// Short-lived link to the visit report (procès-verbal) PDF.
  Future<Uri> visitReportUrl(String orgId, String visitId) => _download(
    '${_org(orgId)}/prevention/visits/${Uri.encodeComponent(visitId)}/report',
  );

  /// Short-lived link to a certificate PDF (safety or prevention).
  Future<Uri> certificatePdfUrl(String orgId, String certificateId) =>
      _download(
        '${_org(orgId)}/certificates/${Uri.encodeComponent(certificateId)}/pdf',
      );

  Future<Uri> _download(String path) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(path);
    return Uri.parse(_dio.options.baseUrl).resolve(r.data!['url']! as String);
  });

  /// The year's activity of the institution (phase P3b §7).
  Future<AnnualReport> annualReport(String orgId, int year) =>
      guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>(
          '${_org(orgId)}/annual-report',
          queryParameters: {'year': year},
        );
        return AnnualReport.fromJson(r.data!);
      });

  static String _org(String orgId) =>
      '/api/v1/orgs/${Uri.encodeComponent(orgId)}';

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

  // ---------------------------------------------------------------- availability calendar (phase N §8)

  Future<AvailabilityCalendar> myAvailability(CalendarRole role) =>
      guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>(
          '/api/v1/me/availability',
          queryParameters: {'role': role.wire},
        );
        return AvailabilityCalendar.fromJson(r.data!);
      });

  /// The whole calendar at once: every slot the person keeps.
  Future<AvailabilityCalendar> putAvailability(
    CalendarRole role,
    List<AvailabilitySlot> slots,
  ) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '/api/v1/me/availability',
      queryParameters: {'role': role.wire},
      data: {
        'slots': [for (final s in slots) s.toJson()],
      },
    );
    return AvailabilityCalendar.fromJson(r.data!);
  });

  // ---------------------------------------------------------------- doctors (phase C1-a)

  /// The account's doctor registration, or null when there is none (`404 not_doctor`).
  Future<Doctor?> myDoctor() async {
    try {
      return await guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>('/api/v1/me/doctor');
        return Doctor.fromJson(r.data!);
      });
    } on ApiException catch (e) {
      if (e.code == ApiErrorCode.notDoctor) return null;
      rethrow;
    }
  }

  Future<Doctor> putDoctor(DoctorInput input) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '/api/v1/me/doctor',
      data: input.toJson(),
    );
    return Doctor.fromJson(r.data!);
  });

  Future<void> withdrawDoctor() => guardApi(() async {
    await _dio.delete<Object?>('/api/v1/me/doctor');
  });

  /// Available for [hours] (approved doctors only), or not available.
  Future<Doctor> setDoctorAvailability({
    required bool available,
    int hours = 8,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/me/doctor/availability',
      data: {'available': available, 'hours': hours},
    );
    return Doctor.fromJson(r.data!);
  });

  /// Approved doctors by specialty and gouvernorat: available first, then the caller's group.
  /// Phase C1-b: the doctors a medical file is locked for at this place (public keys only).
  Future<Map<String, List<int>>> medicalRecipients(GeoPoint at) =>
      guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>(
          '/api/v1/medical/recipients',
          queryParameters: {
            'lat': at.lat,
            'lon': at.lon,
            'accuracy_m': ?at.accuracyM,
          },
        );
        return {
          for (final x in (r.data!['recipients'] as List? ?? const []))
            (x as Map)['doctor_id'] as String: base64.decode(
              x['public_key'] as String,
            ),
        };
      });

  Future<DoctorKeyBackup?> doctorKey() async {
    try {
      return await guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>('/api/v1/me/doctor/key');
        return DoctorKeyBackup.fromJson(r.data!);
      });
    } on ApiException catch (e) {
      if (e.code == ApiErrorCode.doctorKeyMissing) return null;
      rethrow;
    }
  }

  Future<Doctor> putDoctorKey(String publicKey, Map<String, Object?> backup) =>
      guardApi(() async {
        final r = await _dio.put<Map<String, Object?>>(
          '/api/v1/me/doctor/key',
          data: {'public_key': publicKey, 'backup': backup},
        );
        return Doctor.fromJson(r.data!);
      });

  Future<List<MedicalInboxItem>> medicalFiles() => guardApi(() async {
    final r = await _dio.get<List<Object?>>('/api/v1/medical/files');
    return [
      for (final x in r.data!)
        MedicalInboxItem.fromJson((x! as Map).cast<String, Object?>()),
    ];
  });

  /// The doctor's copy of a locked file (recorded; a committee member gives [reason]).
  Future<Map<String, Object?>> openMedicalFile(
    String reportId, {
    String? reason,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/medical/files/$reportId/open',
      data: {'reason': ?reason},
    );
    return r.data!;
  });

  // ---------------------------------------------------------------- phase C1-c

  /// Who the file went to (the gouvernorat group and the committee only).
  Future<List<FileReferral>> fileReferrals(String reportId) =>
      guardApi(() async {
        final r = await _dio.get<List<Object?>>(
          '/api/v1/medical/files/$reportId/referrals',
        );
        return [
          for (final x in r.data!)
            FileReferral.fromJson((x! as Map).cast<String, Object?>()),
        ];
      });

  /// Refers the file: its key locked on this phone for each specialist ([keys]).
  Future<void> referMedicalFile(
    String reportId, {
    required String reason,
    required List<Map<String, Object?>> keys,
  }) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/medical/files/$reportId/referrals',
      data: {'reason': reason, 'keys': keys},
    );
  });

  /// Who a specialist's opinion is locked for (raw public keys).
  Future<Map<String, List<int>>> opinionRecipients(String reportId) => guardApi(
    () async {
      final r = await _dio.get<List<Object?>>(
        '/api/v1/medical/files/$reportId/opinion-recipients',
      );
      return {
        for (final x in r.data!.cast<Map<String, Object?>>())
          x['doctor_id']! as String: base64.decode(x['public_key']! as String),
      };
    },
  );

  Future<void> addOpinion(
    String reportId,
    Map<String, Object?> locked, {
    String? specialty,
  }) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/medical/files/$reportId/opinions',
      data: {...locked, 'specialty': ?specialty},
    );
  });

  Future<List<LockedOpinion>> medicalOpinions(String reportId) =>
      guardApi(() async {
        final r = await _dio.get<List<Object?>>(
          '/api/v1/medical/files/$reportId/opinions',
        );
        return [
          for (final x in r.data!)
            LockedOpinion.fromJson((x! as Map).cast<String, Object?>()),
        ];
      });

  Future<List<PendingMember>> committeePending() => guardApi(() async {
    final r = await _dio.get<List<Object?>>(
      '/api/v1/medical/committee/pending',
    );
    return [
      for (final x in r.data!)
        PendingMember.fromJson((x! as Map).cast<String, Object?>()),
    ];
  });

  /// A file's ([opinionId] null) or an opinion's key locked for new committee members.
  Future<void> shareMedicalKey({
    String? reportId,
    String? opinionId,
    required String reason,
    required List<Map<String, Object?>> keys,
  }) => guardApi(() async {
    await _dio.post<Object?>(
      opinionId != null
          ? '/api/v1/medical/opinions/$opinionId/keys'
          : '/api/v1/medical/files/$reportId/keys',
      data: {'reason': reason, 'keys': keys},
    );
  });

  /// Who saw the reporter's locked medical file (by role only).
  Future<List<MedicalOpening>> myMedicalOpenings({String? reportId}) =>
      guardApi(() async {
        final r = await _dio.get<List<Object?>>(
          '/api/v1/me/medical/openings',
          queryParameters: {'report_id': ?reportId},
        );
        return [
          for (final x in r.data!)
            MedicalOpening.fromJson((x! as Map).cast<String, Object?>()),
        ];
      });

  Future<List<DirectoryDoctor>> doctorDirectory({
    DoctorSpecialty? specialty,
    int? gouvernoratCode,
  }) => guardApi(() async {
    final r = await _dio.get<List<Object?>>(
      '/api/v1/doctors/directory',
      queryParameters: {
        'specialty': ?specialty?.wire,
        'gouvernorat_code': ?gouvernoratCode,
      },
    );
    return [
      for (final d in r.data!)
        if (d is Map<String, Object?>) DirectoryDoctor.fromJson(d),
    ];
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
    bool teamNotices = true,
    GeoPoint? position,
  }) => guardApi(() async {
    await _dio.put<Object?>(
      '/api/v1/devices',
      data: {
        'token': token,
        'platform': platform,
        'locale': locale,
        'location_alerts': locationAlerts,
        'team_notices': teamNotices,
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

  /// Phase L1b: the nearest places of a layer timed on the road (`road`: the routing engine, or
  /// its estimate). Id → (metres, seconds); empty when the server has no road time.
  Future<Map<String, RoadTime>> roadNearest(
    String key,
    GeoPoint from, {
    int limit = 3,
  }) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/layers/${Uri.encodeComponent(key)}/features',
      queryParameters: {
        'near': '${from.lat},${from.lon}',
        'limit': limit,
        'road': 'true',
      },
      options: Options(extra: {kPublicEndpoint: true}),
    );
    return {
      if (r.data?['items'] case final List<Object?> items)
        for (final i in items)
          if (i case {
            'id': final Object id,
            'road_m': final num m,
            'road_s': final num s,
          })
            '$id': RoadTime(m.toInt(), s.toInt(), i['road_engine'] as String?),
    };
  });

  /// Phase L1b: today's drowning risk of every beach (public, cached 15 minutes by the server).
  Future<BeachesReport> coastalBeaches() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/coastal/beaches',
      options: Options(extra: {kPublicEndpoint: true}),
    );
    return BeachesReport.fromJson(r.data!);
  });

  /// The four days of a beach and its card.
  Future<BeachDetail> coastalBeach(String id) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/coastal/beaches/${Uri.encodeComponent(id)}',
      options: Options(extra: {kPublicEndpoint: true}),
    );
    return BeachDetail.fromJson(r.data!);
  });

  /// "I am at this beach": a random code of the day, no account and no position.
  Future<void> coastalPresence(String id, String token) => guardApi(() async {
    await _dio.post<void>(
      '/api/v1/coastal/beaches/${Uri.encodeComponent(id)}/presence',
      data: {'token': token},
      options: Options(extra: {kPublicEndpoint: true}),
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

  // ---------------------------------------------------------------- app rating and work e-mail (phase P5b)

  /// Rates the app from 1 to 5 stars (F-APP-143); any reporter, at most three a day.
  Future<void> rateApp({
    required int stars,
    String? remark,
    String? platform,
    int? build,
    String? version,
    required String locale,
  }) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/app/feedback',
      data: {
        'stars': stars,
        if (remark != null && remark.trim().isNotEmpty) 'remark': remark.trim(),
        'platform': ?platform,
        'build': ?build,
        'version': ?version,
        'locale': locale,
      },
    );
  });

  /// The work e-mail of the signed-in account and whether it is proven (F-APP-12).
  Future<EmailStatus> myEmail() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/me/email');
    return EmailStatus.fromJson(r.data!);
  });

  /// Sends a 6-digit code to [email], valid 10 minutes.
  Future<void> sendEmailCode(String email, String locale) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/me/email/code',
      data: {'email': email, 'locale': locale},
    );
  });

  /// Confirms the address with the code it received.
  Future<EmailStatus> verifyEmailCode(String code) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/me/email/verify',
      data: {'code': code},
    );
    return EmailStatus.fromJson(r.data!);
  });

  // ---------------------------------------------------------------- personal safety (phase B2)

  /// A code (`ABCD-EFGH`, 48 h, single use) the user gives a relative who also uses e-Himaya.
  Future<InvitationCode> createInvitation() => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/invitations',
    );
    return InvitationCode.fromJson(r.data!);
  });

  /// Who invited (first name and the last two digits of their phone), before accepting.
  Future<InvitationPreview> previewInvitation(String code) =>
      guardApi(() async {
        final r = await _dio.get<Map<String, Object?>>(
          '/api/v1/safety/invitations/${Uri.encodeComponent(code)}',
        );
        return InvitationPreview.fromJson(r.data!);
      });

  Future<SafetyLink> acceptInvitation(String code) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/invitations/${Uri.encodeComponent(code)}/accept',
    );
    return SafetyLink.fromJson(r.data!);
  });

  Future<List<SafetyLink>> safetyLinks() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/safety/links');
    return [
      for (final i in r.data!['items']! as List)
        SafetyLink.fromJson(i as Map<String, Object?>),
    ];
  });

  Future<void> removeSafetyLink(String id) => guardApi(() async {
    await _dio.delete<Object?>(
      '/api/v1/safety/links/${Uri.encodeComponent(id)}',
    );
  });

  /// Rings the linked contacts ([linkIds] null: all of them). Returns the alert id and how many
  /// were reached. Idempotent by [clientUuid].
  Future<({String id, int recipients})> sendSafetyAlert({
    required String clientUuid,
    required String message,
    GeoPoint? location,
    int? battery,
    List<String>? linkIds,
    String? liveShareId,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/alerts',
      data: {
        'client_uuid': clientUuid,
        'message': message,
        if (location != null && location.isInTunisiaBox)
          'location': location.toJson(),
        'battery': ?battery,
        'link_ids': ?linkIds,
        'live_share_id': ?liveShareId,
      },
    );
    return (
      id: r.data!['id']! as String,
      recipients: r.data!['recipients']! as int,
    );
  });

  Future<List<SafetyAlertView>> safetyAlerts() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/safety/alerts');
    return [
      for (final i in r.data!['items']! as List)
        SafetyAlertView.fromJson(i as Map<String, Object?>),
    ];
  });

  Future<SafetyAlertView> safetyAlert(String id) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/safety/alerts/${Uri.encodeComponent(id)}',
    );
    return SafetyAlertView.fromJson(r.data!);
  });

  Future<void> markSafetyAlertSeen(String id) => guardApi(() async {
    await _dio.post<Object?>(
      '/api/v1/safety/alerts/${Uri.encodeComponent(id)}/seen',
    );
  });

  Future<LiveShareStart> startLiveShare(int minutes) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/live',
      data: {'minutes': minutes},
    );
    return LiveShareStart.fromJson(r.data!);
  });

  Future<LiveState> putLivePosition(
    String id,
    GeoPoint position, {
    int? battery,
  }) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '/api/v1/safety/live/${Uri.encodeComponent(id)}',
      data: {'location': position.toJson(), 'battery': ?battery},
    );
    return LiveState.fromJson(r.data!);
  });

  Future<LiveState> stopLiveShare(String id) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/live/${Uri.encodeComponent(id)}/stop',
    );
    return LiveState.fromJson(r.data!);
  });

  /// A share the user owns, or one attached to an alert they received.
  Future<LiveState> liveShare(String id) => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>(
      '/api/v1/safety/live/${Uri.encodeComponent(id)}',
    );
    return LiveState.fromJson(r.data!);
  });

  Future<SafetyCheckState> startSafetyCheck({
    required int minutes,
    required String message,
    GeoPoint? location,
    int? battery,
  }) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/checks',
      data: {
        'minutes': minutes,
        'message': message,
        if (location != null && location.isInTunisiaBox)
          'location': location.toJson(),
        'battery': ?battery,
      },
    );
    return SafetyCheckState.fromJson(r.data!);
  });

  Future<SafetyCheckState?> currentSafetyCheck() => guardApi(() async {
    final r = await _dio.get<Object?>('/api/v1/safety/checks/current');
    final data = r.data;
    return data is Map<String, Object?>
        ? SafetyCheckState.fromJson(data)
        : null;
  });

  Future<SafetyCheckState> safetyCheckOk(String id) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/checks/${Uri.encodeComponent(id)}/ok',
    );
    return SafetyCheckState.fromJson(r.data!);
  });

  Future<SafetyCheckState> extendSafetyCheck(String id, int minutes) =>
      guardApi(() async {
        final r = await _dio.post<Map<String, Object?>>(
          '/api/v1/safety/checks/${Uri.encodeComponent(id)}/extend',
          data: {'minutes': minutes},
        );
        return SafetyCheckState.fromJson(r.data!);
      });

  Future<void> putSafetyCheckPosition(
    String id,
    GeoPoint position, {
    int? battery,
  }) => guardApi(() async {
    await _dio.put<Object?>(
      '/api/v1/safety/checks/${Uri.encodeComponent(id)}/position',
      data: {'location': position.toJson(), 'battery': ?battery},
    );
  });

  Future<HistoryState> locationHistory() => guardApi(() async {
    final r = await _dio.get<Map<String, Object?>>('/api/v1/safety/history');
    return HistoryState.fromJson(r.data!);
  });

  Future<HistoryState> setLocationHistory({
    required bool enabled,
    int hours = 72,
    String? noticeVersion,
    String locale = 'ar',
  }) => guardApi(() async {
    final r = await _dio.put<Map<String, Object?>>(
      '/api/v1/safety/history',
      data: {
        'enabled': enabled,
        'hours': hours,
        'notice_version': ?noticeVersion,
        'locale': locale,
      },
    );
    return HistoryState.fromJson(r.data!);
  });

  Future<int> postHistoryPoints(List<SafetyPoint> points) => guardApi(() async {
    final r = await _dio.post<Map<String, Object?>>(
      '/api/v1/safety/history/points',
      data: {
        'points': [
          for (final p in points)
            {
              'location': p.point.toJson(),
              'at': p.at.toUtc().toIso8601String(),
            },
        ],
      },
    );
    return r.data!['stored']! as int;
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
