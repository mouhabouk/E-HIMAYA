import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/providers.dart';
import '../../core/connectivity/connectivity.dart';
import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/platform/device_services.dart';
import '../../core/power/scheduling.dart';
import '../../core/push/push_dedup.dart';
import '../../core/push/push_messaging.dart';
import '../../core/push/push_notifications.dart';
import '../../core/push/push_payload.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// What the self-test found. Nothing is sent to anyone.
class SelfTestResult {
  const SelfTestResult({
    required this.online,
    required this.health,
    required this.criticalChannel,
    required this.position,
    required this.battery,
  });

  final bool online;
  final AlertHealth health;
  final bool criticalChannel;
  final GeoPoint? position;
  final BatteryReading? battery;
}

final selfTestProvider = FutureProvider.autoDispose<SelfTestResult>((
  ref,
) async {
  final notifications = ref.read(pushNotificationsProvider);
  final result = SelfTestResult(
    online: await ref.read(connectivityProvider).isOnline(),
    health: await ref.read(deviceServicesProvider).alertHealth(),
    criticalChannel:
        notifications is LocalPushNotifications &&
        notifications.criticalEnabled,
    position: await ref
        .read(locationServiceProvider)
        .bestEffort(timeout: const Duration(seconds: 10)),
    battery: await ref.read(deviceServicesProvider).battery(),
  );
  await ref
      .read(databaseProvider)
      .addAlertHistory(
        SafetyAlertHistoryCompanion.insert(
          kind: 'test',
          at: ref.read(clockProvider)(),
          status: 'ok',
        ),
      );
  return result;
});

/// Addition 8.5: the alarm sound on the critical channel, the position on the map, network,
/// notifications and battery, and the contacts ready to receive the message.
class SelfTestScreen extends ConsumerWidget {
  const SelfTestScreen({super.key});

  Future<void> _ring(WidgetRef ref, AppLocalizations l10n) async {
    // No id: tapping it opens the safety hub, never an alert screen.
    final payload = PushPayload(
      kind: PushKind.safetyAlert,
      data: const {'type': 'safety_alert'},
      title: l10n.safetyTestAlarmTitle,
      body: l10n.safetyTestAlarmBody,
    );
    final notifications = ref.read(pushNotificationsProvider);
    final id = notificationIdFor(payload);
    if (notifications is LocalPushNotifications) {
      await notifications.plugin.cancel(id: id);
    }
    await notifications.show(id, payload);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final test = ref.watch(selfTestProvider);
    final contacts = ref.watch(emergencyContactsProvider).value ?? const [];
    final links = ref.watch(safetyLinksProvider).value ?? const [];

    Widget line(String key, bool ok, String title, [String? detail]) =>
        ListTile(
          key: Key('test-$key'),
          leading: Icon(
            ok ? Icons.check_circle : Icons.warning_amber,
            color: ok ? Colors.green.shade700 : Colors.amber.shade800,
          ),
          title: Text(title),
          subtitle: detail == null ? null : Text(detail),
        );

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyTestTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.safetyTestIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 12),
            FilledButton.icon(
              key: const Key('test-ring'),
              onPressed: () async {
                await _ring(ref, l10n);
                if (context.mounted) {
                  showSafetySnack(context, l10n.safetyTestAlarmSent);
                }
              },
              icon: const Icon(Icons.notifications_active),
              label: Text(l10n.safetyTestAlarm),
            ),
            const SizedBox(height: 12),
            ...test.when(
              loading: () => [
                const Center(child: CircularProgressIndicator()),
                const SizedBox(height: 8),
                Text(l10n.safetyTestRunning, textAlign: TextAlign.center),
              ],
              error: (e, _) => [
                SafetyError(
                  error: e,
                  onRetry: () => ref.invalidate(selfTestProvider),
                ),
              ],
              data: (r) => [
                line(
                  'notifications',
                  r.health.notificationsEnabled != false,
                  r.health.notificationsEnabled == false
                      ? l10n.safetyTestNotificationsOff
                      : l10n.safetyTestNotificationsOn,
                ),
                line(
                  'critical',
                  r.criticalChannel,
                  r.criticalChannel
                      ? l10n.safetyTestCriticalOn
                      : l10n.safetyTestCriticalOff,
                ),
                if (!r.criticalChannel)
                  Align(
                    alignment: AlignmentDirectional.centerEnd,
                    child: TextButton(
                      onPressed: () => context.push(Routes.criticalAlerts),
                      child: Text(l10n.safetyTestCriticalFix),
                    ),
                  ),
                if (r.health.doNotDisturb == true)
                  line('dnd', false, l10n.safetyTestDnd),
                line(
                  'network',
                  r.online,
                  r.online ? l10n.safetyTestOnline : l10n.safetyTestOffline,
                ),
                line(
                  'position',
                  r.position != null,
                  r.position == null
                      ? l10n.safetyTestNoPosition
                      : l10n.safetyTestPosition,
                  r.position?.accuracyM == null
                      ? null
                      : l10n.safetyAccuracy(r.position!.accuracyM!.ceil()),
                ),
                if (r.position != null) ...[
                  SafetyMap(point: r.position!, height: 180),
                  const SizedBox(height: 8),
                ],
                line(
                  'battery',
                  r.battery?.level == null || r.battery!.level! >= 20,
                  r.battery?.level == null
                      ? l10n.safetyTestBatteryUnknown
                      : l10n.safetyTestBattery(r.battery!.level!),
                  r.battery?.systemPowerSave == true
                      ? l10n.safetyTestPowerSave
                      : null,
                ),
                line(
                  'contacts',
                  contacts.isNotEmpty || links.isNotEmpty,
                  l10n.safetyTestContacts(contacts.length, links.length),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  key: const Key('test-again'),
                  onPressed: () => ref.invalidate(selfTestProvider),
                  icon: const Icon(Icons.refresh),
                  label: Text(l10n.safetyTestAgain),
                ),
                const SizedBox(height: 8),
                Text(
                  l10n.safetyTestNothingSent,
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
