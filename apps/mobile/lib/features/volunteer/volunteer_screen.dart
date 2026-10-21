import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/location/location_service.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../onboarding/login_actions.dart';
import '../settings/alert_check.dart';
import 'volunteer_providers.dart';

/// Shows [error] in a snack bar; offers the profile form when the server needs it completed.
void showVolunteerError(BuildContext context, Object error) {
  final l10n = AppLocalizations.of(context);
  final message = switch (error) {
    LocationUnavailable(availability: LocationAvailability.serviceDisabled) =>
      l10n.locationServiceDisabled,
    LocationUnavailable(availability: LocationAvailability.granted) =>
      l10n.volunteerNoFix,
    LocationUnavailable() => l10n.volunteerLocationDenied,
    _ => errorMessageFor(l10n, error),
  };
  final incomplete =
      error is ApiException && error.code == ApiErrorCode.profileIncomplete;
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message),
      action: incomplete
          ? SnackBarAction(
              label: l10n.settingsProfile,
              onPressed: () => context.push(Routes.profile),
            )
          : null,
    ),
  );
}

/// Volunteer space of the app (FR-A-020…023).
class VolunteerScreen extends ConsumerWidget {
  const VolunteerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final identity = ref.watch(identityProvider);
    final volunteer = ref.watch(volunteerProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.volunteerTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: !identity.isRegistered
          ? _RegistrationNeeded(
              onRegister: () => runLogin(context, ref, register: true),
            )
          : RefreshIndicator(
              onRefresh: () => ref.read(volunteerProvider.notifier).reload(),
              child: volunteer.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    Text(errorMessageFor(l10n, e)),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => ref.invalidate(volunteerProvider),
                      child: Text(l10n.actionRetry),
                    ),
                  ],
                ),
                data: (v) => v == null ? const _Intro() : _Space(volunteer: v),
              ),
            ),
    );
  }
}

class _RegistrationNeeded extends StatelessWidget {
  const _RegistrationNeeded({required this.onRegister});
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const Icon(Icons.volunteer_activism, size: 56),
        const SizedBox(height: 16),
        Text(l10n.volunteerIntro, textAlign: TextAlign.center),
        const SizedBox(height: 16),
        Text(l10n.errorRegistrationRequired, textAlign: TextAlign.center),
        const SizedBox(height: 16),
        FilledButton(onPressed: onRegister, child: Text(l10n.citizenRegister)),
      ],
    );
  }
}

class _Intro extends StatelessWidget {
  const _Intro();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      children: [
        const Icon(Icons.volunteer_activism, size: 56),
        const SizedBox(height: 16),
        Text(l10n.volunteerIntro, textAlign: TextAlign.center),
        const SizedBox(height: 24),
        FilledButton.icon(
          key: const Key('volunteer-apply'),
          icon: const Icon(Icons.how_to_reg),
          label: Text(l10n.volunteerApply),
          onPressed: () => context.push(Routes.volunteerApply),
        ),
      ],
    );
  }
}

class _Space extends ConsumerWidget {
  const _Space({required this.volunteer});

  final Volunteer volunteer;

  Future<void> _withdraw(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.volunteerWithdraw),
        content: Text(l10n.volunteerWithdrawConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.volunteerWithdraw),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(volunteerProvider.notifier).withdraw();
    } on Object catch (e) {
      if (context.mounted) showVolunteerError(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final v = volunteer;
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
                        l10n.volunteerApplication,
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                    Chip(
                      key: const Key('volunteer-status'),
                      label: Text(volunteerStatusLabel(l10n, v.status)),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(_statusHelp(l10n, v.status)),
                if (v.reviewReason != null &&
                    (v.status == VolunteerStatus.rejected ||
                        v.status == VolunteerStatus.suspended)) ...[
                  const SizedBox(height: 8),
                  Text(
                    l10n.volunteerReason(v.reviewReason!),
                    style: TextStyle(color: theme.colorScheme.error),
                  ),
                ],
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    for (final s in v.skills)
                      Chip(
                        label: Text(
                          s == VolunteerSkill.other && v.otherSkill != null
                              ? v.otherSkill!
                              : skillLabel(l10n, s),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  v.periodTo == null
                      ? l10n.volunteerPeriodFrom(
                          dateLabel(context, v.periodFrom),
                        )
                      : l10n.volunteerPeriodRange(
                          dateLabel(context, v.periodFrom),
                          dateLabel(context, v.periodTo!),
                        ),
                ),
                Text(
                  v.availability == VolunteerAvailability.continuous
                      ? l10n.availabilityContinuous
                      : l10n.availabilityIntermittent,
                ),
              ],
            ),
          ),
        ),
        if (v.status == VolunteerStatus.approved) ...[
          const SizedBox(height: 8),
          _ReadinessCard(volunteer: v),
          const SizedBox(height: 8),
          Card(
            child: ListTile(
              key: const Key('volunteer-callouts'),
              leading: const Icon(Icons.campaign, size: 32),
              title: Text(l10n.calloutsTitle),
              subtitle: Text(l10n.calloutsDesc),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push(Routes.callouts),
            ),
          ),
        ],
        const SizedBox(height: 16),
        OutlinedButton.icon(
          key: const Key('volunteer-edit'),
          icon: Icon(v.status.canResubmit ? Icons.how_to_reg : Icons.edit),
          label: Text(
            v.status.canResubmit ? l10n.volunteerResubmit : l10n.volunteerEdit,
          ),
          onPressed: () => context.push(Routes.volunteerApply),
        ),
        if (v.status != VolunteerStatus.withdrawn)
          TextButton.icon(
            key: const Key('volunteer-withdraw'),
            icon: Icon(Icons.logout, color: theme.colorScheme.error),
            label: Text(
              l10n.volunteerWithdraw,
              style: TextStyle(color: theme.colorScheme.error),
            ),
            onPressed: () => _withdraw(context, ref),
          ),
      ],
    );
  }

  static String _statusHelp(AppLocalizations l10n, VolunteerStatus s) =>
      switch (s) {
        VolunteerStatus.pending => l10n.volunteerPendingHelp,
        VolunteerStatus.approved => l10n.volunteerApprovedHelp,
        VolunteerStatus.rejected => l10n.volunteerRejectedHelp,
        VolunteerStatus.suspended => l10n.volunteerSuspendedHelp,
        VolunteerStatus.withdrawn => l10n.volunteerWithdrawnHelp,
      };
}

/// «جاهز للتدخل»: readiness with its duration; the position is shared only while ready.
class _ReadinessCard extends ConsumerStatefulWidget {
  const _ReadinessCard({required this.volunteer});
  final Volunteer volunteer;

  @override
  ConsumerState<_ReadinessCard> createState() => _ReadinessCardState();
}

class _ReadinessCardState extends ConsumerState<_ReadinessCard> {
  static const _durations = [2, 4, 8, 12, 24];
  int _hours = 8;
  bool _busy = false;

  /// The notice of phase 10 §4.2: what is shared, with whom and for how long. True when accepted.
  Future<bool> _askLocationConsent() async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        key: const Key('location-consent-dialog'),
        title: Text(l10n.locationConsentTitle),
        content: SingleChildScrollView(child: Text(l10n.locationConsentBody)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('location-consent-accept'),
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.locationConsentAccept),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return false;
    await ref
        .read(volunteerProvider.notifier)
        .giveLocationConsent(Localizations.localeOf(context).languageCode);
    return true;
  }

  Future<void> _consent(bool give) async {
    setState(() => _busy = true);
    try {
      if (give) {
        await _askLocationConsent();
      } else {
        await ref.read(volunteerProvider.notifier).withdrawLocationConsent();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                AppLocalizations.of(context).locationConsentWithdrawn,
              ),
            ),
          );
        }
      }
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _toggle(bool ready) async {
    setState(() => _busy = true);
    try {
      final controller = ref.read(volunteerProvider.notifier);
      if (ready) {
        // Phase 10 §4.2: the first readiness asks for the consent to share the position.
        if (!widget.volunteer.locationConsent && !await _askLocationConsent()) {
          return;
        }
        await controller.setReady(_hours);
        // On call: the one case where the app asks to leave battery optimisation.
        if (mounted) await maybeAskBatteryExemption(context, ref);
      } else {
        await controller.setNotReady();
      }
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final now = ref.watch(clockProvider)();
    final v = widget.volunteer;
    final ready = v.isReadyAt(now);
    final inPeriod = v.inPeriod(now);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SwitchListTile(
              key: const Key('volunteer-ready'),
              secondary: Icon(
                ready ? Icons.directions_run : Icons.bedtime,
                size: 32,
              ),
              title: Text(l10n.volunteerReady),
              subtitle: Text(
                ready && v.readyUntil != null
                    ? l10n.volunteerReadyUntil(
                        dateTimeLabel(context, v.readyUntil!),
                      )
                    : inPeriod
                    ? l10n.volunteerReadyHelp
                    : l10n.errorOutsidePeriod,
              ),
              value: ready,
              onChanged: _busy || (!ready && !inPeriod) ? null : _toggle,
            ),
            if (!ready && inPeriod)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Wrap(
                  spacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(l10n.volunteerReadyFor),
                    for (final h in _durations)
                      ChoiceChip(
                        key: Key('ready-hours-$h'),
                        label: Text(l10n.hoursShort(h)),
                        selected: _hours == h,
                        onSelected: (_) => setState(() => _hours = h),
                      ),
                  ],
                ),
              ),
            SwitchListTile(
              key: const Key('volunteer-location-consent'),
              secondary: const Icon(Icons.share_location, size: 32),
              title: Text(l10n.locationConsentSwitch),
              subtitle: Text(
                v.locationConsent
                    ? l10n.locationConsentSwitchOn
                    : l10n.locationConsentSwitchOff,
              ),
              value: v.locationConsent,
              onChanged: _busy ? null : _consent,
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Text(
                l10n.volunteerLocationPrivacy,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
