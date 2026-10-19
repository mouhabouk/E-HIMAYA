import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/routing/app_router.dart';
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
  }) => guardRedirect(
    location: location,
    charterAccepted: charter,
    identity: identity,
    profilePrompted: prompted,
  );

  test('charter first, emergency numbers always allowed', () {
    expect(go(Routes.home, charter: false), Routes.charter);
    expect(go(Routes.newReport, charter: false), Routes.charter);
    expect(go(Routes.charter, charter: false), isNull);
    expect(go(Routes.emergency, charter: false), isNull);
  });

  test('then role, then identity', () {
    expect(go(Routes.home), Routes.onboarding);
    expect(
      go(
        Routes.home,
        identity: const IdentityState(
          mode: IdentityMode.none,
          role: UserRole.citizen,
        ),
      ),
      Routes.onboardingCitizen,
    );
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
    expect(go(Routes.onboardingCitizen, identity: anon), Routes.home);
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
}
