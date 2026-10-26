import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat, NumberFormat;

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'institution_providers.dart';
import 'institution_records.dart';
import 'institution_space.dart';
import 'kind_fields.dart';
import 'my_institution_screen.dart';
import 'org_labels.dart';
import 'org_text.dart';

/// One section of "My institution" (phases P2a and P2b): Office messages, the card with its tabs,
/// the safety team, the equipment with its maintenance log, hazardous materials, evacuation
/// points, reports, certificates, drills and events, awareness and members. Admins and editors make the quick changes here; the rest stays on
/// the institutions portal.
class InstitutionSectionScreen extends ConsumerWidget {
  const InstitutionSectionScreen({
    super.key,
    required this.orgId,
    required this.section,
  });

  final String orgId;
  final InstitutionSection section;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    if (section == InstitutionSection.card) return _CardScreen(orgId: orgId);
    final title = switch (section) {
      InstitutionSection.messages => l10n.orgSectionMessages,
      InstitutionSection.card => l10n.orgSectionCard,
      InstitutionSection.team => l10n.orgSafetyTeam,
      InstitutionSection.equipment => l10n.orgSectionEquipment,
      InstitutionSection.hazmat => l10n.orgSectionHazmat,
      InstitutionSection.evacuation => l10n.orgSectionEvacuation,
      InstitutionSection.reports => l10n.orgSectionReports,
      InstitutionSection.certificates => l10n.orgSectionCertificates,
      InstitutionSection.records => l10n.orgSectionRecords,
      InstitutionSection.activities => l10n.orgSectionActivities,
      InstitutionSection.awareness => l10n.orgSectionAwareness,
      InstitutionSection.members => l10n.orgSectionMembers,
    };
    final body = switch (section) {
      InstitutionSection.messages => OrgMessagesSection(orgId: orgId),
      InstitutionSection.activities => OrgActivitiesSection(orgId: orgId),
      InstitutionSection.awareness => OrgAwarenessSection(orgId: orgId),
      InstitutionSection.team ||
      InstitutionSection.hazmat => _FromSummary(orgId: orgId, section: section),
      InstitutionSection.equipment => _Equipment(orgId: orgId),
      InstitutionSection.evacuation => _Evacuation(orgId: orgId),
      InstitutionSection.reports => OrgReportsList(orgId: orgId),
      InstitutionSection.certificates => _Certificates(orgId: orgId),
      InstitutionSection.records => OrgRecordsSection(orgId: orgId),
      InstitutionSection.members => _Members(orgId: orgId),
      InstitutionSection.card => const SizedBox.shrink(),
    };
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        key: Key('org-section-body-${section.name}'),
        padding: const EdgeInsets.all(16),
        children: [body],
      ),
    );
  }
}

/// Error or empty text of a section.
class _Note extends StatelessWidget {
  const _Note(this.text, {this.error = false});

  final String text;
  final bool error;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24),
    child: Text(
      text,
      textAlign: TextAlign.center,
      style: error
          ? TextStyle(color: Theme.of(context).colorScheme.error)
          : null,
    ),
  );
}

Widget _loading() => const Padding(
  padding: EdgeInsets.all(24),
  child: Center(child: CircularProgressIndicator()),
);

/// Team and hazardous materials come with the summary, so they also show offline.
class _FromSummary extends ConsumerWidget {
  const _FromSummary({required this.orgId, required this.section});

  final String orgId;
  final InstitutionSection section;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    return ref
        .watch(orgSummaryProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (view) {
            final s = view.summary;
            if (section == InstitutionSection.team) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (s.team.isEmpty) _Note(l10n.orgTeamEmpty),
                  for (final m in s.team) TeamMemberTile(member: m),
                ],
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(l10n.orgHazmatTitle(s.hazmatCount)),
                if (s.hazmat.isEmpty) _Note(l10n.orgHazmatEmpty),
                for (final h in s.hazmat) HazmatTile(item: h, locale: locale),
              ],
            );
          },
        );
  }
}

// ---------------------------------------------------------------- card

/// The card in four tabs (identity, kind-specific, building, hazardous materials), each field of
/// the kind with the badge of who may see it. Admins and editors edit the kind's fields and the
/// building figures; changing the name or identifier stays on the portal (it sends the
/// institution back to review).
class _CardScreen extends ConsumerWidget {
  const _CardScreen({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final card = ref.watch(orgCardProvider(orgId));
    final data = card.value;
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l10n.orgSectionCard),
          actions: [
            if (data != null && data.canEdit)
              IconButton(
                key: const Key('org-card-edit'),
                tooltip: l10n.orgEdit,
                icon: const Icon(Icons.edit),
                onPressed: () => showModalBottomSheet<void>(
                  context: context,
                  isScrollControlled: true,
                  showDragHandle: true,
                  builder: (_) => _CardEditor(card: data),
                ),
              ),
            const StandardAppBarActions(),
          ],
          bottom: TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: l10n.orgCardTabIdentity),
              Tab(text: l10n.orgKindFieldsTitle),
              Tab(text: l10n.orgCardTabBuilding),
              Tab(text: l10n.orgSectionHazmat),
            ],
          ),
        ),
        body: card.when(
          loading: _loading,
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(16),
            children: [_Note(errorMessageFor(l10n, e), error: true)],
          ),
          data: (c) => TabBarView(
            children: [
              _Tab(children: _identity(context, c)),
              _Tab(children: _kind(context, c)),
              _Tab(children: _building(context, c)),
              _Tab(
                children: [
                  _FromSummary(
                    orgId: orgId,
                    section: InstitutionSection.hazmat,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _identity(BuildContext context, OrgCardData c) {
    final l10n = AppLocalizations.of(context);
    final manager = c.manager;
    return [
      _Line(l10n.orgName, c.name, FieldVisibility.public),
      _Line(
        l10n.orgKindLabelTitle,
        orgKindLabel(l10n, c.kind),
        FieldVisibility.public,
      ),
      _Line(
        c.identifierType == 'rne'
            ? l10n.orgIdentifierRne
            : l10n.orgIdentifierMf,
        c.identifier,
        FieldVisibility.orgOffice,
        ltr: true,
      ),
      if (manager['full_name'] case final String name)
        _Line(l10n.orgManagerName, name, FieldVisibility.orgOffice),
      if (manager['phone'] case final String phone)
        _Line(
          l10n.orgManagerPhone,
          phone,
          FieldVisibility.orgOffice,
          ltr: true,
        ),
      if (c.contactEmail case final String email)
        _Line(
          l10n.orgContactEmail,
          email,
          FieldVisibility.orgOffice,
          ltr: true,
        ),
      _Line(
        l10n.orgAddress,
        c.address ?? l10n.orgNotSet,
        FieldVisibility.public,
      ),
    ];
  }

  List<Widget> _kind(BuildContext context, OrgCardData c) {
    final l10n = AppLocalizations.of(context);
    final specs = kindFields[c.kind] ?? const <KindField>[];
    final values = c.kindFields;
    return [
      Align(
        alignment: AlignmentDirectional.centerStart,
        child: Pill(
          l10n.orgKindFieldsSim,
          tone: Tone.amber,
          icon: Icons.science,
        ),
      ),
      const SizedBox(height: 8),
      if (specs.isEmpty) _Note(l10n.orgKindFieldsEmpty),
      for (final f in specs) KindFieldRow(field: f, value: values[f.key]),
    ];
  }

  List<Widget> _building(BuildContext context, OrgCardData c) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final number = NumberFormat.decimalPattern(locale);
    return [
      _Line(
        l10n.orgCapacity,
        c.capacity == null ? l10n.orgNotSet : number.format(c.capacity),
        FieldVisibility.orgOffice,
      ),
      _Line(
        l10n.orgFloors,
        c.floors == null ? l10n.orgNotSet : number.format(c.floors),
        FieldVisibility.orgOffice,
      ),
      _Line(
        l10n.orgHeight,
        c.heightM == null ? l10n.orgNotSet : number.format(c.heightM),
        FieldVisibility.orgOffice,
      ),
      _Line(
        l10n.orgReceivesPublic,
        c.receivesPublic ? l10n.orgYes : l10n.orgNo,
        FieldVisibility.orgOffice,
      ),
    ];
  }
}

class _Tab extends StatelessWidget {
  const _Tab({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: children,
        ),
      ),
    ],
  );
}

/// Label, value and the badge of who may see it.
class _Line extends StatelessWidget {
  const _Line(this.label, this.value, this.visibility, {this.ltr = false});

  final String label;
  final String value;
  final FieldVisibility visibility;
  final bool ltr;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: theme.textTheme.bodySmall),
        Text(
          value,
          style: theme.textTheme.bodyLarge,
          textDirection: ltr ? TextDirection.ltr : null,
        ),
      ],
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: PillBeside(pill: VisibilityPill(visibility), child: text),
    );
  }
}

/// Edits the kind's fields and the building figures, then saves the whole card with its version.
class _CardEditor extends ConsumerStatefulWidget {
  const _CardEditor({required this.card});

  final OrgCardData card;

  @override
  ConsumerState<_CardEditor> createState() => _CardEditorState();
}

class _CardEditorState extends ConsumerState<_CardEditor> {
  late final Map<String, Object?> _values = {
    for (final e in widget.card.kindFields.entries)
      e.key: e.value is bool ? e.value : '${e.value}',
  };
  late final _capacity = TextEditingController(
    text: widget.card.capacity?.toString() ?? '',
  );
  late final _floors = TextEditingController(
    text: widget.card.floors?.toString() ?? '',
  );
  late bool _receivesPublic = widget.card.receivesPublic;
  bool _busy = false;
  bool _submitted = false;
  String? _error;

  @override
  void dispose() {
    _capacity.dispose();
    _floors.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final l10n = AppLocalizations.of(context);
    final specs = kindFields[widget.card.kind] ?? const <KindField>[];
    setState(() => _submitted = true);
    final bad = specs.any(
      (f) => kindFieldError(l10n, f, _values[f.key]) != null,
    );
    final capacity = int.tryParse(_capacity.text.trim());
    final floors = _floors.text.trim().isEmpty
        ? null
        : int.tryParse(_floors.text.trim());
    if (bad ||
        capacity == null ||
        (_floors.text.trim().isNotEmpty && floors == null)) {
      setState(() => _error = l10n.orgInvalidNumber);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      await ref
          .read(apiProvider)
          .updateOrg(
            widget.card.id,
            widget.card.toUpdate({
              'kind_fields': kindFieldsToJson(widget.card.kind, _values),
              'capacity': capacity,
              'floors': floors,
              'receives_public': _receivesPublic,
            }),
          );
      ref.invalidate(orgCardProvider(widget.card.id));
      ref.invalidate(orgSummaryProvider(widget.card.id));
      navigator.pop();
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.orgSaved)));
    } on ApiException catch (e) {
      if (e.code == ApiErrorCode.versionConflict) {
        ref.invalidate(orgCardProvider(widget.card.id));
      }
      setState(() {
        _busy = false;
        _error = e.code == ApiErrorCode.versionConflict
            ? l10n.orgVersionConflict
            : apiErrorMessage(l10n, e.code);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final specs = kindFields[widget.card.kind] ?? const <KindField>[];
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionTitle(l10n.orgCardTabBuilding),
            TextField(
              key: const Key('edit-capacity'),
              controller: _capacity,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(labelText: l10n.orgCapacity),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('edit-floors'),
              controller: _floors,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(labelText: l10n.orgFloors),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l10n.orgReceivesPublic),
              value: _receivesPublic,
              onChanged: (v) => setState(() => _receivesPublic = v),
            ),
            if (specs.isNotEmpty) ...[
              SectionTitle(l10n.orgKindFieldsTitle),
              KindFieldInputs(
                kind: widget.card.kind,
                values: _values,
                showErrors: _submitted,
                onChanged: (k, v) => setState(() => _values[k] = v),
              ),
            ],
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 12),
            FilledButton(
              key: const Key('org-card-save'),
              onPressed: _busy ? null : _save,
              child: Text(l10n.orgSave),
            ),
          ],
        ),
      ),
    );
  }
}

/// Form inputs of the kind's fields, each with the badge of who may see it.
class KindFieldInputs extends StatelessWidget {
  const KindFieldInputs({
    super.key,
    required this.kind,
    required this.values,
    required this.onChanged,
    this.showErrors = false,
  });

  final String kind;
  final Map<String, Object?> values;
  final void Function(String key, Object? value) onChanged;
  final bool showErrors;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final specs = kindFields[kind] ?? const <KindField>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: Pill(
            l10n.orgKindFieldsSim,
            tone: Tone.amber,
            icon: Icons.science,
          ),
        ),
        for (final f in specs)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: f.type == KindFieldType.bool
                ? SwitchListTile(
                    key: Key('kf-${f.key}'),
                    contentPadding: EdgeInsets.zero,
                    title: Text(kindFieldText(l10n, f.key)),
                    subtitle: Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: VisibilityPill(f.visibility),
                    ),
                    value: values[f.key] == true,
                    onChanged: (v) => onChanged(f.key, v),
                  )
                : TextFormField(
                    key: Key('kf-${f.key}'),
                    initialValue: values[f.key] is String
                        ? values[f.key]! as String
                        : '',
                    keyboardType: f.type == KindFieldType.int
                        ? TextInputType.number
                        : f.key == 'reception_phone'
                        ? TextInputType.phone
                        : TextInputType.text,
                    textDirection: f.key == 'reception_phone'
                        ? TextDirection.ltr
                        : null,
                    decoration: InputDecoration(
                      labelText: kindFieldText(l10n, f.key),
                      suffixIcon: Padding(
                        padding: const EdgeInsetsDirectional.only(end: 8),
                        child: VisibilityPill(f.visibility),
                      ),
                      suffixIconConstraints: const BoxConstraints(),
                      errorText: showErrors
                          ? kindFieldError(l10n, f, values[f.key])
                          : null,
                    ),
                    onChanged: (v) => onChanged(f.key, v),
                  ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------- equipment

class _Equipment extends ConsumerWidget {
  const _Equipment({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final role = ref.watch(myOrgRoleProvider(orgId));
    final canEdit = role == 'admin' || role == 'editor';
    return ref
        .watch(orgEquipmentProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgEquipmentEmpty),
              for (final e in items) ...[
                _EquipmentCard(orgId: orgId, item: e, canEdit: canEdit),
                const SizedBox(height: 8),
              ],
            ],
          ),
        );
  }
}

class _EquipmentCard extends ConsumerStatefulWidget {
  const _EquipmentCard({
    required this.orgId,
    required this.item,
    required this.canEdit,
  });

  final String orgId;
  final OrgEquipment item;
  final bool canEdit;

  @override
  ConsumerState<_EquipmentCard> createState() => _EquipmentCardState();
}

class _EquipmentCardState extends ConsumerState<_EquipmentCard> {
  bool _history = false;

  void _log() => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => MaintenanceSheet(orgId: widget.orgId, item: widget.item),
  );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final e = widget.item;
    final (tone, label) = switch (e.maintenanceStatus) {
      'ok' => (Tone.green, l10n.orgMaintenanceOk),
      'due_soon' => (Tone.amber, l10n.orgMaintenanceDueSoon),
      'overdue' => (Tone.red, l10n.orgMaintenanceOverdue),
      _ => (Tone.slate, l10n.orgMaintenanceUnknown),
    };
    final next = e.nextMaintenanceOn;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const IconTile(Icons.fire_extinguisher, tone: Tone.red),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      equipmentKindText(l10n, e.kind),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(l10n.orgEquipmentCount(e.count)),
                    if (e.location case final String where) Text(where),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Pill(label, tone: tone),
              if (next != null)
                Text(
                  l10n.orgMaintenanceNext(
                    DateFormat.yMMMd(locale).format(next),
                  ),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
            ],
          ),
          Wrap(
            alignment: WrapAlignment.end,
            spacing: 8,
            children: [
              TextButton.icon(
                key: Key('maintenance-history-toggle-${e.id}'),
                onPressed: () => setState(() => _history = !_history),
                icon: Icon(_history ? Icons.expand_less : Icons.history),
                label: Text(l10n.orgMaintenanceHistory),
              ),
              if (widget.canEdit)
                TextButton.icon(
                  key: Key('log-maintenance-${e.id}'),
                  onPressed: _log,
                  icon: const Icon(Icons.build),
                  label: Text(l10n.orgLogMaintenance),
                ),
            ],
          ),
          if (_history) MaintenanceHistory(orgId: widget.orgId, itemId: e.id),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- evacuation, certificates

class _Evacuation extends ConsumerWidget {
  const _Evacuation({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return ref
        .watch(orgFeaturesProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgEvacuationEmpty),
              for (final f in items) ...[
                NavCard(
                  icon: switch (f.kind) {
                    'water_point' => Icons.water_drop,
                    'alarm' => Icons.notifications_active,
                    _ => Icons.directions_run,
                  },
                  tone: f.kind == 'evacuation_point' ? Tone.green : Tone.sky,
                  title: f.label ?? featureKindText(l10n, f.kind),
                  subtitle: [
                    if (f.label != null) featureKindText(l10n, f.kind),
                    if (f.location case final GeoPoint p)
                      '${p.lat.toStringAsFixed(5)}, ${p.lon.toStringAsFixed(5)}',
                  ].join(' · '),
                ),
                const SizedBox(height: 8),
              ],
            ],
          ),
        );
  }
}

class _Certificates extends ConsumerWidget {
  const _Certificates({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    return ref
        .watch(orgCertificatesProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgCertificatesEmpty),
              for (final c in items) ...[
                NavCard(
                  icon: Icons.verified,
                  tone: c.status == 'approved' ? Tone.green : Tone.slate,
                  title: c.code,
                  subtitle: [
                    certificateStatusText(l10n, c.status),
                    if (c.validUntil case final DateTime until)
                      l10n.orgCertificateValidUntil(
                        DateFormat.yMMMd(locale).format(until),
                      ),
                  ].join(' · '),
                ),
                if (c.needsUpdate != null || c.stamps.isNotEmpty)
                  _CertificateExtras(certificate: c),
                const SizedBox(height: 8),
              ],
            ],
          ),
        );
  }
}

/// Phase P3a under the current certificate: "needs updating" with the sections that changed (the new
/// certificate is generated on the portal), and the stamps put at regional administrations.
class _CertificateExtras extends StatelessWidget {
  const _CertificateExtras({required this.certificate});

  final OrgCertificate certificate;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final c = certificate;
    final sections = {
      for (final change in c.changes)
        certificateSectionText(l10n, change.section),
    };
    return Padding(
      padding: const EdgeInsetsDirectional.only(start: 12, top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (c.needsUpdate == true) ...[
            Pill(l10n.orgCertNeedsUpdate, tone: Tone.amber, icon: Icons.update),
            const SizedBox(height: 4),
            Text(
              l10n.orgCertNeedsUpdateBody(
                sections.join(locale == 'ar' ? '، ' : ', '),
              ),
              key: Key('cert-changes-${c.code}'),
            ),
          ] else if (c.needsUpdate == false)
            Pill(l10n.orgCertUpToDate, tone: Tone.green, icon: Icons.check),
          for (final s in c.stamps) ...[
            const SizedBox(height: 6),
            Pill(
              [
                l10n.orgCertStamped,
                s.place,
                if (s.stampedOn case final DateTime on)
                  DateFormat.yMMMd(locale).format(on),
              ].join(' · '),
              tone: Tone.navy,
              icon: Icons.approval,
            ),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- members

class _Members extends ConsumerWidget {
  const _Members({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final isAdmin = ref.watch(myOrgRoleProvider(orgId)) == 'admin';
    return ref
        .watch(orgMembersProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgMembersEmpty),
              for (final m in items) ...[
                AppCard(
                  child: Row(
                    children: [
                      const IconTile(Icons.person, tone: Tone.sky, soft: true),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.displayName ?? m.email ?? ''),
                            if (m.email case final String email)
                              Text(
                                email,
                                textDirection: TextDirection.ltr,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                          ],
                        ),
                      ),
                      Pill(
                        orgRoleText(l10n, m.role),
                        tone: m.role == 'admin' ? Tone.navy : Tone.slate,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
              ],
              if (isAdmin) _InviteForm(orgId: orgId),
            ],
          ),
        );
  }
}

class _InviteForm extends ConsumerStatefulWidget {
  const _InviteForm({required this.orgId});

  final String orgId;

  @override
  ConsumerState<_InviteForm> createState() => _InviteFormState();
}

class _InviteFormState extends ConsumerState<_InviteForm> {
  final _email = TextEditingController();
  String _role = 'member';
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    final email = _email.text.trim();
    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(email)) {
      setState(() => _error = l10n.orgInvalidEmail);
      return;
    }
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(apiProvider).inviteOrgMember(widget.orgId, email, _role);
      _email.clear();
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(l10n.orgInviteSent(email))));
    } on ApiException catch (e) {
      setState(() => _error = apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(l10n.orgInvite, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            key: const Key('invite-email'),
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            textDirection: TextDirection.ltr,
            decoration: InputDecoration(
              labelText: l10n.orgInviteEmail,
              errorText: _error,
            ),
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            key: const Key('invite-role'),
            initialValue: _role,
            decoration: InputDecoration(labelText: l10n.orgInviteRole),
            items: [
              for (final r in const ['member', 'editor', 'admin'])
                DropdownMenuItem(value: r, child: Text(orgRoleText(l10n, r))),
            ],
            onChanged: (v) => setState(() => _role = v ?? 'member'),
          ),
          const SizedBox(height: 12),
          FilledButton(
            key: const Key('invite-send'),
            onPressed: _busy ? null : _send,
            child: Text(l10n.orgInviteSend),
          ),
        ],
      ),
    );
  }
}
