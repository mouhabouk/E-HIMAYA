import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';

/// F-STF-02: the leader takes a vehicle of the gouvernorat and gives the crew size.
class ShiftScreen extends ConsumerStatefulWidget {
  const ShiftScreen({super.key});

  @override
  ConsumerState<ShiftScreen> createState() => _ShiftScreenState();
}

class _ShiftScreenState extends ConsumerState<ShiftScreen> {
  late Future<List<CrewVehicle>> _vehicles;
  CrewVehicle? _chosen;
  int _crew = 4;
  final _names = TextEditingController();

  @override
  void initState() {
    super.initState();
    _vehicles = ref.read(staffControllerProvider.notifier).vehicles();
  }

  @override
  void dispose() {
    _names.dispose();
    super.dispose();
  }

  void _reload() => setState(
    () => _vehicles = ref.read(staffControllerProvider.notifier).vehicles(),
  );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = ref.read(staffControllerProvider.notifier);
    final chosen = _chosen;
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffShiftTitle,
        subtitle: s.me?.name,
        actions: [
          PopupMenuButton<String>(
            key: const Key('staff-menu'),
            onSelected: (_) => unawaited(c.signOut()),
            itemBuilder: (_) => [
              PopupMenuItem(value: 'out', child: Text(l10n.staffSignOut)),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () async => _reload(),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (s.me?.name != null)
                    Text(
                      l10n.staffHello(s.me!.name!),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  const SizedBox(height: 8),
                  SectionTitle(l10n.staffChooseVehicle),
                  FutureBuilder<List<CrewVehicle>>(
                    future: _vehicles,
                    builder: (context, snap) {
                      if (snap.connectionState != ConnectionState.done) {
                        return const Padding(
                          padding: EdgeInsets.all(24),
                          child: Center(child: CircularProgressIndicator()),
                        );
                      }
                      final list = snap.data ?? const <CrewVehicle>[];
                      if (list.isEmpty) {
                        return AppCard(child: Text(l10n.staffNoVehicles));
                      }
                      return Column(
                        children: [
                          for (final v in list)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: ChoiceTile(
                                key: Key('vehicle-${v.id}'),
                                icon: vehicleKindIcon(v.kind),
                                tone: v.onShift ? Tone.slate : Tone.navy,
                                title: v.label,
                                caption: [
                                  vehicleKindLabel(l10n, v.kind),
                                  v.unitName,
                                  if (v.onShift) l10n.staffVehicleTaken,
                                ].join(' · '),
                                selected: chosen?.id == v.id,
                                onTap: v.onShift
                                    ? null
                                    : () => setState(() => _chosen = v),
                              ),
                            ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 16),
                  SectionTitle(l10n.staffCrewSize),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton.filledTonal(
                        key: const Key('crew-minus'),
                        tooltip: l10n.staffLess,
                        iconSize: 32,
                        onPressed: _crew > 1
                            ? () => setState(() => _crew--)
                            : null,
                        icon: const Icon(Icons.remove),
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 24),
                        child: Semantics(
                          liveRegion: true,
                          label: l10n.staffCrewCount(_crew),
                          excludeSemantics: true,
                          child: Text(
                            '$_crew',
                            key: const Key('crew-size'),
                            style: Theme.of(context).textTheme.displaySmall,
                          ),
                        ),
                      ),
                      IconButton.filledTonal(
                        key: const Key('crew-plus'),
                        tooltip: l10n.staffMore,
                        iconSize: 32,
                        onPressed: _crew < 20
                            ? () => setState(() => _crew++)
                            : null,
                        icon: const Icon(Icons.add),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('crew-names'),
                    controller: _names,
                    maxLength: 300,
                    decoration: InputDecoration(
                      labelText: l10n.staffCrewNames,
                      helperText: l10n.staffOptional,
                    ),
                  ),
                  if (s.error != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      crewErrorLabel(l10n, s.error!),
                      key: const Key('staff-error'),
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: BottomActionBar(
        actions: [
          BarAction(
            key: const Key('start-shift'),
            label: l10n.staffStartShift,
            icon: Icons.play_arrow,
            tone: Tone.green,
            onPressed: chosen == null || s.busy
                ? null
                : () async {
                    if (!await c.startShift(chosen, _crew, _names.text)) {
                      _reload();
                    }
                  },
          ),
        ],
      ),
    );
  }
}
