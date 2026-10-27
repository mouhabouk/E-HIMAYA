import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/report/category_labels.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart' show sentLabel;
import '../staff_models.dart';
import 'field_widgets.dart';

/// The detailed report of the incident's type (F-STF-05, design §5.7): the questions of the
/// approved template, each answered with a tap; only the last note is typed, and it is optional.
class DetailedReportScreen extends ConsumerStatefulWidget {
  const DetailedReportScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<DetailedReportScreen> createState() =>
      _DetailedReportScreenState();
}

class _DetailedReportScreenState extends ConsumerState<DetailedReportScreen> {
  final _answers = <String, Object>{};
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    final m = ref.read(staffControllerProvider).mission(widget.missionId);
    final last = m?.detailedReport;
    // A correction starts from the answers sent, when they answer the same version.
    if (last != null && last.templateVersion == m?.template?.version) {
      for (final e in last.answers.entries) {
        final v = e.value;
        if (v is List) {
          _answers[e.key] = [for (final x in v) x as String];
        } else if (v != null) {
          _answers[e.key] = v as Object;
        }
      }
      _note.text = last.note ?? '';
    }
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final code = ref.watch(localeCodeProvider);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(widget.missionId);
    final t = m?.template;
    if (m == null || t == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffDetailedReport),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final editable = m.status == MissionStatus.onScene;
    final missing = t.fields.any(
      (f) => f.required && !_answers.containsKey(f.key),
    );
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffDetailedReport,
        subtitle:
            '${categoryLabel(l10n, m.category ?? ReportCategory.other)} · ${l10n.staffTemplateVersion(t.version)}',
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (t.simulated)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: Pill(
                        l10n.staffSimTemplate,
                        tone: Tone.amber,
                        icon: Icons.science,
                      ),
                    ),
                  ),
                for (final f in t.fields) ...[
                  _FieldTitle(field: f, code: code),
                  _answer(context, f, code, editable),
                  const SizedBox(height: 16),
                ],
                SectionTitle(l10n.staffNote),
                TextField(
                  key: const Key('detailed-note'),
                  controller: _note,
                  enabled: editable,
                  maxLength: 1000,
                  maxLines: 3,
                  decoration: InputDecoration(helperText: l10n.staffOptional),
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
                  key: const Key('send-detailed'),
                  label: l10n.staffSendReport,
                  icon: Icons.send,
                  tone: Tone.navy,
                  onPressed: missing || s.busy
                      ? null
                      : () => unawaited(_send(t)),
                ),
              ],
            )
          : null,
    );
  }

  Widget _answer(
    BuildContext context,
    TemplateField f,
    String code,
    bool editable,
  ) {
    final l10n = AppLocalizations.of(context);
    final value = _answers[f.key];
    void set(Object? v) => setState(
      () => v == null ? _answers.remove(f.key) : _answers[f.key] = v,
    );
    switch (f.type) {
      case FieldType.single:
        return Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final o in f.options)
              ChoiceChip(
                key: Key('field-${f.key}-${o.key}'),
                label: Text(o.label.of(code)),
                selected: value == o.key,
                onSelected: editable ? (on) => set(on ? o.key : null) : null,
              ),
          ],
        );
      case FieldType.multi:
        final chosen = value is List<String> ? value : const <String>[];
        return Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final o in f.options)
              FilterChip(
                key: Key('field-${f.key}-${o.key}'),
                label: Text(o.label.of(code)),
                selected: chosen.contains(o.key),
                onSelected: editable
                    ? (on) {
                        final next = [
                          for (final x in f.options)
                            if (x.key == o.key ? on : chosen.contains(x.key))
                              x.key,
                        ];
                        set(next.isEmpty ? null : next);
                      }
                    : null,
              ),
          ],
        );
      case FieldType.yesno:
        return ChoiceRow(
          children: [
            ToneChoice(
              key: Key('field-${f.key}-no'),
              label: l10n.staffNo,
              tone: Tone.slate,
              selected: value == false,
              onTap: editable ? () => set(false) : null,
            ),
            ToneChoice(
              key: Key('field-${f.key}-yes'),
              label: l10n.staffYes,
              tone: Tone.navy,
              selected: value == true,
              onTap: editable ? () => set(true) : null,
            ),
          ],
        );
      case FieldType.count:
        final v = value is int ? value : 0;
        final max = f.max ?? 1000000;
        return Row(
          children: [
            IconButton.filledTonal(
              key: Key('field-${f.key}-minus'),
              tooltip: l10n.staffLess,
              onPressed: editable && v > 0 ? () => set(v - 1) : null,
              icon: const Icon(Icons.remove),
            ),
            SizedBox(
              width: 72,
              child: Text(
                '$v',
                key: Key('field-${f.key}-value'),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ),
            IconButton.filled(
              key: Key('field-${f.key}-plus'),
              tooltip: l10n.staffMore,
              onPressed: editable && v < max ? () => set(v + 1) : null,
              icon: const Icon(Icons.add),
            ),
            if (f.unit != null) ...[
              const SizedBox(width: 8),
              Text(f.unit!.of(code)),
            ],
          ],
        );
    }
  }

  Future<void> _send(ReportTemplate t) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final nav = Navigator.of(context);
    final ok = await ref
        .read(staffControllerProvider.notifier)
        .detailedReport(widget.missionId, t.id, _answers, _note.text);
    if (!ok) return;
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          sentLabel(l10n, ref.read(staffControllerProvider).pending),
        ),
      ),
    );
    if (mounted) nav.pop();
  }
}

class _FieldTitle extends StatelessWidget {
  const _FieldTitle({required this.field, required this.code});

  final TemplateField field;
  final String code;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Flexible(
            child: Text(
              field.label.of(code),
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          if (field.required) ...[
            const SizedBox(width: 6),
            Text(
              '· ${l10n.staffRequired}',
              style: TextStyle(color: Tone.red.colors(context).onTint),
            ),
          ],
        ],
      ),
    );
  }
}
