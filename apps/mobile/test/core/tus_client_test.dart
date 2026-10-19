import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:ehimaya/core/tus/tus_client.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

/// Minimal tus server state machine for the fake adapter.
class FakeTusServer {
  FakeTusServer({this.locationIsRelative = true});

  final bool locationIsRelative;
  final Map<String, BytesBuilder> uploads = {};
  final Map<String, int> lengths = {};
  final Map<String, String> metadata = {};
  int created = 0;

  /// PATCH numbers (1-based, across the server lifetime) that fail with a network error after
  /// the server has stored the bytes (worst case: the client cannot know).
  Set<int> dropAfterStoring = {};
  int patches = 0;

  FakeResponse handle(SeenRequest r) {
    expect(r.header('Tus-Resumable'), '1.0.0');
    switch (r.method) {
      case 'POST':
        final id = 'u${++created}';
        uploads[id] = BytesBuilder();
        lengths[id] = int.parse(r.header('Upload-Length')!);
        metadata[id] = r.header('Upload-Metadata')!;
        return FakeResponse(
          201,
          headers: {
            'Location': locationIsRelative
                ? '/api/v1/uploads/$id'
                : 'http://tus.test/api/v1/uploads/$id',
          },
        );
      case 'HEAD':
        final id = r.uri.pathSegments.last;
        return FakeResponse(
          200,
          headers: {
            'Upload-Offset': '${uploads[id]!.length}',
            'Upload-Length': '${lengths[id]}',
          },
        );
      case 'PATCH':
        patches++;
        final id = r.uri.pathSegments.last;
        expect(r.header('Content-Type'), 'application/offset+octet-stream');
        final offset = int.parse(r.header('Upload-Offset')!);
        if (offset != uploads[id]!.length) return const FakeResponse(409);
        uploads[id]!.add(r.body!);
        if (dropAfterStoring.contains(patches)) {
          return const FakeResponse.network();
        }
        return FakeResponse(
          204,
          headers: {'Upload-Offset': '${uploads[id]!.length}'},
        );
    }
    return const FakeResponse(405);
  }
}

void main() {
  late Directory tmp;
  late File file;
  late Uint8List content;

  setUp(() async {
    tmp = await Directory.systemTemp.createTemp('tus_test');
    // 2.5 chunks of 1 KiB in tests (chunkSize is configurable; production uses 1 MiB).
    content = Uint8List.fromList(List.generate(2560, (i) => i % 251));
    file = File('${tmp.path}/video.mp4')..writeAsBytesSync(content);
  });

  tearDown(() => tmp.delete(recursive: true));

  TusClient client(FakeTusServer server, {int chunk = 1024}) {
    final dio = Dio(BaseOptions(baseUrl: 'http://tus.test/api/v1/uploads/'))
      ..httpClientAdapter = FakeAdapter(server.handle);
    return TusClient(dio, chunkSize: chunk);
  }

  test('default chunk size is 1 MiB', () {
    expect(TusClient.defaultChunkSize, 1024 * 1024);
  });

  test('metadata is encoded as key base64(value) pairs', () {
    final encoded = TusClient.encodeMetadata({
      'report_id': 'abc',
      'filetype': 'video/mp4',
    });
    final pairs = encoded.split(',');
    expect(pairs, hasLength(2));
    expect(pairs.first, 'report_id ${base64.encode(utf8.encode('abc'))}');
    expect(pairs.last, 'filetype ${base64.encode(utf8.encode('video/mp4'))}');
  });

  test('create sends Upload-Length and resolves a relative Location', () async {
    final server = FakeTusServer();
    final url = await client(server)
        .create(length: 42, metadata: {'kind': 'video'});
    expect(url.toString(), 'http://tus.test/api/v1/uploads/u1');
    expect(server.lengths['u1'], 42);
    expect(server.metadata['u1'], startsWith('kind '));
  });

  test('uploads in chunks and persists progress after each chunk', () async {
    final server = FakeTusServer(locationIsRelative: false);
    final progress = <int>[];
    final url = await client(server).upload(
      file: file,
      metadata: {'kind': 'video'},
      onProgress: (_, offset) async => progress.add(offset),
    );
    expect(url.pathSegments.last, 'u1');
    expect(server.patches, 3);
    expect(progress, [0, 1024, 2048, 2560]);
    expect(server.uploads['u1']!.toBytes(), content);
  });

  test('resumes with HEAD after an interrupted PATCH', () async {
    final server = FakeTusServer()..dropAfterStoring = {2};
    final progress = <int>[];
    await client(server).upload(
      file: file,
      metadata: {'kind': 'video'},
      onProgress: (_, offset) async => progress.add(offset),
    );
    // Second PATCH reached the server but the answer was lost: HEAD says 2048, no duplicate.
    expect(server.uploads['u1']!.toBytes(), content);
    expect(progress, [0, 1024, 2048, 2560]);
    expect(server.created, 1);
  });

  test('resumes a stored upload URL from the server offset', () async {
    final server = FakeTusServer();
    final tus = client(server);
    // First run: the connection drops for good after the first chunk.
    server.dropAfterStoring = {2, 3, 4, 5};
    Uri? stored;
    var storedOffset = -1;
    await expectLater(
      tus.upload(
        file: file,
        metadata: {'kind': 'video'},
        onProgress: (u, o) async {
          stored = u;
          storedOffset = o;
        },
        maxResumes: 0,
      ),
      throwsA(isA<TusException>().having((e) => e.isNetwork, 'network', true)),
    );
    expect(storedOffset, 1024);

    // Later run (e.g. after an app restart): HEAD first, then continue.
    server.dropAfterStoring = {};
    final requestsBefore = server.patches;
    await tus.upload(
      file: file,
      metadata: {'kind': 'video'},
      uploadUrl: stored,
      onProgress: (_, _) async {},
    );
    expect(server.created, 1);
    expect(server.uploads['u1']!.toBytes(), content);
    // The second chunk had been stored before the drop: only the last chunk is sent again.
    expect(server.patches - requestsBefore, 1);
  });

  test('a refused creation surfaces the contract error code', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://tus.test/api/v1/uploads/'))
      ..httpClientAdapter = FakeAdapter(
        (_) =>
            const FakeResponse(409, json: {'detail': 'upload_window_closed'}),
      );
    final tus = TusClient(dio, chunkSize: 1024);
    await expectLater(
      tus.upload(file: file, metadata: {}, onProgress: (_, _) async {}),
      throwsA(
        isA<TusException>()
            .having((e) => e.code, 'code', 'upload_window_closed')
            .having((e) => e.isTransient, 'transient', false),
      ),
    );
  });
}
