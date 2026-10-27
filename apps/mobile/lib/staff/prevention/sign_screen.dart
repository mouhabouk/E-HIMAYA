import 'dart:async';
import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import 'prevention_controller.dart';
import 'prevention_labels.dart';
import 'prevention_models.dart';
import 'visit_screen.dart';

/// Turns the strokes of a signature into a PNG in base64. Overridden in tests.
typedef SignatureEncoder = Future<String> Function(
  List<List<Offset>> strokes,
  Size size,
);

final signatureEncoderProvider = Provider<SignatureEncoder>(
  (ref) => encodeSignature,
);

/// Dark strokes on a transparent background, at the pad's size (a few kilobytes).
Future<String> encodeSignature(List<List<Offset>> strokes, Size size) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  _paintStrokes(canvas, strokes, const Color(0xFF0B1F44));
  final image = await recorder.endRecording().toImage(
    size.width.ceil(),
    size.height.ceil(),
  );
  final data = await image.toByteData(format: ui.ImageByteFormat.png);
  image.dispose();
  return base64.encode(data!.buffer.asUint8List());
}

void _paintStrokes(Canvas canvas, List<List<Offset>> strokes, Color color) {
  final paint = Paint()
    ..color = color
    ..strokeWidth = 3
    ..strokeCap = StrokeCap.round
    ..strokeJoin = StrokeJoin.round
    ..style = PaintingStyle.stroke;
  for (final s in strokes) {
    if (s.length == 1) {
      canvas.drawCircle(s.first, 1.5, paint..style = PaintingStyle.fill);
      paint.style = PaintingStyle.stroke;
      continue;
    }
    final path = Path()..moveTo(s.first.dx, s.first.dy);
    for (final p in s.skip(1)) {
      path.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(path, paint);
  }
}

/// The attendees, the institution's representative and both signatures (design §8.4); closing
/// the inspection puts it in the box and sends it when the network is there.
class SignScreen extends ConsumerWidget {
  const SignScreen({super.key, required this.visitId});

  final String visitId;

  static String attendeeText(AppLocalizations l10n, String a) =>
      a.startsWith('person:') ? a.substring(7) : roleLabel(l10n, a);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(preventionControllerProvider);
    final pack = s.packs[visitId];
    if (pack == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.prevSignTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final c = ref.read(preventionControllerProvider.notifier);
    final v = pack.visit;
    final d = pack.draft;
    final editable = !d.signedOff;
    final declared = v.declaredRepresentative;
    final attendees = [
      if (declared != null) 'person:$declared',
      ...representativeRoles,
    ];
    final undetailed = v.checklist
        .where((i) => needsDetail(d.item(i.key)))
        .length;
    final signed =
        d.inspectorSignature != null &&
        d.representativeSignature != null &&
        (d.representativeName?.trim().isNotEmpty ?? false);
    return Scaffold(
      appBar: StaffAppBar(title: l10n.prevSignTitle, subtitle: v.orgName),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: [
                SectionTitle(l10n.prevAttendees),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final a in attendees)
                      FilterChip(
                        key: Key('attendee-$a'),
                        label: Text(attendeeText(l10n, a)),
                        selected: d.attendees.contains(a),
                        onSelected: editable
                            ? (_) => unawaited(c.attendee(visitId, a))
                            : null,
                      ),
                  ],
                ),
                SectionTitle(l10n.prevRepresentative),
                _NameField(
                  visitId: visitId,
                  initial: d.representativeName,
                  enabled: editable,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final r in representativeRoles)
                      ChoiceChip(
                        key: Key('role-$r'),
                        label: Text(roleLabel(l10n, r)),
                        selected: d.representativeRole == r,
                        onSelected: editable
                            ? (_) =>
                                  unawaited(c.representative(visitId, role: r))
                            : null,
                      ),
                  ],
                ),
                SectionTitle(l10n.prevSignInspector),
                SignaturePad(
                  key: const Key('pad-inspector'),
                  png: d.inspectorSignature,
                  enabled: editable,
                  onSigned: (png) => unawaited(
                    c.signature(visitId, inspector: true, png: png),
                  ),
                ),
                SectionTitle(l10n.prevSignRepresentative),
                SignaturePad(
                  key: const Key('pad-representative'),
                  png: d.representativeSignature,
                  enabled: editable,
                  onSigned: (png) => unawaited(
                    c.signature(visitId, inspector: false, png: png),
                  ),
                ),
                const SizedBox(height: 12),
                if (editable && undetailed > 0)
                  Text(
                    l10n.prevDetailMissing(undetailed),
                    key: const Key('detail-missing'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                if (editable && !signed)
                  Text(
                    l10n.prevSignMissing,
                    key: const Key('sign-missing'),
                    style: TextStyle(color: Neutrals.of(context).muted),
                  ),
                if (!editable)
                  AppCard(
                    key: const Key('signed-off'),
                    color: Tone.green.colors(context).tint,
                    child: Text(
                      d.inspectionSent
                          ? l10n.prevInspectionSent
                          : l10n.prevInspectionQueued,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: editable
          ? BottomActionBar(
              actions: [
                BarAction(
                  key: const Key('sign-off'),
                  label: l10n.prevSignOff,
                  icon: Icons.send,
                  tone: Tone.navy,
                  onPressed: signed && undetailed == 0
                      ? () => unawaited(_signOff(context, ref, pack))
                      : null,
                ),
              ],
            )
          : null,
    );
  }

  Future<void> _signOff(
    BuildContext context,
    WidgetRef ref,
    VisitPack pack,
  ) async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final nav = Navigator.of(context);
    final c = ref.read(preventionControllerProvider.notifier);
    await c.signOff(
      visitId,
      noteOf: (d) => findingNote(l10n, d),
      roleText: (r) => r == null ? null : roleLabel(l10n, r),
      attendees: [for (final a in pack.draft.attendees) attendeeText(l10n, a)]
          .join('، '),
    );
    final sent =
        ref
            .read(preventionControllerProvider)
            .packs[visitId]
            ?.draft
            .inspectionSent ??
        false;
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          sent ? l10n.prevInspectionSent : l10n.prevInspectionQueued,
        ),
      ),
    );
    if (nav.mounted) nav.popUntil(backToVisit);
  }
}

class _NameField extends ConsumerStatefulWidget {
  const _NameField({
    required this.visitId,
    required this.initial,
    required this.enabled,
  });

  final String visitId;
  final String? initial;
  final bool enabled;

  @override
  ConsumerState<_NameField> createState() => _NameFieldState();
}

class _NameFieldState extends ConsumerState<_NameField> {
  late final _text = TextEditingController(text: widget.initial ?? '');

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextField(
    key: const Key('representative-name'),
    controller: _text,
    enabled: widget.enabled,
    maxLength: 120,
    textCapitalization: TextCapitalization.words,
    decoration: InputDecoration(
      labelText: AppLocalizations.of(context).prevRepresentativeName,
      counterText: '',
    ),
    onChanged: (t) => unawaited(
      ref
          .read(preventionControllerProvider.notifier)
          .representative(widget.visitId, name: t),
    ),
  );
}

/// A pad to sign with the finger. Each lift of the finger saves the drawing as a PNG; «امسح»
/// starts again. A saved signature is shown as it was drawn.
class SignaturePad extends ConsumerStatefulWidget {
  const SignaturePad({
    super.key,
    required this.png,
    required this.enabled,
    required this.onSigned,
  });

  /// The saved signature (PNG in base64), or null.
  final String? png;
  final bool enabled;

  /// The new drawing, or null when cleared.
  final ValueChanged<String?> onSigned;

  static const height = 160.0;

  @override
  ConsumerState<SignaturePad> createState() => _SignaturePadState();
}

class _SignaturePadState extends ConsumerState<SignaturePad> {
  final _strokes = <List<Offset>>[];
  Size _size = Size.zero;

  Future<void> _save() async {
    if (_strokes.isEmpty || _size.isEmpty) return;
    final png = await ref.read(signatureEncoderProvider)([
      for (final s in _strokes) [...s],
    ], _size);
    if (mounted) widget.onSigned(png);
  }

  void _start(DragStartDetails e) =>
      setState(() => _strokes.add([e.localPosition]));

  void _move(DragUpdateDetails e) =>
      setState(() => _strokes.last.add(e.localPosition));

  void _end(DragEndDetails _) => unawaited(_save());

  void _clear() {
    setState(_strokes.clear);
    widget.onSigned(null);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final n = Neutrals.of(context);
    final saved = widget.png;
    final drawing = _strokes.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          label: l10n.prevSignHere,
          value: saved != null ? l10n.prevSigned : null,
          child: Container(
            height: SignaturePad.height,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(Radii.card),
              border: Border.all(
                color: saved != null ? Tone.green.colors(context).fill : n.line,
                width: 2,
              ),
            ),
            clipBehavior: Clip.antiAlias,
            child: LayoutBuilder(
              builder: (context, box) {
                _size = Size(box.maxWidth, box.maxHeight);
                if (saved != null && !drawing) {
                  return Image.memory(
                    base64.decode(saved),
                    key: const Key('signature-image'),
                    fit: BoxFit.contain,
                    errorBuilder: (_, _, _) => Center(
                      child: Icon(
                        Icons.check_circle,
                        color: Tone.green.colors(context).fill,
                        size: 40,
                      ),
                    ),
                  );
                }
                // The pad takes the finger at once: a vertical stroke draws, it does not
                // scroll the page.
                return RawGestureDetector(
                  behavior: HitTestBehavior.opaque,
                  gestures: {
                    if (widget.enabled)
                      _ImmediatePan:
                          GestureRecognizerFactoryWithHandlers<_ImmediatePan>(
                            _ImmediatePan.new,
                            (g) => g
                              ..onStart = _start
                              ..onUpdate = _move
                              ..onEnd = _end,
                          ),
                  },
                  child: CustomPaint(
                    painter: _PadPainter(
                      _strokes,
                      _strokes.length,
                      _strokes.fold(0, (n, s) => n + s.length),
                    ),
                    child: drawing
                        ? null
                        : Center(
                            child: Text(
                              l10n.prevSignHere,
                              style: const TextStyle(color: Color(0xFF6B7280)),
                            ),
                          ),
                  ),
                );
              },
            ),
          ),
        ),
        if (widget.enabled)
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: TextButton.icon(
              key: Key(
                '${(widget.key as ValueKey<String>?)?.value ?? 'pad'}-clear',
              ),
              onPressed: saved != null || drawing ? _clear : null,
              icon: const Icon(Icons.backspace_outlined),
              label: Text(l10n.prevClear),
            ),
          ),
      ],
    );
  }
}

/// A pan that wins the gesture arena on touch, before the page's scroll.
class _ImmediatePan extends PanGestureRecognizer {
  _ImmediatePan() : super(debugOwner: null);

  @override
  void addAllowedPointer(PointerDownEvent event) {
    super.addAllowedPointer(event);
    resolve(GestureDisposition.accepted);
  }
}

class _PadPainter extends CustomPainter {
  _PadPainter(this.strokes, this.count, this.points);

  final List<List<Offset>> strokes;
  final int count;
  final int points;

  @override
  void paint(Canvas canvas, Size size) =>
      _paintStrokes(canvas, strokes, const Color(0xFF0B1F44));

  @override
  bool shouldRepaint(_PadPainter old) =>
      old.count != count || old.points != points;
}
