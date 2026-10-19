import 'package:flutter/material.dart';

import '../../core/http/models.dart';
import '../../l10n/app_localizations.dart';

/// Kind labels fixed by the phase-4 contract (§1).
String orgKindLabel(AppLocalizations l10n, String kind) =>
    switch (OrgKind.fromWire(kind)) {
      OrgKind.industrial => l10n.orgKindIndustrial,
      OrgKind.educational => l10n.orgKindEducational,
      OrgKind.hotel => l10n.orgKindHotel,
      OrgKind.government => l10n.orgKindGovernment,
      OrgKind.private => l10n.orgKindPrivate,
      OrgKind.other || null => l10n.orgKindOther,
    };

String orgStatusLabel(AppLocalizations l10n, String status) =>
    switch (OrgStatus.fromWire(status)) {
      OrgStatus.pendingReview => l10n.orgStatusPendingReview,
      OrgStatus.active => l10n.orgStatusActive,
      OrgStatus.rejected => l10n.orgStatusRejected,
      OrgStatus.suspended => l10n.orgStatusSuspended,
      null => l10n.statusUnknown,
    };

/// Classification family (phase 4 §1, FR-B-003), with the ERP category when there is one.
String orgClassificationLabel(AppLocalizations l10n, OrgClassification c) {
  final family = switch (c.family) {
    'high_rise' => l10n.orgFamilyHighRise,
    'industrial' => l10n.orgFamilyIndustrial,
    'erp' => l10n.orgFamilyErp,
    'workplace' => l10n.orgFamilyWorkplace,
    _ => l10n.statusUnknown,
  };
  final category = c.category;
  return category == null
      ? family
      : '$family · ${l10n.orgErpCategory(category)}';
}

String teamRoleLabel(AppLocalizations l10n, String role) =>
    role == 'representative' ? l10n.orgTeamRepresentative : l10n.orgTeamMember;

String trainingStatusLabel(AppLocalizations l10n, String status) =>
    switch (status) {
      'valid' => l10n.trainingValid,
      'expiring' => l10n.trainingExpiring,
      'expired' => l10n.trainingExpired,
      _ => l10n.trainingUnknown,
    };

/// Quantity units of hazardous materials (`kg`, `t`, `l`, `m3`): international symbols.
String hazmatUnitSymbol(String? unit) => switch (unit) {
  'm3' => 'm³',
  'l' => 'L',
  null => '',
  _ => unit,
};

class OrgStatusChip extends StatelessWidget {
  const OrgStatusChip({super.key, required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final (bg, fg, icon) = switch (OrgStatus.fromWire(status)) {
      OrgStatus.active => (
        scheme.primaryContainer,
        scheme.onPrimaryContainer,
        Icons.verified,
      ),
      OrgStatus.pendingReview => (
        scheme.tertiaryContainer,
        scheme.onTertiaryContainer,
        Icons.hourglass_top,
      ),
      OrgStatus.rejected || OrgStatus.suspended => (
        scheme.errorContainer,
        scheme.onErrorContainer,
        Icons.block,
      ),
      null => (
        scheme.surfaceContainerHighest,
        scheme.onSurface,
        Icons.help_outline,
      ),
    };
    return Chip(
      avatar: Icon(icon, size: 18, color: fg),
      label: Text(orgStatusLabel(l10n, status)),
      labelStyle: TextStyle(color: fg),
      backgroundColor: bg,
      side: BorderSide.none,
    );
  }
}

/// Small chip naming the institution a report was sent for (FR-B-011).
class OrgChip extends StatelessWidget {
  const OrgChip({super.key, required this.name});

  /// Empty when the name is not known on this phone.
  final String name;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Chip(
      avatar: Icon(Icons.apartment, size: 18, color: scheme.onSurfaceVariant),
      label: Text(name.isEmpty ? l10n.reportAsInstitutionUnnamed : name),
      side: BorderSide.none,
      backgroundColor: scheme.surfaceContainerHigh,
    );
  }
}
