import 'dart:math';

/// Exponential back-off with "equal jitter": half of the exponential delay is fixed, the other
/// half random, so thousands of phones coming back online (e.g. after a storm cut the network)
/// do not hit the API in lockstep. `Retry-After` from the server is a floor.
Duration backoffDelay(
  int attempt,
  Random random, {
  Duration base = const Duration(seconds: 5),
  Duration cap = const Duration(minutes: 30),
  Duration? retryAfter,
}) {
  final n = attempt < 1 ? 0 : min(attempt - 1, 20);
  final exp = base.inMilliseconds * pow(2, n);
  final capped = min(exp, cap.inMilliseconds).toInt();
  final half = capped ~/ 2;
  final delay = Duration(milliseconds: half + random.nextInt(half + 1));
  if (retryAfter != null && retryAfter > delay) return retryAfter;
  return delay;
}
