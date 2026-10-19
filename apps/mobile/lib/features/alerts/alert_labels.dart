import 'package:flutter/material.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/http/notify_models.dart';
import '../../core/http/volunteer_models.dart';
import '../../l10n/app_localizations.dart';

String severityLabel(AppLocalizations l10n, AlertSeverity s) => switch (s) {
  AlertSeverity.high => l10n.severityHigh,
  AlertSeverity.medium => l10n.severityMedium,
  AlertSeverity.low => l10n.severityLow,
};

/// Fixed colours (same in light and dark) so a red alert always reads as red; text colour
/// chosen for WCAG AA contrast on each.
(Color background, Color foreground) severityColors(AlertSeverity s) =>
    switch (s) {
      AlertSeverity.high => (const Color(0xFFB71C1C), Colors.white),
      AlertSeverity.medium => (const Color(0xFFE65100), Colors.white),
      AlertSeverity.low => (const Color(0xFFFBC02D), Colors.black),
    };

String hazardLabel(AppLocalizations l10n, AlertHazard h) => switch (h) {
  AlertHazard.heavyRain => l10n.hazardHeavyRain,
  AlertHazard.flood => l10n.hazardFlood,
  AlertHazard.storm => l10n.hazardStorm,
  AlertHazard.wind => l10n.hazardWind,
  AlertHazard.heatWave => l10n.hazardHeatWave,
  AlertHazard.coldWave => l10n.hazardColdWave,
  AlertHazard.sea => l10n.hazardSea,
  AlertHazard.forestFire => l10n.hazardForestFire,
  AlertHazard.chemical => l10n.hazardChemical,
  AlertHazard.other => l10n.hazardOther,
};

IconData hazardIcon(AlertHazard h) => switch (h) {
  AlertHazard.heavyRain => Icons.thunderstorm,
  AlertHazard.flood => Icons.flood,
  AlertHazard.storm => Icons.storm,
  AlertHazard.wind => Icons.air,
  AlertHazard.heatWave => Icons.thermostat,
  AlertHazard.coldWave => Icons.ac_unit,
  AlertHazard.sea => Icons.waves,
  AlertHazard.forestFire => Icons.local_fire_department,
  AlertHazard.chemical => Icons.science,
  AlertHazard.other => Icons.warning_amber,
};

String topicLabel(AppLocalizations l10n, NotificationTopic? t) => switch (t) {
  NotificationTopic.activity => l10n.topicActivity,
  NotificationTopic.awareness => l10n.topicAwareness,
  NotificationTopic.training => l10n.topicTraining,
  NotificationTopic.worldDay => l10n.topicWorldDay,
  NotificationTopic.other || null => l10n.topicOther,
};

String tipHazardLabel(AppLocalizations l10n, TipHazard h) => switch (h) {
  TipHazard.fire => l10n.categoryFire,
  TipHazard.flood => l10n.categoryFlood,
  TipHazard.trafficAccident => l10n.categoryTrafficAccident,
  TipHazard.medical => l10n.categoryMedical,
  TipHazard.drowning => l10n.categoryDrowning,
  TipHazard.landslide => l10n.categoryLandslide,
  TipHazard.chemicalLeak => l10n.categoryChemicalLeak,
  TipHazard.heatWave => l10n.hazardHeatWave,
  TipHazard.storm => l10n.hazardStorm,
  TipHazard.earthquake => l10n.tipEarthquake,
  TipHazard.other => l10n.categoryOther,
};

IconData tipHazardIcon(TipHazard h) => switch (h) {
  TipHazard.fire => Icons.local_fire_department,
  TipHazard.flood => Icons.flood,
  TipHazard.trafficAccident => Icons.car_crash,
  TipHazard.medical => Icons.medical_services,
  TipHazard.drowning => Icons.pool,
  TipHazard.landslide => Icons.landslide,
  TipHazard.chemicalLeak => Icons.science,
  TipHazard.heatWave => Icons.thermostat,
  TipHazard.storm => Icons.thunderstorm,
  TipHazard.earthquake => Icons.vibration,
  TipHazard.other => Icons.health_and_safety,
};

String skillLabel(AppLocalizations l10n, VolunteerSkill s) => switch (s) {
  VolunteerSkill.firstAid => l10n.skillFirstAid,
  VolunteerSkill.diving => l10n.skillDiving,
  VolunteerSkill.heavyVehicles => l10n.skillHeavyVehicles,
  VolunteerSkill.firefighting => l10n.skillFirefighting,
  VolunteerSkill.searchRescue => l10n.skillSearchRescue,
  VolunteerSkill.logistics => l10n.skillLogistics,
  VolunteerSkill.medical => l10n.skillMedical,
  VolunteerSkill.other => l10n.skillOther,
};

String volunteerStatusLabel(AppLocalizations l10n, VolunteerStatus s) =>
    switch (s) {
      VolunteerStatus.pending => l10n.volunteerStatusPending,
      VolunteerStatus.approved => l10n.volunteerStatusApproved,
      VolunteerStatus.rejected => l10n.volunteerStatusRejected,
      VolunteerStatus.suspended => l10n.volunteerStatusSuspended,
      VolunteerStatus.withdrawn => l10n.volunteerStatusWithdrawn,
    };

String calloutAnswerLabel(AppLocalizations l10n, CalloutTargetStatus s) =>
    switch (s) {
      CalloutTargetStatus.sent => l10n.calloutAnswerSent,
      CalloutTargetStatus.accepted => l10n.calloutAnswerAccepted,
      CalloutTargetStatus.declined => l10n.calloutAnswerDeclined,
      CalloutTargetStatus.expired => l10n.calloutAnswerExpired,
      CalloutTargetStatus.arrived => l10n.calloutAnswerArrived,
    };

/// Distance in the UI language (metres under 1 km; decimal comma in French).
String distanceLabel(AppLocalizations l10n, int meters) {
  if (meters < 1000) return l10n.distanceMeters(meters);
  final km = (meters / 1000).toStringAsFixed(meters < 10000 ? 1 : 0);
  return l10n.distanceKm(
    l10n.localeName == 'fr' ? km.replaceAll('.', ',') : km,
  );
}

/// Date and time in the UI language, e.g. «19 oct. 2026 14:05».
String dateTimeLabel(BuildContext context, DateTime at) {
  final locale = Localizations.localeOf(context).toLanguageTag();
  return DateFormat.yMMMd(locale).add_Hm().format(at.toLocal());
}

String dateLabel(BuildContext context, DateTime at) =>
    DateFormat.yMMMd(Localizations.localeOf(context).toLanguageTag())
        .format(at);

/// The coloured severity pill used in lists, the banner and the detail screen.
class SeverityChip extends StatelessWidget {
  const SeverityChip({super.key, required this.severity});

  final AlertSeverity severity;

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = severityColors(severity);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        child: Text(
          severityLabel(AppLocalizations.of(context), severity),
          style: Theme.of(context).textTheme.labelMedium
              ?.copyWith(color: fg, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}
