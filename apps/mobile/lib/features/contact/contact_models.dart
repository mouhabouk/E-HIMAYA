/// "Contact us" (phase B1, design §2ter): kinds, statuses and the citizen's own requests.
enum ContactKind {
  accessInfo('access_info'),
  hazard('hazard'),
  question('question'),
  suggestion('suggestion'),
  appProblem('app_problem'),
  partnership('partnership');

  const ContactKind(this.wire);
  final String wire;

  static ContactKind fromWire(String? v) =>
      values.where((k) => k.wire == v).firstOrNull ?? question;
}

enum ContactStatus {
  received('received'),
  inProgress('in_progress'),
  answered('answered'),
  closed('closed'),
  rejected('rejected');

  const ContactStatus(this.wire);
  final String wire;

  static ContactStatus fromWire(String? v) =>
      values.where((s) => s.wire == v).firstOrNull ?? received;
}

/// Limits mirrored from the API (a refused field is caught before sending).
abstract final class ContactRules {
  static const subjectMin = 3;
  static const subjectMax = 120;
  static const messageMin = 10;
  static const messageMax = 3000;
  static const nameMin = 2;
  static const nameMax = 120;
  static final localPhone = RegExp(r'^\d{8}$');
  static final email = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  /// Law 2016-22 asks who requests the information.
  static bool nameRequired(ContactKind k) => k == ContactKind.accessInfo;

  /// A hazard is handled by a gouvernorat.
  static bool gouvernoratRequired(ContactKind k) => k == ContactKind.hazard;
}

class ContactHistoryEntry {
  const ContactHistoryEntry({
    required this.action,
    required this.at,
    this.status,
  });

  final String action;
  final ContactStatus? status;
  final DateTime at;

  factory ContactHistoryEntry.fromJson(Map<String, Object?> json) =>
      ContactHistoryEntry(
        action: '${json['action']}',
        status: json['status'] == null
            ? null
            : ContactStatus.fromWire(json['status'] as String?),
        at: DateTime.parse('${json['at']}'),
      );
}

class MyContactRequest {
  const MyContactRequest({
    required this.id,
    required this.number,
    required this.kind,
    required this.status,
    required this.subject,
    required this.message,
    required this.createdAt,
    this.gouvernoratCode,
    this.dueAt,
    this.answer,
    this.answeredAt,
    this.history = const [],
  });

  final String id;
  final String number;
  final ContactKind kind;
  final ContactStatus status;
  final String subject;
  final String message;
  final DateTime createdAt;
  final int? gouvernoratCode;
  final DateTime? dueAt;

  /// The Office's answer, or the reason of a rejection.
  final String? answer;
  final DateTime? answeredAt;
  final List<ContactHistoryEntry> history;

  static DateTime? _date(Object? v) => v == null ? null : DateTime.parse('$v');

  factory MyContactRequest.fromJson(Map<String, Object?> json) {
    final history = json['history'];
    return MyContactRequest(
      id: '${json['id']}',
      number: '${json['number']}',
      kind: ContactKind.fromWire(json['kind'] as String?),
      status: ContactStatus.fromWire(json['status'] as String?),
      subject: (json['subject'] as String?) ?? '',
      message: (json['message'] as String?) ?? '',
      createdAt: DateTime.parse('${json['created_at']}'),
      gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt(),
      dueAt: _date(json['due_at']),
      answer: json['answer'] as String?,
      answeredAt: _date(json['answered_at']),
      history: [
        if (history is List)
          for (final h in history)
            if (h is Map<String, Object?>) ContactHistoryEntry.fromJson(h),
      ],
    );
  }
}
