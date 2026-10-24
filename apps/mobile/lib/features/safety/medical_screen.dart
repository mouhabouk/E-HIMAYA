import 'dart:convert';

import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/providers.dart';
import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/platform/device_services.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'safety_models.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// The file as plain text, in the user's language (shown to a rescuer, or copied).
String medicalText(AppLocalizations l10n, MedicalFile f) {
  final d = f.birthDate;
  return [
    if (f.sex != null) '${l10n.medicalSex}: ${_sexLabel(l10n, f.sex!)}',
    if (d != null)
      '${l10n.medicalBirthDate}: ${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}',
    if (f.bloodGroup != null) '${l10n.medicalBloodGroup}: ${f.bloodGroup}',
    if (f.allergies != null) '${l10n.medicalAllergies}: ${f.allergies}',
    if (f.conditions != null) '${l10n.medicalConditions}: ${f.conditions}',
    if (f.medications != null) '${l10n.medicalMedications}: ${f.medications}',
    if (f.other != null) '${l10n.medicalOther}: ${f.other}',
    if (f.treatmentCard != null)
      '${l10n.medicalTreatmentCard}: ${f.treatmentCard}',
    if (f.contactName != null || f.contactPhone != null)
      '${l10n.medicalContact}: ${[?f.contactName, ?f.contactPhone].join(' ')}',
  ].join('\n');
}

String _sexLabel(AppLocalizations l10n, String sex) => switch (sex) {
  'female' => l10n.medicalSexFemale,
  'male' => l10n.medicalSexMale,
  _ => sex,
};

/// Addition 7b: the medical file, kept on the phone only (encrypted database), with its own
/// consent and an optional phone lock. Sent with a report only when the user ticks it for that
/// report. Deleted in one tap.
class MedicalScreen extends ConsumerStatefulWidget {
  const MedicalScreen({super.key});

  @override
  ConsumerState<MedicalScreen> createState() => _MedicalScreenState();
}

class _MedicalScreenState extends ConsumerState<MedicalScreen> {
  bool _unlocked = false;
  bool _agreed = false;

  Future<void> _create() async {
    final now = ref.read(clockProvider)();
    await ref
        .read(databaseProvider)
        .saveMedical(
          MedicalProfilesCompanion.insert(
            id: const Value(1),
            data: '{}',
            consentVersion: SafetyRules.medicalConsentVersion,
            consentAt: now,
            updatedAt: now,
          ),
        );
    setState(() => _unlocked = true);
  }

  Future<void> _unlock() async {
    final l10n = AppLocalizations.of(context);
    final ok = await ref
        .read(deviceServicesProvider)
        .confirmCredential(
          title: l10n.safetyMedicalTitle,
          description: l10n.medicalUnlockHint,
        );
    if (!mounted) return;
    if (ok == null) {
      // No secure lock on this phone: the lock cannot protect the file.
      showSafetySnack(context, l10n.medicalNoPhoneLock);
      setState(() => _unlocked = true);
    } else if (ok) {
      setState(() => _unlocked = true);
    }
  }

  Future<void> _delete() async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.medicalDeleteTitle),
        content: Text(l10n.medicalDeleteBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('medical-delete-confirm'),
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.safetyDelete),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await ref.read(databaseProvider).deleteMedical();
    if (mounted) {
      setState(() {
        _unlocked = false;
        _agreed = false;
      });
      showSafetySnack(context, l10n.medicalDeleted);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final row = ref.watch(medicalRowProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyMedicalTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: row.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text(l10n.errorUnknown)),
          data: (r) {
            if (r == null) {
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    l10n.medicalConsentTitle,
                    style: theme.textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(l10n.medicalConsentBody),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    key: const Key('medical-consent'),
                    contentPadding: EdgeInsets.zero,
                    value: _agreed,
                    onChanged: (v) => setState(() => _agreed = v == true),
                    title: Text(l10n.medicalConsentCheck),
                  ),
                  FilledButton.icon(
                    key: const Key('medical-create'),
                    onPressed: _agreed ? _create : null,
                    icon: const Icon(Icons.medical_information),
                    label: Text(l10n.medicalCreate),
                  ),
                ],
              );
            }
            if (r.locked && !_unlocked) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.lock, size: 56),
                      const SizedBox(height: 12),
                      Text(l10n.medicalLocked, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        key: const Key('medical-unlock'),
                        onPressed: _unlock,
                        icon: const Icon(Icons.fingerprint),
                        label: Text(l10n.medicalUnlock),
                      ),
                    ],
                  ),
                ),
              );
            }
            return _MedicalForm(row: r, onDelete: _delete);
          },
        ),
      ),
    );
  }
}

class _MedicalForm extends ConsumerStatefulWidget {
  const _MedicalForm({required this.row, required this.onDelete});

  final MedicalProfileRow row;
  final VoidCallback onDelete;

  @override
  ConsumerState<_MedicalForm> createState() => _MedicalFormState();
}

class _MedicalFormState extends ConsumerState<_MedicalForm> {
  late MedicalFile _file;
  late final Map<String, TextEditingController> _fields;
  String? _sex;
  String? _blood;
  DateTime? _birth;

  static const _keys = [
    'allergies',
    'conditions',
    'medications',
    'other',
    'treatment_card',
    'contact_name',
    'contact_phone',
  ];

  @override
  void initState() {
    super.initState();
    _file = medicalOf(widget.row) ?? const MedicalFile();
    final json = _file.toJson();
    _fields = {
      for (final k in _keys)
        k: TextEditingController(text: json[k] as String? ?? ''),
    };
    _sex = _file.sex;
    _blood = _file.bloodGroup;
    _birth = _file.birthDate;
  }

  @override
  void dispose() {
    for (final c in _fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  MedicalFile _current() => MedicalFile.fromJson({
    'sex': _sex,
    if (_birth != null) 'birth_date': _birth!.toIso8601String(),
    'blood_group': _blood,
    for (final k in _keys) k: _fields[k]!.text,
  });

  Future<void> _save({bool? locked}) async {
    final l10n = AppLocalizations.of(context);
    final file = _current();
    await ref
        .read(databaseProvider)
        .saveMedical(
          MedicalProfilesCompanion.insert(
            id: const Value(1),
            data: jsonEncode(file.toJson()),
            consentVersion: widget.row.consentVersion,
            consentAt: widget.row.consentAt,
            locked: Value(locked ?? widget.row.locked),
            updatedAt: ref.read(clockProvider)(),
          ),
        );
    _file = file;
    if (mounted && locked == null) showSafetySnack(context, l10n.safetySaved);
  }

  Future<void> _setLock(bool on) async {
    if (on) {
      final l10n = AppLocalizations.of(context);
      final ok = await ref
          .read(deviceServicesProvider)
          .confirmCredential(
            title: l10n.safetyMedicalTitle,
            description: l10n.medicalUnlockHint,
          );
      if (!mounted) return;
      if (ok == null) {
        showSafetySnack(context, l10n.medicalNoPhoneLock);
        return;
      }
      if (!ok) return;
    }
    await _save(locked: on);
  }

  void _show() {
    final l10n = AppLocalizations.of(context);
    final text = medicalText(l10n, _current());
    showDialog<void>(
      context: context,
      builder: (context) => Dialog.fullscreen(
        child: Scaffold(
          appBar: AppBar(
            title: Text(l10n.medicalForRescuer),
            actions: const [StandardAppBarActions()],
          ),
          body: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                text.isEmpty ? l10n.medicalEmpty : text,
                key: const Key('medical-rescuer-text'),
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _text(
    String key,
    String label, {
    int lines = 1,
    TextInputType? type,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: TextField(
      key: Key('medical-$key'),
      controller: _fields[key],
      maxLines: lines,
      minLines: 1,
      maxLength: 500,
      keyboardType: type,
      decoration: InputDecoration(labelText: label),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final birth = _birth;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(l10n.medicalIntro, style: theme.textTheme.bodySmall),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<String?>(
                key: const Key('medical-sex'),
                initialValue: _sex,
                decoration: InputDecoration(labelText: l10n.medicalSex),
                items: [
                  DropdownMenuItem(
                    value: null,
                    child: Text(l10n.medicalNotSaid),
                  ),
                  DropdownMenuItem(
                    value: 'female',
                    child: Text(l10n.medicalSexFemale),
                  ),
                  DropdownMenuItem(
                    value: 'male',
                    child: Text(l10n.medicalSexMale),
                  ),
                ],
                onChanged: (v) => setState(() => _sex = v),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DropdownButtonFormField<String?>(
                key: const Key('medical-blood'),
                initialValue: _blood,
                decoration: InputDecoration(labelText: l10n.medicalBloodGroup),
                items: [
                  DropdownMenuItem(
                    value: null,
                    child: Text(l10n.medicalNotSaid),
                  ),
                  for (final g in MedicalFile.bloodGroups)
                    DropdownMenuItem(
                      value: g,
                      child: Text(g, textDirection: TextDirection.ltr),
                    ),
                ],
                onChanged: (v) => setState(() => _blood = v),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ListTile(
          key: const Key('medical-birth'),
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.cake),
          title: Text(l10n.medicalBirthDate),
          subtitle: Text(
            birth == null
                ? l10n.medicalNotSaid
                : '${birth.day.toString().padLeft(2, '0')}/${birth.month.toString().padLeft(2, '0')}/${birth.year}',
          ),
          trailing: birth == null
              ? null
              : IconButton(
                  tooltip: l10n.safetyDelete,
                  icon: const Icon(Icons.clear),
                  onPressed: () => setState(() => _birth = null),
                ),
          onTap: () async {
            final now = DateTime.now();
            final picked = await showDatePicker(
              context: context,
              initialDate: birth ?? DateTime(now.year - 30),
              firstDate: DateTime(1900),
              lastDate: now,
            );
            if (picked != null) setState(() => _birth = picked);
          },
        ),
        _text('allergies', l10n.medicalAllergies, lines: 3),
        _text('conditions', l10n.medicalConditions, lines: 3),
        _text('medications', l10n.medicalMedications, lines: 3),
        _text('other', l10n.medicalOther, lines: 3),
        _text('treatment_card', l10n.medicalTreatmentCard),
        _text('contact_name', l10n.medicalContactName),
        _text(
          'contact_phone',
          l10n.medicalContactPhone,
          type: TextInputType.phone,
        ),
        FilledButton.icon(
          key: const Key('medical-save'),
          onPressed: _save,
          icon: const Icon(Icons.save),
          label: Text(l10n.actionSave),
        ),
        const SizedBox(height: 8),
        SwitchListTile(
          key: const Key('medical-lock'),
          contentPadding: EdgeInsets.zero,
          value: widget.row.locked,
          onChanged: _setLock,
          title: Text(l10n.medicalLock),
          subtitle: Text(l10n.medicalLockHint),
        ),
        const Divider(),
        OutlinedButton.icon(
          key: const Key('medical-show'),
          onPressed: _show,
          icon: const Icon(Icons.visibility),
          label: Text(l10n.medicalForRescuer),
        ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          key: const Key('medical-copy'),
          onPressed: () async {
            await Clipboard.setData(
              ClipboardData(text: medicalText(l10n, _current())),
            );
            if (context.mounted) showSafetySnack(context, l10n.safetyCopied);
          },
          icon: const Icon(Icons.copy),
          label: Text(l10n.medicalCopy),
        ),
        const SizedBox(height: 16),
        Text(l10n.medicalAttachHint, style: theme.textTheme.bodySmall),
        const SizedBox(height: 16),
        TextButton.icon(
          key: const Key('medical-delete'),
          style: TextButton.styleFrom(foregroundColor: theme.colorScheme.error),
          onPressed: widget.onDelete,
          icon: const Icon(Icons.delete_forever),
          label: Text(l10n.medicalDelete),
        ),
      ],
    );
  }
}
