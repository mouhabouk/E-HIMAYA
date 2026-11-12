import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';

/// The needs a citizen may declare at their address (OS8, design-os8.md §6).
const personalNeeds = ['mob', 'oxy', 'deaf'];

IconData _needIcon(String key) => switch (key) {
  'mob' => Icons.accessible,
  'oxy' => Icons.air,
  _ => Icons.hearing_disabled,
};

String needLabel(AppLocalizations l10n, String key) => switch (key) {
  'mob' => l10n.awCatMob,
  'oxy' => l10n.awCatOxy,
  _ => l10n.awCatDeaf,
};

/// What the server keeps of the citizen's consent: the address, the needs, and when the room read the name.
class MyAddressWarnings {
  const MyAddressWarnings({
    this.location,
    this.address,
    this.needs = const {},
    this.reveals = const [],
  });

  factory MyAddressWarnings.fromJson(Map<String, Object?> j) {
    final loc = j['location'] as Map<String, Object?>?;
    return MyAddressWarnings(
      location: loc == null
          ? null
          : GeoPoint(
              lat: (loc['lat']! as num).toDouble(),
              lon: (loc['lon']! as num).toDouble(),
            ),
      address: j['address'] as String?,
      needs: {
        for (final n in j['needs'] as List? ?? const [])
          (n as Map<String, Object?>)['category']! as String:
              n['description'] as String? ?? '',
      },
      reveals: [
        for (final r in j['reveals'] as List? ?? const [])
          (
            at: DateTime.parse((r as Map<String, Object?>)['at']! as String),
            category: r['category'] as String? ?? '',
            reason: r['reason'] as String? ?? '',
          ),
      ],
    );
  }

  final GeoPoint? location;
  final String? address;
  final Map<String, String> needs;
  final List<({DateTime at, String category, String reason})> reveals;
}

final myAddressWarningsProvider =
    FutureProvider.autoDispose<MyAddressWarnings?>((ref) async {
      if (!ref.watch(identityProvider).isRegistered) return null;
      return MyAddressWarnings.fromJson(
        await ref.watch(apiProvider).myAddressWarnings(),
      );
    });

/// The citizen's consent, from their medical file: «أريد أن تعرف فرق الإنقاذ أن في بيتي من يحتاج مساعدة». One mark
/// per need at their address, without a name; the room may read the name for an incident, with a reason, and the
/// citizen sees when and why. Renewed each year, withdrawn in one tap.
class AddressWarningsConsentScreen extends ConsumerWidget {
  const AddressWarningsConsentScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final async = ref.watch(myAddressWarningsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.awConsentTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: switch (async) {
        AsyncData(:final value) when value == null => Padding(
          padding: const EdgeInsets.all(16),
          child: Text(l10n.awConsentRegistered),
        ),
        AsyncData(:final value) => _ConsentForm(current: value!),
        AsyncError() => Padding(
          padding: const EdgeInsets.all(16),
          child: Text(l10n.awFailed),
        ),
        _ => const Center(child: CircularProgressIndicator()),
      },
    );
  }
}

class _ConsentForm extends ConsumerStatefulWidget {
  const _ConsentForm({required this.current});

  final MyAddressWarnings current;

  @override
  ConsumerState<_ConsentForm> createState() => _ConsentFormState();
}

class _ConsentFormState extends ConsumerState<_ConsentForm> {
  late final _address = TextEditingController(text: widget.current.address);
  late final _notes = {
    for (final k in personalNeeds)
      k: TextEditingController(text: widget.current.needs[k] ?? ''),
  };
  late final _on = {...widget.current.needs.keys};
  late GeoPoint? _place = widget.current.location;
  bool _busy = false;

  @override
  void dispose() {
    _address.dispose();
    for (final c in _notes.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _locate() async {
    final p = await ref.read(locationServiceProvider).bestEffort();
    if (p != null && mounted) setState(() => _place = p);
  }

  Future<void> _run(Future<Map<String, Object?>> Function() call) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      await call();
      ref.invalidate(myAddressWarningsProvider);
      messenger.showSnackBar(SnackBar(content: Text(l10n.awConsentSaved)));
    } on Object {
      messenger.showSnackBar(SnackBar(content: Text(l10n.awFailed)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _save() {
    final place = _place;
    if (place == null) return;
    final api = ref.read(apiProvider);
    unawaited(
      _run(
        () => api.saveMyAddressWarnings({
          'location': {'lat': place.lat, 'lon': place.lon},
          'address': _address.text.trim(),
          'needs': [
            for (final k in personalNeeds)
              if (_on.contains(k))
                {
                  'category': k,
                  'description': _notes[k]!.text.trim().isEmpty
                      ? needLabel(AppLocalizations.of(context), k)
                      : _notes[k]!.text.trim(),
                },
          ],
        }),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final current = widget.current;
    final ready = _place != null && _address.text.trim().length >= 3;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(l10n.awConsentIntro, style: theme.textTheme.bodyMedium),
        const SizedBox(height: 8),
        for (final k in personalNeeds) ...[
          CheckboxListTile(
            key: Key('aw-need-$k'),
            contentPadding: EdgeInsets.zero,
            value: _on.contains(k),
            onChanged: (v) =>
                setState(() => v == true ? _on.add(k) : _on.remove(k)),
            secondary: IconTile(_needIcon(k), tone: Tone.green, size: 40),
            title: Text(needLabel(l10n, k)),
          ),
          if (_on.contains(k))
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: TextField(
                key: Key('aw-note-$k'),
                controller: _notes[k],
                maxLength: 500,
                decoration: InputDecoration(labelText: l10n.awConsentNote),
              ),
            ),
        ],
        const SizedBox(height: 8),
        TextField(
          key: const Key('aw-address'),
          controller: _address,
          maxLength: 200,
          decoration: InputDecoration(labelText: l10n.awConsentAddress),
          onChanged: (_) => setState(() {}),
        ),
        ListTile(
          key: const Key('aw-locate'),
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            _place == null ? Icons.location_searching : Icons.location_on,
          ),
          title: Text(
            _place == null ? l10n.awConsentLocate : l10n.awConsentLocated,
          ),
          onTap: () => unawaited(_locate()),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(
          key: const Key('aw-save'),
          onPressed: _busy || !ready ? null : _save,
          icon: const Icon(Icons.save),
          label: Text(l10n.actionSave),
        ),
        const SizedBox(height: 8),
        Text(l10n.awConsentPrivacy, style: theme.textTheme.bodySmall),
        if (current.reveals.isNotEmpty) ...[
          SectionTitle(l10n.awConsentReveals),
          for (final r in current.reveals)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.visibility),
              title: Text(r.reason),
              subtitle: Text(
                '${needLabel(l10n, r.category)} · ${_date(r.at.toLocal())}',
              ),
            ),
        ],
        if (current.needs.isNotEmpty) ...[
          const SizedBox(height: 16),
          TextButton.icon(
            key: const Key('aw-withdraw'),
            style: TextButton.styleFrom(
              foregroundColor: theme.colorScheme.error,
            ),
            onPressed: _busy
                ? null
                : () => unawaited(
                    _run(
                      () => ref.read(apiProvider).withdrawMyAddressWarnings(),
                    ),
                  ),
            icon: const Icon(Icons.delete_forever),
            label: Text(l10n.awConsentWithdraw),
          ),
        ],
        const SizedBox(height: 72),
      ],
    );
  }
}

String _date(DateTime d) =>
    '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year} '
    '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
