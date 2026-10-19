import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../../core/logging/log.dart';
import '../../core/media/media_rules.dart';
import '../../l10n/app_localizations.dart';

final _log = logger('audio');

enum _Phase { idle, recording, recorded }

/// Voice message: record (AAC-LC in .m4a = `audio/mp4`, max 5 minutes with auto-stop), live
/// amplitude bars, play back, re-record, delete.
class AudioRecorderPanel extends StatefulWidget {
  const AudioRecorderPanel({super.key, required this.onChanged});

  /// Path of the finished recording, or null when deleted.
  final ValueChanged<String?> onChanged;

  @override
  State<AudioRecorderPanel> createState() => _AudioRecorderPanelState();
}

class _AudioRecorderPanelState extends State<AudioRecorderPanel> {
  final _recorder = AudioRecorder();
  final _player = AudioPlayer();
  final _levels = <double>[];
  StreamSubscription<Amplitude>? _amplitudeSub;
  StreamSubscription<PlayerState>? _playerSub;
  Timer? _ticker;
  _Phase _phase = _Phase.idle;
  Duration _elapsed = Duration.zero;
  String? _path;
  bool _playing = false;

  static const _maxBars = 40;

  @override
  void initState() {
    super.initState();
    _playerSub = _player.playerStateStream.listen((s) {
      final playing =
          s.playing && s.processingState != ProcessingState.completed;
      if (s.processingState == ProcessingState.completed) {
        _player.pause();
        _player.seek(Duration.zero);
      }
      if (mounted && playing != _playing) setState(() => _playing = playing);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _amplitudeSub?.cancel();
    _playerSub?.cancel();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    if (!await _recorder.hasPermission()) {
      messenger.showSnackBar(
        SnackBar(content: Text(l10n.audioPermissionDenied)),
      );
      return;
    }
    if (_path != null) {
      await _discardFile();
      widget.onChanged(null);
    }
    final dir = await getTemporaryDirectory();
    final path = p.join(
      dir.path,
      'voice_${DateTime.now().millisecondsSinceEpoch}.m4a',
    );
    try {
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 44100,
          numChannels: 1,
        ),
        path: path,
      );
    } on Exception catch (e) {
      _log.warning('recorder failed to start: ${e.runtimeType}');
      messenger.showSnackBar(SnackBar(content: Text(l10n.audioFailed)));
      return;
    }
    _levels.clear();
    _amplitudeSub = _recorder
        .onAmplitudeChanged(const Duration(milliseconds: 120))
        .listen((a) {
          // dBFS (-60..0) → 0..1
          final level = ((a.current + 60) / 60).clamp(0.02, 1.0);
          if (!mounted) return;
          setState(() {
            _levels.add(level);
            if (_levels.length > _maxBars) _levels.removeAt(0);
          });
        });
    final started = DateTime.now();
    _ticker = Timer.periodic(const Duration(milliseconds: 250), (_) {
      final elapsed = DateTime.now().difference(started);
      if (elapsed >= MediaRules.maxAudioDuration) {
        _stop();
        return;
      }
      if (mounted) setState(() => _elapsed = elapsed);
    });
    setState(() {
      _phase = _Phase.recording;
      _elapsed = Duration.zero;
      _path = path;
    });
  }

  Future<void> _stop() async {
    _ticker?.cancel();
    _ticker = null;
    await _amplitudeSub?.cancel();
    _amplitudeSub = null;
    final path = await _recorder.stop();
    if (!mounted) return;
    if (path == null) {
      setState(() => _phase = _Phase.idle);
      return;
    }
    _path = path;
    await _player.setFilePath(path);
    if (!mounted) return;
    setState(() => _phase = _Phase.recorded);
    widget.onChanged(path);
  }

  Future<void> _togglePlay() async {
    if (_playing) {
      await _player.pause();
    } else {
      await _player.play();
    }
  }

  Future<void> _delete() async {
    await _player.stop();
    await _discardFile();
    if (!mounted) return;
    setState(() {
      _phase = _Phase.idle;
      _elapsed = Duration.zero;
      _levels.clear();
    });
    widget.onChanged(null);
  }

  Future<void> _discardFile() async {
    final path = _path;
    _path = null;
    if (path == null) return;
    try {
      final f = File(path);
      if (await f.exists()) await f.delete();
    } on FileSystemException {
      // Temporary directory: cleaned by the OS anyway.
    }
  }

  static String _fmt(Duration d) =>
      '${d.inMinutes.toString().padLeft(2, '0')}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.mic),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.audioTitle,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                Text(l10n.audioMaxDuration, style: theme.textTheme.bodySmall),
              ],
            ),
            if (_phase == _Phase.recording) ...[
              const SizedBox(height: 8),
              SizedBox(
                height: 48,
                child: ExcludeSemantics(
                  child: _AmplitudeBars(
                    levels: _levels,
                    color: theme.colorScheme.error,
                  ),
                ),
              ),
              Text(
                l10n.audioRecording(_fmt(_elapsed)),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 8),
            switch (_phase) {
              _Phase.idle => OutlinedButton.icon(
                key: const Key('audio-record'),
                onPressed: _start,
                icon: const Icon(Icons.fiber_manual_record),
                label: Text(l10n.audioRecord),
              ),
              _Phase.recording => FilledButton.icon(
                key: const Key('audio-stop'),
                onPressed: _stop,
                icon: const Icon(Icons.stop),
                label: Text(l10n.audioStop),
              ),
              _Phase.recorded => Wrap(
                alignment: WrapAlignment.center,
                spacing: 8,
                children: [
                  IconButton.filledTonal(
                    tooltip: _playing ? l10n.audioPause : l10n.audioPlay,
                    icon: Icon(_playing ? Icons.pause : Icons.play_arrow),
                    onPressed: _togglePlay,
                  ),
                  IconButton(
                    tooltip: l10n.audioReRecord,
                    icon: const Icon(Icons.replay),
                    onPressed: () async {
                      await _player.stop();
                      await _start();
                    },
                  ),
                  IconButton(
                    tooltip: l10n.audioDelete,
                    icon: const Icon(Icons.delete_outline),
                    onPressed: _delete,
                  ),
                ],
              ),
            },
          ],
        ),
      ),
    );
  }
}

class _AmplitudeBars extends StatelessWidget {
  const _AmplitudeBars({required this.levels, required this.color});

  final List<double> levels;
  final Color color;

  @override
  Widget build(BuildContext context) => CustomPaint(
    painter: _BarsPainter(List.of(levels), color),
    size: Size.infinite,
  );
}

class _BarsPainter extends CustomPainter {
  _BarsPainter(this.levels, this.color);

  final List<double> levels;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const count = _AudioRecorderPanelState._maxBars;
    final slot = size.width / count;
    final paint = Paint()
      ..color = color
      ..strokeCap = StrokeCap.round
      ..strokeWidth = slot * 0.6;
    for (var i = 0; i < levels.length; i++) {
      final x = slot * (count - levels.length + i) + slot / 2;
      final h = levels[i] * size.height;
      canvas.drawLine(
        Offset(x, (size.height - h) / 2),
        Offset(x, (size.height + h) / 2),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_BarsPainter old) => true;
}
