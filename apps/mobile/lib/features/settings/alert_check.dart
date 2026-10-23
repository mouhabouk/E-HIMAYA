import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/providers.dart';
import '../../core/platform/device_services.dart';
import '../../core/push/push_dedup.dart';
import '../../core/push/push_messaging.dart';
import '../../core/push/push_notifications.dart';
import '../../core/push/push_payload.dart';
import '../../core/routing/app_router.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../volunteer/volunteer_providers.dart';

/// Something on the phone that may keep our alerts from getting through.
enum AlertIssue {
  /// Notifications refused (POST_NOTIFICATIONS on Android 13+, or turned off).
  notificationsOff,

  /// The user lowered or blocked the official alerts channel.
  alertChannelMuted,

  /// Do Not Disturb is on and the user did not opt in to critical alerts.
  doNotDisturb,

  /// Android 14+: full-screen notifications not allowed (most severe alerts).
  fullScreenDenied,

  /// The app is battery-optimised while the volunteer is on call.
  batteryOptimized,

  /// No push on this phone (no Google Play services, build without Firebase): alerts arrive
  /// only while the app is open.
  pushUnavailable,
}

/// Android importance below which the channel no longer rings nor pops up (IMPORTANCE_HIGH).
const _highImportance = 4;

/// The issues found in [health]. The battery optimisation is reported only for a volunteer who
/// is ready (high-priority pushes reach everyone else through Doze anyway).
List<AlertIssue> alertIssues(
  AlertHealth health, {
  required bool pushAvailable,
  required bool volunteerReady,
  required bool criticalOptIn,
}) {
  final importance = health.channelImportance[alertChannelId];
  return [
    if (health.notificationsEnabled == false) AlertIssue.notificationsOff,
    if (importance != null && importance < _highImportance)
      AlertIssue.alertChannelMuted,
    if (health.doNotDisturb == true &&
        !(criticalOptIn && health.policyAccess == true))
      AlertIssue.doNotDisturb,
    if (health.fullScreenIntentAllowed == false) AlertIssue.fullScreenDenied,
    if (volunteerReady && health.ignoringBatteryOptimizations == false)
      AlertIssue.batteryOptimized,
    if (!pushAvailable) AlertIssue.pushUnavailable,
  ];
}

/// The volunteer is on call right now.
final volunteerReadyNowProvider = Provider<bool>((ref) {
  final v = ref.watch(volunteerProvider).value;
  return v != null && v.isReadyAt(ref.watch(clockProvider)());
});

/// Shows what an official alert looks like and sounds like on this phone.
Future<void> showTestAlert(WidgetRef ref, AppLocalizations l10n) async {
  final payload = PushPayload(
    kind: PushKind.alert,
    data: const {'type': 'alert', 'id': 'test', 'severity': 'medium'},
    title: l10n.testAlertTitle,
    body: l10n.testAlertBody,
  );
  final notifications = ref.read(pushNotificationsProvider);
  final id = notificationIdFor(payload);
  if (notifications is LocalPushNotifications) {
    // Rings again on every tap (a replaced notification would stay silent).
    await notifications.plugin.cancel(id: id);
  }
  await notifications.show(id, payload, channelId: alertChannelId);
}

/// Asks a volunteer who just became ready to exempt the app from battery optimisation, with
/// the reason. Never asked to other users, at most once a month, and only when it matters.
Future<void> maybeAskBatteryExemption(
  BuildContext context,
  WidgetRef ref,
) async {
  final prefs = ref.read(appPrefsProvider);
  final now = ref.read(clockProvider)();
  final asked = prefs.batteryOptAskedAt;
  if (asked != null && now.difference(asked) < const Duration(days: 30)) {
    return;
  }
  final health = await ref.read(deviceServicesProvider).alertHealth();
  if (health.ignoringBatteryOptimizations != false || !context.mounted) return;
  await prefs.setBatteryOptAskedAt(now);
  if (!context.mounted) return;
  final l10n = AppLocalizations.of(context);
  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.battery_alert),
      title: Text(l10n.batteryExemptTitle),
      content: Text(l10n.batteryExemptBody),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: Text(l10n.actionNotNow),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text(l10n.batteryExemptAllow),
        ),
      ],
    ),
  );
  if (ok == true) {
    await ref.read(deviceServicesProvider).requestIgnoreBatteryOptimizations();
  }
}

/// «Alert delivery check»: what may block our alerts on this phone, each with a way to fix
/// it, a test alert, and the shortcut to the alert channel settings.
class AlertCheckScreen extends ConsumerStatefulWidget {
  const AlertCheckScreen({super.key});

  @override
  ConsumerState<AlertCheckScreen> createState() => _AlertCheckScreenState();
}

class _AlertCheckScreenState extends ConsumerState<AlertCheckScreen> {
  AlertHealth? _health;
  late final AppLifecycleListener _lifecycle;

  @override
  void initState() {
    super.initState();
    // Back from a system settings page: check again.
    _lifecycle = AppLifecycleListener(onResume: _check);
    unawaited(_check());
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  Future<void> _check() async {
    final health = await ref.read(deviceServicesProvider).alertHealth();
    if (mounted) setState(() => _health = health);
  }

  Future<void> _fix(AlertIssue issue) async {
    final device = ref.read(deviceServicesProvider);
    switch (issue) {
      case AlertIssue.notificationsOff:
        final notifications = ref.read(pushNotificationsProvider);
        await notifications.requestPermission();
        await _check();
        if (_health?.notificationsEnabled == false) {
          await device.openAppNotificationSettings();
        }
      case AlertIssue.alertChannelMuted:
        await device.openChannelSettings(alertChannelId);
      case AlertIssue.doNotDisturb:
        if (mounted) await openCriticalAlerts(context);
      case AlertIssue.fullScreenDenied:
        await device.openFullScreenIntentSettings();
      case AlertIssue.batteryOptimized:
        await device.requestIgnoreBatteryOptimizations();
      case AlertIssue.pushUnavailable:
        break;
    }
    await _check();
  }

  static IconData _icon(AlertIssue issue) => switch (issue) {
    AlertIssue.notificationsOff => Icons.notifications_off,
    AlertIssue.alertChannelMuted => Icons.volume_off,
    AlertIssue.doNotDisturb => Icons.do_not_disturb_on,
    AlertIssue.fullScreenDenied => Icons.fullscreen_exit,
    AlertIssue.batteryOptimized => Icons.battery_saver,
    AlertIssue.pushUnavailable => Icons.cloud_off,
  };

  static String _title(AppLocalizations l10n, AlertIssue issue) =>
      switch (issue) {
        AlertIssue.notificationsOff => l10n.issueNotificationsOff,
        AlertIssue.alertChannelMuted => l10n.issueChannelMuted,
        AlertIssue.doNotDisturb => l10n.issueDnd,
        AlertIssue.fullScreenDenied => l10n.issueFullScreen,
        AlertIssue.batteryOptimized => l10n.issueBatteryOptimized,
        AlertIssue.pushUnavailable => l10n.issuePushUnavailable,
      };

  static String _help(AppLocalizations l10n, AlertIssue issue) =>
      switch (issue) {
        AlertIssue.notificationsOff => l10n.issueNotificationsOffHelp,
        AlertIssue.alertChannelMuted => l10n.issueChannelMutedHelp,
        AlertIssue.doNotDisturb => l10n.issueDndHelp,
        AlertIssue.fullScreenDenied => l10n.issueFullScreenHelp,
        AlertIssue.batteryOptimized => l10n.issueBatteryOptimizedHelp,
        AlertIssue.pushUnavailable => l10n.issuePushUnavailableHelp,
      };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final health = _health;
    final issues = health == null
        ? const <AlertIssue>[]
        : alertIssues(
            health,
            pushAvailable: ref.watch(pushAvailableProvider),
            volunteerReady: ref.watch(volunteerReadyNowProvider),
            criticalOptIn: ref.read(appPrefsProvider).criticalAlertsOptIn,
          );
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.alertCheckTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          Text(l10n.alertCheckIntro, style: theme.textTheme.bodyMedium),
          const SizedBox(height: 16),
          if (health == null)
            const Center(child: CircularProgressIndicator())
          else if (issues.isEmpty)
            Card(
              key: const Key('alert-check-ok'),
              child: ListTile(
                leading: Icon(
                  Icons.check_circle,
                  color: theme.colorScheme.primary,
                ),
                title: Text(l10n.alertCheckAllGood),
              ),
            )
          else
            for (final issue in issues)
              Card(
                key: Key('alert-issue-${issue.name}'),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      ListTile(
                        leading: Icon(
                          _icon(issue),
                          color: theme.colorScheme.error,
                        ),
                        title: Text(_title(l10n, issue)),
                        subtitle: Text(_help(l10n, issue)),
                      ),
                      if (issue != AlertIssue.pushUnavailable)
                        Align(
                          alignment: AlignmentDirectional.centerEnd,
                          child: Padding(
                            padding: const EdgeInsetsDirectional.only(end: 16),
                            child: FilledButton.tonal(
                              onPressed: () => _fix(issue),
                              child: Text(l10n.alertCheckFix),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('alert-test'),
            icon: const Icon(Icons.campaign),
            label: Text(l10n.testAlertButton),
            onPressed: () async {
              await showTestAlert(ref, l10n);
              if (context.mounted) {
                ScaffoldMessenger.of(context)
                    .showSnackBar(SnackBar(content: Text(l10n.testAlertSent)));
              }
            },
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('alert-channel-settings'),
            icon: const Icon(Icons.tune),
            label: Text(l10n.alertChannelSettings),
            onPressed: () => ref
                .read(deviceServicesProvider)
                .openChannelSettings(alertChannelId),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('alert-critical'),
            icon: const Icon(Icons.priority_high),
            label: Text(l10n.criticalAlertsTitle),
            onPressed: () => openCriticalAlerts(context),
          ),
        ],
      ),
    );
  }
}

Future<void> openCriticalAlerts(BuildContext context) =>
    context.push(Routes.criticalAlerts);

/// Explicit opt-in for the most severe official alerts to sound through Do Not Disturb
/// (Android). Nothing is enabled without the user reading this and agreeing; they can turn it
/// off here at any time.
class CriticalAlertsScreen extends ConsumerStatefulWidget {
  const CriticalAlertsScreen({super.key});

  @override
  ConsumerState<CriticalAlertsScreen> createState() =>
      _CriticalAlertsScreenState();
}

class _CriticalAlertsScreenState extends ConsumerState<CriticalAlertsScreen> {
  late bool _on = ref.read(appPrefsProvider).criticalAlertsOptIn;
  bool _waitingAccess = false;
  late final AppLifecycleListener _lifecycle;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: _afterSettings);
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  /// Back from the "Do Not Disturb access" page: finish the opt-in if access was granted.
  Future<void> _afterSettings() async {
    if (!_waitingAccess) return;
    _waitingAccess = false;
    final health = await ref.read(deviceServicesProvider).alertHealth();
    if (health.policyAccess == true) await _enable();
  }

  Future<void> _enable() async {
    final notifications = ref.read(pushNotificationsProvider);
    if (notifications is LocalPushNotifications) {
      await notifications.setCriticalChannel(true);
    }
    await ref.read(appPrefsProvider).setCriticalAlertsOptIn(true);
    if (mounted) setState(() => _on = true);
  }

  Future<void> _optIn() async {
    final health = await ref.read(deviceServicesProvider).alertHealth();
    if (health.policyAccess == true) {
      await _enable();
      return;
    }
    _waitingAccess = true;
    await ref.read(deviceServicesProvider).openDndAccessSettings();
  }

  Future<void> _optOut() async {
    final notifications = ref.read(pushNotificationsProvider);
    if (notifications is LocalPushNotifications) {
      await notifications.setCriticalChannel(false);
    }
    await ref.read(appPrefsProvider).setCriticalAlertsOptIn(false);
    if (mounted) setState(() => _on = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.criticalAlertsTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          Icon(Icons.priority_high, size: 48, color: theme.colorScheme.error),
          const SizedBox(height: 16),
          Text(l10n.criticalAlertsIntro, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 12),
          Text(l10n.criticalAlertsHow, style: theme.textTheme.bodyMedium),
          const SizedBox(height: 24),
          if (_on) ...[
            ListTile(
              key: const Key('critical-on'),
              leading: Icon(
                Icons.check_circle,
                color: theme.colorScheme.primary,
              ),
              title: Text(l10n.criticalAlertsEnabled),
            ),
            OutlinedButton(
              key: const Key('critical-opt-out'),
              onPressed: _optOut,
              child: Text(l10n.criticalAlertsDisable),
            ),
          ] else
            FilledButton(
              key: const Key('critical-opt-in'),
              onPressed: _optIn,
              child: Text(l10n.criticalAlertsEnable),
            ),
        ],
      ),
    );
  }
}
