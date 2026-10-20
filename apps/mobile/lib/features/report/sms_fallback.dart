import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/config/providers.dart';
import '../../core/connectivity/connectivity.dart';
import '../../core/db/app_database.dart';
import '../../core/http/models.dart';
import '../../core/logging/log.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';

final _log = logger('report.sms');

/// FR-A-048: compact, machine-readable SMS body of a queued report, parsed by the platform's SMS
/// gateway (`POST /internal/sms/inbound`):
///
/// `EH1 <category> <lat>,<lon> <acc>m <id8>`
///
/// ASCII only, single spaces; coordinates with 5 decimals (≈ 1 m) and `.` whatever the UI
/// language; `acc` in whole metres rounded up and clamped to 1…99999, `0` when unknown; `id8`
/// the first 8 hex digits of the report's `client_uuid`, so the server merges the SMS report
/// with the same report when the phone syncs it later.
String smsReportBody({
  required ReportCategory category,
  required GeoPoint location,
  required String clientUuid,
}) {
  final id8 = clientUuid.replaceAll('-', '').toLowerCase();
  if (id8.length < 8 || !RegExp(r'^[0-9a-f]{8}').hasMatch(id8)) {
    throw ArgumentError.value(clientUuid, 'clientUuid', 'not a UUID');
  }
  final acc = location.accuracyM;
  final accM = acc == null || !acc.isFinite || acc <= 0
      ? 0
      : acc.ceil().clamp(1, 99999);
  // toStringAsFixed never localises digits or the decimal separator.
  final lat = location.lat.toStringAsFixed(5);
  final lon = location.lon.toStringAsFixed(5);
  return 'EH1 ${category.wire} $lat,$lon ${accM}m ${id8.substring(0, 8)}';
}

/// A usable SMS number: an optional `+` then 3 to 15 digits (spaces and dashes ignored).
/// Null when the configured value is empty or malformed (the option is then hidden).
String? normalizeSmsNumber(String raw) {
  final n = raw.replaceAll(RegExp(r'[\s-]'), '');
  return RegExp(r'^\+?[0-9]{3,15}$').hasMatch(n) ? n : null;
}

/// `sms:` URI that opens the SMS app with the number and the body filled in. The body is
/// percent-encoded (`%20`, not `+`, which some SMS apps would show literally).
Uri smsUri(String number, String body) =>
    Uri.parse('sms:$number?body=${Uri.encodeComponent(body)}');

/// Opens the SMS app (the user presses Send themselves). Returns false when it cannot.
typedef SmsComposer = Future<bool> Function(Uri smsUri);

Future<bool> _launchSms(Uri uri) async {
  try {
    return await launchUrl(uri, mode: LaunchMode.externalApplication);
  } on Exception {
    return false;
  }
}

final smsComposerProvider = Provider<SmsComposer>((ref) => _launchSms);

/// The platform SMS number from `--dart-define=SMS_REPORT_NUMBER`, null when not configured.
final smsReportNumberProvider = Provider<String?>(
  (ref) => normalizeSmsNumber(ref.watch(appConfigProvider).smsReportNumber),
);

/// The SMS body of a queued report row, or null when it lacks a valid position.
String? smsBodyForRow(PendingReport row) {
  try {
    final payload = jsonDecode(row.payload);
    if (payload is! Map) return null;
    final location = GeoPoint.fromJson(payload['location']);
    final category = ReportCategory.fromWire(row.category);
    if (location == null || category == null) return null;
    return smsReportBody(
      category: category,
      location: location,
      clientUuid: row.clientUuid,
    );
  } on FormatException {
    return null;
  } on ArgumentError {
    return null;
  }
}

/// FR-A-048: shown with a report (or SOS) still waiting in the queue while the phone has no
/// network at all. Offers (a) an SMS to the platform, prepared in the SMS app, and (b) a call
/// to 198 with the phone's own dialer (scenario 0). The report itself stays queued and is
/// synced when the network returns.
class OfflineFallbackCard extends ConsumerWidget {
  const OfflineFallbackCard({super.key, required this.row});

  final PendingReport row;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final online = ref.watch(onlineProvider).value ?? true;
    if (online) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final number = ref.watch(smsReportNumberProvider);
    final body = number == null ? null : smsBodyForRow(row);
    final civil = emergencyNumbers.first;
    return Semantics(
      container: true,
      liveRegion: true,
      child: Card(
        key: const Key('offline-fallback'),
        color: theme.colorScheme.errorContainer,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.signal_wifi_connected_no_internet_4,
                    color: theme.colorScheme.onErrorContainer,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Semantics(
                      header: true,
                      child: Text(
                        l10n.offlineFallbackTitle,
                        style: theme.textTheme.titleMedium?.copyWith(
                          color: theme.colorScheme.onErrorContainer,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                l10n.offlineFallbackBody,
                style: TextStyle(color: theme.colorScheme.onErrorContainer),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                key: const Key('offline-call-198'),
                style: FilledButton.styleFrom(
                  backgroundColor: theme.colorScheme.error,
                  foregroundColor: theme.colorScheme.onError,
                ),
                onPressed: () => ref.read(dialerProvider)(civil.telUri),
                icon: const Icon(Icons.call),
                label: Text(l10n.callNumber(civil.number)),
              ),
              if (number != null && body != null) ...[
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  key: const Key('offline-send-sms'),
                  onPressed: () =>
                      unawaited(_sendSms(context, ref, number, body)),
                  icon: const Icon(Icons.sms_outlined),
                  label: Text(l10n.offlineSendSms),
                ),
                const SizedBox(height: 4),
                Text(
                  l10n.offlineSmsHelp,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                  ),
                ),
                Text(
                  l10n.offlineSmsFee,
                  key: const Key('offline-sms-fee'),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onErrorContainer,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  static Future<void> _sendSms(
    BuildContext context,
    WidgetRef ref,
    String number,
    String body,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    final failed = AppLocalizations.of(context).offlineSmsFailed;
    final ok = await ref.read(smsComposerProvider)(smsUri(number, body));
    if (!ok) {
      _log.info('sms app not available');
      messenger.showSnackBar(SnackBar(content: Text(failed)));
    }
  }
}
