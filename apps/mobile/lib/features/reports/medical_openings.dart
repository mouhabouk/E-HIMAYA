import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/doctor_models.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../doctor/doctor_labels.dart';
import '../doctor/doctor_providers.dart';
import '../profile/profile_screen.dart';

/// Phase C1-c (design §13.4): on a report card, "who saw my medical file". Shown once a doctor
/// opened (or received) the locked part; each line gives a role, never a name, and the committee
/// only as "the medical committee".
class MedicalOpeningsButton extends ConsumerWidget {
  const MedicalOpeningsButton({super.key, required this.reportId});

  final String reportId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final mine = [
      for (final o
          in ref.watch(myMedicalOpeningsProvider).value ??
              const <MedicalOpening>[])
        if (o.reportId == reportId) o,
    ];
    if (mine.isEmpty) return const SizedBox.shrink();
    return Align(
      alignment: AlignmentDirectional.centerEnd,
      child: TextButton.icon(
        key: Key('openings-$reportId'),
        onPressed: () => showModalBottomSheet<void>(
          context: context,
          isScrollControlled: true,
          showDragHandle: true,
          builder: (_) => MedicalOpeningsSheet(openings: mine),
        ),
        icon: const Icon(Icons.visibility_outlined),
        label: Text(l10n.medicalOpeningsCount(mine.length)),
      ),
    );
  }
}

class MedicalOpeningsSheet extends ConsumerWidget {
  const MedicalOpeningsSheet({super.key, required this.openings});

  final List<MedicalOpening> openings;

  static String label(
    AppLocalizations l10n,
    MedicalOpening o,
    Map<int, String> gouvernorats,
  ) {
    final specialty = o.specialties.isEmpty
        ? '—'
        : o.specialties.map((s) => specialtyLabel(l10n, s)).join('، ');
    if (o.referral) return l10n.medicalOpeningReferral(specialty);
    return switch (o.role) {
      OpeningRole.committee => l10n.medicalOpeningCommittee,
      OpeningRole.civilProtection => l10n.medicalOpeningCp(
        gouvernorats[o.gouvernoratCode] ?? '${o.gouvernoratCode ?? '—'}',
      ),
      OpeningRole.specialist => l10n.medicalOpeningSpecialist(
        specialty,
        o.workplace ?? '—',
      ),
    };
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final gouvernorats = ref.watch(gouvernoratsProvider).value ?? const [];
    final names = {for (final g in gouvernorats) g.code: g.name};
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.75,
        ),
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          children: [
            Text(l10n.medicalOpeningsTitle, style: theme.textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(l10n.medicalOpeningsNote, style: theme.textTheme.bodySmall),
            const SizedBox(height: 8),
            if (openings.isEmpty) Text(l10n.medicalOpeningsEmpty),
            for (final o in openings)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(
                  o.referral ? Icons.forward_to_inbox : Icons.lock_open,
                ),
                title: Text(label(l10n, o, names)),
                subtitle: Text(
                  [
                    if (!o.referral) l10n.medicalOpeningOpened,
                    dateTimeLabel(context, o.at),
                  ].join(' · '),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
