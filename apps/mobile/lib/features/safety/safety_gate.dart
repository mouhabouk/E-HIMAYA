import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/platform/device_services.dart';
import '../../core/routing/app_router.dart';
import '../../core/storage/app_prefs.dart';
import '../../l10n/app_localizations.dart';
import 'live_share_screen.dart';
import 'safety_providers.dart';

/// Phase B2, around the main screens: opens the screen of an app shortcut (long press of the
/// icon), and keeps a live location share or the location history going after a restart.
class SafetyGate extends ConsumerStatefulWidget {
  const SafetyGate({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<SafetyGate> createState() => _SafetyGateState();
}

class _SafetyGateState extends ConsumerState<SafetyGate>
    with WidgetsBindingObserver {
  bool _started = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    final l10n = AppLocalizations.of(context);
    if (ref.read(liveShareProvider) != null) {
      ref.read(liveShareProvider.notifier).resume(liveNotice(l10n));
    }
    if (ref.read(appPrefsProvider).locationHistoryOn &&
        ref.read(identityProvider).isRegistered) {
      ref.read(locationHistoryRecorderProvider).start();
    }
    unawaited(_shortcut());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(_shortcut());
  }

  Future<void> _shortcut() async {
    final name = await ref.read(deviceServicesProvider).takeShortcut();
    if (!mounted || name == null) return;
    final route = switch (name) {
      'sos_message' => Routes.safetySend,
      'report' => Routes.newReport,
      _ => null,
    };
    if (route != null) unawaited(GoRouter.of(context).push(route));
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
