import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../charter/charter_controller.dart';

final gouvernoratsProvider = FutureProvider.autoDispose<List<Gouvernorat>>(
  (ref) => ref.watch(apiProvider).gouvernorats(ref.watch(localeCodeProvider)),
);

final delegationsProvider = FutureProvider.autoDispose
    .family<List<Delegation>, int>(
      (ref, code) => ref
          .watch(apiProvider)
          .delegations(code, ref.watch(localeCodeProvider)),
    );

final profileProvider = FutureProvider.autoDispose<Profile>(
  (ref) => ref.watch(apiProvider).getProfile(),
);

/// Phone and CIN validation (Tunisia): CIN = 8 digits, phone = +216 followed by 8 digits.
abstract final class ProfileRules {
  static final cin = RegExp(r'^\d{8}$');
  static final localPhone = RegExp(r'^\d{8}$');
  static const phonePrefix = '+216';

  static String? localPart(String? phone) =>
      phone != null && phone.startsWith(phonePrefix)
      ? phone.substring(phonePrefix.length)
      : phone;
}

/// "Complete your profile" after the first login (used later for verified reports). Saved with
/// `PUT /api/v1/me/profile`.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _form = GlobalKey<FormState>();
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _cin = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();
  int? _gouvernorat;
  int? _delegation;
  String? _cinLast4;
  bool _prefilled = false;
  bool _saving = false;

  @override
  void dispose() {
    for (final c in [_first, _last, _cin, _phone, _address]) {
      c.dispose();
    }
    super.dispose();
  }

  void _prefill(Profile p) {
    if (_prefilled) return;
    _prefilled = true;
    _first.text = p.firstName ?? '';
    _last.text = p.lastName ?? '';
    _phone.text = ProfileRules.localPart(p.phone) ?? '';
    _address.text = p.address ?? '';
    _gouvernorat = p.gouvernoratCode;
    _delegation = p.delegationId;
    _cinLast4 = p.cinLast4;
  }

  Future<void> _leave() async {
    await ref.read(profilePromptedProvider.notifier).markPrompted();
    if (!mounted) return;
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(Routes.home);
    }
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _saving = true);
    try {
      final address = _address.text.trim();
      await ref
          .read(apiProvider)
          .putProfile(
            ProfileInput(
              firstName: _first.text.trim(),
              lastName: _last.text.trim(),
              cin: _cin.text.trim(),
              phone: '${ProfileRules.phonePrefix}${_phone.text.trim()}',
              gouvernoratCode: _gouvernorat!,
              delegationId: _delegation!,
              address: address.isEmpty ? null : address,
              locale: ref.read(localeCodeProvider),
            ),
          );
      messenger.showSnackBar(SnackBar(content: Text(l10n.profileSaved)));
      ref.invalidate(profileProvider);
      await _leave();
    } on Object catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(errorMessageFor(l10n, e))));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _required(String? v) => (v == null || v.trim().isEmpty)
      ? AppLocalizations.of(context).validationRequired
      : null;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final profile = ref.watch(profileProvider);
    profile.whenData(_prefill);
    final gouvernorats = ref.watch(gouvernoratsProvider);
    final delegations = _gouvernorat == null
        ? null
        : ref.watch(delegationsProvider(_gouvernorat!));

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.profileTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(l10n.profileIntro),
              if (profile.isLoading) const LinearProgressIndicator(),
              const SizedBox(height: 16),
              TextFormField(
                controller: _first,
                textCapitalization: TextCapitalization.words,
                autofillHints: const [AutofillHints.givenName],
                decoration: InputDecoration(labelText: l10n.profileFirstName),
                validator: _required,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _last,
                textCapitalization: TextCapitalization.words,
                autofillHints: const [AutofillHints.familyName],
                decoration: InputDecoration(labelText: l10n.profileLastName),
                validator: _required,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _cin,
                keyboardType: TextInputType.number,
                textDirection: TextDirection.ltr,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(8),
                ],
                decoration: InputDecoration(
                  labelText: l10n.profileCin,
                  helperText: _cinLast4 == null
                      ? l10n.profileCinHint
                      : l10n.profileCinStored(_cinLast4!),
                ),
                validator: (v) => ProfileRules.cin.hasMatch(v?.trim() ?? '')
                    ? null
                    : l10n.validationCin,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                textDirection: TextDirection.ltr,
                autofillHints: const [AutofillHints.telephoneNumberNational],
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(8),
                ],
                decoration: InputDecoration(
                  labelText: l10n.profilePhone,
                  prefixText: '${ProfileRules.phonePrefix} ',
                ),
                validator: (v) =>
                    ProfileRules.localPhone.hasMatch(v?.trim() ?? '')
                    ? null
                    : l10n.validationPhone,
              ),
              const SizedBox(height: 12),
              gouvernorats.when(
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => _RetryRow(
                  message: l10n.geoLoadFailed,
                  onRetry: () => ref.invalidate(gouvernoratsProvider),
                ),
                data: (list) => DropdownButtonFormField<int>(
                  key: const Key('profile-gouvernorat'),
                  initialValue: list.any((g) => g.code == _gouvernorat)
                      ? _gouvernorat
                      : null,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: l10n.profileGouvernorat,
                  ),
                  items: [
                    for (final g in list)
                      DropdownMenuItem(value: g.code, child: Text(g.name)),
                  ],
                  onChanged: (v) => setState(() {
                    _gouvernorat = v;
                    _delegation = null;
                  }),
                  validator: (v) => v == null ? l10n.validationRequired : null,
                ),
              ),
              const SizedBox(height: 12),
              if (delegations != null)
                delegations.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => _RetryRow(
                    message: l10n.geoLoadFailed,
                    onRetry: () =>
                        ref.invalidate(delegationsProvider(_gouvernorat!)),
                  ),
                  data: (list) => DropdownButtonFormField<int>(
                    key: ValueKey('profile-delegation-$_gouvernorat'),
                    initialValue: list.any((d) => d.id == _delegation)
                        ? _delegation
                        : null,
                    isExpanded: true,
                    decoration: InputDecoration(
                      labelText: l10n.profileDelegation,
                    ),
                    items: [
                      for (final d in list)
                        DropdownMenuItem(value: d.id, child: Text(d.name)),
                    ],
                    onChanged: (v) => setState(() => _delegation = v),
                    validator: (v) =>
                        v == null ? l10n.validationRequired : null,
                  ),
                ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _address,
                maxLength: 300,
                autofillHints: const [AutofillHints.fullStreetAddress],
                decoration: InputDecoration(labelText: l10n.profileAddress),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _saving ? null : _save,
                child: Text(l10n.actionSave),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: _saving ? null : _leave,
                child: Text(l10n.actionLater),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RetryRow extends StatelessWidget {
  const _RetryRow({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(child: Text(message)),
      TextButton(
        onPressed: onRetry,
        child: Text(AppLocalizations.of(context).actionRetry),
      ),
    ],
  );
}
