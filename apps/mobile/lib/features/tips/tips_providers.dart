import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/notify_models.dart';
import '../../core/logging/log.dart';
import '../../core/storage/app_prefs.dart';

final _log = logger('tips');

/// Copy of the seed tips shipped in the app (first launch without network).
const bundledTipsAsset = 'assets/safety_tips.json';

typedef BundledTipsLoader = Future<String> Function();

final bundledTipsLoaderProvider = Provider<BundledTipsLoader>(
  (ref) =>
      () => rootBundle.loadString(bundledTipsAsset),
);

/// Safety tips readable offline (FR-A-062): the last copy downloaded, else the bundled one. The
/// server is asked with the stored ETag, so an unchanged list costs a `304` and no download.
class TipsRepository {
  TipsRepository(this._prefs, this._api, this._bundled);

  final AppPrefs _prefs;
  final EHimayaApi _api;
  final BundledTipsLoader _bundled;

  /// The stored copy, or the bundled one when none was downloaded yet (or it is unreadable).
  Future<SafetyTips> local() async {
    final raw = _prefs.tipsJson;
    if (raw != null) {
      try {
        final tips = SafetyTips.fromJson(jsonDecode(raw));
        if (tips.items.isNotEmpty) return tips;
      } on FormatException {
        // Corrupted copy: fall back to the bundled one.
      }
    }
    return SafetyTips.fromJson(jsonDecode(await _bundled()));
  }

  /// Asks the server for a newer copy. Returns it, or null when the stored one is current.
  Future<SafetyTips?> refresh() async {
    final hasCopy = _prefs.tipsJson != null;
    final fetch = await _api.safetyTips(etag: hasCopy ? _prefs.tipsEtag : null);
    final tips = fetch.tips;
    if (tips == null) return null;
    await _prefs.setTips(
      jsonEncode({
        'revision': tips.revision,
        'items': [
          for (final t in tips.items)
            {
              'id': t.id,
              'hazard': t.hazard.wire,
              'position': t.position,
              'content': {
                for (final e in t.content.entries)
                  e.key: {
                    'title': e.value.title,
                    'do': e.value.doItems,
                    'dont': e.value.dontItems,
                  },
              },
            },
        ],
      }),
      fetch.etag,
    );
    return tips;
  }
}

final tipsRepositoryProvider = Provider<TipsRepository>(
  (ref) => TipsRepository(
    ref.watch(appPrefsProvider),
    ref.watch(apiProvider),
    ref.watch(bundledTipsLoaderProvider),
  ),
);

/// Shown at once from the local copy, then updated from the server in the background.
class SafetyTipsController extends AsyncNotifier<SafetyTips> {
  @override
  Future<SafetyTips> build() async {
    final repo = ref.watch(tipsRepositoryProvider);
    final local = await repo.local();
    unawaited(_refresh(repo));
    return local;
  }

  Future<void> _refresh(TipsRepository repo) async {
    try {
      final fresh = await repo.refresh();
      if (fresh != null && fresh.items.isNotEmpty && ref.mounted) {
        state = AsyncData(fresh);
      }
    } on ApiException catch (e) {
      _log.info('tips not refreshed: ${e.code.wire}');
    }
  }

  Future<void> refresh() => _refresh(ref.read(tipsRepositoryProvider));
}

final safetyTipsProvider =
    AsyncNotifierProvider<SafetyTipsController, SafetyTips>(
      SafetyTipsController.new,
      retry: (_, _) => null,
    );
