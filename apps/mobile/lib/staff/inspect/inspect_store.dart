import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/storage/secure_store.dart';
import '../prevention/prevention_store.dart';
import 'inspect_models.dart';

/// The inspector's tokens and the matricule typed at registration, in the keystore.
class InspectVault {
  InspectVault(this._store);

  final SecureStore _store;

  static const _tokens = 'insp_tokens_v1';
  static const _matricule = 'insp_matricule_v1';

  /// The key that seals the missions and the reports kept on the phone.
  static const boxKey = 'insp_box_key_v1';
  static const keys = [_tokens, _matricule, boxKey];

  Future<InspectTokens?> tokens() async {
    final raw = await _store.read(_tokens);
    if (raw == null) return null;
    try {
      return InspectTokens.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } on Object {
      return null;
    }
  }

  Future<void> saveTokens(InspectTokens t) =>
      _store.write(_tokens, jsonEncode(t.toJson()));

  Future<void> dropTokens() => _store.delete(_tokens);

  Future<String?> matricule() => _store.read(_matricule);

  Future<void> saveMatricule(String m) => _store.write(_matricule, m.trim());

  /// Everything: tokens, matricule and the key of the sealed box (its files become unreadable).
  Future<void> wipe() async {
    for (final k in keys) {
      await _store.delete(k);
    }
  }
}

/// The missions downloaded and the reports on the phone, sealed under [InspectVault.boxKey] in
/// their own folder.
class InspectBox {
  InspectBox(BlobStore blobs, SecureStore secure)
    : _sealed = SealedBlobs(blobs, secure, InspectVault.boxKey);

  final SealedBlobs _sealed;

  static const _missions = 'missions.bin';
  static String _draft(String id) => 'draft-$id.bin';

  Future<List<InspectMission>> missions() async {
    if (!await _sealed.opened()) return const [];
    final j = await _sealed.readJson(_missions);
    return [
      for (final m in (j as List? ?? const []))
        InspectMission.fromJson(m as Map<String, dynamic>),
    ];
  }

  Future<void> saveMissions(List<InspectMission> missions) =>
      _sealed.writeJson(_missions, [for (final m in missions) m.toJson()]);

  Future<Map<String, InspectDraft>> drafts() async {
    if (!await _sealed.opened()) return {};
    final out = <String, InspectDraft>{};
    for (final name in await _sealed.names()) {
      if (!name.startsWith('draft-')) continue;
      final j = await _sealed.readJson(name);
      if (j == null) continue;
      final d = InspectDraft.fromJson(j as Map<String, dynamic>);
      out[d.inspectionId] = d;
    }
    return out;
  }

  Future<void> saveDraft(InspectDraft d) =>
      _sealed.writeJson(_draft(d.inspectionId), d.toJson());

  Future<void> removeDraft(String id) => _sealed.delete(_draft(id));

  Future<void> wipe() => _sealed.wipe();
}

final inspectBlobStoreProvider = Provider<BlobStore>(
  (ref) => FileBlobStore(folder: 'staff_inspections'),
);

final inspectVaultProvider = Provider<InspectVault>(
  (ref) => InspectVault(ref.watch(secureStoreProvider)),
);

final inspectBoxProvider = Provider<InspectBox>(
  (ref) => InspectBox(
    ref.watch(inspectBlobStoreProvider),
    ref.watch(secureStoreProvider),
  ),
);
