import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/quota/anon_quota.dart';
import '../../core/quota/anon_quota_controller.dart';
import '../../core/routing/app_router.dart';
import '../../l10n/app_localizations.dart';

/// "N of 5 left" for the anonymous quota (phase 9 §3), N as last announced by the server.
String anonQuotaLabel(AppLocalizations l10n, AnonQuota quota) {
  final limit = quota.limit;
  return limit == null
      ? l10n.anonQuotaRemainingShort(quota.remaining)
      : l10n.anonQuotaRemaining(quota.remaining, limit);
}

/// Card on the home and report screens of an anonymous installation: reports left without an
/// account, and the way to the quota screen. Hidden for registered accounts and while the
/// server has not told the quota yet. Watching it fetches the quota once on start (online).
class AnonQuotaCard extends ConsumerWidget {
  const AnonQuotaCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(anonQuotaStartupProvider);
    final anonymous = ref.watch(identityProvider.select((i) => i.isAnonymous));
    final quota = ref.watch(anonQuotaProvider);
    if (!anonymous || quota == null) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final exhausted = quota.exhausted;
    return Card(
      key: const Key('anon-quota-card'),
      color: exhausted ? scheme.errorContainer : null,
      child: ListTile(
        leading: Icon(
          exhausted ? Icons.lock_outline : Icons.person_outline,
          color: exhausted ? scheme.onErrorContainer : null,
        ),
        title: Text(l10n.anonQuotaCardTitle),
        subtitle: Text(
          exhausted
              ? '${anonQuotaLabel(l10n, quota)}. ${l10n.anonQuotaExhaustedHint}'
              : anonQuotaLabel(l10n, quota),
          key: const Key('anon-quota-label'),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push(Routes.quota),
      ),
    );
  }
}
