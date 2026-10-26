import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_app.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';

/// F-STF-04: live counters (each tap is sent at once) and the victims taken to hospital, with
/// the triage colour and no names.
class CasualtiesScreen extends ConsumerWidget {
  const CasualtiesScreen({super.key, required this.missionId});

  final String missionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(missionId);
    final c = ref.read(staffControllerProvider.notifier);
    final editable = m != null && m.status == MissionStatus.onScene;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.staffCasualties),
        actions: staffBarActions(),
      ),
      body: m == null
          ? Center(child: Text(l10n.staffMissionGone))
          : Column(
              children: [
                const OfflineStrip(),
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      for (final k in CasualtyCounter.values)
                        _Counter(
                          label: counterLabel(l10n, k),
                          value: m.casualties.of(k),
                          keyName: k.name,
                          onChange: editable && !s.busy
                              ? (d) => c.count(missionId, k, d)
                              : null,
                        ),
                      const SizedBox(height: 16),
                      SectionTitle(l10n.staffTransports),
                      if (m.transports.isEmpty)
                        AppCard(child: Text(l10n.staffNoTransport)),
                      for (final t in m.transports)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: AppCard(
                            child: Row(
                              children: [
                                Pill(
                                  triageLabel(l10n, t.triage),
                                  tone: triageTone(t.triage),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '${ageLabel(l10n, t.ageBand)} · '
                                    '${sexLabel(l10n, t.sex)} → ${t.hospital}',
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      if (s.error != null)
                        Text(
                          crewErrorLabel(l10n, s.error!),
                          key: const Key('staff-error'),
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
      bottomNavigationBar: editable
          ? BottomActionBar(
              actions: [
                BarAction(
                  key: const Key('add-transport'),
                  label: l10n.staffAddTransport,
                  icon: Icons.local_hospital,
                  tone: Tone.red,
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    builder: (_) => TransportSheet(missionId: missionId),
                  ),
                ),
              ],
            )
          : null,
    );
  }
}

class _Counter extends StatelessWidget {
  const _Counter({
    required this.label,
    required this.value,
    required this.keyName,
    required this.onChange,
  });

  final String label;
  final int value;
  final String keyName;
  final Future<bool> Function(int delta)? onChange;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final change = onChange;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            IconButton.filledTonal(
              key: Key('$keyName-minus'),
              tooltip: '${l10n.staffLess}: $label',
              onPressed: change == null || value == 0 ? null : () => change(-1),
              icon: const Icon(Icons.remove),
            ),
            SizedBox(
              width: 56,
              child: Semantics(
                liveRegion: true,
                label: '$label: $value',
                excludeSemantics: true,
                child: Text(
                  '$value',
                  key: Key('$keyName-value'),
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ),
            ),
            IconButton.filled(
              key: Key('$keyName-plus'),
              tooltip: '${l10n.staffMore}: $label',
              onPressed: change == null ? null : () => change(1),
              icon: const Icon(Icons.add),
            ),
          ],
        ),
      ),
    );
  }
}

/// One victim taken to hospital: triage colour, age band, sex, hospital. No name (data
/// minimisation; the hospital identifies the patient).
class TransportSheet extends ConsumerStatefulWidget {
  const TransportSheet({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<TransportSheet> createState() => _TransportSheetState();
}

class _TransportSheetState extends ConsumerState<TransportSheet> {
  Triage? _triage;
  AgeBand _age = AgeBand.unknown;
  Sex _sex = Sex.unknown;
  final _hospital = TextEditingController();

  @override
  void dispose() {
    _hospital.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final busy = ref.watch(staffControllerProvider.select((s) => s.busy));
    final ready = _triage != null && _hospital.text.trim().isNotEmpty && !busy;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              l10n.staffAddTransport,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            SectionTitle(l10n.staffTriage),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final t in Triage.values)
                  ChoiceChip(
                    key: Key('triage-${t.name}'),
                    avatar: CircleAvatar(
                      backgroundColor: triageTone(t).colors(context).fill,
                      radius: 8,
                    ),
                    label: Text(triageLabel(l10n, t)),
                    selected: _triage == t,
                    onSelected: (_) => setState(() => _triage = t),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            SectionTitle(l10n.staffAge),
            Wrap(
              spacing: 8,
              children: [
                for (final a in AgeBand.values)
                  ChoiceChip(
                    key: Key('age-${a.name}'),
                    label: Text(ageLabel(l10n, a)),
                    selected: _age == a,
                    onSelected: (_) => setState(() => _age = a),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            SectionTitle(l10n.staffSex),
            Wrap(
              spacing: 8,
              children: [
                for (final x in Sex.values)
                  ChoiceChip(
                    key: Key('sex-${x.name}'),
                    label: Text(sexLabel(l10n, x)),
                    selected: _sex == x,
                    onSelected: (_) => setState(() => _sex = x),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('hospital'),
              controller: _hospital,
              maxLength: 120,
              decoration: InputDecoration(labelText: l10n.staffHospital),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 8),
            ToneButton(
              action: BarAction(
                key: const Key('send-transport'),
                label: l10n.staffSend,
                icon: Icons.send,
                tone: Tone.red,
                onPressed: !ready
                    ? null
                    : () async {
                        final ok = await ref
                            .read(staffControllerProvider.notifier)
                            .transport(
                              widget.missionId,
                              triage: _triage!,
                              ageBand: _age,
                              sex: _sex,
                              hospital: _hospital.text,
                            );
                        if (ok && context.mounted) Navigator.of(context).pop();
                      },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
