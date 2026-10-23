import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/required_label.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../profile/profile_screen.dart' show gouvernoratsProvider;
import 'contact_models.dart';

/// The caller's own requests (`GET /api/v1/me/contact`).
final myContactProvider = FutureProvider.autoDispose<List<MyContactRequest>>(
  (ref) => ref.watch(apiProvider).myContactRequests(),
  retry: (_, _) => null,
);

String contactKindLabel(AppLocalizations l10n, ContactKind k) => switch (k) {
  ContactKind.accessInfo => l10n.contactKindAccessInfo,
  ContactKind.hazard => l10n.contactKindHazard,
  ContactKind.question => l10n.contactKindQuestion,
  ContactKind.suggestion => l10n.contactKindSuggestion,
  ContactKind.appProblem => l10n.contactKindAppProblem,
  ContactKind.partnership => l10n.contactKindPartnership,
};

String contactStatusLabel(AppLocalizations l10n, ContactStatus s) =>
    switch (s) {
      ContactStatus.received => l10n.contactStatusReceived,
      ContactStatus.inProgress => l10n.contactStatusInProgress,
      ContactStatus.answered => l10n.contactStatusAnswered,
      ContactStatus.closed => l10n.contactStatusClosed,
      ContactStatus.rejected => l10n.contactStatusRejected,
    };

/// Always on top of the form: this is not an emergency channel.
class _EmergencyBanner extends ConsumerWidget {
  const _EmergencyBanner();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Card(
      key: const Key('contact-emergency-banner'),
      color: theme.colorScheme.errorContainer,
      child: ListTile(
        leading: Icon(Icons.warning_amber, color: theme.colorScheme.error),
        title: Text(
          l10n.contactEmergencyBanner,
          style: TextStyle(color: theme.colorScheme.onErrorContainer),
        ),
        trailing: IconButton.filled(
          key: const Key('contact-call-198'),
          tooltip: l10n.guideCall198,
          style: IconButton.styleFrom(backgroundColor: theme.colorScheme.error),
          icon: const Icon(Icons.call),
          onPressed: () =>
              ref.read(dialerProvider)(emergencyNumbers.first.telUri),
        ),
      ),
    );
  }
}

/// "Contact us" form (phase B1): kind, gouvernorat, subject, message and optional contact
/// details; the request number is shown at once.
class ContactScreen extends ConsumerStatefulWidget {
  const ContactScreen({super.key});

  @override
  ConsumerState<ContactScreen> createState() => _ContactScreenState();
}

class _ContactScreenState extends ConsumerState<ContactScreen> {
  final _form = GlobalKey<FormState>();
  final _subject = TextEditingController();
  final _message = TextEditingController();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();
  ContactKind _kind = ContactKind.question;
  int? _gouvernorat;
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    for (final c in [_subject, _message, _name, _phone, _email]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _send() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    final l10n = AppLocalizations.of(context);
    setState(() {
      _sending = true;
      _error = null;
    });
    String? opt(TextEditingController c) =>
        c.text.trim().isEmpty ? null : c.text.trim();
    try {
      final phone = opt(_phone);
      final sent = await ref.read(apiProvider).sendContact({
        'kind': _kind.wire,
        'subject': _subject.text.trim(),
        'message': _message.text.trim(),
        'gouvernorat_code': _gouvernorat,
        'name': opt(_name),
        'phone': phone == null ? null : '+216$phone',
        'email': opt(_email),
        'locale': ref.read(localeCodeProvider),
        'platform': defaultTargetPlatform == TargetPlatform.iOS
            ? 'ios'
            : 'android',
      });
      ref.invalidate(myContactProvider);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          key: const Key('contact-sent'),
          title: Text(l10n.contactSentTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.contactSentBody),
              const SizedBox(height: 8),
              SelectableText(
                sent.number,
                textDirection: TextDirection.ltr,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () =>
                  Clipboard.setData(ClipboardData(text: sent.number)),
              child: Text(l10n.nearestCopy),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.contactSeeMine),
            ),
          ],
        ),
      );
      if (mounted) context.pushReplacement(Routes.contactMine);
    } on Object catch (e) {
      if (mounted) setState(() => _error = errorMessageFor(l10n, e));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final gouvernorats = ref.watch(gouvernoratsProvider);
    String? length(String? v, int min, int max, {bool required = true}) {
      final t = v?.trim() ?? '';
      if (t.isEmpty) return required ? l10n.validationRequired : null;
      return t.length < min || t.length > max
          ? l10n.contactLength(min, max)
          : null;
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.contactTitle),
        actions: [
          IconButton(
            key: const Key('contact-mine'),
            tooltip: l10n.contactMineTitle,
            icon: const Icon(Icons.inbox),
            onPressed: () => context.push(Routes.contactMine),
          ),
          const StandardAppBarActions(),
        ],
      ),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const _EmergencyBanner(),
            const SizedBox(height: 8),
            Text(l10n.contactIntro),
            const SizedBox(height: 12),
            DropdownButtonFormField<ContactKind>(
              key: const Key('contact-kind'),
              initialValue: _kind,
              isExpanded: true,
              decoration: InputDecoration(
                label: RequiredLabel(l10n.contactKind),
              ),
              items: [
                for (final k in ContactKind.values)
                  DropdownMenuItem(
                    value: k,
                    child: Text(contactKindLabel(l10n, k)),
                  ),
              ],
              onChanged: (k) => setState(() => _kind = k ?? _kind),
            ),
            if (_kind == ContactKind.accessInfo)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  l10n.contactAccessInfoHint,
                  key: const Key('contact-access-info-hint'),
                ),
              ),
            const SizedBox(height: 12),
            gouvernorats.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, _) => Text(l10n.geoLoadFailed),
              data: (list) => DropdownButtonFormField<int?>(
                key: const Key('contact-gouvernorat'),
                initialValue: _gouvernorat,
                isExpanded: true,
                decoration: InputDecoration(
                  label: ContactRules.gouvernoratRequired(_kind)
                      ? RequiredLabel(l10n.profileGouvernorat)
                      : Text(l10n.profileGouvernorat),
                ),
                items: [
                  DropdownMenuItem<int?>(
                    child: Text(l10n.contactNoGouvernorat),
                  ),
                  for (final g in list)
                    DropdownMenuItem<int?>(value: g.code, child: Text(g.name)),
                ],
                validator: (v) =>
                    ContactRules.gouvernoratRequired(_kind) && v == null
                    ? l10n.validationRequired
                    : null,
                onChanged: (v) => setState(() => _gouvernorat = v),
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              key: const Key('contact-subject'),
              controller: _subject,
              maxLength: ContactRules.subjectMax,
              decoration: InputDecoration(
                label: RequiredLabel(l10n.contactSubject),
              ),
              validator: (v) =>
                  length(v, ContactRules.subjectMin, ContactRules.subjectMax),
            ),
            TextFormField(
              key: const Key('contact-message'),
              controller: _message,
              minLines: 4,
              maxLines: 10,
              maxLength: ContactRules.messageMax,
              decoration: InputDecoration(
                label: RequiredLabel(l10n.contactMessage),
                alignLabelWithHint: true,
              ),
              validator: (v) =>
                  length(v, ContactRules.messageMin, ContactRules.messageMax),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.contactDetailsHint,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            TextFormField(
              key: const Key('contact-name'),
              controller: _name,
              maxLength: ContactRules.nameMax,
              autofillHints: const [AutofillHints.name],
              decoration: InputDecoration(
                label: ContactRules.nameRequired(_kind)
                    ? RequiredLabel(l10n.contactName)
                    : Text(l10n.contactName),
              ),
              validator: (v) => length(
                v,
                ContactRules.nameMin,
                ContactRules.nameMax,
                required: ContactRules.nameRequired(_kind),
              ),
            ),
            TextFormField(
              key: const Key('contact-phone'),
              controller: _phone,
              keyboardType: TextInputType.phone,
              textDirection: TextDirection.ltr,
              inputFormatters: [
                FilteringTextInputFormatter.digitsOnly,
                LengthLimitingTextInputFormatter(8),
              ],
              decoration: InputDecoration(
                labelText: l10n.profilePhone,
                prefixText: '+216 ',
              ),
              validator: (v) {
                final t = v?.trim() ?? '';
                return t.isEmpty || ContactRules.localPhone.hasMatch(t)
                    ? null
                    : l10n.validationPhone;
              },
            ),
            TextFormField(
              key: const Key('contact-email'),
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              textDirection: TextDirection.ltr,
              decoration: InputDecoration(labelText: l10n.contactEmail),
              validator: (v) {
                final t = v?.trim() ?? '';
                return t.isEmpty || ContactRules.email.hasMatch(t)
                    ? null
                    : l10n.contactEmailInvalid;
              },
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  _error!,
                  key: const Key('contact-error'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('contact-send'),
              onPressed: _sending ? null : _send,
              icon: const Icon(Icons.send),
              label: Text(l10n.contactSend),
            ),
          ],
        ),
      ),
    );
  }
}

/// "My requests": number, status and the Office's answer.
class MyContactScreen extends ConsumerWidget {
  const MyContactScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final mine = ref.watch(myContactProvider);
    final date = DateFormat.yMMMd(lang);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.contactMineTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(myContactProvider.future),
        child: mine.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(24),
            children: [Text(errorMessageFor(l10n, e))],
          ),
          data: (items) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              if (items.isEmpty) Text(l10n.contactMineEmpty),
              for (final r in items)
                Card(
                  key: Key('contact-${r.number}'),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                r.number,
                                textDirection: TextDirection.ltr,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                            ),
                            Chip(
                              label: Text(contactStatusLabel(l10n, r.status)),
                            ),
                          ],
                        ),
                        Text(
                          '${contactKindLabel(l10n, r.kind)} · '
                          '${date.format(r.createdAt.toLocal())}',
                        ),
                        if (r.dueAt != null &&
                            (r.status == ContactStatus.received ||
                                r.status == ContactStatus.inProgress))
                          Text(
                            l10n.contactDue(date.format(r.dueAt!.toLocal())),
                          ),
                        const SizedBox(height: 8),
                        Text(
                          r.subject,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        if (r.answer != null) ...[
                          const SizedBox(height: 8),
                          Text(
                            r.status == ContactStatus.rejected
                                ? l10n.contactRejectReason
                                : l10n.contactAnswer,
                            style: Theme.of(context).textTheme.labelLarge,
                          ),
                          Text(r.answer!, key: Key('answer-${r.number}')),
                        ],
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
