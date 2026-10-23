import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/logging/log.dart';
import '../../core/settings/settings_controller.dart';
import 'places_models.dart';

final _log = logger('places');

/// Where the offline copies of the layers live: one small text document per name.
abstract class PlacesStore {
  Future<String?> read(String name);
  Future<void> write(String name, String text);
  Future<void> delete(String name);
}

/// Files in the app's support folder (`places/`), out of the backed-up documents.
class FilePlacesStore implements PlacesStore {
  Future<File> _file(String name) async {
    final dir = Directory(
      '${(await getApplicationSupportDirectory()).path}/places',
    );
    if (!dir.existsSync()) await dir.create(recursive: true);
    return File('${dir.path}/$name.json');
  }

  @override
  Future<String?> read(String name) async {
    final f = await _file(name);
    return f.existsSync() ? f.readAsString() : null;
  }

  @override
  Future<void> write(String name, String text) async {
    final f = await _file(name);
    // Written beside, then renamed: a copy is never left half written.
    final tmp = File('${f.path}.tmp');
    await tmp.writeAsString(text, flush: true);
    await tmp.rename(f.path);
  }

  @override
  Future<void> delete(String name) async {
    final f = await _file(name);
    if (f.existsSync()) await f.delete();
  }
}

class MemoryPlacesStore implements PlacesStore {
  final docs = <String, String>{};
  @override
  Future<String?> read(String name) async => docs[name];
  @override
  Future<void> write(String name, String text) async => docs[name] = text;
  @override
  Future<void> delete(String name) async => docs.remove(name);
}

final placesStoreProvider = Provider<PlacesStore>((ref) => FilePlacesStore());

/// The public layers and their places, as last downloaded.
class PlacesData {
  const PlacesData({
    required this.layers,
    required this.packages,
    this.updatedAt,
    this.refreshFailed = false,
  });

  final List<PlaceLayer> layers;
  final Map<String, PlacePackage> packages;
  final DateTime? updatedAt;

  /// The last refresh did not reach the server: the copy shown may be old.
  final bool refreshFailed;

  bool get isEmpty => layers.isEmpty;

  PlacesData copyWith({bool? refreshFailed}) => PlacesData(
    layers: layers,
    packages: packages,
    updatedAt: updatedAt,
    refreshFailed: refreshFailed ?? this.refreshFailed,
  );
}

/// "Nearest to me", offline (phase B1): the list of public layers and the whole country's places
/// of each, asked again with their ETags so an unchanged layer costs a `304`. A layer that is no
/// longer public is forgotten at the next refresh.
class PlacesRepository {
  PlacesRepository(this._store, this._api, this._clock);

  final PlacesStore _store;
  final EHimayaApi _api;
  final DateTime Function() _clock;

  static const _index = 'layers';
  static String _package(String key) => 'layer-$key';

  Future<PlacesData> local() async {
    try {
      final raw = await _store.read(_index);
      if (raw == null) return const PlacesData(layers: [], packages: {});
      final index = jsonDecode(raw) as Map<String, Object?>;
      final layers = [
        for (final l in index['items']! as List)
          PlaceLayer.fromJson(l as Map<String, Object?>),
      ];
      final packages = <String, PlacePackage>{};
      for (final layer in layers) {
        final text = await _store.read(_package(layer.key));
        if (text == null) continue;
        packages[layer.key] = PlacePackage.fromJson(
          jsonDecode(text) as Map<String, Object?>,
        );
      }
      return PlacesData(
        layers: layers,
        packages: packages,
        updatedAt: DateTime.tryParse('${index['updated_at']}'),
      );
    } on Object catch (e) {
      // Unreadable copy: start again from the server.
      _log.warning('offline places unreadable: $e');
      return const PlacesData(layers: [], packages: {});
    }
  }

  /// Brings every copy up to date. Throws [ApiException] when the server cannot be reached.
  Future<PlacesData> refresh(PlacesData current, String lang) async {
    final index = await _store.read(_index);
    final indexEtag = index == null
        ? null
        : (jsonDecode(index) as Map<String, Object?>)['etag'] as String?;
    final fetch = await _api.publicLayers(
      etag: current.layers.isEmpty ? null : indexEtag,
    );
    final layers = fetch.layers ?? current.layers;
    final packages = <String, PlacePackage>{};
    for (final layer in layers) {
      final held = current.packages[layer.key];
      final sameLang = held?.lang == lang;
      final got = await _api.layerPackage(
        layer.key,
        lang: lang,
        etag: sameLang ? held?.etag : null,
      );
      final package = got.package;
      if (package == null) {
        packages[layer.key] = held!;
        continue;
      }
      final stored = PlacePackage(
        layer: layer.key,
        places: package.places,
        etag: got.etag,
        lang: lang,
        truncated: package.truncated,
      );
      await _store.write(_package(layer.key), jsonEncode(stored.toJson()));
      packages[layer.key] = stored;
    }
    for (final gone in current.layers.where(
      (l) => !layers.any((k) => k.key == l.key),
    )) {
      await _store.delete(_package(gone.key));
    }
    final now = _clock();
    await _store.write(
      _index,
      jsonEncode({
        'etag': fetch.etag,
        'updated_at': now.toIso8601String(),
        'items': [for (final l in layers) l.toJson()],
      }),
    );
    return PlacesData(layers: layers, packages: packages, updatedAt: now);
  }
}

final placesRepositoryProvider = Provider<PlacesRepository>(
  (ref) => PlacesRepository(
    ref.watch(placesStoreProvider),
    ref.watch(apiProvider),
    ref.watch(clockProvider),
  ),
);

/// Shown at once from the offline copy, then refreshed in the background.
class PlacesController extends AsyncNotifier<PlacesData> {
  @override
  Future<PlacesData> build() async {
    final repo = ref.watch(placesRepositoryProvider);
    final local = await repo.local();
    unawaited(_refresh(repo, local));
    return local;
  }

  Future<void> _refresh(PlacesRepository repo, PlacesData from) async {
    try {
      final fresh = await repo.refresh(from, ref.read(localeCodeProvider));
      if (ref.mounted) state = AsyncData(fresh);
    } on ApiException catch (e) {
      _log.info('places not refreshed: ${e.code.wire}');
      if (ref.mounted) state = AsyncData(from.copyWith(refreshFailed: true));
    }
  }

  Future<void> refresh() async {
    final current = state.value;
    if (current == null) return;
    await _refresh(ref.read(placesRepositoryProvider), current);
  }
}

final placesProvider = AsyncNotifierProvider<PlacesController, PlacesData>(
  PlacesController.new,
  retry: (_, _) => null,
);
