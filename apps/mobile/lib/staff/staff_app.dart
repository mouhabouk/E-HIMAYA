import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/settings/settings_controller.dart';
import '../core/ui/brand.dart';
import '../core/ui/components.dart';
import '../core/ui/theme.dart';
import '../core/ui/tokens.dart';
import '../l10n/app_localizations.dart';
import 'prevention/visits_screen.dart';
import 'screens/missions_screen.dart';
import 'screens/shift_screen.dart';
import 'staff_chrome.dart';
import 'staff_config.dart';
import 'staff_controller.dart';

/// Opens a link in the phone's browser (the sign-in page). Overridden in tests.
final staffLauncherProvider = Provider<Future<bool> Function(Uri)>(
  (ref) =>
      (uri) => launchUrl(uri, mode: LaunchMode.externalApplication),
);

/// Staff app of the civil protection's team leaders (phase P4a, F-STF-01..05) and of the
/// prevention inspectors (phase P4c, F-STF-06).
class StaffApp extends ConsumerStatefulWidget {
  const StaffApp({super.key, this.clock = DateTime.now});

  final DateTime Function() clock;

  @override
  ConsumerState<StaffApp> createState() => _StaffAppState();
}

class _StaffAppState extends ConsumerState<StaffApp>
    with WidgetsBindingObserver {
  DateTime? _hiddenAt;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.paused || s == AppLifecycleState.hidden) {
      _hiddenAt ??= widget.clock();
    } else if (s == AppLifecycleState.resumed) {
      final since = _hiddenAt;
      _hiddenAt = null;
      final c = ref.read(staffControllerProvider.notifier);
      if (since != null &&
          widget.clock().difference(since) >= StaffConfig.lockAfter) {
        c.lock();
      } else {
        unawaited(c.poll());
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);
    return MaterialApp(
      onGenerateTitle: (context) => AppLocalizations.of(context).staffAppTitle,
      debugShowCheckedModeBanner: false,
      locale: settings.locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      theme: buildTheme(Brightness.light, settings.palette),
      darkTheme: buildTheme(Brightness.dark, settings.palette),
      themeMode: settings.themeMode,
      home: const StaffHome(),
    );
  }
}

class StaffHome extends ConsumerWidget {
  const StaffHome({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final phase = ref.watch(staffControllerProvider.select((s) => s.phase));
    return switch (phase) {
      StaffPhase.loading => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      StaffPhase.signedOut || StaffPhase.signingIn => const SignInScreen(),
      StaffPhase.setPin => const PinScreen(create: true),
      StaffPhase.locked => const PinScreen(create: false),
      StaffPhase.noShift => const ShiftScreen(),
      StaffPhase.onShift => const MissionsScreen(),
      StaffPhase.prevention => const PreventionVisitsScreen(home: true),
    };
  }
}

/// F-STF-01: the leader signs in on the phone's browser with password and second factor; the
/// app only shows the code and waits.
class SignInScreen extends ConsumerWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = ref.read(staffControllerProvider.notifier);
    final code = s.phase == StaffPhase.signingIn ? s.code : null;
    final reason = switch (s.reason) {
      SignOutReason.wiped => l10n.staffWiped,
      SignOutReason.pinFailures => l10n.staffPinWiped,
      SignOutReason.refused => l10n.staffSignInRefused,
      SignOutReason.expired => l10n.staffSignInExpired,
      SignOutReason.none => s.offline ? l10n.staffOffline : null,
    };
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffAppTitle),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Center(child: BrandLogo(size: 72)),
          const SizedBox(height: 16),
          Text(
            l10n.staffSignInTitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(l10n.staffSignInBody, textAlign: TextAlign.center),
          if (reason != null) ...[
            const SizedBox(height: 16),
            AppCard(
              key: const Key('staff-signout-reason'),
              color: Tone.amber.colors(context).tint,
              child: Text(reason),
            ),
          ],
          const SizedBox(height: 24),
          if (code == null)
            ToneButton(
              action: BarAction(
                key: const Key('staff-sign-in'),
                label: l10n.staffSignIn,
                icon: Icons.login,
                tone: Tone.navy,
                onPressed: s.busy ? null : () => unawaited(c.signIn()),
              ),
            )
          else ...[
            Text(l10n.staffCodeIntro, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            Semantics(
              label: l10n.staffCodeSemantics(code.userCode.split('').join(' ')),
              excludeSemantics: true,
              child: SelectableText(
                code.userCode,
                key: const Key('staff-user-code'),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.displaySmall
                    ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: 4),
              ),
            ),
            const SizedBox(height: 16),
            ToneButton(
              action: BarAction(
                key: const Key('staff-open-browser'),
                label: l10n.staffOpenSignInPage,
                icon: Icons.open_in_browser,
                tone: Tone.navy,
                onPressed: () => unawaited(
                  ref.read(staffLauncherProvider)(
                    Uri.parse(
                      code.verificationUriComplete ?? code.verificationUri,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 10),
                Flexible(child: Text(l10n.staffWaitingSignIn)),
              ],
            ),
            const SizedBox(height: 8),
            TextButton(
              key: const Key('staff-cancel-sign-in'),
              onPressed: c.cancelSignIn,
              child: Text(l10n.actionCancel),
            ),
          ],
        ],
      ),
    );
  }
}

/// Six-digit PIN: chosen after the sign-in, asked again after five minutes in the background.
/// Five wrong PINs in a row erase the phone.
class PinScreen extends ConsumerStatefulWidget {
  const PinScreen({super.key, required this.create});

  final bool create;

  @override
  ConsumerState<PinScreen> createState() => _PinScreenState();
}

class _PinScreenState extends ConsumerState<PinScreen> {
  final _pin = TextEditingController();
  String? _first;
  bool _mismatch = false;

  @override
  void dispose() {
    _pin.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final pin = _pin.text;
    if (pin.length != 6) return;
    final c = ref.read(staffControllerProvider.notifier);
    _pin.clear();
    if (!widget.create) {
      await c.unlock(pin);
      return;
    }
    if (_first == null) {
      setState(() {
        _first = pin;
        _mismatch = false;
      });
    } else if (_first == pin) {
      await c.setPin(pin);
    } else {
      setState(() {
        _first = null;
        _mismatch = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final title = widget.create
        ? (_first == null ? l10n.staffPinCreate : l10n.staffPinConfirm)
        : l10n.staffPinEnter;
    final error = _mismatch
        ? l10n.staffPinMismatch
        : (!widget.create && s.pinError)
        ? l10n.staffPinWrong(s.pinTriesLeft)
        : null;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffAppTitle),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const SizedBox(height: 12),
          const Center(child: IconTile(Icons.lock, tone: Tone.navy, size: 64)),
          const SizedBox(height: 16),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (widget.create) ...[
            const SizedBox(height: 8),
            Text(l10n.staffPinHelp, textAlign: TextAlign.center),
          ],
          const SizedBox(height: 20),
          TextField(
            key: const Key('staff-pin'),
            controller: _pin,
            autofocus: true,
            obscureText: true,
            maxLength: 6,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            style: const TextStyle(fontSize: 28, letterSpacing: 12),
            decoration: InputDecoration(
              labelText: l10n.staffPinLabel,
              errorText: error,
              counterText: '',
            ),
            onChanged: (v) {
              if (v.length == 6) unawaited(_submit());
            },
          ),
          if (!widget.create) ...[
            const SizedBox(height: 24),
            TextButton(
              key: const Key('staff-sign-out'),
              onPressed: () => unawaited(
                ref.read(staffControllerProvider.notifier).signOut(),
              ),
              child: Text(l10n.staffSignOut),
            ),
          ],
        ],
      ),
    );
  }
}
