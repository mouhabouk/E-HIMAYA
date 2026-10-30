import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_capture.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';
import 'field_widgets.dart';

/// The mission flow after Yamen's review (phase F, docs/phase-f/design-f.md): the round button
/// recorded by a long press with an undo window, «تجاوز المرحلة», «بدون تدخل» with a double
/// confirmation, the nature chips, the toll, the spoken intervention report, a mission opened from
/// the field, and the charter of an agent activated with a code.

/// The natures a team chooses from (the room's category is chosen first).
const crewNatures = [
  'fire',
  'flood',
  'traffic_accident',
  'rescue',
  'medical',
  'drowning',
  'landslide',
  'chemical_leak',
  'animal',
  'other',
];

const skipReasons = [
  'no_transport',
  'other_transport',
  'refused_transport',
  'not_needed',
  'other',
];

const noInterventionReasons = [
  'false_alarm',
  'put_out_before',
  'other_agency',
  'place_not_found',
  'cancelled',
  'other',
];

const damages = ['none', 'minor', 'moderate', 'major', 'total'];

/// The version of the charter the agent accepts (kept with the acceptance).
const charterVersion = '2026.1';

String natureLabel(AppLocalizations l10n, String n) => switch (n) {
  'fire' => l10n.staffNatureFire,
  'flood' => l10n.staffNatureFlood,
  'traffic_accident' => l10n.staffNatureTraffic,
  'rescue' => l10n.staffNatureRescue,
  'medical' => l10n.staffNatureMedical,
  'drowning' => l10n.staffNatureDrowning,
  'landslide' => l10n.staffNatureLandslide,
  'chemical_leak' => l10n.staffNatureChemical,
  'animal' => l10n.staffNatureAnimal,
  _ => l10n.staffNatureOther,
};

String skipReasonLabel(AppLocalizations l10n, String r) => switch (r) {
  'no_transport' => l10n.staffSkipNoTransport,
  'other_transport' => l10n.staffSkipOtherTransport,
  'refused_transport' => l10n.staffSkipRefused,
  'not_needed' => l10n.staffSkipNotNeeded,
  _ => l10n.staffReasonOther,
};

String noInterventionLabel(AppLocalizations l10n, String r) => switch (r) {
  'false_alarm' => l10n.staffNoIntFalseAlarm,
  'put_out_before' => l10n.staffNoIntPutOut,
  'other_agency' => l10n.staffNoIntOtherAgency,
  'place_not_found' => l10n.staffNoIntNotFound,
  'cancelled' => l10n.staffNoIntCancelled,
  _ => l10n.staffReasonOther,
};

String damageLabel(AppLocalizations l10n, String d) => switch (d) {
  'none' => l10n.staffDamageNone,
  'minor' => l10n.staffDamageMinor,
  'moderate' => l10n.staffDamageModerate,
  'major' => l10n.staffDamageMajor,
  _ => l10n.staffDamageTotal,
};

/// The text, icon and colour of each step of the round button (design-f, approved colours).
(String, IconData, Tone) stepLook(AppLocalizations l10n, String step) =>
    switch (step) {
      'en_route' => (l10n.staffFlowLeftUnit, Icons.directions_car, Tone.navy),
      'on_scene' => (l10n.staffFlowArrived, Icons.place, Tone.orange),
      'left_scene' => (l10n.staffFlowLeftScene, Icons.logout, Tone.purple),
      'at_hospital' => (
        l10n.staffFlowAtHospital,
        Icons.local_hospital,
        Tone.pink,
      ),
      'available' => (l10n.staffFlowAvailable, Icons.check_circle, Tone.teal),
      _ => (l10n.staffFlowBackAtUnit, Icons.home_work, Tone.green),
    };

/// The room's category as the first nature.
String natureOf(Mission m) =>
    m.crewNature ??
    switch (m.category?.wire) {
      final c? when crewNatures.contains(c) => c,
      _ => 'other',
    };

// ------------------------------------------------------------------ the round button

/// A big round button locked between steps: the step is recorded by holding it [holdMs]; a ring
/// fills while it is held. Screen readers get the long-press action.
class RoundHoldButton extends StatefulWidget {
  const RoundHoldButton({
    super.key,
    required this.label,
    required this.icon,
    required this.tone,
    required this.holdMs,
    required this.onConfirmed,
    this.caption,
  });

  final String label;
  final String? caption;
  final IconData icon;
  final Tone tone;
  final int holdMs;
  final VoidCallback? onConfirmed;

  @override
  State<RoundHoldButton> createState() => _RoundHoldButtonState();
}

class _RoundHoldButtonState extends State<RoundHoldButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _hold = AnimationController(
    vsync: this,
    duration: Duration(milliseconds: widget.holdMs),
  )..addStatusListener(_done);

  void _done(AnimationStatus s) {
    if (s != AnimationStatus.completed) return;
    unawaited(HapticFeedback.heavyImpact());
    widget.onConfirmed?.call();
    _hold.value = 0;
  }

  @override
  void didUpdateWidget(RoundHoldButton old) {
    super.didUpdateWidget(old);
    _hold.duration = Duration(milliseconds: widget.holdMs);
  }

  @override
  void dispose() {
    _hold.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = widget.tone.colors(context);
    final enabled = widget.onConfirmed != null;
    return Column(
      children: [
        Semantics(
          button: true,
          enabled: enabled,
          label: '${widget.label}. ${l10n.staffFlowHoldHint}',
          onLongPress: enabled ? widget.onConfirmed : null,
          excludeSemantics: true,
          child: Listener(
            onPointerDown: enabled ? (_) => _hold.forward(from: 0) : null,
            // The finger can still be down when the recorded step replaces this button.
            onPointerUp: (_) {
              if (mounted && _hold.status != AnimationStatus.completed) {
                _hold.reverse();
              }
            },
            onPointerCancel: (_) {
              if (mounted) _hold.reverse();
            },
            child: AnimatedBuilder(
              animation: _hold,
              builder: (context, _) => SizedBox(
                width: 210,
                height: 210,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox.expand(
                      child: CircularProgressIndicator(
                        value: _hold.value,
                        strokeWidth: 10,
                        color: c.onTint,
                        backgroundColor: c.tint,
                      ),
                    ),
                    Container(
                      width: 180,
                      height: 180,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: enabled ? c.fill : c.tint,
                        boxShadow: const [
                          BoxShadow(blurRadius: 8, color: Color(0x33000000)),
                        ],
                      ),
                      padding: const EdgeInsets.all(14),
                      // Large text sizes shrink to the circle instead of overflowing it.
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: SizedBox(
                          width: 152,
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(widget.icon, size: 34, color: c.onFill),
                              const SizedBox(height: 6),
                              Text(
                                widget.label,
                                key: const Key('round-step-label'),
                                textAlign: TextAlign.center,
                                maxLines: 2,
                                style: TextStyle(
                                  color: c.onFill,
                                  fontSize: 20,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Icon(Icons.lock, size: 16, color: c.onFill),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          widget.caption ?? l10n.staffFlowHoldHint,
          textAlign: TextAlign.center,
          style: TextStyle(color: Neutrals.of(context).muted),
        ),
      ],
    );
  }
}

/// The step that waits for its undo window: «سُجّل … · تراجع (N)».
class UndoBar extends ConsumerStatefulWidget {
  const UndoBar({super.key, required this.staged});

  final StagedStep staged;

  @override
  ConsumerState<UndoBar> createState() => _UndoBarState();
}

class _UndoBarState extends ConsumerState<UndoBar> {
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(
      const Duration(seconds: 1),
      (_) => mounted ? setState(() {}) : null,
    );
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final left = widget.staged.deadline.difference(DateTime.now()).inSeconds;
    final (label, _, tone) = stepLook(l10n, widget.staged.step);
    return AppCard(
      key: const Key('undo-bar'),
      color: tone.colors(context).tint,
      child: Row(
        children: [
          Expanded(
            child: Text(
              l10n.staffFlowRecorded(label, hhmm(widget.staged.at)),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          TextButton.icon(
            key: const Key('undo-step'),
            onPressed: ref.read(staffControllerProvider.notifier).undo,
            icon: const Icon(Icons.undo),
            label: Text(l10n.staffFlowUndo(left < 0 ? 0 : left)),
          ),
        ],
      ),
    );
  }
}

/// The round button of the mission, the undo bar, and «تجاوز المرحلة» and «بدون تدخل» under it.
class MissionFlowPanel extends ConsumerWidget {
  const MissionFlowPanel({super.key, required this.mission, this.caption});

  final Mission mission;
  final String? caption;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = ref.read(staffControllerProvider.notifier);
    final m = mission;
    final staged = s.staged?.missionId == m.id ? s.staged : null;
    final step = m.nextStep;
    final children = <Widget>[];
    if (staged != null) children.add(UndoBar(staged: staged));
    if (step != null && staged == null) {
      final (label, icon, tone) = stepLook(l10n, step);
      children.add(
        Center(
          child: RoundHoldButton(
            key: Key('step-$step'),
            label: label,
            icon: icon,
            tone: tone,
            holdMs: s.me?.holdMs ?? 1500,
            caption: caption,
            onConfirmed: s.busy
                ? null
                : () async {
                    GeoPoint? at;
                    if (step == 'en_route' || step == 'on_scene') {
                      at = await ref
                          .read(locationServiceProvider)
                          .bestEffort(timeout: const Duration(seconds: 2));
                    }
                    c.stage(m.id, step, at: at);
                  },
          ),
        ),
      );
    }
    if (staged == null && (m.canSkip || m.canEndWithout)) {
      children.add(
        Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Row(
            children: [
              if (m.canSkip)
                Expanded(
                  child: OutlinedButton.icon(
                    key: const Key('flow-skip'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(52),
                    ),
                    onPressed: () =>
                        unawaited(_skip(context, ref, m, m.nextStep!)),
                    icon: const Icon(Icons.skip_next),
                    label: Text(l10n.staffFlowSkip),
                  ),
                ),
              if (m.canSkip && m.canEndWithout) const SizedBox(width: 8),
              if (m.canEndWithout)
                Expanded(
                  child: OutlinedButton.icon(
                    key: const Key('flow-no-intervention'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(52),
                      foregroundColor: Tone.red.colors(context).onTint,
                    ),
                    onPressed: () => unawaited(_endWithout(context, ref, m)),
                    icon: const Icon(Icons.block),
                    label: Text(l10n.staffFlowNoIntervention),
                  ),
                ),
            ],
          ),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    );
  }
}

Future<String?> _pickReason(
  BuildContext context,
  String title,
  List<String> reasons,
  String Function(String) label,
  String keyPrefix,
) => showModalBottomSheet<String>(
  context: context,
  showDragHandle: true,
  builder: (context) => SafeArea(
    child: ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final r in reasons)
          ListTile(
            key: Key('$keyPrefix-$r'),
            title: Text(label(r)),
            onTap: () => Navigator.of(context).pop(r),
          ),
      ],
    ),
  ),
);

Future<void> _skip(
  BuildContext context,
  WidgetRef ref,
  Mission m,
  String step,
) async {
  final l10n = AppLocalizations.of(context);
  final (label, _, _) = stepLook(l10n, step);
  final reason = await _pickReason(
    context,
    l10n.staffFlowSkipWhy(label),
    skipReasons,
    (r) => skipReasonLabel(l10n, r),
    'skip-reason',
  );
  if (reason == null) return;
  await ref.read(staffControllerProvider.notifier).skip(m.id, step, reason);
}

/// «بدون تدخل»: the reason, then a second confirmation; the toll follows.
Future<void> _endWithout(BuildContext context, WidgetRef ref, Mission m) async {
  final l10n = AppLocalizations.of(context);
  final reason = await _pickReason(
    context,
    l10n.staffFlowNoInterventionWhy,
    noInterventionReasons,
    (r) => noInterventionLabel(l10n, r),
    'no-int-reason',
  );
  if (reason == null || !context.mounted) return;
  final sure = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(l10n.staffFlowNoInterventionConfirm),
      content: Text(noInterventionLabel(l10n, reason)),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(l10n.actionCancel),
        ),
        FilledButton(
          key: const Key('no-int-confirm'),
          style: FilledButton.styleFrom(
            backgroundColor: Tone.red.colors(context).fill,
          ),
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(l10n.staffFlowNoInterventionYes),
        ),
      ],
    ),
  );
  if (sure != true) return;
  final ok = await ref
      .read(staffControllerProvider.notifier)
      .endWithout(m.id, reason);
  if (ok && context.mounted) push(context, TollScreen(missionId: m.id));
}

// ------------------------------------------------------------------ nature

/// The intervention's nature: the room's category first, the leader corrects it; an agent of the
/// crew reads it.
class NatureChips extends ConsumerWidget {
  const NatureChips({super.key, required this.mission, required this.readOnly});

  final Mission mission;
  final bool readOnly;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final chosen = natureOf(mission);
    return AppCard(
      key: const Key('nature-chips'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionTitle(l10n.staffNature),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              for (final n in crewNatures)
                if (!readOnly || n == chosen)
                  ChoiceChip(
                    key: Key('nature-$n'),
                    label: Text(natureLabel(l10n, n)),
                    selected: n == chosen,
                    // The chosen one stays enabled so it reads as chosen, not as greyed out.
                    onSelected: readOnly
                        ? null
                        : (_) {
                            if (n == chosen) return;
                            unawaited(
                              ref
                                  .read(staffControllerProvider.notifier)
                                  .nature(mission.id, n),
                            );
                          },
                  ),
            ],
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ mission point and details

/// The point the room picked (or the incident's centre) and the copy of its coordinates; the route
/// is the quick button under the card.
class MissionPointCard extends ConsumerWidget {
  const MissionPointCard({super.key, required this.mission});

  final Mission mission;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final p = mission.destination;
    if (p == null) return const SizedBox.shrink();
    final coords = '${p.lat.toStringAsFixed(6)}, ${p.lon.toStringAsFixed(6)}';
    return AppCard(
      key: const Key('mission-point'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconTile(
                Icons.my_location,
                tone: mission.target != null ? Tone.red : Tone.slate,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      mission.target != null
                          ? l10n.staffPointFromRoom
                          : l10n.staffPointIncident,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    Directionality(
                      textDirection: TextDirection.ltr,
                      child: Text(coords, key: const Key('mission-coords')),
                    ),
                    if (mission.targetNote != null) Text(mission.targetNote!),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  key: const Key('point-copy'),
                  onPressed: () async {
                    await Clipboard.setData(ClipboardData(text: coords));
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(l10n.staffPointCopied)),
                      );
                    }
                  },
                  icon: const Icon(Icons.copy),
                  label: Text(l10n.staffPointCopy),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// The agent of the crew reads the mission; only the leader's phone records it.
class ReadOnlyBanner extends StatelessWidget {
  const ReadOnlyBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AppCard(
      key: const Key('read-only'),
      color: Tone.sky.colors(context).tint,
      child: Row(
        children: [
          const Icon(Icons.visibility),
          const SizedBox(width: 10),
          Expanded(child: Text(l10n.staffReadOnly)),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ spoken text, corrected

/// A text the leader types, or speaks: the audio goes to the platform to be transcribed and is
/// deleted there; the text comes back here to be corrected before it is sent.
class SpokenTextField extends ConsumerStatefulWidget {
  const SpokenTextField({
    super.key,
    required this.missionId,
    required this.controller,
    required this.label,
    required this.onVoice,
    this.minLines = 4,
  });

  final String missionId;
  final TextEditingController controller;
  final String label;
  final int minLines;

  /// The transcript's id, or null when the leader cleared it and typed instead.
  final ValueChanged<String?> onVoice;

  @override
  ConsumerState<SpokenTextField> createState() => _SpokenTextFieldState();
}

class _SpokenTextFieldState extends ConsumerState<SpokenTextField> {
  bool _listening = false;

  Future<void> _speak() async {
    final media = await ref.read(staffCaptureProvider).voice(context);
    if (media == null || !mounted) return;
    setState(() => _listening = true);
    final lang = ref.read(localeCodeProvider) == 'fr' ? 'fr' : 'ar';
    final heard = await ref
        .read(staffControllerProvider.notifier)
        .transcribe(widget.missionId, media, lang);
    if (!mounted) return;
    setState(() => _listening = false);
    if (heard == null) return;
    widget.controller.text = heard.text;
    widget.onVoice(heard.voiceId);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          key: const Key('spoken-text'),
          controller: widget.controller,
          minLines: widget.minLines,
          maxLines: 12,
          maxLength: 4000,
          decoration: InputDecoration(labelText: widget.label),
        ),
        OutlinedButton.icon(
          key: const Key('spoken-mic'),
          onPressed: _listening ? null : () => unawaited(_speak()),
          icon: _listening
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.mic),
          label: Text(
            _listening ? l10n.staffVoiceListening : l10n.staffVoiceSpeak,
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            l10n.staffVoiceDeleted,
            style: TextStyle(color: Neutrals.of(context).muted, fontSize: 13),
          ),
        ),
      ],
    );
  }
}

// ------------------------------------------------------------------ toll

/// The toll at the end of the mission: the people (live counters), the material damage and the
/// description, typed or spoken and corrected.
class TollScreen extends ConsumerStatefulWidget {
  const TollScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<TollScreen> createState() => _TollScreenState();
}

class _TollScreenState extends ConsumerState<TollScreen> {
  final _text = TextEditingController();
  String? _voiceId;
  String? _damage;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = ref.read(staffControllerProvider.notifier);
    final m = s.mission(widget.missionId);
    if (m == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffToll),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final damage = _damage ?? (m.toll?.answers['damage'] as String?) ?? 'none';
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffToll),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                SectionTitle(l10n.staffLiveCounts),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final k in CasualtyCounter.values)
                      SizedBox(
                        width: 170,
                        child: CounterCell(
                          label: counterLabel(l10n, k),
                          value: m.casualties.of(k),
                          keyName: 'toll-${k.wire}',
                          tone: counterTone(k),
                          onMinus: s.busy
                              ? null
                              : () => unawaited(c.count(m.id, k, -1)),
                          onPlus: s.busy
                              ? null
                              : () => unawaited(c.count(m.id, k, 1)),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                SectionTitle(l10n.staffDamage),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    for (final d in damages)
                      ChoiceChip(
                        key: Key('damage-$d'),
                        label: Text(damageLabel(l10n, d)),
                        selected: d == damage,
                        onSelected: (_) => setState(() => _damage = d),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                SpokenTextField(
                  missionId: m.id,
                  controller: _text,
                  label: l10n.staffTollDescription,
                  onVoice: (id) => _voiceId = id,
                ),
                const StaffErrorText(),
                const SizedBox(height: 12),
                ToneButton(
                  action: BarAction(
                    key: const Key('toll-send'),
                    label: l10n.staffRecordSend,
                    icon: Icons.send,
                    tone: Tone.green,
                    onPressed: s.busy
                        ? null
                        : () async {
                            final ok = await c.toll(
                              m.id,
                              damage: damage,
                              description: _text.text,
                              voiceId: _voiceId,
                            );
                            if (ok && context.mounted) {
                              Navigator.of(context).pop();
                            }
                          },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ intervention report

/// «محضر التدخل», from the mission's page at any time: typed, or spoken and corrected.
class InterventionReportScreen extends ConsumerStatefulWidget {
  const InterventionReportScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<InterventionReportScreen> createState() =>
      _InterventionReportScreenState();
}

class _InterventionReportScreenState
    extends ConsumerState<InterventionReportScreen> {
  late final _text = TextEditingController(
    text: ref
        .read(staffControllerProvider)
        .mission(widget.missionId)
        ?.interventionReport
        ?.note,
  );
  String? _voiceId;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffInterventionReport),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(l10n.staffInterventionReportHelp),
                const SizedBox(height: 12),
                SpokenTextField(
                  missionId: widget.missionId,
                  controller: _text,
                  minLines: 8,
                  label: l10n.staffInterventionReport,
                  onVoice: (id) => _voiceId = id,
                ),
                const StaffErrorText(),
                const SizedBox(height: 12),
                ToneButton(
                  action: BarAction(
                    key: const Key('report-send'),
                    label: l10n.staffRecordSend,
                    icon: Icons.send,
                    tone: Tone.navy,
                    onPressed: s.busy
                        ? null
                        : () async {
                            if (_text.text.trim().length < 3) return;
                            final ok = await ref
                                .read(staffControllerProvider.notifier)
                                .interventionReport(
                                  widget.missionId,
                                  _text.text,
                                  voiceId: _voiceId,
                                );
                            if (ok && context.mounted) {
                              Navigator.of(context).pop();
                            }
                          },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ a mission opened from the field

/// The team meets an incident on its way: the nature, the phone's position, a note; the room is
/// told at once.
class OpenMissionScreen extends ConsumerStatefulWidget {
  const OpenMissionScreen({super.key});

  @override
  ConsumerState<OpenMissionScreen> createState() => _OpenMissionScreenState();
}

class _OpenMissionScreenState extends ConsumerState<OpenMissionScreen> {
  final _note = TextEditingController();
  String _nature = 'traffic_accident';
  bool _locating = false;
  bool _noFix = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() {
      _locating = true;
      _noFix = false;
    });
    final at = await ref
        .read(locationServiceProvider)
        .bestEffort(timeout: const Duration(seconds: 8));
    if (!mounted) return;
    setState(() => _locating = false);
    if (at == null) {
      setState(() => _noFix = true);
      return;
    }
    final m = await ref
        .read(staffControllerProvider.notifier)
        .openMission(nature: _nature, at: at, note: _note.text);
    if (m != null && mounted) Navigator.of(context).pop(m.id);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffOpenMission),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l10n.staffOpenMissionHelp),
          const SizedBox(height: 12),
          SectionTitle(l10n.staffNature),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              for (final n in crewNatures)
                ChoiceChip(
                  key: Key('open-nature-$n'),
                  label: Text(natureLabel(l10n, n)),
                  selected: n == _nature,
                  onSelected: (_) => setState(() => _nature = n),
                ),
            ],
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('open-note'),
            controller: _note,
            maxLength: 500,
            minLines: 2,
            maxLines: 5,
            decoration: InputDecoration(labelText: l10n.staffOpenMissionNote),
          ),
          if (_noFix)
            Text(
              l10n.staffOpenMissionNoFix,
              style: TextStyle(color: Tone.red.colors(context).onTint),
            ),
          const StaffErrorText(),
          const SizedBox(height: 12),
          ToneButton(
            action: BarAction(
              key: const Key('open-send'),
              label: _locating
                  ? l10n.staffOpenMissionLocating
                  : l10n.staffOpenMissionSend,
              icon: Icons.add_location_alt,
              tone: Tone.red,
              onPressed: s.busy || _locating ? null : () => unawaited(_send()),
            ),
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ charter

/// The charter drawn from the law, general advice and the agent's duties; the agent accepts it
/// and consents to text messages and to sending the phone's position.
class CharterScreen extends ConsumerStatefulWidget {
  const CharterScreen({super.key});

  @override
  ConsumerState<CharterScreen> createState() => _CharterScreenState();
}

class _CharterScreenState extends ConsumerState<CharterScreen> {
  bool _read = false;
  bool _sms = false;
  bool _location = false;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final ready = _read && _sms && _location && !s.busy;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffCharterTitle),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l10n.staffCharterIntro,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                for (final line in [
                  l10n.staffCharter1,
                  l10n.staffCharter2,
                  l10n.staffCharter3,
                  l10n.staffCharter4,
                  l10n.staffCharter5,
                ])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('•  '),
                        Expanded(child: Text(line)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          CheckboxListTile(
            key: const Key('charter-read'),
            value: _read,
            onChanged: (v) => setState(() => _read = v ?? false),
            title: Text(l10n.staffCharterAccept),
          ),
          CheckboxListTile(
            key: const Key('charter-sms'),
            value: _sms,
            onChanged: (v) => setState(() => _sms = v ?? false),
            title: Text(l10n.staffCharterSms),
          ),
          CheckboxListTile(
            key: const Key('charter-location'),
            value: _location,
            onChanged: (v) => setState(() => _location = v ?? false),
            title: Text(l10n.staffCharterLocation),
          ),
          const StaffErrorText(),
          const SizedBox(height: 12),
          ToneButton(
            action: BarAction(
              key: const Key('charter-accept'),
              label: l10n.staffCharterSubmit,
              icon: Icons.verified,
              tone: Tone.green,
              onPressed: ready
                  ? () => unawaited(
                      ref
                          .read(staffControllerProvider.notifier)
                          .acceptCharter(
                            version: charterVersion,
                            sms: _sms,
                            location: _location,
                          ),
                    )
                  : null,
            ),
          ),
          TextButton(
            key: const Key('charter-sign-out'),
            onPressed: () =>
                unawaited(ref.read(staffControllerProvider.notifier).signOut()),
            child: Text(l10n.staffSignOut),
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ activation

/// Phase F: the agent types the professional number and the one-time code the room chief gave.
class ActivationCard extends ConsumerStatefulWidget {
  const ActivationCard({super.key});

  @override
  ConsumerState<ActivationCard> createState() => _ActivationCardState();
}

class _ActivationCardState extends ConsumerState<ActivationCard> {
  final _matricule = TextEditingController();
  final _code = TextEditingController();

  @override
  void dispose() {
    _matricule.dispose();
    _code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final error = switch (s.activation) {
      null => null,
      'activation_expired' => l10n.staffActivationExpired,
      'network' => l10n.staffOffline,
      'rate_limited' => l10n.staffActivationLater,
      _ => l10n.staffActivationRefused,
    };
    return AppCard(
      key: const Key('activation'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            l10n.staffActivationTitle,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(l10n.staffActivationHelp),
          const SizedBox(height: 12),
          TextField(
            key: const Key('activation-matricule'),
            controller: _matricule,
            textDirection: TextDirection.ltr,
            keyboardType: TextInputType.visiblePassword,
            autocorrect: false,
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp('[0-9A-Za-z]')),
            ],
            maxLength: 20,
            decoration: InputDecoration(
              labelText: l10n.staffActivationMatricule,
              counterText: '',
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            key: const Key('activation-code'),
            controller: _code,
            textDirection: TextDirection.ltr,
            textCapitalization: TextCapitalization.characters,
            autocorrect: false,
            keyboardType: TextInputType.visiblePassword,
            maxLength: 9,
            style: const TextStyle(letterSpacing: 3, fontSize: 20),
            decoration: InputDecoration(
              labelText: l10n.staffActivationCode,
              hintText: 'XXXX-XXXX',
              errorText: error,
              counterText: '',
            ),
          ),
          const SizedBox(height: 12),
          ToneButton(
            action: BarAction(
              key: const Key('activation-submit'),
              label: l10n.staffActivationSubmit,
              icon: Icons.key,
              tone: Tone.navy,
              onPressed: s.busy
                  ? null
                  : () {
                      if (_matricule.text.trim().length < 3 ||
                          _code.text.trim().length < 8) {
                        return;
                      }
                      unawaited(
                        ref
                            .read(staffControllerProvider.notifier)
                            .activate(_matricule.text, _code.text),
                      );
                    },
            ),
          ),
        ],
      ),
    );
  }
}
