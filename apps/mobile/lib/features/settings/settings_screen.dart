import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/push/push_controller.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/directional_icons.dart';
import '../../core/ui/emergency_action.dart';
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
    final theme = Theme.of(context);
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
        actions: const [EmergencyNumbersAction()],
      ),
      body: ListView(
        padding: const EdgeInsets.only(bottom: 96),
        children: [
          _Header(l10n.settingsLanguage),
          RadioGroup<String>(
            groupValue: settings.locale.languageCode,
            onChanged: (v) {
              if (v != null) ref.read(settingsProvider.notifier).setLanguage(v);
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
          const Divider(),
          _Header(l10n.settingsTheme),
          RadioGroup<ThemeMode>(
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
          const Divider(),
          _Header(l10n.settingsAlerts),
          const _LocationAlertsTile(),
          ListTile(
            key: const Key('settings-notifications'),
            leading: const Icon(Icons.notifications_outlined),
            title: Text(l10n.notificationsTitle),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push(Routes.notifications),
          ),
          ListTile(
            leading: const Icon(Icons.health_and_safety),
            title: Text(l10n.tipsTitle),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push(Routes.tips),
          ),
          const Divider(),
          _Header(l10n.settingsIdentity),
          ListTile(
            leading: Icon(
              identity.isAnonymous ? Icons.visibility_off : Icons.verified_user,
            ),
            title: Text(identityText),
            subtitle: Text(roleText),
          ),
          if (identity.isAnonymous)
            ListTile(
              leading: const Icon(Icons.person_add),
              title: Text(l10n.settingsRegister),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => runLogin(context, ref, register: true),
            ),
          if (identity.isAnonymous)
            ListTile(
              leading: const Icon(DirectionalIcons.login),
              title: Text(l10n.citizenLogin),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => runLogin(context, ref),
            ),
          if (identity.isRegistered && identity.role == UserRole.citizen)
            ListTile(
              leading: const Icon(Icons.badge),
              title: Text(l10n.settingsProfile),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push(Routes.profile),
            ),
          if (identity.isRegistered && identity.role == UserRole.citizen)
            ListTile(
              key: const Key('settings-volunteer'),
              leading: const Icon(Icons.volunteer_activism),
              title: Text(l10n.volunteerTitle),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push(Routes.volunteer),
            ),
          if (identity.isRegistered && orgs.isNotEmpty)
            ListTile(
              key: const Key('settings-institution'),
              leading: const Icon(Icons.apartment),
              title: Text(l10n.myInstitutionTitle),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => openMyInstitution(context, orgs),
            ),
          if (identity.isRegistered)
            ListTile(
              key: const Key('settings-logout'),
              leading: Icon(
                DirectionalIcons.logout,
                color: theme.colorScheme.error,
              ),
              title: Text(l10n.settingsLogout),
              onTap: () => _logout(context, ref),
            ),
          ListTile(
            leading: const Icon(Icons.swap_horiz),
            title: Text(l10n.changeRole),
            trailing: const Icon(Icons.chevron_right),
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
            const Divider(),
            _Header(l10n.settingsSosReportAs),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
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
          const Divider(),
          ListTile(
            leading: const Icon(Icons.privacy_tip),
            title: Text(l10n.settingsCharter),
            trailing: const Icon(Icons.chevron_right),
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
    return SwitchListTile(
      key: const Key('settings-location-alerts'),
      secondary: const Icon(Icons.my_location),
      title: Text(l10n.settingsLocationAlerts),
      subtitle: Text(l10n.settingsLocationAlertsHelp),
      value: _on,
      onChanged: _set,
    );
  }
}

class _Header extends StatelessWidget {
  const _Header(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsetsDirectional.fromSTEB(16, 16, 16, 4),
    child: Semantics(
      header: true,
      child: Text(
        text,
        style: Theme.of(context).textTheme.titleSmall
            ?.copyWith(color: Theme.of(context).colorScheme.primary),
      ),
    ),
  );
}
