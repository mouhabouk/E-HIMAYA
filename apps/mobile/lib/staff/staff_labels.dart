import 'package:flutter/material.dart';

import '../core/ui/tokens.dart';
import '../l10n/app_localizations.dart';
import 'staff_models.dart';

String vehicleKindLabel(AppLocalizations l10n, String kind) => switch (kind) {
  'fire_engine' => l10n.staffKindFireEngine,
  'water_tanker' => l10n.staffKindWaterTanker,
  'ambulance' => l10n.staffKindAmbulance,
  'rescue_vehicle' => l10n.staffKindRescue,
  'heavy_equipment' => l10n.staffKindHeavy,
  'drone' => l10n.staffKindDrone,
  'large_extinguisher' => l10n.staffKindExtinguisher,
  'boat' => l10n.staffKindBoat,
  'command_vehicle' => l10n.staffKindCommand,
  _ => l10n.staffKindOther,
};

IconData vehicleKindIcon(String kind) => switch (kind) {
  'fire_engine' || 'water_tanker' || 'large_extinguisher' => Icons.fire_truck,
  'ambulance' => Icons.emergency,
  'boat' => Icons.directions_boat,
  'drone' => Icons.flight,
  'heavy_equipment' => Icons.construction,
  'command_vehicle' => Icons.hub,
  _ => Icons.local_shipping,
};

String missionStatusLabel(AppLocalizations l10n, MissionStatus s) =>
    switch (s) {
      MissionStatus.ordered => l10n.staffStatusOrdered,
      MissionStatus.enRoute => l10n.staffStatusEnRoute,
      MissionStatus.onScene => l10n.staffStatusOnScene,
      MissionStatus.released => l10n.staffStatusReleased,
      MissionStatus.cancelled => l10n.staffStatusCancelled,
    };

Tone missionStatusTone(MissionStatus s) => switch (s) {
  MissionStatus.ordered => Tone.red,
  MissionStatus.enRoute => Tone.orange,
  MissionStatus.onScene => Tone.purple,
  MissionStatus.released => Tone.green,
  MissionStatus.cancelled => Tone.slate,
};

String counterLabel(AppLocalizations l10n, CasualtyCounter c) => switch (c) {
  CasualtyCounter.injuredLight => l10n.staffInjuredLight,
  CasualtyCounter.injuredSerious => l10n.staffInjuredSerious,
  CasualtyCounter.deceased => l10n.staffDeceased,
  CasualtyCounter.rescued => l10n.staffRescued,
  CasualtyCounter.trapped => l10n.staffTrapped,
};

Tone counterTone(CasualtyCounter c) => switch (c) {
  CasualtyCounter.injuredLight => Tone.amber,
  CasualtyCounter.injuredSerious => Tone.red,
  CasualtyCounter.deceased => Tone.slate,
  CasualtyCounter.rescued => Tone.green,
  CasualtyCounter.trapped => Tone.orange,
};

String backupLabel(AppLocalizations l10n, String kind) => switch (kind) {
  'fire_engine' => l10n.staffBackupFireEngine,
  'ambulance' => l10n.staffBackupAmbulance,
  'extrication' => l10n.staffBackupExtrication,
  'ladder' => l10n.staffBackupLadder,
  'water_tanker' => l10n.staffBackupWaterTanker,
  'hazmat' => l10n.staffBackupHazmat,
  'police' => l10n.staffBackupPolice,
  'heavy_equipment' => l10n.staffBackupHeavy,
  _ => kind,
};

String dangerLabel(AppLocalizations l10n, String kind) => switch (kind) {
  'fire_spread' => l10n.staffDangerFireSpread,
  'collapse' => l10n.staffDangerCollapse,
  'gas' => l10n.staffDangerGas,
  'electricity' => l10n.staffDangerElectricity,
  'violence' => l10n.staffDangerViolence,
  'traffic' => l10n.staffDangerTraffic,
  _ => kind,
};

/// Severity buttons go from green to red.
Tone severityTone(int s) => switch (s) {
  1 => Tone.green,
  2 => Tone.amber,
  3 => Tone.orange,
  _ => Tone.red,
};

String triageLabel(AppLocalizations l10n, Triage t) => switch (t) {
  Triage.red => l10n.staffTriageRed,
  Triage.yellow => l10n.staffTriageYellow,
  Triage.green => l10n.staffTriageGreen,
  Triage.black => l10n.staffTriageBlack,
};

Tone triageTone(Triage t) => switch (t) {
  Triage.red => Tone.red,
  Triage.yellow => Tone.amber,
  Triage.green => Tone.green,
  Triage.black => Tone.slate,
};

String ageLabel(AppLocalizations l10n, AgeBand a) => switch (a) {
  AgeBand.under12 => l10n.staffAgeUnder12,
  AgeBand.from12 => l10n.staffAge12,
  AgeBand.from18 => l10n.staffAge18,
  AgeBand.from30 => l10n.staffAge30,
  AgeBand.from45 => l10n.staffAge45,
  AgeBand.from60 => l10n.staffAge60,
  AgeBand.unknown || AgeBand.legacy => l10n.staffUnknown,
};

String sexLabel(AppLocalizations l10n, Sex s) => switch (s) {
  Sex.female => l10n.staffSexFemale,
  Sex.male => l10n.staffSexMale,
  Sex.unknown => l10n.staffUnknown,
};

String severityLabel(AppLocalizations l10n, int s) => switch (s) {
  1 => l10n.staffSeverity1,
  2 => l10n.staffSeverity2,
  3 => l10n.staffSeverity3,
  _ => l10n.staffSeverity4,
};

/// Server error codes the leader can act on; anything else reads as a generic failure.
String crewErrorLabel(AppLocalizations l10n, String code) => switch (code) {
  'resource_on_shift' => l10n.staffErrVehicleTaken,
  'shift_open' => l10n.staffErrShiftOpen,
  'mission_active' => l10n.staffErrMissionActive,
  'not_on_scene' => l10n.staffErrNotOnScene,
  'no_open_shift' => l10n.staffErrNoShift,
  'media_too_large' => l10n.staffErrTooLarge,
  'too_many_attachments' => l10n.staffErrTooMany,
  'unsupported_media_type' ||
  'type_mismatch' ||
  'empty_file' ||
  'invalid_duration' => l10n.staffErrBadMedia,
  'template_not_current' => l10n.staffErrTemplateChanged,
  _ => l10n.staffErrGeneric,
};

String hhmm(DateTime t) {
  final l = t.toLocal();
  return '${l.hour.toString().padLeft(2, '0')}:${l.minute.toString().padLeft(2, '0')}';
}

String placeOf(Mission m, String localeCode) {
  final d = localeCode == 'ar'
      ? (m.delegationAr ?? m.delegationFr)
      : (m.delegationFr ?? m.delegationAr);
  return d ?? '';
}

/// The colour's name alone, for the four big triage buttons.
String triageShort(AppLocalizations l10n, Triage t) => switch (t) {
  Triage.green => l10n.staffTriageGreenShort,
  Triage.yellow => l10n.staffTriageYellowShort,
  Triage.red => l10n.staffTriageRedShort,
  Triage.black => l10n.staffTriageBlackShort,
};

/// After a write: "sent", or "kept on the phone" while writes wait for the network (phase P4d).
String sentLabel(AppLocalizations l10n, int pending, {bool alert = false}) =>
    pending > 0
    ? l10n.staffKept
    : alert
    ? l10n.staffAlertSent
    : l10n.staffSent;
