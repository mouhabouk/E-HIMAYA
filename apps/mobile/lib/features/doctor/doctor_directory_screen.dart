import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/doctor_models.dart';
import '../../core/http/error_messages.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../profile/profile_screen.dart';
import 'doctor_labels.dart';
import 'doctor_providers.dart';

/// Approved doctors by specialty and gouvernorat (phase C1-a): the list a doctor will pick from
/// to refer a medical file. Available doctors first, then the doctor's own group.
class DoctorDirectoryScreen extends ConsumerStatefulWidget {
  const DoctorDirectoryScreen({super.key});

  @override
  ConsumerState<DoctorDirectoryScreen> createState() =>
      _DoctorDirectoryScreenState();
}

class _DoctorDirectoryScreenState extends ConsumerState<DoctorDirectoryScreen> {
  DoctorSpecialty? _specialty;
  int? _gouvernorat;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final gouvernorats = ref.watch(gouvernoratsProvider).value ?? const [];
    final names = {for (final g in gouvernorats) g.code: g.name};
    final filter = (specialty: _specialty, gouvernorat: _gouvernorat);
    final doctors = ref.watch(doctorDirectoryProvider(filter));
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.doctorDirectory),
        actions: const [StandardAppBarActions()],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: DropdownButtonFormField<DoctorSpecialty?>(
              key: const Key('directory-specialty'),
              initialValue: _specialty,
              isExpanded: true,
              decoration: InputDecoration(labelText: l10n.doctorSpecialty),
              items: [
                DropdownMenuItem(child: Text(l10n.doctorAllSpecialties)),
                for (final s in DoctorSpecialty.values)
                  DropdownMenuItem(
                    value: s,
                    child: Text(specialtyLabel(l10n, s)),
                  ),
              ],
              onChanged: (v) => setState(() => _specialty = v),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: DropdownButtonFormField<int?>(
              key: const Key('directory-gouvernorat'),
              initialValue: _gouvernorat,
              isExpanded: true,
              decoration: InputDecoration(labelText: l10n.doctorRegion),
              items: [
                DropdownMenuItem(child: Text(l10n.doctorAllGouvernorats)),
                for (final g in gouvernorats)
                  DropdownMenuItem(value: g.code, child: Text(g.name)),
              ],
              onChanged: (v) => setState(() => _gouvernorat = v),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () =>
                  ref.refresh(doctorDirectoryProvider(filter).future),
              child: doctors.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => ListView(
                  padding: const EdgeInsets.all(24),
                  children: [Text(errorMessageFor(l10n, e))],
                ),
                data: (list) => list.isEmpty
                    ? ListView(
                        padding: const EdgeInsets.all(24),
                        children: [
                          Text(
                            l10n.doctorDirectoryEmpty,
                            key: const Key('directory-empty'),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      )
                    : ListView.separated(
                        itemCount: list.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final d = list[i];
                          return ListTile(
                            key: Key('directory-${d.id}'),
                            leading: Icon(
                              d.kind == DoctorKind.civilProtection
                                  ? Icons.local_hospital
                                  : Icons.medical_services,
                            ),
                            title: Text(d.fullName ?? '—'),
                            subtitle: Text(
                              [
                                d.specialties
                                    .map((s) => specialtyLabel(l10n, s))
                                    .join('، '),
                                [
                                  d.workplace,
                                  ?names[d.gouvernoratCode],
                                ].join(' · '),
                              ].join('\n'),
                            ),
                            isThreeLine: true,
                            trailing: d.available
                                ? Chip(
                                    label: Text(l10n.doctorAvailableBadge),
                                    backgroundColor:
                                        theme.colorScheme.primaryContainer,
                                  )
                                : null,
                          );
                        },
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
