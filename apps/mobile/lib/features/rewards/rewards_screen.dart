import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/auth/identity.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/rewards_models.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../onboarding/login_actions.dart';
import 'rewards_labels.dart';
import 'rewards_providers.dart';

/// FR-A-072: the citizen's points, badges, history and certificates. Anonymous users see why
/// they earn nothing; everyone sees the safety notice (never take a risk to report).
class RewardsScreen extends ConsumerWidget {
  const RewardsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final owner = ref.watch(rewardsOwnerProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.rewardsTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: owner == null
            ? const _AnonymousRewards()
            : switch (ref.watch(rewardsProvider)) {
                AsyncData(value: final view?) =>
                  view.summary.anonymous
                      ? const _AnonymousRewards()
                      : _RewardsBody(view: view),
                AsyncError(:final error) => _LoadError(
                  message: errorMessageFor(l10n, error),
                  onRetry: () => ref.invalidate(rewardsProvider),
                ),
                _ => const Center(child: CircularProgressIndicator()),
              },
      ),
    );
  }
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          message,
          key: const Key('rewards-error'),
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
        const SizedBox(height: 12),
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: Text(l10n.actionRetry),
          ),
        ),
        const SizedBox(height: 16),
        const _SafetyNotice(),
      ],
    );
  }
}

/// Shown to anonymous users (and to anyone without a citizen account).
class _AnonymousRewards extends ConsumerWidget {
  const _AnonymousRewards();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final identity = ref.watch(identityProvider);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          key: const Key('rewards-anonymous'),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.visibility_off),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        l10n.rewardsAnonymousTitle,
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(l10n.rewardsAnonymousBody),
                if (identity.isAnonymous) ...[
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    key: const Key('rewards-register'),
                    onPressed: () => runLogin(context, ref, register: true),
                    icon: const Icon(Icons.person_add),
                    label: Text(l10n.citizenRegister),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        const _SafetyNotice(),
        const SizedBox(height: 8),
        const _HowToEarn(),
      ],
    );
  }
}

class _RewardsBody extends ConsumerStatefulWidget {
  const _RewardsBody({required this.view});

  final RewardsView view;

  @override
  ConsumerState<_RewardsBody> createState() => _RewardsBodyState();
}

class _RewardsBodyState extends ConsumerState<_RewardsBody> {
  /// Older history pages loaded with "show more" (after the summary's first page).
  final _older = <PointsEntry>[];
  String? _cursor;
  bool _loadingMore = false;
  String? _openingCertificate;

  @override
  void initState() {
    super.initState();
    _cursor = widget.view.summary.historyNextCursor;
  }

  @override
  void didUpdateWidget(_RewardsBody old) {
    super.didUpdateWidget(old);
    if (!identical(old.view, widget.view)) {
      // A refresh starts the history again from its first page.
      _older.clear();
      _cursor = widget.view.summary.historyNextCursor;
    }
  }

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _loadMore() async {
    final cursor = _cursor;
    if (cursor == null || _loadingMore) return;
    final l10n = AppLocalizations.of(context);
    setState(() => _loadingMore = true);
    try {
      final page = await ref.read(apiProvider).rewardsHistory(cursor: cursor);
      if (!mounted) return;
      setState(() {
        _older.addAll(page.items);
        _cursor = page.nextCursor;
      });
    } on Object catch (e) {
      if (mounted) _message(errorMessageFor(l10n, e));
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _openCertificate(RewardCertificate c) async {
    if (_openingCertificate != null) return;
    final l10n = AppLocalizations.of(context);
    setState(() => _openingCertificate = c.id);
    try {
      final opened = await ref.read(openCertificateProvider)(c.id);
      if (!opened && mounted) _message(l10n.rewardsPdfNoViewer);
    } on Object catch (e) {
      if (mounted) _message(errorMessageFor(l10n, e));
    } finally {
      if (mounted) setState(() => _openingCertificate = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final fmt = DateFormat.yMMMd(locale).add_Hm();
    final view = widget.view;
    final s = view.summary;
    final history = [...s.history, ..._older];
    return RefreshIndicator(
      onRefresh: () => ref.refresh(rewardsProvider.future),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          if (view.offlineSince != null)
            Card(
              key: const Key('rewards-offline'),
              color: theme.colorScheme.tertiaryContainer,
              child: ListTile(
                leading: const Icon(Icons.cloud_off),
                title: Text(
                  l10n.rewardsOfflineCopy(
                    fmt.format(view.offlineSince!.toLocal()),
                  ),
                ),
              ),
            ),
          if (s.paused)
            Card(
              key: const Key('rewards-paused'),
              color: theme.colorScheme.errorContainer,
              child: ListTile(
                leading: Icon(
                  Icons.pause_circle,
                  color: theme.colorScheme.onErrorContainer,
                ),
                title: Text(
                  l10n.rewardsPausedTitle,
                  style: TextStyle(color: theme.colorScheme.onErrorContainer),
                ),
                subtitle: Text(
                  s.pendingPoints > 0
                      ? '${l10n.rewardsPausedBody}\n'
                            '${l10n.rewardsPendingPoints(s.pendingPoints)}'
                      : l10n.rewardsPausedBody,
                  style: TextStyle(color: theme.colorScheme.onErrorContainer),
                ),
              ),
            ),
          _BalanceCard(summary: s),
          const SizedBox(height: 8),
          const _SafetyNotice(),
          const SizedBox(height: 16),
          Text(l10n.rewardsHistoryTitle, style: theme.textTheme.titleMedium),
          if (history.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                l10n.rewardsHistoryEmpty,
                key: const Key('rewards-history-empty'),
              ),
            ),
          for (final e in history) _HistoryTile(entry: e, format: fmt),
          if (_cursor != null && !view.isOffline)
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                key: const Key('rewards-history-more'),
                onPressed: _loadingMore ? null : _loadMore,
                icon: _loadingMore
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.expand_more),
                label: Text(l10n.rewardsShowMore),
              ),
            ),
          const SizedBox(height: 16),
          Text(
            l10n.rewardsCertificatesTitle,
            style: theme.textTheme.titleMedium,
          ),
          if (s.certificates.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(l10n.rewardsCertificatesEmpty),
            ),
          for (final c in s.certificates)
            Card(
              child: ListTile(
                key: Key('rewards-certificate-${c.id}'),
                leading: const Icon(Icons.workspace_premium),
                title: Text(distinctionLabel(l10n, c.distinction)),
                subtitle: Text(
                  [
                    if (c.year != null)
                      l10n.rewardsCertificateYear('${c.year}'),
                    if (c.issuedAt != null)
                      DateFormat.yMMMd(locale).format(c.issuedAt!.toLocal()),
                  ].join(' · '),
                ),
                trailing: _openingCertificate == c.id
                    ? const SizedBox.square(
                        dimension: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Tooltip(
                        message: l10n.rewardsOpenPdf,
                        child: const Icon(Icons.picture_as_pdf),
                      ),
                onTap: () => _openCertificate(c),
              ),
            ),
          const SizedBox(height: 16),
          _HowToEarn(dailyCap: s.dailyCap),
        ],
      ),
    );
  }
}

class _BalanceCard extends StatelessWidget {
  const _BalanceCard({required this.summary});

  final RewardsSummary summary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final current = summary.currentBadge;
    final next = summary.nextBadge;
    final progress = summary.progress;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.rewardsBalanceLabel, style: theme.textTheme.labelLarge),
            Text(
              '${summary.balance}',
              key: const Key('rewards-balance'),
              textDirection: TextDirection.ltr,
              style: theme.textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(
                  Icons.military_tech,
                  color: current == null ? theme.disabledColor : null,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    current == null
                        ? l10n.rewardsNoBadge
                        : l10n.rewardsCurrentBadge(badgeLabel(l10n, current)),
                    key: const Key('rewards-current-badge'),
                    style: theme.textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (next != null) ...[
              Semantics(
                label: l10n.rewardsNextBadge(
                  badgeLabel(l10n, next.level),
                  next.missingPoints,
                ),
                child: LinearProgressIndicator(
                  key: const Key('rewards-progress'),
                  value: progress,
                  minHeight: 8,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                l10n.rewardsNextBadge(
                  badgeLabel(l10n, next.level),
                  next.missingPoints,
                ),
                key: const Key('rewards-next-badge'),
              ),
            ] else if (current != null)
              Text(l10n.rewardsTopBadge),
            const SizedBox(height: 8),
            Text(l10n.rewardsConfirmNote, style: theme.textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.entry, required this.format});

  final PointsEntry entry;
  final DateFormat format;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final e = entry;
    final sign = e.delta > 0 ? '+' : '';
    final details = [
      if (e.trackingCode != null) '\u2066${e.trackingCode}\u2069',
      if (e.multiplier != null && e.multiplier != 1)
        '\u2066×${_trim(e.multiplier!)}\u2069',
      if (e.capped) l10n.rewardsCapped,
      if (e.createdAt != null) format.format(e.createdAt!.toLocal()),
    ];
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(pointsReasonIcon(e.reason)),
      title: Text(pointsReasonLabel(l10n, e.reason)),
      subtitle: details.isEmpty ? null : Text(details.join(' · ')),
      trailing: Text(
        '$sign${e.delta}',
        textDirection: TextDirection.ltr,
        style: theme.textTheme.titleMedium?.copyWith(
          color: e.delta < 0 ? theme.colorScheme.error : null,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  static String _trim(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : '$v';
}

/// Fixed notice (phase 8 §3, safety): never take a risk to report; 198 one tap away.
class _SafetyNotice extends ConsumerWidget {
  const _SafetyNotice();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final civilProtection = emergencyNumbers.first;
    return Card(
      key: const Key('rewards-safety'),
      color: theme.colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.health_and_safety,
                  color: theme.colorScheme.onSecondaryContainer,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    l10n.rewardsSafetyNotice,
                    style: TextStyle(
                      color: theme.colorScheme.onSecondaryContainer,
                    ),
                  ),
                ),
              ],
            ),
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton.icon(
                key: const Key('rewards-call-198'),
                onPressed: () async {
                  final ok = await ref.read(dialerProvider)(
                    civilProtection.telUri,
                  );
                  if (!ok && context.mounted) {
                    ScaffoldMessenger.of(context)
                        .showSnackBar(SnackBar(content: Text(l10n.dialFailed)));
                  }
                },
                icon: const Icon(Icons.call),
                label: Text(l10n.callNumber(civilProtection.number)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// How points are earned (generic: the amounts are rules staff can change) and the prizes
/// notice (no cash is promised in the app).
class _HowToEarn extends StatelessWidget {
  const _HowToEarn({this.dailyCap});

  final int? dailyCap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l10n.rewardsHowTitle, style: theme.textTheme.titleMedium),
        const SizedBox(height: 4),
        Text(l10n.rewardsHowBody),
        if (dailyCap != null && dailyCap! > 0) ...[
          const SizedBox(height: 4),
          Text(l10n.rewardsDailyCap(dailyCap!)),
        ],
        const SizedBox(height: 8),
        Text(
          l10n.rewardsPrizesNotice,
          key: const Key('rewards-prizes'),
          style: theme.textTheme.bodySmall,
        ),
      ],
    );
  }
}
