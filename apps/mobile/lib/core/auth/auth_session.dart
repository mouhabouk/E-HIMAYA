import 'dart:convert';

/// OIDC tokens of a registered citizen or institution account (realm `ehimaya-public`).
class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.expiresAt,
    this.refreshToken,
    this.idToken,
  });

  final String accessToken;
  final DateTime expiresAt;
  final String? refreshToken;
  final String? idToken;

  bool expiresWithin(Duration margin, DateTime now) =>
      !now.add(margin).isBefore(expiresAt);

  /// `sub` claim of the access token (used only as a local identity fingerprint, the server
  /// verifies the signature).
  String? get subject => _claims(accessToken)?['sub'] as String?;

  /// Display hint for the settings screen: the verified phone number (phase A sign-in), else
  /// `preferred_username` or `email`.
  String? get displayName {
    final claims = _claims(idToken ?? accessToken);
    return (claims?['phone_number'] ??
            claims?['preferred_username'] ??
            claims?['email'])
        as String?;
  }

  Map<String, Object?> toJson() => {
    'access_token': accessToken,
    'expires_at': expiresAt.toUtc().toIso8601String(),
    'refresh_token': refreshToken,
    'id_token': idToken,
  };

  static AuthSession? tryParse(String? raw) {
    if (raw == null) return null;
    try {
      final json = jsonDecode(raw) as Map<String, Object?>;
      return AuthSession(
        accessToken: json['access_token']! as String,
        expiresAt: DateTime.parse(json['expires_at']! as String),
        refreshToken: json['refresh_token'] as String?,
        idToken: json['id_token'] as String?,
      );
    } on Object {
      return null;
    }
  }

  static Map<String, Object?>? _claims(String jwt) {
    final parts = jwt.split('.');
    if (parts.length != 3) return null;
    try {
      final payload = utf8.decode(
        base64Url.decode(base64Url.normalize(parts[1])),
      );
      return jsonDecode(payload) as Map<String, Object?>;
    } on Object {
      return null;
    }
  }
}
