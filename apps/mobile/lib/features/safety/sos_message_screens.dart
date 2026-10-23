import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/db/app_database.dart';
import '../../core/routing/app_router.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../institution/institution_providers.dart';
import 'safety_models.dart';
import 'safety_providers.dart';

/// The labels of the message in the user's language.
SosLabels sosLabels(AppLocalizations l10n) => SosLabels(
  position: l10n.sosLabelPosition,
  accuracy: l10n.sosLabelAccuracy,
  time: l10n.sosLabelTime,
  battery: l10n.sosLabelBattery,
  noPosition: l10n.sosLabelNoPosition,
);

/// The user's text, or the default one of the language.
String sosTemplateOf(WidgetRef ref, AppLocalizations l10n) {
  final saved = ref.read(appPrefsProvider).sosTemplate;
  return saved == null || saved.trim().isEmpty
      ? l10n.sosDefaultTemplate
      : saved;
}

/// Addition 5: the text of the SOS message and the 5-second cancel window.
class SosMessageSettingsScreen extends ConsumerStatefulWidget {
  const SosMessageSettingsScreen({super.key});

  @override
  ConsumerState<SosMessageSettingsScreen> createState() =>
      _SosMessageSettingsState();
}

class _SosMessageSettingsState extends ConsumerState<SosMessageSettingsScreen> {
  late final TextEditingController _text;
  late bool _cancelWindow;

  @override
  void initState() {
    super.initState();
    final prefs = ref.read(appPrefsProvider);
    _text = TextEditingController(text: prefs.sosTemplate);
    _cancelWindow = prefs.sosCancelWindow;
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final prefs = ref.read(appPrefsProvider);
    final t = _text.text.trim();
    await prefs.setSosTemplate(t.isEmpty ? null : t);
    await prefs.setSosCancelWindow(_cancelWindow);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppLocalizations.of(context).safetySaved)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final preview = sosMessageText(
      template: _text.text.trim().isEmpty
          ? l10n.sosDefaultTemplate
          : _text.text,
      labels: sosLabels(l10n),
      at: DateTime.now(),
      position: null,
    );
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyMessageTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              key: const Key('sos-template'),
              controller: _text,
              maxLines: 4,
              minLines: 2,
              maxLength: SafetyRules.messageMax,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                labelText: l10n.safetyMessageText,
                hintText: l10n.sosDefaultTemplate,
                alignLabelWithHint: true,
              ),
            ),
            Text(l10n.safetyMessageAdded, style: theme.textTheme.bodySmall),
            const SizedBox(height: 8),
            SwitchListTile(
              key: const Key('sos-cancel-window'),
              contentPadding: EdgeInsets.zero,
              value: _cancelWindow,
              onChanged: (v) => setState(() => _cancelWindow = v),
              title: Text(l10n.safetyCancelWindow),
              subtitle: Text(l10n.safetyCancelWindowHint),
            ),
            const SizedBox(height: 8),
            Text(l10n.safetyPreview, style: theme.textTheme.titleSmall),
            const SizedBox(height: 4),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(preview, key: const Key('sos-preview')),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('sos-template-save'),
              onPressed: _save,
              icon: const Icon(Icons.save),
              label: Text(l10n.actionSave),
            ),
          ],
        ),
      ),
    );
  }
}

enum _Phase { ready, countdown, sending, done }

/// Sends the SOS message: a choice of recipients (everyone or one group), an optional 5-second
/// window to cancel, then the in-app alert and the SMS app; WhatsApp afterwards.
class SosSendScreen extends ConsumerStatefulWidget {
  const SosSendScreen({super.key});

  @override
  ConsumerState<SosSendScreen> createState() => _SosSendScreenState();
}

class _SosSendScreenState extends ConsumerState<SosSendScreen> {
  static const window = 5;

  _Phase _phase = _Phase.ready;
  int? _group;
  int _left = window;
  Timer? _tick;
  SosSendResult? _result;

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  void _press() {
    if (!ref.read(appPrefsProvider).sosCancelWindow) {
      unawaited(_send());
      return;
    }
    setState(() {
      _phase = _Phase.countdown;
      _left = window;
    });
    _tick = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return t.cancel();
      if (_left <= 1) {
        t.cancel();
        unawaited(_send());
      } else {
        setState(() => _left--);
      }
    });
  }

  Future<void> _cancel() async {
    _tick?.cancel();
    setState(() => _phase = _Phase.ready);
    await ref.read(sosMessageSenderProvider).recordCancelled();
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _phase = _Phase.sending);
    final result = await ref
        .read(sosMessageSenderProvider)
        .send(
          template: sosTemplateOf(ref, l10n),
          labels: sosLabels(l10n),
          groupId: _group,
        );
    if (!mounted) return;
    setState(() {
      _result = result;
      _phase = _Phase.done;
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final contacts = ref.watch(emergencyContactsProvider).value ?? const [];
    final groups = ref.watch(contactGroupsProvider).value ?? const [];
    final links = ref.watch(safetyLinksProvider).value ?? const [];
    final registered = ref.watch(identityProvider).isRegistered;
    final civil = emergencyNumbers.first;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetySendSos),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            ...switch (_phase) {
              _Phase.ready => _ready(
                l10n,
                contacts.length,
                links.length,
                groups,
                registered,
              ),
              _Phase.countdown => _countdown(l10n),
              _Phase.sending => [
                const SizedBox(height: 48),
                const Center(child: CircularProgressIndicator()),
                const SizedBox(height: 16),
                Text(l10n.safetySending, textAlign: TextAlign.center),
              ],
              _Phase.done => _done(l10n, _result!, contacts),
            },
            const SizedBox(height: 24),
            OutlinedButton.icon(
              key: const Key('sos-call-198'),
              style: OutlinedButton.styleFrom(
                foregroundColor: sosRed,
                minimumSize: const Size.fromHeight(52),
              ),
              onPressed: () => ref.read(dialerProvider)(civil.telUri),
              icon: const Icon(Icons.phone),
              label: Text(l10n.homeCall198),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _ready(
    AppLocalizations l10n,
    int contacts,
    int links,
    List<ContactGroup> groups,
    bool registered,
  ) {
    final theme = Theme.of(context);
    final nobody = contacts == 0 && links == 0;
    return [
      Text(l10n.safetySendIntro, style: theme.textTheme.bodyLarge),
      const SizedBox(height: 12),
      if (nobody) ...[
        Card(
          color: theme.colorScheme.errorContainer,
          child: ListTile(
            key: const Key('sos-no-contacts'),
            title: Text(l10n.safetyNoContacts),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push(Routes.safetyContacts),
          ),
        ),
      ] else ...[
        Text(l10n.safetySendTo, style: theme.textTheme.titleSmall),
        Wrap(
          spacing: 8,
          children: [
            ChoiceChip(
              key: const Key('sos-to-all'),
              label: Text(l10n.safetySendToAll(contacts)),
              selected: _group == null,
              onSelected: (_) => setState(() => _group = null),
            ),
            for (final g in groups)
              ChoiceChip(
                key: Key('sos-to-group-${g.id}'),
                label: Text(g.name),
                selected: _group == g.id,
                onSelected: (_) => setState(() => _group = g.id),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          registered ? l10n.safetySendChannels(links) : l10n.safetySendSmsOnly,
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          key: const Key('sos-send'),
          style: FilledButton.styleFrom(
            backgroundColor: sosRed,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(72),
          ),
          onPressed: _press,
          icon: const Icon(Icons.sms_failed, size: 32),
          label: Text(l10n.safetySendNow),
        ),
      ],
    ];
  }

  List<Widget> _countdown(AppLocalizations l10n) => [
    const SizedBox(height: 24),
    Text(
      l10n.safetySendingIn(_left),
      key: const Key('sos-countdown'),
      textAlign: TextAlign.center,
      style: Theme.of(context).textTheme.headlineSmall,
    ),
    const SizedBox(height: 24),
    FilledButton.icon(
      key: const Key('sos-cancel'),
      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(72)),
      onPressed: _cancel,
      icon: const Icon(Icons.close, size: 32),
      label: Text(l10n.actionCancel),
    ),
  ];

  List<Widget> _done(
    AppLocalizations l10n,
    SosSendResult r,
    List<EmergencyContact> contacts,
  ) {
    final theme = Theme.of(context);
    final open = ref.read(urlOpenerProvider);
    return [
      Icon(Icons.check_circle, size: 56, color: theme.colorScheme.primary),
      const SizedBox(height: 8),
      if (r.appRecipients > 0)
        Text(
          l10n.safetySentApp(r.appRecipients),
          key: const Key('sos-sent-app'),
          textAlign: TextAlign.center,
        ),
      if (r.appFailed)
        Text(
          l10n.safetySentAppFailed,
          textAlign: TextAlign.center,
          style: TextStyle(color: theme.colorScheme.error),
        ),
      if (r.smsOpened)
        Text(
          l10n.safetySentSms(r.phones.length),
          key: const Key('sos-sent-sms'),
          textAlign: TextAlign.center,
        ),
      const SizedBox(height: 16),
      Text(l10n.safetyWhatsApp, style: theme.textTheme.titleSmall),
      const SizedBox(height: 4),
      OutlinedButton.icon(
        key: const Key('sos-whatsapp-share'),
        onPressed: () => open(whatsAppShareUri(r.text)),
        icon: const Icon(Icons.forum),
        label: Text(l10n.safetyWhatsAppChoose),
      ),
      for (final c in contacts)
        if (normalizeContactPhone(c.phone) case final phone?
            when r.phones.contains(phone))
          ListTile(
            key: Key('sos-whatsapp-${c.id}'),
            leading: const Icon(Icons.chat),
            title: Text(c.name),
            trailing: const Icon(Icons.open_in_new),
            onTap: () => open(whatsAppUri(phone, r.text)),
          ),
      const SizedBox(height: 8),
      TextButton.icon(
        key: const Key('sos-to-live'),
        onPressed: () => context.push(Routes.safetyLive),
        icon: const Icon(Icons.share_location),
        label: Text(l10n.safetyLiveTitle),
      ),
    ];
  }
}
