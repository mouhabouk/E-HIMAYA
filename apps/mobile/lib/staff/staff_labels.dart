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
  CasualtyCounter.injured => l10n.staffInjured,
  CasualtyCounter.deceased => l10n.staffDeceased,
  CasualtyCounter.rescued => l10n.staffRescued,
  CasualtyCounter.trapped => l10n.staffTrapped,
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
  AgeBand.child => l10n.staffAgeChild,
  AgeBand.adult => l10n.staffAgeAdult,
  AgeBand.elderly => l10n.staffAgeElderly,
  AgeBand.unknown => l10n.staffUnknown,
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
  _ => l10n.staffErrGeneric,
};

String placeOf(Mission m, String localeCode) {
  final d = localeCode == 'ar'
      ? (m.delegationAr ?? m.delegationFr)
      : (m.delegationFr ?? m.delegationAr);
  return d ?? '';
}
