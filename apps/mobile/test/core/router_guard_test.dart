import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/welcome/welcome_controller.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const none = IdentityState(mode: IdentityMode.none);
  const anon = IdentityState(
    mode: IdentityMode.anonymous,
    role: UserRole.citizen,
  );
  final registered = IdentityState(
    mode: IdentityMode.registered,
    role: UserRole.citizen,
    session: AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100)),
  );

  String? go(
    String location, {
    bool charter = true,
    IdentityState identity = none,
    bool prompted = true,
    bool locked = false,
    WelcomeSteps welcome = WelcomeSteps.done,
  }) => guardRedirect(
    location: location,
    charterAccepted: charter,
    identity: identity,
    profilePrompted: prompted,
    lockedAlert: locked,
    welcome: welcome,
  );

  // Phase A first launch: language → introduction → terms → permissions → sign-in.
  test('first launch order', () {
    const fresh = WelcomeSteps(
      languageChosen: false,
      introSeen: false,
      permissionsSeen: false,
    );
    expect(
      go(Routes.home, charter: false, welcome: fresh),
      Routes.welcomeLanguage,
    );
    expect(
      go(Routes.charter, charter: false, welcome: fresh),
      Routes.welcomeLanguage,
    );
    expect(go(Routes.welcomeLanguage, charter: false, welcome: fresh), isNull);
    const language = WelcomeSteps(
      languageChosen: true,
      introSeen: false,
      permissionsSeen: false,
    );
    expect(
      go(Routes.home, charter: false, welcome: language),
      Routes.welcomeIntro,
    );
    const intro = WelcomeSteps(
      languageChosen: true,
      introSeen: true,
      permissionsSeen: false,
    );
    expect(
      go(Routes.welcomeIntro, charter: false, welcome: intro),
      Routes.charter,
    );
    expect(go(Routes.home, welcome: intro), Routes.welcomePermissions);
    expect(go(Routes.welcomePermissions, welcome: intro), isNull);
    expect(go(Routes.welcomePermissions), Routes.onboarding);
    // Once signed in, the first-launch screens are left for home.
    expect(go(Routes.welcomeLanguage, identity: anon), Routes.home);
    expect(go(Routes.welcomePermissions, identity: anon), Routes.home);
  });

  test('emergency numbers reachable at every first-launch step', () {
    const fresh = WelcomeSteps(
      languageChosen: false,
      introSeen: false,
      permissionsSeen: false,
    );
    expect(go(Routes.emergency, charter: false, welcome: fresh), isNull);
  });

  test('over a locked phone only the public alert view exists', () {
    for (final location in [
      Routes.home,
      Routes.reports,
      Routes.settings,
      Routes.profile,
      Routes.myData,
      Routes.deleteAccount,
      Routes.emergency,
      Routes.alert('a1'),
      Routes.callouts,
      // Phase 6: live streaming is never reachable from the locked alert view.
      Routes.live,
      Routes.liveFor(serverId: 'rep-1'),
      Routes.charter,
      '/unknown/deep/link',
    ]) {
      expect(
        go(location, identity: registered, locked: true),
        Routes.lockedAlert,
        reason: location,
      );
    }
    expect(go(Routes.lockedAlert, identity: registered, locked: true), isNull);
    // Even before the charter: the lock wins.
    expect(
      go(Routes.charter, charter: false, locked: true),
      Routes.lockedAlert,
    );
    // Once unlocked the alert view is left for the app.
    expect(go(Routes.lockedAlert, identity: registered), Routes.home);
  });

  test('charter first, emergency numbers always allowed', () {
    expect(go(Routes.home, charter: false), Routes.charter);
    expect(go(Routes.newReport, charter: false), Routes.charter);
    expect(go(Routes.charter, charter: false), isNull);
    expect(go(Routes.emergency, charter: false), isNull);
  });

  test('then sign-in (phone, guest or institution), then home', () {
    expect(go(Routes.home), Routes.onboarding);
    expect(
      go(
        Routes.home,
        identity: const IdentityState(
          mode: IdentityMode.none,
          role: UserRole.citizen,
        ),
      ),
      Routes.onboarding,
    );
    expect(go(Routes.signIn), isNull);
    expect(
      go(
        Routes.home,
        identity: const IdentityState(
          mode: IdentityMode.none,
          role: UserRole.institution,
        ),
      ),
      Routes.onboardingInstitution,
    );
    expect(go(Routes.home, identity: anon), isNull);
    expect(go(Routes.charter, identity: anon), Routes.home);
    expect(go(Routes.onboarding, identity: anon), Routes.home);
    // An anonymous citizen may still open the phone sign-in from inside the app.
    expect(go(Routes.signIn, identity: anon), isNull);
  });

  test('profile is offered once after the first login', () {
    expect(
      go(Routes.home, identity: registered, prompted: false),
      Routes.profile,
    );
    expect(go(Routes.profile, identity: registered, prompted: false), isNull);
    expect(go(Routes.home, identity: registered), isNull);
    expect(go(Routes.home, identity: anon, prompted: false), isNull);
  });

  test('live route: new report without parameters, else the given report', () {
    final fresh = liveTargetFromQuery(Uri.parse(Routes.live));
    expect(fresh.isNew, isTrue);
    expect(fresh.category, ReportCategory.other);
    final uri = Uri.parse(
      Routes.liveFor(
        clientUuid: 'c-1',
        serverId: 'rep-1',
        trackingCode: 'EH-26-11-0000001',
        category: ReportCategory.fire,
      ),
    );
    final t = liveTargetFromQuery(uri);
    expect(t.isNew, isFalse);
    expect(t.clientUuid, 'c-1');
    expect(t.serverId, 'rep-1');
    expect(t.trackingCode, 'EH-26-11-0000001');
    expect(t.category, ReportCategory.fire);
    expect(go(Routes.live, identity: anon), isNull);
    expect(liveTargetFromQuery(Uri.parse('/live?report=r9')).serverId, 'r9');
  });
}
