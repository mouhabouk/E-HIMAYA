import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/ui/components.dart';
import '../core/ui/tokens.dart';
import '../l10n/app_localizations.dart';
import 'staff_api.dart';
import 'staff_controller.dart' show staffApiProvider;

/// OS3-1 (docs/phase-os3/design-os3b.md §1, Yamen 2026-11-13): the room sends the vehicle on shift to
/// another unit as reinforcement, or back to its own unit. A content-free push rings the leader's
/// phone; the order is fetched here and the leader says the crew saw it, left and arrived.
class RepositionOrder {
  const RepositionOrder({
    required this.id,
    required this.kind,
    required this.fromUnit,
    required this.toUnit,
    required this.state,
    required this.createdAt,
    this.createdBy,
    this.note,
    this.seenAt,
    this.departedAt,
    this.arrivedAt,
  });

  factory RepositionOrder.fromJson(Map<String, dynamic> j) => RepositionOrder(
    id: j['id'] as String,
    kind: j['kind'] as String,
    fromUnit: j['from_unit'] as String,
    toUnit: j['to_unit'] as String,
    state: j['state'] as String,
    createdAt: DateTime.parse(j['created_at'] as String),
    createdBy: j['created_by_name'] as String?,
    note: j['note'] as String?,
    seenAt: _at(j['seen_at']),
    departedAt: _at(j['departed_at']),
    arrivedAt: _at(j['arrived_at']),
  );

  static DateTime? _at(Object? v) => v is String ? DateTime.parse(v) : null;

  final String id;

  /// `reinforce` or `return`.
  final String kind;
  final String fromUnit;
  final String toUnit;

  /// `sent`, `seen`, `departed`, `arrived` or `closed`.
  final String state;
  final DateTime createdAt;
  final String? createdBy;
  final String? note;
  final DateTime? seenAt;
  final DateTime? departedAt;
  final DateTime? arrivedAt;

  bool get open => state != 'arrived' && state != 'closed';
}

extension RepositionApi on StaffApi {
  /// The orders of the vehicle on shift: the open ones and those of the last hours.
  Future<List<RepositionOrder>> repositions() async {
    final r = await repositionsJson();
    final items = r['items'];
    return [
      if (items is List)
        for (final o in items)
          RepositionOrder.fromJson(o as Map<String, dynamic>),
    ];
  }

  /// `seen`, `departed` or `arrived`; [at] is when it happened (an offline phone sends it later).
  Future<RepositionOrder> repositionStep(
    String id,
    String step,
    DateTime at,
  ) async => RepositionOrder.fromJson(await repositionStepJson(id, step, at));
}

final repositionsProvider = FutureProvider.autoDispose<List<RepositionOrder>>(
  (ref) => ref.read(staffApiProvider).repositions(),
);

/// The open orders on top of the missions, with the three steps for the leader.
class RepositionCards extends ConsumerWidget {
  const RepositionCards({super.key, required this.leader});

  final bool leader;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orders = ref.watch(repositionsProvider).asData?.value ?? const [];
    final shown = [
      for (final o in orders)
        if (o.open) o,
    ];
    if (shown.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final o in shown)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _OrderCard(o, leader: leader),
          ),
      ],
    );
  }
}

class _OrderCard extends ConsumerStatefulWidget {
  const _OrderCard(this.order, {required this.leader});

  final RepositionOrder order;
  final bool leader;

  @override
  ConsumerState<_OrderCard> createState() => _OrderCardState();
}

class _OrderCardState extends ConsumerState<_OrderCard> {
  bool _busy = false;

  Future<void> _step(String step) async {
    setState(() => _busy = true);
    try {
      await ref
          .read(staffApiProvider)
          .repositionStep(widget.order.id, step, DateTime.now());
    } on Object {
      // The card stays as it was; the next refresh shows the order again.
    } finally {
      if (mounted) setState(() => _busy = false);
      ref.invalidate(repositionsProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final o = widget.order;
    final time = MaterialLocalizations.of(context);
    String hm(DateTime d) =>
        time.formatTimeOfDay(TimeOfDay.fromDateTime(d.toLocal()));
    final steps = <(String, String, DateTime?)>[
      ('seen', l10n.staffRepositionSeen, o.seenAt),
      ('departed', l10n.staffRepositionDeparted, o.departedAt),
      ('arrived', l10n.staffRepositionArrived, o.arrivedAt),
    ];
    final next = steps.where((s) => s.$3 == null).firstOrNull;
    return AppCard(
      key: Key('reposition-${o.id}'),
      borderColor: Tone.purple.colors(context).fill,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.swap_horiz, color: Tone.purple.colors(context).fill),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  l10n.staffRepositionTitle,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            o.kind == 'return'
                ? l10n.staffRepositionReturn(o.fromUnit, o.toUnit)
                : l10n.staffRepositionReinforce(o.fromUnit, o.toUnit),
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          if (o.createdBy != null)
            Text(l10n.staffRepositionBy(o.createdBy!, hm(o.createdAt))),
          if (o.note != null && o.note!.isNotEmpty) Text(o.note!),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final s in steps)
                if (s.$3 != null)
                  Pill(
                    l10n.staffRepositionStepDone(s.$2, hm(s.$3!)),
                    tone: Tone.green,
                    icon: Icons.check,
                  ),
            ],
          ),
          if (next != null) ...[
            const SizedBox(height: 12),
            if (widget.leader)
              FilledButton(
                key: Key('reposition-${next.$1}'),
                onPressed: _busy ? null : () => unawaited(_step(next.$1)),
                child: Text(next.$2),
              )
            else
              Text(l10n.staffRepositionLeaderOnly),
          ],
        ],
      ),
    );
  }
}
