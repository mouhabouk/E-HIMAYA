import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../http/api_client.dart';
import '../logging/log.dart';

final _log = logger('whip');

/// Why a WHIP exchange failed.
enum WhipFailure {
  /// No HTTP answer (timeout, connection refused, no network).
  network,

  /// `401`/`403`: the publish token was refused (expired, already used, wrong path).
  unauthorized,

  /// Another `4xx` (bad offer, path busy, unknown path): retrying the same request will not help.
  rejected,

  /// `5xx`, or a `2xx` that is not a valid WHIP answer.
  server,
}

class WhipException implements Exception {
  const WhipException(this.failure, [this.statusCode]);

  final WhipFailure failure;
  final int? statusCode;

  bool get isTransient =>
      failure == WhipFailure.network || failure == WhipFailure.server;

  @override
  String toString() => 'WhipException(${failure.name}, $statusCode)';
}

/// The publishing session created by the WHIP endpoint: its resource URL (used to send late ICE
/// candidates and to end the session) and the SDP answer.
class WhipSession {
  const WhipSession({
    required this.resourceUrl,
    required this.answerSdp,
    this.etag,
  });

  final Uri resourceUrl;
  final String answerSdp;

  /// ETag of the ICE session (RFC 9725 §4.3.1), sent back in `If-Match` on PATCH.
  final String? etag;
}

/// Minimal WHIP client (RFC 9725) on top of Dio, for MediaMTX:
///
/// * `POST <whip_url>` with the SDP offer (`application/sdp`) and
///   `Authorization: Bearer <publish_token>` → `201 Created`, the SDP answer in the body and the
///   session resource in `Location` (often relative, resolved against the WHIP URL);
/// * `PATCH <resource>` with `application/trickle-ice-sdpfrag` for candidates gathered after the
///   offer was sent (best effort: a server without trickle answers 405/501, ignored);
/// * `DELETE <resource>` to end the session.
///
/// The Dio instance has **no** identity interceptor: the platform's bearer token or device key
/// must never be sent to the media server, only the single-use publish token.
class WhipClient {
  WhipClient(this._dio);

  final Dio _dio;

  static const sdpType = 'application/sdp';
  static const trickleType = 'application/trickle-ice-sdpfrag';

  Options _options(String token, {Map<String, String> headers = const {}}) =>
      Options(
        headers: {'Authorization': 'Bearer $token', ...headers},
        responseType: ResponseType.plain,
        // Every status is inspected here rather than thrown by Dio.
        validateStatus: (_) => true,
        followRedirects: false,
      );

  Future<Response<String>> _send(
    Future<Response<String>> Function() call,
  ) async {
    try {
      return await call();
    } on DioException catch (e) {
      _log.info('whip transport error: ${e.type.name}');
      throw const WhipException(WhipFailure.network);
    }
  }

  static WhipException _failure(int status) => switch (status) {
    401 || 403 => WhipException(WhipFailure.unauthorized, status),
    >= 400 && < 500 => WhipException(WhipFailure.rejected, status),
    _ => WhipException(WhipFailure.server, status),
  };

  /// Sends the offer and returns the session. Throws [WhipException].
  Future<WhipSession> publish({
    required Uri whipUrl,
    required String token,
    required String offerSdp,
  }) async {
    final response = await _send(
      () => _dio.postUri<String>(
        whipUrl,
        data: offerSdp,
        options: _options(
          token,
          headers: {'Content-Type': sdpType, 'Accept': sdpType},
        ),
      ),
    );
    final status = response.statusCode ?? 0;
    if (status != 201) {
      _log.info('whip offer refused: $status');
      throw _failure(status == 200 ? 500 : status);
    }
    final location = response.headers.value('location');
    final answer = response.data ?? '';
    if (location == null || location.isEmpty || !answer.contains('v=0')) {
      throw const WhipException(WhipFailure.server, 201);
    }
    return WhipSession(
      resourceUrl: whipUrl.resolve(location),
      answerSdp: answer,
      etag: response.headers.value('etag'),
    );
  }

  /// Trickles late candidates. Returns false when the server does not support it (not an error:
  /// the candidates in the offer are enough for MediaMTX).
  Future<bool> patchCandidates({
    required WhipSession session,
    required String token,
    required String sdpFragment,
  }) async {
    final response = await _send(
      () => _dio.patchUri<String>(
        session.resourceUrl,
        data: sdpFragment,
        options: _options(
          token,
          headers: {
            'Content-Type': trickleType,
            'If-Match': session.etag ?? '*',
          },
        ),
      ),
    );
    final status = response.statusCode ?? 0;
    if (status == 204 || status == 200) return true;
    if (status == 405 || status == 501 || status == 422) return false;
    throw _failure(status);
  }

  /// Ends the session. 404/410 mean it is already gone (the operator stopped it, or the server
  /// timed it out): success.
  Future<void> delete({
    required WhipSession session,
    required String token,
  }) async {
    final response = await _send(
      () =>
          _dio.deleteUri<String>(session.resourceUrl, options: _options(token)),
    );
    final status = response.statusCode ?? 0;
    if (status >= 200 && status < 300 || status == 404 || status == 410) {
      return;
    }
    throw _failure(status);
  }
}

/// Builds the SDP fragment of RFC 8840 for late candidates of one media section.
String trickleFragment({
  required String iceUfrag,
  required String icePwd,
  required String mid,
  required List<String> candidates,
  bool endOfCandidates = false,
}) {
  final b = StringBuffer()
    ..write('a=ice-ufrag:$iceUfrag\r\n')
    ..write('a=ice-pwd:$icePwd\r\n')
    ..write('m=audio 9 RTP/AVP 0\r\n')
    ..write('a=mid:$mid\r\n');
  for (final c in candidates) {
    b.write(c.startsWith('a=') ? '$c\r\n' : 'a=$c\r\n');
  }
  if (endOfCandidates) b.write('a=end-of-candidates\r\n');
  return b.toString();
}

/// Dio for the media server: short timeouts, no identity headers.
final whipDioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 15),
    ),
  );
  final adapter = ref.watch(httpAdapterProvider);
  if (adapter != null) dio.httpClientAdapter = adapter;
  return dio;
});

final whipClientProvider = Provider<WhipClient>(
  (ref) => WhipClient(ref.watch(whipDioProvider)),
);
