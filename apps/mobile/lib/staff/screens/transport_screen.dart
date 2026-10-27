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
import 'field_widgets.dart';

/// People taken to hospital, with no names (phase P4b, design §5.6): triage colour, age band,
/// sex, and the hospital among the nearest of the map. The time is the phone's.
class TransportScreen extends ConsumerStatefulWidget {
  const TransportScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<TransportScreen> createState() => _TransportScreenState();
}

class _TransportScreenState extends ConsumerState<TransportScreen> {
  late final Future<List<Hospital>> _hospitals;
  Triage? _triage;
  AgeBand _age = AgeBand.unknown;
  Sex _sex = Sex.unknown;
  String? _hospital;
  bool _other = false;
  final _name = TextEditingController();

  @override
  void initState() {
    super.initState();
    _hospitals = ref
        .read(staffControllerProvider.notifier)
        .hospitals(widget.missionId);
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(widget.missionId);
    if (m == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffTransportTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final editable = m.status == MissionStatus.onScene;
    final ready =
        editable &&
        _triage != null &&
        (_other ? _name.text.trim().isNotEmpty : _hospital != null) &&
        !s.busy;
    final n = Neutrals.of(context);
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffTransportShort,
        subtitle: [l10n.staffNoNames, ?s.me?.shift?.vehicle.label].join(' · '),
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (editable) ...[
                  SectionTitle(l10n.staffTriage),
                  ChoiceRow(
                    children: [
                      for (final t in Triage.values)
                        ToneChoice(
                          key: Key('triage-${t.name}'),
                          label: triageShort(l10n, t),
                          tone: triageTone(t),
                          selected: _triage == t,
                          height: 60,
                          onTap: () => setState(() => _triage = t),
                        ),
                    ],
                  ),
                  if (_triage != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        triageLabel(l10n, _triage!),
                        textAlign: TextAlign.center,
                        style: TextStyle(color: n.muted),
                      ),
                    ),
                  const SizedBox(height: 14),
                  SectionTitle(l10n.staffAge),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final a in AgeBand.choices)
                        ChoiceChip(
                          key: Key('age-${a.wire}'),
                          label: Text(ageLabel(l10n, a)),
                          selected: _age == a,
                          onSelected: (_) => setState(() => _age = a),
                        ),
                    ],
                  ),
                  const SizedBox(height: 14),
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
                  const SizedBox(height: 14),
                  SectionTitle(l10n.staffHospital),
                  FutureBuilder<List<Hospital>>(
                    future: _hospitals,
                    builder: (context, snap) => Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        if (snap.connectionState != ConnectionState.done)
                          const SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        for (final h in snap.data ?? const <Hospital>[])
                          ChoiceChip(
                            key: Key('hospital-${h.id}'),
                            label: Text(
                              '${h.name} · ${l10n.staffDistanceKm((h.distanceM / 1000).toStringAsFixed(1))}'
                              '${h.simulated ? ' ${l10n.staffSimHospital}' : ''}',
                            ),
                            selected: !_other && _hospital == h.id,
                            onSelected: (_) => setState(() {
                              _other = false;
                              _hospital = h.id;
                            }),
                          ),
                        ChoiceChip(
                          key: const Key('hospital-other'),
                          label: Text(l10n.staffHospitalOther),
                          selected: _other,
                          onSelected: (_) => setState(() => _other = true),
                        ),
                      ],
                    ),
                  ),
                  if (_other) ...[
                    const SizedBox(height: 8),
                    TextField(
                      key: const Key('hospital'),
                      controller: _name,
                      maxLength: 120,
                      decoration: InputDecoration(
                        labelText: l10n.staffHospitalName,
                      ),
                      onChanged: (_) => setState(() {}),
                    ),
                  ],
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.schedule, size: 16, color: n.muted),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          l10n.staffTimeAuto,
                          style: TextStyle(color: n.muted),
                        ),
                      ),
                    ],
                  ),
                  const StaffErrorText(),
                  const SizedBox(height: 12),
                ],
                SectionTitle(l10n.staffTransportsCount(m.transports.length)),
                for (final (i, t) in m.transports.indexed)
                  _TransportRow(index: i + 1, transport: t),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: editable
          ? BottomActionBar(
              actions: [
                BarAction(
                  key: const Key('send-transport'),
                  label: l10n.staffSendNow,
                  icon: Icons.send,
                  tone: Tone.green,
                  onPressed: !ready ? null : () => unawaited(_send()),
                ),
              ],
            )
          : null,
    );
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final ok = await ref
        .read(staffControllerProvider.notifier)
        .transport(
          widget.missionId,
          triage: _triage!,
          ageBand: _age,
          sex: _sex,
          hospitalRef: _other ? null : _hospital,
          hospital: _other ? _name.text : null,
        );
    if (!ok || !mounted) return;
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          sentLabel(l10n, ref.read(staffControllerProvider).pending),
        ),
      ),
    );
    setState(() {
      _triage = null;
      _age = AgeBand.unknown;
      _sex = Sex.unknown;
    });
  }
}

class _TransportRow extends StatelessWidget {
  const _TransportRow({required this.index, required this.transport});

  final int index;
  final Transport transport;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final t = transport;
    final n = Neutrals.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        key: Key('transport-${t.id}'),
        padding: EdgeInsets.zero,
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                width: 8,
                color: triageTone(t.triage).colors(context).fill,
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '#$index · ${triageLabel(l10n, t.triage)}',
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      Text(
                        '${ageLabel(l10n, t.ageBand)} · ${sexLabel(l10n, t.sex)}',
                      ),
                      Text(
                        [
                          t.hospital,
                          if (t.createdAt != null) hhmm(t.createdAt!),
                        ].join(' · '),
                        style: TextStyle(color: n.muted),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
