import '../../features/alerts/alert_labels.dart';
import '../../features/report/category_labels.dart';
import '../../features/reports/status_chip.dart';
import '../../l10n/app_localizations.dart';
import '../http/api_error.dart';
import '../http/ehimaya_api.dart';
import '../http/models.dart';
import '../logging/log.dart';
import 'push_payload.dart';

final _log = logger('push');

/// A8: personal pushes reach Google/Apple without any personal text (`redacted: "1"`). The
/// phone fetches the content with the user's own identity from the existing authenticated
/// endpoints and shows it locally; the text never transits the push services.
class RedactedPushResolver {
  RedactedPushResolver(this._api, this._l10n);

  final EHimayaApi _api;
  final AppLocalizations _l10n;

  /// The push with its real title and body, or null when the content cannot be fetched (offline,
  /// signed out, item gone): the generic text then stays.
  Future<PushPayload?> resolve(PushPayload p) async {
    if (!p.redacted) return null;
    try {
      return switch (p.kind) {
        PushKind.callout => await _callout(p),
        PushKind.reportStatus => await _report(p),
        PushKind.info => await _info(p),
        PushKind.safetyAlert => await _safetyAlert(p),
        PushKind.safetyLink => await _safetyLink(p),
        PushKind.safetyCheckFired => p.withText(
          title: _l10n.safetyCheckFired,
          body: _l10n.safetyCheckFiredHint,
        ),
        PushKind.safetyHistoryViewed => p.withText(
          title: _l10n.safetyHistoryViewedTitle,
          body: _l10n.safetyHistoryViewedBody,
        ),
        PushKind.medicalReferral => p.withText(
          title: _l10n.pushMedicalReferralTitle,
          body: _l10n.pushMedicalReferralBody,
        ),
        PushKind.teamStatus => _team(p),
        PushKind.medicalOpinion => p.withText(
          title: _l10n.pushMedicalOpinionTitle,
          body: _l10n.pushMedicalOpinionBody,
        ),
        PushKind.alert ||
        PushKind.alertCancelled ||
        PushKind.safetyCheckReminder => null,
      };
    } on ApiException catch (e) {
      _log.info('redacted push not resolved: ${e.code.wire}');
      return null;
    }
  }

  Future<PushPayload?> _callout(PushPayload p) async {
    final id = p.data['callout_id'] ?? p.data['id'];
    final callouts = await _api.myCallouts();
    final c =
        callouts.where((c) => c.id == id).firstOrNull ??
        (id == null ? callouts.firstOrNull : null);
    if (c == null) return null;
    final category = ReportCategory.fromWire(c.incidentCategory);
    final distance = c.distanceM;
    final parts = [
      if (c.message != null && c.message!.trim().isNotEmpty) c.message!.trim(),
      if (distance != null) distanceLabel(_l10n, distance),
    ];
    return p.withText(
      title: category == null
          ? _l10n.pushCalloutTitle
          : '${_l10n.pushCalloutTitle} · ${categoryLabel(_l10n, category)}',
      body: parts.isEmpty ? _l10n.pushOpenToSee : parts.join(' · '),
    );
  }

  Future<PushPayload?> _report(PushPayload p) async {
    final code = p.data['tracking_code'] ?? p.data['code'];
    String? status;
    String trackingCode;
    if (code != null && code.isNotEmpty) {
      final result = await _api.track(code);
      status = result.status;
      trackingCode = result.trackingCode;
    } else {
      final reportId = p.data['report_id'] ?? p.data['id'];
      if (reportId == null) return null;
      final mine = await _api.myReports(limit: 20);
      final r = mine.items.where((r) => r.id == reportId).firstOrNull;
      if (r == null) return null;
      status = r.status;
      trackingCode = r.trackingCode;
    }
    final parsed = ReportStatus.fromWire(status);
    return p.withText(
      title: _l10n.pushReportTitle(trackingCode),
      body: parsed == null
          ? _l10n.pushOpenToSee
          : reportStatusLabel(_l10n, parsed),
    );
  }

  /// Phase P4d (F-APP-38): fixed words, in the phone's language; the code names the report.
  PushPayload? _team(PushPayload p) {
    final code = p.data['tracking_code'];
    final body = switch (p.data['team']) {
      'en_route' => _l10n.teamEnRoute,
      'on_scene' => _l10n.teamOnScene,
      _ => null,
    };
    if (body == null) return null;
    return p.withText(
      title: code == null ? null : _l10n.pushReportTitle(code),
      body: body,
    );
  }

  /// Phase B2: who is in distress and their message (shown on the phone only, never on a locked
  /// screen: personal pushes are private).
  Future<PushPayload?> _safetyAlert(PushPayload p) async {
    final id = p.id;
    if (id == null) return null;
    final a = await _api.safetyAlert(id);
    final who = a.senderFirstName ?? _l10n.safetySomeone;
    return p.withText(
      title: a.isCheck
          ? _l10n.safetyAlertCheckFrom(who)
          : _l10n.safetyAlertFrom(who),
      body: a.message,
    );
  }

  Future<PushPayload?> _safetyLink(PushPayload p) async {
    final id = p.id;
    final links = await _api.safetyLinks();
    final link = links.where((l) => l.id == id).firstOrNull;
    if (link == null) return null;
    return p.withText(
      title: _l10n.safetyLinkedTitle,
      body: _l10n.safetyLinkedPush(link.firstName ?? _l10n.safetySomeone),
    );
  }

  Future<PushPayload?> _info(PushPayload p) async {
    final id = p.data['id'];
    if (id == null) return null;
    final page = await _api.inbox(limit: 30);
    final item = page.items.where((i) => i.id == id).firstOrNull;
    if (item == null) return null;
    final lang = _l10n.localeName;
    return p.withText(title: item.title.of(lang), body: item.body.of(lang));
  }
}
