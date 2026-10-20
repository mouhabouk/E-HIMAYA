import 'package:flutter/material.dart';

import '../../core/http/rewards_models.dart';
import '../../l10n/app_localizations.dart';

String badgeLabel(AppLocalizations l10n, BadgeLevel level) => switch (level) {
  BadgeLevel.bronze => l10n.badgeBronze,
  BadgeLevel.silver => l10n.badgeSilver,
  BadgeLevel.gold => l10n.badgeGold,
  BadgeLevel.ambassador => l10n.badgeAmbassador,
};

String pointsReasonLabel(AppLocalizations l10n, PointsReason? reason) =>
    switch (reason) {
      PointsReason.reportVerified => l10n.pointsReasonReportVerified,
      PointsReason.reportHelpedRescue => l10n.pointsReasonHelpedRescue,
      PointsReason.accurateCategory => l10n.pointsReasonAccurateCategory,
      PointsReason.volunteerMission => l10n.pointsReasonVolunteerMission,
      PointsReason.manual => l10n.pointsReasonManual,
      PointsReason.revocation => l10n.pointsReasonRevocation,
      null => l10n.pointsReasonOther,
    };

IconData pointsReasonIcon(PointsReason? reason) => switch (reason) {
  PointsReason.reportVerified => Icons.verified,
  PointsReason.reportHelpedRescue => Icons.health_and_safety,
  PointsReason.accurateCategory => Icons.category,
  PointsReason.volunteerMission => Icons.volunteer_activism,
  PointsReason.manual => Icons.edit_note,
  PointsReason.revocation => Icons.remove_circle_outline,
  null => Icons.star_outline,
};

/// A certificate's distinction: a badge level or a nomination kind (FR-C-20).
String distinctionLabel(AppLocalizations l10n, String distinction) =>
    switch (distinction) {
      'vigilant_citizen' => l10n.distinctionVigilantCitizen,
      'brave_volunteer' => l10n.distinctionBraveVolunteer,
      'leading_institution' => l10n.distinctionLeadingInstitution,
      _ => switch (BadgeLevel.fromWire(distinction)) {
        final level? => l10n.distinctionBadge(badgeLabel(l10n, level)),
        null => l10n.distinctionOther,
      },
    };
