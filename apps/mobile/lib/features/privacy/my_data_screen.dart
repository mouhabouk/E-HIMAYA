import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../../core/auth/identity.dart';
import '../../core/http/ehimaya_api.dart' show LastAdminException;
import '../../core/http/error_messages.dart';
import '../../core/routing/app_router.dart';
import '../../l10n/app_localizations.dart';
import 'account_deletion.dart';

/// Where the exported copy is written: the Downloads folder the app may write to (Android:
/// the app's own folder under Android/data, readable with a file manager or over USB), else
/// the app documents folder. Overridden in tests.
final exportDirProvider = Provider<Future<Directory> Function()>(
  (ref) =>
      () async =>
          await getDownloadsDirectory() ??
          await getApplicationDocumentsDirectory(),
);

/// «My data» (A6): download a copy of everything the server holds about the user, or delete
/// the account.
class MyDataScreen extends ConsumerStatefulWidget {
  const MyDataScreen({super.key});

  @override
  ConsumerState<MyDataScreen> createState() => _MyDataScreenState();
}

class _MyDataScreenState extends ConsumerState<MyDataScreen> {
  String? _json;
  bool _busy = false;

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _download() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      final json = await ref.read(citizenRightsProvider).exportData();
      if (mounted) setState(() => _json = json);
    } on Object catch (e) {
      if (mounted) _message(errorMessageFor(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save(String json) async {
    final l10n = AppLocalizations.of(context);
    try {
      final dir = await ref.read(exportDirProvider)();
      final stamp = DateTime.now()
          .toUtc()
          .toIso8601String()
          .replaceAll(RegExp('[^0-9]'), '')
          .substring(0, 14);
      final file = File(p.join(dir.path, 'ehimaya-my-data-$stamp.json'));
      await file.writeAsString(json, flush: true);
      if (mounted) _message(l10n.myDataSaved(file.path));
    } on FileSystemException {
      if (mounted) _message(l10n.myDataSaveFailed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final json = _json;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.myDataTitle)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          Text(l10n.myDataIntro, style: theme.textTheme.bodyMedium),
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('my-data-download'),
            icon: _busy
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.download),
            label: Text(l10n.myDataDownload),
            onPressed: _busy ? null : _download,
          ),
          if (json != null) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    key: const Key('my-data-copy'),
                    icon: const Icon(Icons.copy),
                    label: Text(l10n.myDataCopy),
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: json));
                      if (mounted) _message(l10n.myDataCopied);
                    },
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    key: const Key('my-data-save'),
                    icon: const Icon(Icons.save_alt),
                    label: Text(l10n.myDataSave),
                    onPressed: () => _save(json),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Container(
              key: const Key('my-data-json'),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              // JSON reads left to right in every language.
              child: Directionality(
                textDirection: TextDirection.ltr,
                child: SelectableText(
                  json,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontFamily: 'monospace',
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 32),
          const Divider(),
          ListTile(
            key: const Key('my-data-delete'),
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.delete_forever, color: theme.colorScheme.error),
            title: Text(
              l10n.deleteAccountTitle,
              style: TextStyle(color: theme.colorScheme.error),
            ),
            subtitle: Text(l10n.deleteAccountSubtitle),
            onTap: () => context.push(Routes.deleteAccount),
          ),
        ],
      ),
    );
  }
}

/// Deleting the account needs the confirmation word typed in full (in the UI language).
class DeleteAccountScreen extends ConsumerStatefulWidget {
  const DeleteAccountScreen({super.key});

  @override
  ConsumerState<DeleteAccountScreen> createState() =>
      _DeleteAccountScreenState();
}

/// Whether [typed] is the confirmation [word] (case and surrounding spaces ignored).
bool deleteConfirmationMatches(String typed, String word) =>
    typed.trim().toLowerCase() == word.trim().toLowerCase();

class _DeleteAccountScreenState extends ConsumerState<DeleteAccountScreen> {
  final _controller = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _delete() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      await ref.read(citizenRightsProvider).deleteAccount();
      // The router now sends the app back to the charter (start of onboarding).
      messenger.showSnackBar(SnackBar(content: Text(l10n.deleteAccountDone)));
      if (mounted) context.go(Routes.charter);
    } on Object catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              e is LastAdminException
                  ? l10n.deleteAccountLastAdmin
                  : errorMessageFor(l10n, e),
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final registered = ref.watch(identityProvider).isRegistered;
    final word = l10n.deleteAccountWord;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.deleteAccountTitle)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          Icon(Icons.warning_amber, size: 48, color: theme.colorScheme.error),
          const SizedBox(height: 16),
          Text(
            registered
                ? l10n.deleteAccountExplain
                : l10n.deleteAccountExplainAnonymous,
            style: theme.textTheme.bodyLarge,
          ),
          const SizedBox(height: 24),
          TextField(
            key: const Key('delete-confirm-field'),
            controller: _controller,
            enabled: !_busy,
            autocorrect: false,
            decoration: InputDecoration(
              labelText: l10n.deleteAccountTypeWord(word),
              border: const OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 16),
          FilledButton(
            key: const Key('delete-confirm'),
            style: FilledButton.styleFrom(
              backgroundColor: theme.colorScheme.error,
              foregroundColor: theme.colorScheme.onError,
            ),
            onPressed:
                !_busy && deleteConfirmationMatches(_controller.text, word)
                ? _delete
                : null,
            child: _busy
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l10n.deleteAccountConfirm),
          ),
        ],
      ),
    );
  }
}
