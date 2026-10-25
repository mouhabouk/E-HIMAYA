import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/tus/tus_client.dart';
import 'package:ehimaya/features/institution/maintenance_photo.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

void main() {
  late Directory tmp;

  setUp(() async => tmp = await Directory.systemTemp.createTemp('maint'));
  tearDown(() => tmp.delete(recursive: true));

  test('only JPEG or PNG of at most 10 MB', () async {
    final jpg = File('${tmp.path}/a.jpg')..writeAsBytesSync([1, 2, 3]);
    final png = File('${tmp.path}/a.png')..writeAsBytesSync([1, 2, 3]);
    final mp4 = File('${tmp.path}/a.mp4')..writeAsBytesSync([1, 2, 3]);
    final big = File('${tmp.path}/big.jpg');
    final raf = big.openSync(mode: FileMode.write)
      ..truncateSync(maintenancePhotoMaxBytes + 1);
    raf.closeSync();
    expect(await checkMaintenancePhoto(jpg), isNull);
    expect(await checkMaintenancePhoto(png), isNull);
    expect(await checkMaintenancePhoto(mp4), PhotoProblem.unsupported);
    expect(await checkMaintenancePhoto(big), PhotoProblem.tooLarge);
  });

  test('creates the document, then sends the photo with its SHA-256', () async {
    final bytes = Uint8List.fromList(List.generate(3000, (i) => i % 251));
    final file = File('${tmp.path}/photo.jpg')..writeAsBytesSync(bytes);
    final seen = <SeenRequest>[];
    FakeResponse handle(SeenRequest r) {
      seen.add(r);
      return switch ((r.method, r.path)) {
        ('POST', '/api/v1/orgs/o1/documents') => const FakeResponse(
          201,
          json: {'id': 'd1', 'kind': 'maintenance_photo'},
        ),
        ('POST', '/api/v1/uploads/') => const FakeResponse(
          201,
          headers: {'Location': '/api/v1/uploads/t1'},
        ),
        ('PATCH', '/api/v1/uploads/t1') => FakeResponse(
          204,
          headers: {'Upload-Offset': '${bytes.length}'},
        ),
        _ => const FakeResponse(404, json: {'detail': 'not_found'}),
      };
    }

    final api = EHimayaApi(
      Dio(BaseOptions(baseUrl: 'http://api.test'))
        ..httpClientAdapter = FakeAdapter(handle),
    );
    final tus = TusClient(
      Dio(BaseOptions(baseUrl: 'http://tus.test/api/v1/uploads/'))
        ..httpClientAdapter = FakeAdapter(handle),
    );
    final id = await uploadMaintenancePhoto(
      api: api,
      tus: tus,
      orgId: 'o1',
      file: file,
      title: 'extinguisher 2026-10-25',
    );
    expect(id, 'd1');
    expect(seen.first.json, {
      'kind': 'maintenance_photo',
      'title': 'extinguisher 2026-10-25',
    });
    final create = seen.firstWhere((r) => r.path == '/api/v1/uploads/');
    final meta = {
      for (final pair in create.header('Upload-Metadata')!.split(','))
        pair.split(' ').first: utf8.decode(base64.decode(pair.split(' ').last)),
    };
    expect(meta['target'], 'org_document');
    expect(meta['document_id'], 'd1');
    expect(meta['filetype'], 'image/jpeg');
    expect(meta['sha256'], sha256.convert(bytes).toString());
    expect(meta['filename'], 'photo.jpg');
  });
}
