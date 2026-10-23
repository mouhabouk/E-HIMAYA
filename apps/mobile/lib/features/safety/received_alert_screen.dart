import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../institution/institution_providers.dart';
import 'safety_models.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// Additions 11.1 and 11.2: what a linked contact sees when they receive an SOS message or a
/// fired safety check. Opened by the critical notification (after the phone is unlocked: the
/// content is personal). The position follows the live share when there is one.
class SafetyAlertScreen extends ConsumerStatefulWidget {
  const SafetyAlertScreen({super.key, required this.alertId});

  final String alertId;

  @override
  ConsumerState<SafetyAlertScreen> createState() => _SafetyAlertScreenState();
}

class _SafetyAlertScreenState extends ConsumerState<SafetyAlertScreen> {
  static const refreshEvery = Duration(seconds: 30);

  Timer? _refresh;
  bool _markedSeen = false;

  @override
  void initState() {
    super.initState();
    _refresh = Timer.periodic(refreshEvery, (_) {
      final a = ref.read(safetyAlertProvider(widget.alertId)).value;
      if (a?.live?.active == true) {
        ref.invalidate(safetyAlertProvider(widget.alertId));
      }
    });
  }

  @override
  void dispose() {
    _refresh?.cancel();
    super.dispose();
  }

  Future<void> _seen(SafetyAlertView a) async {
    if (_markedSeen || a.mine || a.seen) return;
    _markedSeen = true;
    try {
      await ref.read(apiProvider).markSafetyAlertSeen(a.id);
    } on ApiException {
      _markedSeen = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final alert = ref.watch(safetyAlertProvider(widget.alertId));
    return Scaffold(
      backgroundColor: alert.value?.mine == false
          ? sosRed.withValues(alpha: 0.06)
          : null,
      appBar: AppBar(
        title: Text(l10n.safetyAlertTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: alert.when(
          data: (a) {
            unawaited(_seen(a));
            return _AlertBody(alert: a);
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
            child: SafetyError(
              error: e,
              onRetry: () =>
                  ref.invalidate(safetyAlertProvider(widget.alertId)),
            ),
          ),
        ),
      ),
    );
  }
}

class _AlertBody extends ConsumerWidget {
  const _AlertBody({required this.alert});

  final SafetyAlertView alert;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final who = alert.senderFirstName ?? l10n.safetySomeone;
    final latest = alert.latest;
    final phone = alert.senderPhone;
    final open = ref.read(urlOpenerProvider);
    final dial = ref.read(dialerProvider);
    final civil = emergencyNumbers.first;
    final live = alert.live;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            const Icon(Icons.sos, color: sosRed, size: 40),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                alert.mine
                    ? l10n.safetyAlertMine
                    : (alert.isCheck
                          ? l10n.safetyAlertCheckFrom(who)
                          : l10n.safetyAlertFrom(who)),
                key: const Key('alert-who'),
                style: theme.textTheme.titleLarge?.copyWith(
                  color: sosRed,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert.message,
                  key: const Key('alert-message'),
                  style: theme.textTheme.bodyLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  [
                    l10n.safetyAlertAt(safetyTime(context, alert.createdAt)),
                    if (alert.battery != null)
                      l10n.safetyAlertBattery(alert.battery!),
                  ].join(' · '),
                  style: theme.textTheme.bodySmall,
                ),
                if (alert.mine && alert.recipients != null)
                  Text(
                    l10n.safetyAlertSeenBy(
                      alert.seenBy ?? 0,
                      alert.recipients!,
                    ),
                    style: theme.textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (latest == null)
          Text(l10n.safetyAlertNoPosition)
        else ...[
          SafetyMap(point: latest.point),
          const SizedBox(height: 4),
          Text(
            [
              if (live?.active == true)
                l10n.safetyAlertLive(safetyTime(context, latest.at))
              else
                l10n.safetyAlertPositionAt(safetyTime(context, latest.at)),
              if (latest.point.accuracyM case final acc?)
                l10n.safetyAccuracy(acc.ceil()),
            ].join(' · '),
            style: theme.textTheme.bodySmall,
          ),
        ],
        const SizedBox(height: 16),
        if (!alert.mine) ...[
          if (phone != null)
            FilledButton.icon(
              key: const Key('alert-call'),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52),
              ),
              onPressed: () => dial(Uri(scheme: 'tel', path: phone)),
              icon: const Icon(Icons.phone),
              label: Text(l10n.safetyAlertCall(who)),
            ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: [
              if (phone != null)
                OutlinedButton.icon(
                  onPressed: () => open(Uri(scheme: 'sms', path: phone)),
                  icon: const Icon(Icons.sms),
                  label: Text(l10n.safetyBySms),
                ),
              if (phone != null && normalizeContactPhone(phone) != null)
                OutlinedButton.icon(
                  onPressed: () =>
                      open(whatsAppUri(normalizeContactPhone(phone)!, '')),
                  icon: const Icon(Icons.chat),
                  label: const Text('WhatsApp'),
                ),
              if (latest != null)
                OutlinedButton.icon(
                  key: const Key('alert-route'),
                  onPressed: () => open(
                    Uri.parse(
                      'geo:${latest.point.lat},${latest.point.lon}'
                      '?q=${latest.point.lat},${latest.point.lon}',
                    ),
                  ),
                  icon: const Icon(Icons.directions),
                  label: Text(l10n.safetyAlertRoute),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Text(l10n.safetyAlertReportHint, style: theme.textTheme.bodySmall),
          const SizedBox(height: 4),
          FilledButton.icon(
            key: const Key('alert-call-198'),
            style: FilledButton.styleFrom(
              backgroundColor: sosRed,
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(52),
            ),
            onPressed: () => dial(civil.telUri),
            icon: const Icon(Icons.local_fire_department),
            label: Text(l10n.safetyAlertCall198),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('alert-report'),
            onPressed: () => context.push(Routes.newReport),
            icon: const Icon(Icons.campaign),
            label: Text(l10n.safetyAlertReport),
          ),
        ],
      ],
    );
  }
}
