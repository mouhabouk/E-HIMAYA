/// The work e-mail of the signed-in account (phase P5b, F-APP-12): proven by the identity
/// provider (`account`) or by a code sent by the API (`code`), or not yet.
class EmailStatus {
  const EmailStatus({required this.email, required this.verified, this.source});

  factory EmailStatus.fromJson(Map<String, Object?> json) => EmailStatus(
    email: json['email'] as String?,
    verified: json['verified'] == true,
    source: json['source'] as String?,
  );

  final String? email;
  final bool verified;
  final String? source;
}
