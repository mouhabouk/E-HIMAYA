import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_config.dart';

final appConfigProvider = Provider<AppConfig>(
  (ref) => AppConfig.fromEnvironment(),
);

/// Injectable clock (tests freeze or advance time).
final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);
