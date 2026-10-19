import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../l10n/app_localizations.dart';
import '../onboarding/login_actions.dart';
import '../sos/sos_widgets.dart';

/// Main screens (home, my reports, settings) with the SOS action always one tap away.
class MainShell extends ConsumerWidget {
  const MainShell({super.key, required this.shell});

  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final blocked = ref.watch(anonBlockedProvider);
    final identity = ref.watch(identityProvider);
    return Scaffold(
      body: Column(
        children: [
          if (blocked && identity.isAnonymous)
            SafeArea(
              bottom: false,
              child: MaterialBanner(
                key: const Key('anon-blocked-banner'),
                leading: const Icon(Icons.block),
                content: Text(l10n.anonBlockedBody),
                actions: [
                  TextButton(
                    onPressed: () => runLogin(context, ref, register: true),
                    child: Text(l10n.citizenRegister),
                  ),
                ],
              ),
            ),
          Expanded(child: shell),
        ],
      ),
      // The home screen has its own big SOS button.
      floatingActionButton: shell.currentIndex == 0 ? null : const SosFab(),
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        onDestinationSelected: (i) =>
            shell.goBranch(i, initialLocation: i == shell.currentIndex),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_outlined),
            selectedIcon: const Icon(Icons.home),
            label: l10n.navHome,
          ),
          NavigationDestination(
            icon: const Icon(Icons.list_alt_outlined),
            selectedIcon: const Icon(Icons.list_alt),
            label: l10n.navReports,
          ),
          NavigationDestination(
            icon: const Icon(Icons.settings_outlined),
            selectedIcon: const Icon(Icons.settings),
            label: l10n.navSettings,
          ),
        ],
      ),
    );
  }
}
