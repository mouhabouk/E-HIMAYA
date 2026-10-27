import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';

/// The big button of the next step, with a line under it (design §5.2).
class BigStepButton extends StatelessWidget {
  const BigStepButton({
    super.key,
    required this.label,
    required this.icon,
    required this.tone,
    required this.onPressed,
    this.caption,
  });

  final String label;
  final String? caption;
  final IconData icon;
  final Tone tone;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final c = tone.colors(context);
    return FilledButton(
      style: FilledButton.styleFrom(
        backgroundColor: c.fill,
        foregroundColor: c.onFill,
        minimumSize: const Size.fromHeight(76),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Radii.card),
        ),
      ),
      onPressed: onPressed,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 28),
              const SizedBox(width: 10),
              Flexible(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          if (caption != null)
            Text(
              caption!,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
            ),
        ],
      ),
    );
  }
}

/// A large toned choice (severity, triage, yes or no): filled when selected, outlined otherwise,
/// with a check mark so the state never rests on colour alone.
class ToneChoice extends StatelessWidget {
  const ToneChoice({
    super.key,
    required this.label,
    required this.tone,
    required this.selected,
    required this.onTap,
    this.height = 56,
  });

  final String label;
  final Tone tone;
  final bool selected;
  final VoidCallback? onTap;
  final double height;

  @override
  Widget build(BuildContext context) {
    final c = tone.colors(context);
    return Semantics(
      selected: selected,
      button: true,
      child: Material(
        color: selected ? c.fill : c.tint,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Radii.button),
          side: BorderSide(color: c.fill, width: 2),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox(
            height: height,
            child: Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (selected) ...[
                      Icon(Icons.check, size: 18, color: c.onFill),
                      const SizedBox(width: 4),
                    ],
                    Flexible(
                      child: Text(
                        label,
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        style: TextStyle(
                          color: selected ? c.onFill : c.onTint,
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A row of equal [ToneChoice]s.
class ChoiceRow extends StatelessWidget {
  const ChoiceRow({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      for (final (i, w) in children.indexed) ...[
        if (i > 0) const SizedBox(width: 8),
        Expanded(child: w),
      ],
    ],
  );
}

/// One live counter: its name, − value + (each tap is sent at once).
class CounterCell extends StatelessWidget {
  const CounterCell({
    super.key,
    required this.label,
    required this.value,
    required this.keyName,
    required this.tone,
    this.onMinus,
    this.onPlus,
  });

  final String label;
  final int value;
  final String keyName;
  final Tone tone;
  final VoidCallback? onMinus;
  final VoidCallback? onPlus;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = tone.colors(context);
    final n = Neutrals.of(context);
    return AppCard(
      padding: const EdgeInsets.fromLTRB(6, 10, 6, 8),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  color: c.fill,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: n.muted,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              IconButton.filledTonal(
                key: Key('$keyName-minus'),
                tooltip: '${l10n.staffLess}: $label',
                onPressed: onMinus == null || value == 0 ? null : onMinus,
                icon: const Icon(Icons.remove),
              ),
              Semantics(
                liveRegion: true,
                label: '$label: $value',
                excludeSemantics: true,
                child: Text(
                  '$value',
                  key: Key('$keyName-value'),
                  style: Theme.of(context).textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              IconButton.filled(
                key: Key('$keyName-plus'),
                tooltip: '${l10n.staffMore}: $label',
                style: IconButton.styleFrom(
                  backgroundColor: Tone.navy.colors(context).fill,
                  foregroundColor: Colors.white,
                ),
                onPressed: onPlus,
                icon: const Icon(Icons.add),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// The last server refusal, in words the leader can act on.
class StaffErrorText extends ConsumerWidget {
  const StaffErrorText({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final error = ref.watch(staffControllerProvider.select((s) => s.error));
    if (error == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        crewErrorLabel(AppLocalizations.of(context), error),
        key: const Key('staff-error'),
        style: TextStyle(
          color: Theme.of(context).colorScheme.error,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

/// "Request backup" or "danger to the crew": chips, then send (design §5.4).
Future<void> showCrewAlertSheet(
  BuildContext context,
  String missionId,
  String kind,
) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  builder: (_) => _AlertSheet(missionId: missionId, kind: kind),
);

class _AlertSheet extends ConsumerStatefulWidget {
  const _AlertSheet({required this.missionId, required this.kind});

  final String missionId;
  final String kind;

  @override
  ConsumerState<_AlertSheet> createState() => _AlertSheetState();
}

class _AlertSheetState extends ConsumerState<_AlertSheet> {
  final _chosen = <String>{};

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final backup = widget.kind == 'backup';
    final busy = ref.watch(staffControllerProvider.select((s) => s.busy));
    final tone = backup ? Tone.red : Tone.slate;
    return SafeArea(
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.all(20),
        children: [
          Row(
            children: [
              IconTile(
                backup ? Icons.add_alert : Icons.warning_amber,
                tone: tone,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  backup ? l10n.staffAskBackup : l10n.staffCrewDanger,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(l10n.staffAlertChoose),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final k in backup ? backupKinds : dangerKinds)
                FilterChip(
                  key: Key('${widget.kind}-$k'),
                  label: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Text(
                      backup ? backupLabel(l10n, k) : dangerLabel(l10n, k),
                    ),
                  ),
                  selected: _chosen.contains(k),
                  onSelected: (v) =>
                      setState(() => v ? _chosen.add(k) : _chosen.remove(k)),
                ),
            ],
          ),
          const SizedBox(height: 16),
          ToneButton(
            action: BarAction(
              key: Key('send-${widget.kind}'),
              label: l10n.staffSend,
              icon: Icons.send,
              tone: tone,
              onPressed: busy
                  ? null
                  : () async {
                      final messenger = ScaffoldMessenger.of(context);
                      final ok = await ref
                          .read(staffControllerProvider.notifier)
                          .alert(widget.missionId, widget.kind, [
                            for (final k in backup ? backupKinds : dangerKinds)
                              if (_chosen.contains(k)) k,
                          ]);
                      if (!context.mounted) return;
                      Navigator.of(context).pop();
                      messenger.showSnackBar(
                        SnackBar(
                          content: Text(
                            ok
                                ? sentLabel(
                                    l10n,
                                    ref.read(staffControllerProvider).pending,
                                    alert: true,
                                  )
                                : crewErrorLabel(
                                    l10n,
                                    ref.read(staffControllerProvider).error ??
                                        '',
                                  ),
                          ),
                        ),
                      );
                    },
            ),
          ),
        ],
      ),
    );
  }
}

/// Short line about an alert already sent: what, when, and whether the room saw it.
class AlertLine extends StatelessWidget {
  const AlertLine({super.key, required this.alert});

  final CrewAlert alert;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final backup = alert.kind == 'backup';
    final c = (backup ? Tone.red : Tone.slate).colors(context);
    final items = [
      for (final k in alert.items)
        backup ? backupLabel(l10n, k) : dangerLabel(l10n, k),
    ].join('، ');
    final seen = alert.seenAt;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: AppCard(
        key: Key('alert-${alert.id}'),
        color: c.tint,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            Icon(
              backup ? Icons.add_alert : Icons.warning_amber,
              color: c.onTint,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${backup ? l10n.staffAskBackup : l10n.staffCrewDanger} · ${hhmm(alert.createdAt)}',
                    style: TextStyle(
                      color: c.onTint,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  if (items.isNotEmpty)
                    Text(items, style: TextStyle(color: c.onTint)),
                ],
              ),
            ),
            Pill(
              alert.pending
                  ? l10n.staffWaitingBadge
                  : seen == null
                  ? l10n.staffAlertWaiting
                  : l10n.staffAlertSeen(hhmm(seen)),
              tone: seen == null ? Tone.amber : Tone.green,
              icon: alert.pending
                  ? Icons.schedule_send
                  : seen == null
                  ? Icons.schedule
                  : Icons.done_all,
            ),
          ],
        ),
      ),
    );
  }
}

/// Opens [screen] above the current one.
void push(BuildContext context, Widget screen) => unawaited(
  Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen)),
);
