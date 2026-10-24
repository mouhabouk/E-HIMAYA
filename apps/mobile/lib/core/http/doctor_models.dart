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
  });

  final String id;
  final String? fullName;
  final DoctorKind kind;
  final List<DoctorSpecialty> specialties;
  final String workplace;
  final int gouvernoratCode;
  final bool available;

  factory DirectoryDoctor.fromJson(Map<String, Object?> json) =>
      DirectoryDoctor(
        id: json['id']! as String,
        fullName: json['full_name'] as String?,
        kind: DoctorKind.fromWire(json['kind'] as String?),
        specialties: _specialties(json['specialties']),
        workplace: json['workplace'] as String? ?? '',
        gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt() ?? 0,
        available: json['available'] == true,
      );
}
