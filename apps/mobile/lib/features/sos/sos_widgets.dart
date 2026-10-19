import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_router.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../institution/institution_providers.dart';
import '../institution/report_as_selector.dart';
import 'sos_service.dart';

/// Sends the SOS and shows the outcome (temporary code, or a call-198 fallback).
/// [organizationId] null: as the user themselves.
Future<void> performSos(
  BuildContext context,
  WidgetRef ref, {
  String? organizationId,
}) async {
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final router = GoRouter.of(context);
  final dial = ref.read(dialerProvider);
  final result = await ref
      .read(sosServiceProvider)
      .send(organizationId: organizationId);
  switch (result) {
    case SosQueued(:final tempCode):
      unawaited(
        router.push(
          Uri(
            path: Routes.reportQueued,
            queryParameters: {'code': tempCode, 'sos': '1'},
          ).toString(),
        ),
      );
    case SosNoLocation():
      final civil = emergencyNumbers.first;
      messenger.showSnackBar(
        SnackBar(
          duration: const Duration(seconds: 10),
          content: Text(l10n.sosNoLocation),
          action: SnackBarAction(
            label: l10n.callNumber(civil.number),
            onPressed: () => dial(civil.telUri),
          ),
        ),
      );
  }
}

/// Big SOS button of the home screen: first tap arms it (5 s), second tap sends. A long press
/// sends at once. Two taps from home = NFR-09 (≤ 3 taps).
class SosButton extends ConsumerStatefulWidget {
  const SosButton({super.key});

  @override
  ConsumerState<SosButton> createState() => _SosButtonState();
}

class _SosButtonState extends ConsumerState<SosButton> {
  bool _armed = false;
  bool _sending = false;
  Timer? _disarm;

  @override
  void dispose() {
    _disarm?.cancel();
    super.dispose();
  }

  Future<void> _send() async {
    _disarm?.cancel();
    setState(() {
      _armed = false;
      _sending = true;
    });
    try {
      // The big button sends at once: for the default chosen in settings (myself unless an
      // institution was chosen there).
      await performSos(
        context,
        ref,
        organizationId: ref.read(sosReportAsProvider),
      );
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _tap() {
    if (_sending) return;
    if (_armed) {
      _send();
      return;
    }
    setState(() => _armed = true);
    _disarm?.cancel();
    _disarm = Timer(const Duration(seconds: 5), () {
      if (mounted) setState(() => _armed = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final label = _sending
        ? l10n.sosSending
        : _armed
        ? l10n.sosArmed
        : l10n.sosHint;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Semantics(
          button: true,
          label: '${l10n.sosButtonLabel}. $label',
          excludeSemantics: true,
          child: SizedBox.square(
            dimension: 200,
            child: Material(
              key: const Key('sos-button'),
              color: _armed ? const Color(0xFF8E0000) : sosRed,
              shape: CircleBorder(
                side: BorderSide(
                  color: _armed ? Colors.amber : Colors.transparent,
                  width: 8,
                ),
              ),
              elevation: 6,
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                onTap: _tap,
                onLongPress: _sending ? null : _send,
                child: Center(
                  child: _sending
                      ? const CircularProgressIndicator(color: Colors.white)
                      : Text(
                          l10n.sosButtonLabel,
                          style: theme.textTheme.displayMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          label,
          textAlign: TextAlign.center,
          style: theme.textTheme.titleMedium?.copyWith(
            color: _armed ? theme.colorScheme.error : null,
            fontWeight: _armed ? FontWeight.w700 : null,
          ),
        ),
      ],
    );
  }
}

/// SOS on the other main screens: tap opens a confirmation sheet, second tap sends.
class SosFab extends ConsumerWidget {
  const SosFab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return FloatingActionButton.extended(
      key: const Key('sos-fab'),
      heroTag: 'sos-fab',
      backgroundColor: sosRed,
      foregroundColor: Colors.white,
      tooltip: l10n.sosConfirmTitle,
      icon: const Icon(Icons.sos),
      label: Text(l10n.sosButtonLabel),
      onPressed: () => showSosConfirmSheet(context, ref),
    );
  }
}

Future<void> showSosConfirmSheet(BuildContext context, WidgetRef ref) async {
  final orgs = ref.read(activeOrgsProvider);
  var reportAs = ref.read(sosReportAsProvider);
  final confirmed = await showModalBottomSheet<bool>(
    context: context,
    showDragHandle: true,
    isScrollControlled: orgs.isNotEmpty,
    builder: (context) {
      final l10n = AppLocalizations.of(context);
      final theme = Theme.of(context);
      return SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(l10n.sosConfirmTitle, style: theme.textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(l10n.sosConfirmBody),
              if (orgs.isNotEmpty) ...[
                const SizedBox(height: 8),
                StatefulBuilder(
                  builder: (context, setState) => ReportAsSelector(
                    orgs: orgs,
                    value: reportAs,
                    onChanged: (orgId) => setState(() => reportAs = orgId),
                  ),
                ),
              ],
              const SizedBox(height: 16),
              FilledButton.icon(
                key: const Key('sos-confirm'),
                style: FilledButton.styleFrom(
                  backgroundColor: sosRed,
                  foregroundColor: Colors.white,
                  minimumSize: const Size.fromHeight(64),
                ),
                onPressed: () => Navigator.of(context).pop(true),
                icon: const Icon(Icons.sos),
                label: Text(l10n.sosConfirmAction),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: Text(l10n.actionCancel),
              ),
            ],
          ),
        ),
      );
    },
  );
  if (confirmed == true && context.mounted) {
    await performSos(context, ref, organizationId: reportAs);
  }
}
