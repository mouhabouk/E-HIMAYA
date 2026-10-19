import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:ehimaya/core/http/api_client.dart';
import 'package:ehimaya/core/identity/device_key.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

class _Headers implements IdentityHeaderSource {
  _Headers(this.value);
  Map<String, String> value;
  int refreshes = 0;
  bool blocked = false;

  @override
  Future<Map<String, String>> headers() async => value;

  @override
  Future<bool> refreshAfterUnauthorized() async {
    refreshes++;
    value = {'Authorization': 'Bearer fresh'};
    return true;
  }

  @override
  void onAnonBlocked() => blocked = true;
}

void main() {
  group('device key', () {
    test('is 32 random bytes, base64url without padding', () {
      final key = DeviceKeyStore.generate(Random(42));
      expect(key, hasLength(43));
      expect(DeviceKeyStore.format.hasMatch(key), isTrue);
      expect(key.contains('='), isFalse);
      expect(key.contains('+') || key.contains('/'), isFalse);
      expect(base64Url.decode(base64Url.normalize(key)), hasLength(32));
    });

    test('is generated once and persisted in secure storage', () async {
      final store = MemorySecureStore();
      final first = await DeviceKeyStore(store).get();
      final second = await DeviceKeyStore(store).get();
      expect(first, second);
      expect(store.values[SecureStoreKeys.deviceKey], first);
    });

    test('a corrupted stored value is replaced', () async {
      final store = MemorySecureStore({SecureStoreKeys.deviceKey: 'short'});
      final key = await DeviceKeyStore(store).get();
      expect(DeviceKeyStore.format.hasMatch(key), isTrue);
    });

    test('two installs get different keys', () async {
      final a = await DeviceKeyStore(MemorySecureStore()).get();
      final b = await DeviceKeyStore(MemorySecureStore()).get();
      expect(a, isNot(b));
    });
  });

  group('identity interceptor', () {
    test('sends X-Device-Key only, never with a Bearer token', () async {
      final adapter = FakeAdapter((_) => const FakeResponse(200, json: {}));
      final dio = buildDio(
        baseUrl: 'http://api.test',
        identity: _Headers({'X-Device-Key': 'k' * 43}),
        adapter: adapter,
      );
      await dio.get<Object?>(
        '/x',
        options: Options(headers: {'Authorization': 'Bearer stale'}),
      );
      final r = adapter.requests.single;
      expect(r.header('X-Device-Key'), 'k' * 43);
      expect(r.header('Authorization'), isNull);
    });

    test('public endpoints carry no identity header', () async {
      final adapter = FakeAdapter((_) => const FakeResponse(200, json: {}));
      final dio = buildDio(
        baseUrl: 'http://api.test',
        identity: _Headers({'X-Device-Key': 'k' * 43}),
        adapter: adapter,
      );
      await dio.get<Object?>(
        '/track',
        options: Options(extra: {kPublicEndpoint: true}),
      );
      expect(adapter.requests.single.header('X-Device-Key'), isNull);
    });

    test('401 on a Bearer request refreshes once and retries', () async {
      final source = _Headers({'Authorization': 'Bearer old'});
      final adapter = FakeAdapter(
        (r) => r.header('Authorization') == 'Bearer fresh'
            ? const FakeResponse(200, json: {'ok': true})
            : const FakeResponse(
                401,
                json: {'detail': 'authentication_required'},
              ),
      );
      final dio = buildDio(
        baseUrl: 'http://api.test',
        identity: source,
        adapter: adapter,
      );
      final r = await dio.get<Map<String, Object?>>('/x');
      expect(r.data, {'ok': true});
      expect(source.refreshes, 1);
      expect(adapter.requests, hasLength(2));
    });

    test('403 anon_blocked is reported to the app', () async {
      final source = _Headers({'X-Device-Key': 'k' * 43});
      final dio = buildDio(
        baseUrl: 'http://api.test',
        identity: source,
        adapter: FakeAdapter(
          (_) => const FakeResponse(403, json: {'detail': 'anon_blocked'}),
        ),
      );
      await expectLater(
        guardApi(() => dio.get<Object?>('/x')),
        throwsA(anything),
      );
      expect(source.blocked, isTrue);
    });
  });
}
