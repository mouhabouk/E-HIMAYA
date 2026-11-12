import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/report/category_labels.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import 'field_widgets.dart';

/// One address warning of a mission (OS8, design-os8.md §5): a mark whose circle holds the incident.
class AddressWarning {
  const AddressWarning({
    required this.markerId,
    required this.category,
    required this.categoryName,
    required this.personal,
    required this.address,
    required this.description,
    required this.distanceM,
    required this.critical,
    required this.offHours,
    this.teamAckAt,
  });

  factory AddressWarning.fromJson(Map<String, dynamic> j) => AddressWarning(
    markerId: j['marker_id'] as String,
    category: j['category'] as String,
    categoryName: (j['category_name'] as String?) ?? j['category'] as String,
    personal: j['personal'] as bool? ?? false,
    address: j['address'] as String? ?? '',
    description: j['description'] as String? ?? '',
    distanceM: (j['distance_m'] as num?)?.round() ?? 0,
    critical: j['critical'] as bool? ?? false,
    offHours: j['off_hours'] as bool? ?? false,
    teamAckAt: DateTime.tryParse(j['team_ack_at'] as String? ?? ''),
  );

  final String markerId;
  final String category;
  final String categoryName;
  final bool personal;
  final String address;
  final String description;
  final int distanceM;
  final bool critical;
  final bool offHours;
  final DateTime? teamAckAt;
}

/// The warnings the team sees for its mission, most dangerous first.
class MissionWarnings {
  const MissionWarnings({
    required this.kind,
    required this.items,
    required this.unread,
  });

  factory MissionWarnings.fromJson(Map<String, dynamic> j) => MissionWarnings(
    kind: j['incident_kind'] as String? ?? 'other',
    items: [
      for (final w in j['items'] as List? ?? const [])
        AddressWarning.fromJson(w as Map<String, dynamic>),
    ],
    unread: (j['unread'] as num?)?.toInt() ?? 0,
  );

  final String kind;
  final List<AddressWarning> items;
  final int unread;

  int get critical => items.where((w) => w.critical).length;
}

/// The marks a leader may propose from the scene (the personal ones come from their owners only).
const proposableCategories = [
  'gas',
  'chem',
  'fuel',
  'batt',
  'coll',
  'acc',
  'dog',
  'occ',
];

String awCategoryLabel(AppLocalizations l10n, String key) => switch (key) {
  'gas' => l10n.awCatGas,
  'chem' => l10n.awCatChem,
  'fuel' => l10n.awCatFuel,
  'batt' => l10n.awCatBatt,
  'coll' => l10n.awCatColl,
  'acc' => l10n.awCatAcc,
  'dog' => l10n.awCatDog,
  'occ' => l10n.awCatOcc,
  'mob' => l10n.awCatMob,
  'oxy' => l10n.awCatOxy,
  'deaf' => l10n.awCatDeaf,
  _ => key,
};

IconData awCategoryIcon(String key) => switch (key) {
  'gas' => Icons.propane_tank,
  'chem' => Icons.science,
  'fuel' => Icons.local_gas_station,
  'batt' => Icons.bolt,
  'coll' => Icons.domain_disabled,
  'acc' => Icons.remove_road,
  'dog' => Icons.pets,
  'occ' => Icons.groups,
  'mob' => Icons.accessible,
  'oxy' => Icons.air,
  'deaf' => Icons.hearing_disabled,
  _ => Icons.warning_amber,
};

/// The warnings of a mission, read from the server each time the screen opens (none without network).
final missionWarningsProvider = FutureProvider.autoDispose
    .family<MissionWarnings, String>(
      (ref, missionId) async => MissionWarnings.fromJson(
        await ref.watch(staffApiProvider).addressWarnings(missionId),
      ),
    );

/// The line on the mission screen: how many warnings, the most dangerous one, read or not.
class AddressWarningsCard extends ConsumerWidget {
  const AddressWarningsCard({super.key, required this.missionId});

  final String missionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final w = ref.watch(missionWarningsProvider(missionId)).value;
    if (w == null) return const SizedBox.shrink();
    final first = w.items.isEmpty ? null : w.items.first;
    final tone = w.items.isEmpty
        ? Tone.slate
        : w.unread == 0
        ? Tone.green
        : w.critical > 0
        ? Tone.red
        : Tone.amber;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: NavCard(
        key: const Key('open-address-warnings'),
        icon: Icons.warning_amber,
        tone: tone,
        title: w.items.isEmpty ? l10n.awNone : l10n.awCardTitle(w.items.length),
        subtitle: first == null
            ? l10n.awProposeHint
            : w.unread == 0
            ? l10n.awAllRead
            : '${first.categoryName} · ${first.description}',
        onTap: () => push(context, AddressWarningsScreen(missionId: missionId)),
      ),
    );
  }
}

/// The warnings of a mission in full, «قرأت التحذيرات», and a mark proposed from the scene.
class AddressWarningsScreen extends ConsumerStatefulWidget {
  const AddressWarningsScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<AddressWarningsScreen> createState() =>
      _AddressWarningsScreenState();
}

class _AddressWarningsScreenState extends ConsumerState<AddressWarningsScreen> {
  bool _busy = false;

  Future<void> _ack() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      await ref.read(staffApiProvider).ackAddressWarnings(widget.missionId);
      ref.invalidate(missionWarningsProvider(widget.missionId));
      messenger.showSnackBar(SnackBar(content: Text(l10n.awAcked)));
    } on Object {
      messenger.showSnackBar(SnackBar(content: Text(l10n.awFailed)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final readOnly = s.me?.readOnly ?? false;
    final async = ref.watch(missionWarningsProvider(widget.missionId));
    final w = async.value;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.awTitle),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (async.isLoading && w == null)
            const Center(child: CircularProgressIndicator()),
          if (async.hasError && w == null) Text(l10n.awFailed),
          if (w != null) ...[
            if (w.items.isEmpty) Text(l10n.awNone),
            for (final x in w.items) _WarningTile(warning: x, kind: w.kind),
            const SizedBox(height: 12),
            if (!readOnly && w.unread > 0)
              FilledButton.icon(
                key: const Key('aw-ack'),
                onPressed: _busy ? null : _ack,
                icon: const Icon(Icons.done_all),
                label: Text(l10n.awAck),
              ),
            if (!readOnly) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                key: const Key('aw-propose'),
                onPressed: () => unawaited(
                  showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    builder: (_) => _ProposeSheet(missionId: widget.missionId),
                  ),
                ),
                icon: const Icon(Icons.add_location_alt),
                label: Text(l10n.awPropose),
              ),
            ],
            const SizedBox(height: 12),
            Text(l10n.awNote, style: Theme.of(context).textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class _WarningTile extends StatelessWidget {
  const _WarningTile({required this.warning, required this.kind});

  final AddressWarning warning;
  final String kind;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final w = warning;
    final tone = w.critical
        ? Tone.red
        : w.personal
        ? Tone.green
        : w.offHours
        ? Tone.slate
        : Tone.amber;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        key: Key('aw-${w.markerId}'),
        borderColor: w.critical ? tone.colors(context).fill : null,
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            IconTile(awCategoryIcon(w.category), tone: tone),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(w.categoryName, style: theme.textTheme.titleSmall),
                  const SizedBox(height: 2),
                  Text(w.description),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      if (w.critical)
                        Pill(
                          l10n.awCriticalWith(
                            categoryLabel(
                              l10n,
                              ReportCategory.fromWire(kind) ??
                                  ReportCategory.other,
                            ),
                          ),
                          tone: Tone.red,
                          icon: Icons.warning,
                        ),
                      Pill(l10n.awDistance(w.distanceM), tone: Tone.slate),
                      if (w.offHours) Pill(l10n.awOffHours, tone: Tone.slate),
                      if (w.personal) Pill(l10n.awConsent, tone: Tone.green),
                      if (w.teamAckAt != null)
                        Pill(
                          l10n.awReadAt(hhmm(w.teamAckAt!)),
                          tone: Tone.green,
                          icon: Icons.check,
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProposeSheet extends ConsumerStatefulWidget {
  const _ProposeSheet({required this.missionId});

  final String missionId;

  @override
  ConsumerState<_ProposeSheet> createState() => _ProposeSheetState();
}

class _ProposeSheetState extends ConsumerState<_ProposeSheet> {
  String _category = proposableCategories.first;
  final _text = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final nav = Navigator.of(context);
    setState(() => _busy = true);
    try {
      final here = ref.read(staffPositionProvider).value;
      await ref
          .read(staffApiProvider)
          .proposeAddressWarning(
            widget.missionId,
            category: _category,
            description: _text.text.trim(),
            location: here,
          );
      nav.pop();
      messenger.showSnackBar(SnackBar(content: Text(l10n.awProposed)));
    } on Object {
      if (mounted) setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(l10n.awFailed)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        16,
        16,
        16 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionTitle(l10n.awPropose),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final c in proposableCategories)
                ChoiceChip(
                  key: Key('aw-cat-$c'),
                  avatar: Icon(awCategoryIcon(c), size: 18),
                  label: Text(awCategoryLabel(l10n, c)),
                  selected: _category == c,
                  onSelected: (_) => setState(() => _category = c),
                ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('aw-text'),
            controller: _text,
            maxLines: 3,
            maxLength: 500,
            decoration: InputDecoration(labelText: l10n.awProposeText),
            onChanged: (_) => setState(() {}),
          ),
          Text(
            l10n.awProposeHint,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          FilledButton(
            key: const Key('aw-send'),
            onPressed: _busy || _text.text.trim().length < 3 ? null : _send,
            child: Text(l10n.awProposeSend),
          ),
        ],
      ),
    );
  }
}
