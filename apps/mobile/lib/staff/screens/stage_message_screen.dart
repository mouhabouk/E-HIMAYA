import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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

/// The step a mission has reached after «انطلقنا», as the server files a message under it; null
/// before leaving the unit or once cancelled.
String? missionStage(Mission m) {
  if (m.status == MissionStatus.cancelled) return null;
  if (m.backAtUnitAt != null) return 'back_at_unit';
  if (m.availableAt != null) return 'available';
  if (m.atHospitalAt != null) return 'at_hospital';
  if (m.leftSceneAt != null) return 'left_scene';
  if (m.onSceneAt != null) return 'on_scene';
  if (m.enRouteAt != null) return 'en_route';
  return null;
}

String stageLabel(AppLocalizations l10n, String stage) => switch (stage) {
  'en_route' => l10n.staffStepOnTheWay,
  'on_scene' => l10n.staffStepArrived,
  'left_scene' => l10n.staffStepLeftScene,
  'at_hospital' => l10n.staffStepAtHospital,
  'available' => l10n.staffStepAvailable,
  'back_at_unit' => l10n.staffStepBackAtUnit,
  _ => stage,
};

/// A spoken word at every step (Yamen, 2026-11-01): the leader speaks, the platform transcribes
/// and tidies, the leader corrects, the room reads it under the mission's step.
class StageMessageScreen extends ConsumerStatefulWidget {
  const StageMessageScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<StageMessageScreen> createState() => _StageMessageScreenState();
}

class _StageMessageScreenState extends ConsumerState<StageMessageScreen> {
  final _text = TextEditingController();
  StageVoice? _heard;
  bool _listening = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _speak() async {
    final media = await ref.read(staffCaptureProvider).voice(context);
    if (media == null || !mounted) return;
    setState(() => _listening = true);
    final lang = ref.read(localeCodeProvider) == 'fr' ? 'fr' : 'ar';
    final heard = await ref
        .read(staffControllerProvider.notifier)
        .stageVoice(widget.missionId, media, lang);
    if (!mounted) return;
    setState(() {
      _listening = false;
      if (heard != null) {
        _heard = heard;
        _text.text = heard.text;
      }
    });
  }

  Future<void> _send() async {
    if (_text.text.trim().length < 2) return;
    final ok = await ref
        .read(staffControllerProvider.notifier)
        .stageMessage(widget.missionId, _text.text, voiceId: _heard?.voiceId);
    if (!ok || !mounted) return;
    setState(() {
      _heard = null;
      _text.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(widget.missionId);
    final stage = m == null ? null : missionStage(m);
    if (m == null || stage == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffStageMessage),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final muted = Neutrals.of(context).muted;
    final sent = [
      for (final a in m.attachments)
        if (a.stage != null) a,
    ].reversed.toList();
    final heard = _heard;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.staffStageMessage),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  l10n.staffStageNow(stageLabel(l10n, stage)),
                  key: const Key('stage-now'),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 4),
                Text(l10n.staffStageMessageSub),
                const SizedBox(height: 12),
                ToneButton(
                  action: BarAction(
                    key: const Key('stage-mic'),
                    label: _listening
                        ? l10n.staffVoiceListening
                        : l10n.staffStageSpeak,
                    icon: Icons.mic,
                    tone: Tone.red,
                    onPressed: _listening || s.busy
                        ? null
                        : () => unawaited(_speak()),
                  ),
                ),
                if (heard != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    l10n.staffStageHeard,
                    style: TextStyle(color: muted, fontSize: 13),
                  ),
                  Text(
                    heard.transcript,
                    key: const Key('stage-heard'),
                    style: TextStyle(color: muted),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    heard.byModel
                        ? l10n.staffStageByModel
                        : l10n.staffStageByRules,
                    style: const TextStyle(fontSize: 13),
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  key: const Key('stage-text'),
                  controller: _text,
                  minLines: 3,
                  maxLines: 8,
                  maxLength: 1000,
                  decoration: InputDecoration(labelText: l10n.staffStageText),
                ),
                Text(
                  l10n.staffVoiceDeleted,
                  style: TextStyle(color: muted, fontSize: 13),
                ),
                const StaffErrorText(),
                const SizedBox(height: 12),
                ToneButton(
                  action: BarAction(
                    key: const Key('stage-send'),
                    label: l10n.staffStageSend,
                    icon: Icons.send,
                    tone: Tone.navy,
                    onPressed: s.busy ? null : () => unawaited(_send()),
                  ),
                ),
                if (sent.isNotEmpty) ...[
                  SectionTitle(l10n.staffStageSentList),
                  for (final a in sent)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        a.spoken ? Icons.record_voice_over : Icons.notes,
                      ),
                      title: Text(a.body ?? ''),
                      subtitle: Text(
                        [
                          hhmm(a.createdAt),
                          stageLabel(l10n, a.stage!),
                          if (a.spoken) l10n.staffStageSpoken,
                        ].join(' · '),
                      ),
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
