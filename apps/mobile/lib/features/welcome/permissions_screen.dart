import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/location/location_service.dart';
import '../../core/push/push_messaging.dart';
import '../../l10n/app_localizations.dart';
import 'welcome_controller.dart';
import 'welcome_scaffold.dart';

enum _PermState { unknown, granted, refused }

/// Permissions step (addition 4): each card says why, and what happens without. Location and
/// notifications are asked here; SMS needs no permission; contacts are asked later (phase B).
class PermissionsScreen extends ConsumerStatefulWidget {
  const PermissionsScreen({super.key});

  @override
  ConsumerState<PermissionsScreen> createState() => _PermissionsScreenState();
}

class _PermissionsScreenState extends ConsumerState<PermissionsScreen> {
  var _location = _PermState.unknown;
  var _notifications = _PermState.unknown;

  Future<void> _askLocation() async {
    final result = await ref.read(locationServiceProvider).ensurePermission();
    if (mounted) {
      setState(
        () => _location = result == LocationAvailability.granted
            ? _PermState.granted
            : _PermState.refused,
      );
    }
  }

  Future<void> _askNotifications() async {
    await ref.read(pushNotificationsProvider).requestPermission();
    if (mounted) setState(() => _notifications = _PermState.granted);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return WelcomeScaffold(
      title: l10n.permissionsTitle,
      bottom: FilledButton(
        key: const Key('permissions-continue'),
        onPressed: () => ref.read(welcomeProvider.notifier).permissionsSeen(),
        child: Text(l10n.actionContinue),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l10n.permissionsIntro, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 12),
          _PermissionCard(
            key: const Key('perm-location'),
            icon: Icons.location_on,
            title: l10n.permLocationTitle,
            body: l10n.permLocationBody,
            state: _location,
            onAllow: _askLocation,
          ),
          _PermissionCard(
            key: const Key('perm-notifications'),
            icon: Icons.notifications_active,
            title: l10n.permNotificationsTitle,
            body: l10n.permNotificationsBody,
            state: _notifications,
            onAllow: _askNotifications,
          ),
          _PermissionCard(
            key: const Key('perm-sms'),
            icon: Icons.sms,
            title: l10n.permSmsTitle,
            body: l10n.permSmsBody,
            note: l10n.permNoneNeeded,
          ),
          _PermissionCard(
            key: const Key('perm-contacts'),
            icon: Icons.contacts,
            title: l10n.permContactsTitle,
            body: l10n.permContactsBody,
            note: l10n.permLater,
          ),
        ],
      ),
    );
  }
}

class _PermissionCard extends StatelessWidget {
  const _PermissionCard({
    super.key,
    required this.icon,
    required this.title,
    required this.body,
    this.state = _PermState.unknown,
    this.onAllow,
    this.note,
  });

  final IconData icon;
  final String title;
  final String body;
  final _PermState state;
  final VoidCallback? onAllow;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final Widget trailing = switch ((onAllow, state)) {
      (null, _) => Text(note ?? '', style: theme.textTheme.labelMedium),
      (_, _PermState.granted) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.check_circle, color: theme.colorScheme.tertiary),
          const SizedBox(width: 4),
          Text(l10n.permAllowed),
        ],
      ),
      (_, _PermState.refused) => Text(
        l10n.permRefused,
        style: theme.textTheme.labelMedium?.copyWith(
          color: theme.colorScheme.error,
        ),
      ),
      _ => FilledButton.tonal(
        key: Key('${(key as ValueKey<String>?)?.value}-allow'),
        onPressed: onAllow,
        child: Text(l10n.permAllow),
      ),
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 32, color: theme.colorScheme.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Semantics(
                    header: true,
                    child: Text(title, style: theme.textTheme.titleMedium),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(body, style: theme.textTheme.bodyMedium),
            const SizedBox(height: 8),
            Align(alignment: AlignmentDirectional.centerEnd, child: trailing),
          ],
        ),
      ),
    );
  }
}
