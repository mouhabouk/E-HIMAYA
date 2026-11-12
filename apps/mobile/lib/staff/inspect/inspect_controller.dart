import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../core/location/location_service.dart';
import '../staff_controller.dart';
import 'inspect_api.dart';
import 'inspect_models.dart';
import 'inspect_store.dart';

enum InspectPhase { loading, signedOut, active }

class InspectState {
  const InspectState({
    this.phase = InspectPhase.loading,
    this.name,
    this.kind,
    this.expiresOn,
    this.missions = const [],
    this.drafts = const {},
    this.busy = false,
    this.offline = false,
    this.error,
    this.destination,
    this.matricule,
    this.wiped = false,
  });

  final InspectPhase phase;
  final String? name;
  final String? kind;
  final DateTime? expiresOn;
  final List<InspectMission> missions;

  /// The reports on the phone, by inspection id.
  final Map<String, InspectDraft> drafts;
  final bool busy;

  /// The last call found no network: what is shown is the copy on the phone.
  final bool offline;

  /// The server's last refusal (`activation_refused`, `mission_not_today`…).
  final String? error;

  /// Where the activation code goes (masked), after a registration.
  final String? destination;
  final String? matricule;

  /// The account was closed or the phone reported lost: everything was erased.
  final bool wiped;

  int get waiting =>
      drafts.values.where((d) => d.state == DraftState.queued).length;

  InspectDraft? draftOfSite(String siteId) {
    for (final d in drafts.values) {
      if (d.siteId == siteId) return d;
    }
    return null;
  }

  InspectState copyWith({
    InspectPhase? phase,
    String? Function()? name,
    String? Function()? kind,
    DateTime? Function()? expiresOn,
    List<InspectMission>? missions,
    Map<String, InspectDraft>? drafts,
    bool? busy,
    bool? offline,
    String? Function()? error,
    String? Function()? destination,
    String? Function()? matricule,
    bool? wiped,
  }) => InspectState(
    phase: phase ?? this.phase,
    name: name == null ? this.name : name(),
    kind: kind == null ? this.kind : kind(),
    expiresOn: expiresOn == null ? this.expiresOn : expiresOn(),
    missions: missions ?? this.missions,
    drafts: drafts ?? this.drafts,
    busy: busy ?? this.busy,
    offline: offline ?? this.offline,
    error: error == null ? this.error : error(),
    destination: destination == null ? this.destination : destination(),
    matricule: matricule == null ? this.matricule : matricule(),
    wiped: wiped ?? this.wiped,
  );
}

final inspectClockProvider = Provider<DateTime Function()>(
  (ref) => DateTime.now,
);

final inspectApiProvider = Provider<InspectApi>(
  (ref) => InspectApi(
    ref.watch(staffDioProvider),
    ref.watch(staffConfigProvider).apiBaseUrl,
    ref.watch(inspectVaultProvider),
    clock: ref.watch(inspectClockProvider),
  ),
);

/// The inspector's session on this phone (phase I3).
class InspectController extends Notifier<InspectState> {
  InspectApi get _api => ref.read(inspectApiProvider);
  InspectVault get _vault => ref.read(inspectVaultProvider);
  InspectBox get _box => ref.read(inspectBoxProvider);
  DateTime _now() => ref.read(inspectClockProvider)();

  @override
  InspectState build() {
    unawaited(Future.microtask(load));
    return const InspectState();
  }

  /// Reads what the phone keeps, then asks the server for the missions and sends what waits.
  Future<void> load() async {
    final t = await _vault.tokens();
    final matricule = await _vault.matricule();
    if (t == null) {
      state = state.copyWith(
        phase: InspectPhase.signedOut,
        matricule: () => matricule,
      );
      return;
    }
    state = state.copyWith(
      phase: InspectPhase.active,
      name: () => t.name,
      kind: () => t.kind,
      expiresOn: () => t.expiresOn,
      matricule: () => matricule,
      missions: await _box.missions(),
      drafts: await _box.drafts(),
    );
    await refresh();
  }

  Future<T?> _guard<T>(Future<T> Function() run) async {
    try {
      final out = await run();
      state = state.copyWith(offline: false, error: () => null);
      return out;
    } on InspectOffline {
      state = state.copyWith(offline: true);
    } on InspectGone {
      await _wipe();
    } on InspectSignedOut {
      await _vault.dropTokens();
      state = state.copyWith(phase: InspectPhase.signedOut);
    } on InspectError catch (e) {
      state = state.copyWith(error: () => e.code);
    }
    return null;
  }

  Future<void> _wipe() async {
    await _box.wipe();
    await _vault.wipe();
    state = const InspectState(phase: InspectPhase.signedOut, wiped: true);
  }

  /// The missions from the server, then the reports that wait for the network.
  Future<void> refresh() async {
    final missions = await _guard(_api.missions);
    if (missions != null) {
      await _box.saveMissions(missions);
      state = state.copyWith(missions: missions);
    }
    if (state.phase == InspectPhase.active) await flush();
  }

  Future<bool> register({
    required String kind,
    required String matricule,
    required String name,
    String? organisation,
    String? phone,
    String? email,
    required String via,
  }) async {
    state = state.copyWith(busy: true, error: () => null);
    final dest = await _guard(
      () => _api.register(
        kind: kind,
        matricule: matricule,
        name: name,
        organisation: organisation,
        phone: phone,
        email: email,
        via: via,
      ),
    );
    if (dest != null) await _vault.saveMatricule(matricule);
    state = state.copyWith(
      busy: false,
      destination: dest == null ? null : () => dest,
      matricule: dest == null ? null : () => matricule.trim(),
    );
    return dest != null;
  }

  Future<bool> activate(String matricule, String code) async {
    state = state.copyWith(busy: true, error: () => null);
    final t = await _guard(
      () => _api.activate(
        matricule: matricule,
        code: code,
        platform: ref.read(staffPlatformProvider),
      ),
    );
    if (t == null) {
      state = state.copyWith(busy: false);
      return false;
    }
    await _vault.saveMatricule(matricule);
    state = state.copyWith(
      busy: false,
      phase: InspectPhase.active,
      name: () => t.name,
      kind: () => t.kind,
      expiresOn: () => t.expiresOn,
      wiped: false,
    );
    await refresh();
    return true;
  }

  /// Opens the report of a place on the phone, from the order and the model downloaded with the
  /// missions: no network needed (Yamen 2026-11-12). The server records it, with the arrival time
  /// taken here, as soon as the phone reaches it.
  Future<InspectDraft?> open(InspectMission mission, InspectSite site) async {
    final kept = state.draftOfSite(site.id);
    if (kept != null) return kept;
    final now = _now();
    if (mission.onDate.isAfter(DateTime(now.year, now.month, now.day))) {
      state = state.copyWith(error: () => 'mission_not_today');
      return null;
    }
    state = state.copyWith(busy: true, error: () => null);
    double? lat;
    double? lon;
    try {
      final here = await ref.read(locationServiceProvider).lastKnown();
      lat = here?.lat;
      lon = here?.lon;
    } on Object {
      // The place's position is optional.
    }
    final profile = mission.profile;
    if (profile != null && site.inspectionStatus == null) {
      final d = InspectDraft(
        inspectionId: const Uuid().v4(),
        siteId: site.id,
        missionRef: mission.ref,
        siteName: site.name,
        profile: profile,
        clientId: const Uuid().v4(),
        startedAt: _now().toUtc(),
        lat: lat,
        lon: lon,
      );
      await _save(d);
      state = state.copyWith(busy: false);
      unawaited(_reach(d.inspectionId));
      return d;
    }
    // A report already opened on the server (another phone, a reinstall), or no model yet.
    final j = await _guard(
      () => _api.start(site.id, lat: lat, lon: lon, at: _now()),
    );
    state = state.copyWith(busy: false);
    if (j == null) return null;
    final submitted = j['status'] == 'submitted';
    final d = InspectDraft(
      inspectionId: j['id'] as String,
      serverId: j['id'] as String,
      siteId: site.id,
      missionRef: mission.ref,
      siteName: site.name,
      profile: InspectProfile.fromJson(j['profile'] as Map<String, dynamic>),
      clientId: const Uuid().v4(),
      answers: _answersOf(j),
      present: (j['present'] as num?)?.toInt(),
      expected: (j['expected'] as num?)?.toInt(),
      exitSeconds: (j['exit_seconds'] as num?)?.toInt(),
      state: submitted ? DraftState.sent : DraftState.editing,
      receipt: j['receipt'] as String?,
      score: (j['score'] as num?)?.toInt(),
      verdict: j['verdict'] as String?,
    );
    await _save(d);
    return d;
  }

  static Map<String, String> _answersOf(Map<String, dynamic> j) => {
    for (final e in (j['answers'] as Map? ?? const {}).entries)
      '${e.key}': '${e.value}',
  };

  /// Gives a report opened on the phone to the server (once), with the arrival time and place
  /// recorded on the phone; the server's model version wins, the answers given here stay.
  Future<InspectDraft> _reached(InspectDraft d) async {
    if (d.serverId != null) return d;
    final j = await _api.start(
      d.siteId,
      lat: d.lat,
      lon: d.lon,
      at: d.startedAt,
    );
    final current = state.drafts[d.inspectionId] ?? d;
    final serverProfile = InspectProfile.fromJson(
      j['profile'] as Map<String, dynamic>,
    );
    final known = {for (final i in serverProfile.items) i.key};
    final merged = current.copyWith(
      serverId: j['id'] as String,
      profile: serverProfile,
      answers: {
        ..._answersOf(j),
        for (final e in current.answers.entries)
          if (known.contains(e.key)) e.key: e.value,
      },
    );
    await _save(merged);
    return merged;
  }

  /// Quiet: the phone tries again with the next answers or the signed report.
  Future<void> _reach(String id) async {
    final d = state.drafts[id];
    if (d == null) return;
    try {
      await _reached(d);
      state = state.copyWith(offline: false);
    } on InspectOffline {
      state = state.copyWith(offline: true);
    } on InspectGone {
      await _wipe();
    } on Object {
      // Shown when the report is sent.
    }
  }

  Future<void> _save(InspectDraft d) async {
    await _box.saveDraft(d);
    state = state.copyWith(drafts: {...state.drafts, d.inspectionId: d});
  }

  /// Changes a report being filled; its answers are sent when the network is there.
  Future<void> edit(
    String id,
    InspectDraft Function(InspectDraft) change,
  ) async {
    final d = state.drafts[id];
    if (d == null || d.state != DraftState.editing) return;
    await _save(change(d));
  }

  /// Sends the answers so far ("in progress" for the central room). Quiet without network.
  Future<void> sync(String id) async {
    final d = state.drafts[id];
    if (d == null || d.state != DraftState.editing) return;
    try {
      await _api.progress(await _reached(d));
      state = state.copyWith(offline: false);
    } on InspectOffline {
      state = state.copyWith(offline: true);
    } on InspectGone {
      await _wipe();
    } on Object {
      // Sent again with the report.
    }
  }

  /// Signs the report: it is sealed on the phone and sent now, or as soon as the network is back.
  Future<void> sign(String id) async {
    final d = state.drafts[id];
    if (d == null || d.state != DraftState.editing || !d.signable) return;
    await _save(
      d.copyWith(state: DraftState.queued, signedAt: () => _now().toUtc()),
    );
    await _send(id);
  }

  Future<void> _send(String id) async {
    final d = state.drafts[id];
    if (d == null || d.state != DraftState.queued) return;
    state = state.copyWith(busy: true);
    try {
      final reached = await _reached(d);
      final r = await _api.submit(reached);
      await _save(
        reached.copyWith(
          state: DraftState.sent,
          receipt: r['receipt'] as String?,
          score: (r['score'] as num?)?.toInt(),
          verdict: r['verdict'] as String?,
        ),
      );
      state = state.copyWith(offline: false, error: () => null);
    } on InspectOffline {
      state = state.copyWith(offline: true);
    } on InspectGone {
      await _wipe();
    } on InspectSignedOut {
      await _vault.dropTokens();
      state = state.copyWith(phase: InspectPhase.signedOut);
    } on InspectError catch (e) {
      // Refused (not a network matter): back to the form, with the reason.
      final now = state.drafts[id] ?? d;
      await _save(now.copyWith(state: DraftState.editing));
      state = state.copyWith(error: () => e.code);
    } finally {
      state = state.copyWith(busy: false);
    }
  }

  /// Sends every signed report that waits.
  Future<void> flush() async {
    for (final d in [...state.drafts.values]) {
      if (d.state == DraftState.queued) await _send(d.inspectionId);
      if (state.offline || state.phase != InspectPhase.active) return;
    }
  }

  /// Forgets a report already received by the server.
  Future<void> forget(String id) async {
    final d = state.drafts[id];
    if (d == null || d.state != DraftState.sent) return;
    await _box.removeDraft(id);
    state = state.copyWith(drafts: {...state.drafts}..remove(id));
  }

  void clearError() => state = state.copyWith(error: () => null);

  /// Leaves the inspector's space on this phone: tokens and sealed copies are erased.
  Future<void> signOut() => _wipe();
}

final inspectControllerProvider =
    NotifierProvider<InspectController, InspectState>(InspectController.new);
