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
