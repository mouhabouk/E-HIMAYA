import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/institution/org_text.dart';
import '../../l10n/app_localizations.dart';
import '../screens/field_widgets.dart';
import '../staff_chrome.dart';
import 'prevention_controller.dart';
import 'prevention_labels.dart';
import 'prevention_models.dart';

/// The decision on the phone (design §8.5): approval, approval with reservations proposed from
/// the non-conformities and their deadlines by chips, or a refusal with its reasons. The same
/// rules as the dashboard; it is sent after the inspection.
class DecisionScreen extends ConsumerStatefulWidget {
  const DecisionScreen({super.key, required this.visitId, this.today});

  final String visitId;

  /// For the tests; the phone's date otherwise.
  final DateTime? today;

  static const validityYears = [1, 2, 3, 5];
  static const dueMonths = [1, 3, 6, 12];

  @override
  ConsumerState<DecisionScreen> createState() => _DecisionScreenState();
}

class _DecisionScreenState extends ConsumerState<DecisionScreen> {
  String? _decision;
  int _years = 1;
  int _months = 3;
  final _reservations = <String>{};
  final _refusal = <String>{};
  final _note = TextEditingController();
  bool _seeded = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  /// Non-conforming items: from the grid on this phone, or the inspection recorded on the server.
  List<String> _nonconform(VisitPack pack) {
    final d = pack.draft;
    final local = [
      for (final i in pack.visit.checklist)
        if (d.item(i.key).result == Finding.nonconform) i.key,
    ];
    return local.isNotEmpty ? local : pack.visit.nonconform;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final pack = ref.watch(
      preventionControllerProvider.select((s) => s.packs[widget.visitId]),
    );
    if (pack == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.prevDecisionTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final keys = _nonconform(pack);
    if (!_seeded) {
      _seeded = true;
      _decision = keys.isEmpty ? 'approved' : 'approved_with_reservations';
      _reservations.addAll(keys);
    }
    final decision = _decision!;
    final queued = pack.draft.decision != null;
    final ready = switch (decision) {
      'approved_with_reservations' => _reservations.isNotEmpty,
      'refused' => _refusal.isNotEmpty || _note.text.trim().isNotEmpty,
      _ => true,
    };
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.prevDecisionTitle,
        subtitle: pack.visit.orgName,
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: [
                if (queued)
                  AppCard(
                    key: const Key('decision-queued'),
                    color: Tone.amber.colors(context).tint,
                    child: Text(l10n.prevDecisionQueued),
                  ),
                SectionTitle(l10n.prevDecisionTitle),
                for (final (wire, tone) in const [
                  ('approved', Tone.green),
                  ('approved_with_reservations', Tone.amber),
                  ('refused', Tone.red),
                ])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: ToneChoice(
                      key: Key('decision-$wire'),
                      label: visitDecisionText(l10n, wire),
                      tone: tone,
                      // Room for two lines of large text.
                      height: MediaQuery.textScalerOf(context).scale(56),
                      selected: decision == wire,
                      onTap: queued
                          ? null
                          : () => setState(() => _decision = wire),
                    ),
                  ),
                if (decision != 'refused') ...[
                  SectionTitle(l10n.prevValidFor),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final y in DecisionScreen.validityYears)
                        ChoiceChip(
                          key: Key('valid-$y'),
                          label: Text(l10n.prevYears(y)),
                          selected: _years == y,
                          onSelected: queued
                              ? null
                              : (_) => setState(() => _years = y),
                        ),
                    ],
                  ),
                ],
                if (decision == 'approved_with_reservations') ...[
                  SectionTitle(l10n.prevReservations),
                  Text(
                    l10n.prevReservationsHelp,
                    style: TextStyle(color: Neutrals.of(context).muted),
                  ),
                  const SizedBox(height: 6),
                  for (final k in keys)
                    CheckboxListTile(
                      key: Key('reservation-$k'),
                      contentPadding: EdgeInsets.zero,
                      value: _reservations.contains(k),
                      title: Text(_reservationText(l10n, pack, k)),
                      onChanged: queued
                          ? null
                          : (on) => setState(
                              () => on == true
                                  ? _reservations.add(k)
                                  : _reservations.remove(k),
                            ),
                    ),
                  SectionTitle(l10n.prevDueIn),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final m in DecisionScreen.dueMonths)
                        ChoiceChip(
                          key: Key('due-$m'),
                          label: Text(l10n.prevMonths(m)),
                          selected: _months == m,
                          onSelected: queued
                              ? null
                              : (_) => setState(() => _months = m),
                        ),
                    ],
                  ),
                ],
                if (decision == 'refused') ...[
                  SectionTitle(l10n.prevRefusalReason),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final r in refusalReasons)
                        FilterChip(
                          key: Key('refuse-$r'),
                          label: Text(refusalLabel(l10n, r)),
                          selected: _refusal.contains(r),
                          onSelected: queued
                              ? null
                              : (on) => setState(
                                  () =>
                                      on ? _refusal.add(r) : _refusal.remove(r),
                                ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    key: const Key('refusal-note'),
                    controller: _note,
                    enabled: !queued,
                    maxLength: 500,
                    decoration: InputDecoration(
                      labelText: l10n.prevNoteOptional,
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                ],
                if (pack.draft.error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      visitErrorLabel(l10n, pack.draft.error!),
                      key: const Key('decision-error'),
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: queued
          ? null
          : BottomActionBar(
              actions: [
                BarAction(
                  key: const Key('send-decision'),
                  label: l10n.prevSendDecision,
                  icon: Icons.gavel,
                  tone: Tone.navy,
                  onPressed: ready
                      ? () => unawaited(_send(pack, decision))
                      : null,
                ),
              ],
            ),
    );
  }

  String _reservationText(AppLocalizations l10n, VisitPack pack, String key) {
    final note = findingNote(l10n, pack.draft.item(key));
    return note.isEmpty
        ? itemLabel(l10n, key)
        : '${itemLabel(l10n, key)}: $note';
  }

  Future<void> _send(VisitPack pack, String decision) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final nav = Navigator.of(context);
    final today = widget.today ?? DateTime.now();
    final due = isoDay(addMonths(today, _months));
    final body = <String, dynamic>{
      'decision': decision,
      if (decision != 'refused')
        'valid_until': isoDay(addMonths(today, 12 * _years)),
      if (decision == 'refused')
        'reason': [
          for (final r in refusalReasons)
            if (_refusal.contains(r)) refusalLabel(l10n, r),
          if (_note.text.trim().isNotEmpty) _note.text.trim(),
        ].join('، '),
      'reservations': [
        if (decision == 'approved_with_reservations')
          for (final k in _nonconform(pack))
            if (_reservations.contains(k))
              {
                'text': _reservationText(l10n, pack, k),
                'due_on': due,
                'item_key': k,
              },
      ],
    };
    final c = ref.read(preventionControllerProvider.notifier);
    await c.decide(widget.visitId, body);
    final left = ref.read(preventionControllerProvider).packs[widget.visitId];
    // Refused by the server: the reason stays on this screen.
    if (left != null && left.draft.decision == null) return;
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          left == null ? l10n.prevDecisionSent : l10n.prevDecisionQueued,
        ),
      ),
    );
    if (nav.mounted) {
      if (left == null) {
        nav.popUntil((r) => r.isFirst);
      } else {
        nav.pop();
      }
    }
  }
}
