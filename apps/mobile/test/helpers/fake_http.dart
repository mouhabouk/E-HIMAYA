import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// A recorded request seen by [FakeAdapter].
class SeenRequest {
  SeenRequest(this.method, this.uri, this.headers, this.body);

  final String method;
  final Uri uri;
  final Map<String, dynamic> headers;
  final Uint8List? body;

  String get path => uri.path;
  String get text => body == null ? '' : utf8.decode(body!);
  Object? get json =>
      body == null || body!.isEmpty ? null : jsonDecode(utf8.decode(body!));

  String? header(String name) {
    for (final e in headers.entries) {
      if (e.key.toLowerCase() == name.toLowerCase()) return '${e.value}';
    }
    return null;
  }

  @override
  String toString() => '$method ${uri.path}';
}

class FakeResponse {
  const FakeResponse(
    this.status, {
    this.json,
    this.text,
    this.headers = const {},
    this.networkError = false,
  });

  /// Simulates a dropped connection (no HTTP response at all).
  const FakeResponse.network()
    : status = 0,
      json = null,
      text = null,
      headers = const {},
      networkError = true;

  final int status;
  final Object? json;

  /// Raw body (SDP for WHIP), sent instead of [json].
  final String? text;
  final Map<String, String> headers;
  final bool networkError;
}

typedef FakeHandler = FutureOr<FakeResponse> Function(SeenRequest request);

/// In-process HTTP adapter for Dio: no sockets, every request answered by [handler].
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);

  FakeHandler handler;
  final List<SeenRequest> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    Uint8List? body;
    if (requestStream != null) {
      final builder = BytesBuilder(copy: false);
      await for (final chunk in requestStream) {
        builder.add(chunk);
      }
      body = builder.takeBytes();
    }
    final seen = SeenRequest(
      options.method,
      options.uri,
      Map.of(options.headers),
      body,
    );
    requests.add(seen);
    final r = await handler(seen);
    if (r.networkError) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'fake network error',
      );
    }
    final headers = <String, List<String>>{
      for (final e in r.headers.entries) e.key.toLowerCase(): [e.value],
      if (r.json != null) 'content-type': ['application/json'],
    };
    return ResponseBody.fromString(
      r.text ?? (r.json == null ? '' : jsonEncode(r.json)),
      r.status,
      headers: headers,
    );
  }

  @override
  void close({bool force = false}) {}
}
