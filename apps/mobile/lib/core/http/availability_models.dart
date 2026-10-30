/// DTOs of the availability calendar of volunteers and doctors (phase N, docs/phase-n/design-n.md §8).
library;

/// Whose calendar: the same person may keep one as a volunteer and one as a doctor.
enum CalendarRole {
  volunteer,
  doctor;

  String get wire => name;
}

enum SlotKind {
  available,
  unavailable;

  String get wire => name;

  static SlotKind fromWire(String? value) =>
      value == 'unavailable' ? unavailable : available;
}

/// A period the person is available, or not: every day between two dates, or on some weekdays
/// (ISO, 1 Monday … 7 Sunday) only, between two hours of Tunisia; an end before the start runs
/// past midnight.
class AvailabilitySlot {
  const AvailabilitySlot({
    required this.kind,
    required this.startsOn,
    required this.from,
    required this.to,
    this.weekdays = const [],
    this.endsOn,
  });

  factory AvailabilitySlot.fromJson(Map<String, Object?> json) =>
      AvailabilitySlot(
        kind: SlotKind.fromWire(json['kind'] as String?),
        weekdays: [
          for (final d in (json['weekdays'] as List? ?? const [])) d as int,
        ],
        startsOn: DateTime.parse(json['starts_on']! as String),
        endsOn: switch (json['ends_on']) {
          final String s => DateTime.parse(s),
          _ => null,
        },
        from: _minutes(json['from_time']! as String),
        to: _minutes(json['to_time']! as String),
      );

  final SlotKind kind;
  final List<int> weekdays;
  final DateTime startsOn;
  final DateTime? endsOn;

  /// Minutes since midnight.
  final int from;
  final int to;

  bool get overnight => to < from;

  Map<String, Object?> toJson() => {
    'kind': kind.wire,
    'weekdays': weekdays,
    'starts_on': _date(startsOn),
    'ends_on': endsOn == null ? null : _date(endsOn!),
    'from_time': hhmm(from),
    'to_time': hhmm(to),
  };

  static int _minutes(String t) {
    final parts = t.split(':');
    return int.parse(parts[0]) * 60 + int.parse(parts[1]);
  }

  static String _date(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  static String hhmm(int minutes) =>
      '${(minutes ~/ 60).toString().padLeft(2, '0')}:${(minutes % 60).toString().padLeft(2, '0')}';
}

class AvailabilityCalendar {
  const AvailabilityCalendar({required this.slots, required this.plannedNow});

  factory AvailabilityCalendar.fromJson(Map<String, Object?> json) =>
      AvailabilityCalendar(
        slots: [
          for (final s in (json['slots'] as List? ?? const []))
            if (s is Map<String, Object?>) AvailabilitySlot.fromJson(s),
        ],
        plannedNow: switch (json['planned_now']) {
          final String s => SlotKind.fromWire(s),
          _ => null,
        },
      );

  final List<AvailabilitySlot> slots;

  /// What the calendar says now; null when nothing is planned.
  final SlotKind? plannedNow;
}

/// Slots kept at most (server `MAX_SLOTS`).
const maxAvailabilitySlots = 20;
