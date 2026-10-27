import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/institution/org_text.dart';
import '../../l10n/app_localizations.dart';
import '../screens/field_widgets.dart';
import '../staff_capture.dart';
import '../staff_chrome.dart';
import 'prevention_controller.dart';
import 'prevention_labels.dart';
import 'prevention_models.dart';
import 'sign_screen.dart';

/// The grid by buttons (design §8.3): one card per declared item, three results, and for a
/// non-conformity what was seen (a count, reason chips) and photos. Works without network; every
/// tap is kept sealed on the phone.
class GridScreen extends ConsumerWidget {
  const GridScreen({super.key, required this.visitId});

  final String visitId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final pack = ref.watch(
      preventionControllerProvider.select((s) => s.packs[visitId]),
    );
    if (pack == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.prevGridTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final v = pack.visit;
    final d = pack.draft;
    final editable = !d.signedOff;
    final summary = GridSummary.of(v.checklist, d);
    final c = ref.read(preventionControllerProvider.notifier);
    final general = d.photos.where((p) => p.itemKey == null).length;
    return Scaffold(
      appBar: StaffAppBar(title: l10n.prevGridTitle, subtitle: v.orgName),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              key: const Key('grid-list'),
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: [
                for (final section in visitSections)
                  if (v.checklist.any((i) => i.section == section)) ...[
                    _SectionHeader(
                      section: section,
                      onAllConform: editable
                          ? () => unawaited(
                              c.sectionConform(visitId, [
                                for (final i in v.checklist)
                                  if (i.section == section) i.key,
                              ]),
                            )
                          : null,
                    ),
                    if (section == 'site')
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Align(
                          alignment: AlignmentDirectional.centerStart,
                          child: Pill(
                            l10n.prevSimGrid,
                            tone: Tone.amber,
                            icon: Icons.science,
                          ),
                        ),
                      ),
                    for (final i in v.checklist)
                      if (i.section == section)
                        _ItemCard(
                          visitId: visitId,
                          item: i,
                          draft: d.item(i.key),
                          photos: d.photos
                              .where((p) => p.itemKey == i.key)
                              .length,
                          canPhoto: d.photos.length < visitPhotoLimit,
                          editable: editable,
                        ),
                  ],
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  key: const Key('photo-general'),
                  onPressed: editable && d.photos.length < visitPhotoLimit
                      ? () => unawaited(_photo(context, ref, visitId, null))
                      : null,
                  icon: const Icon(Icons.photo_camera),
                  label: Text('${l10n.prevGeneral} ($general)'),
                ),
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    l10n.prevPhotoLimit,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Neutrals.of(context).muted),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: _SummaryBar(
        summary: summary,
        onNext: () => push(context, SignScreen(visitId: visitId)),
      ),
    );
  }
}

Future<void> _photo(
  BuildContext context,
  WidgetRef ref,
  String visitId,
  String? itemKey,
) async {
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final media = await ref.read(staffCaptureProvider).photo();
  if (media == null) return;
  final ok = await ref
      .read(preventionControllerProvider.notifier)
      .photo(visitId, itemKey, media);
  if (!ok) {
    messenger.showSnackBar(SnackBar(content: Text(l10n.prevErrTooManyPhotos)));
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.section, this.onAllConform});

  final String section;
  final VoidCallback? onAllConform;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Row(
      children: [
        Expanded(child: SectionTitle(sectionLabel(l10n, section))),
        Padding(
          padding: const EdgeInsets.only(top: 10),
          child: TextButton.icon(
            key: Key('all-conform-$section'),
            onPressed: onAllConform,
            icon: const Icon(Icons.done_all),
            label: Text(l10n.prevAllConform),
          ),
        ),
      ],
    );
  }
}

class _ItemCard extends ConsumerWidget {
  const _ItemCard({
    required this.visitId,
    required this.item,
    required this.draft,
    required this.photos,
    required this.canPhoto,
    required this.editable,
  });

  final String visitId;
  final ChecklistItem item;
  final ItemDraft draft;
  final int photos;
  final bool canPhoto;
  final bool editable;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final n = Neutrals.of(context);
    final c = ref.read(preventionControllerProvider.notifier);
    final declared = declaredText(l10n, item);
    final bad = draft.result == Finding.nonconform;
    final missing = needsDetail(draft);
    void set(Finding f) {
      unawaited(c.result(visitId, item.key, f));
      final count = item.declaredCount;
      if (f == Finding.nonconform && draft.count == null && count != null) {
        unawaited(c.count(visitId, item.key, count));
      }
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: AppCard(
        key: Key('item-${item.key}'),
        borderColor: bad ? Tone.red.colors(context).fill : null,
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              itemLabel(l10n, item.key),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (declared != null)
              Text(
                l10n.prevDeclared(declared),
                style: TextStyle(color: n.muted),
              ),
            const SizedBox(height: 8),
            ChoiceRow(
              children: [
                ToneChoice(
                  key: Key('${item.key}-conform'),
                  label: l10n.prevResultConform,
                  tone: Tone.green,
                  height: 48,
                  selected: draft.result == Finding.conform,
                  onTap: editable ? () => set(Finding.conform) : null,
                ),
                ToneChoice(
                  key: Key('${item.key}-nonconform'),
                  label: l10n.prevResultNonconform,
                  tone: Tone.red,
                  height: 48,
                  selected: bad,
                  onTap: editable ? () => set(Finding.nonconform) : null,
                ),
                ToneChoice(
                  key: Key('${item.key}-not_checked'),
                  label: l10n.prevResultNotChecked,
                  tone: Tone.slate,
                  height: 48,
                  selected: draft.result == Finding.notChecked,
                  onTap: editable ? () => set(Finding.notChecked) : null,
                ),
              ],
            ),
            if (bad) ...[
              if (item.declaredCount != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(child: Text(l10n.prevObserved)),
                    IconButton.filledTonal(
                      key: Key('${item.key}-minus'),
                      tooltip: '${l10n.staffLess}: ${l10n.prevObserved}',
                      onPressed: editable && (draft.count ?? 0) > 0
                          ? () => unawaited(
                              c.count(
                                visitId,
                                item.key,
                                (draft.count ?? 0) - 1,
                              ),
                            )
                          : null,
                      icon: const Icon(Icons.remove),
                    ),
                    SizedBox(
                      width: 56,
                      child: Semantics(
                        liveRegion: true,
                        label: '${l10n.prevObserved}: ${draft.count ?? 0}',
                        excludeSemantics: true,
                        child: Text(
                          '${draft.count ?? 0}',
                          key: Key('${item.key}-count'),
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                    ),
                    IconButton.filled(
                      key: Key('${item.key}-plus'),
                      tooltip: '${l10n.staffMore}: ${l10n.prevObserved}',
                      onPressed: editable
                          ? () => unawaited(
                              c.count(
                                visitId,
                                item.key,
                                (draft.count ?? 0) + 1,
                              ),
                            )
                          : null,
                      icon: const Icon(Icons.add),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final r in findingReasons)
                    FilterChip(
                      key: Key('${item.key}-reason-$r'),
                      label: Text(reasonLabel(l10n, r)),
                      selected: draft.reasons.contains(r),
                      onSelected: editable
                          ? (_) => unawaited(c.reason(visitId, item.key, r))
                          : null,
                    ),
                ],
              ),
              if (missing)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    l10n.prevNeedsDetail,
                    key: Key('${item.key}-needs-detail'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              const SizedBox(height: 8),
              _NoteField(
                visitId: visitId,
                itemKey: item.key,
                initial: draft.note,
                enabled: editable,
              ),
            ],
            const SizedBox(height: 4),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                key: Key('${item.key}-photo'),
                onPressed: editable && canPhoto
                    ? () => unawaited(_photo(context, ref, visitId, item.key))
                    : null,
                icon: const Icon(Icons.photo_camera),
                label: Text('${l10n.prevPhoto} ($photos)'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The optional note, kept when the field loses focus.
class _NoteField extends ConsumerStatefulWidget {
  const _NoteField({
    required this.visitId,
    required this.itemKey,
    required this.initial,
    required this.enabled,
  });

  final String visitId;
  final String itemKey;
  final String? initial;
  final bool enabled;

  @override
  ConsumerState<_NoteField> createState() => _NoteFieldState();
}

class _NoteFieldState extends ConsumerState<_NoteField> {
  late final _text = TextEditingController(text: widget.initial ?? '');

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextField(
    key: Key('${widget.itemKey}-note'),
    controller: _text,
    enabled: widget.enabled,
    maxLength: 200,
    decoration: InputDecoration(
      labelText: AppLocalizations.of(context).prevNoteOptional,
      counterText: '',
      isDense: true,
    ),
    onChanged: (t) => unawaited(
      ref
          .read(preventionControllerProvider.notifier)
          .note(widget.visitId, widget.itemKey, t),
    ),
  );
}

class _SummaryBar extends StatelessWidget {
  const _SummaryBar({required this.summary, required this.onNext});

  final GridSummary summary;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final n = Neutrals.of(context);
    final tone = summary.nonconform > 0 ? Tone.amber : Tone.green;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: n.card,
        border: Border(top: BorderSide(color: n.line)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Semantics(
                liveRegion: true,
                child: Text(
                  l10n.prevSummary(
                    summary.conform,
                    summary.nonconform,
                    summary.notChecked,
                  ),
                  key: const Key('grid-summary'),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(height: 4),
              Pill(
                l10n.prevSuggested(visitDecisionText(l10n, summary.suggested)),
                tone: tone,
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: ToneButton(
                  action: BarAction(
                    key: const Key('grid-next'),
                    label: l10n.prevNextSign,
                    icon: Icons.draw,
                    tone: Tone.navy,
                    onPressed: onNext,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
