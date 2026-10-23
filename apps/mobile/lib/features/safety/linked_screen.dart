import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../institution/institution_providers.dart';
import 'safety_models.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// Additions 8.3 and 11: two e-Himaya users are linked when one shows a code and the other
/// enters it. Linked contacts receive the SOS message in the app, ringing through silent mode.
class LinkedContactsScreen extends ConsumerWidget {
  const LinkedContactsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final registered = ref.watch(identityProvider).isRegistered;
    final links = ref.watch(safetyLinksProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyLinkedTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.safetyLinkedIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            if (!registered)
              SafetyRegistrationCard(reason: l10n.safetyLinkedNeedsAccount)
            else ...[
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      key: const Key('linked-invite'),
                      onPressed: () => _invite(context, ref),
                      icon: const Icon(Icons.person_add_alt),
                      label: Text(l10n.safetyInvite),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      key: const Key('linked-enter-code'),
                      onPressed: () => _enterCode(context, ref),
                      icon: const Icon(Icons.keyboard),
                      label: Text(l10n.safetyEnterCode),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ...links.when(
                data: (items) => items.isEmpty
                    ? [
                        Text(
                          l10n.safetyLinkedEmpty,
                          textAlign: TextAlign.center,
                        ),
                      ]
                    : [
                        for (final l in items)
                          Card(
                            child: ListTile(
                              key: Key('link-${l.id}'),
                              leading: const Icon(Icons.verified_user),
                              title: Text(l.firstName ?? l10n.safetySomeone),
                              subtitle: l.phone == null
                                  ? null
                                  : Text(
                                      l.phone!,
                                      textDirection: TextDirection.ltr,
                                    ),
                              trailing: IconButton(
                                key: Key('link-remove-${l.id}'),
                                tooltip: l10n.safetyUnlink,
                                icon: const Icon(Icons.link_off),
                                onPressed: () => _remove(context, ref, l),
                              ),
                            ),
                          ),
                      ],
                loading: () => [
                  const Center(child: CircularProgressIndicator()),
                ],
                error: (e, _) => [
                  SafetyError(
                    error: e,
                    onRetry: () => ref.invalidate(safetyLinksProvider),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(l10n.safetyLinkedPrivacy, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _invite(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    InvitationCode code;
    try {
      code = await ref.read(apiProvider).createInvitation();
    } on ApiException catch (e) {
      if (context.mounted) {
        showSafetySnack(context, apiErrorMessage(l10n, e.code));
      }
      return;
    }
    if (!context.mounted) return;
    final text = l10n.safetyInviteText(code.code);
    final open = ref.read(urlOpenerProvider);
    await showDialog<void>(
      context: context,
      builder: (context) {
        final theme = Theme.of(context);
        return AlertDialog(
          title: Text(l10n.safetyInviteTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(l10n.safetyInviteBody),
              const SizedBox(height: 16),
              SelectableText(
                code.code,
                key: const Key('invite-code'),
                textAlign: TextAlign.center,
                textDirection: TextDirection.ltr,
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                  letterSpacing: 4,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                l10n.safetyInviteExpires(safetyTime(context, code.expiresAt)),
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
          actions: [
            TextButton.icon(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: code.code));
                if (context.mounted) {
                  showSafetySnack(context, l10n.safetyCopied);
                }
              },
              icon: const Icon(Icons.copy),
              label: Text(l10n.safetyCopy),
            ),
            TextButton.icon(
              onPressed: () => open(smsGroupUri(const [], text)),
              icon: const Icon(Icons.sms),
              label: Text(l10n.safetyBySms),
            ),
            TextButton.icon(
              onPressed: () => open(whatsAppShareUri(text)),
              icon: const Icon(Icons.forum),
              label: const Text('WhatsApp'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.safetyDone),
            ),
          ],
        );
      },
    );
  }

  Future<void> _enterCode(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final controller = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.safetyEnterCode),
        content: TextField(
          key: const Key('code-field'),
          controller: controller,
          autofocus: true,
          textDirection: TextDirection.ltr,
          textCapitalization: TextCapitalization.characters,
          decoration: const InputDecoration(hintText: 'XXXX-XXXX'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('code-check'),
            onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            child: Text(l10n.actionContinue),
          ),
        ],
      ),
    );
    if (code == null || code.isEmpty || !context.mounted) return;
    final api = ref.read(apiProvider);
    try {
      final preview = await api.previewInvitation(code);
      if (!context.mounted) return;
      final who = [
        preview.firstName ?? l10n.safetySomeone,
        if (preview.phoneHint != null) preview.phoneHint!,
      ].join(' · ');
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(l10n.safetyLinkConfirmTitle),
          content: Text(l10n.safetyLinkConfirmBody(who)),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(l10n.actionCancel),
            ),
            FilledButton(
              key: const Key('code-accept'),
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(l10n.safetyLinkAccept),
            ),
          ],
        ),
      );
      if (ok != true) return;
      await api.acceptInvitation(code);
      ref.invalidate(safetyLinksProvider);
      if (context.mounted) showSafetySnack(context, l10n.safetyLinkedDone);
    } on ApiException catch (e) {
      if (context.mounted) {
        showSafetySnack(
          context,
          e.code == ApiErrorCode.notFound
              ? l10n.safetyCodeInvalid
              : apiErrorMessage(l10n, e.code),
        );
      }
    }
  }

  Future<void> _remove(
    BuildContext context,
    WidgetRef ref,
    SafetyLink l,
  ) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.safetyUnlinkTitle(l.firstName ?? l10n.safetySomeone)),
        content: Text(l10n.safetyUnlinkBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('unlink-confirm'),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.safetyUnlink),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(apiProvider).removeSafetyLink(l.id);
      ref.invalidate(safetyLinksProvider);
    } on ApiException catch (e) {
      if (context.mounted) {
        showSafetySnack(context, apiErrorMessage(l10n, e.code));
      }
    }
  }
}
