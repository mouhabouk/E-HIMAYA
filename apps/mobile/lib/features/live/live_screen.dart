import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/logging/log.dart';
import '../../core/media/media_rules.dart';
import '../../core/platform/device_services.dart';
import '../../core/routing/app_router.dart';
import '../../core/sync/sync_scheduler.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../report/category_labels.dart';
import '../report/new_report_screen.dart' show imagePickerProvider;
import 'live_controller.dart';
import 'live_widgets.dart';

final _log = logger('live.screen');

/// Longest clip recorded when live streaming is not possible (FR-A-051).
const liveClipMaxDuration = Duration(seconds: 60);

/// FR-A-031/050/052: the Live screen. Before start: what is shared and why (camera, microphone,
/// position), the incident type for a new report, one start button. While live: the camera
/// picture, the red pulsing LIVE indicator with the elapsed time, one-tap stop, mute, camera
/// switch. After: the outcome, and the clip fallback when streaming failed (FR-A-051).
class LiveScreen extends ConsumerStatefulWidget {
  const LiveScreen({super.key, required this.target});

  final LiveTarget target;

  @override
  ConsumerState<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends ConsumerState<LiveScreen> {
  late final LiveController _controller;
  late ReportCategory _category;
  bool _recording = false;

  @override
  void initState() {
    super.initState();
    _controller = ref.read(liveControllerProvider.notifier);
    _category = widget.target.category;
    // A finished session of an earlier visit is not shown again.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _controller.reset();
    });
  }

  @override
  void dispose() {
    // Leaving the screen (or the locked alert view taking over) never leaves a stream running.
    unawaited(_controller.stop());
    super.dispose();
  }

  LiveTarget get _startTarget => widget.target.isNew
      ? LiveTarget.newReport(category: _category)
      : widget.target;

  /// Retry on the report that was created by the failed attempt (never a second report).
  LiveTarget _retryTarget(LiveState s) =>
      s.reportClientUuid != null || s.reportServerId != null
      ? LiveTarget.existing(
          clientUuid: s.reportClientUuid,
          serverId: s.reportServerId,
          trackingCode: s.trackingCode,
          category: s.target?.category ?? _category,
        )
      : _startTarget;

  Future<void> _start(LiveTarget target) async {
    _controller.reset();
    await _controller.start(target);
  }

  Future<bool> _confirmLeave() async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.liveLeaveTitle),
        content: Text(l10n.liveLeaveBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: sosRed),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.liveStop),
          ),
        ],
      ),
    );
    return ok == true;
  }

  void _close() {
    final router = GoRouter.of(context);
    if (router.canPop()) {
      router.pop();
    } else {
      router.go(Routes.home);
    }
  }

  /// FR-A-051: record a clip of at most 60 s and queue it on the report (tus, kind video).
  Future<void> _recordClip() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final session = ref.read(liveControllerProvider);
    if (session.isActive) {
      // The camera belongs to the stream: stop it first.
      await _controller.stop();
    }
    setState(() => _recording = true);
    try {
      final file = await ref
          .read(imagePickerProvider)
          .pickVideo(
            source: ImageSource.camera,
            maxDuration: liveClipMaxDuration,
            preferredCameraDevice: CameraDevice.rear,
          );
      if (file == null) return;
      final mime = MediaRules.mimeFor(file.path);
      if (mime == null || MediaRules.kindOfMime(mime) != MediaKind.video) {
        messenger.showSnackBar(
          SnackBar(content: Text(l10n.attachmentUnsupported)),
        );
        return;
      }
      if (await File(file.path).length() > MediaRules.maxVideoBytes) {
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              l10n.attachmentTooLarge(
                MediaRules.maxVideoBytes ~/ (1024 * 1024),
              ),
            ),
          ),
        );
        return;
      }
      await _controller.attachClip(file.path, mime: mime);
      unawaited(ref.read(requestSyncProvider)());
      messenger.showSnackBar(SnackBar(content: Text(l10n.liveClipQueued)));
      if (mounted) _close();
    } on Object catch (e) {
      _log.warning('clip fallback failed: ${e.runtimeType}');
      messenger.showSnackBar(SnackBar(content: Text(l10n.liveClipFailed)));
    } finally {
      if (mounted) setState(() => _recording = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(liveControllerProvider);
    final l10n = AppLocalizations.of(context);
    return PopScope(
      canPop: !state.isActive,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop || !state.isActive) return;
        if (await _confirmLeave()) {
          await _controller.stop();
          if (mounted) _close();
        }
      },
      child: switch (state.phase) {
        LivePhase.idle => _PreStart(
          target: widget.target,
          category: _category,
          onCategory: (c) => setState(() => _category = c),
          onStart: () => _start(_startTarget),
        ),
        LivePhase.ended => _Outcome(
          key: const Key('live-ended'),
          icon: Icons.check_circle_outline,
          title: l10n.liveEndedTitle,
          body: _endMessage(l10n, state),
          duration: state.startedAt == null || state.endedAt == null
              ? null
              : state.endedAt!.difference(state.startedAt!),
          simulated: state.simulated,
          actions: [
            FilledButton(
              key: const Key('live-done'),
              onPressed: _close,
              child: Text(l10n.liveDone),
            ),
            OutlinedButton(
              onPressed: () => context.go(Routes.reports),
              child: Text(l10n.myReportsTitle),
            ),
          ],
        ),
        LivePhase.failed => _Outcome(
          key: const Key('live-failed'),
          icon: Icons.videocam_off_outlined,
          title: l10n.liveFailedTitle,
          body: _failMessage(l10n, state),
          simulated: state.simulated,
          actions: _failActions(l10n, state),
        ),
        _ => _OnAir(
          state: state,
          busy: _recording,
          onStop: _controller.stop,
          onMute: _controller.toggleMute,
          onSwitch: _controller.switchCamera,
          onRecordClip: _recordClip,
          maxAttempts: ref.watch(liveTimingsProvider).reconnect.maxAttempts,
          preview: _controller.publisher?.preview(context),
        ),
      },
    );
  }

  String _endMessage(AppLocalizations l10n, LiveState s) =>
      switch (s.endReason) {
        LiveEndReason.operatorStopped => l10n.liveEndedByOperator,
        LiveEndReason.maxDuration => l10n.liveEndedMaxDuration(
          s.maxDuration.inMinutes,
        ),
        LiveEndReason.serverEnded => l10n.liveEndedByServer,
        LiveEndReason.locked => l10n.liveEndedLocked,
        LiveEndReason.userStopped || null => l10n.liveEndedByUser,
      };

  String _failMessage(AppLocalizations l10n, LiveState s) =>
      switch (s.failure) {
        LiveFailure.noLocation => l10n.liveFailNoLocation,
        LiveFailure.reportNotSent => l10n.liveFailReportNotSent,
        LiveFailure.permissionDenied => l10n.liveFailPermission,
        LiveFailure.cameraUnavailable => l10n.liveFailCamera,
        LiveFailure.locked => l10n.liveFailLocked,
        LiveFailure.connectionFailed when s.apiError == null =>
          l10n.liveFailConnection,
        _ when s.apiError != null => apiErrorMessage(l10n, s.apiError!),
        _ => l10n.liveFailConnection,
      };

  List<Widget> _failActions(AppLocalizations l10n, LiveState s) {
    final civil = emergencyNumbers.first;
    final fallback =
        s.canFallback &&
        s.failure != LiveFailure.locked &&
        s.failure != LiveFailure.permissionDenied;
    return [
      if (fallback)
        FilledButton.icon(
          key: const Key('live-record-clip'),
          onPressed: _recording ? null : _recordClip,
          icon: const Icon(Icons.videocam),
          label: Text(l10n.liveRecordClip),
        ),
      if (s.failure == LiveFailure.noLocation)
        FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: sosRed),
          onPressed: () => ref.read(dialerProvider)(civil.telUri),
          icon: const Icon(Icons.call),
          label: Text(l10n.callNumber(civil.number)),
        ),
      if (s.failure == LiveFailure.permissionDenied)
        FilledButton.icon(
          key: const Key('live-open-settings'),
          onPressed: () => ref.read(deviceServicesProvider).openAppSettings(),
          icon: const Icon(Icons.settings),
          label: Text(l10n.liveOpenSettings),
        ),
      if (s.failure != LiveFailure.locked)
        OutlinedButton.icon(
          key: const Key('live-retry'),
          onPressed: _recording ? null : () => _start(_retryTarget(s)),
          icon: const Icon(Icons.refresh),
          label: Text(l10n.liveRetry),
        ),
      TextButton(onPressed: _close, child: Text(l10n.liveDone)),
    ];
  }
}

class _PreStart extends StatelessWidget {
  const _PreStart({
    required this.target,
    required this.category,
    required this.onCategory,
    required this.onStart,
  });

  final LiveTarget target;
  final ReportCategory category;
  final ValueChanged<ReportCategory> onCategory;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final code = target.trackingCode;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.liveTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Icon(Icons.videocam, size: 64, color: sosRed),
            const SizedBox(height: 12),
            if (code != null) ...[
              Text(
                l10n.liveReportCode(code),
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
            ],
            Text(l10n.liveIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const ExcludeSemantics(
                      child: Column(
                        children: [
                          Icon(Icons.photo_camera_outlined),
                          SizedBox(height: 4),
                          Icon(Icons.mic_none),
                          SizedBox(height: 4),
                          Icon(Icons.location_on_outlined),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        l10n.livePermissionRationale,
                        key: const Key('live-rationale'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            if (target.isNew) ...[
              const SizedBox(height: 16),
              Text(l10n.liveCategoryLabel, style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final c in ReportCategory.grid)
                    ChoiceChip(
                      key: Key('live-category-${c.wire}'),
                      avatar: Icon(categoryIcon(c), size: 18),
                      label: Text(categoryLabel(l10n, c)),
                      selected: c == category,
                      onSelected: (_) => onCategory(c),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
      // Always on screen, whatever the text size: the start button is never scrolled away.
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: FilledButton.icon(
            key: const Key('live-start'),
            style: FilledButton.styleFrom(
              backgroundColor: sosRed,
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(64),
              textStyle: theme.textTheme.titleLarge,
            ),
            onPressed: onStart,
            icon: const Icon(Icons.fiber_manual_record),
            label: Text(l10n.liveStart),
          ),
        ),
      ),
    );
  }
}

class _OnAir extends StatelessWidget {
  const _OnAir({
    required this.state,
    required this.busy,
    required this.onStop,
    required this.onMute,
    required this.onSwitch,
    required this.onRecordClip,
    required this.maxAttempts,
    required this.preview,
  });

  final LiveState state;
  final bool busy;
  final Future<void> Function() onStop;
  final Future<void> Function() onMute;
  final Future<void> Function() onSwitch;
  final Future<void> Function() onRecordClip;
  final int maxAttempts;
  final Widget? preview;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final stopping = state.phase == LivePhase.stopping;
    final code = state.trackingCode;
    final status = switch (state.phase) {
      LivePhase.preparing => l10n.livePreparing,
      LivePhase.connecting => l10n.liveConnecting,
      LivePhase.reconnecting => l10n.liveReconnecting(
        state.reconnectAttempt,
        maxAttempts,
      ),
      _ => null,
    };
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          preview ?? const ColoredBox(color: Colors.black),
          SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (state.simulated) const LiveSimulationBand(),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (state.phase == LivePhase.live)
                        LiveIndicator(startedAt: state.startedAt)
                      else if (status != null)
                        LivePill(
                          key: const Key('live-status'),
                          icon: state.phase == LivePhase.reconnecting
                              ? Icons.wifi_off
                              : Icons.hourglass_top,
                          text: status,
                        ),
                      if (code != null)
                        LivePill(
                          icon: Icons.confirmation_number_outlined,
                          text: l10n.liveReportCode(code),
                        ),
                      LivePill(
                        key: const Key('live-location'),
                        icon: state.locationShared
                            ? Icons.my_location
                            : Icons.location_disabled,
                        text: state.locationShared
                            ? l10n.liveLocationOn
                            : l10n.liveLocationOff,
                      ),
                      LiveRemaining(
                        startedAt: state.startedAt,
                        maxDuration: state.maxDuration,
                      ),
                    ],
                  ),
                ),
                if (state.weakNetwork)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Material(
                      key: const Key('live-weak-network'),
                      color: Theme.of(context).colorScheme.errorContainer,
                      borderRadius: BorderRadius.circular(12),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(l10n.liveWeakNetwork),
                            Align(
                              alignment: AlignmentDirectional.centerEnd,
                              child: TextButton.icon(
                                onPressed: busy ? null : onRecordClip,
                                icon: const Icon(Icons.videocam),
                                label: Text(l10n.liveRecordClip),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                const Spacer(),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      IconButton.filledTonal(
                        key: const Key('live-mute'),
                        iconSize: 32,
                        tooltip: state.muted ? l10n.liveUnmute : l10n.liveMute,
                        onPressed: stopping ? null : onMute,
                        icon: Icon(state.muted ? Icons.mic_off : Icons.mic),
                      ),
                      _StopButton(
                        onPressed: stopping ? null : onStop,
                        label: l10n.liveStop,
                      ),
                      IconButton.filledTonal(
                        key: const Key('live-switch-camera'),
                        iconSize: 32,
                        tooltip: l10n.liveSwitchCamera,
                        onPressed: stopping ? null : onSwitch,
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

/// One tap stops everything (FR-A-052): no confirmation on the stop button itself.
class _StopButton extends StatelessWidget {
  const _StopButton({required this.onPressed, required this.label});

  final VoidCallback? onPressed;
  final String label;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: label,
    excludeSemantics: true,
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox.square(
          dimension: 88,
          child: Material(
            key: const Key('live-stop'),
            color: sosRed,
            shape: const CircleBorder(
              side: BorderSide(color: Colors.white, width: 4),
            ),
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: onPressed,
              child: onPressed == null
                  ? const Padding(
                      padding: EdgeInsets.all(28),
                      child: CircularProgressIndicator(color: Colors.white),
                    )
                  : const Icon(
                      Icons.stop_rounded,
                      color: Colors.white,
                      size: 48,
                    ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          label,
          style: Theme.of(context).textTheme.titleSmall
              ?.copyWith(color: Colors.white, fontWeight: FontWeight.w700),
        ),
      ],
    ),
  );
}

class _Outcome extends StatelessWidget {
  const _Outcome({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    required this.actions,
    this.duration,
    this.simulated = false,
  });

  final IconData icon;
  final String title;
  final String body;
  final Duration? duration;
  final bool simulated;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final d = duration;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.liveTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (simulated) ...[
              const LiveSimulationBand(),
              const SizedBox(height: 16),
            ],
            Icon(icon, size: 64, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text(
              title,
              textAlign: TextAlign.center,
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            Text(
              body,
              textAlign: TextAlign.center,
              key: const Key('live-outcome-body'),
            ),
            if (d != null) ...[
              const SizedBox(height: 8),
              Text(
                l10n.liveDuration(formatLiveDuration(d)),
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 24),
            for (final a in actions) ...[a, const SizedBox(height: 8)],
          ],
        ),
      ),
    );
  }
}
