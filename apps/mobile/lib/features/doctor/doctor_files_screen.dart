import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/doctor_models.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/messenger.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../report/category_labels.dart';
import '../safety/safety_models.dart';
import 'doctor_key.dart';
import 'doctor_providers.dart';
import 'opened_file_screen.dart';

/// Phase C1-b: the medical files locked for this doctor (their gouvernorat, the medical
/// committee, or a referral in phase C1-c). Each file is opened on the phone with the doctor's
/// key; the opening is recorded, and a committee member gives a reason. A committee member also
/// sees the files waiting to be locked for a newly appointed member.
class DoctorFilesScreen extends ConsumerWidget {
  const DoctorFilesScreen({super.key});

  static String viaLabel(AppLocalizations l10n, FileVia via) => switch (via) {
    FileVia.gouvernorat => l10n.doctorFileViaGouvernorat,
    FileVia.committee => l10n.doctorFileViaCommittee,
    FileVia.referral => l10n.doctorFileViaReferral,
  };

  static Future<String?> askReason(BuildContext context, {String? hint}) {
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
          decoration: InputDecoration(
            helperText: hint ?? l10n.doctorFileReasonHint,
            helperMaxLines: 3,
          ),
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
      reason = await askReason(context);
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
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          fullscreenDialog: true,
          builder: (_) => OpenedFileScreen(
            item: item,
            file: file,
            opened: opened,
            doctorKey: key,
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
    final until = ref.watch(doctorProvider).value?.committeeUntil;
    final member = until != null && until.isAfter(DateTime.now());
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
                    if (member) const _PendingMembers(),
                    Padding(
                      key: const Key('files-empty'),
                      padding: const EdgeInsets.all(24),
                      child: Text(l10n.doctorFilesEmpty),
                    ),
                  ],
                )
              : ListView.separated(
                  itemCount: items.length + 1,
                  separatorBuilder: (_, i) => i == 0
                      ? const SizedBox.shrink()
                      : const Divider(height: 1),
                  itemBuilder: (context, i) {
                    if (i == 0) {
                      return member
                          ? const _PendingMembers()
                          : const SizedBox.shrink();
                    }
                    final item = items[i - 1];
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

/// Committee members appointed after files this member holds were locked (design §13.3): one
/// button opens each file and opinion on this phone and locks its key for them.
class _PendingMembers extends ConsumerStatefulWidget {
  const _PendingMembers();

  @override
  ConsumerState<_PendingMembers> createState() => _PendingMembersState();
}

class _PendingMembersState extends ConsumerState<_PendingMembers> {
  String? _busy;

  Future<void> _share(PendingMember m) async {
    final l10n = AppLocalizations.of(context);
    final reason = await DoctorFilesScreen.askReason(
      context,
      hint: l10n.doctorPendingReasonHint,
    );
    if (reason == null || !mounted) return;
    final key = await ref.read(doctorKeyProvider.future);
    if (key == null || !mounted) return;
    setState(() => _busy = m.doctorId);
    final api = ref.read(apiProvider);
    final crypto = ref.read(medicalCryptoProvider);
    final to = {m.doctorId: base64.decode(m.publicKey)};
    try {
      for (final reportId in m.files) {
        final opened = await api.openMedicalFile(reportId, reason: reason);
        final keys = await crypto.wrap(await crypto.unwrap(opened, key), to);
        await api.shareMedicalKey(
          reportId: reportId,
          reason: reason,
          keys: keys,
        );
      }
      for (final reportId in {...m.opinions.values}) {
        for (final o in await api.medicalOpinions(reportId)) {
          if (!m.opinions.containsKey(o.id)) continue;
          final keys = await crypto.wrap(await crypto.unwrap(o.copy, key), to);
          await api.shareMedicalKey(
            opinionId: o.id,
            reason: reason,
            keys: keys,
          );
        }
      }
      showRootMessage(l10n.doctorPendingDone, null);
    } on Object catch (e) {
      showRootMessage(errorMessageFor(l10n, e), null);
    } finally {
      ref.invalidate(committeePendingProvider);
      ref.invalidate(medicalFilesProvider);
      if (mounted) setState(() => _busy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final pending = ref.watch(committeePendingProvider).value ?? const [];
    if (pending.isEmpty) return const SizedBox.shrink();
    return Card(
      key: const Key('pending-members'),
      margin: const EdgeInsets.all(12),
      color: Theme.of(context).colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.doctorPendingTitle,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            for (final m in pending)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.group_add_outlined),
                title: Text(l10n.doctorPendingBody(m.count, m.fullName ?? '—')),
                trailing: _busy == m.doctorId
                    ? const SizedBox.square(
                        dimension: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : TextButton(
                        key: Key('pending-share-${m.doctorId}'),
                        onPressed: _busy == null ? () => _share(m) : null,
                        child: Text(l10n.doctorPendingShare),
                      ),
              ),
          ],
        ),
      ),
    );
  }
}
