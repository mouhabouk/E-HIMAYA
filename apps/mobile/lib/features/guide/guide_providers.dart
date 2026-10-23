import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/logging/log.dart';
import '../../core/storage/app_prefs.dart';
import 'guide_models.dart';

final _log = logger('guide');

/// Copy of the first load of the guide shipped in the app (scripts/guide_seed.py).
const bundledGuideAsset = 'assets/emergency_guide.json';

typedef BundledGuideLoader = Future<String> Function();

final bundledGuideLoaderProvider = Provider<BundledGuideLoader>(
  (ref) =>
      () => rootBundle.loadString(bundledGuideAsset),
);

/// Emergency guide readable offline: the last copy downloaded, else the bundled one. Asked with
/// the stored ETag, so an unchanged guide costs a `304`. A topic or item the content editors
/// hide disappears at the next refresh; one they add or change appears.
class GuideRepository {
  GuideRepository(this._prefs, this._api, this._bundled);

  final AppPrefs _prefs;
  final EHimayaApi _api;
  final BundledGuideLoader _bundled;

  Future<EmergencyGuide> local() async {
    final raw = _prefs.guideJson;
    if (raw != null) {
      try {
        final guide = EmergencyGuide.fromJson(jsonDecode(raw));
        return guide;
      } on FormatException {
        // Corrupted copy: fall back to the bundled one.
      }
    }
    return EmergencyGuide.fromJson(jsonDecode(await _bundled()));
  }

  /// Returns the newer copy, or null when the stored one is current.
  Future<EmergencyGuide?> refresh() async {
    final hasCopy = _prefs.guideJson != null;
    final fetch = await _api.emergencyGuide(
      etag: hasCopy ? _prefs.guideEtag : null,
    );
    final guide = fetch.guide;
    if (guide == null) return null;
    await _prefs.setGuide(jsonEncode(guide.toJson()), fetch.etag);
    return guide;
  }
}

final guideRepositoryProvider = Provider<GuideRepository>(
  (ref) => GuideRepository(
    ref.watch(appPrefsProvider),
    ref.watch(apiProvider),
    ref.watch(bundledGuideLoaderProvider),
  ),
);

/// Shown at once from the local copy, then updated from the server in the background. An empty
/// published guide (every topic hidden) is shown as such.
class EmergencyGuideController extends AsyncNotifier<EmergencyGuide> {
  @override
  Future<EmergencyGuide> build() async {
    final repo = ref.watch(guideRepositoryProvider);
    final local = await repo.local();
    unawaited(_refresh(repo));
    return local;
  }

  Future<void> _refresh(GuideRepository repo) async {
    try {
      final fresh = await repo.refresh();
      if (fresh != null && ref.mounted) state = AsyncData(fresh);
    } on ApiException catch (e) {
      _log.info('guide not refreshed: ${e.code.wire}');
    }
  }

  Future<void> refresh() => _refresh(ref.read(guideRepositoryProvider));
}

final emergencyGuideProvider =
    AsyncNotifierProvider<EmergencyGuideController, EmergencyGuide>(
      EmergencyGuideController.new,
      retry: (_, _) => null,
    );
