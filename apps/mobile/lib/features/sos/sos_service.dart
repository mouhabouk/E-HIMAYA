import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/sync/report_queue.dart';
import '../../core/sync/sync_scheduler.dart';

sealed class SosResult {
  const SosResult();
}

class SosQueued extends SosResult {
  const SosQueued(this.tempCode);
  final String tempCode;
}

class SosNoLocation extends SosResult {
  const SosNoLocation();
}

/// One-touch SOS (NFR-09): current position (or the last known one when the fix is slow) is
/// queued as a `sos` report and pushed by the sync engine. [organizationId] sends it on behalf
/// of an institution (FR-A-080); null: the user themselves.
abstract class SosService {
  Future<SosResult> send({String? organizationId});
}

class QueueSosService implements SosService {
  QueueSosService({
    required this.location,
    required this.queue,
    required this.requestSync,
    required this.lang,
  });

  final LocationService location;
  final ReportQueue queue;
  final Future<void> Function() requestSync;
  final String lang;

  @override
  Future<SosResult> send({String? organizationId}) async {
    final point = await location.bestEffort(
      timeout: const Duration(seconds: 5),
    );
    if (point == null) return const SosNoLocation();
    final queued = await queue.enqueue(
      ReportDraft(
        category: ReportCategory.sos,
        location: point,
        lang: lang,
        organizationId: organizationId,
      ),
    );
    unawaited(requestSync());
    return SosQueued(queued.tempCode);
  }
}

final sosServiceProvider = Provider<SosService>(
  (ref) => QueueSosService(
    location: ref.watch(locationServiceProvider),
    queue: ref.watch(reportQueueProvider),
    requestSync: ref.watch(requestSyncProvider),
    lang: ref.watch(localeCodeProvider),
  ),
);
