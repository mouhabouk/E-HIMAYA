import 'package:dio/dio.dart';

/// Anonymous report quota of this installation (phase 9 §3).
///
/// The server is the only authority: it counts the accepted non-SOS reports of the device's
/// pseudonymous account and announces the result in `X-Anon-Quota-Limit` /
/// `X-Anon-Quota-Remaining` on every answer to an anonymous caller, and in
/// `GET /api/v1/reports/quota`. The app only keeps the last value it was told, to warn before
/// a report is queued; an SOS is never gated by it.
class AnonQuota {
  const AnonQuota({required this.limit, required this.remaining, this.used});

  /// Accepted reports allowed per installation; null when the server did not say.
  final int? limit;

  /// Reports this installation may still send without an account (0: exhausted).
  final int remaining;

  /// Reports already counted, when the server said.
  final int? used;

  bool get exhausted => remaining <= 0;

  /// Parsed from the `X-Anon-Quota-*` headers; null when absent (registered callers, older
  /// servers) or malformed.
  static AnonQuota? fromHeaders(Headers headers) {
    final remaining = _nonNegative(headers.value('x-anon-quota-remaining'));
    if (remaining == null) return null;
    return AnonQuota(
      limit: _nonNegative(headers.value('x-anon-quota-limit')),
      remaining: remaining,
    );
  }

  /// `GET /api/v1/reports/quota`: null for registered accounts (`{"limit": null, ...}`).
  static AnonQuota? fromJson(Map<String, Object?> json) {
    final remaining = json['remaining'];
    if (remaining is! int) return null;
    final limit = json['limit'];
    final used = json['used'];
    return AnonQuota(
      limit: limit is int ? limit : null,
      remaining: remaining < 0 ? 0 : remaining,
      used: used is int ? used : null,
    );
  }

  /// Keeps the known limit when a later answer did not repeat it.
  AnonQuota mergedWith(AnonQuota? previous) => limit != null
      ? this
      : AnonQuota(limit: previous?.limit, remaining: remaining, used: used);

  static int? _nonNegative(String? raw) {
    if (raw == null) return null;
    final value = int.tryParse(raw.trim());
    if (value == null) return null;
    return value < 0 ? 0 : value;
  }

  @override
  bool operator ==(Object other) =>
      other is AnonQuota &&
      other.limit == limit &&
      other.remaining == remaining &&
      other.used == used;

  @override
  int get hashCode => Object.hash(limit, remaining, used);

  @override
  String toString() => 'AnonQuota($remaining of $limit)';
}
