/// DTOs of the doctors' space (phase C1-a, docs/phase-c/design-medical-axis.md §2).
library;

import 'volunteer_models.dart';

/// Version of the doctor's terms the app shows before the registration (server `TERMS_VERSION`).
const doctorTermsVersion = '1';

/// A volunteer doctor (gives an opinion on the files referred to them) or a Civil Protection
/// doctor (receives the files of their gouvernorat).
enum DoctorKind {
  volunteer('volunteer'),
  civilProtection('civil_protection');

  const DoctorKind(this.wire);
  final String wire;

  static DoctorKind fromWire(String? value) =>
      value == 'civil_protection' ? civilProtection : volunteer;
}

/// Specialties a doctor can declare (server `Specialty`).
enum DoctorSpecialty {
  generalPractice('general_practice'),
  emergencyMedicine('emergency_medicine'),
  anesthesiaIcu('anesthesia_icu'),
  cardiology('cardiology'),
  pulmonology('pulmonology'),
  neurology('neurology'),
  pediatrics('pediatrics'),
  obstetricsGynecology('obstetrics_gynecology'),
  internalMedicine('internal_medicine'),
  endocrinology('endocrinology'),
  nephrology('nephrology'),
  gastroenterology('gastroenterology'),
  allergyImmunology('allergy_immunology'),
  infectiousDiseases('infectious_diseases'),
  dermatologyBurns('dermatology_burns'),
  orthopedics('orthopedics'),
  generalSurgery('general_surgery'),
  psychiatry('psychiatry'),
  toxicology('toxicology'),
  ophthalmology('ophthalmology'),
  ent('ent');

  const DoctorSpecialty(this.wire);
  final String wire;

  /// At most this many per doctor.
  static const max = 4;

  static DoctorSpecialty? fromWire(String? value) {
    for (final s in values) {
      if (s.wire == value) return s;
    }
    return null;
  }
}

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

List<DoctorSpecialty> _specialties(Object? v) => [
  for (final s in (v as List? ?? const []))
    ?DoctorSpecialty.fromWire(s as String?),
];

/// `GET /api/v1/me/doctor`. The review statuses are the volunteers' ones.
class Doctor {
  const Doctor({
    required this.kind,
    required this.status,
    required this.specialties,
    required this.workplace,
    required this.gouvernoratCode,
    required this.submittedAt,
    required this.available,
    required this.version,
    this.licenceNo,
    this.cpUnit,
    this.cpStaffNo,
    this.reviewReason,
    this.reviewedAt,
    this.availableUntil,
    this.committeeUntil,
    this.hasKey = false,
  });

  final DoctorKind kind;
  final VolunteerStatus status;
  final List<DoctorSpecialty> specialties;
  final String? licenceNo;
  final String workplace;
  final int gouvernoratCode;
  final String? cpUnit;
  final String? cpStaffNo;
  final String? reviewReason;
  final DateTime submittedAt;
  final DateTime? reviewedAt;
  final bool available;
  final DateTime? availableUntil;

  /// End of the term on the national medical committee; null when not a member.
  final DateTime? committeeUntil;

  /// Phase C1-b: the doctor set their personal key (medical files can be locked for them).
  final bool hasKey;
  final int version;

  bool isAvailableAt(DateTime now) =>
      available && (availableUntil == null || availableUntil!.isAfter(now));

  factory Doctor.fromJson(Map<String, Object?> json) => Doctor(
    kind: DoctorKind.fromWire(json['kind'] as String?),
    status: VolunteerStatus.fromWire(json['status'] as String?),
    specialties: _specialties(json['specialties']),
    licenceNo: json['licence_no'] as String?,
    workplace: json['workplace'] as String? ?? '',
    gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt() ?? 0,
    cpUnit: json['cp_unit'] as String?,
    cpStaffNo: json['cp_staff_no'] as String?,
    reviewReason: json['review_reason'] as String?,
    submittedAt: _date(json['submitted_at']) ?? DateTime(1970),
    reviewedAt: _date(json['reviewed_at']),
    available: json['available'] == true,
    availableUntil: _date(json['available_until']),
    committeeUntil: _date(json['committee_until']),
    hasKey: json['has_key'] == true,
    version: (json['version'] as num?)?.toInt() ?? 1,
  );
}

/// Body of `PUT /api/v1/me/doctor`.
class DoctorInput {
  const DoctorInput({
    required this.kind,
    required this.specialties,
    required this.licenceNo,
    required this.workplace,
    required this.gouvernoratCode,
    this.cpUnit,
    this.cpStaffNo,
    this.version,
  });

  final DoctorKind kind;
  final Set<DoctorSpecialty> specialties;
  final String licenceNo;
  final String workplace;
  final int gouvernoratCode;
  final String? cpUnit;
  final String? cpStaffNo;
  final int? version;

  Map<String, Object?> toJson() {
    final civil = kind == DoctorKind.civilProtection;
    return {
      'kind': kind.wire,
      'specialties': [
        for (final s in DoctorSpecialty.values)
          if (specialties.contains(s)) s.wire,
      ],
      'licence_no': licenceNo.trim(),
      'workplace': workplace.trim(),
      'gouvernorat_code': gouvernoratCode,
      'cp_unit': civil ? cpUnit?.trim() : null,
      'cp_staff_no': civil ? cpStaffNo?.trim() : null,
      'terms_version': doctorTermsVersion,
      'version': ?version,
    };
  }
}

/// A registration or staff number: letters, digits, "-" and "/" (3 to 30).
final doctorNumberPattern = RegExp(r'^[A-Za-z0-9/-]{3,30}$');

/// One line of `GET /api/v1/doctors/directory` (no phone, no registration number).
class DirectoryDoctor {
  const DirectoryDoctor({
    required this.id,
    required this.kind,
    required this.specialties,
    required this.workplace,
    required this.gouvernoratCode,
    required this.available,
    this.fullName,
    this.publicKey,
  });

  final String id;
  final String? fullName;
  final DoctorKind kind;
  final List<DoctorSpecialty> specialties;
  final String workplace;
  final int gouvernoratCode;
  final bool available;

  /// Phase C1-c: what a referral locks the file key for (base64); null while the doctor has not
  /// set their key, and then they cannot be chosen.
  final String? publicKey;

  factory DirectoryDoctor.fromJson(Map<String, Object?> json) =>
      DirectoryDoctor(
        id: json['id']! as String,
        fullName: json['full_name'] as String?,
        kind: DoctorKind.fromWire(json['kind'] as String?),
        specialties: _specialties(json['specialties']),
        workplace: json['workplace'] as String? ?? '',
        gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt() ?? 0,
        available: json['available'] == true,
        publicKey: json['public_key'] as String?,
      );
}

/// Why a locked medical file reached the doctor (phase C1-b).
enum FileVia {
  gouvernorat('gouvernorat'),
  committee('committee'),
  referral('referral');

  const FileVia(this.wire);
  final String wire;

  static FileVia fromWire(String? v) =>
      values.firstWhere((e) => e.wire == v, orElse: () => gouvernorat);
}

/// One line of the doctor's inbox (`GET /api/v1/medical/files`).
class MedicalInboxItem {
  const MedicalInboxItem({
    required this.reportId,
    required this.trackingCode,
    required this.category,
    required this.receivedAt,
    required this.via,
    this.gouvernoratCode,
    this.openedAt,
  });

  final String reportId;
  final String trackingCode;
  final String category;
  final int? gouvernoratCode;
  final DateTime receivedAt;
  final FileVia via;
  final DateTime? openedAt;

  factory MedicalInboxItem.fromJson(Map<String, Object?> json) =>
      MedicalInboxItem(
        reportId: json['report_id']! as String,
        trackingCode: json['tracking_code'] as String? ?? '',
        category: json['category'] as String? ?? 'other',
        gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt(),
        receivedAt: _date(json['received_at']) ?? DateTime(1970),
        via: FileVia.fromWire(json['via'] as String?),
        openedAt: _date(json['opened_at']),
      );
}

/// A doctor's personal key as kept by the server: the public key and the private key locked by
/// the doctor's code (`GET /api/v1/me/doctor/key`).
class DoctorKeyBackup {
  const DoctorKeyBackup({required this.publicKey, required this.backup});

  final String publicKey;
  final Map<String, Object?> backup;

  factory DoctorKeyBackup.fromJson(Map<String, Object?> json) =>
      DoctorKeyBackup(
        publicKey: json['public_key']! as String,
        backup: (json['backup']! as Map).cast<String, Object?>(),
      );
}

/// A specialist a file was referred to (`GET /api/v1/medical/files/{id}/referrals`, phase C1-c).
class FileReferral {
  const FileReferral({
    required this.doctorId,
    required this.specialties,
    required this.workplace,
    required this.at,
    required this.mine,
    this.fullName,
  });

  final String doctorId;
  final String? fullName;
  final List<DoctorSpecialty> specialties;
  final String workplace;
  final DateTime at;

  /// Referred by this doctor.
  final bool mine;

  factory FileReferral.fromJson(Map<String, Object?> json) => FileReferral(
    doctorId: json['doctor_id']! as String,
    fullName: json['full_name'] as String?,
    specialties: _specialties(json['specialties']),
    workplace: json['workplace'] as String? ?? '',
    at: _date(json['at']) ?? DateTime(1970),
    mine: json['mine'] == true,
  );
}

/// A specialist's opinion locked for this doctor (`GET …/opinions`): [copy] is opened on the
/// phone like a file.
class LockedOpinion {
  const LockedOpinion({
    required this.id,
    required this.createdAt,
    required this.mine,
    required this.copy,
    this.specialty,
  });

  final String id;
  final DoctorSpecialty? specialty;
  final DateTime createdAt;
  final bool mine;
  final Map<String, Object?> copy;

  factory LockedOpinion.fromJson(Map<String, Object?> json) => LockedOpinion(
    id: json['id']! as String,
    specialty: DoctorSpecialty.fromWire(json['specialty'] as String?),
    createdAt: _date(json['created_at']) ?? DateTime(1970),
    mine: json['mine'] == true,
    copy: json,
  );
}

/// A committee member appointed after files (or opinions) this member holds were locked
/// (`GET /api/v1/medical/committee/pending`).
class PendingMember {
  const PendingMember({
    required this.doctorId,
    required this.publicKey,
    required this.files,
    required this.opinions,
    this.fullName,
  });

  final String doctorId;
  final String? fullName;
  final String publicKey;
  final List<String> files;

  /// Opinion id → its file.
  final Map<String, String> opinions;

  int get count => files.length + opinions.length;

  factory PendingMember.fromJson(Map<String, Object?> json) => PendingMember(
    doctorId: json['doctor_id']! as String,
    fullName: json['full_name'] as String?,
    publicKey: json['public_key']! as String,
    files: [for (final f in (json['files'] as List? ?? const [])) f as String],
    opinions: {
      for (final o in (json['opinions'] as List? ?? const []))
        (o as Map)['id'] as String: o['report_id'] as String,
    },
  );
}

/// Who saw the reporter's locked medical file, by role only (`GET /api/v1/me/medical/openings`).
enum OpeningRole { civilProtection, specialist, committee }

class MedicalOpening {
  const MedicalOpening({
    required this.reportId,
    required this.trackingCode,
    required this.referral,
    required this.role,
    required this.specialties,
    required this.at,
    this.gouvernoratCode,
    this.workplace,
  });

  final String reportId;
  final String trackingCode;

  /// A referral to a specialist (else an opening).
  final bool referral;
  final OpeningRole role;
  final int? gouvernoratCode;
  final List<DoctorSpecialty> specialties;
  final String? workplace;
  final DateTime at;

  factory MedicalOpening.fromJson(Map<String, Object?> json) => MedicalOpening(
    reportId: json['report_id']! as String,
    trackingCode: json['tracking_code'] as String? ?? '',
    referral: json['kind'] == 'referral',
    role: switch (json['role']) {
      'civil_protection' => OpeningRole.civilProtection,
      'specialist' => OpeningRole.specialist,
      _ => OpeningRole.committee,
    },
    gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt(),
    specialties: _specialties(json['specialties']),
    workplace: json['workplace'] as String?,
    at: _date(json['at']) ?? DateTime(1970),
  );
}
