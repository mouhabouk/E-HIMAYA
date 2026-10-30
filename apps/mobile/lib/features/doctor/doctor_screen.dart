import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/crypto/medical_crypto.dart';
import '../../core/http/availability_models.dart';
import '../../core/http/doctor_models.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../onboarding/login_actions.dart';
import '../profile/profile_screen.dart';
import '../volunteer/volunteer_screen.dart';
import 'doctor_key.dart';
import 'doctor_labels.dart';
import 'doctor_providers.dart';

/// Doctors' space of the app (phase C1-a, docs/phase-c/design-medical-axis.md §2): a registered
/// citizen declares themselves a volunteer doctor or a Civil Protection doctor, waits for the
/// check of their registration, then shows their availability and finds colleagues.
class DoctorScreen extends ConsumerWidget {
  const DoctorScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final identity = ref.watch(identityProvider);
    final doctor = ref.watch(doctorProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.doctorTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: !identity.isRegistered
          ? ListView(
              padding: const EdgeInsets.all(24),
              children: [
                const Icon(Icons.medical_services, size: 56),
                const SizedBox(height: 16),
                Text(l10n.doctorIntro, textAlign: TextAlign.center),
                const SizedBox(height: 16),
                Text(
                  l10n.errorRegistrationRequired,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => runLogin(context, ref, register: true),
                  child: Text(l10n.citizenRegister),
                ),
              ],
            )
          : RefreshIndicator(
              onRefresh: () => ref.read(doctorProvider.notifier).reload(),
              child: doctor.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    Text(errorMessageFor(l10n, e)),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => ref.invalidate(doctorProvider),
                      child: Text(l10n.actionRetry),
                    ),
                  ],
                ),
                data: (d) => d == null ? const _Intro() : _Space(doctor: d),
              ),
            ),
    );
  }
}

/// The two doctor roles, each opening the form with its kind chosen.
class _Intro extends StatelessWidget {
  const _Intro();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    Widget choice(DoctorKind kind, IconData icon, String help) => NavCard(
      key: Key('doctor-choose-${kind.wire}'),
      icon: icon,
      tone: Tone.purple,
      title: doctorKindLabel(l10n, kind),
      subtitle: help,
      onTap: () => context.push('${Routes.doctorApply}?kind=${kind.wire}'),
    );
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        const Icon(Icons.medical_services, size: 56),
        const SizedBox(height: 16),
        Text(l10n.doctorIntro, textAlign: TextAlign.center),
        const SizedBox(height: 16),
        Text(l10n.doctorChoose, style: theme.textTheme.titleMedium),
        const SizedBox(height: 8),
        choice(
          DoctorKind.volunteer,
          Icons.volunteer_activism,
          l10n.doctorKindVolunteerHelp,
        ),
        choice(
          DoctorKind.civilProtection,
          Icons.local_hospital,
          l10n.doctorKindCivilProtectionHelp,
        ),
      ],
    );
  }
}

class _Space extends ConsumerWidget {
  const _Space({required this.doctor});

  final Doctor doctor;

  Future<void> _withdraw(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.doctorWithdraw),
        content: Text(l10n.doctorWithdrawConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('doctor-withdraw-confirm'),
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.doctorWithdraw),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(doctorProvider.notifier).withdraw();
      // The server dropped the key and every copy locked for it.
      await ref.read(doctorKeyProvider.notifier).forget();
    } on Object catch (e) {
      if (context.mounted) showVolunteerError(context, e);
    }
  }

  static String _statusHelp(AppLocalizations l10n, VolunteerStatus s) =>
      switch (s) {
        VolunteerStatus.pending => l10n.doctorHelpPending,
        VolunteerStatus.approved => l10n.doctorHelpApproved,
        VolunteerStatus.rejected => l10n.doctorHelpRejected,
        VolunteerStatus.suspended => l10n.doctorHelpSuspended,
        VolunteerStatus.withdrawn => l10n.doctorHelpWithdrawn,
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final d = doctor;
    final gouvernorat = ref
        .watch(gouvernoratsProvider)
        .value
        ?.where((g) => g.code == d.gouvernoratCode)
        .firstOrNull;
    final approved = d.status == VolunteerStatus.approved;
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        doctorKindLabel(l10n, d.kind),
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                    Chip(
                      key: const Key('doctor-status'),
                      label: Text(volunteerStatusLabel(l10n, d.status)),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(_statusHelp(l10n, d.status)),
                if (d.reviewReason != null &&
                    (d.status == VolunteerStatus.rejected ||
                        d.status == VolunteerStatus.suspended)) ...[
                  const SizedBox(height: 8),
                  Text(
                    l10n.volunteerReason(d.reviewReason!),
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ],
                const Divider(height: 24),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    for (final s in d.specialties)
                      Chip(label: Text(specialtyLabel(l10n, s))),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  [d.workplace, ?gouvernorat?.name].join(' · '),
                  key: const Key('doctor-workplace'),
                ),
                if (d.cpUnit != null) Text(d.cpUnit!),
              ],
            ),
          ),
        ),
        if (approved && d.committeeUntil != null) ...[
          const SizedBox(height: 8),
          Card(
            key: const Key('doctor-committee'),
            child: ListTile(
              leading: const Icon(Icons.verified_user),
              title: Text(
                l10n.doctorCommitteeMember(
                  dateTimeLabel(context, d.committeeUntil!),
                ),
              ),
              subtitle: Text(l10n.doctorCommitteeHelp),
            ),
          ),
        ],
        if (approved) ...[
          const SizedBox(height: 8),
          _AvailabilityCard(doctor: d),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('doctor-directory'),
            icon: const Icon(Icons.groups),
            label: Text(l10n.doctorDirectory),
            onPressed: () => context.push(Routes.doctorDirectory),
          ),
          const SizedBox(height: 8),
          _KeyCard(doctor: d),
        ],
        if (d.status != VolunteerStatus.withdrawn) ...[
          const SizedBox(height: 8),
          NavCard(
            key: const Key('doctor-availability'),
            icon: Icons.calendar_month_rounded,
            tone: Tone.teal,
            title: l10n.availabilityTitle,
            subtitle: l10n.availabilityDesc,
            onTap: () => context.push(Routes.availability(CalendarRole.doctor)),
          ),
        ],
        const SizedBox(height: 16),
        if (d.status != VolunteerStatus.withdrawn)
          OutlinedButton.icon(
            key: const Key('doctor-edit'),
            icon: const Icon(Icons.edit),
            label: Text(l10n.doctorEdit),
            onPressed: () => context.push(Routes.doctorApply),
          )
        else
          FilledButton.icon(
            key: const Key('doctor-reapply'),
            icon: const Icon(Icons.how_to_reg),
            label: Text(l10n.doctorApply),
            onPressed: () => context.push(Routes.doctorApply),
          ),
        if (d.status != VolunteerStatus.withdrawn) ...[
          const SizedBox(height: 8),
          TextButton(
            key: const Key('doctor-withdraw'),
            onPressed: () => _withdraw(context, ref),
            child: Text(l10n.doctorWithdraw),
          ),
        ],
      ],
    );
  }
}

/// Availability: available doctors come first in the referral list; it ends by itself.
class _AvailabilityCard extends ConsumerStatefulWidget {
  const _AvailabilityCard({required this.doctor});

  final Doctor doctor;

  @override
  ConsumerState<_AvailabilityCard> createState() => _AvailabilityCardState();
}

class _AvailabilityCardState extends ConsumerState<_AvailabilityCard> {
  bool _busy = false;

  Future<void> _set(bool on) async {
    setState(() => _busy = true);
    try {
      await ref.read(doctorProvider.notifier).setAvailable(on);
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final d = widget.doctor;
    final available = d.isAvailableAt(ref.watch(clockProvider)());
    return Card(
      child: SwitchListTile(
        key: const Key('doctor-available'),
        value: available,
        onChanged: _busy ? null : _set,
        title: Text(l10n.doctorAvailable),
        subtitle: Text(
          available && d.availableUntil != null
              ? l10n.doctorAvailableUntil(
                  dateTimeLabel(context, d.availableUntil!),
                )
              : l10n.doctorAvailableHelp,
        ),
      ),
    );
  }
}

/// Phase C1-b: the doctor's personal key, protected by a code they choose, then their files.
class _KeyCard extends ConsumerStatefulWidget {
  const _KeyCard({required this.doctor});

  final Doctor doctor;

  @override
  ConsumerState<_KeyCard> createState() => _KeyCardState();
}

class _KeyCardState extends ConsumerState<_KeyCard> {
  bool _busy = false;

  static final _codeFormat = RegExp(r'^[0-9]{6,12}$');

  /// Asks for the code ([confirm]: twice, for a new key).
  Future<String?> _askCode({required bool confirm}) {
    final l10n = AppLocalizations.of(context);
    final code = TextEditingController();
    final again = TextEditingController();
    String? error;
    return showDialog<String>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialog) => AlertDialog(
          title: Text(
            confirm ? l10n.doctorKeyChooseCode : l10n.doctorKeyEnterCode,
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (confirm) Text(l10n.doctorKeyCodeHint),
              TextField(
                key: const Key('doctor-code'),
                controller: code,
                obscureText: true,
                keyboardType: TextInputType.number,
                maxLength: 12,
                decoration: InputDecoration(labelText: l10n.doctorKeyCode),
              ),
              if (confirm)
                TextField(
                  key: const Key('doctor-code-again'),
                  controller: again,
                  obscureText: true,
                  keyboardType: TextInputType.number,
                  maxLength: 12,
                  decoration: InputDecoration(
                    labelText: l10n.doctorKeyCodeAgain,
                  ),
                ),
              if (error != null)
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(l10n.actionCancel),
            ),
            FilledButton(
              key: const Key('doctor-code-ok'),
              onPressed: () {
                final value = code.text.trim();
                if (!_codeFormat.hasMatch(value)) {
                  setDialog(() => error = l10n.doctorKeyCodeInvalid);
                } else if (confirm && again.text.trim() != value) {
                  setDialog(() => error = l10n.doctorKeyCodeMismatch);
                } else {
                  Navigator.pop(context, value);
                }
              },
              child: Text(l10n.actionContinue),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _run(
    Future<void> Function(String code) action, {
    required bool confirm,
  }) async {
    final l10n = AppLocalizations.of(context);
    final code = await _askCode(confirm: confirm);
    if (code == null || !mounted) return;
    setState(() => _busy = true);
    try {
      await action(code);
    } on WrongCodeException {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(l10n.doctorKeyWrongCode)));
      }
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _reset() async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.doctorKeyForgot),
        content: Text(l10n.doctorKeyResetWarning),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('doctor-key-reset-confirm'),
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.doctorKeyNew),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await _run(ref.read(doctorKeyProvider.notifier).create, confirm: true);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final local = ref.watch(doctorKeyProvider).value;
    final keys = ref.read(doctorKeyProvider.notifier);
    final ready = widget.doctor.hasKey && local != null;
    return Card(
      key: const Key('doctor-key'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(ready ? Icons.key : Icons.key_off),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.doctorKeyTitle,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              ready
                  ? l10n.doctorKeyReady
                  : widget.doctor.hasKey
                  ? l10n.doctorKeyRestoreHelp
                  : l10n.doctorKeyCreateHelp,
            ),
            const SizedBox(height: 12),
            if (_busy)
              const Center(child: CircularProgressIndicator())
            else if (ready)
              FilledButton.icon(
                key: const Key('doctor-files'),
                icon: const Icon(Icons.folder_shared),
                label: Text(l10n.doctorFiles),
                onPressed: () => context.push(Routes.doctorFiles),
              )
            else if (widget.doctor.hasKey) ...[
              FilledButton.icon(
                key: const Key('doctor-key-restore'),
                icon: const Icon(Icons.lock_open),
                label: Text(l10n.doctorKeyRestore),
                onPressed: () => _run(keys.restore, confirm: false),
              ),
              TextButton(
                key: const Key('doctor-key-reset'),
                onPressed: _reset,
                child: Text(l10n.doctorKeyForgot),
              ),
            ] else
              FilledButton.icon(
                key: const Key('doctor-key-create'),
                icon: const Icon(Icons.vpn_key),
                label: Text(l10n.doctorKeyCreate),
                onPressed: () => _run(keys.create, confirm: true),
              ),
          ],
        ),
      ),
    );
  }
}
