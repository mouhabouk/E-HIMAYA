import 'package:flutter/widgets.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../features/institution/org_text.dart';
import '../../l10n/app_localizations.dart';
import 'prevention_models.dart';

/// Words of the prevention grid on the phone (phase P4c): the same as the dashboard's.

/// The order of the grid's sections, as the server builds it.
const visitSections = [
  'building',
  'classification',
  'hazmat',
  'equipment',
  'evacuation',
  'safety_team',
  'documents',
  'site',
];

/// Reason chips of a non-conformity (design §8.3).
const findingReasons = [
  'missing',
  'broken',
  'expired',
  'blocked',
  'insufficient',
  'not_as_plan',
];

/// Who signs for the institution, and the attendees' chips.
const representativeRoles = [
  'director',
  'safety_officer',
  'manager',
  'guard',
  'technician',
];

/// Reasons offered for a refusal.
const refusalReasons = ['danger', 'exits', 'equipment', 'documents'];

String sectionLabel(AppLocalizations l10n, String section) => switch (section) {
  'equipment' => l10n.prevSectionEquipment,
  'site' => l10n.prevSectionSite,
  _ => certificateSectionText(l10n, section),
};

String itemLabel(AppLocalizations l10n, String key) {
  final dot = key.indexOf('.');
  final section = dot < 0 ? key : key.substring(0, dot);
  final field = dot < 0 ? '' : key.substring(dot + 1);
  if (section == 'hazmat') {
    return l10n.prevItemHazmat((int.tryParse(field) ?? 0) + 1);
  }
  if (section == 'equipment') return equipmentKindText(l10n, field);
  return switch (key) {
    'building.capacity' => l10n.prevItemCapacity,
    'building.floors' => l10n.prevItemFloors,
    'building.height_m' => l10n.prevItemHeight,
    'building.address' => l10n.prevItemAddress,
    'classification.family' => l10n.prevItemFamily,
    'classification.category' => l10n.prevItemCategory,
    'evacuation.points' => l10n.prevItemEvacuation,
    'safety_team.representative' => l10n.prevItemRepresentative,
    'safety_team.members' => l10n.prevItemMembers,
    'documents.safety_file' => l10n.prevItemSafetyFile,
    'documents.safety_plan' => l10n.prevItemSafetyPlan,
    'site.exits' => l10n.prevItemExits,
    'site.signage' => l10n.prevItemSignage,
    'site.emergency_lighting' => l10n.prevItemLighting,
    'site.alarm' => l10n.prevItemAlarm,
    'site.extinguishers_access' => l10n.prevItemExtinguishers,
    'site.electrical' => l10n.prevItemElectrical,
    _ => key,
  };
}

/// What the institution declared for an item, in words (null for the site checks).
String? declaredText(AppLocalizations l10n, ChecklistItem item) {
  final v = item.declared;
  if (item.section == 'site') return null;
  if (v == null) return l10n.prevDeclaredNone;
  if (item.key == 'classification.family') {
    return switch (v) {
      'high_rise' => l10n.orgFamilyHighRise,
      'industrial' => l10n.orgFamilyIndustrial,
      'erp' => l10n.orgFamilyErp,
      'workplace' => l10n.orgFamilyWorkplace,
      _ => '$v',
    };
  }
  if (v is bool) return v ? l10n.prevYes : l10n.prevNo;
  if (v is double && v == v.roundToDouble()) return '${v.toInt()}';
  return '$v';
}

String reasonLabel(AppLocalizations l10n, String reason) => switch (reason) {
  'missing' => l10n.prevReasonMissing,
  'broken' => l10n.prevReasonBroken,
  'expired' => l10n.prevReasonExpired,
  'blocked' => l10n.prevReasonBlocked,
  'insufficient' => l10n.prevReasonInsufficient,
  'not_as_plan' => l10n.prevReasonNotAsPlan,
  _ => reason,
};

String roleLabel(AppLocalizations l10n, String role) => switch (role) {
  'director' => l10n.prevRoleDirector,
  'safety_officer' => l10n.prevRoleSafetyOfficer,
  'manager' => l10n.prevRoleManager,
  'guard' => l10n.prevRoleGuard,
  'technician' => l10n.prevRoleTechnician,
  _ => role,
};

String refusalLabel(AppLocalizations l10n, String reason) => switch (reason) {
  'danger' => l10n.prevRefuseDanger,
  'exits' => l10n.prevRefuseExits,
  'equipment' => l10n.prevRefuseEquipment,
  'documents' => l10n.prevRefuseDocuments,
  _ => reason,
};

String resultLabel(AppLocalizations l10n, Finding f) => switch (f) {
  Finding.conform => l10n.prevResultConform,
  Finding.nonconform => l10n.prevResultNonconform,
  Finding.notChecked => l10n.prevResultNotChecked,
};

/// The note sent for a non-conformity: the reason chips, then the inspector's words.
String findingNote(AppLocalizations l10n, ItemDraft d) => [
  ...d.reasons.map((r) => reasonLabel(l10n, r)),
  if (d.note != null && d.note!.isNotEmpty) d.note!,
].join('، ');

/// A non-conformity needs what was seen: a reason, a count or a note (the server's rule).
bool needsDetail(ItemDraft d) =>
    d.result == Finding.nonconform &&
    d.count == null &&
    d.reasons.isEmpty &&
    (d.note == null || d.note!.isEmpty);

String visitErrorLabel(AppLocalizations l10n, String code) => switch (code) {
  'visit_taken' => l10n.prevErrTaken,
  'too_many_photos' => l10n.prevErrTooManyPhotos,
  'invalid_signature' => l10n.prevErrSignature,
  'invalid_valid_until' => l10n.prevErrValidUntil,
  'invalid_transition' => l10n.prevErrState,
  'media_too_large' => l10n.staffErrTooLarge,
  'unsupported_media_type' ||
  'type_mismatch' ||
  'empty_file' => l10n.staffErrBadMedia,
  _ => l10n.staffErrGeneric,
};

/// A visit's day in the app's language («28 oct. 2026», «28 أكتوبر 2026»…).
String visitDay(BuildContext context, DateTime d) =>
    DateFormat.yMMMd(Localizations.localeOf(context).languageCode).format(d);

String isoDay(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// [months] after [from], on the same day of the month or the month's last day.
DateTime addMonths(DateTime from, int months) {
  final m = from.month - 1 + months;
  final y = from.year + m ~/ 12;
  final month = m % 12 + 1;
  final last = DateTime(y, month + 1, 0).day;
  return DateTime(y, month, from.day > last ? last : from.day);
}
