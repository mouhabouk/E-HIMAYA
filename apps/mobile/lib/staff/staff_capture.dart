import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../core/logging/log.dart';
import '../core/media/media_rules.dart';
import '../core/ui/components.dart';
import '../core/ui/tokens.dart';
import '../l10n/app_localizations.dart';
import 'staff_models.dart';

final _log = logger('staff.capture');

/// The camera and the microphone of the field app (phase P4b, design §5.8). Overridden in tests.
abstract class StaffCapture {
  /// A photo from the camera, already reduced on the phone (null when cancelled).
  Future<CapturedMedia?> photo();

  /// A voice note of 60 seconds at most (null when cancelled).
  Future<CapturedMedia?> voice(BuildContext context);
}

final staffCaptureProvider = Provider<StaffCapture>((ref) => DeviceCapture());

class DeviceCapture implements StaffCapture {
  @override
  Future<CapturedMedia?> photo() async {
    final f = await ImagePicker().pickImage(
      source: ImageSource.camera,
      maxWidth: 1920,
      maxHeight: 1920,
      imageQuality: 80,
    );
    if (f == null) return null;
    final bytes = await f.readAsBytes();
    await _forget(f.path);
    return CapturedMedia(
      bytes: bytes,
      contentType: MediaRules.mimeFor(f.path) ?? 'image/jpeg',
    );
  }

  @override
  Future<CapturedMedia?> voice(BuildContext context) =>
      showModalBottomSheet<CapturedMedia>(
        context: context,
        isDismissible: false,
        builder: (_) => const VoiceSheet(),
      );
}

Future<void> _forget(String path) async {
  try {
    final f = File(path);
    if (await f.exists()) await f.delete();
  } on FileSystemException {
    // Temporary directory: cleaned by the OS anyway.
  }
}

/// One big button: record, stop (or 60 seconds), then send or record again.
class VoiceSheet extends StatefulWidget {
  const VoiceSheet({super.key});

  static const max = Duration(seconds: 60);

  @override
  State<VoiceSheet> createState() => _VoiceSheetState();
}

class _VoiceSheetState extends State<VoiceSheet> {
  final _recorder = AudioRecorder();
  Timer? _ticker;
  DateTime? _started;
  Duration _elapsed = Duration.zero;
  String? _path;
  bool _recording = false;

  @override
  void dispose() {
    _ticker?.cancel();
    unawaited(_recorder.dispose());
    final path = _path;
    if (path != null) unawaited(_forget(path));
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
    final old = _path;
    if (old != null) await _forget(old);
    final dir = await getTemporaryDirectory();
    final path = p.join(
      dir.path,
      'field_${DateTime.now().millisecondsSinceEpoch}.m4a',
    );
    try {
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 48000,
          sampleRate: 22050,
          numChannels: 1,
        ),
        path: path,
      );
    } on Exception catch (e) {
      _log.warning('recorder failed to start: ${e.runtimeType}');
      return;
    }
    _started = DateTime.now();
    _ticker = Timer.periodic(const Duration(milliseconds: 250), (_) {
      final e = DateTime.now().difference(_started!);
      if (e >= VoiceSheet.max) {
        unawaited(_stop());
      } else if (mounted) {
        setState(() => _elapsed = e);
      }
    });
    setState(() {
      _recording = true;
      _elapsed = Duration.zero;
      _path = path;
    });
  }

  Future<void> _stop() async {
    _ticker?.cancel();
    _ticker = null;
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() {
      _recording = false;
      if (_started != null) {
        final e = DateTime.now().difference(_started!);
        _elapsed = e > VoiceSheet.max ? VoiceSheet.max : e;
      }
      _path = path ?? _path;
    });
  }

  Future<void> _send() async {
    final path = _path;
    if (path == null) return;
    final bytes = await File(path).readAsBytes();
    await _forget(path);
    _path = null;
    if (!mounted) return;
    final secs = _elapsed.inMilliseconds / 1000;
    Navigator.of(context).pop(
      CapturedMedia(
        bytes: bytes,
        contentType: 'audio/mp4',
        durationS: secs <= 0 ? 1 : secs.clamp(1, 60).toDouble(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = _elapsed.inSeconds;
    final done = !_recording && _path != null;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              l10n.staffVoice,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 4),
            Text(l10n.staffVoiceMax),
            const SizedBox(height: 16),
            Icon(
              Icons.mic,
              size: 56,
              color: (_recording ? Tone.red : Tone.navy).colors(context).fill,
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: _elapsed.inMilliseconds / VoiceSheet.max.inMilliseconds,
              minHeight: 8,
              borderRadius: BorderRadius.circular(4),
              color: (_recording ? Tone.red : Tone.navy).colors(context).fill,
            ),
            const SizedBox(height: 8),
            Text(
              '00:${s.toString().padLeft(2, '0')}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            if (_recording)
              ToneButton(
                action: BarAction(
                  key: const Key('voice-stop'),
                  label: l10n.staffRecordStop,
                  icon: Icons.stop,
                  tone: Tone.red,
                  onPressed: () => unawaited(_stop()),
                ),
              )
            else
              ToneButton(
                action: BarAction(
                  key: const Key('voice-record'),
                  label: done ? l10n.staffRecordAgain : l10n.staffRecord,
                  icon: Icons.mic,
                  tone: done ? Tone.slate : Tone.red,
                  onPressed: () => unawaited(_start()),
                ),
              ),
            if (done) ...[
              const SizedBox(height: 8),
              ToneButton(
                action: BarAction(
                  key: const Key('voice-send'),
                  label: l10n.staffSend,
                  icon: Icons.send,
                  tone: Tone.navy,
                  onPressed: () => unawaited(_send()),
                ),
              ),
            ],
            TextButton(
              onPressed: _recording ? null : () => Navigator.of(context).pop(),
              child: Text(l10n.actionCancel),
            ),
          ],
        ),
      ),
    );
  }
}
