import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../../core/storage/secure_store.dart';
import 'prevention_models.dart';

/// Named blobs on the phone: files in the app's private folder, or memory in tests.
abstract class BlobStore {
  Future<Uint8List?> read(String name);
  Future<void> write(String name, List<int> bytes);
  Future<void> delete(String name);
  Future<List<String>> names();
}

class FileBlobStore implements BlobStore {
  FileBlobStore([Future<Directory> Function()? root])
    : _root = root ?? getApplicationSupportDirectory;

  final Future<Directory> Function() _root;
  Directory? _dir;

  Future<Directory> _folder() async {
    final dir = _dir ??= Directory(
      p.join((await _root()).path, 'staff_visits'),
    );
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<File> _file(String name) async =>
      File(p.join((await _folder()).path, name));

  @override
  Future<Uint8List?> read(String name) async {
    final f = await _file(name);
    return await f.exists() ? f.readAsBytes() : null;
  }

  @override
  Future<void> write(String name, List<int> bytes) async {
    // Written next to the old copy, then renamed: a crash leaves one whole copy.
    final f = await _file(name);
    final tmp = File('${f.path}.tmp');
    await tmp.writeAsBytes(bytes, flush: true);
    await tmp.rename(f.path);
  }

  @override
  Future<void> delete(String name) async {
    final f = await _file(name);
    if (await f.exists()) await f.delete();
  }

  @override
  Future<List<String>> names() async => [
    await for (final e in (await _folder()).list())
      if (e is File && !e.path.endsWith('.tmp')) p.basename(e.path),
  ];
}

class MemoryBlobStore implements BlobStore {
  final values = <String, Uint8List>{};

  @override
  Future<Uint8List?> read(String name) async => values[name];

  @override
  Future<void> write(String name, List<int> bytes) async =>
      values[name] = Uint8List.fromList(bytes);

  @override
  Future<void> delete(String name) async => values.remove(name);

  @override
  Future<List<String>> names() async => [...values.keys];
}

/// The visits downloaded on the inspector's phone, their drafts and their photos (design §8.2).
/// Everything is sealed with AES-256-GCM under a key kept in the keystore; erasing that key (sign-out,
/// remote wipe, five wrong PINs) leaves nothing readable, and the files are deleted too.
class PreventionBox {
  PreventionBox(this._blobs, this._secure);

  /// In [StaffVault.keys]: the vault's wipe erases it with the tokens.
  static const keyName = 'staff_visits_key_v1';
  static final _aes = AesGcm.with256bits();

  final BlobStore _blobs;
  final SecureStore _secure;
  SecretKey? _key;

  Future<SecretKey> _secret({bool create = true}) async {
    final known = _key;
    if (known != null) return known;
    final stored = await _secure.read(keyName);
    if (stored != null) return _key = SecretKey(base64.decode(stored));
    if (!create) throw StateError('no key');
    // A new key: whatever was sealed under a lost one cannot be opened any more.
    await _clearFiles();
    final key = await _aes.newSecretKey();
    await _secure.write(keyName, base64.encode(await key.extractBytes()));
    return _key = key;
  }

  Future<List<int>> _seal(List<int> clear) async {
    final box = await _aes.encrypt(clear, secretKey: await _secret());
    return box.concatenation();
  }

  Future<List<int>?> _open(String name) async {
    final sealed = await _blobs.read(name);
    if (sealed == null) return null;
    try {
      final box = SecretBox.fromConcatenation(
        sealed,
        nonceLength: _aes.nonceLength,
        macLength: _aes.macAlgorithm.macLength,
      );
      return await _aes.decrypt(box, secretKey: await _secret());
    } on Object {
      return null;
    }
  }

  static String _visit(String id) => 'visit-$id.bin';
  static String _photo(String visitId, String photoId) =>
      'photo-$visitId-$photoId.bin';

  Future<Map<String, VisitPack>> load() async {
    if (await _secure.read(keyName) == null) {
      await _clearFiles();
      return {};
    }
    final out = <String, VisitPack>{};
    for (final name in await _blobs.names()) {
      if (!name.startsWith('visit-')) continue;
      final clear = await _open(name);
      if (clear == null) continue;
      final pack = VisitPack.fromJson(
        jsonDecode(utf8.decode(clear)) as Map<String, dynamic>,
      );
      out[pack.visit.id] = pack;
    }
    return out;
  }

  Future<void> save(VisitPack pack) async => _blobs.write(
    _visit(pack.visit.id),
    await _seal(utf8.encode(jsonEncode(pack.toJson()))),
  );

  Future<void> savePhoto(
    String visitId,
    String photoId,
    List<int> bytes,
  ) async => _blobs.write(_photo(visitId, photoId), await _seal(bytes));

  Future<Uint8List?> photo(String visitId, String photoId) async {
    final clear = await _open(_photo(visitId, photoId));
    return clear == null ? null : Uint8List.fromList(clear);
  }

  Future<void> deletePhoto(String visitId, String photoId) =>
      _blobs.delete(_photo(visitId, photoId));

  /// The visit, its draft and its photos.
  Future<void> remove(String visitId) async {
    for (final name in await _blobs.names()) {
      if (name == _visit(visitId) || name.startsWith('photo-$visitId-')) {
        await _blobs.delete(name);
      }
    }
  }

  Future<void> wipe() async {
    _key = null;
    await _secure.delete(keyName);
    await _clearFiles();
  }

  Future<void> _clearFiles() async {
    for (final name in await _blobs.names()) {
      await _blobs.delete(name);
    }
  }
}

final blobStoreProvider = Provider<BlobStore>((ref) => FileBlobStore());

final preventionBoxProvider = Provider<PreventionBox>(
  (ref) => PreventionBox(
    ref.watch(blobStoreProvider),
    ref.watch(secureStoreProvider),
  ),
);
