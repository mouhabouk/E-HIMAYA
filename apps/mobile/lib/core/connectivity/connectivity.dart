import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../power/scheduling.dart';

/// Network reachability hint (a connected interface does not guarantee the API is reachable;
/// the sync engine handles failures itself).
abstract class ConnectivityMonitor {
  Stream<bool> get onlineChanges;
  Future<bool> isOnline();

  /// Wi-Fi/Ethernet versus mobile data (large media may wait for Wi-Fi in battery saver).
  Future<NetworkKind> networkKind();
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

  @override
  Future<NetworkKind> networkKind() async {
    final r = await _connectivity.checkConnectivity();
    if (!_online(r)) return NetworkKind.none;
    // Mobile data wins when both are up (the system routes over it then).
    if (r.contains(ConnectivityResult.mobile)) return NetworkKind.metered;
    if (r.contains(ConnectivityResult.wifi) ||
        r.contains(ConnectivityResult.ethernet)) {
      return NetworkKind.unmetered;
    }
    return NetworkKind.metered;
  }
}

final connectivityProvider = Provider<ConnectivityMonitor>(
  (ref) => PlatformConnectivityMonitor(),
);

/// Whether any network interface is up, for the UI (the offline SMS / 198 fallback). Starts
/// from the current state and follows the changes.
final onlineProvider = StreamProvider<bool>((ref) async* {
  final monitor = ref.watch(connectivityProvider);
  yield await monitor.isOnline();
  yield* monitor.onlineChanges;
});
