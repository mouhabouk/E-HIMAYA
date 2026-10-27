import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/institution/org_text.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import 'prevention_controller.dart';
import 'prevention_labels.dart';
import 'prevention_models.dart';
import 'visit_screen.dart';

/// The inspector's visits (phase P4c, design §8.2): scheduled ones and inspected ones waiting for
/// the decision, the nearest first. The home of an inspector, or opened from the shift screen.
class PreventionVisitsScreen extends ConsumerStatefulWidget {
  const PreventionVisitsScreen({super.key, this.home = false});

  /// The app's home (inspector only): the menu signs out.
  final bool home;

  @override
  ConsumerState<PreventionVisitsScreen> createState() =>
      _PreventionVisitsScreenState();
}

class _PreventionVisitsScreenState
    extends ConsumerState<PreventionVisitsScreen> {
  @override
  void initState() {
    super.initState();
    unawaited(ref.read(preventionControllerProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(preventionControllerProvider);
    final c = ref.read(preventionControllerProvider.notifier);
    final name = ref.watch(staffControllerProvider.select((s) => s.me?.name));
    final visits = s.shown;
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.prevVisitsTitle,
        subtitle: name,
        actions: [
          if (widget.home)
            PopupMenuButton<String>(
              key: const Key('staff-menu'),
              onSelected: (_) => unawaited(
                ref.read(staffControllerProvider.notifier).signOut(),
              ),
              itemBuilder: (_) => [
                PopupMenuItem(value: 'out', child: Text(l10n.staffSignOut)),
              ],
            ),
        ],
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          const PendingBar(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: c.load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (!s.loaded)
                    const Center(child: CircularProgressIndicator())
                  else if (visits.isEmpty)
                    AppCard(
                      key: const Key('no-visits'),
                      child: Text(l10n.prevVisitsEmpty),
                    ),
                  for (final v in visits)
                    _VisitCard(visit: v, kept: s.packs[v.id]),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _VisitCard extends StatelessWidget {
  const _VisitCard({required this.visit, this.kept});

  final FieldVisit visit;
  final VisitPack? kept;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final n = Neutrals.of(context);
    final date = visit.scheduledOn;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: AppCard(
        key: Key('visit-${visit.id}'),
        onTap: () => openVisit(context, visit.id),
        borderColor: visit.mine ? Tone.navy.colors(context).fill : null,
        child: Row(
          children: [
            IconTile(
              visit.inspected ? Icons.gavel : Icons.fact_check,
              tone: visit.inspected ? Tone.amber : Tone.navy,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    visit.orgName,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text(
                    [
                      orgKindText(l10n, visit.orgKind),
                      if (date != null)
                        l10n.prevScheduledOn(visitDay(context, date))
                      else
                        l10n.prevNoDate,
                    ].join(' · '),
                    style: TextStyle(color: n.muted),
                  ),
                  if (visit.orgAddress != null)
                    Text(
                      visit.orgAddress!,
                      style: TextStyle(color: n.muted),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      Pill(
                        visitStatusText(l10n, visit.status),
                        tone: visit.inspected ? Tone.amber : Tone.sky,
                      ),
                      if (visit.mine)
                        Pill(
                          l10n.prevMine,
                          tone: Tone.navy,
                          icon: Icons.person,
                        ),
                      if (visit.takenByOther)
                        Pill(
                          l10n.prevTakenByOther,
                          tone: Tone.slate,
                          icon: Icons.lock,
                        ),
                      if (kept != null)
                        Pill(
                          l10n.prevOnPhone,
                          tone: Tone.green,
                          icon: Icons.offline_pin,
                        ),
                      if ((kept?.draft.pending ?? 0) > 0)
                        Pill(
                          l10n.prevPending(kept!.draft.pending),
                          tone: Tone.amber,
                          icon: Icons.cloud_upload,
                        ),
                    ],
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: n.muted),
          ],
        ),
      ),
    );
  }
}

/// Amber band while writes wait on the phone, with «أرسل الآن».
class PendingBar extends ConsumerWidget {
  const PendingBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final (pending, syncing) = ref.watch(
      preventionControllerProvider.select((s) => (s.pending, s.syncing)),
    );
    if (pending == 0) return const SizedBox.shrink();
    final c = Tone.amber.colors(context);
    return Container(
      key: const Key('visits-pending'),
      width: double.infinity,
      color: c.tint,
      padding: const EdgeInsets.fromLTRB(16, 4, 8, 4),
      child: Row(
        children: [
          Icon(Icons.cloud_upload, color: c.onTint, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              l10n.prevPending(pending),
              style: TextStyle(color: c.onTint, fontWeight: FontWeight.w700),
            ),
          ),
          TextButton(
            key: const Key('send-now'),
            onPressed: syncing
                ? null
                : () => unawaited(
                    ref.read(preventionControllerProvider.notifier).sync(),
                  ),
            child: Text(l10n.prevSendNow),
          ),
        ],
      ),
    );
  }
}
