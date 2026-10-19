import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';

/// Emergency services reachable by a native SIM call (FR-A-033, BR-30, scenario 0).
enum EmergencyService { civilProtection, samu, police, nationalGuard }

class EmergencyNumber {
  const EmergencyNumber({
    required this.service,
    required this.number,
    required this.icon,
  });

  final EmergencyService service;
  final String number;
  final IconData icon;

  /// `tel:` URI dialled with the phone's own dialer. Never routed through the platform.
  Uri get telUri => Uri(scheme: 'tel', path: number);

  String label(AppLocalizations l10n) => switch (service) {
    EmergencyService.civilProtection => l10n.emergencyCivilProtection,
    EmergencyService.samu => l10n.emergencySamu,
    EmergencyService.police => l10n.emergencyPolice,
    EmergencyService.nationalGuard => l10n.emergencyNationalGuard,
  };
}

/// Constant data source: available offline, without any API call. Civil protection first.
const emergencyNumbers = <EmergencyNumber>[
  EmergencyNumber(
    service: EmergencyService.civilProtection,
    number: '198',
    icon: Icons.local_fire_department,
  ),
  EmergencyNumber(
    service: EmergencyService.samu,
    number: '190',
    icon: Icons.medical_services,
  ),
  EmergencyNumber(
    service: EmergencyService.police,
    number: '197',
    icon: Icons.local_police,
  ),
  EmergencyNumber(
    service: EmergencyService.nationalGuard,
    number: '193',
    icon: Icons.shield,
  ),
];
