import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'status_chip.dart';

/// Public tracking by code (`GET /api/v1/reports/track/{code}`), works for anonymous users and
/// sends no identity header.
class TrackScreen extends ConsumerStatefulWidget {
  const TrackScreen({super.key});

  static final codeFormat = RegExp(r'^EH-\d{2}-\d{2}-\d{7}$');

  @override
  ConsumerState<TrackScreen> createState() => _TrackScreenState();
}

class _TrackScreenState extends ConsumerState<TrackScreen> {
  final _controller = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  TrackingResult? _result;
  String? _error;
  bool _loading = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _track() async {
    if (!_formKey.currentState!.validate()) return;
    final l10n = AppLocalizations.of(context);
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final r = await ref
          .read(apiProvider)
          .track(_controller.text.trim().toUpperCase());
      if (mounted) setState(() => _result = r);
    } on Object catch (e) {
      if (mounted) setState(() => _error = errorMessageFor(l10n, e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final fmt = DateFormat.yMMMd(locale).add_Hm();
    final result = _result;
    final status = ReportStatus.fromWire(result?.status);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.trackTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Form(
              key: _formKey,
              child: TextFormField(
                key: const Key('track-field'),
                controller: _controller,
                textDirection: TextDirection.ltr,
                textCapitalization: TextCapitalization.characters,
                decoration: InputDecoration(
                  labelText: l10n.trackingCodeLabel,
                  hintText: l10n.trackHint,
                  hintTextDirection: TextDirection.ltr,
                ),
                validator: (v) =>
                    TrackScreen.codeFormat.hasMatch(
                      (v ?? '').trim().toUpperCase(),
                    )
                    ? null
                    : l10n.trackInvalid,
                onFieldSubmitted: (_) => _track(),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _loading ? null : _track,
              icon: const Icon(Icons.search),
              label: Text(l10n.trackAction),
            ),
            if (_loading) ...[
              const SizedBox(height: 16),
              const LinearProgressIndicator(),
            ],
            if (_error != null) ...[
              const SizedBox(height: 16),
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            ],
            if (result != null) ...[
              const SizedBox(height: 24),
              Text(
                result.trackingCode,
                textDirection: TextDirection.ltr,
                style: theme.textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              if (status != null)
                Align(
                  alignment: AlignmentDirectional.centerStart,
                  child: ReportStatusChip(status: status),
                ),
              if (result.receivedAt != null)
                Text(l10n.receivedAt(fmt.format(result.receivedAt!.toLocal()))),
              const SizedBox(height: 16),
              Text(l10n.trackHistory, style: theme.textTheme.titleMedium),
              for (final h in result.history)
                ListTile(
                  leading: const Icon(Icons.history),
                  title: Text(switch (ReportStatus.fromWire(h.status)) {
                    final s? => reportStatusLabel(l10n, s),
                    null => l10n.statusUnknown,
                  }),
                  subtitle: h.at == null
                      ? null
                      : Text(fmt.format(h.at!.toLocal())),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
