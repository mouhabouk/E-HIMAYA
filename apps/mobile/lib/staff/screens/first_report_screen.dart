import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/report/category_labels.dart';
import '../../l10n/app_localizations.dart';
import '../staff_app.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';

/// F-STF-04: the first report from the scene, in under thirty seconds: the nature (prefilled
/// from the room's), the severity, backup needed, danger to the crew. Detailed reports by type
/// come in phase P4b.
class FirstReportScreen extends ConsumerStatefulWidget {
  const FirstReportScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<FirstReportScreen> createState() => _FirstReportScreenState();
}

class _FirstReportScreenState extends ConsumerState<FirstReportScreen> {
  ReportCategory? _category;
  int? _severity;
  bool _backup = false;
  bool _danger = false;
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    final m = ref.read(staffControllerProvider).mission(widget.missionId);
    _category = m?.category == ReportCategory.sos ? null : m?.category;
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final ready = _category != null && _severity != null && !s.busy;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.staffFirstReport),
        actions: staffBarActions(),
      ),
      body: Column(
        children: [
          const OfflineStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                SectionTitle(l10n.staffNature),
                TileGrid(
                  minTileWidth: 150,
                  children: [
                    for (final c in ReportCategory.grid)
                      ChoiceTile(
                        key: Key('cat-${c.wire}'),
                        icon: categoryIcon(c),
                        tone: Tone.navy,
                        title: categoryLabel(l10n, c),
                        selected: _category == c,
                        onTap: () => setState(() => _category = c),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                SectionTitle(l10n.staffSeverity),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final v in [1, 2, 3, 4])
                      ChoiceChip(
                        key: Key('severity-$v'),
                        label: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          child: Text(severityLabel(l10n, v)),
                        ),
                        selected: _severity == v,
                        onSelected: (_) => setState(() => _severity = v),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  key: const Key('backup-needed'),
                  value: _backup,
                  onChanged: (v) => setState(() => _backup = v),
                  title: Text(l10n.staffBackupNeeded),
                  secondary: const Icon(Icons.add_alert),
                ),
                if (_backup)
                  TextField(
                    key: const Key('backup-note'),
                    controller: _note,
                    maxLength: 300,
                    decoration: InputDecoration(
                      labelText: l10n.staffBackupNote,
                      helperText: l10n.staffOptional,
                    ),
                  ),
                SwitchListTile(
                  key: const Key('crew-danger'),
                  value: _danger,
                  onChanged: (v) => setState(() => _danger = v),
                  title: Text(l10n.staffCrewDanger),
                  secondary: Icon(
                    Icons.warning,
                    color: Tone.red.colors(context).fill,
                  ),
                ),
                if (s.error != null)
                  Text(
                    crewErrorLabel(l10n, s.error!),
                    key: const Key('staff-error'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: BottomActionBar(
        actions: [
          BarAction(
            key: const Key('send-first-report'),
            label: l10n.staffSend,
            icon: Icons.send,
            tone: _danger || _backup ? Tone.red : Tone.navy,
            onPressed: !ready
                ? null
                : () async {
                    final ok = await ref
                        .read(staffControllerProvider.notifier)
                        .firstReport(
                          widget.missionId,
                          category: _category!,
                          severity: _severity!,
                          backupNeeded: _backup,
                          backupNote: _backup ? _note.text : null,
                          crewDanger: _danger,
                        );
                    if (ok && context.mounted) Navigator.of(context).pop();
                  },
          ),
        ],
      ),
    );
  }
}
