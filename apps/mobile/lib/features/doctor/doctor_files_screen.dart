import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/doctor_models.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../report/category_labels.dart';
import '../safety/medical_screen.dart';
import '../safety/safety_models.dart';
import 'doctor_key.dart';
import 'doctor_providers.dart';

/// Phase C1-b: the medical files locked for this doctor (their gouvernorat, or the medical
/// committee). Each file is opened on the phone with the doctor's key; the opening is recorded,
/// and a committee member gives a reason.
class DoctorFilesScreen extends ConsumerWidget {
  const DoctorFilesScreen({super.key});

  static String viaLabel(AppLocalizations l10n, FileVia via) => switch (via) {
    FileVia.gouvernorat => l10n.doctorFileViaGouvernorat,
    FileVia.committee => l10n.doctorFileViaCommittee,
    FileVia.referral => l10n.doctorFileViaReferral,
  };

  Future<String?> _askReason(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.doctorFileReasonTitle),
        content: TextField(
          key: const Key('file-reason'),
          controller: controller,
          maxLength: 500,
          autofocus: true,
          decoration: InputDecoration(helperText: l10n.doctorFileReasonHint),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('file-reason-ok'),
            onPressed: () {
              final reason = controller.text.trim();
              if (reason.length >= 3) Navigator.pop(context, reason);
            },
            child: Text(l10n.doctorFileOpen),
          ),
        ],
      ),
    );
  }

  Future<void> _open(
    BuildContext context,
    WidgetRef ref,
    MedicalInboxItem item,
  ) async {
    final l10n = AppLocalizations.of(context);
    final key = await ref.read(doctorKeyProvider.future);
    if (key == null || !context.mounted) return;
    String? reason;
    if (item.via == FileVia.committee) {
      reason = await _askReason(context);
      if (reason == null || !context.mounted) return;
    }
    try {
      final opened = await ref
          .read(apiProvider)
          .openMedicalFile(item.reportId, reason: reason);
      final locked = await ref.read(medicalCryptoProvider).open(opened, key);
      final card = (opened['card'] as Map?)?.cast<String, Object?>() ?? {};
      final file = MedicalFile.fromJson({...card, ...locked});
      ref.invalidate(medicalFilesProvider);
      if (!context.mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => Dialog.fullscreen(
          child: Scaffold(
            appBar: AppBar(
              title: Text(item.trackingCode),
              actions: const [StandardAppBarActions()],
            ),
            body: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  medicalText(l10n, file),
                  key: const Key('file-text'),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 16),
                Text(
                  l10n.doctorFileConfidential,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
      );
    } on Object catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            e is ApiException
                ? errorMessageFor(l10n, e)
                : l10n.doctorFileCannotOpen,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final files = ref.watch(medicalFilesProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.doctorFiles),
        actions: const [StandardAppBarActions()],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(medicalFilesProvider.future),
        child: files.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(
            children: [
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text(errorMessageFor(l10n, e)),
              ),
            ],
          ),
          data: (items) => items.isEmpty
              ? ListView(
                  children: [
                    Padding(
                      key: const Key('files-empty'),
                      padding: const EdgeInsets.all(24),
                      child: Text(l10n.doctorFilesEmpty),
                    ),
                  ],
                )
              : ListView.separated(
                  itemCount: items.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final item = items[i];
                    final category = ReportCategory.fromWire(item.category);
                    return ListTile(
                      key: Key('file-${item.reportId}'),
                      leading: Icon(
                        item.openedAt == null
                            ? Icons.lock
                            : Icons.lock_open_outlined,
                      ),
                      title: Text(
                        [
                          item.trackingCode,
                          if (category != null) categoryLabel(l10n, category),
                        ].join(' · '),
                      ),
                      subtitle: Text(
                        '${dateTimeLabel(context, item.receivedAt)} · '
                        '${viaLabel(l10n, item.via)}',
                      ),
                      onTap: () => _open(context, ref, item),
                    );
                  },
                ),
        ),
      ),
    );
  }
}
