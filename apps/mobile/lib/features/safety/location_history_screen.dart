import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// Addition 7b §2: the 72-hour location history. Off by default, with its own consent; while on,
/// the phone keeps sending its position; an operator reads it only for a report they handle,
/// with a reason, and the user is told. Turning it off deletes every point at once.
class LocationHistoryScreen extends ConsumerStatefulWidget {
  const LocationHistoryScreen({super.key});

  @override
  ConsumerState<LocationHistoryScreen> createState() =>
      _LocationHistoryScreenState();
}

class _LocationHistoryScreenState extends ConsumerState<LocationHistoryScreen> {
  bool _agreed = false;
  bool _busy = false;

  Future<void> _set(bool on, String noticeVersion) async {
    final l10n = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await ref
          .read(apiProvider)
          .setLocationHistory(
            enabled: on,
            noticeVersion: on ? noticeVersion : null,
            locale: ref.read(localeCodeProvider),
          );
      final recorder = ref.read(locationHistoryRecorderProvider);
      on ? recorder.start() : await recorder.stop();
      await ref.read(appPrefsProvider).setLocationHistoryOn(on);
      ref.invalidate(locationHistoryProvider);
    } on ApiException catch (e) {
      if (mounted) showSafetySnack(context, apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final state = ref.watch(locationHistoryProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyHistoryTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: state.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
            child: SafetyError(
              error: e,
              onRetry: () => ref.invalidate(locationHistoryProvider),
            ),
          ),
          data: (h) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(l10n.safetyHistoryNotice, style: theme.textTheme.bodyLarge),
              const SizedBox(height: 16),
              if (!h.available)
                Text(
                  l10n.safetyHistoryUnavailable,
                  key: const Key('history-unavailable'),
                )
              else if (h.enabled) ...[
                Card(
                  child: ListTile(
                    key: const Key('history-on'),
                    leading: const Icon(Icons.route),
                    title: Text(l10n.safetyHistoryOn),
                    subtitle: h.until == null
                        ? null
                        : Text(
                            l10n.safetyHistoryUntil(
                              safetyTime(context, h.until!),
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  key: const Key('history-off'),
                  onPressed: _busy ? null : () => _set(false, h.noticeVersion),
                  icon: const Icon(Icons.location_off),
                  label: Text(l10n.safetyHistoryTurnOff),
                ),
              ] else ...[
                CheckboxListTile(
                  key: const Key('history-consent'),
                  contentPadding: EdgeInsets.zero,
                  value: _agreed,
                  onChanged: (v) => setState(() => _agreed = v == true),
                  title: Text(l10n.safetyHistoryConsent),
                ),
                FilledButton.icon(
                  key: const Key('history-turn-on'),
                  onPressed: _busy || !_agreed
                      ? null
                      : () => _set(true, h.noticeVersion),
                  icon: const Icon(Icons.route),
                  label: Text(l10n.safetyHistoryTurnOn),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
