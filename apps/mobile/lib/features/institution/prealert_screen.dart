import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/sim_banner.dart';
import '../../core/ui/theme.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'institution_providers.dart';

/// Review point 25 (phase D, design §2): a camera of the institution saw a fire or smoke. The
/// owner sees the picture and a countdown; «confirm» sends the report to the room at once,
/// «false alarm» (with a ready reason) closes it. With no answer the room is told when the
/// countdown ends (`orgs.prealert_seconds`, 90 s by default).
class PrealertScreen extends ConsumerStatefulWidget {
  const PrealertScreen({
    super.key,
    required this.orgId,
    required this.prealertId,
  });

  final String orgId;
  final String prealertId;

  @override
  ConsumerState<PrealertScreen> createState() => _PrealertScreenState();
}

/// Ready reasons of a false alarm (design §2): no typing in a hurry.
const prealertReasons = ['test', 'cooking', 'drill', 'camera', 'other'];

class _PrealertScreenState extends ConsumerState<PrealertScreen> {
  Timer? _tick;
  bool _busy = false;
  OrgPrealert? _decided;
  Future<String>? _frame;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  Future<void> _decide({required bool confirm, String? reason}) async {
    setState(() => _busy = true);
    final l10n = AppLocalizations.of(context);
    try {
      final out = await ref
          .read(apiProvider)
          .decidePrealert(
            widget.orgId,
            widget.prealertId,
            confirm: confirm,
            reason: reason,
          );
      ref.invalidate(orgPrealertsProvider(widget.orgId));
      if (mounted) setState(() => _decided = out);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.maybeOf(context)
            ?.showSnackBar(SnackBar(content: Text(errorMessageFor(l10n, e))));
      }
      ref.invalidate(orgPrealertsProvider(widget.orgId));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _falseAlarm() async {
    final l10n = AppLocalizations.of(context);
    final reason = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SectionTitle(l10n.prealertWhyFalse),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final r in prealertReasons)
                    ActionChip(
                      key: Key('prealert-reason-$r'),
                      label: Text(prealertReasonLabel(l10n, r)),
                      onPressed: () =>
                          Navigator.of(context)
                              .pop(prealertReasonLabel(l10n, r)),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
    if (reason != null) await _decide(confirm: false, reason: reason);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final list = ref.watch(orgPrealertsProvider(widget.orgId));
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.prealertTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: list.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(errorMessageFor(l10n, e)),
          ),
        ),
        data: (items) {
          final p =
              _decided ??
              items.where((p) => p.id == widget.prealertId).firstOrNull;
          if (p == null) {
            return Center(child: Text(l10n.prealertGone));
          }
          return _body(context, l10n, p);
        },
      ),
    );
  }

  Widget _body(BuildContext context, AppLocalizations l10n, OrgPrealert p) {
    final left = p.pending
        ? p.deadlineAt.difference(DateTime.now()).inSeconds.clamp(0, 3600)
        : 0;
    final seen = p.label == 'smoke' ? l10n.prealertSmoke : l10n.prealertFire;
    _frame ??= p.hasFrame
        ? ref.read(apiProvider).prealertFrame(widget.orgId, p.id)
        : null;
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        if (p.simulated) SimBanner(text: l10n.prealertSimulated),
        HeroHeader(
          icon: Icons.local_fire_department,
          title: '$seen · ${(p.confidence * 100).round()}%',
          meta: p.orgName,
          tone: p.pending ? Tone.red : Tone.navy,
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_frame != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: FutureBuilder<String>(
                    future: _frame,
                    builder: (context, snap) => AspectRatio(
                      aspectRatio: 16 / 9,
                      child: snap.hasData
                          ? Image.network(
                              snap.data!,
                              fit: BoxFit.cover,
                              errorBuilder: (_, _, _) =>
                                  const ColoredBox(color: Colors.black12),
                            )
                          : const ColoredBox(color: Colors.black12),
                    ),
                  ),
                ),
              const SizedBox(height: 16),
              if (p.pending) ...[
                Text(
                  l10n.prealertCountdown(left),
                  key: const Key('prealert-countdown'),
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value:
                      left /
                      p.deadlineAt
                          .difference(p.raisedAt)
                          .inSeconds
                          .clamp(1, 3600),
                  color: sosRed,
                ),
                const SizedBox(height: 16),
                ToneButton(
                  action: BarAction(
                    key: const Key('prealert-confirm'),
                    label: l10n.prealertConfirm,
                    icon: Icons.campaign,
                    tone: Tone.red,
                    onPressed: _busy ? null : () => _decide(confirm: true),
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  key: const Key('prealert-false'),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size.fromHeight(52),
                  ),
                  onPressed: _busy ? null : _falseAlarm,
                  icon: const Icon(Icons.do_not_disturb_on),
                  label: Text(l10n.prealertFalseAlarm),
                ),
                const SizedBox(height: 12),
                Text(
                  l10n.prealertHint,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ] else
                Card(
                  child: ListTile(
                    key: const Key('prealert-state'),
                    leading: Icon(
                      p.state == 'cancelled'
                          ? Icons.do_not_disturb_on
                          : Icons.check_circle,
                    ),
                    title: Text(prealertStateLabel(l10n, p.state)),
                    subtitle: p.reason == null ? null : Text(p.reason!),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

String prealertReasonLabel(AppLocalizations l10n, String reason) =>
    switch (reason) {
      'test' => l10n.prealertReasonTest,
      'cooking' => l10n.prealertReasonCooking,
      'drill' => l10n.prealertReasonDrill,
      'camera' => l10n.prealertReasonCamera,
      _ => l10n.prealertReasonOther,
    };

String prealertStateLabel(AppLocalizations l10n, String state) =>
    switch (state) {
      'cancelled' => l10n.prealertCancelled,
      'confirmed' => l10n.prealertConfirmed,
      'escalated' => l10n.prealertEscalated,
      _ => l10n.prealertPending,
    };
