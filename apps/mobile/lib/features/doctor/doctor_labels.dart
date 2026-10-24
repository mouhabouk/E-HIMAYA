import '../../core/http/doctor_models.dart';
import '../../l10n/app_localizations.dart';

String doctorKindLabel(AppLocalizations l10n, DoctorKind k) => switch (k) {
  DoctorKind.volunteer => l10n.doctorKindVolunteer,
  DoctorKind.civilProtection => l10n.doctorKindCivilProtection,
};

String specialtyLabel(AppLocalizations l10n, DoctorSpecialty s) => switch (s) {
  DoctorSpecialty.generalPractice => l10n.specialtyGeneralPractice,
  DoctorSpecialty.emergencyMedicine => l10n.specialtyEmergencyMedicine,
  DoctorSpecialty.anesthesiaIcu => l10n.specialtyAnesthesiaIcu,
  DoctorSpecialty.cardiology => l10n.specialtyCardiology,
  DoctorSpecialty.pulmonology => l10n.specialtyPulmonology,
  DoctorSpecialty.neurology => l10n.specialtyNeurology,
  DoctorSpecialty.pediatrics => l10n.specialtyPediatrics,
  DoctorSpecialty.obstetricsGynecology => l10n.specialtyObstetricsGynecology,
  DoctorSpecialty.internalMedicine => l10n.specialtyInternalMedicine,
  DoctorSpecialty.endocrinology => l10n.specialtyEndocrinology,
  DoctorSpecialty.nephrology => l10n.specialtyNephrology,
  DoctorSpecialty.gastroenterology => l10n.specialtyGastroenterology,
  DoctorSpecialty.allergyImmunology => l10n.specialtyAllergyImmunology,
  DoctorSpecialty.infectiousDiseases => l10n.specialtyInfectiousDiseases,
  DoctorSpecialty.dermatologyBurns => l10n.specialtyDermatologyBurns,
  DoctorSpecialty.orthopedics => l10n.specialtyOrthopedics,
  DoctorSpecialty.generalSurgery => l10n.specialtyGeneralSurgery,
  DoctorSpecialty.psychiatry => l10n.specialtyPsychiatry,
  DoctorSpecialty.toxicology => l10n.specialtyToxicology,
  DoctorSpecialty.ophthalmology => l10n.specialtyOphthalmology,
  DoctorSpecialty.ent => l10n.specialtyEnt,
};
