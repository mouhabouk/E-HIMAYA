import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/error_messages.dart';
import '../../core/ui/theme.dart';
import '../../features/live/live_controller.dart';
import '../../features/live/live_widgets.dart';
import '../../l10n/app_localizations.dart';

/// Phase D, review point 17: the team streams the scene to the room from the staff app. The same
/// live session as the citizen app (WHIP, adaptive quality, reconnections, position), aimed at the
/// mission (`/api/v1/crew/missions/{id}/stream`): the room sees it in the wall and on the incident
/// page. It starts at once (the leader already chose to stream) and stops when the screen closes.
class StaffLiveScreen extends ConsumerStatefulWidget {
  const StaffLiveScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<StaffLiveScreen> createState() => _StaffLiveScreenState();
}

class _StaffLiveScreenState extends ConsumerState<StaffLiveScreen> {
  late final LiveController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ref.read(liveControllerProvider.notifier);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_start());
    });
  }

  @override
  void dispose() {
    unawaited(_controller.stop());
    super.dispose();
  }

  Future<void> _start() async {
    _controller.reset();
    await _controller.start(LiveTarget.existing(serverId: widget.missionId));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(liveControllerProvider);
    final over = s.phase == LivePhase.ended || s.phase == LivePhase.failed;
    final stopping = s.phase == LivePhase.stopping;
    final status = switch (s.phase) {
      LivePhase.idle || LivePhase.preparing => l10n.livePreparing,
      LivePhase.connecting => l10n.liveConnecting,
      LivePhase.reconnecting => l10n.liveReconnecting(
        s.reconnectAttempt,
        ref.watch(liveTimingsProvider).reconnect.maxAttempts,
      ),
      LivePhase.ended => switch (s.endReason) {
        LiveEndReason.operatorStopped => l10n.liveEndedByOperator,
        LiveEndReason.maxDuration => l10n.liveEndedMaxDuration(
          s.maxDuration.inMinutes,
        ),
        _ => l10n.staffLiveEnded,
      },
      LivePhase.failed => switch (s.failure) {
        LiveFailure.permissionDenied => l10n.liveFailPermission,
        LiveFailure.cameraUnavailable => l10n.liveFailCamera,
        _ when s.apiError != null => apiErrorMessage(l10n, s.apiError!),
        _ => l10n.liveFailConnection,
      },
      _ => null,
    };
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          if (!over)
            _controller.publisher?.preview(context) ??
                const ColoredBox(color: Colors.black),
          SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (s.simulated) const LiveSimulationBand(),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (s.phase == LivePhase.live)
                        LiveIndicator(startedAt: s.startedAt)
                      else if (status != null)
                        LivePill(
                          key: const Key('staff-live-status'),
                          icon: over ? Icons.info_outline : Icons.hourglass_top,
                          text: status,
                        ),
                      LivePill(icon: Icons.groups, text: l10n.staffLiveHint),
                      LiveRemaining(
                        startedAt: s.startedAt,
                        maxDuration: s.maxDuration,
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                  child: over
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            FilledButton.icon(
                              key: const Key('staff-live-again'),
                              style: FilledButton.styleFrom(
                                backgroundColor: sosRed,
                                minimumSize: const Size.fromHeight(52),
                              ),
                              onPressed: _start,
                              icon: const Icon(Icons.videocam),
                              label: Text(l10n.staffLiveAgain),
                            ),
                            const SizedBox(height: 8),
                            OutlinedButton(
                              key: const Key('staff-live-close'),
                              style: OutlinedButton.styleFrom(
                                foregroundColor: Colors.white,
                                minimumSize: const Size.fromHeight(52),
                              ),
                              onPressed: () => Navigator.of(context).pop(),
                              child: Text(l10n.staffLiveBack),
                            ),
                          ],
                        )
                      : Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            IconButton.filledTonal(
                              key: const Key('staff-live-mute'),
                              iconSize: 32,
                              tooltip: s.muted
                                  ? l10n.liveUnmute
                                  : l10n.liveMute,
                              onPressed: stopping
                                  ? null
                                  : _controller.toggleMute,
                              icon: Icon(s.muted ? Icons.mic_off : Icons.mic),
                            ),
                            FilledButton.icon(
                              key: const Key('staff-live-stop'),
                              style: FilledButton.styleFrom(
                                backgroundColor: sosRed,
                                minimumSize: const Size(160, 64),
                              ),
                              onPressed: stopping ? null : _controller.stop,
                              icon: const Icon(Icons.stop_circle),
                              label: Text(l10n.liveStop),
                            ),
                            IconButton.filledTonal(
                              key: const Key('staff-live-switch'),
                              iconSize: 32,
                              tooltip: l10n.liveSwitchCamera,
                              onPressed: stopping
                                  ? null
                                  : _controller.switchCamera,
                              icon: const Icon(Icons.cameraswitch),
                            ),
                          ],
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
