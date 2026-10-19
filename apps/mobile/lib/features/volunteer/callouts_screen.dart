import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../report/category_labels.dart';
import 'volunteer_providers.dart';
import 'volunteer_screen.dart';

/// Call-outs addressed to the volunteer (UC-05, FR-A-023): accept with an ETA or decline, then
/// report arrival on scene.
class CalloutsScreen extends ConsumerWidget {
  const CalloutsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final callouts = ref.watch(myCalloutsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.calloutsTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(myCalloutsProvider.future),
        child: callouts.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(24),
            children: [Text(errorMessageFor(l10n, e))],
          ),
          data: (items) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              if (items.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(l10n.calloutsEmpty, textAlign: TextAlign.center),
                ),
              for (final c in items) _CalloutCard(callout: c),
            ],
          ),
        ),
      ),
    );
  }
}

class _CalloutCard extends ConsumerStatefulWidget {
  const _CalloutCard({required this.callout});
  final MyCallout callout;

  @override
  ConsumerState<_CalloutCard> createState() => _CalloutCardState();
}

class _CalloutCardState extends ConsumerState<_CalloutCard> {
  bool _busy = false;

  Future<void> _run(Future<void> Function(EHimayaApi api) action) async {
    setState(() => _busy = true);
    try {
      await action(ref.read(apiProvider));
      ref.invalidate(myCalloutsProvider);
    } on Object catch (e) {
      if (mounted) showVolunteerError(context, e);
      ref.invalidate(myCalloutsProvider);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _accept() async {
    final eta = await showDialog<int>(
      context: context,
      builder: (_) => const _EtaDialog(),
    );
    if (eta == null) return;
    await _run(
      (api) =>
          api.respondCallout(widget.callout.id, accept: true, etaMinutes: eta),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final c = widget.callout;
    final category =
        ReportCategory.fromWire(c.incidentCategory) ?? ReportCategory.other;
    final closed =
        c.status == CalloutStatus.cancelled || c.status == CalloutStatus.closed;
    return Card(
      key: Key('callout-${c.id}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  categoryIcon(category),
                  size: 32,
                  color: theme.colorScheme.error,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    categoryLabel(l10n, category),
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                Chip(label: Text(calloutAnswerLabel(l10n, c.myStatus))),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 16,
              runSpacing: 4,
              children: [
                if (c.skill != null)
                  Text(l10n.calloutSkill(skillLabel(l10n, c.skill!))),
                if (c.distanceM != null)
                  Text(l10n.calloutDistance(distanceLabel(l10n, c.distanceM!))),
                Text(dateTimeLabel(context, c.createdAt)),
                if (c.etaMinutes != null &&
                    c.myStatus == CalloutTargetStatus.accepted)
                  Text(l10n.calloutEta(c.etaMinutes!)),
              ],
            ),
            if (c.message != null && c.message!.trim().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(c.message!),
            ],
            if (closed) ...[
              const SizedBox(height: 8),
              Text(
                l10n.errorCalloutClosed,
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ],
            if (c.canRespond || c.canArrive) const SizedBox(height: 12),
            if (c.canRespond)
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      key: Key('callout-decline-${c.id}'),
                      onPressed: _busy
                          ? null
                          : () => _run(
                              (api) => api.respondCallout(c.id, accept: false),
                            ),
                      child: Text(l10n.calloutDecline),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      key: Key('callout-accept-${c.id}'),
                      onPressed: _busy ? null : _accept,
                      child: Text(l10n.calloutAccept),
                    ),
                  ),
                ],
              ),
            if (c.canArrive)
              FilledButton.icon(
                key: Key('callout-arrived-${c.id}'),
                icon: const Icon(Icons.flag),
                label: Text(l10n.calloutArrived),
                onPressed: _busy
                    ? null
                    : () => _run((api) => api.calloutArrived(c.id)),
              ),
          ],
        ),
      ),
    );
  }
}

/// Estimated time of arrival, in minutes (1–600, required to accept).
class _EtaDialog extends StatefulWidget {
  const _EtaDialog();

  @override
  State<_EtaDialog> createState() => _EtaDialogState();
}

class _EtaDialogState extends State<_EtaDialog> {
  final _controller = TextEditingController(text: '15');

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  int? get _value {
    final v = int.tryParse(_controller.text.trim());
    return v != null && v >= 1 && v <= 600 ? v : null;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.calloutAccept),
      content: TextField(
        key: const Key('callout-eta'),
        controller: _controller,
        autofocus: true,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
        decoration: InputDecoration(
          labelText: l10n.calloutEtaLabel,
          errorText: _value == null ? l10n.errorEtaRequired : null,
        ),
        onChanged: (_) => setState(() {}),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.actionCancel),
        ),
        FilledButton(
          key: const Key('callout-eta-ok'),
          onPressed: _value == null
              ? null
              : () => Navigator.pop(context, _value),
          child: Text(l10n.calloutAccept),
        ),
      ],
    );
  }
}
