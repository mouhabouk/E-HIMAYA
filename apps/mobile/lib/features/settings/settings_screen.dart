import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/power/battery_saver.dart';
import '../../core/power/scheduling.dart';
import '../../core/push/push_controller.dart';
import '../../core/push/push_simulation_banner.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/components.dart';
import '../../core/ui/directional_icons.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alerts_providers.dart';
import '../charter/charter_controller.dart';
import '../institution/institution_providers.dart';
import '../institution/my_institution_screen.dart';
import '../institution/report_as_selector.dart';
import '../onboarding/login_actions.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  static String languageName(AppLocalizations l10n, String code) =>
      switch (code) {
        'fr' => l10n.languageFrench,
        'en' => l10n.languageEnglish,
        _ => l10n.languageArabic,
      };

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.logoutConfirmTitle),
        content: Text(l10n.logoutConfirmBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.settingsLogout),
          ),
        ],
      ),
    );
    if (ok != true) return;
    // While the session still proves whose phone it is.
    await ref.read(deviceRegistrarProvider).unregister();
    await ref.read(profilePromptedProvider.notifier).reset();
    await ref.read(identityProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final settings = ref.watch(settingsProvider);
    final identity = ref.watch(identityProvider);
    final name = identity.session?.displayName;
    final identityText = switch (identity.mode) {
      IdentityMode.anonymous => l10n.identityAnonymous,
      IdentityMode.registered =>
        name == null
            ? l10n.identityRegistered
            : l10n.identityRegisteredAs(name),
      IdentityMode.none => l10n.identityNone,
    };
    final orgs = identity.isRegistered
        ? ref.watch(myOrgsProvider).value ?? const <MyOrg>[]
        : const <MyOrg>[];
    final activeOrgs = ref.watch(activeOrgsProvider);
    final roleText = identity.role == UserRole.institution
        ? l10n.roleInstitution
        : l10n.roleCitizen;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.settingsTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 96),
        children: [
          const PushSimulationBanner(),
          SectionTitle(l10n.settingsLanguage),
          AppCard(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: RadioGroup<String>(
              groupValue: settings.locale.languageCode,
              onChanged: (v) {
                if (v != null) {
                  ref.read(settingsProvider.notifier).setLanguage(v);
                }
              },
              child: Column(
                children: [
                  for (final code in supportedLanguageCodes)
                    RadioListTile<String>(
                      key: Key('language-$code'),
                      value: code,
                      title: Text(languageName(l10n, code)),
                    ),
                ],
              ),
            ),
          ),
          SectionTitle(l10n.settingsTheme),
          AppCard(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: RadioGroup<ThemeMode>(
              groupValue: settings.themeMode,
              onChanged: (v) {
                if (v != null) {
                  ref.read(settingsProvider.notifier).setThemeMode(v);
                }
              },
              child: Column(
                children: [
                  RadioListTile(
                    value: ThemeMode.system,
                    title: Text(l10n.themeSystem),
                  ),
                  RadioListTile(
                    value: ThemeMode.light,
                    title: Text(l10n.themeLight),
                  ),
                  RadioListTile(
                    value: ThemeMode.dark,
                    title: Text(l10n.themeDark),
                  ),
                ],
              ),
            ),
          ),
          // Phase A: colour palette (the logo's colours by default).
          SectionTitle(l10n.settingsColors),
          AppCard(
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (palette, label, color) in [
                  (AppPalette.office, l10n.colorOffice, BrandColors.blue),
                  (AppPalette.red, l10n.colorRed, const Color(0xFFB3261E)),
                  (AppPalette.blue, l10n.colorBlue, const Color(0xFF1565C0)),
                  (AppPalette.green, l10n.colorGreen, const Color(0xFF2E7D32)),
                ])
                  ChoiceChip(
                    key: Key('palette-${palette.name}'),
                    avatar: CircleAvatar(backgroundColor: color, radius: 8),
                    label: Text(label),
                    selected: settings.palette == palette,
                    onSelected: (_) =>
                        ref.read(settingsProvider.notifier).setPalette(palette),
                  ),
              ],
            ),
          ),
          SectionTitle(l10n.settingsAlerts),
          const _LocationAlertsTile(),
          NavCard(
            key: const Key('settings-notifications'),
            icon: Icons.notifications_rounded,
            tone: Tone.sky,
            title: l10n.notificationsTitle,
            onTap: () => context.push(Routes.notifications),
          ),
          NavCard(
            key: const Key('settings-alert-check'),
            icon: Icons.notifications_active_rounded,
            tone: Tone.sky,
            title: l10n.alertCheckTitle,
            subtitle: l10n.alertCheckSubtitle,
            onTap: () => context.push(Routes.alertCheck),
          ),
          NavCard(
            key: const Key('settings-accessibility'),
            icon: Icons.accessibility_new_rounded,
            tone: Tone.navy,
            title: l10n.a11yTitle,
            subtitle: l10n.a11ySubtitle,
            onTap: () => context.push(Routes.accessibility),
          ),
          const _BatterySaverTile(),
          NavCard(
            key: const Key('settings-safety'),
            icon: Icons.shield_rounded,
            tone: Tone.green,
            title: l10n.safetyTitle,
            subtitle: l10n.safetySettingsHint,
            onTap: () => context.push(Routes.safety),
          ),
          NavCard(
            key: const Key('settings-tips'),
            icon: Icons.health_and_safety_rounded,
            tone: Tone.green,
            title: l10n.tipsTitle,
            onTap: () => context.push(Routes.tips),
          ),
          NavCard(
            key: const Key('settings-contact'),
            icon: Icons.mail_rounded,
            tone: Tone.navy,
            title: l10n.contactTitle,
            subtitle: l10n.contactMineTitle,
            onTap: () => context.push(Routes.contact),
          ),
          // Phase P5b (F-APP-143).
          NavCard(
            key: const Key('settings-rate'),
            icon: Icons.star_rounded,
            tone: Tone.amber,
            title: l10n.rateTitle,
            subtitle: l10n.rateSubtitle,
            onTap: () => context.push(Routes.rateApp),
          ),
          NavCard(
            key: const Key('settings-intro'),
            icon: Icons.slideshow_rounded,
            tone: Tone.purple,
            title: l10n.introReplayTitle,
            subtitle: l10n.introReplaySubtitle,
            onTap: () => context.push(Routes.introReplay),
          ),
          SectionTitle(l10n.settingsIdentity),
          NavCard(
            key: const Key('settings-identity'),
            icon: identity.isAnonymous
                ? Icons.visibility_off_rounded
                : Icons.verified_user_rounded,
            tone: Tone.navy,
            title: identityText,
            subtitle: roleText,
          ),
          if (identity.isAnonymous)
            NavCard(
              key: const Key('settings-register'),
              icon: Icons.person_add_rounded,
              tone: Tone.navy,
              title: l10n.settingsRegister,
              onTap: () => runLogin(context, ref, register: true),
            ),
          if (identity.isAnonymous)
            NavCard(
              key: const Key('settings-login'),
              icon: DirectionalIcons.login,
              tone: Tone.navy,
              title: l10n.citizenLogin,
              onTap: () => runLogin(context, ref),
            ),
          if (identity.isRegistered && identity.role == UserRole.citizen)
            NavCard(
              key: const Key('settings-profile'),
              icon: Icons.badge_rounded,
              tone: Tone.navy,
              title: l10n.settingsProfile,
              onTap: () => context.push(Routes.profile),
            ),
          if (identity.isRegistered && identity.role == UserRole.citizen)
            NavCard(
              key: const Key('settings-volunteer'),
              icon: Icons.volunteer_activism_rounded,
              tone: Tone.green,
              title: l10n.volunteerTitle,
              onTap: () => context.push(Routes.volunteer),
            ),
          if (identity.isRegistered && identity.role == UserRole.citizen)
            NavCard(
              key: const Key('settings-doctor'),
              icon: Icons.medical_services_rounded,
              tone: Tone.purple,
              title: l10n.doctorTitle,
              onTap: () => context.push(Routes.doctor),
            ),
          if (identity.hasIdentity && identity.role == UserRole.citizen)
            NavCard(
              key: const Key('settings-rewards'),
              icon: Icons.military_tech_rounded,
              tone: Tone.pink,
              title: l10n.rewardsTitle,
              onTap: () => context.push(Routes.rewards),
            ),
          if (identity.isRegistered && orgs.isNotEmpty)
            NavCard(
              key: const Key('settings-institution'),
              icon: Icons.apartment_rounded,
              tone: Tone.navy,
              title: l10n.myInstitutionTitle,
              onTap: () => openMyInstitution(context, orgs),
            ),
          if (identity.hasIdentity)
            NavCard(
              key: const Key('settings-my-data'),
              icon: Icons.folder_shared_rounded,
              tone: Tone.slate,
              title: l10n.myDataTitle,
              subtitle: l10n.myDataSubtitle,
              onTap: () => context.push(Routes.myData),
            ),
          if (identity.isRegistered)
            NavCard(
              key: const Key('settings-logout'),
              icon: DirectionalIcons.logout,
              tone: Tone.red,
              title: l10n.settingsLogout,
              onTap: () => _logout(context, ref),
            ),
          NavCard(
            key: const Key('settings-change-role'),
            icon: Icons.swap_horiz_rounded,
            tone: Tone.slate,
            title: l10n.changeRole,
            onTap: () async {
              if (identity.isRegistered) {
                await _logout(context, ref);
                if (ref.read(identityProvider).isRegistered) return;
              } else {
                await ref.read(deviceRegistrarProvider).unregister();
              }
              await ref.read(identityProvider.notifier).chooseRole(null);
            },
          ),
          if (activeOrgs.isNotEmpty) ...[
            SectionTitle(l10n.settingsSosReportAs),
            AppCard(
              child: ReportAsSelector(
                key: const Key('settings-sos-report-as'),
                title: l10n.settingsSosReportAsHint,
                orgs: activeOrgs,
                value: ref.watch(sosReportAsProvider),
                onChanged: (orgId) =>
                    ref.read(sosReportAsChoiceProvider.notifier).choose(orgId),
              ),
            ),
          ],
          const SizedBox(height: 10),
          NavCard(
            key: const Key('settings-charter'),
            icon: Icons.privacy_tip_rounded,
            tone: Tone.purple,
            title: l10n.settingsCharter,
            onTap: () => context.push(Routes.charterRead),
          ),
        ],
      ),
    );
  }
}

/// FR-A-061: alerts for the phone's current position (coarse, about 1 km), on by default.
class _LocationAlertsTile extends ConsumerStatefulWidget {
  const _LocationAlertsTile();

  @override
  ConsumerState<_LocationAlertsTile> createState() =>
      _LocationAlertsTileState();
}

class _LocationAlertsTileState extends ConsumerState<_LocationAlertsTile> {
  late bool _on = ref.read(appPrefsProvider).locationAlerts;

  Future<void> _set(bool on) async {
    if (on) {
      // Asked here, where the user expects it, never in the background.
      await ref.read(locationServiceProvider).ensurePermission();
    }
    await ref.read(appPrefsProvider).setLocationAlerts(on);
    if (!mounted) return;
    setState(() => _on = on);
    await ref.read(deviceRegistrarProvider).register();
    await ref.read(activeAlertsProvider.notifier).refresh();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return NavCard(
      icon: Icons.my_location_rounded,
      tone: Tone.sky,
      title: l10n.settingsLocationAlerts,
      subtitle: l10n.settingsLocationAlertsHelp,
      trailing: Switch(
        key: const Key('settings-location-alerts'),
        value: _on,
        onChanged: _set,
      ),
    );
  }
}

/// In-app battery saver: automatic (low battery), always on, or off.
class _BatterySaverTile extends ConsumerWidget {
  const _BatterySaverTile();

  static String modeLabel(AppLocalizations l10n, BatterySaverMode mode) =>
      switch (mode) {
        BatterySaverMode.auto => l10n.batterySaverAuto,
        BatterySaverMode.on => l10n.batterySaverOn,
        BatterySaverMode.off => l10n.batterySaverOff,
      };

  Future<void> _choose(
    BuildContext context,
    WidgetRef ref,
    BatterySaverMode current,
  ) async {
    final l10n = AppLocalizations.of(context);
    final chosen = await showDialog<BatterySaverMode>(
      context: context,
      builder: (context) => SimpleDialog(
        title: Text(l10n.batterySaverTitle),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(l10n.batterySaverHelp),
          ),
          RadioGroup<BatterySaverMode>(
            groupValue: current,
            onChanged: (v) => Navigator.pop(context, v),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final mode in BatterySaverMode.values)
                  RadioListTile<BatterySaverMode>(
                    key: Key('battery-saver-${mode.name}'),
                    value: mode,
                    title: Text(modeLabel(l10n, mode)),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
    if (chosen != null) {
      await ref.read(batterySaverProvider.notifier).setMode(chosen);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final saver = ref.watch(batterySaverProvider);
    final level = saver.reading?.level;
    final status = saver.active
        ? l10n.batterySaverActive
        : l10n.batterySaverInactive;
    return NavCard(
      key: const Key('settings-battery-saver'),
      icon: saver.active
          ? Icons.battery_saver_rounded
          : Icons.battery_std_rounded,
      tone: saver.active ? Tone.green : Tone.slate,
      title: l10n.batterySaverTitle,
      subtitle: [
        modeLabel(l10n, saver.mode),
        status,
        if (level != null) l10n.batteryLevel(level),
      ].join(' · '),
      onTap: () => _choose(context, ref, saver.mode),
    );
  }
}
