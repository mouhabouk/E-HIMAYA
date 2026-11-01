import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_models.dart';

/// What a mission used, with its step on the steppers (design-system.md `Stepper`): the same list
/// as the room's (services/api/app/modules/ops/record.py `CONSUMABLES`).
const consumableSteps = <String, (int max, int step)>{
  'water_m3': (1000, 1),
  'foam_l': (20000, 10),
  'powder_kg': (5000, 1),
  'co2_kg': (2000, 1),
  'extinguishers': (200, 1),
  'oxygen_l': (50000, 10),
  'fuel_l': (5000, 1),
  'sandbags': (20000, 10),
  'absorbent_kg': (5000, 1),
};

String consumableLabel(AppLocalizations l10n, String key) => switch (key) {
  'water_m3' => l10n.staffUsedWater,
  'foam_l' => l10n.staffUsedFoam,
  'powder_kg' => l10n.staffUsedPowder,
  'co2_kg' => l10n.staffUsedCo2,
  'extinguishers' => l10n.staffUsedExtinguishers,
  'oxygen_l' => l10n.staffUsedOxygen,
  'fuel_l' => l10n.staffUsedFuel,
  'sandbags' => l10n.staffUsedSandbags,
  _ => l10n.staffUsedAbsorbent,
};

String damageUnitLabel(AppLocalizations l10n, DamageUnit u) => switch (u) {
  DamageUnit.ha => l10n.staffDamageHectare,
  DamageUnit.bale => l10n.staffDamageBale,
  DamageUnit.bag => l10n.staffDamageBag,
};

/// A damage line being entered: a forest (hectares) or a farm loss (hectares, bales, bags).
class _DamageRow {
  _DamageRow({
    required this.forest,
    this.place,
    this.crop,
    this.unit = DamageUnit.ha,
    String value = '',
  }) : value = TextEditingController(text: value);

  factory _DamageRow.of(DamageEntry d) => _DamageRow(
    forest: d.forest,
    place: d.place,
    crop: d.crop,
    unit: d.unit,
    value: d.value == d.value.roundToDouble()
        ? '${d.value.toInt()}'
        : '${d.value}',
  );

  final bool forest;
  String? place;
  String? crop;
  DamageUnit unit;
  final TextEditingController value;

  double? get amount => double.tryParse(value.text.trim().replaceAll(',', '.'));

  bool get complete =>
      place != null &&
      (forest || crop != null) &&
      (amount ?? 0) > 0 &&
      (amount ?? 0) <= 1000000;

  DamageEntry get entry => DamageEntry(
    forest: forest,
    place: place!,
    crop: forest ? null : crop,
    unit: forest ? DamageUnit.ha : unit,
    value: amount!,
  );
}

/// The crew and the resources of a mission (phase S2, design-s2 §4): counts only, no typing,
/// sent like every other write (kept on the phone without network). The room sees them at once
/// and can correct them.
class MissionRecordScreen extends ConsumerStatefulWidget {
  const MissionRecordScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<MissionRecordScreen> createState() =>
      _MissionRecordScreenState();
}

class _MissionRecordScreenState extends ConsumerState<MissionRecordScreen> {
  final _crew = TextEditingController();
  final _used = {
    for (final k in consumableSteps.keys) k: TextEditingController(),
  };
  final _damages = <_DamageRow>[];
  bool _filled = false;

  @override
  void dispose() {
    _crew.dispose();
    for (final c in _used.values) {
      c.dispose();
    }
    for (final d in _damages) {
      d.value.dispose();
    }
    super.dispose();
  }

  void _fill(Mission m, int? shiftCrew) {
    if (_filled) return;
    _filled = true;
    final crew = m.crewCount ?? shiftCrew;
    _crew.text = crew == null ? '' : '$crew';
    for (final e in _used.entries) {
      final v = m.consumables[e.key];
      e.value.text = v == null || v == 0 ? '' : '$v';
    }
    _damages.addAll(m.damages.map(_DamageRow.of));
  }

  Widget _damageCard(
    AppLocalizations l10n,
    DamageLists lists,
    int i,
    _DamageRow d,
  ) {
    final places = d.forest ? lists.forestPlaces : lists.agriPlaces;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        key: Key('damage-$i'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    d.forest ? l10n.staffDamageForest : l10n.staffDamageAgri,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                IconButton(
                  key: Key('damage-$i-remove'),
                  tooltip: l10n.staffDamageRemove,
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () {
                    final gone = d.value;
                    setState(() => _damages.removeAt(i));
                    WidgetsBinding.instance.addPostFrameCallback(
                      (_) => gone.dispose(),
                    );
                  },
                ),
              ],
            ),
            Text(l10n.staffDamagePlace),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final p in places)
                  ChoiceChip(
                    label: Text(p),
                    selected: d.place == p,
                    onSelected: (_) => setState(() => d.place = p),
                  ),
              ],
            ),
            if (!d.forest) ...[
              const SizedBox(height: 8),
              Text(l10n.staffDamageCrop),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final c in lists.crops)
                    ChoiceChip(
                      label: Text(c.label),
                      selected: d.crop == c.label,
                      onSelected: (_) => setState(() {
                        d.crop = c.label;
                        d.unit = c.unit ?? d.unit;
                      }),
                    ),
                ],
              ),
            ],
            const SizedBox(height: 8),
            TextField(
              key: Key('damage-$i-value'),
              controller: d.value,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: l10n.staffDamageValue,
                suffixText: d.forest
                    ? damageUnitLabel(l10n, DamageUnit.ha)
                    : null,
              ),
              onChanged: (_) => setState(() {}),
            ),
            if (!d.forest) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (final u in DamageUnit.values)
                    ChoiceChip(
                      key: Key('damage-$i-${u.name}'),
                      label: Text(damageUnitLabel(l10n, u)),
                      selected: d.unit == u,
                      onSelected: (_) => setState(() => d.unit = u),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(widget.missionId);
    if (m == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffRecordTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    _fill(m, s.me?.shift?.crewSize);
    final crew = int.tryParse(_crew.text.trim());
    final lists = s.me?.damageLists ?? DamageLists.defaults;
    final ready =
        m.status != MissionStatus.cancelled &&
        crew != null &&
        crew >= 1 &&
        _damages.every((d) => d.complete) &&
        !s.busy;
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffRecordTitle,
        subtitle: s.me?.shift?.vehicle.label,
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                SectionTitle(l10n.staffRecordCrew),
                NumberStepper(
                  controller: _crew,
                  fieldKey: const ValueKey('record-crew'),
                  label: l10n.staffRecordCrew,
                  min: 1,
                  max: 60,
                  start: 4,
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 16),
                SectionTitle(l10n.staffRecordUsed),
                for (final e in consumableSteps.entries) ...[
                  NumberStepper(
                    controller: _used[e.key]!,
                    fieldKey: ValueKey('record-${e.key}'),
                    label: consumableLabel(l10n, e.key),
                    max: e.value.$1,
                    step: e.value.$2,
                    start: e.value.$2,
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 8),
                ],
                const SizedBox(height: 16),
                SectionTitle(l10n.staffDamagesTitle),
                Text(l10n.staffDamagesHint),
                const SizedBox(height: 8),
                for (final (i, d) in _damages.indexed)
                  _damageCard(l10n, lists, i, d),
                if (_damages.length < 20)
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      OutlinedButton.icon(
                        key: const Key('add-forest-damage'),
                        icon: const Icon(Icons.forest),
                        label: Text(l10n.staffDamageAddForest),
                        onPressed: () => setState(
                          () => _damages.add(_DamageRow(forest: true)),
                        ),
                      ),
                      OutlinedButton.icon(
                        key: const Key('add-agri-damage'),
                        icon: const Icon(Icons.agriculture),
                        label: Text(l10n.staffDamageAddAgri),
                        onPressed: () => setState(
                          () => _damages.add(_DamageRow(forest: false)),
                        ),
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: BottomActionBar(
        actions: [
          BarAction(
            key: const Key('send-record'),
            label: l10n.staffRecordSend,
            icon: Icons.send,
            tone: Tone.navy,
            onPressed: ready
                ? () async {
                    final ok = await ref
                        .read(staffControllerProvider.notifier)
                        .teamRecord(
                          m.id,
                          crewCount: crew,
                          consumables: {
                            for (final e in _used.entries)
                              e.key: int.tryParse(e.value.text.trim()) ?? 0,
                          },
                          damages: _damages.isEmpty && m.damages.isEmpty
                              ? null
                              : [for (final d in _damages) d.entry],
                        );
                    if (ok && context.mounted) Navigator.of(context).pop();
                  }
                : null,
          ),
        ],
      ),
    );
  }
}
