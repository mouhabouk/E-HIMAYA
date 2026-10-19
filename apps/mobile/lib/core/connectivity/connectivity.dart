import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Network reachability hint (a connected interface does not guarantee the API is reachable;
/// the sync engine handles failures itself).
abstract class ConnectivityMonitor {
  Stream<bool> get onlineChanges;
  Future<bool> isOnline();
}

class PlatformConnectivityMonitor implements ConnectivityMonitor {
  final Connectivity _connectivity = Connectivity();

  static bool _online(List<ConnectivityResult> r) =>
      r.any((c) => c != ConnectivityResult.none);

  @override
  Stream<bool> get onlineChanges =>
      _connectivity.onConnectivityChanged.map(_online).distinct();

  @override
  Future<bool> isOnline() async =>
      _online(await _connectivity.checkConnectivity());
}

final connectivityProvider = Provider<ConnectivityMonitor>(
  (ref) => PlatformConnectivityMonitor(),
);
