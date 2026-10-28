# Keycloak with the e-Himaya providers (providers/phone-otp, one jar): ehimaya-phone-otp, sign-in of the mobile app
# with a phone number and an SMS code (phase A, docs/phase-a/design.md §2.2), and ehimaya-guarded-password-form, the
# password form with a proof of work after three failed attempts (phase L2, docs/phase-l/design-l2.md §3). Both
# images are pinned by digest.
FROM maven:3.9.11-eclipse-temurin-21@sha256:6fdc855a6ed81d288ca7ca37ac6ff5e9308b612485c0801d70b25a858c83d237 AS providers
WORKDIR /src
COPY providers/phone-otp/pom.xml .
RUN mvn -q -B dependency:go-offline
COPY providers/phone-otp/src ./src
# The unit tests run here too: a broken provider never reaches an image.
RUN mvn -q -B package

FROM keycloak/keycloak:26.8@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244
COPY --from=providers /src/target/ehimaya-phone-otp.jar /opt/keycloak/providers/ehimaya-phone-otp.jar
# Login theme of both realms (logo and colours of the Office; phase L2: the proof of work's page and solver).
COPY themes/ehimaya /opt/keycloak/themes/ehimaya
