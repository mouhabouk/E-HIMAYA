import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/quota/anon_quota_controller.dart';
import '../../core/sync/report_queue.dart';
import '../../core/sync/sync_scheduler.dart';

/// What happened to a submitted report form.
class SubmitOutcome {
  const SubmitOutcome(this.queued, {required this.keptForAccount});

  final QueuedReport queued;

  /// The anonymous quota is known to be exhausted (phase 9 §3): the report is kept on the
  /// device as `blocked` and goes once the user signs in; the quota screen explains why.
  final bool keptForAccount;
}

/// Queues a report form. A non-SOS report of an anonymous installation whose quota is known to
/// be exhausted is kept (`blocked`) instead of being sent to be refused; anything else is queued
/// and a sync pass is requested at once. The SOS button does not come through here and is never
/// gated (`SosService`).
final reportSubmitterProvider =
    Provider<Future<SubmitOutcome> Function(ReportDraft draft)>(
      (ref) => (draft) async {
        final blocked = anonQuotaBlocks(
          identity: ref.read(identityProvider),
          category: draft.category,
          quota: ref.read(anonQuotaProvider),
        );
        final queued = await ref
            .read(reportQueueProvider)
            .enqueue(draft, blocked: blocked);
        if (!blocked) unawaited(ref.read(requestSyncProvider)());
        return SubmitOutcome(queued, keptForAccount: blocked);
      },
    );
