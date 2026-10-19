import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../http/api_error.dart';
import '../logging/log.dart';

final _log = logger('tus');

/// Minimal tus 1.0 client (core protocol + `creation`) on top of Dio.
///
/// The Dio instance carries the identity interceptor, so tusd receives the same
/// `Authorization` / `X-Device-Key` header as the API (contract §4).
class TusClient {
  TusClient(this._dio, {this.chunkSize = defaultChunkSize});

  static const tusVersion = '1.0.0';
  static const defaultChunkSize = 1024 * 1024;

  final Dio _dio;
  final int chunkSize;

  /// `POST` with `Upload-Length` and `Upload-Metadata`; returns the absolute upload URL.
  Future<Uri> create({
    required int length,
    required Map<String, String> metadata,
  }) async {
    final response = await _call(
      () => _dio.post<Object?>(
        '',
        options: Options(
          headers: {
            'Tus-Resumable': tusVersion,
            'Upload-Length': '$length',
            'Upload-Metadata': encodeMetadata(metadata),
          },
          responseType: ResponseType.plain,
        ),
      ),
    );
    final location = response.headers.value('location');
    if (response.statusCode != 201 || location == null) {
      throw TusException('creation failed', response.statusCode);
    }
    final base = Uri.parse(_dio.options.baseUrl);
    return base.resolve(location);
  }

  /// `HEAD` → current `Upload-Offset` of an existing upload.
  Future<int> offset(Uri uploadUrl) async {
    final response = await _call(
      () => _dio.headUri<Object?>(
        uploadUrl,
        options: Options(
          headers: {'Tus-Resumable': tusVersion},
          responseType: ResponseType.plain,
        ),
      ),
    );
    final value = int.tryParse(response.headers.value('upload-offset') ?? '');
    if (value == null) throw TusException('missing Upload-Offset', 0);
    return value;
  }

  /// `PATCH` one chunk at [offset]; returns the new offset acknowledged by the server.
  Future<int> patch(Uri uploadUrl, int offset, Uint8List chunk) async {
    final response = await _call(
      () => _dio.patchUri<Object?>(
        uploadUrl,
        data: Stream<List<int>>.value(chunk),
        options: Options(
          headers: {
            'Tus-Resumable': tusVersion,
            'Upload-Offset': '$offset',
            Headers.contentTypeHeader: 'application/offset+octet-stream',
            Headers.contentLengthHeader: chunk.length,
          },
          responseType: ResponseType.plain,
        ),
      ),
    );
    final next = int.tryParse(response.headers.value('upload-offset') ?? '');
    if (next == null) throw TusException('missing Upload-Offset', 0);
    return next;
  }

  /// Uploads [file] from the stored [uploadUrl]/[offset] (or creates the upload), persisting
  /// progress through [onProgress] after creation and after every chunk so an interrupted
  /// upload resumes where it stopped. When resuming, the offset is re-read with `HEAD`.
  ///
  /// Network errors inside a run are retried from a fresh `HEAD` up to [maxResumes] times;
  /// beyond that the error is rethrown and the caller schedules a later attempt.
  Future<Uri> upload({
    required File file,
    required Map<String, String> metadata,
    required Future<void> Function(Uri uploadUrl, int offset) onProgress,
    Uri? uploadUrl,
    int maxResumes = 2,
  }) async {
    final length = await file.length();
    var url = uploadUrl;
    var offset = 0;
    if (url == null) {
      url = await create(length: length, metadata: metadata);
      await onProgress(url, 0);
    } else {
      offset = await this.offset(url);
      await onProgress(url, offset);
    }

    final raf = await file.open();
    var resumes = 0;
    try {
      while (offset < length) {
        final size = (length - offset) < chunkSize
            ? length - offset
            : chunkSize;
        await raf.setPosition(offset);
        final chunk = await raf.read(size);
        try {
          offset = await patch(url, offset, chunk);
          resumes = 0;
          await onProgress(url, offset);
        } on TusException catch (e) {
          // 409 = offset mismatch; network errors may have hit the server or not.
          if (!(e.isNetwork || e.statusCode == 409) || resumes >= maxResumes) {
            rethrow;
          }
          resumes++;
          _log.fine('resuming upload after ${e.statusCode ?? 'network'} error');
          offset = await this.offset(url);
          await onProgress(url, offset);
        }
      }
    } finally {
      await raf.close();
    }
    return url;
  }

  Future<Response<Object?>> _call(
    Future<Response<Object?>> Function() call,
  ) async {
    try {
      return await call();
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      if (status == null) throw TusException.network();
      throw TusException('HTTP $status', status, api: ApiException.fromDio(e));
    }
  }

  /// `key base64(value)` pairs separated by commas (tus 1.0 `Upload-Metadata`).
  static String encodeMetadata(Map<String, String> metadata) => metadata.entries
      .map((e) => '${e.key} ${base64.encode(utf8.encode(e.value))}')
      .join(',');
}

class TusException implements Exception {
  TusException(this.message, this.statusCode, {this.api});
  TusException.network() : message = 'network', statusCode = null, api = null;

  final String message;
  final int? statusCode;
  final ApiException? api;

  bool get isNetwork => statusCode == null;

  /// 404/410: the upload expired on the server; a new one must be created.
  bool get uploadGone => statusCode == 404 || statusCode == 410;

  /// Worth retrying later. Every other 4xx is permanent for that file (contract §4), except
  /// 401 which the identity interceptor already answered with a token refresh + retry.
  bool get isTransient =>
      isNetwork ||
      statusCode == 401 ||
      statusCode == 408 ||
      statusCode == 423 ||
      statusCode == 429 ||
      (statusCode != null && statusCode! >= 500);

  /// Contract error code from the JSON body (`{"detail": code}`), if any.
  String get code =>
      api?.code.wire ?? (isNetwork ? 'network' : 'http_$statusCode');

  @override
  String toString() => 'TusException($message, $statusCode)';
}
