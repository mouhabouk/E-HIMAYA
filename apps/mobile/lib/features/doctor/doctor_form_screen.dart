import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/http/doctor_models.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/required_label.dart';
import '../../l10n/app_localizations.dart';
import '../profile/profile_screen.dart';
import '../volunteer/volunteer_screen.dart';
import 'doctor_labels.dart';
import 'doctor_providers.dart';

/// Doctor registration (phase C1-a): role, specialties, registration number, workplace and its
/// gouvernorat (the doctor's group), and for a Civil Protection doctor their unit and staff
/// number. Also edits it: what staff checked changing sends it back to review.
class DoctorFormScreen extends ConsumerStatefulWidget {
  const DoctorFormScreen({super.key, this.kind});

  /// The role chosen on the intro screen (a new registration).
  final DoctorKind? kind;

  @override
  ConsumerState<DoctorFormScreen> createState() => _DoctorFormScreenState();
}

class _DoctorFormScreenState extends ConsumerState<DoctorFormScreen> {
  final _licence = TextEditingController();
  final _workplace = TextEditingController();
  final _cpUnit = TextEditingController();
  final _cpStaffNo = TextEditingController();
  final _specialties = <DoctorSpecialty>{};
  var _kind = DoctorKind.volunteer;
  int? _gouvernorat;
  int? _version;
  bool _terms = false;
  bool _busy = false;
  bool _showErrors = false;

  @override
  void initState() {
    super.initState();
    final current = ref.read(doctorProvider).value;
    if (current != null) {
      _kind = current.kind;
      _specialties.addAll(current.specialties);
      _licence.text = current.licenceNo ?? '';
      _workplace.text = current.workplace == '--' ? '' : current.workplace;
      _cpUnit.text = current.cpUnit ?? '';
      _cpStaffNo.text = current.cpStaffNo ?? '';
      _gouvernorat = current.gouvernoratCode;
      _version = current.version;
      // The terms were accepted with the registration; a withdrawn doctor accepts them again.
      _terms = current.status != VolunteerStatus.withdrawn;
    }
    if (widget.kind != null) _kind = widget.kind!;
  }

  @override
  void dispose() {
    _licence.dispose();
    _workplace.dispose();
    _cpUnit.dispose();
    _cpStaffNo.dispose();
    super.dispose();
  }

  bool get _civil => _kind == DoctorKind.civilProtection;
  bool get _specialtiesOk =>
      _specialties.isNotEmpty && _specialties.length <= DoctorSpecialty.max;
  bool _number(TextEditingController c) =>
      doctorNumberPattern.hasMatch(c.text.trim());
  bool get _workplaceOk => _workplace.text.trim().length >= 2;
  bool get _cpUnitOk => !_civil || _cpUnit.text.trim().length >= 2;
  bool get _cpStaffOk => !_civil || _number(_cpStaffNo);

  bool get _valid =>
      _specialtiesOk &&
      _number(_licence) &&
      _workplaceOk &&
      _gouvernorat != null &&
      _cpUnitOk &&
      _cpStaffOk &&
      _terms;

  Future<void> _submit() async {
    setState(() => _showErrors = true);
    if (!_valid) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(doctorProvider.notifier)
          .submit(
            DoctorInput(
              kind: _kind,
              specialties: _specialties,
              licenceNo: _licence.text,
              workplace: _workplace.text,
              gouvernoratCode: _gouvernorat!,
              cpUnit: _cpUnit.text,
              cpStaffNo: _cpStaffNo.text,
              version: _version,
            ),
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).doctorSubmitted)),
      );
      context.pop();
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String? _error(bool ok, String message) =>
      _showErrors && !ok ? message : null;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final gouvernorats = ref.watch(gouvernoratsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.doctorApply),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.doctorKind, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            SegmentedButton<DoctorKind>(
              key: const Key('doctor-kind'),
              segments: [
                for (final k in DoctorKind.values)
                  ButtonSegment(
                    value: k,
                    label: Text(doctorKindLabel(l10n, k)),
                  ),
              ],
              selected: {_kind},
              onSelectionChanged: (s) => setState(() => _kind = s.first),
            ),
            const SizedBox(height: 16),
            Text(l10n.doctorSpecialties, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                for (final s in DoctorSpecialty.values)
                  FilterChip(
                    key: Key('specialty-${s.wire}'),
                    label: Text(specialtyLabel(l10n, s)),
                    selected: _specialties.contains(s),
                    onSelected:
                        !_specialties.contains(s) &&
                            _specialties.length >= DoctorSpecialty.max
                        ? null
                        : (on) => setState(
                            () => on
                                ? _specialties.add(s)
                                : _specialties.remove(s),
                          ),
                  ),
              ],
            ),
            if (_showErrors && !_specialtiesOk)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  l10n.doctorSpecialtiesRequired,
                  style: TextStyle(color: theme.colorScheme.error),
                ),
              ),
            const SizedBox(height: 16),
            TextField(
              key: const Key('doctor-licence'),
              controller: _licence,
              maxLength: 30,
              textDirection: TextDirection.ltr,
              decoration: InputDecoration(
                label: RequiredLabel(l10n.doctorLicence),
                errorText: _error(_number(_licence), l10n.doctorNumberInvalid),
              ),
              onChanged: (_) => setState(() {}),
            ),
            TextField(
              key: const Key('doctor-workplace'),
              controller: _workplace,
              maxLength: 150,
              decoration: InputDecoration(
                label: RequiredLabel(l10n.doctorWorkplace),
                errorText: _error(_workplaceOk, l10n.fieldRequired),
              ),
              onChanged: (_) => setState(() {}),
            ),
            gouvernorats.when(
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => TextButton(
                onPressed: () => ref.invalidate(gouvernoratsProvider),
                child: Text(l10n.geoLoadFailed),
              ),
              data: (list) => DropdownButtonFormField<int>(
                key: const Key('doctor-gouvernorat'),
                initialValue: list.any((g) => g.code == _gouvernorat)
                    ? _gouvernorat
                    : null,
                isExpanded: true,
                decoration: InputDecoration(
                  label: RequiredLabel(l10n.doctorGouvernorat),
                  helperText: l10n.doctorGouvernoratHelp,
                  errorText: _error(_gouvernorat != null, l10n.fieldRequired),
                ),
                items: [
                  for (final g in list)
                    DropdownMenuItem(value: g.code, child: Text(g.name)),
                ],
                onChanged: (v) => setState(() => _gouvernorat = v),
              ),
            ),
            if (_civil) ...[
              const SizedBox(height: 12),
              TextField(
                key: const Key('doctor-cp-unit'),
                controller: _cpUnit,
                maxLength: 150,
                decoration: InputDecoration(
                  label: RequiredLabel(l10n.doctorCpUnit),
                  errorText: _error(_cpUnitOk, l10n.fieldRequired),
                ),
                onChanged: (_) => setState(() {}),
              ),
              TextField(
                key: const Key('doctor-cp-staff'),
                controller: _cpStaffNo,
                maxLength: 30,
                textDirection: TextDirection.ltr,
                decoration: InputDecoration(
                  label: RequiredLabel(l10n.doctorCpStaffNo),
                  errorText: _error(_cpStaffOk, l10n.doctorNumberInvalid),
                ),
                onChanged: (_) => setState(() {}),
              ),
            ],
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.doctorTermsTitle,
                      style: theme.textTheme.titleSmall,
                    ),
                    const SizedBox(height: 6),
                    Text(l10n.doctorTermsBody),
                    CheckboxListTile(
                      key: const Key('doctor-terms'),
                      contentPadding: EdgeInsets.zero,
                      value: _terms,
                      onChanged: (v) => setState(() => _terms = v ?? false),
                      title: Text(l10n.doctorTermsAccept),
                      subtitle: _showErrors && !_terms
                          ? Text(
                              l10n.doctorTermsRequired,
                              style: TextStyle(color: theme.colorScheme.error),
                            )
                          : null,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(l10n.doctorRecheckNote, style: theme.textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton(
              key: const Key('doctor-submit'),
              onPressed: _busy ? null : _submit,
              child: _busy
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(l10n.doctorSubmit),
            ),
          ],
        ),
      ),
    );
  }
}
