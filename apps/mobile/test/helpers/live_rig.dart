import 'dart:io';

import 'package:dio/dio.dart';
import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/config/providers.dart';
import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/consent/consent_service.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/db/open_database.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/platform/device_services.dart';
import 'package:ehimaya/core/power/battery_saver.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/security/locked_alert.dart';
import 'package:ehimaya/core/settings/settings_controller.dart';
import 'package:ehimaya/core/sync/report_queue.dart';
import 'package:ehimaya/core/sync/sync_engine.dart';
import 'package:ehimaya/core/tus/tus_client.dart';
import 'package:ehimaya/core/webrtc/whip_client.dart';
import 'package:ehimaya/features/live/live_controller.dart';
import 'package:ehimaya/features/live/live_publisher.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;

import 'fake_http.dart';
import 'hardening_fakes.dart';
import 'live_fakes.dart';

class _NoConsent implements ConsentSender {
  @override
  Future<bool> sendIfNeeded({bool force = false}) async => true;
}

class LiveConnectivity implements ConnectivityMonitor {
  LiveConnectivity([this.kind = NetworkKind.unmetered]);
  NetworkKind kind;
  @override
  Future<bool> isOnline() async => kind != NetworkKind.none;
  @override
  Stream<bool> get onlineChanges => const Stream.empty();
  @override
  Future<NetworkKind> networkKind() async => kind;
}

/// A [ProviderContainer] wired for the live controller: fake API/MediaMTX, fake camera, fake
/// position, in-memory queue, injectable clock.
class LiveRig {
  LiveRig({
    required DateTime Function() clock,
    this.locked = false,
    this.batterySaver = false,
    NetworkKind network = NetworkKind.unmetered,
    LiveTimings timings = const LiveTimings(),
    Directory? mediaDir,
    List<Override> overrides = const [],
  }) {
    driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
    db = inMemoryDatabase();
    adapter = FakeAdapter(server.handle);
    final apiDio = Dio(BaseOptions(baseUrl: 'http://api.test'))
      ..httpClientAdapter = adapter;
    final tusDio = Dio(BaseOptions(baseUrl: 'http://tus.test/api/v1/uploads/'))
      ..httpClientAdapter = adapter;
    final api = EHimayaApi(apiDio);
    connectivity = LiveConnectivity(network);
    container = ProviderContainer(
      overrides: [
        apiProvider.overrideWithValue(api),
        whipDioProvider.overrideWithValue(Dio()..httpClientAdapter = adapter),
        livePublisherFactoryProvider.overrideWithValue(() {
          final p = FakeLivePublisher(autoConnect: autoConnect)
            ..openError = mediaError;
          publishers.add(p);
          return p;
        }),
        locationServiceProvider.overrideWithValue(location),
        deviceServicesProvider.overrideWithValue(device),
        connectivityProvider.overrideWithValue(connectivity),
        batterySaverActiveProvider.overrideWithValue(batterySaver),
        databaseProvider.overrideWithValue(db),
        mediaDirProvider.overrideWithValue(
          () async => mediaDir ?? Directory.systemTemp,
        ),
        clockProvider.overrideWithValue(clock),
        localeCodeProvider.overrideWithValue('ar'),
        initialLockedAlertProvider.overrideWithValue(locked),
        liveTimingsProvider.overrideWithValue(timings),
        syncEngineProvider.overrideWith(
          (ref) => SyncEngine(
            db: db,
            api: api,
            tus: TusClient(tusDio),
            consent: _NoConsent(),
            clock: clock,
            identity: () => const IdentityState(
              mode: IdentityMode.anonymous,
              role: UserRole.citizen,
            ),
            onAnonBlocked: () {},
          ),
        ),
        ...overrides,
      ],
    );
  }

  final bool locked;
  final bool batterySaver;
  late final AppDatabase db;
  late final FakeAdapter adapter;
  late final ProviderContainer container;
  late final LiveConnectivity connectivity;
  final server = FakeLiveServer();
  final location = LiveFakeLocation();
  final device = FakeDeviceServices();
  final publishers = <FakeLivePublisher>[];
  bool autoConnect = true;

  /// Thrown by the next publishers' `openMedia` (e.g. [MediaPermissionDenied]).
  Object? mediaError;

  FakeLivePublisher get publisher => publishers.last;
  LiveController get controller =>
      container.read(liveControllerProvider.notifier);
  LiveState get state => container.read(liveControllerProvider);

  List<SeenRequest> requests(String method, String pathPattern) => [
    for (final r in adapter.requests)
      if (r.method == method && RegExp(pathPattern).hasMatch(r.uri.toString()))
        r,
  ];

  Future<void> dispose() async {
    container.dispose();
    await db.close();
  }
}
