import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/auth/phone_otp.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/brand.dart';
import '../../core/ui/components.dart';
import '../../core/ui/required_label.dart';
import '../../core/ui/sim_banner.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../welcome/welcome_scaffold.dart';
import 'login_actions.dart';

/// Phase A, addition 6: sign-in with a Tunisian mobile number and a 6-digit SMS code. Also offers
/// "continue as a guest" (anonymous reporting), the institution account and, for accounts created
/// before phase A, the e-mail sign-in in the browser.
///
/// [standalone]: opened from inside the app (an anonymous citizen signing in): a success pops
/// the screen with `true`.
class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({
    super.key,
    this.standalone = false,
    this.role = UserRole.citizen,
  });

  final bool standalone;

  /// Phase P5b (F-APP-12): an institution signing in to register goes on to the form.
  final UserRole role;

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  final _phone = TextEditingController();
  final _code = TextEditingController();
  String? _sentTo;
  bool _simulated = false;
  bool _busy = false;
  String? _error;
  int _resendIn = 0;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    _phone.dispose();
    _code.dispose();
    super.dispose();
  }

  void _startCountdown(Duration d) {
    _timer?.cancel();
    setState(() => _resendIn = d.inSeconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return t.cancel();
      setState(() => _resendIn = _resendIn > 0 ? _resendIn - 1 : 0);
      if (_resendIn == 0) t.cancel();
    });
  }

  String _message(AppLocalizations l10n, PhoneOtpException e) =>
      switch (e.error) {
        PhoneOtpError.invalidPhone => l10n.signInPhoneInvalid,
        PhoneOtpError.tooSoon => l10n.signInTooSoon,
        PhoneOtpError.limit => l10n.signInLimit,
        PhoneOtpError.smsUnavailable => l10n.signInSmsUnavailable,
        PhoneOtpError.wrongCode => l10n.signInWrongCode(e.triesLeft ?? 0),
        PhoneOtpError.expired => l10n.signInCodeExpired,
        PhoneOtpError.network => l10n.signInNetworkError,
        PhoneOtpError.unknown => l10n.loginFailed,
      };

  Future<void> _sendCode() async {
    final l10n = AppLocalizations.of(context);
    final phone = normalizeTunisianMobile(_phone.text);
    if (phone == null) {
      setState(() => _error = l10n.signInPhoneInvalid);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final sent = await ref
          .read(phoneOtpClientProvider)
          .requestCode(phone, ref.read(localeCodeProvider));
      if (!mounted) return;
      setState(() {
        _sentTo = phone;
        _simulated = sent.simulated;
      });
      _startCountdown(sent.resendAfter);
    } on PhoneOtpException catch (e) {
      if (mounted) setState(() => _error = _message(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    final l10n = AppLocalizations.of(context);
    final phone = _sentTo;
    if (phone == null || !RegExp(r'^\d{6}$').hasMatch(_code.text.trim())) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final session = await ref
          .read(phoneOtpClientProvider)
          .verify(phone, _code.text.trim());
      await ref
          .read(identityProvider.notifier)
          .signInWithSession(session, role: widget.role);
      ref.read(anonBlockedProvider.notifier).set(false);
      if (mounted && widget.role == UserRole.institution) {
        context.go(Routes.institutionRegister);
        return;
      }
      if (mounted && widget.standalone && context.canPop()) context.pop(true);
    } on PhoneOtpException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = _message(l10n, e);
        _code.clear();
        if (e.error == PhoneOtpError.expired) _sentTo = null;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _guest() async {
    await ref.read(identityProvider.notifier).useAnonymous();
    if (mounted && widget.standalone && context.canPop()) context.pop(false);
  }

  Future<void> _institution() async {
    await ref.read(identityProvider.notifier).chooseRole(UserRole.institution);
    if (mounted) context.go(Routes.onboardingInstitution);
  }

  Future<void> _email() async {
    await ref.read(identityProvider.notifier).chooseRole(UserRole.citizen);
    if (!mounted) return;
    final ok = await runBrowserLogin(context, ref);
    if (ok && mounted && widget.standalone && context.canPop()) {
      context.pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final identity = ref.watch(identityProvider);
    final codeStep = _sentTo != null;
    return WelcomeScaffold(
      title: l10n.signInTitle,
      showBack: widget.standalone,
      body: AbsorbPointer(
        absorbing: _busy,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_busy) const LinearProgressIndicator(),
            const Center(child: BrandLogo(size: 88)),
            const SizedBox(height: 12),
            Text(l10n.signInIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            if (!codeStep) ...[
              const RequiredNote(),
              TextField(
                key: const Key('signin-phone'),
                controller: _phone,
                keyboardType: TextInputType.phone,
                textDirection: TextDirection.ltr,
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'[0-9 ]')),
                  LengthLimitingTextInputFormatter(11),
                ],
                autofillHints: const [AutofillHints.telephoneNumberNational],
                decoration: InputDecoration(
                  label: RequiredLabel(l10n.signInPhoneLabel),
                  hintText: l10n.signInPhoneHint,
                  prefixText: '+216 ',
                  prefixIcon: const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('🇹🇳', style: TextStyle(fontSize: 20)),
                  ),
                ),
                onSubmitted: (_) => _sendCode(),
              ),
              const SizedBox(height: 12),
              FilledButton(
                key: const Key('signin-send'),
                onPressed: _sendCode,
                child: Text(l10n.signInSendCode),
              ),
            ] else ...[
              // SIMULATION: development SMS gateway; never shown with a real SMS provider.
              if (_simulated) SimBanner(text: l10n.simBanner),
              Text(
                l10n.signInCodeSentTo(_sentTo!),
                key: const Key('signin-sent-to'),
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('signin-code'),
                controller: _code,
                keyboardType: TextInputType.number,
                textDirection: TextDirection.ltr,
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall?.copyWith(
                  letterSpacing: 8,
                ),
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(6),
                ],
                autofillHints: const [AutofillHints.oneTimeCode],
                decoration: InputDecoration(
                  label: RequiredLabel(l10n.signInCodeLabel),
                ),
                onChanged: (v) {
                  if (v.length == 6) _verify();
                },
              ),
              const SizedBox(height: 12),
              FilledButton(
                key: const Key('signin-verify'),
                onPressed: _verify,
                child: Text(l10n.signInVerify),
              ),
              Row(
                children: [
                  TextButton(
                    key: const Key('signin-change-number'),
                    onPressed: () => setState(() {
                      _sentTo = null;
                      _error = null;
                      _code.clear();
                    }),
                    child: Text(l10n.signInChangeNumber),
                  ),
                  const Spacer(),
                  TextButton(
                    key: const Key('signin-resend'),
                    onPressed: _resendIn > 0 ? null : _sendCode,
                    child: Text(
                      _resendIn > 0
                          ? l10n.signInResendIn(_resendIn)
                          : l10n.signInResend,
                    ),
                  ),
                ],
              ),
            ],
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    key: const Key('signin-error'),
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ),
              ),
            const SizedBox(height: 8),
            Text(l10n.signInPrivacyNote, style: theme.textTheme.bodySmall),
            const Divider(height: 32),
            if (!identity.isAnonymous)
              NavCard(
                key: const Key('signin-guest'),
                icon: Icons.visibility_off_rounded,
                tone: Tone.slate,
                title: l10n.signInGuest,
                subtitle: l10n.signInGuestDesc,
                onTap: _guest,
              ),
            if (!widget.standalone)
              NavCard(
                key: const Key('signin-institution'),
                icon: Icons.apartment_rounded,
                tone: Tone.navy,
                title: l10n.signInInstitution,
                subtitle: l10n.signInInstitutionDesc,
                onTap: _institution,
              ),
            NavCard(
              key: const Key('signin-email'),
              icon: Icons.alternate_email_rounded,
              tone: Tone.navy,
              title: l10n.signInEmail,
              onTap: _email,
            ),
          ],
        ),
      ),
    );
  }
}
