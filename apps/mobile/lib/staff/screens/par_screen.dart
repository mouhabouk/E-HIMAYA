import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_api.dart';
import '../staff_capture.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import 'field_widgets.dart';

/// One member of a team inside a danger zone (OS7, design-os7.md): the leader is `m0`.
class ParMember {
  const ParMember({
    required this.key,
    required this.name,
    this.role,
    this.awayWhy,
  });

  factory ParMember.fromJson(Map<String, dynamic> j) => ParMember(
    key: j['key'] as String,
    name: j['name'] as String,
    role: j['role'] as String?,
    awayWhy: j['away_why'] as String?,
  );

  final String key;
  final String name;
  final String? role;
  final String? awayWhy;
}

/// The team of the mission inside the zone, as the server computes it.
class ParTeam {
  const ParTeam({
    required this.zone,
    required this.status,
    required this.intervalS,
    required this.remainingS,
    required this.lastConfirmedAt,
    required this.members,
    this.nextAt,
    this.pauseReason,
    this.outAt,
  });

  factory ParTeam.fromJson(Map<String, dynamic> j) => ParTeam(
    zone: j['zone'] as String,
    status: j['status'] as String,
    intervalS: (j['interval_s'] as num).toInt(),
    remainingS: (j['remaining_s'] as num?)?.toInt(),
    lastConfirmedAt: DateTime.parse(j['last_confirmed_at'] as String),
    nextAt: DateTime.tryParse(j['next_at'] as String? ?? ''),
    pauseReason: j['pause_reason'] as String?,
    outAt: DateTime.tryParse(j['out_at'] as String? ?? ''),
    members: [
      for (final m in j['members'] as List? ?? const [])
        ParMember.fromJson(m as Map<String, dynamic>),
    ],
  );

  final String zone;
  final String status;
  final int intervalS;
  final int? remainingS;
  final DateTime lastConfirmedAt;
  final DateTime? nextAt;
  final String? pauseReason;
  final DateTime? outAt;
  final List<ParMember> members;

  bool get inside => outAt == null;
  bool get paused => status == 'paused';
  int get away => members.where((m) => m.awayWhy != null).length;
}

/// What the leader's phone shows for one mission.
class ParMission {
  const ParMission({
    required this.team,
    required this.missing,
    required this.closed,
    required this.resources,
    required this.lastSituation,
    required this.read,
  });

  factory ParMission.fromJson(Map<String, dynamic> j) => ParMission(
    team: j['team'] == null
        ? null
        : ParTeam.fromJson(j['team'] as Map<String, dynamic>),
    missing: [
      for (final m in j['missing'] as List? ?? const [])
        m as Map<String, dynamic>,
    ],
    closed: j['closed'] as bool? ?? false,
    resources: [
      for (final r in j['resources'] as List? ?? const []) r as String,
    ],
    lastSituation:
        (j['last_sitrep'] as Map<String, dynamic>?)?['situation'] as String?,
    read: DateTime.now(),
  );

  final ParTeam? team;
  final List<Map<String, dynamic>> missing;
  final bool closed;
  final List<String> resources;
  final String? lastSituation;

  /// When the phone read it: the timer counts down from there.
  final DateTime read;

  /// Seconds left to the next check now (negative: late); frozen while paused.
  int? leftNow() {
    final t = team;
    if (t == null || t.remainingS == null) return null;
    if (t.paused) return t.remainingS;
    return t.remainingS! - DateTime.now().difference(read).inSeconds;
  }
}

/// The check of a mission (OS7).
final parProvider = FutureProvider.autoDispose.family<ParMission, String>((
  ref,
  missionId,
) async {
  return ParMission.fromJson(await ref.watch(staffApiProvider).par(missionId));
});

const awayReasons = ['air', 'water_fuel', 'care', 'rest', 'other'];

String parAwayLabel(AppLocalizations l10n, String key) => switch (key) {
  'air' => l10n.parAwayAir,
  'water_fuel' => l10n.parAwayWater,
  'care' => l10n.parAwayCare,
  'rest' => l10n.parAwayRest,
  _ => l10n.parAwayOther,
};

String parSituationLabel(AppLocalizations l10n, String key) => switch (key) {
  'controlled' => l10n.parSituationControlled,
  'progress' => l10n.parSituationProgress,
  _ => l10n.parSituationNot,
};

Tone parSituationTone(String key) => switch (key) {
  'controlled' => Tone.green,
  'progress' => Tone.amber,
  _ => Tone.red,
};

String mmss(int seconds) {
  final s = seconds.abs();
  final t =
      '${(s ~/ 60).toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';
  return seconds < 0 ? '-$t' : t;
}

/// The line on the mission screen: the timer when the team is inside, «enter the zone» otherwise.
class ParCard extends ConsumerWidget {
  const ParCard({super.key, required this.missionId});

  final String missionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final p = ref.watch(parProvider(missionId)).value;
    if (p == null) return const SizedBox.shrink();
    final t = p.team;
    final inside = t != null && t.inside;
    final left = p.leftNow();
    final tone = !inside
        ? Tone.slate
        : t.paused
        ? Tone.slate
        : (left ?? 0) < 0 || p.missing.isNotEmpty
        ? Tone.red
        : Tone.green;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: NavCard(
        key: const Key('open-par'),
        icon: Icons.groups,
        tone: tone,
        title: l10n.parTitle,
        subtitle: p.closed
            ? l10n.parClosed
            : !inside
            ? l10n.parEnterHint
            : t.paused
            ? l10n.parPaused
            : l10n.parLeft(mmss(left ?? 0)),
        onTap: () => push(context, ParScreen(missionId: missionId)),
      ),
    );
  }
}

/// The leader's check screen: the timer, «الكل حاضر الآن», the crew with «خرج مؤقتا», a missing
/// resource, «ردّ الخبر» and «خرجنا» with the headcount.
class ParScreen extends ConsumerStatefulWidget {
  const ParScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<ParScreen> createState() => _ParScreenState();
}

class _ParScreenState extends ConsumerState<ParScreen> {
  Timer? _tick;
  int _seconds = 0;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _seconds++);
      // The room may change the time or pause the check: read it again now and then.
      if (_seconds % 15 == 0) ref.invalidate(parProvider(widget.missionId));
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  Future<bool> _act(
    String action, [
    Map<String, dynamic> body = const {},
  ]) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      await ref
          .read(staffApiProvider)
          .parAction(widget.missionId, action, body);
      ref.invalidate(parProvider(widget.missionId));
      return true;
    } on CrewError catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(parError(l10n, e.code))));
      return false;
    } on Object {
      messenger.showSnackBar(SnackBar(content: Text(l10n.parFailed)));
      return false;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sheet(Widget sheet) => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => sheet,
  );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final readOnly = s.me?.readOnly ?? false;
    final async = ref.watch(parProvider(widget.missionId));
    final p = async.value;
    final t = p?.team;
    final inside = t != null && t.inside;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.parTitle),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (async.isLoading && p == null)
                  const Center(child: CircularProgressIndicator()),
                if (async.hasError && p == null) Text(l10n.parFailed),
                if (p != null && p.closed)
                  Pill(l10n.parClosed, tone: Tone.navy, icon: Icons.archive),
                if (p != null && !p.closed && !inside)
                  _Enter(
                    busy: _busy || readOnly,
                    outAt: t?.outAt,
                    onEnter: (zone) => unawaited(_act('enter', {'zone': zone})),
                  ),
                if (p != null && inside) ...[
                  _Timer(mission: p, team: t),
                  const SizedBox(height: 12),
                  if (p.missing.isNotEmpty)
                    for (final m in p.missing)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Pill(
                          l10n.parMissingLine(
                            m['resource'] as String,
                            m['carrier'] as String,
                          ),
                          tone: Tone.red,
                          icon: Icons.warning,
                        ),
                      ),
                  SectionTitle(l10n.parCrew(t.members.length - t.away)),
                  for (final m in t.members)
                    _MemberTile(
                      member: m,
                      busy: _busy || readOnly,
                      onAway: () => unawaited(
                        _sheet(
                          _AwaySheet(
                            member: m,
                            onPick: (why) =>
                                _act('away', {'member': m.key, 'why': why}),
                          ),
                        ),
                      ),
                      onBack: () => unawaited(_act('back', {'member': m.key})),
                    ),
                  if (p.lastSituation != null) ...[
                    const SizedBox(height: 8),
                    Pill(
                      l10n.parLastWord(
                        parSituationLabel(l10n, p.lastSituation!),
                      ),
                      tone: parSituationTone(p.lastSituation!),
                    ),
                  ],
                ],
                const SizedBox(height: 12),
                Text(
                  l10n.parNote,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: p == null || !inside || readOnly
          ? null
          : SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: ToneButton(
                            action: BarAction(
                              key: const Key('par-confirm'),
                              label: l10n.parAllHere,
                              icon: Icons.check,
                              tone: Tone.green,
                              onPressed: _busy || t.paused
                                  ? null
                                  : () => unawaited(_act('confirm')),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: ToneButton(
                            action: BarAction(
                              key: const Key('par-sitrep'),
                              label: l10n.parSitrep,
                              icon: Icons.campaign,
                              tone: Tone.navy,
                              onPressed: _busy
                                  ? null
                                  : () => unawaited(
                                      _sheet(
                                        _SitrepSheet(
                                          missionId: widget.missionId,
                                          onSend: (body) =>
                                              _act('sitrep', body),
                                        ),
                                      ),
                                    ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: ToneButton(
                            action: BarAction(
                              key: const Key('par-missing'),
                              label: l10n.parMissing,
                              icon: Icons.warning,
                              tone: Tone.red,
                              onPressed: _busy
                                  ? null
                                  : () => unawaited(
                                      _sheet(
                                        _MissingSheet(
                                          team: t,
                                          resources: p.resources,
                                          onSend: (body) =>
                                              _act('missing', body),
                                        ),
                                      ),
                                    ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: ToneButton(
                            action: BarAction(
                              key: const Key('par-exit'),
                              label: l10n.parWeAreOut,
                              icon: Icons.logout,
                              tone: Tone.slate,
                              onPressed: _busy
                                  ? null
                                  : () => unawaited(
                                      _sheet(
                                        _ExitSheet(
                                          team: t,
                                          onSend: (keys) =>
                                              _act('exit', {'members': keys}),
                                        ),
                                      ),
                                    ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}

String parError(AppLocalizations l10n, String code) => switch (code) {
  'paused' => l10n.parPaused,
  'par_closed' => l10n.parClosed,
  'headcount_incomplete' => l10n.parHeadcountIncomplete,
  'already_inside' || 'not_inside' => l10n.parFailed,
  _ => l10n.parFailed,
};

class _Enter extends StatelessWidget {
  const _Enter({required this.busy, required this.onEnter, this.outAt});

  final bool busy;
  final DateTime? outAt;
  final void Function(String zone) onEnter;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (outAt != null) ...[
          Pill(
            l10n.parOutAt(hhmm(outAt!.toLocal())),
            tone: Tone.green,
            icon: Icons.check,
          ),
          const SizedBox(height: 12),
        ],
        Text(l10n.parEnterHint),
        const SizedBox(height: 12),
        ToneButton(
          action: BarAction(
            key: const Key('par-enter-hot'),
            label: l10n.parEnterHot,
            icon: Icons.local_fire_department,
            tone: Tone.red,
            onPressed: busy ? null : () => onEnter('hot'),
          ),
        ),
        const SizedBox(height: 10),
        ToneButton(
          action: BarAction(
            key: const Key('par-enter-warm'),
            label: l10n.parEnterWarm,
            icon: Icons.warning_amber,
            tone: Tone.amber,
            onPressed: busy ? null : () => onEnter('warm'),
          ),
        ),
      ],
    );
  }
}

class _Timer extends StatelessWidget {
  const _Timer({required this.mission, required this.team});

  final ParMission mission;
  final ParTeam team;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final left = mission.leftNow() ?? 0;
    final tone = team.paused
        ? Tone.slate
        : left < 0
        ? Tone.red
        : left <= 60
        ? Tone.amber
        : Tone.green;
    return AppCard(
      key: const Key('par-timer'),
      child: Column(
        children: [
          Stack(
            alignment: Alignment.center,
            children: [
              ProgressRing(
                value: team.paused ? 1 : left / team.intervalS,
                size: 180,
                tone: tone,
              ),
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    team.paused ? '‖' : mmss(left),
                    key: const Key('par-left'),
                    textDirection: TextDirection.ltr,
                    style: theme.textTheme.headlineLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: tone == Tone.red
                          ? tone.colors(context).fill
                          : null,
                    ),
                  ),
                  Text(team.paused ? l10n.parPaused : l10n.parUntilCheck),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            alignment: WrapAlignment.center,
            children: [
              Pill(
                team.zone == 'hot'
                    ? l10n.parZoneHot(team.intervalS ~/ 60)
                    : l10n.parZoneWarm(team.intervalS ~/ 60),
                tone: team.zone == 'hot' ? Tone.red : Tone.amber,
              ),
              Pill(
                l10n.parLastConfirmed(hhmm(team.lastConfirmedAt.toLocal())),
                tone: Tone.green,
                icon: Icons.check,
              ),
              if (team.nextAt != null && !team.paused)
                Pill(
                  l10n.parSetTime(hhmm(team.nextAt!.toLocal())),
                  tone: Tone.navy,
                  icon: Icons.schedule,
                ),
              if (team.paused && team.pauseReason != null)
                Pill(team.pauseReason!, tone: Tone.slate, icon: Icons.pause),
            ],
          ),
        ],
      ),
    );
  }
}

class _MemberTile extends StatelessWidget {
  const _MemberTile({
    required this.member,
    required this.busy,
    required this.onAway,
    required this.onBack,
  });

  final ParMember member;
  final bool busy;
  final VoidCallback onAway;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final away = member.awayWhy;
    final leader = member.key == 'm0';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: AppCard(
        key: Key('par-member-${member.key}'),
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            IconTile(
              away == null ? Icons.person : Icons.directions_walk,
              tone: away == null ? Tone.green : Tone.amber,
              soft: true,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    member.name,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  Text(
                    away != null
                        ? l10n.parAwayNow(parAwayLabel(l10n, away))
                        : leader
                        ? l10n.parLeader
                        : member.role ?? '',
                  ),
                ],
              ),
            ),
            if (!leader)
              away == null
                  ? OutlinedButton(
                      key: Key('par-away-${member.key}'),
                      onPressed: busy ? null : onAway,
                      child: Text(l10n.parAway),
                    )
                  : FilledButton(
                      key: Key('par-back-${member.key}'),
                      onPressed: busy ? null : onBack,
                      child: Text(l10n.parBack),
                    ),
          ],
        ),
      ),
    );
  }
}

class _AwaySheet extends StatelessWidget {
  const _AwaySheet({required this.member, required this.onPick});

  final ParMember member;
  final Future<bool> Function(String why) onPick;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionTitle(l10n.parAwayTitle(member.name)),
          for (final why in awayReasons)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: OutlinedButton(
                key: Key('par-why-$why'),
                onPressed: () {
                  final nav = Navigator.of(context);
                  unawaited(onPick(why).then((_) => nav.pop()));
                },
                child: Text(parAwayLabel(l10n, why)),
              ),
            ),
          Text(l10n.parAwayNote, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _MissingSheet extends StatefulWidget {
  const _MissingSheet({
    required this.team,
    required this.resources,
    required this.onSend,
  });

  final ParTeam team;
  final List<String> resources;
  final Future<bool> Function(Map<String, dynamic> body) onSend;

  @override
  State<_MissingSheet> createState() => _MissingSheetState();
}

class _MissingSheetState extends State<_MissingSheet> {
  late final List<String> _resources = [...widget.resources];
  String? _resource;
  String? _member;
  final _place = TextEditingController();
  final _added = TextEditingController();

  @override
  void dispose() {
    _place.dispose();
    _added.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        16,
        16,
        16 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionTitle(l10n.parMissingWhat),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final r in _resources)
                  ChoiceChip(
                    key: Key('par-res-$r'),
                    label: Text(r),
                    selected: _resource == r,
                    onSelected: (_) => setState(() => _resource = r),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('par-res-new'),
                    controller: _added,
                    maxLength: 80,
                    decoration: InputDecoration(labelText: l10n.parAddResource),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                IconButton(
                  key: const Key('par-res-add'),
                  tooltip: l10n.parAddResource,
                  icon: const Icon(Icons.add),
                  onPressed: _added.text.trim().length < 2
                      ? null
                      : () => setState(() {
                          final r = _added.text.trim();
                          if (!_resources.contains(r)) _resources.add(r);
                          _resource = r;
                          _added.clear();
                        }),
                ),
              ],
            ),
            SectionTitle(l10n.parMissingWho),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final m in widget.team.members)
                  ChoiceChip(
                    key: Key('par-who-${m.key}'),
                    label: Text(m.name),
                    selected: _member == m.key,
                    onSelected: (_) => setState(() => _member = m.key),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('par-place'),
              controller: _place,
              maxLength: 200,
              decoration: InputDecoration(labelText: l10n.parMissingPlace),
            ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('par-missing-send'),
              style: FilledButton.styleFrom(
                backgroundColor: Tone.red.colors(context).fill,
              ),
              onPressed: _resource == null || _member == null
                  ? null
                  : () {
                      final nav = Navigator.of(context);
                      unawaited(
                        widget
                            .onSend({
                              'resource': _resource,
                              'member': _member,
                              if (_place.text.trim().isNotEmpty)
                                'place': _place.text.trim(),
                            })
                            .then((ok) {
                              if (ok) nav.pop();
                            }),
                      );
                    },
              child: Text(l10n.parMissingSend),
            ),
          ],
        ),
      ),
    );
  }
}

class _SitrepSheet extends ConsumerStatefulWidget {
  const _SitrepSheet({required this.missionId, required this.onSend});

  final String missionId;
  final Future<bool> Function(Map<String, dynamic> body) onSend;

  @override
  ConsumerState<_SitrepSheet> createState() => _SitrepSheetState();
}

class _SitrepSheetState extends ConsumerState<_SitrepSheet> {
  String? _situation;
  bool _reinforcement = false;
  final _text = TextEditingController();
  String? _transcript;
  int? _voiceSeconds;
  bool _listening = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _speak() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final media = await ref.read(staffCaptureProvider).voice(context);
    if (media == null || !mounted) return;
    setState(() => _listening = true);
    try {
      final lang = ref.read(localeCodeProvider) == 'fr' ? 'fr' : 'ar';
      final heard = await ref
          .read(staffApiProvider)
          .transcribe(widget.missionId, media, lang: lang);
      if (!mounted) return;
      setState(() {
        _transcript = heard.text;
        _voiceSeconds = (media.durationS ?? 1).round().clamp(1, 600);
        _text.text = heard.text;
      });
    } on Object {
      messenger.showSnackBar(SnackBar(content: Text(l10n.parFailed)));
    } finally {
      if (mounted) setState(() => _listening = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        16,
        16,
        16,
        16 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionTitle(l10n.parSitrepTitle),
            for (final k in const ['controlled', 'progress', 'not_controlled'])
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: ChoiceChip(
                  key: Key('par-sit-$k'),
                  label: Text(parSituationLabel(l10n, k)),
                  selected: _situation == k,
                  onSelected: (_) => setState(() => _situation = k),
                ),
              ),
            SwitchListTile(
              key: const Key('par-reinforce'),
              contentPadding: EdgeInsets.zero,
              title: Text(l10n.parReinforcement),
              value: _reinforcement,
              onChanged: (v) => setState(() => _reinforcement = v),
            ),
            OutlinedButton.icon(
              key: const Key('par-mic'),
              onPressed: _listening ? null : () => unawaited(_speak()),
              icon: const Icon(Icons.mic),
              label: Text(
                _listening ? l10n.staffVoiceListening : l10n.parSpeak,
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('par-sitrep-text'),
              controller: _text,
              minLines: 3,
              maxLines: 6,
              maxLength: 2000,
              decoration: InputDecoration(
                labelText: _transcript == null
                    ? l10n.parSitrepText
                    : l10n.parSitrepCorrect,
              ),
            ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('par-sitrep-send'),
              onPressed: _situation == null
                  ? null
                  : () {
                      final nav = Navigator.of(context);
                      unawaited(
                        widget
                            .onSend({
                              'situation': _situation,
                              'reinforcement': _reinforcement,
                              if (_text.text.trim().isNotEmpty)
                                'text': _text.text.trim(),
                              if (_voiceSeconds != null)
                                'voice_seconds': _voiceSeconds,
                              if (_transcript != null)
                                'transcript': _transcript,
                            })
                            .then((ok) {
                              if (ok) nav.pop();
                            }),
                      );
                    },
              child: Text(l10n.parSitrepSend),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExitSheet extends StatefulWidget {
  const _ExitSheet({required this.team, required this.onSend});

  final ParTeam team;
  final Future<bool> Function(List<String> keys) onSend;

  @override
  State<_ExitSheet> createState() => _ExitSheetState();
}

class _ExitSheetState extends State<_ExitSheet> {
  final _out = <String>{};

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final all = widget.team.members.length;
    final complete = _out.length == all;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionTitle(l10n.parExitTitle(_out.length, all)),
            Text(l10n.parExitHint),
            for (final m in widget.team.members)
              CheckboxListTile(
                key: Key('par-out-${m.key}'),
                contentPadding: EdgeInsets.zero,
                title: Text(m.name),
                value: _out.contains(m.key),
                onChanged: (v) => setState(
                  () => v == true ? _out.add(m.key) : _out.remove(m.key),
                ),
              ),
            const SizedBox(height: 8),
            FilledButton(
              key: const Key('par-exit-send'),
              onPressed: !complete
                  ? null
                  : () {
                      final nav = Navigator.of(context);
                      unawaited(
                        widget.onSend(_out.toList()).then((ok) {
                          if (ok) nav.pop();
                        }),
                      );
                    },
              child: Text(
                complete ? l10n.parExitSend : l10n.parHeadcountIncomplete,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
