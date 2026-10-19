import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/charter/charter_controller.dart';
import '../../features/charter/charter_screen.dart';
import '../../features/emergency/emergency_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/home/main_shell.dart';
import '../../features/institution/my_institution_screen.dart';
import '../../features/onboarding/citizen_mode_screen.dart';
import '../../features/onboarding/institution_screen.dart';
import '../../features/onboarding/role_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/report/category_screen.dart';
import '../../features/report/new_report_screen.dart';
import '../../features/report/report_queued_screen.dart';
import '../../features/reports/my_reports_screen.dart';
import '../../features/reports/track_screen.dart';
import '../../features/settings/settings_screen.dart';
import '../auth/identity.dart';
import '../http/models.dart';

abstract final class Routes {
  static const charter = '/charter';
  static const charterRead = '/charter/read';
  static const onboarding = '/onboarding';
  static const onboardingCitizen = '/onboarding/citizen';
  static const onboardingInstitution = '/onboarding/institution';
  static const profile = '/profile';
  static const home = '/home';
  static const reports = '/reports';
  static const settings = '/settings';
  static const emergency = '/emergency';
  static const newReport = '/report/new';
  static String newReportFor(ReportCategory c) => '/report/new/${c.wire}';
  static const reportQueued = '/report/queued';
  static const track = '/track';
  static const institutions = '/institutions';
  static String institution(String id) =>
      '/institutions/${Uri.encodeComponent(id)}';
}

/// Navigation guard (charter accepted → role chosen → identity → home). Pure function so it can
/// be unit tested. The emergency numbers are always reachable, even before the charter.
String? guardRedirect({
  required String location,
  required bool charterAccepted,
  required IdentityState identity,
  required bool profilePrompted,
}) {
  if (location == Routes.emergency) return null;
  if (!charterAccepted) {
    return location == Routes.charter ? null : Routes.charter;
  }
  if (identity.role == null) {
    return location == Routes.onboarding ? null : Routes.onboarding;
  }
  if (!identity.hasIdentity) {
    final target = identity.role == UserRole.institution
        ? Routes.onboardingInstitution
        : Routes.onboardingCitizen;
    return location == target || location == Routes.onboarding ? null : target;
  }
  if (location == Routes.charter || location.startsWith(Routes.onboarding)) {
    return Routes.home;
  }
  if (identity.isRegistered &&
      identity.role == UserRole.citizen &&
      !profilePrompted &&
      location != Routes.profile) {
    return Routes.profile;
  }
  return null;
}

class _RouterRefresh extends ChangeNotifier {
  void ping() => notifyListeners();
}

final _rootKey = GlobalKey<NavigatorState>(debugLabel: 'root');

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh();
  ref.listen(charterAcceptedProvider, (_, _) => refresh.ping());
  ref.listen(identityProvider, (_, _) => refresh.ping());
  ref.listen(profilePromptedProvider, (_, _) => refresh.ping());

  final router = GoRouter(
    navigatorKey: _rootKey,
    initialLocation: Routes.home,
    refreshListenable: refresh,
    redirect: (context, state) => guardRedirect(
      location: state.matchedLocation,
      charterAccepted: ref.read(charterAcceptedProvider),
      identity: ref.read(identityProvider),
      profilePrompted: ref.read(profilePromptedProvider),
    ),
    routes: [
      GoRoute(
        path: Routes.charter,
        builder: (_, _) => const CharterScreen(),
        routes: [
          GoRoute(
            path: 'read',
            builder: (_, _) => const CharterScreen(readOnly: true),
          ),
        ],
      ),
      GoRoute(
        path: Routes.onboarding,
        builder: (_, _) => const RoleScreen(),
        routes: [
          GoRoute(
            path: 'citizen',
            builder: (_, _) => const CitizenModeScreen(),
          ),
          GoRoute(
            path: 'institution',
            builder: (_, _) => const InstitutionScreen(),
          ),
        ],
      ),
      GoRoute(path: Routes.profile, builder: (_, _) => const ProfileScreen()),
      GoRoute(
        path: Routes.emergency,
        builder: (_, _) => const EmergencyScreen(),
      ),
      GoRoute(
        path: Routes.newReport,
        builder: (_, _) => const CategoryScreen(),
        routes: [
          GoRoute(
            path: ':category',
            builder: (_, state) {
              final category =
                  ReportCategory.fromWire(state.pathParameters['category']) ??
                  ReportCategory.other;
              return NewReportScreen(category: category);
            },
          ),
        ],
      ),
      GoRoute(
        path: Routes.reportQueued,
        builder: (_, state) => ReportQueuedScreen(
          tempCode: state.uri.queryParameters['code'] ?? '',
          sos: state.uri.queryParameters['sos'] == '1',
        ),
      ),
      GoRoute(path: Routes.track, builder: (_, _) => const TrackScreen()),
      GoRoute(
        path: Routes.institutions,
        builder: (_, _) => const MyInstitutionsScreen(),
        routes: [
          GoRoute(
            path: ':id',
            builder: (_, state) =>
                MyInstitutionScreen(orgId: state.pathParameters['id'] ?? ''),
          ),
        ],
      ),
      StatefulShellRoute.indexedStack(
        builder: (_, _, shell) => MainShell(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(path: Routes.home, builder: (_, _) => const HomeScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.reports,
                builder: (_, _) => const MyReportsScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.settings,
                builder: (_, _) => const SettingsScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
  ref.onDispose(() {
    router.dispose();
    refresh.dispose();
  });
  return router;
});
