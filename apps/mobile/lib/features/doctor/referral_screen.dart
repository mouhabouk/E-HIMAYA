import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/doctor_models.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../profile/profile_screen.dart';
import 'doctor_key.dart';
import 'doctor_labels.dart';
import 'doctor_providers.dart';

/// Referral of an opened file to specialists (phase C1-c, design §13.1): the specialty, then the
/// gouvernorat, then doctors of the directory, and a short reason. The file key is locked on this
/// phone for each chosen doctor's public key; pops `true` once sent.
class ReferralScreen extends ConsumerStatefulWidget {
  const ReferralScreen({
    super.key,
    required this.reportId,
    required this.fileKey,
  });

  final String reportId;

  /// The file key (DEK), opened on this phone from the doctor's own copy.
  final List<int> fileKey;

  /// Server cap per file.
  static const maxReferrals = 5;

  @override
  ConsumerState<ReferralScreen> createState() => _ReferralScreenState();
}

class _ReferralScreenState extends ConsumerState<ReferralScreen> {
  DoctorSpecialty? _specialty;
  int? _gouvernorat;
  final _chosen = <String, DirectoryDoctor>{};
  final _reason = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  bool get _ready =>
      _chosen.isNotEmpty && _reason.text.trim().length >= 3 && !_sending;

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _sending = true);
    try {
      final keys = await ref.read(medicalCryptoProvider).wrap(widget.fileKey, {
        for (final d in _chosen.values) d.id: base64.decode(d.publicKey!),
      });
      await ref
          .read(apiProvider)
          .referMedicalFile(
            widget.reportId,
            reason: _reason.text.trim(),
            keys: keys,
          );
      if (mounted) Navigator.of(context).pop(true);
    } on Object catch (e) {
      if (!mounted) return;
      setState(() => _sending = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(errorMessageFor(l10n, e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final gouvernorats = ref.watch(gouvernoratsProvider).value ?? const [];
    final names = {for (final g in gouvernorats) g.code: g.name};
    final specialty = _specialty;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.doctorReferTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l10n.doctorReferHint),
          const SizedBox(height: 12),
          DropdownButtonFormField<DoctorSpecialty>(
            key: const Key('referral-specialty'),
            initialValue: _specialty,
            isExpanded: true,
            decoration: InputDecoration(labelText: l10n.doctorSpecialty),
            items: [
              for (final s in DoctorSpecialty.values)
                DropdownMenuItem(
                  value: s,
                  child: Text(specialtyLabel(l10n, s)),
                ),
            ],
            onChanged: (v) => setState(() {
              _specialty = v;
              _chosen.clear();
            }),
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<int?>(
            key: const Key('referral-gouvernorat'),
            initialValue: _gouvernorat,
            isExpanded: true,
            decoration: InputDecoration(labelText: l10n.doctorRegion),
            items: [
              DropdownMenuItem(child: Text(l10n.doctorAllGouvernorats)),
              for (final g in gouvernorats)
                DropdownMenuItem(value: g.code, child: Text(g.name)),
            ],
            onChanged: (v) => setState(() => _gouvernorat = v),
          ),
          const SizedBox(height: 8),
          if (specialty == null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Text(l10n.doctorReferPickSpecialty),
            )
          else
            ref
                .watch(
                  doctorDirectoryProvider((
                    specialty: specialty,
                    gouvernorat: _gouvernorat,
                  )),
                )
                .when(
                  loading: () => const LinearProgressIndicator(),
                  error: (e, _) => Text(errorMessageFor(l10n, e)),
                  data: (list) => list.isEmpty
                      ? Padding(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          child: Text(l10n.doctorDirectoryEmpty),
                        )
                      : Column(
                          children: [
                            for (final d in list)
                              CheckboxListTile(
                                key: Key('referral-${d.id}'),
                                contentPadding: EdgeInsets.zero,
                                value: _chosen.containsKey(d.id),
                                onChanged:
                                    d.publicKey == null ||
                                        (!_chosen.containsKey(d.id) &&
                                            _chosen.length >=
                                                ReferralScreen.maxReferrals)
                                    ? null
                                    : (v) => setState(
                                        () => v == true
                                            ? _chosen[d.id] = d
                                            : _chosen.remove(d.id),
                                      ),
                                title: Text(d.fullName ?? '—'),
                                subtitle: Text(
                                  [
                                    [
                                      d.workplace,
                                      ?names[d.gouvernoratCode],
                                    ].join(' · '),
                                    if (d.publicKey == null)
                                      l10n.doctorReferNoKey
                                    else if (d.available)
                                      l10n.doctorAvailableBadge,
                                  ].join('\n'),
                                ),
                              ),
                          ],
                        ),
                ),
          const SizedBox(height: 8),
          TextField(
            key: const Key('referral-reason'),
            controller: _reason,
            maxLength: 500,
            decoration: InputDecoration(labelText: l10n.doctorReferReason),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            key: const Key('referral-send'),
            onPressed: _ready ? _send : null,
            icon: const Icon(Icons.lock_outline),
            label: Text(
              _chosen.isEmpty
                  ? l10n.doctorReferSend
                  : '${l10n.doctorReferSend} (${_chosen.length})',
            ),
          ),
        ],
      ),
    );
  }
}
