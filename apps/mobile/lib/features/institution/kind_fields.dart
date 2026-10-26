import 'package:flutter/material.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'org_text.dart';

/// Who may see a field of the kind (phase P2a, docs/phase-p2/design-institutions-app.md §2.2).
enum FieldVisibility {
  public('public', Tone.green, Icons.public),
  orgOffice('org_office', Tone.navy, Icons.apartment),
  incident('incident', Tone.red, Icons.emergency);

  const FieldVisibility(this.wire, this.tone, this.icon);

  final String wire;
  final Tone tone;
  final IconData icon;
}

enum KindFieldType { int, bool, text }

class KindField {
  const KindField(
    this.key,
    this.type,
    this.visibility, [
    this.maximum = 1000000,
  ]);

  final String key;
  final KindFieldType type;
  final FieldVisibility visibility;

  /// int: largest value; text: longest length.
  final int maximum;
}

const _i = KindFieldType.int;
const _b = KindFieldType.bool;
const _t = KindFieldType.text;
const _pub = FieldVisibility.public;
const _org = FieldVisibility.orgOffice;
const _inc = FieldVisibility.incident;

/// Mirror of `app.modules.orgs.domain.KIND_FIELDS` (also served at `GET /public/org-kinds`): the
/// server validates the answers. Working list [SIM] until the Office approves it.
const kindFields = <String, List<KindField>>{
  'health': [
    KindField('reception_phone', _t, _pub, 20),
    KindField('beds', _i, _org, 10000),
    KindField('icu', _b, _org),
    KindField('oxygen_hours', _i, _org, 10000),
    KindField('generator', _b, _org),
    KindField('helipad', _b, _org),
    KindField('non_ambulatory', _i, _inc, 10000),
  ],
  'industrial': [
    KindField('workers_per_shift', _i, _org, 100000),
    KindField('self_fire_fighting', _b, _org),
    KindField('tanks', _i, _inc, 1000),
  ],
  'energy': [
    KindField('fuel_types', _t, _org, 200),
    KindField('storage_m3', _i, _inc, 10000000),
    KindField('shutoff_valves', _b, _inc),
  ],
  'tourism': [
    KindField('rooms', _i, _org, 10000),
    KindField('guest_languages', _t, _org, 200),
    KindField('pool_or_beach', _b, _org),
    KindField('occupancy_pct', _i, _inc, 100),
  ],
  'education': [
    KindField('students', _i, _org, 100000),
    KindField('age_range', _t, _org, 50),
    KindField('boarding', _b, _org),
    KindField('students_special_needs', _i, _inc, 10000),
  ],
  'social_care': [
    KindField('residents', _i, _org, 10000),
    KindField('night_watch', _b, _org),
    KindField('non_ambulatory', _i, _inc, 10000),
  ],
  'public_admin': [
    KindField('staff', _i, _org, 100000),
    KindField('archive', _b, _org),
  ],
  'culture_sport': [
    KindField('seated_capacity', _i, _org, 200000),
    KindField('stands', _b, _org),
  ],
  'commercial': [
    KindField('shops', _i, _org, 10000),
    KindField('underground_parking', _b, _inc),
  ],
  'transport': [
    KindField('daily_passengers', _i, _org, 10000000),
    KindField('emergency_exits', _i, _org, 1000),
  ],
  'religious': [KindField('peak_times', _t, _org, 200)],
  'other': [],
};

/// Icon and colour of each kind on the registration grid and the institution's header.
(IconData, Tone) kindLook(String kind) => switch (kind) {
  'health' => (Icons.local_hospital, Tone.red),
  'industrial' => (Icons.factory, Tone.slate),
  'energy' => (Icons.local_gas_station, Tone.orange),
  'tourism' => (Icons.hotel, Tone.sky),
  'education' => (Icons.school, Tone.navy),
  'social_care' => (Icons.elderly, Tone.purple),
  'public_admin' => (Icons.account_balance, Tone.navy),
  'culture_sport' => (Icons.stadium, Tone.green),
  'commercial' => (Icons.storefront, Tone.amber),
  'transport' => (Icons.directions_bus, Tone.teal),
  'religious' => (Icons.mosque, Tone.green),
  _ => (Icons.apartment, Tone.slate),
};

/// What is wrong with one answer typed in a form, if anything (null: fine or empty).
String? kindFieldError(AppLocalizations l10n, KindField f, Object? raw) {
  if (raw is! String || raw.trim().isEmpty || f.type == KindFieldType.bool) {
    return null;
  }
  if (f.type == KindFieldType.int) {
    final n = int.tryParse(raw.trim());
    return n != null && n >= 0 && n <= f.maximum ? null : l10n.orgInvalidNumber;
  }
  return raw.trim().length > f.maximum ? l10n.orgInvalidNumber : null;
}

/// The answers of [kind] as the API takes them, from form values (text as typed, yes/no as bool).
Map<String, Object> kindFieldsToJson(String kind, Map<String, Object?> form) =>
    {
      for (final f in kindFields[kind] ?? const <KindField>[])
        if (_value(f, form[f.key]) case final Object v) f.key: v,
    };

Object? _value(KindField f, Object? raw) => switch (f.type) {
  KindFieldType.bool => raw is bool ? raw : null,
  KindFieldType.int =>
    raw is int ? raw : (raw is String ? int.tryParse(raw.trim()) : null),
  KindFieldType.text =>
    raw is String && raw.trim().isNotEmpty ? raw.trim() : null,
};

/// The badge naming who may see a field.
class VisibilityPill extends StatelessWidget {
  const VisibilityPill(this.visibility, {super.key});

  final FieldVisibility visibility;

  @override
  Widget build(BuildContext context) => Pill(
    visibilityText(AppLocalizations.of(context), visibility.wire),
    tone: visibility.tone,
    icon: visibility.icon,
  );
}

/// One answer of the kind's fields, shown as label, value and visibility badge.
class KindFieldRow extends StatelessWidget {
  const KindFieldRow({super.key, required this.field, required this.value});

  final KindField field;
  final Object? value;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final v = value;
    final text = switch (v) {
      null => l10n.orgNotSet,
      final bool b => b ? l10n.orgYes : l10n.orgNo,
      _ => '$v',
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: PillBeside(
        pill: VisibilityPill(field.visibility),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              kindFieldText(l10n, field.key),
              style: theme.textTheme.bodySmall,
            ),
            Text(
              text,
              style: theme.textTheme.bodyLarge,
              textDirection: field.key == 'reception_phone'
                  ? TextDirection.ltr
                  : null,
            ),
          ],
        ),
      ),
    );
  }
}

/// A value with its badge at the end of the line; at large text sizes the badge
/// moves under the value so neither is clipped.
class PillBeside extends StatelessWidget {
  const PillBeside({super.key, required this.child, required this.pill});

  final Widget child;
  final Widget pill;

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.textScalerOf(context).scale(10) > 13) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          child,
          const SizedBox(height: 4),
          Align(alignment: AlignmentDirectional.centerStart, child: pill),
        ],
      );
    }
    return Row(
      children: [
        Expanded(child: child),
        pill,
      ],
    );
  }
}
