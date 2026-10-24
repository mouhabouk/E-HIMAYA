import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/crypto/medical_crypto.dart';
import '../../core/http/doctor_models.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../safety/medical_screen.dart';
import '../safety/safety_models.dart';
import 'doctor_key.dart';
import 'doctor_labels.dart';
import 'doctor_providers.dart';
import 'referral_screen.dart';

/// A locked file opened on this phone (phase C1-b), with what phase C1-c adds around it: the
/// opinions locked for this doctor, the referrals (gouvernorat group and committee), and the
/// specialist's own opinion. Nothing here is ever sent to the server in clear.
class OpenedFileScreen extends ConsumerStatefulWidget {
  const OpenedFileScreen({
    super.key,
    required this.item,
    required this.file,
    required this.opened,
    required this.doctorKey,
  });

  final MedicalInboxItem item;
  final MedicalFile file;

  /// The doctor's copy as `POST …/open` returned it (its key opens again on this phone).
  final Map<String, Object?> opened;
  final DoctorKeyPair doctorKey;

  @override
  ConsumerState<OpenedFileScreen> createState() => _OpenedFileScreenState();
}

class _OpenedFileScreenState extends ConsumerState<OpenedFileScreen> {
  bool _busy = false;

  String get _reportId => widget.item.reportId;
  bool get _specialist => widget.item.via == FileVia.referral;

  void _snack(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  Future<void> _refer() async {
    final crypto = ref.read(medicalCryptoProvider);
    final dek = await crypto.unwrap(widget.opened, widget.doctorKey);
    if (!mounted) return;
    final done = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ReferralScreen(reportId: _reportId, fileKey: dek),
      ),
    );
    if (done == true && mounted) {
      ref.invalidate(fileReferralsProvider(_reportId));
      _snack(AppLocalizations.of(context).doctorReferDone);
    }
  }

  Future<void> _writeOpinion() async {
    final l10n = AppLocalizations.of(context);
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.doctorOpinionWrite),
        content: TextField(
          key: const Key('opinion-text'),
          controller: controller,
          maxLength: 4000,
          minLines: 4,
          maxLines: 10,
          autofocus: true,
          decoration: InputDecoration(helperText: l10n.doctorOpinionHint),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('opinion-send'),
            onPressed: () {
              final t = controller.text.trim();
              if (t.length >= 3) Navigator.pop(context, t);
            },
            child: Text(l10n.doctorOpinionSend),
          ),
        ],
      ),
    );
    if (text == null || !mounted) return;
    setState(() => _busy = true);
    try {
      final api = ref.read(apiProvider);
      final readers = await api.opinionRecipients(_reportId);
      final locked = await ref.read(medicalCryptoProvider).lock({
        'text': text,
      }, readers);
      await api.addOpinion(_reportId, locked);
      ref.invalidate(fileOpinionsProvider(_reportId));
      if (mounted) _snack(l10n.doctorOpinionSent);
    } on Object catch (e) {
      if (mounted) _snack(errorMessageFor(l10n, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final opinions = ref.watch(fileOpinionsProvider(_reportId));
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.item.trackingCode),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            medicalText(l10n, widget.file),
            key: const Key('file-text'),
            style: theme.textTheme.titleMedium,
          ),
          const SizedBox(height: 16),
          Text(l10n.doctorFileConfidential, style: theme.textTheme.bodySmall),
          const Divider(height: 32),
          Text(l10n.doctorOpinions, style: theme.textTheme.titleSmall),
          const SizedBox(height: 8),
          opinions.when(
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text(errorMessageFor(l10n, e)),
            data: (list) => list.isEmpty
                ? Text(l10n.doctorOpinionsEmpty, key: const Key('no-opinion'))
                : Column(
                    children: [
                      for (final o in list)
                        _OpinionCard(opinion: o, doctorKey: widget.doctorKey),
                    ],
                  ),
          ),
          if (_specialist) ...[
            const SizedBox(height: 12),
            FilledButton.icon(
              key: const Key('write-opinion'),
              onPressed: _busy ? null : _writeOpinion,
              icon: const Icon(Icons.rate_review_outlined),
              label: Text(l10n.doctorOpinionWrite),
            ),
          ] else ...[
            const Divider(height: 32),
            Text(l10n.doctorReferrals, style: theme.textTheme.titleSmall),
            ref
                .watch(fileReferralsProvider(_reportId))
                .when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text(errorMessageFor(l10n, e)),
                  data: (list) => Column(
                    children: [
                      for (final r in list)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.forward_to_inbox),
                          title: Text(r.fullName ?? '—'),
                          subtitle: Text(
                            [
                              r.specialties
                                  .map((s) => specialtyLabel(l10n, s))
                                  .join('، '),
                              r.workplace,
                              dateTimeLabel(context, r.at),
                              if (r.mine) l10n.doctorReferralsMine,
                            ].join(' · '),
                          ),
                        ),
                    ],
                  ),
                ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('refer'),
              onPressed: _busy ? null : _refer,
              icon: const Icon(Icons.forward_to_inbox),
              label: Text(l10n.doctorRefer),
            ),
          ],
        ],
      ),
    );
  }
}

/// One opinion, opened on the phone when shown.
class _OpinionCard extends ConsumerStatefulWidget {
  const _OpinionCard({required this.opinion, required this.doctorKey});

  final LockedOpinion opinion;
  final DoctorKeyPair doctorKey;

  @override
  ConsumerState<_OpinionCard> createState() => _OpinionCardState();
}

class _OpinionCardState extends ConsumerState<_OpinionCard> {
  late final Future<Map<String, Object?>> _text = ref
      .read(medicalCryptoProvider)
      .open(widget.opinion.copy, widget.doctorKey);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final opinion = widget.opinion;
    final specialty = opinion.specialty;
    final who = opinion.mine
        ? l10n.doctorOpinionMine
        : l10n.doctorOpinionBy(
            specialty == null ? '—' : specialtyLabel(l10n, specialty),
          );
    return Card(
      key: Key('opinion-${opinion.id}'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$who · ${dateTimeLabel(context, opinion.createdAt)}',
              style: Theme.of(context).textTheme.labelMedium,
            ),
            const SizedBox(height: 6),
            FutureBuilder<Map<String, Object?>>(
              future: _text,
              builder: (context, snap) => snap.hasError
                  ? Text(l10n.doctorOpinionCannotOpen)
                  : snap.hasData
                  ? Text(
                      '${snap.data!['text'] ?? ''}',
                      key: Key('opinion-text-${opinion.id}'),
                    )
                  : const LinearProgressIndicator(),
            ),
          ],
        ),
      ),
    );
  }
}
