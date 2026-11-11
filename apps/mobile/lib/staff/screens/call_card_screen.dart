import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import 'field_widgets.dart';

/// The band of a call-taking card in the words of the app.
String cardBandLabel(AppLocalizations l10n, String band) => switch (band) {
  'critical' => l10n.staffCardBandCritical,
  'high' => l10n.staffCardBandHigh,
  'low' => l10n.staffCardBandLow,
  _ => l10n.staffCardBandNormal,
};

Tone cardBandTone(String band) => switch (band) {
  'critical' || 'high' => Tone.red,
  'low' => Tone.slate,
  _ => Tone.amber,
};

String cardAnswerLabel(AppLocalizations l10n, String answer) =>
    switch (answer) {
      'yes' => l10n.staffCardYes,
      'no' => l10n.staffCardNo,
      _ => l10n.staffCardUnknown,
    };

const cardAnswers = ['yes', 'no', 'unknown'];

/// OS2: the call-taking card on the mission. The team reads what the caller answered and the
/// instructions read to them; the leader completes the card from the scene (what stayed «doesn't
/// know», what the scene contradicts). The room sees it at once; the band never goes down.
class CallCardScreen extends ConsumerStatefulWidget {
  const CallCardScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<CallCardScreen> createState() => _CallCardScreenState();
}

class _CallCardScreenState extends ConsumerState<CallCardScreen> {
  final Map<String, String> _picked = {};

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = ref.read(staffControllerProvider.notifier);
    final m = s.mission(widget.missionId);
    final card = m?.callCard;
    if (m == null || card == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffCallCard),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final readOnly = s.me?.readOnly ?? false;
    String? known(String id) => _picked[id] ?? card.answerOf(id);
    // A follow-up shows once the question it follows has its answer, as in the room.
    final shown = [
      for (final q in card.questions)
        if (q.whenQuestion == null || known(q.whenQuestion!) == q.whenAnswer) q,
    ];
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffCallCard,
        subtitle: '${card.title} · v${card.version}${card.sim ? ' [SIM]' : ''}',
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                AppCard(
                  borderColor: cardBandTone(card.currentBand)
                      .colors(context)
                      .fill,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Pill(
                        l10n.staffCardBand(cardBandLabel(l10n, card.band)),
                        tone: cardBandTone(card.band),
                        icon: Icons.call,
                      ),
                      if (card.fieldBand != null) ...[
                        const SizedBox(height: 6),
                        Pill(
                          l10n.staffCardFieldBand(
                            cardBandLabel(l10n, card.fieldBand!),
                          ),
                          tone: cardBandTone(card.fieldBand!),
                          icon: Icons.groups,
                        ),
                      ],
                      if (card.flags.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            for (final f in card.flags)
                              Pill(
                                f,
                                tone: Tone.red,
                                icon: Icons.warning_amber,
                              ),
                          ],
                        ),
                      ],
                      const SizedBox(height: 8),
                      Text(
                        l10n.staffCallCardHelp,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                for (final q in shown) ...[
                  AppCard(
                    key: Key('card-q-${q.id}'),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                q.text,
                                style: Theme.of(context).textTheme.titleSmall,
                              ),
                            ),
                            if (q.key) Pill(l10n.staffCardKey, tone: Tone.red),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          card.answers[q.id] == null
                              ? l10n.staffCardCallerNone
                              : l10n.staffCardCaller(
                                  cardAnswerLabel(l10n, card.answers[q.id]!),
                                ),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          children: [
                            for (final a in cardAnswers)
                              ChoiceChip(
                                key: Key('card-${q.id}-$a'),
                                label: Text(cardAnswerLabel(l10n, a)),
                                selected:
                                    (_picked[q.id] ??
                                        card.fieldAnswers[q.id]) ==
                                    a,
                                onSelected: readOnly
                                    ? null
                                    : (_) => setState(() => _picked[q.id] = a),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                if (card.instructions.isNotEmpty) ...[
                  SectionTitle(l10n.staffCardRead),
                  for (final e in card.instructions.entries)
                    AppCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            e.key,
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          for (final (i, step) in e.value.indexed)
                            Text('${i + 1}. $step'),
                        ],
                      ),
                    ),
                ],
                const StaffErrorText(),
                if (!readOnly) ...[
                  const SizedBox(height: 12),
                  ToneButton(
                    action: BarAction(
                      key: const Key('card-send'),
                      label: l10n.staffRecordSend,
                      icon: Icons.send,
                      tone: Tone.green,
                      onPressed: s.busy || _picked.isEmpty
                          ? null
                          : () async {
                              final shownIds = {for (final q in shown) q.id};
                              final ok = await c.callCard(m.id, {
                                for (final e in _picked.entries)
                                  if (shownIds.contains(e.key)) e.key: e.value,
                              });
                              if (ok && context.mounted) {
                                Navigator.of(context).pop();
                              }
                            },
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
