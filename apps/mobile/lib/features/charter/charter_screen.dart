import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/config/app_config.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'charter_controller.dart';

/// FR-A-001: privacy & personal-data charter, shown before anything else. The text ships in the
/// ARB files for version [AppConfig.charterVersion].
class CharterScreen extends ConsumerStatefulWidget {
  const CharterScreen({super.key, this.readOnly = false});

  /// Re-reading from the settings: no checkbox.
  final bool readOnly;

  @override
  ConsumerState<CharterScreen> createState() => _CharterScreenState();
}

class _CharterScreenState extends ConsumerState<CharterScreen> {
  bool _checked = false;
  bool _saving = false;

  Future<void> _accept() async {
    setState(() => _saving = true);
    await ref.read(charterAcceptedProvider.notifier).accept();
    if (mounted) setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final acceptedAt = ref.watch(appPrefsProvider).charterAcceptedAt;
    final sections = [
      (l10n.charterDataTitle, l10n.charterDataBody),
      (l10n.charterLawTitle, l10n.charterLawBody),
      (l10n.charterAnonymousTitle, l10n.charterAnonymousBody),
      (l10n.charterRightsTitle, l10n.charterRightsBody),
      (l10n.charterRetentionTitle, l10n.charterRetentionBody),
      (l10n.charterLiabilityTitle, l10n.charterLiabilityBody),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.charterTitle),
        automaticallyImplyLeading: widget.readOnly,
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    l10n.charterVersionLabel(AppConfig.charterVersion),
                    style: theme.textTheme.labelLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(l10n.charterIntro, style: theme.textTheme.bodyLarge),
                  for (final (title, body) in sections) ...[
                    const SizedBox(height: 20),
                    Semantics(
                      header: true,
                      child: Text(title, style: theme.textTheme.titleMedium),
                    ),
                    const SizedBox(height: 6),
                    Text(body, style: theme.textTheme.bodyMedium),
                  ],
                  if (widget.readOnly && acceptedAt != null) ...[
                    const SizedBox(height: 24),
                    Text(
                      l10n.charterAcceptedOn(
                        DateFormat.yMMMd(
                          Localizations.localeOf(context).languageCode,
                        ).format(acceptedAt.toLocal()),
                      ),
                      style: theme.textTheme.labelLarge,
                    ),
                  ],
                ],
              ),
            ),
            if (!widget.readOnly)
              Material(
                elevation: 3,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 16, 16),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      CheckboxListTile(
                        key: const Key('charter-checkbox'),
                        value: _checked,
                        onChanged: (v) => setState(() => _checked = v ?? false),
                        controlAffinity: ListTileControlAffinity.leading,
                        title: Text(l10n.charterCheckbox),
                      ),
                      const SizedBox(height: 8),
                      Padding(
                        padding: const EdgeInsetsDirectional.only(start: 8),
                        child: FilledButton(
                          key: const Key('charter-continue'),
                          onPressed: _checked && !_saving ? _accept : null,
                          child: Text(l10n.actionContinue),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
