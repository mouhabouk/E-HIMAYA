// covers: phase C1-a (docs/phase-c/design-medical-axis.md §2)
import 'package:ehimaya/core/http/doctor_models.dart';
import 'package:ehimaya/core/http/volunteer_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('a volunteer doctor never sends Civil Protection numbers', () {
    final body = const DoctorInput(
      kind: DoctorKind.volunteer,
      specialties: {DoctorSpecialty.pediatrics, DoctorSpecialty.cardiology},
      licenceNo: ' TN-1 ',
      workplace: ' Clinique ',
      gouvernoratCode: 61,
      cpUnit: 'Unit',
      cpStaffNo: 'PC/1',
      version: 3,
    ).toJson();
    expect(body, {
      'kind': 'volunteer',
      // In the server's order, whatever the order of selection.
      'specialties': ['cardiology', 'pediatrics'],
      'licence_no': 'TN-1',
      'workplace': 'Clinique',
      'gouvernorat_code': 61,
      'cp_unit': null,
      'cp_staff_no': null,
      'terms_version': doctorTermsVersion,
      'version': 3,
    });
  });

  test('reads a registration and skips unknown specialties', () {
    final d = Doctor.fromJson({
      'kind': 'civil_protection',
      'status': 'approved',
      'specialties': ['toxicology', 'future_specialty'],
      'workplace': 'DR Sfax',
      'gouvernorat_code': 61,
      'submitted_at': '2026-10-24T08:00:00Z',
      'available': true,
      'available_until': '2026-10-24T16:00:00Z',
      'version': 2,
    });
    expect(d.kind, DoctorKind.civilProtection);
    expect(d.status, VolunteerStatus.approved);
    expect(d.specialties, [DoctorSpecialty.toxicology]);
    expect(d.isAvailableAt(DateTime.utc(2026, 10, 24, 15)), isTrue);
    expect(d.isAvailableAt(DateTime.utc(2026, 10, 24, 17)), isFalse);
  });

  test('registration numbers', () {
    for (final ok in ['TN-12345', '4521', 'PC/45-21']) {
      expect(doctorNumberPattern.hasMatch(ok), isTrue, reason: ok);
    }
    for (final bad in ['12', 'TN 1', 'رقم123', 'a' * 31]) {
      expect(doctorNumberPattern.hasMatch(bad), isFalse, reason: bad);
    }
  });
}
