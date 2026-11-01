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
import 'prealert_alarm.dart';

/// Review point 25 (phase D), staged by Yamen (2026-11-01): a camera of the institution saw a
/// fire or smoke. The safety officer is asked first (60 s), then the owner (60 s); without an
/// answer the room is told automatically. While it waits the alarm rings, and the screen has
/// three tiles: the captured picture, «confirm the report» (SOS: the room at once) and «false
/// alarm or unconfirmed» (with a ready reason: nothing reaches the room).
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
const prealertReasons = [
  'unconfirmed',
  'test',
  'cooking',
  'drill',
  'camera',
  'other',
];

class _PrealertScreenState extends ConsumerState<PrealertScreen> {
  Timer? _tick;
  bool _busy = false;
  OrgPrealert? _decided;
  Future<String>? _frame;
  late final PrealertAlarm _alarm = ref.read(prealertAlarmProvider);
  bool _ringing = false;
  bool _muted = false;

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
    if (_ringing) unawaited(_alarm.stop());
    super.dispose();
  }

  /// Rings while the pre-alert waits for an answer, unless silenced; stops otherwise.
  void _ring(bool pending) {
    final want = pending && !_muted;
    if (want == _ringing) return;
    _ringing = want;
    unawaited(want ? _alarm.start() : _alarm.stop());
  }

  void _mute() {
    setState(() => _muted = true);
    _ring(false);
  }

  Future<void> _decide({required bool confirm, String? reason}) async {
    _mute();
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
    _ring(p.pending);
    final text = Theme.of(context).textTheme;
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
              if (p.pending) ...[
                Text(
                  p.stage == 'officer'
                      ? l10n.prealertStageOfficer(left)
                      : l10n.prealertStageOwner(left),
                  key: const Key('prealert-countdown'),
                  textAlign: TextAlign.center,
                  style: text.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
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
                const SizedBox(height: 12),
              ],
              // Tile 1: the picture the camera captured.
              _MediaTile(frame: _frame, l10n: l10n),
              if (p.pending) ...[
                const SizedBox(height: 12),
                // Tile 2: confirm the report (SOS): the room is told at once.
                _BigTile(
                  key: const Key('prealert-confirm'),
                  icon: Icons.sos,
                  label: l10n.prealertConfirm,
                  background: sosRed,
                  foreground: Colors.white,
                  onTap: _busy ? null : () => _decide(confirm: true),
                ),
                const SizedBox(height: 12),
                // Tile 3: a false alarm or an alert not confirmed on site.
                _BigTile(
                  key: const Key('prealert-false'),
                  icon: Icons.do_not_disturb_on,
                  label: l10n.prealertFalseAlarm,
                  background: Theme.of(context)
                      .colorScheme
                      .surfaceContainerHighest,
                  foreground: Theme.of(context).colorScheme.onSurface,
                  onTap: _busy ? null : _falseAlarm,
                ),
                const SizedBox(height: 8),
                if (!_muted)
                  TextButton.icon(
                    key: const Key('prealert-mute'),
                    onPressed: _mute,
                    icon: const Icon(Icons.volume_off),
                    label: Text(l10n.prealertMute),
                  ),
                Text(l10n.prealertHint, style: text.bodySmall),
              ] else ...[
                const SizedBox(height: 12),
                Card(
                  child: ListTile(
                    key: const Key('prealert-state'),
                    leading: Icon(
                      p.state == 'cancelled'
                          ? Icons.do_not_disturb_on
                          : Icons.check_circle,
                    ),
                    title: Text(
                      p.stage == 'room'
                          ? l10n.prealertRoom
                          : prealertStateLabel(l10n, p.state),
                    ),
                    subtitle: p.reason == null ? null : Text(p.reason!),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

/// The first tile: the camera's picture, or a plain tile saying there is none.
class _MediaTile extends StatelessWidget {
  const _MediaTile({required this.frame, required this.l10n});

  final Future<String>? frame;
  final AppLocalizations l10n;

  @override
  Widget build(BuildContext context) {
    final empty = ColoredBox(
      color: Colors.black12,
      child: Center(child: Text(l10n.prealertNoMedia)),
    );
    return Semantics(
      label: l10n.prealertMedia,
      image: true,
      child: ClipRRect(
        key: const Key('prealert-media'),
        borderRadius: BorderRadius.circular(16),
        child: AspectRatio(
          aspectRatio: 16 / 9,
          child: frame == null
              ? empty
              : FutureBuilder<String>(
                  future: frame,
                  builder: (context, snap) => snap.hasData
                      ? Image.network(
                          snap.data!,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) => empty,
                        )
                      : const ColoredBox(color: Colors.black12),
                ),
        ),
      ),
    );
  }
}

/// A large square-ish tile, easy to hit in a hurry.
class _BigTile extends StatelessWidget {
  const _BigTile({
    super.key,
    required this.icon,
    required this.label,
    required this.background,
    required this.foreground,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color background;
  final Color foreground;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    enabled: onTap != null,
    child: Material(
      color: onTap == null ? background.withValues(alpha: 0.5) : background,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: SizedBox(
          height: 112,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 40, color: foreground),
              const SizedBox(width: 12),
              Flexible(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: foreground,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

String prealertReasonLabel(AppLocalizations l10n, String reason) =>
    switch (reason) {
      'unconfirmed' => l10n.prealertReasonUnconfirmed,
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
