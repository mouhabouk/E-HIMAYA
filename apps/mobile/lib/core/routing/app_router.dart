import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/alerts/notifications_screen.dart';
import '../../features/charter/charter_controller.dart';
import '../../features/charter/charter_screen.dart';
import '../../features/contact/contact_screens.dart';
import '../../features/doctor/doctor_directory_screen.dart';
import '../../features/doctor/doctor_files_screen.dart';
import '../../features/doctor/doctor_form_screen.dart';
import '../../features/doctor/doctor_screen.dart';
import '../../features/emergency/emergency_screen.dart';
import '../../features/guide/guide_screens.dart';
import '../../features/home/home_screen.dart';
import '../../features/home/main_shell.dart';
import '../../features/institution/my_institution_screen.dart';
import '../../features/live/live_controller.dart';
import '../../features/live/live_screen.dart';
import '../../features/onboarding/institution_screen.dart';
import '../../features/onboarding/sign_in_screen.dart';
import '../../features/places/nearest_screen.dart';
import '../../features/privacy/my_data_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/quota/quota_screen.dart';
import '../../features/report/category_screen.dart';
import '../../features/report/new_report_screen.dart';
import '../../features/report/report_queued_screen.dart';
import '../../features/reports/my_reports_screen.dart';
import '../../features/reports/track_screen.dart';
import '../../features/rewards/rewards_screen.dart';
import '../../features/safety/contacts_screen.dart';
import '../../features/safety/linked_screen.dart';
import '../../features/safety/live_share_screen.dart';
import '../../features/safety/location_history_screen.dart';
import '../../features/safety/medical_screen.dart';
import '../../features/safety/received_alert_screen.dart';
import '../../features/safety/recent_screen.dart';
import '../../features/safety/safety_check_screen.dart';
import '../../features/safety/safety_hub_screen.dart';
import '../../features/safety/self_test_screen.dart';
import '../../features/safety/sos_message_screens.dart';
import '../../features/settings/alert_check.dart';
import '../../features/settings/settings_screen.dart';
import '../../features/tips/tips_screen.dart';
import '../../features/volunteer/callouts_screen.dart';
import '../../features/volunteer/volunteer_form_screen.dart';
import '../../features/volunteer/volunteer_screen.dart';
import '../../features/welcome/intro_screen.dart';
import '../../features/welcome/language_screen.dart';
import '../../features/welcome/permissions_screen.dart';
import '../../features/welcome/welcome_controller.dart';
import '../auth/identity.dart';
import '../http/doctor_models.dart';
import '../http/models.dart';
import '../security/locked_alert.dart';

abstract final class Routes {
  static const charter = '/charter';
  static const charterRead = '/charter/read';
  static const onboarding = '/onboarding';
  // Phase A first launch: language, introduction cards, permissions; sign-in by phone.
  static const welcomeLanguage = '/welcome/language';
  static const welcomeIntro = '/welcome/intro';
  static const welcomePermissions = '/welcome/permissions';
  static const signIn = '/sign-in';
  static const onboardingInstitution = '/onboarding/institution';
  static const profile = '/profile';
  static const home = '/home';
  static const reports = '/reports';
  static const settings = '/settings';
  static const emergency = '/emergency';
  // Phase B1: emergency hub guide, reachable before the terms like the numbers.
  static const guide = '/emergency/guide';
  static const nearest = '/emergency/nearest';
  static const contact = '/contact';
  static const contactMine = '/contact/mine';
  static String guideTopic(String key) =>
      '/emergency/guide/${Uri.encodeComponent(key)}';
  static String guideItem(String key, String item) =>
      '/emergency/guide/${Uri.encodeComponent(key)}/${Uri.encodeComponent(item)}';
  static const newReport = '/report/new';
  static String newReportFor(ReportCategory c) => '/report/new/${c.wire}';
  static const reportQueued = '/report/queued';
  static const track = '/track';
  static const institutions = '/institutions';
  static String institution(String id) =>
      '/institutions/${Uri.encodeComponent(id)}';
  // Phase 5: volunteers, notifications and alerts, safety tips.
  static const volunteer = '/volunteer';
  static const volunteerApply = '/volunteer/apply';
  static const callouts = '/callouts';
  // Phase C1-a: doctors.
  static const doctor = '/doctor';
  static const doctorApply = '/doctor/apply';
  static const doctorDirectory = '/doctor/directory';
  static const doctorFiles = '/doctor/files';
  static const notifications = '/notifications';
  static String alert(String id) => '/alerts/${Uri.encodeComponent(id)}';
  static const tips = '/tips';
  // Phase 5.5: alert delivery, citizen rights.
  static const alertCheck = '/alert-check';
  static const criticalAlerts = '/alert-check/critical';
  static const myData = '/my-data';
  static const deleteAccount = '/my-data/delete';

  // Phase 6: live streaming (FR-A-031). Without parameters: a new report.
  static const live = '/live';
  static String liveFor({
    String? clientUuid,
    String? serverId,
    String? trackingCode,
    ReportCategory? category,
  }) => Uri(
    path: live,
    queryParameters: {
      'uuid': ?clientUuid,
      'report': ?serverId,
      'code': ?trackingCode,
      'category': ?category?.wire,
    },
  ).toString();

  /// The public alert view over a locked phone (see [LockedAlertScreen]).
  static const lockedAlert = '/locked-alert';
  static String tip(String hazard) => '/tips/${Uri.encodeComponent(hazard)}';

  // Phase 8: points, badges and certificates (FR-A-072).
  static const rewards = '/rewards';

  // Phase B2: personal safety.
  static const safety = '/safety';
  static const safetyContacts = '/safety/contacts';
  static const safetyMessage = '/safety/message';
  static const safetySend = '/safety/send';
  static const safetyLinked = '/safety/linked';
  static const safetyLive = '/safety/live';
  static const safetyCheck = '/safety/check';
  static const safetyTest = '/safety/test';
  static const safetyRecent = '/safety/recent';
  static const safetyMedical = '/safety/medical';
  static const safetyLocationHistory = '/safety/location-history';
  static String safetyAlert(String id) =>
      '/safety/alerts/${Uri.encodeComponent(id)}';

  // Phase 9 §3: anonymous report quota; `code`: a report kept until the user signs in.
  static const quota = '/quota';
  static String quotaFor(String tempCode) =>
      Uri(path: quota, queryParameters: {'code': tempCode}).toString();
}

/// Navigation guard (phase A order: language → introduction → terms → permissions → sign-in →
/// home). Pure function so it can be unit tested. The emergency numbers are always reachable,
/// even before the terms.
String? guardRedirect({
  required String location,
  required bool charterAccepted,
  required IdentityState identity,
  required bool profilePrompted,
  bool lockedAlert = false,
  WelcomeSteps welcome = WelcomeSteps.done,
}) {
  // Over a locked phone only the public alert view exists: no shell, no other route, no deep
  // link. Checked first, before anything else.
  if (lockedAlert) {
    return location == Routes.lockedAlert ? null : Routes.lockedAlert;
  }
  if (location == Routes.lockedAlert) return Routes.home;
  if (location == Routes.emergency ||
      location.startsWith('${Routes.emergency}/')) {
    return null;
  }
  String? only(String target) => location == target ? null : target;
  if (!welcome.languageChosen) return only(Routes.welcomeLanguage);
  if (!welcome.introSeen) return only(Routes.welcomeIntro);
  if (!charterAccepted) return only(Routes.charter);
  if (!welcome.permissionsSeen) return only(Routes.welcomePermissions);
  if (!identity.hasIdentity) {
    if (location == Routes.onboarding || location == Routes.signIn) return null;
    return identity.role == UserRole.institution
        ? only(Routes.onboardingInstitution)
        : Routes.onboarding;
  }
  if (location == Routes.charter ||
      location.startsWith(Routes.onboarding) ||
      location.startsWith('/welcome/')) {
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

/// `/live?uuid=&report=&code=&category=`: an existing report when `uuid` or `report` is given,
/// otherwise a new one.
LiveTarget liveTargetFromQuery(Uri uri) {
  final q = uri.queryParameters;
  final uuid = q['uuid'];
  final report = q['report'];
  final category =
      ReportCategory.fromWire(q['category']) ?? ReportCategory.other;
  if ((uuid == null || uuid.isEmpty) && (report == null || report.isEmpty)) {
    return LiveTarget.newReport(category: category);
  }
  return LiveTarget.existing(
    clientUuid: uuid == null || uuid.isEmpty ? null : uuid,
    serverId: report == null || report.isEmpty ? null : report,
    trackingCode: q['code'],
    category: category,
  );
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
  ref.listen(welcomeProvider, (_, _) => refresh.ping());
  ref.listen(
    lockedAlertProvider.select((s) => s.locked),
    (_, _) => refresh.ping(),
  );

  final router = GoRouter(
    navigatorKey: _rootKey,
    initialLocation: Routes.home,
    refreshListenable: refresh,
    redirect: (context, state) => guardRedirect(
      location: state.matchedLocation,
      charterAccepted: ref.read(charterAcceptedProvider),
      identity: ref.read(identityProvider),
      profilePrompted: ref.read(profilePromptedProvider),
      lockedAlert: ref.read(lockedAlertProvider).locked,
      welcome: ref.read(welcomeProvider),
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
        path: Routes.welcomeLanguage,
        builder: (_, _) => const LanguageScreen(),
      ),
      GoRoute(
        path: Routes.welcomeIntro,
        builder: (_, _) => const IntroScreen(),
      ),
      GoRoute(
        path: Routes.welcomePermissions,
        builder: (_, _) => const PermissionsScreen(),
      ),
      GoRoute(
        path: Routes.signIn,
        builder: (_, _) => const SignInScreen(standalone: true),
      ),
      GoRoute(
        path: Routes.onboarding,
        builder: (_, _) => const SignInScreen(),
        routes: [
          GoRoute(
            path: 'institution',
            builder: (_, _) => const InstitutionScreen(),
          ),
        ],
      ),
      GoRoute(path: Routes.profile, builder: (_, _) => const ProfileScreen()),
      GoRoute(
        path: Routes.contact,
        builder: (_, _) => const ContactScreen(),
        routes: [
          GoRoute(path: 'mine', builder: (_, _) => const MyContactScreen()),
        ],
      ),
      GoRoute(
        path: Routes.emergency,
        builder: (_, _) => const EmergencyScreen(),
        routes: [
          GoRoute(path: 'nearest', builder: (_, _) => const NearestScreen()),
          GoRoute(
            path: 'guide',
            builder: (_, _) => const GuideTopicsScreen(),
            routes: [
              GoRoute(
                path: ':topic',
                builder: (_, state) =>
                    GuideTopicScreen(topicKey: state.pathParameters['topic']!),
                routes: [
                  GoRoute(
                    path: ':item',
                    builder: (_, state) => GuideItemScreen(
                      topicKey: state.pathParameters['topic']!,
                      itemId: state.pathParameters['item']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
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
        path: Routes.safety,
        builder: (_, _) => const SafetyHubScreen(),
        routes: [
          GoRoute(
            path: 'contacts',
            builder: (_, _) => const EmergencyContactsScreen(),
          ),
          GoRoute(
            path: 'message',
            builder: (_, _) => const SosMessageSettingsScreen(),
          ),
          GoRoute(path: 'send', builder: (_, _) => const SosSendScreen()),
          GoRoute(
            path: 'linked',
            builder: (_, _) => const LinkedContactsScreen(),
          ),
          GoRoute(path: 'live', builder: (_, _) => const LiveShareScreen()),
          GoRoute(path: 'check', builder: (_, _) => const SafetyCheckScreen()),
          GoRoute(path: 'test', builder: (_, _) => const SelfTestScreen()),
          GoRoute(
            path: 'recent',
            builder: (_, _) => const SafetyRecentScreen(),
          ),
          GoRoute(path: 'medical', builder: (_, _) => const MedicalScreen()),
          GoRoute(
            path: 'location-history',
            builder: (_, _) => const LocationHistoryScreen(),
          ),
          GoRoute(
            path: 'alerts/:id',
            builder: (_, state) =>
                SafetyAlertScreen(alertId: state.pathParameters['id'] ?? ''),
          ),
        ],
      ),
      GoRoute(path: Routes.rewards, builder: (_, _) => const RewardsScreen()),
      GoRoute(
        path: Routes.quota,
        builder: (_, state) =>
            AnonQuotaScreen(tempCode: state.uri.queryParameters['code']),
      ),
      GoRoute(
        path: Routes.live,
        builder: (_, state) =>
            LiveScreen(target: liveTargetFromQuery(state.uri)),
      ),
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
      GoRoute(
        path: Routes.volunteer,
        builder: (_, _) => const VolunteerScreen(),
        routes: [
          GoRoute(
            path: 'apply',
            builder: (_, _) => const VolunteerFormScreen(),
          ),
        ],
      ),
      GoRoute(
        path: Routes.doctor,
        builder: (_, _) => const DoctorScreen(),
        routes: [
          GoRoute(
            path: 'apply',
            builder: (_, state) => DoctorFormScreen(
              kind: switch (state.uri.queryParameters['kind']) {
                null => null,
                final k => DoctorKind.fromWire(k),
              },
            ),
          ),
          GoRoute(
            path: 'directory',
            builder: (_, _) => const DoctorDirectoryScreen(),
          ),
          GoRoute(path: 'files', builder: (_, _) => const DoctorFilesScreen()),
        ],
      ),
      GoRoute(path: Routes.callouts, builder: (_, _) => const CalloutsScreen()),
      GoRoute(
        path: Routes.lockedAlert,
        builder: (_, _) => const LockedAlertScreen(),
      ),
      GoRoute(
        path: Routes.alertCheck,
        builder: (_, _) => const AlertCheckScreen(),
        routes: [
          GoRoute(
            path: 'critical',
            builder: (_, _) => const CriticalAlertsScreen(),
          ),
        ],
      ),
      GoRoute(
        path: Routes.myData,
        builder: (_, _) => const MyDataScreen(),
        routes: [
          GoRoute(
            path: 'delete',
            builder: (_, _) => const DeleteAccountScreen(),
          ),
        ],
      ),
      GoRoute(
        path: Routes.notifications,
        builder: (_, _) => const NotificationsScreen(),
      ),
      GoRoute(
        path: '/alerts/:id',
        builder: (_, state) =>
            AlertDetailScreen(alertId: state.pathParameters['id'] ?? ''),
      ),
      GoRoute(
        path: Routes.tips,
        builder: (_, _) => const TipsScreen(),
        routes: [
          GoRoute(
            path: ':hazard',
            builder: (_, state) =>
                TipDetailScreen(hazard: state.pathParameters['hazard'] ?? ''),
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
