// The mission sheet on the leader's phone (Yamen, 2026-11-10: print the incident or keep it on the phone). The PDF is
// downloaded from the server and kept in the app's documents, so it opens again without network; the phone's viewer
// prints or shares it.
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../features/rewards/rewards_providers.dart' show fileOpenerProvider;
import 'staff_controller.dart' show staffApiProvider;

/// Where the sheets are kept: the app's documents (not the cache, which the system may clear).
final missionSheetDirProvider = Provider<Future<Directory> Function()>(
  (ref) =>
      () async => Directory(
        p.join((await getApplicationDocumentsDirectory()).path, 'missions'),
      ),
);

enum SheetResult {
  /// Downloaded now, saved and opened.
  opened,

  /// No network: the copy saved earlier was opened.
  openedSaved,

  /// Saved, but no app on the phone opens a PDF.
  noViewer,

  /// Neither downloaded nor saved before.
  failed,
}

final openMissionSheetProvider =
    Provider<Future<SheetResult> Function(String missionId)>((ref) {
      return (missionId) async {
        final dir = await ref.read(missionSheetDirProvider)();
        final name = missionId.replaceAll(RegExp('[^A-Za-z0-9_-]'), '');
        final file = File(p.join(dir.path, 'mission-$name.pdf'));
        final open = ref.read(fileOpenerProvider);
        try {
          final bytes = await ref
              .read(staffApiProvider)
              .missionSheet(missionId);
          await dir.create(recursive: true);
          await file.writeAsBytes(bytes, flush: true);
        } on Object {
          if (!file.existsSync()) return SheetResult.failed;
          return await open(file.path, 'application/pdf')
              ? SheetResult.openedSaved
              : SheetResult.noViewer;
        }
        return await open(file.path, 'application/pdf')
            ? SheetResult.opened
            : SheetResult.noViewer;
      };
    });
