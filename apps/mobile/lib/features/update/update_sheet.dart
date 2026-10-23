import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/settings/settings_controller.dart';
import '../../core/storage/app_prefs.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../institution/institution_providers.dart';
import 'app_release.dart';

/// Shows "What's new" once per new build (addition 3). A mandatory update (below the oldest build
/// still allowed) cannot be dismissed, but the emergency numbers stay one tap away.
class UpdateGate extends ConsumerStatefulWidget {
  const UpdateGate({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<UpdateGate> createState() => _UpdateGateState();
}

class _UpdateGateState extends ConsumerState<UpdateGate> {
  int? _shownFor;

  void _maybeShow(AppRelease? release) {
    if (release == null || !release.updateAvailable) return;
    if (_shownFor == release.latestBuild) return;
    final postponed = ref.read(appPrefsProvider).updatePostponedBuild;
    if (!release.mandatory && postponed == release.latestBuild) return;
    _shownFor = release.latestBuild;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(showUpdateSheet(context, ref, release));
    });
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(appReleaseProvider, (_, next) => _maybeShow(next.value));
    _maybeShow(ref.watch(appReleaseProvider).value);
    return widget.child;
  }
}

Future<void> showUpdateSheet(
  BuildContext context,
  WidgetRef ref,
  AppRelease release,
) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  isDismissible: !release.mandatory,
  enableDrag: !release.mandatory,
  builder: (context) => PopScope(
    canPop: !release.mandatory,
    child: _UpdateSheet(release: release),
  ),
);

class _UpdateSheet extends ConsumerWidget {
  const _UpdateSheet({required this.release});

  final AppRelease release;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final notes = release.notesFor(ref.watch(localeCodeProvider));
    return SafeArea(
      child: Padding(
        key: Key(release.mandatory ? 'update-mandatory' : 'update-optional'),
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(
              Icons.system_update,
              size: 48,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 12),
            Semantics(
              header: true,
              child: Text(
                release.mandatory
                    ? l10n.updateMandatoryTitle
                    : l10n.updateTitle,
                textAlign: TextAlign.center,
                style: theme.textTheme.titleLarge,
              ),
            ),
            const SizedBox(height: 8),
            if (release.mandatory)
              Text(l10n.updateMandatoryBody, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            Text(
              l10n.updateWhatsNew(release.latestVersion),
              style: theme.textTheme.titleSmall,
            ),
            if (notes.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(notes, key: const Key('update-notes')),
            ],
            const SizedBox(height: 8),
            Text(l10n.updateDataKept, style: theme.textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('update-now'),
              icon: const Icon(Icons.download),
              label: Text(l10n.updateNow),
              onPressed: () async {
                final messenger = ScaffoldMessenger.of(context);
                final ok = await ref.read(urlOpenerProvider)(release.updateUri);
                if (!ok) {
                  messenger.showSnackBar(
                    SnackBar(content: Text(l10n.updateOpenFailed)),
                  );
                }
              },
            ),
            const SizedBox(height: 8),
            if (release.mandatory)
              // The sheet cannot be closed: 198 stays one tap away inside it.
              OutlinedButton.icon(
                key: const Key('update-call-198'),
                icon: const Icon(Icons.phone),
                label: Text(l10n.call198),
                onPressed: () =>
                    ref.read(dialerProvider)(emergencyNumbers.first.telUri),
              )
            else
              TextButton(
                key: const Key('update-later'),
                onPressed: () async {
                  await ref.read(appReleaseProvider.notifier).postpone(release);
                  if (context.mounted) Navigator.of(context).pop();
                },
                child: Text(l10n.updateLater),
              ),
          ],
        ),
      ),
    );
  }
}
