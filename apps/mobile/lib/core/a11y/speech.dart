import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../logging/log.dart';

final _log = logger('speech');

/// What happened when the app asked the phone to speak.
enum SpeechStart { started, noVoice, failed }

/// The phone's own speech engine (Android TextToSpeech, iOS AVSpeechSynthesizer): nothing is
/// sent anywhere (NFR-10, reading aloud for the visually impaired).
abstract class Speech {
  /// Starts reading [text] in [lang] ('ar', 'fr', 'en'); [onDone] runs when it ends or stops.
  Future<SpeechStart> speak(
    String text,
    String lang, {
    required void Function() onDone,
  });

  Future<void> stop();
}

class DeviceSpeech implements Speech {
  DeviceSpeech() : _tts = FlutterTts();

  final FlutterTts _tts;
  void Function()? _onDone;

  /// Voices tried in order for each language: Tunisian Arabic first when the phone has it.
  static const voices = {
    'ar': ['ar-TN', 'ar-SA', 'ar'],
    'fr': ['fr-FR', 'fr'],
    'en': ['en-US', 'en-GB', 'en'],
  };

  void _done() {
    final f = _onDone;
    _onDone = null;
    f?.call();
  }

  @override
  Future<SpeechStart> speak(
    String text,
    String lang, {
    required void Function() onDone,
  }) async {
    try {
      await _tts.stop();
      String? voice;
      for (final v in voices[lang] ?? [lang]) {
        if (await _tts.isLanguageAvailable(v) == true) {
          voice = v;
          break;
        }
      }
      if (voice == null) return SpeechStart.noVoice;
      await _tts.setLanguage(voice);
      // A little slower than the default: emergency instructions must be understood the first time.
      await _tts.setSpeechRate(0.45);
      _tts
        ..setCompletionHandler(_done)
        ..setCancelHandler(_done)
        ..setErrorHandler((_) => _done());
      _onDone = onDone;
      final r = await _tts.speak(text);
      if (r != 1) {
        _onDone = null;
        return SpeechStart.failed;
      }
      return SpeechStart.started;
    } on Object catch (e) {
      _log.info('speech unavailable: ${e.runtimeType}');
      return SpeechStart.failed;
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _tts.stop();
    } on Object catch (e) {
      _log.info('speech stop failed: ${e.runtimeType}');
    }
    _done();
  }
}

final speechProvider = Provider<Speech>((ref) => DeviceSpeech());

/// The text being read aloud (its key), or null: one text at a time in the whole app.
class SpeakingController extends Notifier<String?> {
  @override
  String? build() => null;

  /// Reads [text] under [key], or stops it when it is the one being read.
  Future<SpeechStart?> toggle(String key, String text, String lang) async {
    final speech = ref.read(speechProvider);
    if (state == key) {
      await speech.stop();
      state = null;
      return null;
    }
    state = key;
    final r = await speech.speak(
      text,
      lang,
      onDone: () {
        if (state == key) state = null;
      },
    );
    if (r != SpeechStart.started && state == key) state = null;
    return r;
  }

  /// Stops the reading of [key] only (a page closing must not cut another page's reading).
  Future<void> stopIf(String key) async {
    if (state == key) await stop();
  }

  Future<void> stop() async {
    if (state == null) return;
    state = null;
    await ref.read(speechProvider).stop();
  }
}

final speakingProvider = NotifierProvider<SpeakingController, String?>(
  SpeakingController.new,
);
