import 'dart:developer' as developer;

import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';

/// Small logging facade. Never log personal data (names, phones, CIN, tokens, device key,
/// report text): identifiers and error codes only.
Logger logger(String name) => Logger('ehimaya.$name');

bool _configured = false;

void configureLogging() {
  if (_configured) return;
  _configured = true;
  Logger.root.level = kReleaseMode ? Level.WARNING : Level.FINE;
  Logger.root.onRecord.listen((record) {
    developer.log(
      record.message,
      time: record.time,
      level: record.level.value,
      name: record.loggerName,
      error: record.error,
      stackTrace: record.stackTrace,
    );
  });
}
