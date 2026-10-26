import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:torch_light/torch_light.dart';

import '../logging/log.dart';

final _log = logger('torch');

/// The camera light, flashed for deaf and hard-of-hearing users when an urgent alert arrives.
abstract class Torch {
  Future<bool> available();

  /// [times] flashes at one per second, well under the three per second of WCAG 2.3.1.
  Future<void> flash({int times = 3});
}

class DeviceTorch implements Torch {
  bool _busy = false;

  @override
  Future<bool> available() async {
    try {
      return await TorchLight.isTorchAvailable();
    } on Object catch (e) {
      _log.info('torch unavailable: ${e.runtimeType}');
      return false;
    }
  }

  @override
  Future<void> flash({int times = 3}) async {
    if (_busy) return;
    _busy = true;
    try {
      for (var i = 0; i < times; i++) {
        await TorchLight.enableTorch();
        await Future<void>.delayed(const Duration(milliseconds: 500));
        await TorchLight.disableTorch();
        await Future<void>.delayed(const Duration(milliseconds: 500));
      }
    } on Object catch (e) {
      // Camera in use by another app, no flash on this phone: the screen flash still works.
      _log.info('torch flash failed: ${e.runtimeType}');
    } finally {
      _busy = false;
    }
  }
}

final torchProvider = Provider<Torch>((ref) => DeviceTorch());
