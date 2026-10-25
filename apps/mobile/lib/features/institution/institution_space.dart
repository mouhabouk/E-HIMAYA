import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/http/notify_models.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/tus/tus_client.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import 'institution_providers.dart';
import 'maintenance_photo.dart';

/// The institution space of phase P2b (docs/phase-p2/design-institutions-app.md §5): Office
/// messages with their read acknowledgement, awareness for the institution's kind, drills and
/// public events, and the maintenance of an equipment with its photo.

class _Note extends StatelessWidget {
  const _Note(this.text, {this.error = false});

  final String text;
  final bool error;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24),
    child: Text(
      text,
      textAlign: TextAlign.center,
      style: error
          ? TextStyle(color: Theme.of(context).colorScheme.error)
          : null,
    ),
  );
}

Widget _loading() => const Padding(
  padding: EdgeInsets.all(24),
  child: Center(child: CircularProgressIndicator()),
);

bool _canEdit(WidgetRef ref, String orgId) {
  final role = ref.watch(myOrgRoleProvider(orgId));
  return role == 'admin' || role == 'editor';
}

void _snack(ScaffoldMessengerState messenger, String text) => messenger
  ..hideCurrentSnackBar()
  ..showSnackBar(SnackBar(content: Text(text)));

DateTime _day(DateTime t) => DateTime(t.year, t.month, t.day);

// ---------------------------------------------------------------- Office messages

class OrgMessagesSection extends ConsumerWidget {
  const OrgMessagesSection({super.key, required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final canAck = _canEdit(ref, orgId);
    return ref
        .watch(orgMessagesProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgMessagesEmpty),
              if (!canAck && items.any((m) => m.waiting))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    l10n.orgMessageAckEditors,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              for (final m in items) ...[
                _MessageCard(orgId: orgId, message: m, canAck: canAck),
                const SizedBox(height: 8),
              ],
            ],
          ),
        );
  }
}

class _MessageCard extends ConsumerStatefulWidget {
  const _MessageCard({
    required this.orgId,
    required this.message,
    required this.canAck,
  });

  final String orgId;
  final OrgMessage message;
  final bool canAck;

  @override
  ConsumerState<_MessageCard> createState() => _MessageCardState();
}

class _MessageCardState extends ConsumerState<_MessageCard> {
  bool _busy = false;

  Future<void> _ack() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      await ref
          .read(apiProvider)
          .ackOrgMessage(widget.orgId, widget.message.id);
      ref.invalidate(orgMessagesProvider(widget.orgId));
      ref.invalidate(orgSummaryProvider(widget.orgId));
      _snack(messenger, l10n.orgMessageAckDone);
    } on ApiException catch (e) {
      _snack(messenger, apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final lang = ref.watch(localeCodeProvider);
    final m = widget.message;
    final date = DateFormat.yMMMd(lang);
    return AppCard(
      key: Key('org-message-${m.id}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconTile(
                m.waiting ? Icons.mark_email_unread : Icons.mail,
                tone: m.waiting ? Tone.red : Tone.navy,
                soft: !m.waiting,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      OrgMessage.pick(m.title, lang),
                      style: theme.textTheme.titleMedium,
                    ),
                    Text(
                      date.format(m.publishedAt.toLocal()),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(OrgMessage.pick(m.body, lang)),
          if (m.ackRequired) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (m.ackedAt case final DateTime at)
                  Pill(
                    l10n.orgMessageAcked(date.format(at.toLocal())),
                    tone: Tone.green,
                    icon: Icons.done_all,
                  )
                else
                  Pill(
                    l10n.orgMessageWaiting,
                    tone: Tone.amber,
                    icon: Icons.schedule,
                  ),
                if (m.ackedBy case final String who)
                  Text(who, style: theme.textTheme.bodySmall),
              ],
            ),
          ],
          if (m.waiting && widget.canAck)
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: FilledButton.icon(
                key: Key('org-message-ack-${m.id}'),
                onPressed: _busy ? null : _ack,
                icon: const Icon(Icons.done),
                label: Text(l10n.orgMessageAck),
              ),
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- awareness

class OrgAwarenessSection extends ConsumerWidget {
  const OrgAwarenessSection({super.key, required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    return ref
        .watch(orgAwarenessProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (tips) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (tips.isEmpty)
                _Note(l10n.orgAwarenessEmpty)
              else
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(l10n.orgAwarenessIntro),
                ),
              for (final t in tips) ...[
                _AwarenessCard(tip: t, lang: lang),
                const SizedBox(height: 8),
              ],
            ],
          ),
        );
  }
}

class _AwarenessCard extends StatelessWidget {
  const _AwarenessCard({required this.tip, required this.lang});

  final SafetyTip tip;
  final String lang;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final text = tip.textFor(lang);
    final title = text.title.trim().isEmpty
        ? tipHazardLabel(l10n, tip.hazard)
        : text.title;
    Widget line(String item, IconData icon, Color color) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Text(item)),
        ],
      ),
    );
    return AppCard(
      key: Key('org-awareness-${tip.id ?? tip.hazard.wire}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconTile(tipHazardIcon(tip.hazard), tone: Tone.green),
              const SizedBox(width: 12),
              Expanded(child: Text(title, style: theme.textTheme.titleMedium)),
            ],
          ),
          if (text.doItems.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              l10n.tipsDo,
              style: theme.textTheme.titleSmall?.copyWith(
                color: theme.colorScheme.primary,
              ),
            ),
            for (final i in text.doItems)
              line(i, Icons.check_circle, theme.colorScheme.primary),
          ],
          if (text.dontItems.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              l10n.tipsDont,
              style: theme.textTheme.titleSmall?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
            for (final i in text.dontItems)
              line(i, Icons.cancel, theme.colorScheme.error),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- drills and events

class OrgActivitiesSection extends ConsumerWidget {
  const OrgActivitiesSection({super.key, required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final canEdit = _canEdit(ref, orgId);
    return ref
        .watch(orgActivitiesProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                l10n.orgActivityHint,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 8),
              if (canEdit)
                FilledButton.icon(
                  key: const Key('org-activity-add'),
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    showDragHandle: true,
                    builder: (_) => _ActivityForm(orgId: orgId),
                  ),
                  icon: const Icon(Icons.add),
                  label: Text(l10n.orgActivityAdd),
                ),
              if (items.isEmpty) _Note(l10n.orgActivitiesEmpty),
              for (final a in items) ...[
                const SizedBox(height: 8),
                _ActivityCard(orgId: orgId, item: a, canEdit: canEdit),
              ],
            ],
          ),
        );
  }
}

String activityKindText(AppLocalizations l10n, String kind) =>
    kind == 'event' ? l10n.orgActivityEvent : l10n.orgActivityDrill;

class _ActivityCard extends ConsumerWidget {
  const _ActivityCard({
    required this.orgId,
    required this.item,
    required this.canEdit,
  });

  final String orgId;
  final OrgActivity item;
  final bool canEdit;

  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        content: Text(l10n.orgActivityDeleteConfirm(item.title)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.orgCancel),
          ),
          TextButton(
            key: const Key('org-activity-delete-confirm'),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.orgActivityDelete),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(apiProvider).deleteOrgActivity(orgId, item.id);
      ref.invalidate(orgActivitiesProvider(orgId));
      _snack(messenger, l10n.orgActivityDeleted);
    } on ApiException catch (e) {
      _snack(messenger, apiErrorMessage(l10n, e.code));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final date = DateFormat.yMMMd(ref.watch(localeCodeProvider));
    final event = item.kind == 'event';
    final when = [
      date.format(item.startsOn),
      if (item.endsOn case final DateTime end) date.format(end),
    ].join(' – ');
    return AppCard(
      key: Key('org-activity-${item.id}'),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          IconTile(
            event ? Icons.festival : Icons.directions_run,
            tone: event ? Tone.pink : Tone.orange,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.title, style: theme.textTheme.titleMedium),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Pill(
                      activityKindText(l10n, item.kind),
                      tone: event ? Tone.pink : Tone.orange,
                    ),
                    Text(when, style: theme.textTheme.bodySmall),
                  ],
                ),
                if (item.participants case final int n)
                  Text(l10n.orgActivityParticipantsCount(n)),
                if (item.notes case final String notes) Text(notes),
                if (item.createdBy case final String who)
                  Text(who, style: theme.textTheme.bodySmall),
              ],
            ),
          ),
          if (canEdit)
            IconButton(
              key: Key('org-activity-delete-${item.id}'),
              tooltip: l10n.orgActivityDelete,
              icon: const Icon(Icons.delete_outline),
              onPressed: () => _delete(context, ref),
            ),
        ],
      ),
    );
  }
}

/// A date field opening the date picker.
class _DateField extends StatelessWidget {
  const _DateField({
    super.key,
    required this.label,
    required this.value,
    required this.first,
    required this.last,
    required this.onChanged,
    this.clearable = false,
  });

  final String label;
  final DateTime? value;
  final DateTime first;
  final DateTime last;
  final ValueChanged<DateTime?> onChanged;
  final bool clearable;

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.localeOf(context).languageCode;
    return InkWell(
      onTap: () async {
        final initial = value ?? (last.isBefore(DateTime.now()) ? last : first);
        final picked = await showDatePicker(
          context: context,
          initialDate: initial.isBefore(first)
              ? first
              : initial.isAfter(last)
              ? last
              : initial,
          firstDate: first,
          lastDate: last,
        );
        if (picked != null) onChanged(picked);
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: clearable && value != null
              ? IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () => onChanged(null),
                )
              : const Icon(Icons.event),
        ),
        child: Text(
          value == null ? '' : DateFormat.yMMMd(locale).format(value!),
        ),
      ),
    );
  }
}

class _ActivityForm extends ConsumerStatefulWidget {
  const _ActivityForm({required this.orgId});

  final String orgId;

  @override
  ConsumerState<_ActivityForm> createState() => _ActivityFormState();
}

class _ActivityFormState extends ConsumerState<_ActivityForm> {
  final _title = TextEditingController();
  final _participants = TextEditingController();
  final _notes = TextEditingController();
  String _kind = 'drill';
  late DateTime _startsOn = _day(ref.read(clockProvider)().toLocal());
  DateTime? _endsOn;
  bool _busy = false;
  bool _submitted = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _participants.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _submitted = true);
    final participants = _participants.text.trim();
    final count = participants.isEmpty ? null : int.tryParse(participants);
    if (_title.text.trim().isEmpty ||
        (participants.isNotEmpty && (count == null || count < 0))) {
      if (count == null && participants.isNotEmpty) {
        setState(() => _error = l10n.orgInvalidNumber);
      }
      return;
    }
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(apiProvider).addOrgActivity(widget.orgId, {
        'kind': _kind,
        'title': _title.text.trim(),
        'starts_on': isoDay(_startsOn),
        'ends_on': _kind == 'event' && _endsOn != null
            ? isoDay(_endsOn!)
            : null,
        'participants': count,
        'notes': _notes.text.trim().isEmpty ? null : _notes.text.trim(),
      });
      ref.invalidate(orgActivitiesProvider(widget.orgId));
      navigator.pop();
      _snack(messenger, l10n.orgSaved);
    } on ApiException catch (e) {
      setState(() {
        _busy = false;
        _error = apiErrorMessage(l10n, e.code);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final today = _day(ref.read(clockProvider)().toLocal());
    final first = DateTime(today.year - 1, today.month, today.day);
    final horizon = DateTime(today.year + 1, today.month, today.day);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionTitle(l10n.orgActivityAdd),
            SegmentedButton<String>(
              key: const Key('org-activity-kind'),
              segments: [
                ButtonSegment(
                  value: 'drill',
                  icon: const Icon(Icons.directions_run),
                  label: Text(l10n.orgActivityDrill),
                ),
                ButtonSegment(
                  value: 'event',
                  icon: const Icon(Icons.festival),
                  label: Text(l10n.orgActivityEvent),
                ),
              ],
              selected: {_kind},
              onSelectionChanged: (s) => setState(() {
                _kind = s.first;
                if (_kind == 'drill') {
                  _endsOn = null;
                  if (_startsOn.isAfter(today)) _startsOn = today;
                }
              }),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('org-activity-title'),
              controller: _title,
              maxLength: 120,
              decoration: InputDecoration(
                labelText: l10n.orgActivityTitle,
                errorText: _submitted && _title.text.trim().isEmpty
                    ? l10n.orgActivityTitleRequired
                    : null,
              ),
            ),
            _DateField(
              key: const Key('org-activity-starts'),
              label: l10n.orgActivityStarts,
              value: _startsOn,
              first: first,
              last: _kind == 'drill' ? today : horizon,
              onChanged: (d) => setState(() {
                _startsOn = d ?? _startsOn;
                if (_endsOn != null && _endsOn!.isBefore(_startsOn)) {
                  _endsOn = null;
                }
              }),
            ),
            if (_kind == 'event') ...[
              const SizedBox(height: 8),
              _DateField(
                key: const Key('org-activity-ends'),
                label: l10n.orgActivityEnds,
                value: _endsOn,
                first: _startsOn,
                last: horizon,
                clearable: true,
                onChanged: (d) => setState(() => _endsOn = d),
              ),
            ],
            const SizedBox(height: 8),
            TextField(
              key: const Key('org-activity-participants'),
              controller: _participants,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: l10n.orgActivityParticipants,
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('org-activity-notes'),
              controller: _notes,
              maxLength: 1000,
              maxLines: 3,
              minLines: 1,
              decoration: InputDecoration(labelText: l10n.orgActivityNotes),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 12),
            FilledButton(
              key: const Key('org-activity-save'),
              onPressed: _busy ? null : _save,
              child: Text(l10n.orgSave),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- maintenance

/// Records a maintenance of [item]: the date (today unless changed), a note and an optional
/// photo. The photo goes first; if it cannot be sent, nothing is recorded.
class MaintenanceSheet extends ConsumerStatefulWidget {
  const MaintenanceSheet({super.key, required this.orgId, required this.item});

  final String orgId;
  final OrgEquipment item;

  @override
  ConsumerState<MaintenanceSheet> createState() => _MaintenanceSheetState();
}

class _MaintenanceSheetState extends ConsumerState<MaintenanceSheet> {
  final _note = TextEditingController();
  late DateTime _doneOn = _day(ref.read(clockProvider)().toLocal());
  File? _photo;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _take() async {
    final l10n = AppLocalizations.of(context);
    final file = await ref.read(maintenancePhotoPickerProvider)();
    if (file == null || !mounted) return;
    final problem = await checkMaintenancePhoto(file);
    if (!mounted) return;
    setState(() {
      _photo = problem == null ? file : _photo;
      _error = switch (problem) {
        PhotoProblem.unsupported => l10n.orgMaintenancePhotoUnsupported,
        PhotoProblem.tooLarge => l10n.orgMaintenancePhotoTooLarge,
        null => null,
      };
    });
  }

  Future<void> _save() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final api = ref.read(apiProvider);
    final orgId = widget.orgId;
    final item = widget.item;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      String? documentId;
      if (_photo case final File photo) {
        try {
          documentId = await uploadMaintenancePhoto(
            api: api,
            tus: ref.read(orgTusProvider),
            orgId: orgId,
            file: photo,
            title: equipmentPhotoTitle(item, _doneOn),
          );
        } on TusException {
          throw const _PhotoFailed();
        } on ApiException catch (e) {
          if (e.code == ApiErrorCode.network ||
              e.code == ApiErrorCode.server ||
              e.code == ApiErrorCode.unknown) {
            throw const _PhotoFailed();
          }
          rethrow;
        }
      }
      await api.addMaintenance(
        orgId,
        item.id,
        doneOn: _doneOn,
        note: _note.text.trim().isEmpty ? null : _note.text.trim(),
        documentId: documentId,
      );
      ref.invalidate(orgEquipmentProvider(orgId));
      ref.invalidate(orgSummaryProvider(orgId));
      ref.invalidate(equipmentMaintenanceProvider((orgId, item.id)));
      navigator.pop();
      _snack(messenger, l10n.orgMaintenanceLogged);
    } on _PhotoFailed {
      setState(() {
        _busy = false;
        _error = l10n.orgMaintenancePhotoFailed;
      });
    } on ApiException catch (e) {
      setState(() {
        _busy = false;
        _error = apiErrorMessage(l10n, e.code);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final today = _day(ref.read(clockProvider)().toLocal());
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionTitle(l10n.orgMaintenanceSheetTitle),
            _DateField(
              key: const Key('maintenance-date'),
              label: l10n.orgMaintenanceDate,
              value: _doneOn,
              first: DateTime(today.year - 5, today.month, today.day),
              last: today,
              onChanged: (d) => setState(() => _doneOn = d ?? _doneOn),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('maintenance-note'),
              controller: _note,
              maxLength: 500,
              maxLines: 3,
              minLines: 1,
              decoration: InputDecoration(labelText: l10n.orgMaintenanceNote),
            ),
            Row(
              children: [
                OutlinedButton.icon(
                  key: const Key('maintenance-photo'),
                  onPressed: _busy ? null : _take,
                  icon: const Icon(Icons.photo_camera),
                  label: Text(
                    _photo == null
                        ? l10n.orgMaintenancePhoto
                        : l10n.orgMaintenancePhotoRetake,
                  ),
                ),
                const SizedBox(width: 8),
                if (_photo != null)
                  Flexible(
                    child: Pill(
                      l10n.orgMaintenancePhotoReady,
                      tone: Tone.green,
                      icon: Icons.image,
                    ),
                  ),
              ],
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  _error!,
                  key: const Key('maintenance-error'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 12),
            FilledButton(
              key: const Key('maintenance-save'),
              onPressed: _busy ? null : _save,
              child: _busy
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(l10n.orgMaintenanceSave),
            ),
          ],
        ),
      ),
    );
  }
}

class _PhotoFailed implements Exception {
  const _PhotoFailed();
}

/// Title of the photo document, as the portal lists it.
String equipmentPhotoTitle(OrgEquipment item, DateTime day) =>
    '${item.kind} ${isoDay(day)}';

/// Maintenance log of one equipment, newest first, with the state of each photo.
class MaintenanceHistory extends ConsumerWidget {
  const MaintenanceHistory({
    super.key,
    required this.orgId,
    required this.itemId,
  });

  final String orgId;
  final String itemId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final date = DateFormat.yMMMd(ref.watch(localeCodeProvider));
    return ref
        .watch(equipmentMaintenanceProvider((orgId, itemId)))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            key: Key('maintenance-history-$itemId'),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgMaintenanceHistoryEmpty),
              for (final m in items)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.build_circle, size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(date.format(m.doneOn)),
                            if (m.note case final String note) Text(note),
                            if (m.recordedBy case final String who)
                              Text(who, style: theme.textTheme.bodySmall),
                          ],
                        ),
                      ),
                      if (m.photoVersion != null)
                        Pill(
                          l10n.orgMaintenancePhotoStored,
                          tone: Tone.green,
                          icon: Icons.image,
                        )
                      else if (m.documentId != null)
                        Pill(
                          l10n.orgMaintenancePhotoChecking,
                          tone: Tone.amber,
                          icon: Icons.hourglass_top,
                        ),
                    ],
                  ),
                ),
            ],
          ),
        );
  }
}
