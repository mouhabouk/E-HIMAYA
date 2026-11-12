import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../prevention/sign_screen.dart' show SignaturePad;
import '../staff_chrome.dart';
import 'inspect_controller.dart';
import 'inspect_models.dart';

/// Opens the inspector's space (phase I3) from the staff app's sign-in screen.
void openInspector(BuildContext context) => unawaited(
  Navigator.of(context)
      .push(MaterialPageRoute<void>(builder: (_) => const InspectHome())),
);

/// The server's refusal, in the inspector's words.
String inspectErrorText(AppLocalizations l10n, String code) => switch (code) {
  'activation_refused' => l10n.inspErrActivationRefused,
  'activation_expired' => l10n.inspErrActivationExpired,
  'already_registered' => l10n.inspErrAlreadyRegistered,
  'mission_not_today' => l10n.inspErrNotToday,
  'mission_cancelled' => l10n.inspErrCancelled,
  'inspection_sealed' => l10n.inspErrSealed,
  'inspection_deleted' => l10n.inspErrDeleted,
  'priority_required' => l10n.inspErrPriority,
  'rate_limited' || 'http_429' => l10n.inspErrRateLimited,
  _ => l10n.inspErrGeneric(code),
};

String inspectSiteKind(AppLocalizations l10n, InspectSite s) =>
    s.target == 'room'
    ? (s.room == 'central' ? l10n.inspRoomCentral : l10n.inspRoomRegional)
    : switch (s.unitKind) {
        'regional_directorate' => l10n.inspUnitRegionalDirectorate,
        'brigade' => l10n.inspUnitBrigade,
        'centre' => l10n.inspUnitCentre,
        'advanced_centre' => l10n.inspUnitAdvancedCentre,
        'guard_post' => l10n.inspUnitGuardPost,
        'beach' => l10n.inspUnitBeach,
        _ => l10n.inspUnitOther,
      };

String inspectAnswerText(AppLocalizations l10n, String a) => switch (a) {
  'ok' => l10n.inspAnswerOk,
  'note' => l10n.inspAnswerNote,
  _ => l10n.inspAnswerKo,
};

String inspectPriorityText(AppLocalizations l10n, String p) => switch (p) {
  'high' => l10n.inspPriorityHigh,
  'medium' => l10n.inspPriorityMedium,
  _ => l10n.inspPriorityLow,
};

Tone _answerTone(String a) => switch (a) {
  'ok' => Tone.green,
  'note' => Tone.amber,
  _ => Tone.red,
};

String _day(DateTime d) =>
    '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

class _ErrorCard extends ConsumerWidget {
  const _ErrorCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final code = ref.watch(inspectControllerProvider.select((s) => s.error));
    if (code == null) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppCard(
        key: const Key('insp-error'),
        color: Tone.red.colors(context).tint,
        child: Text(inspectErrorText(l10n, code)),
      ),
    );
  }
}

class _OfflineStrip extends ConsumerWidget {
  const _OfflineStrip();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(inspectControllerProvider);
    if (!s.offline && s.waiting == 0) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final c = Tone.amber.colors(context);
    return Material(
      color: c.tint,
      child: ListTile(
        key: const Key('insp-offline'),
        leading: Icon(
          s.offline ? Icons.cloud_off : Icons.schedule_send,
          color: c.onTint,
        ),
        title: Text(
          [
            if (s.offline) l10n.inspOffline,
            if (s.waiting > 0) l10n.inspWaiting(s.waiting),
          ].join(' · '),
          style: TextStyle(color: c.onTint),
        ),
        trailing: IconButton(
          key: const Key('insp-retry'),
          tooltip: l10n.inspRetry,
          icon: const Icon(Icons.sync),
          onPressed: s.busy
              ? null
              : () => unawaited(
                  ref.read(inspectControllerProvider.notifier).refresh(),
                ),
        ),
      ),
    );
  }
}

/// The inspector's space: registration and activation, then the missions.
class InspectHome extends ConsumerWidget {
  const InspectHome({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final phase = ref.watch(inspectControllerProvider.select((s) => s.phase));
    return switch (phase) {
      InspectPhase.loading => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      InspectPhase.signedOut => const InspectEntryScreen(),
      InspectPhase.active => const InspectMissionsScreen(),
    };
  }
}

/// The code received by SMS or email activates the phone; without an account, the inspector
/// asks for one first (the general inspectorate decides).
class InspectEntryScreen extends ConsumerStatefulWidget {
  const InspectEntryScreen({super.key});

  @override
  ConsumerState<InspectEntryScreen> createState() => _InspectEntryScreenState();
}

class _InspectEntryScreenState extends ConsumerState<InspectEntryScreen> {
  final _matricule = TextEditingController();
  final _code = TextEditingController();
  final _name = TextEditingController();
  final _organisation = TextEditingController();
  final _phone = TextEditingController();
  final _email = TextEditingController();
  String _kind = 'internal';
  String _via = 'sms';
  bool _registering = false;

  @override
  void initState() {
    super.initState();
    final m = ref.read(inspectControllerProvider).matricule;
    if (m != null) _matricule.text = m;
  }

  @override
  void dispose() {
    for (final c in [_matricule, _code, _name, _organisation, _phone, _email]) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _canRegister {
    if (_matricule.text.trim().length < 2 || _name.text.trim().length < 2) {
      return false;
    }
    if (_kind == 'external' && _organisation.text.trim().length < 2) {
      return false;
    }
    return _via == 'sms'
        ? _phone.text.trim().length >= 8
        : _email.text.contains('@');
  }

  Future<void> _register() async {
    final ok = await ref
        .read(inspectControllerProvider.notifier)
        .register(
          kind: _kind,
          matricule: _matricule.text,
          name: _name.text,
          organisation: _kind == 'external' ? _organisation.text : null,
          phone: _phone.text,
          email: _email.text,
          via: _via,
        );
    if (ok && mounted) setState(() => _registering = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(inspectControllerProvider);
    final c = ref.read(inspectControllerProvider.notifier);
    return Scaffold(
      appBar: StaffAppBar(title: l10n.inspTitle),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Center(
            child: IconTile(Icons.verified, tone: Tone.navy, size: 64),
          ),
          const SizedBox(height: 12),
          Text(
            l10n.inspEntryIntro,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          if (s.wiped)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppCard(
                key: const Key('insp-wiped'),
                color: Tone.amber.colors(context).tint,
                child: Text(l10n.inspWiped),
              ),
            ),
          if (s.destination != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppCard(
                key: const Key('insp-registered'),
                color: Tone.green.colors(context).tint,
                child: Text(l10n.inspRegistered(s.destination!)),
              ),
            ),
          const _ErrorCard(),
          TextField(
            key: const Key('insp-matricule'),
            controller: _matricule,
            decoration: InputDecoration(labelText: l10n.inspMatricule),
            textInputAction: TextInputAction.next,
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          if (!_registering) ...[
            TextField(
              key: const Key('insp-code'),
              controller: _code,
              decoration: InputDecoration(
                labelText: l10n.inspCode,
                helperText: l10n.inspCodeHelp,
              ),
              textCapitalization: TextCapitalization.characters,
              inputFormatters: [LengthLimitingTextInputFormatter(12)],
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),
            ToneButton(
              action: BarAction(
                key: const Key('insp-activate'),
                label: l10n.inspActivate,
                icon: Icons.key,
                tone: Tone.navy,
                onPressed:
                    s.busy ||
                        _matricule.text.trim().length < 2 ||
                        _code.text.trim().length < 8
                    ? null
                    : () => unawaited(c.activate(_matricule.text, _code.text)),
              ),
            ),
            const SizedBox(height: 20),
            TextButton(
              key: const Key('insp-to-register'),
              onPressed: () => setState(() => _registering = true),
              child: Text(l10n.inspNoAccount),
            ),
          ] else ...[
            SectionTitle(l10n.inspRegisterTitle),
            SegmentedButton<String>(
              key: const Key('insp-kind'),
              segments: [
                ButtonSegment(
                  value: 'internal',
                  label: Text(l10n.inspInternal),
                ),
                ButtonSegment(
                  value: 'external',
                  label: Text(l10n.inspExternal),
                ),
              ],
              selected: {_kind},
              onSelectionChanged: (v) => setState(() => _kind = v.first),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('insp-name'),
              controller: _name,
              decoration: InputDecoration(labelText: l10n.inspName),
              onChanged: (_) => setState(() {}),
            ),
            if (_kind == 'external') ...[
              const SizedBox(height: 12),
              TextField(
                key: const Key('insp-organisation'),
                controller: _organisation,
                decoration: InputDecoration(labelText: l10n.inspOrganisation),
                onChanged: (_) => setState(() {}),
              ),
            ],
            const SizedBox(height: 12),
            Text(l10n.inspVia),
            const SizedBox(height: 6),
            SegmentedButton<String>(
              key: const Key('insp-via'),
              segments: [
                ButtonSegment(value: 'sms', label: Text(l10n.inspViaSms)),
                ButtonSegment(value: 'email', label: Text(l10n.inspViaEmail)),
              ],
              selected: {_via},
              onSelectionChanged: (v) => setState(() => _via = v.first),
            ),
            const SizedBox(height: 12),
            if (_via == 'sms')
              TextField(
                key: const Key('insp-phone'),
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(labelText: l10n.inspPhone),
                onChanged: (_) => setState(() {}),
              )
            else
              TextField(
                key: const Key('insp-email'),
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                decoration: InputDecoration(labelText: l10n.inspEmail),
                onChanged: (_) => setState(() {}),
              ),
            const SizedBox(height: 16),
            ToneButton(
              action: BarAction(
                key: const Key('insp-register'),
                label: l10n.inspRegister,
                icon: Icons.person_add,
                tone: Tone.navy,
                onPressed: s.busy || !_canRegister
                    ? null
                    : () => unawaited(_register()),
              ),
            ),
            TextButton(
              onPressed: () => setState(() => _registering = false),
              child: Text(l10n.inspHaveCode),
            ),
          ],
        ],
      ),
    );
  }
}

/// «مهامّي»: the orders assigned to the inspector, place by place.
class InspectMissionsScreen extends ConsumerWidget {
  const InspectMissionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(inspectControllerProvider);
    final c = ref.read(inspectControllerProvider.notifier);
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.inspMissionsTitle,
        subtitle: s.name,
        actions: [
          PopupMenuButton<String>(
            key: const Key('insp-menu'),
            onSelected: (_) => unawaited(c.signOut()),
            itemBuilder: (_) => [
              PopupMenuItem(
                key: const Key('insp-sign-out'),
                value: 'out',
                child: Text(l10n.inspSignOut),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          const _OfflineStrip(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: c.refresh,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (s.kind == 'external' && s.expiresOn != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Pill(
                        l10n.inspAccountUntil(_day(s.expiresOn!)),
                        tone: Tone.slate,
                        icon: Icons.event,
                      ),
                    ),
                  const _ErrorCard(),
                  if (s.missions.isEmpty)
                    AppCard(
                      key: const Key('insp-no-missions'),
                      child: Text(l10n.inspNoMissions),
                    ),
                  for (final m in s.missions) _MissionCard(mission: m),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MissionCard extends ConsumerWidget {
  const _MissionCard({required this.mission});

  final InspectMission mission;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(inspectControllerProvider);
    final n = Neutrals.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppCard(
        key: Key('insp-mission-${mission.id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const IconTile(Icons.assignment, tone: Tone.navy),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        mission.ref,
                        style: Theme.of(context).textTheme.titleMedium,
                        textDirection: TextDirection.ltr,
                      ),
                      Text(
                        '${_day(mission.onDate)} · ${mission.atTime} · ${mission.kind == 'surprise' ? l10n.inspKindSurprise : l10n.inspKindPeriodic}',
                        style: TextStyle(color: n.muted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            for (final site in mission.sites)
              _SiteTile(
                mission: mission,
                site: site,
                draft: s.draftOfSite(site.id),
              ),
          ],
        ),
      ),
    );
  }
}

class _SiteTile extends ConsumerWidget {
  const _SiteTile({required this.mission, required this.site, this.draft});

  final InspectMission mission;
  final InspectSite site;
  final InspectDraft? draft;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final busy = ref.watch(inspectControllerProvider.select((s) => s.busy));
    final d = draft;
    final (label, tone) = switch (d?.state) {
      DraftState.sent => (l10n.inspStateSent, Tone.green),
      DraftState.queued => (l10n.inspStateQueued, Tone.amber),
      DraftState.editing => (
        l10n.inspStateProgress(d!.answered, d.total),
        Tone.sky,
      ),
      null when site.inspectionStatus == 'submitted' => (
        l10n.inspStateSent,
        Tone.green,
      ),
      null => (l10n.inspStateNew, Tone.slate),
    };
    return ListTile(
      key: Key('insp-site-${site.id}'),
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        site.target == 'room' ? Icons.headset_mic : Icons.location_city,
      ),
      title: Text(site.name),
      subtitle: Text(inspectSiteKind(l10n, site)),
      trailing: Pill(label, tone: tone),
      onTap: busy
          ? null
          : () async {
              final c = ref.read(inspectControllerProvider.notifier);
              final opened = await c.open(mission, site);
              if (opened == null || !context.mounted) return;
              await Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) =>
                      InspectRunScreen(inspectionId: opened.inspectionId),
                ),
              );
            },
    );
  }
}

/// The checklist of a place, axis by axis, then the presence and the exit drill. Every change
/// stays on the phone; the answers go to the server when the network allows.
class InspectRunScreen extends ConsumerStatefulWidget {
  const InspectRunScreen({super.key, required this.inspectionId});

  final String inspectionId;

  @override
  ConsumerState<InspectRunScreen> createState() => _InspectRunScreenState();
}

class _InspectRunScreenState extends ConsumerState<InspectRunScreen> {
  Timer? _debounce;
  late final InspectController _c = ref.read(
    inspectControllerProvider.notifier,
  );

  @override
  void initState() {
    super.initState();
    _c; // Read while mounted: dispose() sends the answers with it.
  }

  @override
  void dispose() {
    _debounce?.cancel();
    unawaited(_c.sync(widget.inspectionId));
    super.dispose();
  }

  Future<void> _edit(InspectDraft Function(InspectDraft) change) async {
    await ref
        .read(inspectControllerProvider.notifier)
        .edit(widget.inspectionId, change);
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(seconds: 3),
      () => unawaited(
        ref.read(inspectControllerProvider.notifier).sync(widget.inspectionId),
      ),
    );
  }

  int? _int(String v) => v.trim().isEmpty ? null : int.tryParse(v.trim());

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final d = ref.watch(
      inspectControllerProvider.select((s) => s.drafts[widget.inspectionId]),
    );
    if (d == null) return const Scaffold();
    final locked = d.state != DraftState.editing;
    final n = Neutrals.of(context);
    return Scaffold(
      appBar: StaffAppBar(title: d.siteName, subtitle: d.missionRef),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          const _ErrorCard(),
          if (locked) _SealedCard(draft: d),
          Text(
            l10n.inspAnswered(d.answered, d.total),
            key: const Key('insp-answered'),
            style: TextStyle(color: n.muted),
          ),
          for (final axis in d.profile.axes) ...[
            SectionTitle(axis.name),
            for (final item in d.profile.itemsOf(axis.key))
              _ItemRow(
                item: item,
                value: d.answers[item.key],
                enabled: !locked,
                onChanged: (v) => _edit(
                  (x) => x.copyWith(answers: {...x.answers, item.key: v}),
                ),
              ),
          ],
          SectionTitle(l10n.inspPresenceTitle),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  key: const Key('insp-present'),
                  initialValue: d.present?.toString() ?? '',
                  enabled: !locked,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  decoration: InputDecoration(labelText: l10n.inspPresent),
                  onChanged: (v) =>
                      _edit((x) => x.copyWith(present: () => _int(v))),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextFormField(
                  key: const Key('insp-expected'),
                  initialValue: d.expected?.toString() ?? '',
                  enabled: !locked,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  decoration: InputDecoration(labelText: l10n.inspExpected),
                  onChanged: (v) => _edit(
                    (x) => x.copyWith(
                      expected: () {
                        final e = _int(v);
                        return e == null || e < 1 ? null : e;
                      },
                    ),
                  ),
                ),
              ),
            ],
          ),
          SectionTitle(l10n.inspExitTitle),
          _ExitDrill(
            seconds: d.exitSeconds,
            enabled: !locked,
            onChanged: (v) => _edit((x) => x.copyWith(exitSeconds: () => v)),
          ),
          const SizedBox(height: 20),
          ToneButton(
            action: BarAction(
              key: const Key('insp-to-sign'),
              label: locked ? l10n.inspSeeReport : l10n.inspToSign,
              icon: Icons.draw,
              tone: Tone.navy,
              onPressed: () => unawaited(
                Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        InspectSignScreen(inspectionId: widget.inspectionId),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ItemRow extends StatelessWidget {
  const _ItemRow({
    required this.item,
    required this.value,
    required this.enabled,
    required this.onChanged,
  });

  final ProfileItem item;
  final String? value;
  final bool enabled;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: AppCard(
        padding: const EdgeInsets.all(12),
        borderColor: value == null
            ? null
            : _answerTone(value!).colors(context).fill,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(item.text),
            const SizedBox(height: 8),
            Row(
              children: [
                for (final a in inspectAnswers) ...[
                  if (a != inspectAnswers.first) const SizedBox(width: 6),
                  Expanded(
                    child: _AnswerButton(
                      key: Key('${item.key}-$a'),
                      label: inspectAnswerText(l10n, a),
                      tone: _answerTone(a),
                      selected: value == a,
                      onPressed: enabled ? () => onChanged(a) : null,
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _AnswerButton extends StatelessWidget {
  const _AnswerButton({
    super.key,
    required this.label,
    required this.tone,
    required this.selected,
    required this.onPressed,
  });

  final String label;
  final Tone tone;
  final bool selected;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final c = tone.colors(context);
    return Semantics(
      selected: selected,
      button: true,
      child: OutlinedButton(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 48),
          backgroundColor: selected ? c.fill : null,
          foregroundColor: selected ? c.onFill : c.onTint,
          side: BorderSide(color: c.fill),
          padding: const EdgeInsets.symmetric(horizontal: 4),
        ),
        onPressed: onPressed,
        child: Text(label, textAlign: TextAlign.center),
      ),
    );
  }
}

/// The exit drill: a stopwatch started at the alarm and stopped when the first vehicle leaves,
/// or seconds typed by hand.
class _ExitDrill extends StatefulWidget {
  const _ExitDrill({
    required this.seconds,
    required this.enabled,
    required this.onChanged,
  });

  final int? seconds;
  final bool enabled;
  final ValueChanged<int?> onChanged;

  @override
  State<_ExitDrill> createState() => _ExitDrillState();
}

class _ExitDrillState extends State<_ExitDrill> {
  final _watch = Stopwatch();
  Timer? _tick;
  late final _typed = TextEditingController(
    text: widget.seconds?.toString() ?? '',
  );

  @override
  void dispose() {
    _tick?.cancel();
    _typed.dispose();
    super.dispose();
  }

  void _toggle() {
    if (_watch.isRunning) {
      _watch.stop();
      _tick?.cancel();
      final s = _watch.elapsed.inSeconds.clamp(0, 3600);
      _typed.text = '$s';
      widget.onChanged(s);
    } else {
      _watch
        ..reset()
        ..start();
      _tick = Timer.periodic(
        const Duration(seconds: 1),
        (_) => setState(() {}),
      );
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final running = _watch.isRunning;
    return Row(
      children: [
        Expanded(
          child: TextField(
            key: const Key('insp-exit'),
            controller: _typed,
            enabled: widget.enabled && !running,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: InputDecoration(labelText: l10n.inspExitSeconds),
            onChanged: (v) {
              final s = int.tryParse(v.trim());
              widget.onChanged(s?.clamp(0, 3600));
            },
          ),
        ),
        const SizedBox(width: 12),
        FilledButton.icon(
          key: const Key('insp-exit-watch'),
          onPressed: widget.enabled ? _toggle : null,
          icon: Icon(running ? Icons.stop : Icons.timer),
          label: Text(
            running
                ? l10n.inspExitStop(_watch.elapsed.inSeconds)
                : l10n.inspExitStart,
          ),
        ),
      ],
    );
  }
}

class _SealedCard extends StatelessWidget {
  const _SealedCard({required this.draft});

  final InspectDraft draft;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final sent = draft.state == DraftState.sent;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppCard(
        key: const Key('insp-sealed'),
        color: (sent ? Tone.green : Tone.amber).colors(context).tint,
        child: Text(
          sent
              ? l10n.inspReceipt(
                  draft.receipt ?? '—',
                  draft.verdict ?? '—',
                  draft.score?.toString() ?? '—',
                )
              : l10n.inspQueuedNote,
        ),
      ),
    );
  }
}

/// The summary, the recommendations, the head of the place and both signatures; signing seals
/// the report on the phone and sends it now or when the network comes back.
class InspectSignScreen extends ConsumerStatefulWidget {
  const InspectSignScreen({super.key, required this.inspectionId});

  final String inspectionId;

  @override
  ConsumerState<InspectSignScreen> createState() => _InspectSignScreenState();
}

class _InspectSignScreenState extends ConsumerState<InspectSignScreen> {
  Future<void> _edit(InspectDraft Function(InspectDraft) change) => ref
      .read(inspectControllerProvider.notifier)
      .edit(widget.inspectionId, change);

  Future<void> _addRec(InspectDraft d) async {
    final rec = await showModalBottomSheet<RecDraft>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _RecSheet(profile: d.profile),
    );
    if (rec != null) await _edit((x) => x.copyWith(recs: [...x.recs, rec]));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(inspectControllerProvider);
    final d = s.drafts[widget.inspectionId];
    if (d == null) return const Scaffold();
    final locked = d.state != DraftState.editing;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.inspSignTitle, subtitle: d.siteName),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          const _ErrorCard(),
          if (locked) _SealedCard(draft: d),
          SectionTitle(l10n.inspSummary),
          TextFormField(
            key: const Key('insp-summary'),
            initialValue: d.summary,
            enabled: !locked,
            maxLines: 4,
            maxLength: 4000,
            decoration: InputDecoration(hintText: l10n.inspSummaryHint),
            onChanged: (v) => _edit((x) => x.copyWith(summary: v)),
          ),
          SectionTitle(l10n.inspRecommendations),
          for (final (i, r) in d.recs.indexed)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: AppCard(
                key: Key('insp-rec-$i'),
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 6,
                            children: [
                              Pill(
                                r.kind == 'general'
                                    ? l10n.inspRecGeneral
                                    : (d.profile.item(r.itemKey ?? '')?.text ??
                                          l10n.inspRecDetailed),
                                tone: Tone.slate,
                              ),
                              if (r.priority != null)
                                Pill(
                                  inspectPriorityText(l10n, r.priority!),
                                  tone: r.priority == 'high'
                                      ? Tone.red
                                      : r.priority == 'medium'
                                      ? Tone.amber
                                      : Tone.sky,
                                ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(r.text),
                        ],
                      ),
                    ),
                    if (!locked)
                      IconButton(
                        tooltip: l10n.inspRemove,
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () => unawaited(
                          _edit(
                            (x) => x.copyWith(recs: [...x.recs]..removeAt(i)),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          if (!locked)
            OutlinedButton.icon(
              key: const Key('insp-add-rec'),
              onPressed: () => unawaited(_addRec(d)),
              icon: const Icon(Icons.add),
              label: Text(l10n.inspAddRec),
            ),
          SectionTitle(l10n.inspHeadTitle),
          TextFormField(
            key: const Key('insp-head-name'),
            initialValue: d.headName,
            enabled: !locked,
            decoration: InputDecoration(labelText: l10n.inspHeadName),
            onChanged: (v) => _edit((x) => x.copyWith(headName: v)),
          ),
          SectionTitle(l10n.inspSignInspector),
          SignaturePad(
            key: const Key('insp-pad-inspector'),
            png: d.inspectorSignature,
            enabled: !locked,
            onSigned: (png) => unawaited(
              _edit((x) => x.copyWith(inspectorSignature: () => png)),
            ),
          ),
          SectionTitle(l10n.inspSignHead),
          SignaturePad(
            key: const Key('insp-pad-head'),
            png: d.headSignature,
            enabled: !locked,
            onSigned: (png) =>
                unawaited(_edit((x) => x.copyWith(headSignature: () => png))),
          ),
          const SizedBox(height: 20),
          if (!locked)
            ToneButton(
              action: BarAction(
                key: const Key('insp-sign'),
                label: l10n.inspSignSend,
                icon: Icons.send,
                tone: Tone.green,
                onPressed: s.busy || !d.signable
                    ? null
                    : () => unawaited(
                        ref
                            .read(inspectControllerProvider.notifier)
                            .sign(widget.inspectionId),
                      ),
              ),
            ),
          if (!locked && !d.signable)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                l10n.inspSignNeeds,
                key: const Key('insp-sign-needs'),
                textAlign: TextAlign.center,
                style: TextStyle(color: Neutrals.of(context).muted),
              ),
            ),
        ],
      ),
    );
  }
}

class _RecSheet extends StatefulWidget {
  const _RecSheet({required this.profile});

  final InspectProfile profile;

  @override
  State<_RecSheet> createState() => _RecSheetState();
}

class _RecSheetState extends State<_RecSheet> {
  final _text = TextEditingController();
  String _kind = 'detailed';
  String? _item;
  String? _priority;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  bool get _ready =>
      _text.text.trim().length >= 2 &&
      (_kind == 'general' || (_item != null && _priority != null));

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
            Text(
              l10n.inspAddRec,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              key: const Key('insp-rec-kind'),
              segments: [
                ButtonSegment(
                  value: 'detailed',
                  label: Text(l10n.inspRecDetailed),
                ),
                ButtonSegment(
                  value: 'general',
                  label: Text(l10n.inspRecGeneral),
                ),
              ],
              selected: {_kind},
              onSelectionChanged: (v) => setState(() => _kind = v.first),
            ),
            if (_kind == 'detailed') ...[
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('insp-rec-item'),
                initialValue: _item,
                isExpanded: true,
                decoration: InputDecoration(labelText: l10n.inspRecItem),
                items: [
                  for (final i in widget.profile.items)
                    DropdownMenuItem(
                      value: i.key,
                      child: Text(i.text, overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (v) => setState(() => _item = v),
              ),
              const SizedBox(height: 12),
              SegmentedButton<String>(
                key: const Key('insp-rec-priority'),
                emptySelectionAllowed: true,
                segments: [
                  for (final p in inspectPriorities)
                    ButtonSegment(
                      value: p,
                      label: Text(inspectPriorityText(l10n, p)),
                    ),
                ],
                selected: {?_priority},
                onSelectionChanged: (v) =>
                    setState(() => _priority = v.isEmpty ? null : v.first),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              key: const Key('insp-rec-text'),
              controller: _text,
              maxLines: 3,
              maxLength: 600,
              decoration: InputDecoration(labelText: l10n.inspRecText),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 8),
            ToneButton(
              action: BarAction(
                key: const Key('insp-rec-save'),
                label: l10n.inspRecSave,
                icon: Icons.check,
                tone: Tone.navy,
                onPressed: _ready
                    ? () => Navigator.of(context).pop(
                        RecDraft(
                          kind: _kind,
                          text: _text.text.trim(),
                          itemKey: _kind == 'detailed' ? _item : null,
                          priority: _kind == 'detailed' ? _priority : null,
                        ),
                      )
                    : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
