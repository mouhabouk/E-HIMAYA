import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/required_label.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'email_confirm.dart';
import 'institution_providers.dart';
import 'institution_sections.dart' show KindFieldInputs;
import 'kind_fields.dart';
import 'org_labels.dart';
import 'org_text.dart';

/// Matricule fiscal: 7 digits, a letter, optionally /letter/letter/3 digits; RNE: 7 digits and a
/// letter (phase 4 §1). The server stays the authority.
final _mf = RegExp(r'^\d{7}[A-Z](/[A-Z]/[A-Z]/\d{3})?$');
final _rne = RegExp(r'^\d{7}[A-Z]$');

String normalizeIdentifier(String raw) =>
    raw.replaceAll(RegExp(r'\s+'), '').toUpperCase();

/// "20 123 456", "0021620123456" and "+216 20-123-456" all become "+21620123456".
String normalizeTunisianPhone(String raw) {
  var v = raw.replaceAll(RegExp(r'[\s.-]'), '');
  if (RegExp(r'^\d{8}$').hasMatch(v)) v = '+216$v';
  if (v.startsWith('00216')) v = '+${v.substring(2)}';
  return v;
}

bool isTunisianPhone(String raw) =>
    RegExp(r'^\+216\d{8}$').hasMatch(normalizeTunisianPhone(raw));

/// Registering an institution from the phone (phase P2a, addition 12 §3.1): the kind from a grid,
/// then the identifier and contact, then the location and building, then a review. The account
/// needs a confirmed e-mail; the institution stays under review until the Office approves it.
class RegisterInstitutionScreen extends ConsumerStatefulWidget {
  const RegisterInstitutionScreen({super.key});

  @override
  ConsumerState<RegisterInstitutionScreen> createState() =>
      _RegisterInstitutionScreenState();
}

class _RegisterInstitutionScreenState
    extends ConsumerState<RegisterInstitutionScreen> {
  static const _steps = 4;
  int _step = 1;
  String? _kind;
  String _identifierType = 'mf';
  final _name = TextEditingController();
  final _identifier = TextEditingController();
  final _managerName = TextEditingController();
  final _managerPhone = TextEditingController();
  final _contactEmail = TextEditingController();
  final _address = TextEditingController();
  final _capacity = TextEditingController();
  final _floors = TextEditingController();
  final _lat = TextEditingController();
  final _lon = TextEditingController();
  bool _receivesPublic = false;
  final Map<String, Object?> _kindValues = {};
  final Map<String, String> _errors = {};
  bool _locating = false;
  bool _busy = false;
  String? _sendError;
  OrgCardData? _created;

  @override
  void dispose() {
    for (final c in [
      _name,
      _identifier,
      _managerName,
      _managerPhone,
      _contactEmail,
      _address,
      _capacity,
      _floors,
      _lat,
      _lon,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  GeoPoint? get _location {
    final lat = double.tryParse(_lat.text.trim().replaceAll(',', '.'));
    final lon = double.tryParse(_lon.text.trim().replaceAll(',', '.'));
    return lat == null || lon == null ? null : GeoPoint(lat: lat, lon: lon);
  }

  Map<String, String> _check(int step) {
    final l10n = AppLocalizations.of(context);
    final e = <String, String>{};
    void required(String key, TextEditingController c) {
      if (c.text.trim().isEmpty) e[key] = l10n.fieldRequired;
    }

    switch (step) {
      case 1:
        if (_kind == null) e['kind'] = l10n.fieldRequired;
      case 2:
        if (_name.text.trim().length < 2) e['name'] = l10n.fieldRequired;
        final id = normalizeIdentifier(_identifier.text);
        if (id.isEmpty) {
          e['identifier'] = l10n.fieldRequired;
        } else if (!(_identifierType == 'mf' ? _mf : _rne).hasMatch(id)) {
          e['identifier'] = l10n.orgInvalidIdentifier;
        }
        required('manager_name', _managerName);
        if (_managerPhone.text.trim().isEmpty) {
          e['manager_phone'] = l10n.fieldRequired;
        } else if (!isTunisianPhone(_managerPhone.text)) {
          e['manager_phone'] = l10n.orgInvalidPhone;
        }
        final email = _contactEmail.text.trim();
        if (email.isNotEmpty &&
            !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(email)) {
          e['contact_email'] = l10n.orgInvalidEmail;
        }
      case 3:
        final p = _location;
        if (p == null || !p.isInTunisiaBox) {
          e['location'] = l10n.orgLocationRequired;
        }
        required('address', _address);
        final capacity = int.tryParse(_capacity.text.trim());
        if (_capacity.text.trim().isEmpty) {
          e['capacity'] = l10n.fieldRequired;
        } else if (capacity == null || capacity < 0) {
          e['capacity'] = l10n.orgInvalidNumber;
        }
        if (_floors.text.trim().isNotEmpty &&
            (int.tryParse(_floors.text.trim()) ?? -1) < 0) {
          e['floors'] = l10n.orgInvalidNumber;
        }
        for (final f in kindFields[_kind] ?? const <KindField>[]) {
          final err = kindFieldError(l10n, f, _kindValues[f.key]);
          if (err != null) e['kf'] = err;
        }
        final phone = _kindValues['reception_phone'];
        if (phone is String &&
            phone.trim().isNotEmpty &&
            !isTunisianPhone(phone)) {
          e['kf'] = l10n.orgInvalidPhone;
        }
    }
    return e;
  }

  void _next() {
    final found = _check(_step);
    setState(() {
      _errors
        ..clear()
        ..addAll(found);
      if (found.isEmpty && _step < _steps) _step++;
    });
  }

  Future<void> _locate() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _locating = true);
    final p = await ref
        .read(locationServiceProvider)
        .bestEffort(timeout: const Duration(seconds: 8));
    if (!mounted) return;
    setState(() {
      _locating = false;
      if (p != null) {
        _lat.text = p.lat.toStringAsFixed(6);
        _lon.text = p.lon.toStringAsFixed(6);
        _errors.remove('location');
      }
    });
    if (p == null) {
      messenger.showSnackBar(
        SnackBar(content: Text(l10n.orgLocationUnavailable)),
      );
    }
  }

  Map<String, Object?> _body() {
    final reception = _kindValues['reception_phone'];
    final kf = kindFieldsToJson(_kind!, {
      ..._kindValues,
      if (reception is String && reception.trim().isNotEmpty)
        'reception_phone': normalizeTunisianPhone(reception),
    });
    final email = _contactEmail.text.trim();
    return {
      'name': _name.text.trim(),
      'kind': _kind,
      'identifier_type': _identifierType,
      'identifier': normalizeIdentifier(_identifier.text),
      'capacity': int.tryParse(_capacity.text.trim()),
      'floors': int.tryParse(_floors.text.trim()),
      'receives_public': _receivesPublic,
      'address': _address.text.trim(),
      'location': _location!.toJson(),
      'manager': {
        'full_name': _managerName.text.trim(),
        'phone': normalizeTunisianPhone(_managerPhone.text),
      },
      'contact_email': email.isEmpty ? null : email,
      'kind_fields': kf,
    };
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    setState(() {
      _busy = true;
      _sendError = null;
    });
    try {
      final created = await ref.read(apiProvider).registerOrg(_body());
      await ref.read(myOrgsProvider.notifier).refresh();
      if (mounted) setState(() => _created = created);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _sendError = apiErrorMessage(l10n, e.code);
        if (e.code == ApiErrorCode.invalidIdentifier ||
            e.code == ApiErrorCode.identifierAlreadyRegistered) {
          _step = 2;
          _errors['identifier'] = _sendError!;
        }
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final created = _created;
    final title = switch (_step) {
      1 => l10n.orgRegisterKindTitle,
      2 => l10n.orgRegisterIdentityTitle,
      3 => l10n.orgRegisterLocationTitle,
      _ => l10n.orgRegisterReviewTitle,
    };
    // Phase P5b (F-APP-12): an account signed in with a phone number confirms its work e-mail
    // first. If the check fails the form stays open; the server has the last word.
    final email = ref.watch(myEmailProvider);
    final needsEmail = created == null && email.value?.verified == false;
    if (created == null && email.isLoading && !email.hasValue) {
      return Scaffold(
        appBar: AppBar(
          title: Text(l10n.orgRegister),
          actions: const [StandardAppBarActions()],
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.orgRegister),
        actions: const [StandardAppBarActions()],
      ),
      body: needsEmail
          ? EmailConfirmPanel(initial: email.value?.email)
          : created != null
          ? _Done(created: created)
          : ListView(
              key: const Key('org-register-form'),
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: [
                StepBar(
                  current: _step,
                  total: _steps,
                  label: l10n.orgRegisterStep(_step, _steps),
                ),
                const SizedBox(height: 8),
                Text(
                  l10n.orgRegisterStep(_step, _steps),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                Semantics(
                  header: true,
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                const SizedBox(height: 12),
                ...switch (_step) {
                  1 => _kindStep(l10n),
                  2 => _identityStep(l10n),
                  3 => _locationStep(l10n),
                  _ => _reviewStep(l10n),
                },
              ],
            ),
      bottomNavigationBar: created != null || needsEmail
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: Row(
                  children: [
                    if (_step > 1)
                      Expanded(
                        child: OutlinedButton(
                          key: const Key('org-register-back'),
                          onPressed: _busy
                              ? null
                              : () => setState(() {
                                  _errors.clear();
                                  _step--;
                                }),
                          child: Text(l10n.orgBack),
                        ),
                      ),
                    if (_step > 1) const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        key: const Key('org-register-next'),
                        onPressed: _busy
                            ? null
                            : (_step < _steps ? _next : _send),
                        child: Text(
                          _step < _steps ? l10n.orgNext : l10n.orgSubmit,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  List<Widget> _kindStep(AppLocalizations l10n) => [
    Align(
      alignment: AlignmentDirectional.centerStart,
      child: Pill(l10n.orgKindFieldsSim, tone: Tone.amber, icon: Icons.science),
    ),
    const SizedBox(height: 8),
    TileGrid(
      minTileWidth: 100,
      children: [
        for (final kind in OrgKind.values)
          ChoiceTile(
            key: Key('kind-${kind.wire}'),
            icon: kindLook(kind.wire).$1,
            tone: kindLook(kind.wire).$2,
            title: orgKindText(l10n, kind.wire),
            selected: _kind == kind.wire,
            onTap: () => setState(() {
              _kind = kind.wire;
              _errors.remove('kind');
            }),
          ),
      ],
    ),
    if (_errors['kind'] case final String err)
      Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(
          err,
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      ),
  ];

  Widget _field(
    String key,
    TextEditingController c,
    String label, {
    bool isRequired = false,
    TextInputType? keyboard,
    bool ltr = false,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextField(
      key: Key('org-$key'),
      controller: c,
      keyboardType: keyboard,
      textDirection: ltr ? TextDirection.ltr : null,
      decoration: InputDecoration(
        label: isRequired ? RequiredLabel(label) : Text(label),
        errorText: _errors[key],
      ),
    ),
  );

  List<Widget> _identityStep(AppLocalizations l10n) => [
    _field('name', _name, l10n.orgName, isRequired: true),
    Text(l10n.orgIdentifierType, style: Theme.of(context).textTheme.bodySmall),
    const SizedBox(height: 4),
    SegmentedButton<String>(
      key: const Key('org-identifier-type'),
      segments: [
        ButtonSegment(value: 'mf', label: Text(l10n.orgIdentifierMf)),
        ButtonSegment(value: 'rne', label: Text(l10n.orgIdentifierRne)),
      ],
      selected: {_identifierType},
      onSelectionChanged: (v) => setState(() => _identifierType = v.first),
    ),
    const SizedBox(height: 12),
    _field(
      'identifier',
      _identifier,
      l10n.orgIdentifier,
      isRequired: true,
      ltr: true,
    ),
    _field('manager_name', _managerName, l10n.orgManagerName, isRequired: true),
    _field(
      'manager_phone',
      _managerPhone,
      l10n.orgManagerPhone,
      isRequired: true,
      keyboard: TextInputType.phone,
      ltr: true,
    ),
    _field(
      'contact_email',
      _contactEmail,
      l10n.orgContactEmail,
      keyboard: TextInputType.emailAddress,
      ltr: true,
    ),
  ];

  List<Widget> _locationStep(AppLocalizations l10n) {
    final p = _location;
    return [
      AppCard(
        borderColor: _errors.containsKey('location')
            ? Theme.of(context).colorScheme.error
            : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FilledButton.tonalIcon(
              key: const Key('org-locate'),
              onPressed: _locating ? null : _locate,
              icon: const Icon(Icons.my_location),
              label: Text(l10n.orgUseMyLocation),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('org-lat'),
                    controller: _lat,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    textDirection: TextDirection.ltr,
                    decoration: const InputDecoration(labelText: 'Lat'),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    key: const Key('org-lon'),
                    controller: _lon,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    textDirection: TextDirection.ltr,
                    decoration: const InputDecoration(labelText: 'Lon'),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
              ],
            ),
            if (p != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  l10n.orgLocationSet(
                    p.lat.toStringAsFixed(5),
                    p.lon.toStringAsFixed(5),
                  ),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            if (_errors['location'] case final String err)
              Text(
                err,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      const SizedBox(height: 12),
      _field('address', _address, l10n.orgAddress, isRequired: true),
      _field(
        'capacity',
        _capacity,
        l10n.orgCapacity,
        isRequired: true,
        keyboard: TextInputType.number,
      ),
      _field('floors', _floors, l10n.orgFloors, keyboard: TextInputType.number),
      SwitchListTile(
        key: const Key('org-receives-public'),
        contentPadding: EdgeInsets.zero,
        title: Text(l10n.orgReceivesPublic),
        value: _receivesPublic,
        onChanged: (v) => setState(() => _receivesPublic = v),
      ),
      if ((kindFields[_kind] ?? const <KindField>[]).isNotEmpty) ...[
        SectionTitle(l10n.orgKindFieldsTitle),
        KindFieldInputs(
          kind: _kind!,
          values: _kindValues,
          showErrors: _errors.containsKey('kf'),
          onChanged: (k, v) => setState(() => _kindValues[k] = v),
        ),
        if (_errors['kf'] case final String err)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              err,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
      ],
    ];
  }

  List<Widget> _reviewStep(AppLocalizations l10n) {
    final p = _location;
    final rows = <(String, String)>[
      (l10n.orgKindLabelTitle, orgKindText(l10n, _kind ?? 'other')),
      (l10n.orgName, _name.text.trim()),
      (
        _identifierType == 'mf' ? l10n.orgIdentifierMf : l10n.orgIdentifierRne,
        normalizeIdentifier(_identifier.text),
      ),
      (l10n.orgManagerName, _managerName.text.trim()),
      (l10n.orgManagerPhone, normalizeTunisianPhone(_managerPhone.text)),
      if (_contactEmail.text.trim().isNotEmpty)
        (l10n.orgContactEmail, _contactEmail.text.trim()),
      (l10n.orgAddress, _address.text.trim()),
      if (p != null)
        (
          l10n.orgRegisterLocationTitle,
          '${p.lat.toStringAsFixed(5)}, ${p.lon.toStringAsFixed(5)}',
        ),
      (l10n.orgCapacity, _capacity.text.trim()),
      for (final f in kindFields[_kind] ?? const <KindField>[])
        if (kindFieldsToJson(_kind!, _kindValues)[f.key] case final Object v)
          (
            kindFieldText(l10n, f.key),
            v is bool ? (v ? l10n.orgYes : l10n.orgNo) : '$v',
          ),
    ];
    return [
      AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final (label, value) in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: Theme.of(context).textTheme.bodySmall),
                    Text(value, style: Theme.of(context).textTheme.bodyLarge),
                  ],
                ),
              ),
          ],
        ),
      ),
      const SizedBox(height: 12),
      Text(l10n.orgRegisteredBody),
      if (_sendError case final String err)
        Padding(
          padding: const EdgeInsets.only(top: 12),
          child: Text(
            err,
            key: const Key('org-register-error'),
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
    ];
  }
}

class _Done extends StatelessWidget {
  const _Done({required this.created});

  final OrgCardData created;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        HeroHeader(
          icon: Icons.mark_email_read,
          title: l10n.orgRegisteredTitle,
          meta: created.name,
          tone: Tone.green,
        ),
        const SizedBox(height: 16),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              OrgStatusPill(status: created.status),
              const SizedBox(height: 8),
              Text(l10n.orgRegisteredBody),
            ],
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('org-register-open'),
          onPressed: () => context.go(Routes.institution(created.id)),
          child: Text(l10n.orgOpenInstitution),
        ),
      ],
    );
  }
}
