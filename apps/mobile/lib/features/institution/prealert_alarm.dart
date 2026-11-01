import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import 'package:logging/logging.dart';

final _log = Logger('prealert.alarm');

/// The alarm of the fire pre-alert (Yamen, 2026-11-01), played in a loop while the screen waits
/// for the safety officer or the owner, and stopped by an answer or the «silence» button. The
/// notification itself already rings on the alarm stream through silent mode and Do Not Disturb
/// (`prealertChannelId`); this keeps the sound once the screen is open.
abstract class PrealertAlarm {
  Future<void> start();
  Future<void> stop();
}

class AudioPrealertAlarm implements PrealertAlarm {
  AudioPlayer? _player;

  @override
  Future<void> start() async {
    try {
      final player = _player ??= AudioPlayer();
      await player.setAsset('assets/sounds/ehimaya_alert.ogg');
      await player.setLoopMode(LoopMode.one);
      await player.setVolume(1);
      await player.play();
    } on Object catch (e) {
      // No audio output (tests, a phone without the codec): the notification still rang.
      _log.info('alarm unavailable: ${e.runtimeType}');
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _player?.stop();
      await _player?.dispose();
    } on Object {
      // Nothing playing.
    }
    _player = null;
  }
}

/// Silent in tests (overridden), the real alarm in the app.
final prealertAlarmProvider = Provider<PrealertAlarm>(
  (ref) => AudioPrealertAlarm(),
);
