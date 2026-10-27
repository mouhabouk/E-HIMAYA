import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/report/category_labels.dart';
import '../../l10n/app_localizations.dart';
import '../staff_capture.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';
import 'field_widgets.dart';
import 'transport_screen.dart';

/// Situation report and live counts on one screen (phase P4b, design §5.5), all by tapping:
/// the type, the severity, backup, six counters, and photo, voice or a short text.
class SituationScreen extends ConsumerStatefulWidget {
  const SituationScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<SituationScreen> createState() => _SituationScreenState();
}

class _SituationScreenState extends ConsumerState<SituationScreen> {
  ReportCategory? _category;
  bool _different = false;
  int? _severity;
  bool? _backup;
  final _kinds = <String>{};

  @override
  void initState() {
    super.initState();
    final m = ref.read(staffControllerProvider).mission(widget.missionId);
    final last = m?.fieldReport;
    final room = m?.category == ReportCategory.sos ? null : m?.category;
    _category = last?.category ?? room;
    _different = last?.category != null && last!.category != room;
    _severity = last?.severity;
    if (last != null) {
      _backup = last.backupKinds.isNotEmpty || last.backupNeeded;
      _kinds.addAll(last.backupKinds);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(widget.missionId);
    if (m == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffSituation),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final c = ref.read(staffControllerProvider.notifier);
    final editable = m.status == MissionStatus.onScene;
    final room = m.category == ReportCategory.sos ? null : m.category;
    final ready =
        editable &&
        _category != null &&
        _severity != null &&
        _backup != null &&
        !s.busy;
    final place = placeOf(m, ref.watch(localeCodeProvider));
    final n = Neutrals.of(context);
    final photos = m.attachments.where((a) => a.kind == 'photo').length;
    final voices = m.attachments.where((a) => a.kind == 'voice').length;
    final texts = m.attachments.where((a) => a.kind == 'text').length;
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffSituation,
        subtitle: [
          categoryLabel(l10n, m.category ?? ReportCategory.other),
          place,
        ].where((x) => x.isNotEmpty).join(' · '),
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (m.fieldReport != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      l10n.staffSituationLast(
                        hhmm(m.fieldReport!.createdAt ?? m.createdAt),
                        severityLabel(l10n, m.fieldReport!.severity ?? 1),
                      ),
                      key: const Key('situation-last'),
                      style: TextStyle(color: n.muted),
                    ),
                  ),
                SectionTitle(l10n.staffType),
                ChoiceRow(
                  children: [
                    if (room != null)
                      ToneChoice(
                        key: const Key('type-confirmed'),
                        label: l10n.staffConfirmed(categoryLabel(l10n, room)),
                        tone: Tone.navy,
                        selected: !_different && _category == room,
                        onTap: () => setState(() {
                          _different = false;
                          _category = room;
                        }),
                      ),
                    ToneChoice(
                      key: const Key('type-different'),
                      label: l10n.staffDifferent,
                      tone: Tone.navy,
                      selected: _different || room == null,
                      onTap: () => setState(() => _different = true),
                    ),
                  ],
                ),
                if (_different || room == null) ...[
                  const SizedBox(height: 8),
                  TileGrid(
                    minTileWidth: 104,
                    children: [
                      for (final k in ReportCategory.grid)
                        ChoiceTile(
                          key: Key('cat-${k.wire}'),
                          icon: categoryIcon(k),
                          tone: Tone.navy,
                          title: categoryLabel(l10n, k),
                          selected: _category == k,
                          onTap: () => setState(() => _category = k),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: 16),
                SectionTitle(l10n.staffSeverity),
                ChoiceRow(
                  children: [
                    for (final v in [1, 2, 3, 4])
                      Tooltip(
                        message: severityLabel(l10n, v),
                        child: ToneChoice(
                          key: Key('severity-$v'),
                          label: '$v',
                          tone: severityTone(v),
                          selected: _severity == v,
                          height: 60,
                          onTap: () => setState(() => _severity = v),
                        ),
                      ),
                  ],
                ),
                if (_severity != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      severityLabel(l10n, _severity!),
                      textAlign: TextAlign.center,
                      style: TextStyle(color: n.muted),
                    ),
                  ),
                const SizedBox(height: 16),
                SectionTitle(l10n.staffNeedBackup),
                ChoiceRow(
                  children: [
                    ToneChoice(
                      key: const Key('backup-no'),
                      label: l10n.staffNo,
                      tone: Tone.green,
                      selected: _backup == false,
                      onTap: () => setState(() {
                        _backup = false;
                        _kinds.clear();
                      }),
                    ),
                    ToneChoice(
                      key: const Key('backup-yes'),
                      label: _kinds.isEmpty
                          ? l10n.staffYes
                          : '${l10n.staffYes}: ${_kinds.map((k) => backupLabel(l10n, k)).join('، ')}',
                      tone: Tone.red,
                      selected: _backup == true,
                      onTap: () => setState(() => _backup = true),
                    ),
                  ],
                ),
                if (_backup == true) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final k in backupKinds)
                        FilterChip(
                          key: Key('backup-$k'),
                          label: Text(backupLabel(l10n, k)),
                          selected: _kinds.contains(k),
                          onSelected: (v) => setState(
                            () => v ? _kinds.add(k) : _kinds.remove(k),
                          ),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: 20),
                SectionTitle(l10n.staffLiveCounts),
                _Pairs(
                  children: [
                    for (final k in CasualtyCounter.values)
                      CounterCell(
                        label: counterLabel(l10n, k),
                        value: m.casualties.of(k),
                        keyName: k.wire,
                        tone: counterTone(k),
                        onMinus: editable && !s.busy
                            ? () => unawaited(c.count(m.id, k, -1))
                            : null,
                        onPlus: editable && !s.busy
                            ? () => unawaited(c.count(m.id, k, 1))
                            : null,
                      ),
                    CounterCell(
                      label: l10n.staffTransported,
                      value: m.transports.length,
                      keyName: 'transported',
                      tone: Tone.teal,
                      onPlus: editable
                          ? () =>
                                push(context, TransportScreen(missionId: m.id))
                          : null,
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                SectionTitle(l10n.staffAttachments),
                Row(
                  children: [
                    _Attach(
                      keyName: 'attach-photo',
                      icon: Icons.photo_camera,
                      label: l10n.staffPhoto,
                      count: photos,
                      onTap: editable && !s.busy ? _photo : null,
                    ),
                    const SizedBox(width: 8),
                    _Attach(
                      keyName: 'attach-voice',
                      icon: Icons.mic,
                      label: l10n.staffVoice,
                      count: voices,
                      onTap: editable && !s.busy ? _voice : null,
                    ),
                    const SizedBox(width: 8),
                    _Attach(
                      keyName: 'attach-text',
                      icon: Icons.notes,
                      label: l10n.staffText,
                      count: texts,
                      onTap: editable && !s.busy ? _text : null,
                    ),
                  ],
                ),
                const StaffErrorText(),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: editable
          ? BottomActionBar(
              actions: [
                BarAction(
                  key: const Key('send-situation'),
                  label: l10n.staffSendReport,
                  icon: Icons.send,
                  tone: Tone.navy,
                  onPressed: !ready ? null : _send,
                ),
                BarAction(
                  key: const Key('open-transport'),
                  label: l10n.staffAddTransport,
                  icon: Icons.local_hospital,
                  tone: Tone.green,
                  onPressed: () =>
                      push(context, TransportScreen(missionId: m.id)),
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
        .situation(
          widget.missionId,
          category: _category!,
          severity: _severity!,
          backupKinds: [
            for (final k in backupKinds)
              if (_kinds.contains(k)) k,
          ],
        );
    if (ok) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            sentLabel(l10n, ref.read(staffControllerProvider).pending),
          ),
        ),
      );
    }
  }

  Future<void> _sent(Future<bool> Function() call) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    if (await call()) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            sentLabel(l10n, ref.read(staffControllerProvider).pending),
          ),
        ),
      );
    }
  }

  void _photo() => unawaited(() async {
    final media = await ref.read(staffCaptureProvider).photo();
    if (media == null || !mounted) return;
    await _sent(
      () => ref
          .read(staffControllerProvider.notifier)
          .upload(widget.missionId, 'photo', media),
    );
  }());

  void _voice() => unawaited(() async {
    final media = await ref.read(staffCaptureProvider).voice(context);
    if (media == null || !mounted) return;
    await _sent(
      () => ref
          .read(staffControllerProvider.notifier)
          .upload(widget.missionId, 'voice', media),
    );
  }());

  void _text() => unawaited(() async {
    final body = await showDialog<String>(
      context: context,
      builder: (_) => const _TextNoteDialog(),
    );
    if (body == null || body.trim().isEmpty || !mounted) return;
    await _sent(
      () => ref
          .read(staffControllerProvider.notifier)
          .note(widget.missionId, body),
    );
  }());
}

/// Two cells per row, each row as tall as its taller cell (large text grows them).
class _Pairs extends StatelessWidget {
  const _Pairs({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      for (var i = 0; i < children.length; i += 2)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: children[i]),
                const SizedBox(width: 8),
                Expanded(
                  child: i + 1 < children.length
                      ? children[i + 1]
                      : const SizedBox.shrink(),
                ),
              ],
            ),
          ),
        ),
    ],
  );
}

class _Attach extends StatelessWidget {
  const _Attach({
    required this.keyName,
    required this.icon,
    required this.label,
    required this.count,
    required this.onTap,
  });

  final String keyName;
  final IconData icon;
  final String label;
  final int count;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Expanded(
    child: AppCard(
      key: Key(keyName),
      onTap: onTap,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
      child: Column(
        children: [
          IconTile(icon, tone: Tone.navy, size: 44),
          const SizedBox(height: 6),
          Text(
            count == 0 ? label : '$label ($count)',
            textAlign: TextAlign.center,
            maxLines: 2,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ],
      ),
    ),
  );
}

/// The only free text of the report: 500 characters, optional.
class _TextNoteDialog extends StatefulWidget {
  const _TextNoteDialog();

  @override
  State<_TextNoteDialog> createState() => _TextNoteDialogState();
}

class _TextNoteDialogState extends State<_TextNoteDialog> {
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.staffText),
      content: TextField(
        key: const Key('note-text'),
        controller: _text,
        autofocus: true,
        maxLength: 500,
        maxLines: 4,
        decoration: InputDecoration(helperText: l10n.staffNoteHint),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.actionCancel),
        ),
        FilledButton(
          key: const Key('send-note'),
          onPressed: () => Navigator.pop(context, _text.text),
          child: Text(l10n.staffSend),
        ),
      ],
    );
  }
}
