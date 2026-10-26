import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/email_status.dart';
import '../../core/http/error_messages.dart';
import '../../core/ui/components.dart';
import '../../core/ui/required_label.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';

/// The work e-mail of the signed-in account (phase P5b, F-APP-12).
final myEmailProvider = FutureProvider.autoDispose<EmailStatus>(
  (ref) => ref.read(apiProvider).myEmail(),
);

final _email = RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$');

/// Registering an institution needs a proven e-mail. An account signed in with a phone number
/// gives its work address here and the 6-digit code sent to it; then the form opens.
class EmailConfirmPanel extends ConsumerStatefulWidget {
  const EmailConfirmPanel({super.key, this.initial});

  final String? initial;

  @override
  ConsumerState<EmailConfirmPanel> createState() => _EmailConfirmPanelState();
}

class _EmailConfirmPanelState extends ConsumerState<EmailConfirmPanel> {
  late final _address = TextEditingController(text: widget.initial ?? '');
  final _code = TextEditingController();
  String? _sentTo;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _address.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() step) async {
    final l10n = AppLocalizations.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await step();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    final address = _address.text.trim().toLowerCase();
    if (!_email.hasMatch(address)) {
      setState(() => _error = l10n.orgInvalidEmail);
      return;
    }
    final locale = Localizations.localeOf(context).languageCode;
    await _run(() async {
      await ref.read(apiProvider).sendEmailCode(address, locale);
      if (mounted) {
        setState(() {
          _sentTo = address;
          _code.clear();
        });
      }
    });
  }

  Future<void> _verify() async {
    final code = _code.text.trim();
    if (!RegExp(r'^\d{6}$').hasMatch(code)) {
      setState(() => _error = AppLocalizations.of(context).emailCodeInvalid);
      return;
    }
    await _run(() async {
      await ref.read(apiProvider).verifyEmailCode(code);
      ref.invalidate(myEmailProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final sentTo = _sentTo;
    return ListView(
      key: const Key('email-confirm'),
      padding: const EdgeInsets.all(16),
      children: [
        const Center(
          child: IconTile(
            Icons.mark_email_read_rounded,
            tone: Tone.navy,
            size: 64,
          ),
        ),
        const SizedBox(height: 16),
        Semantics(
          header: true,
          child: Text(
            l10n.emailConfirmTitle,
            style: theme.textTheme.titleLarge,
          ),
        ),
        const SizedBox(height: 8),
        Text(l10n.emailConfirmBody, style: theme.textTheme.bodyLarge),
        const SizedBox(height: 16),
        TextField(
          key: const Key('email-address'),
          controller: _address,
          enabled: sentTo == null && !_busy,
          keyboardType: TextInputType.emailAddress,
          autocorrect: false,
          decoration: InputDecoration(label: RequiredLabel(l10n.emailField)),
        ),
        const SizedBox(height: 12),
        if (sentTo == null)
          FilledButton.icon(
            key: const Key('email-send-code'),
            onPressed: _busy ? null : _send,
            icon: const Icon(Icons.send_rounded),
            label: Text(l10n.emailSendCode),
          )
        else ...[
          Text(l10n.emailCodeSent(sentTo), key: const Key('email-code-sent')),
          const SizedBox(height: 12),
          TextField(
            key: const Key('email-code'),
            controller: _code,
            enabled: !_busy,
            keyboardType: TextInputType.number,
            maxLength: 6,
            decoration: InputDecoration(
              label: RequiredLabel(l10n.emailCodeField),
            ),
          ),
          FilledButton.icon(
            key: const Key('email-verify'),
            onPressed: _busy ? null : _verify,
            icon: const Icon(Icons.check_rounded),
            label: Text(l10n.emailVerify),
          ),
          const SizedBox(height: 8),
          TextButton(
            key: const Key('email-change'),
            onPressed: _busy
                ? null
                : () => setState(() {
                    _sentTo = null;
                    _error = null;
                  }),
            child: Text(l10n.emailChange),
          ),
        ],
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              _error!,
              key: const Key('email-error'),
              style: TextStyle(color: theme.colorScheme.error),
            ),
          ),
      ],
    );
  }
}
