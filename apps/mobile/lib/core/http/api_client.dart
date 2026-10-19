import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/identity.dart';
import '../config/providers.dart';
import '../identity/device_key.dart';
import '../logging/log.dart';
import 'api_error.dart';

final _log = logger('http');

/// Supplies the identity headers of the current caller. Exactly one of `Authorization` or
/// `X-Device-Key` is ever returned (contract §1: never both).
abstract class IdentityHeaderSource {
  Future<Map<String, String>> headers();

  /// Called after a 401 on a Bearer request. Returns true when a fresh token is available.
  Future<bool> refreshAfterUnauthorized();

  void onAnonBlocked();
}

/// Request option: skip identity headers (public endpoints such as tracking by code).
const kPublicEndpoint = 'ehimaya.public';
const _kRetried = 'ehimaya.retried';

class IdentityInterceptor extends Interceptor {
  IdentityInterceptor(this._source, this._dio);

  final IdentityHeaderSource _source;
  final Dio _dio;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    options.headers.remove('Authorization');
    options.headers.remove('X-Device-Key');
    if (options.extra[kPublicEndpoint] != true) {
      try {
        options.headers.addAll(await _source.headers());
      } on Object catch (e, st) {
        _log.warning('identity headers unavailable', e, st);
      }
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final response = err.response;
    final options = err.requestOptions;
    if (response?.statusCode == 401 &&
        options.headers.containsKey('Authorization') &&
        options.extra[_kRetried] != true) {
      if (await _source.refreshAfterUnauthorized()) {
        try {
          options.extra[_kRetried] = true;
          handler.resolve(await _dio.fetch<Object?>(options));
          return;
        } on DioException catch (e) {
          handler.next(e);
          return;
        }
      }
    }
    if (response?.statusCode == 403) {
      final data = response?.data;
      if (data is Map && data['detail'] == ApiErrorCode.anonBlocked.wire) {
        _source.onAnonBlocked();
      }
    }
    handler.next(err);
  }
}

class RiverpodIdentityHeaders implements IdentityHeaderSource {
  RiverpodIdentityHeaders(this._ref);

  final Ref _ref;

  @override
  Future<Map<String, String>> headers() async {
    final identity = _ref.read(identityProvider);
    switch (identity.mode) {
      case IdentityMode.registered:
        final token = await _ref
            .read(identityProvider.notifier)
            .validAccessToken();
        return token == null ? const {} : {'Authorization': 'Bearer $token'};
      case IdentityMode.anonymous:
        final key = await _ref.read(deviceKeyStoreProvider).get();
        return {'X-Device-Key': key};
      case IdentityMode.none:
        return const {};
    }
  }

  @override
  Future<bool> refreshAfterUnauthorized() async {
    final token = await _ref
        .read(identityProvider.notifier)
        .validAccessToken(forceRefresh: true);
    return token != null;
  }

  @override
  void onAnonBlocked() => _ref.read(anonBlockedProvider.notifier).set(true);
}

/// Builds a Dio with the identity interceptor. Used for the API and for the tus server.
Dio buildDio({
  required String baseUrl,
  required IdentityHeaderSource identity,
  Duration connectTimeout = const Duration(seconds: 15),
  Duration receiveTimeout = const Duration(seconds: 30),
  HttpClientAdapter? adapter,
}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: connectTimeout,
      receiveTimeout: receiveTimeout,
      sendTimeout: const Duration(seconds: 60),
      responseType: ResponseType.json,
      headers: {'Accept': 'application/json'},
    ),
  );
  if (adapter != null) dio.httpClientAdapter = adapter;
  dio.interceptors.add(IdentityInterceptor(identity, dio));
  return dio;
}

final identityHeaderSourceProvider = Provider<IdentityHeaderSource>(
  RiverpodIdentityHeaders.new,
);

/// Optional adapter override (tests).
final httpAdapterProvider = Provider<HttpClientAdapter?>((ref) => null);

final apiDioProvider = Provider<Dio>((ref) {
  final config = ref.watch(appConfigProvider);
  return buildDio(
    baseUrl: config.apiBaseUrl,
    identity: ref.watch(identityHeaderSourceProvider),
    adapter: ref.watch(httpAdapterProvider),
  );
});

final tusDioProvider = Provider<Dio>((ref) {
  final config = ref.watch(appConfigProvider);
  return buildDio(
    baseUrl: config.tusUrl,
    identity: ref.watch(identityHeaderSourceProvider),
    adapter: ref.watch(httpAdapterProvider),
    receiveTimeout: const Duration(seconds: 60),
  );
});

/// Runs [call] and converts transport errors into [ApiException].
Future<T> guardApi<T>(Future<T> Function() call) async {
  try {
    return await call();
  } on DioException catch (e) {
    throw ApiException.fromDio(e);
  }
}
