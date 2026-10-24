import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/http/doctor_models.dart';
import '../../core/http/ehimaya_api.dart';

/// The account's doctor registration (phase C1-a). Null when there is none; always null for
/// anonymous users (the doctor's space needs a registered account).
class DoctorController extends AsyncNotifier<Doctor?> {
  @override
  Future<Doctor?> build() async {
    final registered = ref.watch(
      identityProvider.select((s) => s.isRegistered ? s.fingerprint : null),
    );
    if (registered == null) return null;
    return ref.read(apiProvider).myDoctor();
  }

  Future<void> reload() async {
    final d = await ref.read(apiProvider).myDoctor();
    if (ref.mounted) state = AsyncData(d);
  }

  Future<Doctor> submit(DoctorInput input) async {
    final d = await ref.read(apiProvider).putDoctor(input);
    if (ref.mounted) state = AsyncData(d);
    return d;
  }

  Future<void> withdraw() async {
    await ref.read(apiProvider).withdrawDoctor();
    await reload();
  }

  /// Phase C1-b: the doctor's public key and its code-locked backup.
  Future<void> applyKey(String publicKey, Map<String, Object?> backup) async {
    final d = await ref.read(apiProvider).putDoctorKey(publicKey, backup);
    if (ref.mounted) state = AsyncData(d);
  }

  /// Available for the next [hours] (shown first in the referral list), or not.
  Future<void> setAvailable(bool available, {int hours = 8}) async {
    final d = await ref
        .read(apiProvider)
        .setDoctorAvailability(available: available, hours: hours);
    if (ref.mounted) state = AsyncData(d);
  }
}

final doctorProvider = AsyncNotifierProvider<DoctorController, Doctor?>(
  DoctorController.new,
  retry: (_, _) => null,
);

/// Filters of the doctors' directory.
typedef DirectoryFilter = ({DoctorSpecialty? specialty, int? gouvernorat});

final doctorDirectoryProvider = FutureProvider.autoDispose
    .family<List<DirectoryDoctor>, DirectoryFilter>(
      (ref, f) => ref
          .watch(apiProvider)
          .doctorDirectory(
            specialty: f.specialty,
            gouvernoratCode: f.gouvernorat,
          ),
      retry: (_, _) => null,
    );

/// The doctor's locked medical files (phase C1-b).
final medicalFilesProvider = FutureProvider.autoDispose<List<MedicalInboxItem>>(
  (ref) => ref.watch(apiProvider).medicalFiles(),
  retry: (_, _) => null,
);

/// Phase C1-c: the specialists a file went to (gouvernorat group and committee only).
final fileReferralsProvider = FutureProvider.autoDispose
    .family<List<FileReferral>, String>(
      (ref, reportId) => ref.watch(apiProvider).fileReferrals(reportId),
      retry: (_, _) => null,
    );

/// The opinions on a file locked for this doctor (still locked: opened on the screen).
final fileOpinionsProvider = FutureProvider.autoDispose
    .family<List<LockedOpinion>, String>(
      (ref, reportId) => ref.watch(apiProvider).medicalOpinions(reportId),
      retry: (_, _) => null,
    );

/// Committee members waiting for keys this member's phone can lock for them.
final committeePendingProvider =
    FutureProvider.autoDispose<List<PendingMember>>(
      (ref) => ref.watch(apiProvider).committeePending(),
      retry: (_, _) => null,
    );

/// The reporter's side: who opened their locked medical files, by role only.
final myMedicalOpeningsProvider =
    FutureProvider.autoDispose<List<MedicalOpening>>(
      (ref) => ref.watch(apiProvider).myMedicalOpenings(),
      retry: (_, _) => null,
    );
