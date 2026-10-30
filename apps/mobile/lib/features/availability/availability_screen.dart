import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/http/availability_models.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';

/// The availability calendar of a volunteer or a doctor (phase N, docs/phase-n/design-n.md §8):
/// periods when they are available or away, every day or on some weekdays, between two hours.
/// The whole calendar is sent at once; the room reads it, and the call-up skips a volunteer
/// whose calendar says unavailable now.
class AvailabilityScreen extends ConsumerStatefulWidget {
  const AvailabilityScreen({super.key, required this.role});

  final CalendarRole role;

  @override
  ConsumerState<AvailabilityScreen> createState() => _AvailabilityScreenState();
}

class _AvailabilityScreenState extends ConsumerState<AvailabilityScreen> {
  List<AvailabilitySlot>? _slots;
  SlotKind? _now;
  Object? _error;
  bool _busy = false;
  bool _dirty = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final c = await ref.read(apiProvider).myAvailability(widget.role);
      if (!mounted) return;
      setState(() {
        _slots = c.slots;
        _now = c.plannedNow;
        _error = null;
      });
    } on Object catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _save() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final c = await ref
          .read(apiProvider)
          .putAvailability(widget.role, _slots!);
      if (!mounted) return;
      setState(() {
        _slots = c.slots;
        _now = c.plannedNow;
        _dirty = false;
      });
      messenger.showSnackBar(SnackBar(content: Text(l10n.availabilitySaved)));
    } on Object catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(errorMessageFor(l10n, e))));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _add() async {
    final slot = await showModalBottomSheet<AvailabilitySlot>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _SlotSheet(),
    );
    if (slot != null && mounted) {
      setState(() {
        _slots = [..._slots!, slot];
        _dirty = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final slots = _slots;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.availabilityTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: switch ((slots, _error)) {
        (null, null) => const Center(child: CircularProgressIndicator()),
        (null, final Object e) => ListView(
          padding: const EdgeInsets.all(24),
          children: [Text(errorMessageFor(l10n, e))],
        ),
        (final List<AvailabilitySlot> slots, _) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.availabilityIntro),
            const SizedBox(height: 12),
            _NowChip(now: _now),
            const SizedBox(height: 12),
            if (slots.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  l10n.availabilityEmpty,
                  textAlign: TextAlign.center,
                ),
              ),
            for (final (i, s) in slots.indexed)
              _SlotTile(
                key: Key('availability-slot-$i'),
                slot: s,
                onRemove: () => setState(() {
                  _slots = [...slots]..removeAt(i);
                  _dirty = true;
                }),
              ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              key: const Key('availability-add'),
              icon: const Icon(Icons.add),
              label: Text(
                slots.length >= maxAvailabilitySlots
                    ? l10n.availabilityMax
                    : l10n.availabilityAdd,
              ),
              onPressed: slots.length >= maxAvailabilitySlots ? null : _add,
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              key: const Key('availability-save'),
              icon: const Icon(Icons.save),
              label: Text(l10n.availabilitySave),
              onPressed: _busy || !_dirty ? null : _save,
            ),
          ],
        ),
      },
    );
  }
}

class _NowChip extends StatelessWidget {
  const _NowChip({required this.now});
  final SlotKind? now;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (tone, text) = switch (now) {
      SlotKind.available => (Tone.green, l10n.availabilityNowAvailable),
      SlotKind.unavailable => (Tone.red, l10n.availabilityNowUnavailable),
      null => (Tone.slate, l10n.availabilityNowNone),
    };
    final colours = tone.colors(context);
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Chip(
        key: const Key('availability-now'),
        backgroundColor: colours.tint,
        label: Text(text, style: TextStyle(color: colours.onTint)),
      ),
    );
  }
}

/// Weekday names of the person's language, ISO order (1 Monday … 7 Sunday).
List<String> weekdayNames(String lang) => [
  // 2024-01-01 was a Monday.
  for (var d = 1; d <= 7; d++) DateFormat.E(lang).format(DateTime(2024, 1, d)),
];

class _SlotTile extends ConsumerWidget {
  const _SlotTile({super.key, required this.slot, required this.onRemove});
  final AvailabilitySlot slot;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final date = DateFormat.yMMMd(lang);
    final days = weekdayNames(lang);
    final dates = slot.endsOn == null
        ? l10n.availabilityFromDate(date.format(slot.startsOn))
        : l10n.availabilityBetween(
            date.format(slot.startsOn),
            date.format(slot.endsOn!),
          );
    final which = slot.weekdays.isEmpty
        ? l10n.availabilityEveryDay
        : [for (final d in slot.weekdays) days[d - 1]].join('، ');
    final hours =
        '${AvailabilitySlot.hhmm(slot.from)}–${AvailabilitySlot.hhmm(slot.to)}'
        '${slot.overnight ? ' (${l10n.availabilityOvernight})' : ''}';
    final available = slot.kind == SlotKind.available;
    final colours = (available ? Tone.green : Tone.red).colors(context);
    return Card(
      child: ListTile(
        leading: Icon(
          available ? Icons.event_available : Icons.event_busy,
          color: colours.fill,
        ),
        title: Text(
          available
              ? l10n.availabilityKindAvailable
              : l10n.availabilityKindUnavailable,
        ),
        subtitle: Text('$dates\n$which · $hours'),
        isThreeLine: true,
        trailing: IconButton(
          tooltip: l10n.availabilityRemove,
          icon: const Icon(Icons.delete_outline),
          onPressed: onRemove,
        ),
      ),
    );
  }
}

class _SlotSheet extends ConsumerStatefulWidget {
  const _SlotSheet();

  @override
  ConsumerState<_SlotSheet> createState() => _SlotSheetState();
}

class _SlotSheetState extends ConsumerState<_SlotSheet> {
  SlotKind _kind = SlotKind.available;
  final Set<int> _weekdays = {};
  DateTime _starts = DateUtils.dateOnly(DateTime.now());
  DateTime? _ends;
  TimeOfDay _from = const TimeOfDay(hour: 8, minute: 0);
  TimeOfDay _to = const TimeOfDay(hour: 20, minute: 0);

  int _minutes(TimeOfDay t) => t.hour * 60 + t.minute;

  Future<void> _pickDate({required bool end}) async {
    final first = end ? _starts : DateUtils.dateOnly(DateTime.now());
    final picked = await showDatePicker(
      context: context,
      firstDate: first,
      lastDate: first.add(const Duration(days: 730)),
      initialDate: end ? (_ends ?? _starts) : _starts,
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (end) {
        _ends = picked;
      } else {
        _starts = picked;
        if (_ends != null && _ends!.isBefore(picked)) _ends = picked;
      }
    });
  }

  Future<void> _pickTime({required bool end}) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: end ? _to : _from,
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (end) {
        _to = picked;
      } else {
        _from = picked;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final date = DateFormat.yMMMd(lang);
    final days = weekdayNames(lang);
    final sameHours = _minutes(_from) == _minutes(_to);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          16,
          16,
          16 + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                l10n.availabilityAdd,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              SegmentedButton<SlotKind>(
                key: const Key('availability-kind'),
                segments: [
                  ButtonSegment(
                    value: SlotKind.available,
                    label: Text(l10n.availabilityKindAvailable),
                  ),
                  ButtonSegment(
                    value: SlotKind.unavailable,
                    label: Text(l10n.availabilityKindUnavailable),
                  ),
                ],
                selected: {_kind},
                onSelectionChanged: (s) => setState(() => _kind = s.first),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (var d = 1; d <= 7; d++)
                    FilterChip(
                      key: Key('availability-day-$d'),
                      label: Text(days[d - 1]),
                      selected: _weekdays.contains(d),
                      onSelected: (on) => setState(
                        () => on ? _weekdays.add(d) : _weekdays.remove(d),
                      ),
                    ),
                ],
              ),
              if (_weekdays.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    l10n.availabilityEveryDay,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              const SizedBox(height: 8),
              ListTile(
                key: const Key('availability-starts'),
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.event),
                title: Text(l10n.availabilityStartsOn),
                subtitle: Text(date.format(_starts)),
                onTap: () => _pickDate(end: false),
              ),
              ListTile(
                key: const Key('availability-ends'),
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.event),
                title: Text(l10n.availabilityEndsOn),
                subtitle: Text(
                  _ends == null ? l10n.availabilityNoEnd : date.format(_ends!),
                ),
                onTap: () => _pickDate(end: true),
                trailing: _ends == null
                    ? null
                    : IconButton(
                        tooltip: l10n.availabilityNoEnd,
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(() => _ends = null),
                      ),
              ),
              Row(
                children: [
                  Expanded(
                    child: ListTile(
                      key: const Key('availability-from'),
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(Icons.schedule),
                      title: Text(l10n.availabilityFromTime),
                      subtitle: Text(AvailabilitySlot.hhmm(_minutes(_from))),
                      onTap: () => _pickTime(end: false),
                    ),
                  ),
                  Expanded(
                    child: ListTile(
                      key: const Key('availability-to'),
                      contentPadding: EdgeInsets.zero,
                      title: Text(l10n.availabilityToTime),
                      subtitle: Text(
                        AvailabilitySlot.hhmm(_minutes(_to)) +
                            (_minutes(_to) < _minutes(_from)
                                ? ' (${l10n.availabilityOvernight})'
                                : ''),
                      ),
                      onTap: () => _pickTime(end: true),
                    ),
                  ),
                ],
              ),
              if (sameHours)
                Text(
                  l10n.availabilityEmptyHours,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              const SizedBox(height: 12),
              FilledButton(
                key: const Key('availability-ok'),
                onPressed: sameHours
                    ? null
                    : () => Navigator.of(context).pop(
                        AvailabilitySlot(
                          kind: _kind,
                          weekdays: [..._weekdays]..sort(),
                          startsOn: _starts,
                          endsOn: _ends,
                          from: _minutes(_from),
                          to: _minutes(_to),
                        ),
                      ),
                child: Text(l10n.availabilityOk),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
