import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/providers.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import 'volunteer_providers.dart';
import 'volunteer_screen.dart';

/// Volunteer application (FR-A-020): skills, availability and period. Also used to edit it
/// (changing skills of an approved volunteer sends the application back to review).
class VolunteerFormScreen extends ConsumerStatefulWidget {
  const VolunteerFormScreen({super.key});

  @override
  ConsumerState<VolunteerFormScreen> createState() =>
      _VolunteerFormScreenState();
}

class _VolunteerFormScreenState extends ConsumerState<VolunteerFormScreen> {
  final _otherSkill = TextEditingController();
  final _notes = TextEditingController();
  final _skills = <VolunteerSkill>{};
  var _availability = VolunteerAvailability.continuous;
  late DateTime _from;
  DateTime? _to;
  int? _version;
  bool _busy = false;
  bool _showErrors = false;

  @override
  void initState() {
    super.initState();
    final now = ref.read(clockProvider)();
    _from = DateTime(now.year, now.month, now.day);
    final current = ref.read(volunteerProvider).value;
    if (current != null) {
      _skills.addAll(current.skills);
      _otherSkill.text = current.otherSkill ?? '';
      _notes.text = current.notes ?? '';
      _availability = current.availability;
      _version = current.version;
      if (!current.status.canResubmit) {
        _from = current.periodFrom;
        _to = current.periodTo;
      }
    }
  }

  @override
  void dispose() {
    _otherSkill.dispose();
    _notes.dispose();
    super.dispose();
  }

  bool get _valid =>
      _skills.isNotEmpty &&
      (!_skills.contains(VolunteerSkill.other) ||
          _otherSkill.text.trim().isNotEmpty) &&
      (_to == null || !_to!.isBefore(_from));

  Future<void> _pick({required bool from}) async {
    final now = ref.read(clockProvider)();
    final today = DateTime(now.year, now.month, now.day);
    final picked = await showDatePicker(
      context: context,
      initialDate: from ? _from : (_to ?? _from),
      firstDate: from ? (_from.isBefore(today) ? _from : today) : _from,
      // The server accepts a period ending at most two years ahead.
      lastDate: DateTime(today.year + 2, today.month, today.day),
    );
    if (picked == null) return;
    setState(() {
      if (from) {
        _from = picked;
        if (_to != null && _to!.isBefore(picked)) _to = picked;
      } else {
        _to = picked;
      }
    });
  }

  Future<void> _submit() async {
    setState(() => _showErrors = true);
    if (!_valid) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(volunteerProvider.notifier)
          .submit(
            VolunteerInput(
              skills: _skills,
              otherSkill: _otherSkill.text,
              availability: _availability,
              periodFrom: _from,
              periodTo: _to,
              notes: _notes.text,
              version: _version,
            ),
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context).volunteerSubmitted),
        ),
      );
      context.pop();
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.volunteerApply),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.volunteerSkills, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                for (final s in VolunteerSkill.values)
                  FilterChip(
                    key: Key('skill-${s.wire}'),
                    label: Text(skillLabel(l10n, s)),
                    selected: _skills.contains(s),
                    onSelected: (on) =>
                        setState(() => on ? _skills.add(s) : _skills.remove(s)),
                  ),
              ],
            ),
            if (_showErrors && _skills.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  l10n.volunteerSkillsRequired,
                  style: TextStyle(color: theme.colorScheme.error),
                ),
              ),
            if (_skills.contains(VolunteerSkill.other)) ...[
              const SizedBox(height: 12),
              TextField(
                key: const Key('other-skill'),
                controller: _otherSkill,
                maxLength: 100,
                decoration: InputDecoration(
                  labelText: l10n.volunteerOtherSkill,
                  errorText: _showErrors && _otherSkill.text.trim().isEmpty
                      ? l10n.fieldRequired
                      : null,
                ),
                onChanged: (_) => setState(() {}),
              ),
            ],
            const SizedBox(height: 16),
            Text(
              l10n.volunteerAvailability,
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            SegmentedButton<VolunteerAvailability>(
              segments: [
                ButtonSegment(
                  value: VolunteerAvailability.continuous,
                  label: Text(l10n.availabilityContinuous),
                ),
                ButtonSegment(
                  value: VolunteerAvailability.intermittent,
                  label: Text(l10n.availabilityIntermittent),
                ),
              ],
              selected: {_availability},
              onSelectionChanged: (s) =>
                  setState(() => _availability = s.first),
            ),
            const SizedBox(height: 16),
            Text(l10n.volunteerPeriod, style: theme.textTheme.titleMedium),
            ListTile(
              key: const Key('period-from'),
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.event),
              title: Text(l10n.volunteerFrom),
              subtitle: Text(dateLabel(context, _from)),
              onTap: () => _pick(from: true),
            ),
            ListTile(
              key: const Key('period-to'),
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.event_available),
              title: Text(l10n.volunteerTo),
              subtitle: Text(
                _to == null ? l10n.volunteerNoEnd : dateLabel(context, _to!),
              ),
              trailing: _to == null
                  ? null
                  : IconButton(
                      tooltip: l10n.volunteerNoEnd,
                      icon: const Icon(Icons.clear),
                      onPressed: () => setState(() => _to = null),
                    ),
              onTap: () => _pick(from: false),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('volunteer-notes'),
              controller: _notes,
              maxLength: 500,
              maxLines: 3,
              decoration: InputDecoration(labelText: l10n.volunteerNotes),
            ),
            const SizedBox(height: 8),
            Text(l10n.volunteerProfileNote, style: theme.textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton(
              key: const Key('volunteer-submit'),
              onPressed: _busy ? null : _submit,
              child: _busy
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(l10n.volunteerSubmit),
            ),
          ],
        ),
      ),
    );
  }
}
