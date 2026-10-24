import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/error_messages.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../institution/institution_providers.dart';
import 'safety_models.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// The notification texts of the foreground service while the position is shared.
FollowNotice liveNotice(AppLocalizations l10n) =>
    (title: l10n.safetyLiveNoticeTitle, text: l10n.safetyLiveNoticeText);

/// Addition 8.4: a random link that ends by itself (15 min to 8 h, 1 h by default) and can be
/// stopped at any time. Whoever has the link sees the moving point, never the user's name.
class LiveShareScreen extends ConsumerStatefulWidget {
  const LiveShareScreen({super.key});

  @override
  ConsumerState<LiveShareScreen> createState() => _LiveShareScreenState();
}

class _LiveShareScreenState extends ConsumerState<LiveShareScreen> {
  int _minutes = 60;
  bool _busy = false;
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    // Repaints the time left every 30 s.
    _tick = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    ref
        .read(liveShareProvider.notifier)
        .resume(liveNotice(AppLocalizations.of(context)));
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  Future<void> _start() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await ref
          .read(liveShareProvider.notifier)
          .start(_minutes, liveNotice(l10n));
    } on ApiException catch (e) {
      if (mounted) showSafetySnack(context, apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final registered = ref.watch(identityProvider).isRegistered;
    final live = ref.watch(liveShareProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyLiveTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.safetyLiveIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            if (!registered)
              SafetyRegistrationCard(reason: l10n.safetyLiveNeedsAccount)
            else if (live == null) ...[
              Text(l10n.safetyLiveFor, style: theme.textTheme.titleSmall),
              Wrap(
                spacing: 8,
                children: [
                  for (final m in SafetyRules.liveMinutes)
                    ChoiceChip(
                      key: Key('live-minutes-$m'),
                      label: Text(safetyDuration(l10n, Duration(minutes: m))),
                      selected: _minutes == m,
                      onSelected: (_) => setState(() => _minutes = m),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                key: const Key('live-start'),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(56),
                ),
                onPressed: _busy ? null : _start,
                icon: const Icon(Icons.share_location),
                label: Text(l10n.safetyLiveStart),
              ),
              const SizedBox(height: 8),
              Text(l10n.safetyLivePrivacy, style: theme.textTheme.bodySmall),
            ] else
              _Running(session: live),
          ],
        ),
      ),
    );
  }
}

class _Running extends ConsumerWidget {
  const _Running({required this.session});

  final LiveShareSession session;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final now = ref.read(clockProvider)();
    final link = liveLink(ref.read(appConfigProvider).portalUrl, session.token);
    final text = l10n.safetyLiveShareText(link.toString());
    final open = ref.read(urlOpenerProvider);
    final contacts = ref.watch(emergencyContactsProvider).value ?? const [];
    final phones = [for (final c in contacts) ?normalizeContactPhone(c.phone)];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          color: sosRed.withValues(alpha: 0.08),
          child: ListTile(
            key: const Key('live-running'),
            leading: const Icon(Icons.share_location, color: sosRed),
            title: Text(l10n.safetyLiveRunning),
            subtitle: Text(
              [
                l10n.safetyLiveLeft(
                  safetyDuration(l10n, session.expiresAt.difference(now)),
                ),
                if (session.lastSentAt != null)
                  l10n.safetyLiveLastSent(
                    safetyTime(context, session.lastSentAt!),
                  ),
              ].join(' · '),
            ),
          ),
        ),
        const SizedBox(height: 8),
        SelectableText(
          link.toString(),
          key: const Key('live-link'),
          textDirection: TextDirection.ltr,
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              key: const Key('live-copy'),
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: link.toString()));
                if (context.mounted) {
                  showSafetySnack(context, l10n.safetyCopied);
                }
              },
              icon: const Icon(Icons.copy),
              label: Text(l10n.safetyCopy),
            ),
            if (phones.isNotEmpty)
              OutlinedButton.icon(
                key: const Key('live-sms'),
                onPressed: () => open(smsGroupUri(phones, text)),
                icon: const Icon(Icons.sms),
                label: Text(l10n.safetyLiveSmsContacts),
              ),
            OutlinedButton.icon(
              key: const Key('live-whatsapp'),
              onPressed: () => open(whatsAppShareUri(text)),
              icon: const Icon(Icons.forum),
              label: const Text('WhatsApp'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          key: const Key('live-stop'),
          style: FilledButton.styleFrom(
            backgroundColor: sosRed,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(56),
          ),
          onPressed: () => ref.read(liveShareProvider.notifier).stop(),
          icon: const Icon(Icons.stop_circle),
          label: Text(l10n.safetyLiveStop),
        ),
      ],
    );
  }
}
