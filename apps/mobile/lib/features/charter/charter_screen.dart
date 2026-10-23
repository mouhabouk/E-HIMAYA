import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/config/app_config.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../welcome/welcome_scaffold.dart';
import 'charter_controller.dart';

/// The ten numbered sections of the terms of use (addition 7), version [AppConfig.charterVersion].
List<(String, String)> termsSections(AppLocalizations l10n) => [
  (l10n.terms1Title, l10n.terms1Body),
  (l10n.terms2Title, l10n.terms2Body),
  (l10n.terms3Title, l10n.terms3Body),
  (l10n.terms4Title, l10n.terms4Body),
  (l10n.terms5Title, l10n.terms5Body),
  (l10n.terms6Title, l10n.terms6Body),
  (l10n.terms7Title, l10n.terms7Body),
  (l10n.terms8Title, l10n.terms8Body),
  (l10n.terms9Title, l10n.terms9Body),
  (l10n.terms10Title, l10n.terms10Body),
];

/// FR-A-001 and addition 7: terms of use, shown before any account. "I accept" is enabled once
/// the text was scrolled to the end and the box is ticked. The texts ship in the ARB files and
/// change only with a release; a new version asks every user to accept once.
class CharterScreen extends ConsumerStatefulWidget {
  const CharterScreen({super.key, this.readOnly = false});

  /// Re-reading from the settings: no checkbox, version and acceptance date shown.
  final bool readOnly;

  @override
  ConsumerState<CharterScreen> createState() => _CharterScreenState();
}

class _CharterScreenState extends ConsumerState<CharterScreen> {
  final _scroll = ScrollController();
  bool _checked = false;
  bool _saving = false;
  bool _readToEnd = false;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_checkEnd);
    // Large text or a tall screen: everything may already be visible.
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkEnd());
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _checkEnd() {
    if (_readToEnd || !_scroll.hasClients) return;
    final p = _scroll.position;
    if (p.pixels >= p.maxScrollExtent - 24) setState(() => _readToEnd = true);
  }

  Future<void> _accept() async {
    setState(() => _saving = true);
    await ref.read(charterAcceptedProvider.notifier).accept();
    if (mounted) setState(() => _saving = false);
  }

  Future<void> _decline() async {
    final l10n = AppLocalizations.of(context);
    final dial = ref.read(dialerProvider);
    final civil = emergencyNumbers.first;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        key: const Key('terms-declined'),
        title: Text(l10n.termsDeclinedTitle),
        content: Text(l10n.termsDeclinedBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.termsReadAgain),
          ),
          FilledButton.icon(
            onPressed: () => dial(civil.telUri),
            icon: const Icon(Icons.phone),
            label: Text(l10n.call198),
          ),
        ],
      ),
    );
  }

  Widget _text(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final acceptedAt = ref.watch(appPrefsProvider).charterAcceptedAt;
    return ListView(
      key: const Key('terms-text'),
      controller: _scroll,
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          l10n.charterVersionLabel(AppConfig.charterVersion),
          style: theme.textTheme.labelLarge,
        ),
        if (widget.readOnly && acceptedAt != null)
          Text(
            l10n.charterAcceptedOn(
              DateFormat.yMMMd(Localizations.localeOf(context).languageCode)
                  .format(acceptedAt.toLocal()),
            ),
            key: const Key('terms-accepted-on'),
            style: theme.textTheme.labelLarge,
          ),
        for (final (title, body) in termsSections(l10n)) ...[
          const SizedBox(height: 20),
          Semantics(
            header: true,
            child: Text(title, style: theme.textTheme.titleMedium),
          ),
          const SizedBox(height: 6),
          Text(body, style: theme.textTheme.bodyMedium),
        ],
        const SizedBox(height: 16),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    if (widget.readOnly) {
      return Scaffold(
        appBar: AppBar(
          title: Text(l10n.charterTitle),
          actions: const [StandardAppBarActions()],
        ),
        body: SafeArea(child: _text(context)),
      );
    }
    return WelcomeScaffold(
      title: l10n.charterTitle,
      body: _text(context),
      bottom: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!_readToEnd)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                l10n.termsScrollHint,
                key: const Key('terms-scroll-hint'),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          CheckboxListTile(
            key: const Key('charter-checkbox'),
            value: _checked,
            enabled: _readToEnd,
            onChanged: (v) => setState(() => _checked = v ?? false),
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.charterCheckbox),
          ),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  key: const Key('terms-decline'),
                  onPressed: _decline,
                  child: Text(l10n.termsDecline),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton(
                  key: const Key('charter-continue'),
                  onPressed: _readToEnd && _checked && !_saving
                      ? _accept
                      : null,
                  child: Text(l10n.termsAccept),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
