import 'dart:async';
import 'dart:convert';

import 'package:drift/drift.dart' show Value;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';
import '../../core/platform/device_services.dart';
import '../../core/storage/app_prefs.dart';
import '../institution/institution_providers.dart';
import 'safety_models.dart';
import 'safety_reminders.dart';

final _log = logger('safety');

// ---------------------------------------------------------------- phone-only data

/// The emergency contacts, kept in the phone's encrypted database only.
final emergencyContactsProvider = StreamProvider<List<EmergencyContact>>(
  (ref) => ref.watch(databaseProvider).watchContacts(),
);

final contactGroupsProvider = StreamProvider<List<ContactGroup>>(
  (ref) => ref.watch(databaseProvider).watchGroups(),
);

/// What this phone sent (SOS messages, safety checks, live shares, self-tests).
final safetyRecentProvider = StreamProvider<List<SafetyAlertEntry>>(
  (ref) => ref.watch(databaseProvider).watchAlertHistory(),
);

/// The medical file row (null: no file, or consent not given yet).
final medicalRowProvider = StreamProvider<MedicalProfileRow?>(
  (ref) => ref.watch(databaseProvider).watchMedical(),
);

/// The medical file's fields (null when there is none).
MedicalFile? medicalOf(MedicalProfileRow? row) {
  if (row == null) return null;
  try {
    final json = jsonDecode(row.data);
    return json is Map<String, Object?> ? MedicalFile.fromJson(json) : null;
  } on FormatException {
    return null;
  }
}

// ---------------------------------------------------------------- server data

/// Linked e-Himaya users (empty for a guest: links need an account).
final safetyLinksProvider = FutureProvider.autoDispose<List<SafetyLink>>((
  ref,
) async {
  if (!ref.watch(identityProvider).isRegistered) return const [];
  return ref.watch(apiProvider).safetyLinks();
}, retry: (_, _) => null);

/// Alerts of the last 24 hours, received and sent.
final safetyAlertsProvider = FutureProvider.autoDispose<List<SafetyAlertView>>((
  ref,
) async {
  if (!ref.watch(identityProvider).isRegistered) return const [];
  return ref.watch(apiProvider).safetyAlerts();
}, retry: (_, _) => null);

final safetyAlertProvider = FutureProvider.autoDispose
    .family<SafetyAlertView, String>(
      (ref, id) => ref.watch(apiProvider).safetyAlert(id),
      retry: (_, _) => null,
    );

/// The safety check in progress (null: none, or a guest).
final safetyCheckProvider = FutureProvider.autoDispose<SafetyCheckState?>((
  ref,
) async {
  if (!ref.watch(identityProvider).isRegistered) return null;
  return ref.watch(apiProvider).currentSafetyCheck();
}, retry: (_, _) => null);

/// The 72-hour location history; [HistoryState.off] for a guest, offline, or while the platform
/// keeps the feature off (the hub then hides it).
final locationHistoryProvider = FutureProvider.autoDispose<HistoryState>((
  ref,
) async {
  if (!ref.watch(identityProvider).isRegistered) return HistoryState.off;
  try {
    return await ref.watch(apiProvider).locationHistory();
  } on ApiException {
    return HistoryState.off;
  }
}, retry: (_, _) => null);

/// Contact id → link id, for the contacts who also use e-Himaya and are linked (same number).
Map<int, String> linkedContacts(
  List<EmergencyContact> contacts,
  List<SafetyLink> links,
) {
  final byPhone = <String, String>{
    for (final l in links) ?normalizeContactPhone(l.phone ?? ''): l.id,
  };
  return {
    for (final c in contacts) c.id: ?byPhone[normalizeContactPhone(c.phone)],
  };
}

// ---------------------------------------------------------------- SOS message

/// What [SosMessageSender.send] did.
class SosSendResult {
  const SosSendResult({
    required this.text,
    required this.phones,
    required this.appRecipients,
    required this.appFailed,
    required this.smsOpened,
    this.emails = const [],
    this.channels = sosChannelDefaults,
    this.opened,
  });

  /// The message with the position link, accuracy, time and battery.
  final String text;

  /// The numbers the SMS app was opened with (the user presses Send there).
  final List<String> phones;

  /// Linked contacts the in-app alert reached (0 when none, or a guest).
  final int appRecipients;

  /// The in-app alert could not be sent (offline, limit): the SMS still opened.
  final bool appFailed;
  final bool smsOpened;

  /// The contacts' e-mail addresses (review point 6).
  final List<String> emails;

  /// The external channels the user keeps on, in their order.
  final List<String> channels;

  /// The channel opened by itself (the first of [channels] with recipients), null when none.
  final String? opened;
}

/// Addition 5: the SOS message to the user's own contacts, in order: the in-app alert to linked
/// contacts (rings through silent mode), then the SMS app with every number and the text ready.
/// WhatsApp is offered afterwards, one contact or group at a time (it never sends on its own).
class SosMessageSender {
  SosMessageSender(this._ref);

  final Ref _ref;

  Future<SosSendResult> send({
    required String template,
    required SosLabels labels,
    int? groupId,
  }) async {
    final db = _ref.read(databaseProvider);
    final all = await db.allContacts();
    final chosen = groupId == null
        ? all
        : all.where((c) => inGroup(c.groups, groupId)).toList();
    final position = await _ref
        .read(locationServiceProvider)
        .bestEffort(timeout: const Duration(seconds: 5));
    final battery = (await _ref.read(deviceServicesProvider).battery())?.level;
    final live = _ref.read(liveShareProvider);
    final portal = _ref.read(appConfigProvider).portalUrl;
    final at = _ref.read(clockProvider)();
    final text = sosMessageText(
      template: template,
      labels: labels,
      at: at,
      position: position,
      battery: battery,
      liveLink: live == null ? null : liveLink(portal, live.token),
    );

    var appRecipients = 0;
    var appFailed = false;
    String? serverId;
    if (_ref.read(identityProvider).isRegistered) {
      try {
        final api = _ref.read(apiProvider);
        final links = await api.safetyLinks();
        // Everyone: every link (also those not in the phone's list). A group: its linked members.
        final linkIds = groupId == null
            ? null
            : linkedContacts(chosen, links).values.toSet().toList();
        if (links.isNotEmpty && (linkIds == null || linkIds.isNotEmpty)) {
          final sent = await api.sendSafetyAlert(
            clientUuid: const Uuid().v4(),
            message: _serverMessage(template),
            location: position,
            battery: battery,
            linkIds: linkIds,
            liveShareId: live?.id,
          );
          appRecipients = sent.recipients;
          serverId = sent.id;
        }
      } on ApiException catch (e) {
        _log.info('in-app SOS not sent: ${e.code.wire}');
        appFailed = true;
      }
    }

    final phones = {for (final c in chosen) ?normalizeContactPhone(c.phone)}
        .toList();
    final emails = {for (final c in chosen) ?normalizeContactEmail(c.email)}
        .toList();
    // Review point 6: the user's order; the first channel that has recipients opens by itself,
    // the others are offered as buttons on the result screen in the same order.
    final prefs = _ref.read(appPrefsProvider);
    final off = prefs.sosChannelsOff;
    final channels = [
      for (final c in prefs.sosChannels)
        if (!off.contains(c)) c,
    ];
    String? opened;
    final open = _ref.read(urlOpenerProvider);
    for (final c in channels) {
      final uri = switch (c) {
        'sms' when phones.isNotEmpty => smsGroupUri(phones, text),
        'email' when emails.isNotEmpty => emailGroupUri(
          emails,
          labels.subject,
          text,
        ),
        'whatsapp' when phones.isNotEmpty => whatsAppShareUri(text),
        _ => null,
      };
      if (uri == null) continue;
      if (await open(uri)) opened = c;
      break;
    }
    final smsOpened = opened == 'sms';
    await db.addAlertHistory(
      SafetyAlertHistoryCompanion.insert(
        kind: 'sos_message',
        at: at,
        status: opened != null || appRecipients > 0 ? 'sent' : 'failed',
        channels: Value([if (appRecipients > 0) 'app', ?opened].join(',')),
        recipients: Value(
          phones.length > appRecipients ? phones.length : appRecipients,
        ),
        serverId: Value(serverId),
      ),
    );
    return SosSendResult(
      text: text,
      phones: phones,
      appRecipients: appRecipients,
      appFailed: appFailed,
      smsOpened: smsOpened,
      emails: emails,
      channels: channels,
      opened: opened,
    );
  }

  /// A cancelled message (inside the 5-second window) stays in the recent list.
  Future<void> recordCancelled() => _ref
      .read(databaseProvider)
      .addAlertHistory(
        SafetyAlertHistoryCompanion.insert(
          kind: 'sos_message',
          at: _ref.read(clockProvider)(),
          status: 'cancelled',
        ),
      );

  static String _serverMessage(String template) {
    final t = template.trim();
    return t.length <= SafetyRules.messageMax
        ? t
        : t.substring(0, SafetyRules.messageMax);
  }
}

final sosMessageSenderProvider = Provider<SosMessageSender>(
  SosMessageSender.new,
);

// ---------------------------------------------------------------- live location share

/// A live location share in progress (kept in the preferences so a restart resumes it).
class LiveShareSession {
  const LiveShareSession({
    required this.id,
    required this.token,
    required this.expiresAt,
    this.lastSentAt,
  });

  final String id;
  final String token;
  final DateTime expiresAt;
  final DateTime? lastSentAt;

  LiveShareSession sentAt(DateTime at) => LiveShareSession(
    id: id,
    token: token,
    expiresAt: expiresAt,
    lastSentAt: at,
  );

  String toJson() => jsonEncode({
    'id': id,
    'token': token,
    'expires_at': expiresAt.toUtc().toIso8601String(),
  });

  static LiveShareSession? fromJson(String? raw) {
    if (raw == null) return null;
    try {
      final m = jsonDecode(raw) as Map<String, Object?>;
      return LiveShareSession(
        id: m['id']! as String,
        token: m['token']! as String,
        expiresAt: DateTime.parse(m['expires_at']! as String),
      );
    } on Object {
      return null;
    }
  }
}

/// Texts of the foreground-service notification shown while the position is shared.
typedef FollowNotice = ({String title, String text});

/// Addition 8.4: a random link that ends by itself and can be stopped at any time. While it
/// runs the phone sends its position at most every 20 seconds.
class LiveShareController extends Notifier<LiveShareSession?> {
  static const minInterval = Duration(seconds: 20);

  StreamSubscription<GeoPoint>? _follow;
  Timer? _end;
  FollowNotice _notice = (title: 'e-Himaya', text: '');

  @override
  LiveShareSession? build() {
    ref.onDispose(_stopFollowing);
    final saved = LiveShareSession.fromJson(
      ref.read(appPrefsProvider).liveShareJson,
    );
    if (saved == null) return null;
    if (!saved.expiresAt.isAfter(ref.read(clockProvider)())) {
      unawaited(ref.read(appPrefsProvider).setLiveShareJson(null));
      return null;
    }
    // Resumed after a restart: positions follow again once the app shows the notice texts.
    _scheduleEnd(saved);
    return saved;
  }

  /// Starts following with the notification texts of the current language (called by the
  /// screens and the shell, which know the language).
  void resume(FollowNotice notice) {
    _notice = notice;
    final s = state;
    if (s != null && _follow == null) _startFollowing(s);
  }

  Future<LiveShareSession> start(int minutes, FollowNotice notice) async {
    _notice = notice;
    final started = await ref.read(apiProvider).startLiveShare(minutes);
    final session = LiveShareSession(
      id: started.id,
      token: started.token,
      expiresAt: started.expiresAt,
    );
    await ref.read(appPrefsProvider).setLiveShareJson(session.toJson());
    state = session;
    _scheduleEnd(session);
    await ref
        .read(databaseProvider)
        .addAlertHistory(
          SafetyAlertHistoryCompanion.insert(
            kind: 'live_share',
            at: ref.read(clockProvider)(),
            status: 'sent',
            serverId: Value(session.id),
          ),
        );
    final first = await ref
        .read(locationServiceProvider)
        .bestEffort(timeout: const Duration(seconds: 5));
    if (first != null) await _send(first);
    _startFollowing(session);
    return session;
  }

  Future<void> stop() async {
    final s = state;
    _stopFollowing();
    state = null;
    await ref.read(appPrefsProvider).setLiveShareJson(null);
    if (s == null) return;
    try {
      await ref.read(apiProvider).stopLiveShare(s.id);
    } on ApiException catch (e) {
      // It ends by itself at its time anyway.
      _log.info('live share not stopped on the server: ${e.code.wire}');
    }
  }

  void _scheduleEnd(LiveShareSession s) {
    _end?.cancel();
    final left = s.expiresAt.difference(ref.read(clockProvider)());
    _end = Timer(
      left.isNegative ? Duration.zero : left,
      () => unawaited(stop()),
    );
  }

  void _startFollowing(LiveShareSession s) {
    _follow?.cancel();
    _follow = ref
        .read(locationServiceProvider)
        .follow(title: _notice.title, text: _notice.text)
        .listen((p) => unawaited(_send(p)));
  }

  void _stopFollowing() {
    _follow?.cancel();
    _follow = null;
    _end?.cancel();
    _end = null;
  }

  Future<void> _send(GeoPoint p) async {
    final s = state;
    if (s == null) return;
    final now = ref.read(clockProvider)();
    final last = s.lastSentAt;
    if (last != null && now.difference(last) < minInterval) return;
    state = s.sentAt(now);
    try {
      final battery = (await ref.read(deviceServicesProvider).battery())?.level;
      final live = await ref
          .read(apiProvider)
          .putLivePosition(s.id, p, battery: battery);
      if (!live.active) {
        _stopFollowing();
        state = null;
        await ref.read(appPrefsProvider).setLiveShareJson(null);
      }
    } on ApiException catch (e) {
      _log.info('live position not sent: ${e.code.wire}');
    }
  }
}

final liveShareProvider =
    NotifierProvider<LiveShareController, LiveShareSession?>(
      LiveShareController.new,
    );

// ---------------------------------------------------------------- safety check

/// Addition 8.1: the server keeps the timer, so the alert goes even when the phone is off; the
/// phone reminds the user 10 minutes and 1 minute before.
class SafetyCheckActions {
  SafetyCheckActions(this._ref);

  final Ref _ref;

  Future<SafetyCheckState> start({
    required int minutes,
    required String message,
    required ReminderTexts texts,
  }) async {
    final position = await _ref
        .read(locationServiceProvider)
        .bestEffort(timeout: const Duration(seconds: 5));
    final battery = (await _ref.read(deviceServicesProvider).battery())?.level;
    final check = await _ref
        .read(apiProvider)
        .startSafetyCheck(
          minutes: minutes,
          message: message,
          location: position,
          battery: battery,
        );
    await _ref.read(safetyRemindersProvider).schedule(check.dueAt, texts);
    await _ref
        .read(databaseProvider)
        .addAlertHistory(
          SafetyAlertHistoryCompanion.insert(
            kind: 'safety_check',
            at: _ref.read(clockProvider)(),
            status: 'sent',
            serverId: Value(check.id),
          ),
        );
    _ref.invalidate(safetyCheckProvider);
    return check;
  }

  Future<void> ok(SafetyCheckState check) async {
    await _ref.read(apiProvider).safetyCheckOk(check.id);
    await _ref.read(safetyRemindersProvider).cancel();
    await _ref
        .read(databaseProvider)
        .addAlertHistory(
          SafetyAlertHistoryCompanion.insert(
            kind: 'safety_check',
            at: _ref.read(clockProvider)(),
            status: 'ok',
            serverId: Value(check.id),
          ),
        );
    _ref.invalidate(safetyCheckProvider);
  }

  Future<void> extend(
    SafetyCheckState check,
    int minutes,
    ReminderTexts texts,
  ) async {
    final updated = await _ref
        .read(apiProvider)
        .extendSafetyCheck(check.id, minutes);
    await _ref.read(safetyRemindersProvider).schedule(updated.dueAt, texts);
    await updatePosition(updated);
    _ref.invalidate(safetyCheckProvider);
  }

  /// The newest position for the server's alert (sent when the screen opens and on extend).
  Future<void> updatePosition(SafetyCheckState check) async {
    final p = await _ref.read(locationServiceProvider).withoutPrompt();
    if (p == null || !p.isInTunisiaBox) return;
    try {
      final battery =
          (await _ref.read(deviceServicesProvider).battery())?.level;
      await _ref
          .read(apiProvider)
          .putSafetyCheckPosition(check.id, p, battery: battery);
    } on ApiException catch (e) {
      _log.info('check position not sent: ${e.code.wire}');
    }
  }
}

final safetyCheckActionsProvider = Provider<SafetyCheckActions>(
  SafetyCheckActions.new,
);

// ---------------------------------------------------------------- location history

/// Addition 7b §2, only while the platform and the user turned it on: positions are collected
/// while the app runs (low power, 250 m) and sent in batches every 15 minutes.
class LocationHistoryRecorder {
  LocationHistoryRecorder(this._ref);

  static const flushEvery = Duration(minutes: 15);

  final Ref _ref;
  final _buffer = <SafetyPoint>[];
  StreamSubscription<GeoPoint>? _sub;
  Timer? _flush;

  bool get running => _sub != null;

  void start() {
    if (_sub != null) return;
    _sub = _ref
        .read(locationServiceProvider)
        .watch(lowPower: true)
        .listen(
          (p) => _buffer.add(
            SafetyPoint(point: p, at: _ref.read(clockProvider)()),
          ),
        );
    _flush = Timer.periodic(flushEvery, (_) => unawaited(flush()));
  }

  Future<void> stop() async {
    await _sub?.cancel();
    _sub = null;
    _flush?.cancel();
    _flush = null;
    _buffer.clear();
  }

  Future<void> flush() async {
    if (_buffer.isEmpty) return;
    final batch = _buffer.take(100).toList();
    try {
      await _ref.read(apiProvider).postHistoryPoints(batch);
      _buffer.removeRange(0, batch.length);
    } on ApiException catch (e) {
      _log.info('history points not sent: ${e.code.wire}');
      if (e.code == ApiErrorCode.historyOff ||
          e.code == ApiErrorCode.featureOff) {
        await stop();
      }
    }
  }
}

final locationHistoryRecorderProvider = Provider<LocationHistoryRecorder>((
  ref,
) {
  final recorder = LocationHistoryRecorder(ref);
  ref.onDispose(() => unawaited(recorder.stop()));
  return recorder;
});
