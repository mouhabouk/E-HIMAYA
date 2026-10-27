import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../core/connectivity/connectivity.dart';
import '../../core/logging/log.dart';
import '../staff_api.dart';
import '../staff_auth.dart';
import '../staff_controller.dart';
import '../staff_models.dart';
import 'prevention_labels.dart' show isoDay;
import 'prevention_models.dart';
import 'prevention_store.dart';

final _log = logger('staff.prevention');

/// At most this many photos for one visit (the server's limit).
const visitPhotoLimit = 20;

/// How often the phone tries again to send what waits, while something waits.
const visitRetryEvery = Duration(seconds: 30);

@immutable
class PreventionState {
  const PreventionState({
    this.visits = const [],
    this.packs = const {},
    this.loaded = false,
    this.busy = false,
    this.syncing = false,
    this.error,
  });

  /// The server's list (the last one), or the visits kept on the phone when there is no network.
  final List<FieldVisit> visits;

  /// The visits downloaded on the phone, with their drafts.
  final Map<String, VisitPack> packs;
  final bool loaded;
  final bool busy;
  final bool syncing;

  /// The server's refusal of the last call (`visit_taken`…).
  final String? error;

  FieldVisit? visit(String id) {
    final kept = packs[id];
    if (kept != null) return kept.visit;
    for (final v in visits) {
      if (v.id == id) return v;
    }
    return null;
  }

  /// The visits to show: the server's list with the phone's copies in it, and the phone's copies
  /// the list no longer has (still waiting to be sent).
  List<FieldVisit> get shown {
    final ids = {for (final v in visits) v.id};
    return [
      for (final v in visits) packs[v.id]?.visit ?? v,
      for (final p in packs.values)
        if (!ids.contains(p.visit.id)) p.visit,
    ];
  }

  int get pending => packs.values.fold(0, (n, p) => n + p.draft.pending);

  PreventionState copyWith({
    List<FieldVisit>? visits,
    Map<String, VisitPack>? packs,
    bool? loaded,
    bool? busy,
    bool? syncing,
    String? error,
    bool clearError = false,
  }) => PreventionState(
    visits: visits ?? this.visits,
    packs: packs ?? this.packs,
    loaded: loaded ?? this.loaded,
    busy: busy ?? this.busy,
    syncing: syncing ?? this.syncing,
    error: clearError ? null : error ?? this.error,
  );
}

/// The inspector's visits (phase P4c, design §8): the list, «آخذها», the grid filled offline, the
/// photos, both signatures and the decision, kept sealed on the phone and sent in order when the
/// network is there: the photos, then the inspection, then the decision (design §8.6).
class PreventionController extends Notifier<PreventionState> {
  Timer? _retry;
  StreamSubscription<bool>? _online;
  Future<void>? _loading;

  StaffApi get _api => ref.read(staffApiProvider);
  PreventionBox get _box => ref.read(preventionBoxProvider);
  StaffController get _staff => ref.read(staffControllerProvider.notifier);

  @override
  PreventionState build() {
    ref.listen(staffControllerProvider.select((s) => s.phase), (_, phase) {
      if (phase == StaffPhase.signedOut) unawaited(_erase());
    });
    _online = ref
        .read(connectivityProvider)
        .onlineChanges
        .listen((up) => up ? unawaited(sync()) : null);
    _retry = Timer.periodic(visitRetryEvery, (_) {
      if (state.pending > 0) unawaited(sync());
    });
    ref.onDispose(() {
      _retry?.cancel();
      unawaited(_online?.cancel());
    });
    return const PreventionState();
  }

  Future<void> _erase() async {
    await _box.wipe();
    state = const PreventionState(loaded: true);
  }

  /// Runs a call to the server. A revoked phone is erased; a refusal is kept in [state] (and on
  /// the visit's draft); a network error leaves the phone's copy. Null on failure.
  Future<T?> _net<T>(Future<T> Function() call, {String? visitId}) async {
    try {
      final out = await call();
      _staff.network(ok: true);
      return out;
    } on DeviceRevoked catch (e) {
      await _staff.forceSignOut(e);
    } on StaffSignedOut catch (e) {
      await _staff.forceSignOut(e);
    } on CrewError catch (e) {
      _log.info('prevention call refused: ${e.code}');
      state = state.copyWith(error: e.code);
      if (visitId != null) {
        await _edit(visitId, (d) => d.copyWith(error: e.code));
      }
    } on Object catch (e) {
      _log.info('prevention call failed: $e');
      _staff.network(ok: false);
    }
    return null;
  }

  /// The phone's copies, then the server's list; then whatever waits is sent.
  Future<void> load() =>
      _loading ??= _load().whenComplete(() => _loading = null);

  Future<void> _load() async {
    if (!state.loaded) {
      state = state.copyWith(packs: await _box.load(), loaded: true);
    }
    final list = await _net(_api.visits);
    if (list != null) {
      state = state.copyWith(visits: list, clearError: true);
      for (final v in list) {
        final kept = state.packs[v.id];
        if (kept != null) await _put(kept.withVisit(v));
      }
    }
    await sync();
  }

  Future<void> _saved = Future.value();

  /// The new copy is shown at once; the sealed writes follow one another, the last one wins.
  Future<void> _put(VisitPack pack) {
    final id = pack.visit.id;
    state = state.copyWith(packs: {...state.packs, id: pack});
    return _saved = _saved
        .then((_) async {
          final latest = state.packs[id];
          if (latest != null) await _box.save(latest);
        })
        .catchError((Object e) => _log.warning('visit not saved: $e'));
  }

  Future<void> _edit(
    String id,
    InspectionDraft Function(InspectionDraft) change,
  ) async {
    final pack = state.packs[id];
    if (pack == null) return;
    await _put(pack.withDraft(change(pack.draft)));
  }

  /// «آخذها»: the visit is the inspector's and is kept on the phone for the visit offline.
  Future<bool> take(String id) async {
    state = state.copyWith(busy: true, clearError: true);
    final v = await _net(() => _api.claimVisit(id));
    state = state.copyWith(busy: false);
    if (v == null) return false;
    final kept = state.packs[id];
    await _put(
      kept?.withVisit(v) ??
          VisitPack(
            v,
            InspectionDraft(representativeName: v.declaredRepresentative),
          ),
    );
    state = state.copyWith(
      visits: [for (final x in state.visits) x.id == id ? v : x],
    );
    return true;
  }

  // ------------------------------------------------------------------ the grid

  Future<void> result(String id, String key, Finding f) => _edit(
    id,
    (d) => d.copyWith(
      items: {
        ...d.items,
        key: d.item(key).copyWith(result: f),
      },
    ),
  );

  /// "All conform" for one section.
  Future<void> sectionConform(String id, List<String> keys) => _edit(
    id,
    (d) => d.copyWith(
      items: {
        ...d.items,
        for (final k in keys) k: d.item(k).copyWith(result: Finding.conform),
      },
    ),
  );

  Future<void> count(String id, String key, int value) => _edit(
    id,
    (d) => d.copyWith(
      items: {
        ...d.items,
        key: d.item(key).copyWith(count: value < 0 ? 0 : value),
      },
    ),
  );

  Future<void> reason(String id, String key, String reason) => _edit(id, (d) {
    final item = d.item(key);
    final reasons = item.reasons.contains(reason)
        ? [
            for (final r in item.reasons)
              if (r != reason) r,
          ]
        : [...item.reasons, reason];
    return d.copyWith(
      items: {
        ...d.items,
        key: item.copyWith(reasons: reasons),
      },
    );
  });

  Future<void> note(String id, String key, String note) => _edit(
    id,
    (d) => d.copyWith(
      items: {
        ...d.items,
        key: d.item(key).copyWith(note: note.trim()),
      },
    ),
  );

  /// A photo for an item (or the visit), kept sealed until the server has it.
  Future<bool> photo(String id, String? itemKey, CapturedMedia media) async {
    final pack = state.packs[id];
    if (pack == null || pack.draft.photos.length >= visitPhotoLimit) {
      return false;
    }
    final photo = DraftPhoto(
      id: const Uuid().v4(),
      contentType: media.contentType,
      takenAt: DateTime.now(),
      itemKey: itemKey,
    );
    await _box.savePhoto(id, photo.id, media.bytes);
    await _edit(id, (d) => d.copyWith(photos: [...d.photos, photo]));
    unawaited(sync());
    return true;
  }

  // ------------------------------------------------------------------ signatures

  Future<void> attendee(String id, String who) => _edit(
    id,
    (d) => d.copyWith(
      attendees: d.attendees.contains(who)
          ? [
              for (final a in d.attendees)
                if (a != who) a,
            ]
          : [...d.attendees, who],
    ),
  );

  Future<void> representative(String id, {String? name, String? role}) => _edit(
    id,
    (d) => d.copyWith(representativeName: name, representativeRole: role),
  );

  Future<void> signature(String id, {required bool inspector, String? png}) =>
      _edit(
        id,
        (d) => inspector
            ? d.copyWith(
                inspectorSignature: png,
                clearInspectorSignature: png == null,
              )
            : d.copyWith(
                representativeSignature: png,
                clearRepresentativeSignature: png == null,
              ),
      );

  /// Closes the inspection: the grid, the attendees and both signatures go in the box, and are
  /// sent at once when the network is there. [noteOf] and [roleText] give the words of the
  /// chips in the inspector's language.
  Future<void> signOff(
    String id, {
    required String Function(ItemDraft) noteOf,
    required String? Function(String?) roleText,
    required String attendees,
  }) async {
    final pack = state.packs[id];
    if (pack == null) return;
    final d = pack.draft;
    final now = DateTime.now();
    final body = <String, dynamic>{
      'client_id': const Uuid().v4(),
      'device_at': now.toUtc().toIso8601String(),
      'inspected_on': isoDay(now),
      if (attendees.isNotEmpty) 'attendees': attendees,
      'items': [
        for (final i in pack.visit.checklist)
          if (d.item(i.key).result != Finding.notChecked)
            {
              'key': i.key,
              'result': d.item(i.key).result.wire,
              if (d.item(i.key).result == Finding.nonconform) ...{
                if (d.item(i.key).count != null)
                  'observed': '${d.item(i.key).count}',
                if (noteOf(d.item(i.key)).isNotEmpty)
                  'note': noteOf(d.item(i.key)),
              },
            },
      ],
      'representative_name': d.representativeName?.trim(),
      'representative_role': ?roleText(d.representativeRole),
      'inspector_signature': d.inspectorSignature,
      'representative_signature': d.representativeSignature,
    };
    await _edit(id, (d) => d.copyWith(inspection: body, clearError: true));
    await sync();
  }

  /// The decision with its reservations; sent after the inspection (design §8.5).
  Future<void> decide(String id, Map<String, dynamic> body) async {
    await _edit(id, (d) => d.copyWith(decision: body, clearError: true));
    await sync();
  }

  // ------------------------------------------------------------------ sending

  /// Sends what waits, visit by visit, in order. Stops at the first network error.
  Future<void> sync() async {
    if (state.syncing || state.pending == 0) return;
    state = state.copyWith(syncing: true);
    try {
      for (final id in [...state.packs.keys]) {
        if (!await _send(id)) break;
      }
    } finally {
      state = state.copyWith(syncing: false);
    }
  }

  /// False when the network failed (nothing more is tried now).
  Future<bool> _send(String id) async {
    var pack = state.packs[id];
    if (pack == null || pack.draft.pending == 0) return true;
    if (pack.draft.error != null) {
      await _edit(id, (d) => d.copyWith(clearError: true));
    }
    for (final photo in pack.draft.photos.where((p) => !p.sent)) {
      final bytes = await _box.photo(id, photo.id);
      FieldVisit? v;
      if (bytes != null) {
        v = await _net(() => _api.visitPhoto(id, photo, bytes), visitId: id);
        if (v == null && state.packs[id]?.draft.error == null) return false;
      }
      // Sent, refused (wrong type, too many) or lost: it no longer waits.
      pack = state.packs[id]!;
      final sent = [
        for (final p in pack.draft.photos)
          p.id == photo.id
              ? DraftPhoto(
                  id: p.id,
                  contentType: p.contentType,
                  takenAt: p.takenAt,
                  itemKey: p.itemKey,
                  sent: true,
                )
              : p,
      ];
      await _put(
        (v == null ? pack : pack.withVisit(v)).withDraft(
          pack.draft.copyWith(photos: sent),
        ),
      );
      await _box.deletePhoto(id, photo.id);
    }
    pack = state.packs[id]!;
    final inspection = pack.draft.inspection;
    if (inspection != null && !pack.draft.inspectionSent) {
      final v = await _net(
        () => _api.visitInspection(id, inspection),
        visitId: id,
      );
      if (v == null) return state.packs[id]?.draft.error != null;
      pack = state.packs[id]!;
      await _put(
        pack
            .withVisit(v)
            .withDraft(
              pack.draft.copyWith(inspectionSent: true, clearError: true),
            ),
      );
    }
    pack = state.packs[id]!;
    final decision = pack.draft.decision;
    // After the inspection sent from this phone, or one recorded on the dashboard.
    final inspected =
        pack.draft.inspectionSent ||
        (pack.draft.inspection == null && pack.visit.inspected);
    if (decision != null && inspected) {
      final v = await _net(() => _api.visitDecision(id, decision), visitId: id);
      if (v == null) {
        if (state.packs[id]?.draft.error == null) return false;
        // Refused (a date out of range…): the inspector decides again.
        await _edit(id, (d) => d.copyWith(clearDecision: true));
        return true;
      }
      // Decided: the certificate is issued and nothing stays on the phone.
      state = state.copyWith(
        packs: {...state.packs}..remove(id),
        visits: [
          for (final x in state.visits)
            if (x.id != id) x,
        ],
      );
      await (_saved = _saved.then((_) => _box.remove(id)));
    }
    return true;
  }
}

final preventionControllerProvider =
    NotifierProvider<PreventionController, PreventionState>(
      PreventionController.new,
    );
