import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/notify_models.dart';
import '../../core/push/push_simulation_banner.dart';
import '../../core/routing/app_router.dart';
import '../../core/security/locked_alert.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'alert_labels.dart';
import 'alerts_providers.dart';

/// Active alerts for the user's area, then the notifications inbox (FR-A-060, FR-A-061).
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final lang = ref.watch(localeCodeProvider);
    final alerts = ref.watch(currentAlertsProvider);
    final alertsState = ref.watch(activeAlertsProvider);
    final hasIdentity = ref.watch(
      identityProvider.select((s) => s.hasIdentity),
    );
    final inbox = ref.watch(inboxProvider);

    Future<void> refresh() async {
      await Future.wait([
        ref.read(activeAlertsProvider.notifier).refresh(),
        ref.refresh(inboxProvider.future).then((_) {}, onError: (_) {}),
      ]);
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.notificationsTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            const PushSimulationBanner(),
            _SectionTitle(l10n.activeAlertsTitle),
            if (alertsState.isLoading && alerts.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (alerts.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    Icon(Icons.check_circle, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Expanded(child: Text(l10n.activeAlertsNone)),
                  ],
                ),
              ),
            for (final a in alerts) AlertCard(alert: a, lang: lang),
            const SizedBox(height: 16),
            _SectionTitle(l10n.inboxTitle),
            if (!hasIdentity)
              Text(l10n.inboxNoIdentity)
            else
              inbox.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(16),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => Text(errorMessageFor(l10n, e)),
                data: (state) => Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (state.items.isEmpty) Text(l10n.inboxEmpty),
                    for (final item in state.items)
                      _InboxTile(item: item, lang: lang),
                    if (state.hasMore)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: OutlinedButton(
                          key: const Key('inbox-more'),
                          onPressed: state.loadingMore
                              ? null
                              : () => ref
                                    .read(inboxProvider.notifier)
                                    .loadMore()
                                    .catchError((Object e) {
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context)
                                            .showSnackBar(
                                              SnackBar(
                                                content: Text(
                                                  errorMessageFor(l10n, e),
                                                ),
                                              ),
                                            );
                                      }
                                    }),
                          child: Text(l10n.inboxLoadMore),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Semantics(
      header: true,
      child: Text(text, style: Theme.of(context).textTheme.titleMedium),
    ),
  );
}

/// One active alert, coloured by severity.
class AlertCard extends StatelessWidget {
  const AlertCard({super.key, required this.alert, required this.lang});

  final ActiveAlert alert;
  final String lang;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (bg, _) = severityColors(alert.severity);
    return Card(
      key: Key('alert-${alert.id}'),
      shape: RoundedRectangleBorder(
        side: BorderSide(color: bg, width: 2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ListTile(
        leading: Icon(hazardIcon(alert.hazard), color: bg, size: 32),
        title: Text(alert.title.of(lang)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SeverityChip(severity: alert.severity),
              Text(l10n.alertUntil(dateTimeLabel(context, alert.expiresAt))),
            ],
          ),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push(Routes.alert(alert.id)),
      ),
    );
  }
}

class _InboxTile extends StatelessWidget {
  const _InboxTile({required this.item, required this.lang});

  final InboxItem item;
  final String lang;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final severity = item.severity;
    final subtitle = item.isAlert
        ? (item.active ? l10n.inboxAlertActive : l10n.inboxAlertEnded)
        : topicLabel(l10n, item.topic);
    return Card(
      key: Key('inbox-${item.id}'),
      child: ExpansionTile(
        leading: Icon(
          item.isAlert ? Icons.warning_amber : Icons.campaign,
          color: severity == null
              ? theme.colorScheme.primary
              : severityColors(severity).$1,
        ),
        title: Text(item.title.of(lang)),
        subtitle: Text(
          '$subtitle · ${dateTimeLabel(context, item.publishedAt)}',
        ),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        childrenPadding: const EdgeInsetsDirectional.fromSTEB(16, 0, 16, 16),
        children: [
          Text(item.body.of(lang)),
          if (item.isAlert && item.active)
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton(
                onPressed: () => context.push(Routes.alert(item.id)),
                child: Text(l10n.alertOpen),
              ),
            ),
        ],
      ),
    );
  }
}

/// Detail of an alert (opened from the list, the banner or a push).
class AlertDetailScreen extends ConsumerWidget {
  const AlertDetailScreen({super.key, required this.alertId});

  final String alertId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final lang = ref.watch(localeCodeProvider);
    final state = ref.watch(activeAlertsProvider);
    final alert = (state.value ?? const <ActiveAlert>[])
        .where((a) => a.id == alertId)
        .firstOrNull;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.alertTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: switch ((alert, state.isLoading)) {
          (null, true) => const Center(child: CircularProgressIndicator()),
          (null, false) => Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.check_circle,
                  size: 48,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(height: 12),
                Text(l10n.alertNotActive, textAlign: TextAlign.center),
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: () => context.go(Routes.notifications),
                  child: Text(l10n.notificationsTitle),
                ),
              ],
            ),
          ),
          (final ActiveAlert a, _) => _AlertDetail(alert: a, lang: lang),
        },
      ),
    );
  }
}

/// The only screen shown while the app is displayed over a locked phone (a most severe alert
/// opened it full screen): the public alert itself, nothing personal, no navigation. Leaving it
/// (button or back) asks the phone to unlock first and stays here when the user cancels.
class LockedAlertScreen extends ConsumerWidget {
  const LockedAlertScreen({super.key});

  static Future<void> _leave(BuildContext context, WidgetRef ref) async {
    final alertId = ref.read(lockedAlertProvider).alertId;
    final router = GoRouter.of(context);
    if (!await ref.read(lockedAlertProvider.notifier).unlock()) return;
    router.go(alertId == null ? Routes.home : Routes.alert(alertId));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final lang = ref.watch(localeCodeProvider);
    final pushed = ref.watch(lockedAlertProvider).alert;
    final alerts = ref.watch(currentAlertsProvider);
    final alert = pushed?.id == null
        ? ref.watch(highAlertsProvider).firstOrNull
        : alerts.where((a) => a.id == pushed!.id).firstOrNull;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_leave(context, ref));
      },
      child: Scaffold(
        key: const Key('locked-alert'),
        appBar: AppBar(
          automaticallyImplyLeading: false,
          title: Text(l10n.alertTitle),
        ),
        body: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: alert != null
                    ? _AlertDetail(alert: alert, lang: lang, locked: true)
                    : ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          // The pushed text of a public official alert (never a personal push).
                          Text(
                            pushed?.title ?? l10n.alertTitle,
                            style: theme.textTheme.titleLarge,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            pushed?.body ?? '',
                            style: theme.textTheme.bodyLarge,
                          ),
                        ],
                      ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton.icon(
                  key: const Key('locked-alert-open-app'),
                  icon: const Icon(Icons.lock_open),
                  label: Text(l10n.lockedAlertOpenApp),
                  onPressed: () => _leave(context, ref),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AlertDetail extends StatelessWidget {
  const _AlertDetail({
    required this.alert,
    required this.lang,
    this.locked = false,
  });

  final ActiveAlert alert;
  final String lang;

  /// Over the lock screen: no link to other screens.
  final bool locked;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final (bg, fg) = severityColors(alert.severity);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              Icon(hazardIcon(alert.hazard), color: fg, size: 40),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${severityLabel(l10n, alert.severity)} · ${hazardLabel(l10n, alert.hazard)}',
                      style: theme.textTheme.labelLarge?.copyWith(color: fg),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      alert.title.of(lang),
                      style: theme.textTheme.titleLarge?.copyWith(color: fg),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Text(alert.body.of(lang), style: theme.textTheme.bodyLarge),
        const SizedBox(height: 16),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.schedule),
          title: Text(
            l10n.alertPublishedAt(dateTimeLabel(context, alert.publishedAt)),
          ),
          subtitle: Text(
            l10n.alertUntil(dateTimeLabel(context, alert.expiresAt)),
          ),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.place),
          title: Text(
            alert.isNational
                ? l10n.alertAreaNational
                : alert.hasPolygon
                ? l10n.alertAreaZone
                : l10n.alertAreaGouvernorats(alert.gouvernoratCodes.length),
          ),
        ),
        if (!locked) const SizedBox(height: 8),
        if (!locked)
          FilledButton.icon(
            key: const Key('alert-tips'),
            icon: const Icon(Icons.health_and_safety),
            label: Text(l10n.tipsTitle),
            onPressed: () => context.push(Routes.tips),
          ),
      ],
    );
  }
}

/// Banner of the home screen for active high-severity alerts (one line each).
class HighAlertsBanner extends ConsumerWidget {
  const HighAlertsBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alerts = ref.watch(highAlertsProvider);
    if (alerts.isEmpty) return const SizedBox.shrink();
    final lang = ref.watch(localeCodeProvider);
    final l10n = AppLocalizations.of(context);
    final (bg, fg) = severityColors(AlertSeverity.high);
    return Semantics(
      liveRegion: true,
      child: Card(
        key: const Key('high-alerts-banner'),
        color: bg,
        child: Column(
          children: [
            for (final a in alerts)
              ListTile(
                leading: Icon(hazardIcon(a.hazard), color: fg),
                title: Text(
                  a.title.of(lang),
                  style: TextStyle(color: fg, fontWeight: FontWeight.w600),
                ),
                subtitle: Text(
                  l10n.alertUntil(dateTimeLabel(context, a.expiresAt)),
                  style: TextStyle(color: fg),
                ),
                trailing: Icon(Icons.chevron_right, color: fg),
                onTap: () => context.push(Routes.alert(a.id)),
              ),
          ],
        ),
      ),
    );
  }
}
