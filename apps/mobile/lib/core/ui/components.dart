import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../l10n/app_localizations.dart';
import 'tokens.dart';

/// Shared components of the design system (docs/design-system.md §3). Screens build on these so
/// the app, the portal and the dashboard keep one look.

/// Rounded square holding a glyph in a category colour. [soft] uses the tint with a coloured glyph.
/// Decorative: the row or tile around it carries the label.
class IconTile extends StatelessWidget {
  const IconTile(
    this.icon, {
    super.key,
    required this.tone,
    this.size = 44,
    this.soft = false,
  });

  final IconData icon;
  final Tone tone;
  final double size;
  final bool soft;

  @override
  Widget build(BuildContext context) {
    final c = tone.colors(context);
    return ExcludeSemantics(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: soft ? c.tint : c.fill,
          borderRadius: BorderRadius.circular(Radii.tile),
        ),
        alignment: Alignment.center,
        child: Icon(icon, size: size * 0.55, color: soft ? c.fill : c.onFill),
      ),
    );
  }
}

/// White card with a border, the base surface of every list and panel.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.onTap,
    this.borderColor,
    this.color,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Color? borderColor;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final n = Neutrals.of(context);
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(Radii.card),
      side: BorderSide(
        color: borderColor ?? n.line,
        width: borderColor == null ? 1 : 2,
      ),
    );
    return Material(
      color: color ?? n.card,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: onTap == null
          ? Padding(padding: padding, child: child)
          : InkWell(
              onTap: onTap,
              child: Padding(padding: padding, child: child),
            ),
    );
  }
}

/// Card row: icon tile, bold title, muted subtitle, chevron at the end (mirrored in RTL).
class NavCard extends StatelessWidget {
  const NavCard({
    super.key,
    required this.icon,
    required this.tone,
    required this.title,
    this.subtitle,
    this.onTap,
    this.trailing,
  });

  final IconData icon;
  final Tone tone;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final n = Neutrals.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Semantics(
        button: onTap != null,
        child: AppCard(
          onTap: onTap,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          child: Row(
            children: [
              IconTile(icon, tone: tone),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontSize: 16,
                      ),
                    ),
                    if (subtitle != null)
                      Text(
                        subtitle!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: n.muted,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                  ],
                ),
              ),
              ?trailing,
              if (onTap != null && trailing == null)
                Icon(Icons.chevron_right, color: n.muted),
            ],
          ),
        ),
      ),
    );
  }
}

/// Square choice or shortcut: soft icon tile, title and caption centred. Selected adds an orange
/// border, an orange tint and a check mark, so the state never rests on colour alone.
class ChoiceTile extends StatelessWidget {
  const ChoiceTile({
    super.key,
    required this.icon,
    required this.tone,
    required this.title,
    this.caption,
    this.onTap,
    this.selected = false,
  });

  final IconData icon;
  final Tone tone;
  final String title;
  final String? caption;
  final VoidCallback? onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final orange = Tone.orange.colors(context);
    return Semantics(
      button: onTap != null,
      selected: selected,
      child: AppCard(
        onTap: onTap,
        borderColor: selected ? orange.fill : null,
        color: selected ? orange.tint : null,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 12),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 84),
          child: Stack(
            children: [
              Align(
                alignment: Alignment.center,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconTile(icon, tone: tone, soft: true, size: 48),
                    const SizedBox(height: 8),
                    Text(
                      title,
                      textAlign: TextAlign.center,
                      style: theme.textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (caption != null)
                      Text(
                        caption!,
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        style: theme.textTheme.bodySmall,
                      ),
                  ],
                ),
              ),
              if (selected)
                PositionedDirectional(
                  top: 0,
                  end: 0,
                  child: Icon(
                    Icons.check_circle_rounded,
                    size: 20,
                    color: orange.onTint,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Fully rounded tint badge with its word in the darker shade of the colour.
class Pill extends StatelessWidget {
  const Pill(this.label, {super.key, required this.tone, this.icon});

  final String label;
  final Tone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final c = tone.colors(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: c.tint,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: c.onTint),
            const SizedBox(width: 4),
          ],
          Flexible(
            child: Text(
              label,
              style: TextStyle(
                fontFamily: appFontFamily,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: c.onTint,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Grid of square tiles: as many columns as fit [minTileWidth] (up to four), wider with large text.
class TileGrid extends StatelessWidget {
  const TileGrid({
    super.key,
    required this.children,
    required this.minTileWidth,
  });

  final List<Widget> children;
  final double minTileWidth;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      const gap = 8.0;
      final scale = MediaQuery.textScalerOf(context).scale(1);
      final min = minTileWidth * (scale > 1.3 ? scale * 0.8 : 1);
      final columns = ((constraints.maxWidth + gap) / (min + gap))
          .floor()
          .clamp(1, children.length.clamp(1, 4));
      final width = (constraints.maxWidth - gap * (columns - 1)) / columns;
      return Wrap(
        spacing: gap,
        runSpacing: gap,
        children: [
          for (final child in children) SizedBox(width: width, child: child),
        ],
      );
    },
  );
}

/// Bold section title between groups of cards.
class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 16, bottom: 6),
    child: Semantics(
      header: true,
      child: Text(
        text,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 17),
      ),
    ),
  );
}

/// One action of a [BottomActionBar].
class BarAction {
  const BarAction({
    required this.label,
    required this.icon,
    required this.tone,
    required this.onPressed,
    this.key,
  });

  final String label;
  final IconData icon;
  final Tone tone;

  /// Null disables the button (greyed out, announced as disabled).
  final VoidCallback? onPressed;
  final Key? key;
}

/// White bar with a top border and large rounded buttons; the emergency action comes first.
class BottomActionBar extends StatelessWidget {
  const BottomActionBar({super.key, required this.actions});

  final List<BarAction> actions;

  @override
  Widget build(BuildContext context) {
    final n = Neutrals.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: n.card,
        border: Border(top: BorderSide(color: n.line)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          child: Row(
            children: [
              for (final (i, a) in actions.indexed) ...[
                if (i > 0) const SizedBox(width: 10),
                Expanded(child: ToneButton(action: a)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Large filled button in a category colour.
class ToneButton extends StatelessWidget {
  const ToneButton({super.key, required this.action});

  final BarAction action;

  @override
  Widget build(BuildContext context) {
    final c = action.tone.colors(context);
    return FilledButton.icon(
      key: action.key,
      style: FilledButton.styleFrom(
        backgroundColor: c.fill,
        foregroundColor: c.onFill,
        minimumSize: const Size(64, 56),
      ),
      onPressed: action.onPressed,
      icon: Icon(action.icon),
      label: Text(action.label, textAlign: TextAlign.center),
    );
  }
}

/// Full-width coloured band: white icon, title and one meta line (alert screens).
class HeroHeader extends StatelessWidget {
  const HeroHeader({
    super.key,
    required this.icon,
    required this.title,
    this.meta,
    this.tone = Tone.red,
  });

  final IconData icon;
  final String title;
  final String? meta;
  final Tone tone;

  @override
  Widget build(BuildContext context) {
    final light = _lightFill[tone] ?? Hue.red;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 28, 16, 24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [light, Color.lerp(light, Colors.black, 0.18)!],
        ),
      ),
      child: Column(
        children: [
          ExcludeSemantics(child: Icon(icon, size: 44, color: Colors.white)),
          const SizedBox(height: 8),
          Semantics(
            header: true,
            child: Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontFamily: appFontFamily,
                fontSize: 26,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
          ),
          if (meta != null) ...[
            const SizedBox(height: 6),
            Text(
              meta!,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontFamily: appFontFamily,
                fontSize: 14,
                color: Colors.white,
              ),
            ),
          ],
        ],
      ),
    );
  }

  // White text needs the light-mode fill in both brightnesses.
  static const _lightFill = {
    Tone.red: Hue.red,
    Tone.navy: Hue.navy,
    Tone.green: Hue.green,
    Tone.purple: Hue.purple,
    Tone.teal: Hue.teal,
  };
}

/// Step progress: done segments in orange, the rest in the line grey. The step text is given by
/// [label] for screen readers and shown by the caller.
class StepBar extends StatelessWidget {
  const StepBar({
    super.key,
    required this.current,
    required this.total,
    required this.label,
  });

  final int current;
  final int total;
  final String label;

  @override
  Widget build(BuildContext context) {
    final n = Neutrals.of(context);
    final orange = Tone.orange.colors(context).fill;
    return Semantics(
      label: label,
      excludeSemantics: true,
      child: Row(
        children: [
          for (var i = 1; i <= total; i++) ...[
            if (i > 1) const SizedBox(width: 6),
            Expanded(
              child: Container(
                height: 6,
                decoration: BoxDecoration(
                  color: i <= current ? orange : n.line,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Green ring with the percentage in the centre.
class ProgressRing extends StatelessWidget {
  const ProgressRing({
    super.key,
    required this.value,
    this.size = 88,
    this.tone = Tone.green,
  });

  /// From 0 to 1.
  final double value;
  final double size;
  final Tone tone;

  @override
  Widget build(BuildContext context) {
    final percent = (value.clamp(0, 1) * 100).round();
    return Semantics(
      label: '$percent%',
      excludeSemantics: true,
      child: SizedBox(
        width: size,
        height: size,
        child: CustomPaint(
          painter: _RingPainter(
            value.clamp(0, 1).toDouble(),
            tone.colors(context).fill,
            Neutrals.of(context).line,
          ),
          child: Center(
            child: Text(
              '$percent%',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter(this.value, this.color, this.track);

  final double value;
  final Color color;
  final Color track;

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 9.0;
    final rect = Offset.zero & size;
    final arc = rect.deflate(stroke / 2);
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(arc, 0, 2 * math.pi, false, paint..color = track);
    canvas.drawArc(
      arc,
      -math.pi / 2,
      2 * math.pi * value,
      false,
      paint..color = color,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.value != value || old.color != color || old.track != track;
}

/// A whole number as − value + (R4a, docs/design-system.md §3 `Stepper`): the user taps instead of
/// typing. It edits [controller] as text, so a screen keeps its own parsing; the value stays
/// typeable for a large number, a long press repeats then moves ten steps, and the bounds hold.
class NumberStepper extends StatefulWidget {
  const NumberStepper({
    required this.controller,
    required this.label,
    this.fieldKey,
    this.min = 0,
    this.max = 1000000,
    this.step = 1,
    this.start,
    this.enabled = true,
    this.errorText,
    this.labelWidget,
    this.onChanged,
    super.key,
  });

  final TextEditingController controller;

  /// The field's name, read by screen readers on the buttons ("increase capacity").
  final String label;

  /// The key of the text field, so tests that typed a number keep finding it.
  final Key? fieldKey;
  final int min;
  final int max;
  final int step;

  /// Where the first tap on an empty field lands; [min] when absent.
  final int? start;
  final bool enabled;
  final String? errorText;

  /// Shown instead of [label] above the value (a required mark).
  final Widget? labelWidget;
  final ValueChanged<String>? onChanged;

  @override
  State<NumberStepper> createState() => _NumberStepperState();
}

class _NumberStepperState extends State<NumberStepper> {
  Timer? _repeat;
  int _ticks = 0;

  int? get _value => int.tryParse(widget.controller.text.trim());

  void _move(int sign, [int times = 1]) {
    final current = _value;
    final next = current == null
        ? (widget.start ?? widget.min)
        : (current + sign * widget.step * times).clamp(widget.min, widget.max);
    final text = '$next';
    if (text == widget.controller.text) return;
    setState(() => widget.controller.text = text);
    widget.onChanged?.call(text);
  }

  void _hold(int sign) {
    _ticks = 0;
    final wide = widget.max - widget.min >= widget.step * 100;
    _repeat = Timer.periodic(const Duration(milliseconds: 80), (_) {
      _ticks += 1;
      _move(sign, wide && _ticks > 10 ? 10 : 1);
    });
  }

  void _stop() {
    _repeat?.cancel();
    _repeat = null;
  }

  @override
  void dispose() {
    _stop();
    super.dispose();
  }

  Widget _button(BuildContext context, int sign) {
    final l10n = AppLocalizations.of(context);
    final value = _value;
    final atBound =
        value != null && (sign > 0 ? value >= widget.max : value <= widget.min);
    final active = widget.enabled && !atBound;
    return Semantics(
      button: true,
      enabled: active,
      label: sign > 0
          ? l10n.stepperIncrease(widget.label)
          : l10n.stepperDecrease(widget.label),
      excludeSemantics: true,
      child: GestureDetector(
        onLongPressStart: active ? (_) => _hold(sign) : null,
        onLongPressEnd: (_) => _stop(),
        onLongPressCancel: _stop,
        child: IconButton.filledTonal(
          key: switch (widget.fieldKey) {
            ValueKey<String>(:final value) => Key(
              '$value-${sign > 0 ? 'plus' : 'minus'}',
            ),
            _ => null,
          },
          constraints: const BoxConstraints.tightFor(width: 48, height: 48),
          onPressed: active ? () => _move(sign) : null,
          icon: Icon(sign > 0 ? Icons.add : Icons.remove),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: _button(context, -1),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: TextField(
          key: widget.fieldKey,
          controller: widget.controller,
          enabled: widget.enabled,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          textAlign: TextAlign.center,
          textDirection: TextDirection.ltr,
          style: const TextStyle(fontWeight: FontWeight.w700),
          decoration: InputDecoration(
            label: widget.labelWidget ?? Text(widget.label),
            errorText: widget.errorText,
          ),
          onChanged: (text) {
            setState(() {});
            widget.onChanged?.call(text);
          },
        ),
      ),
      const SizedBox(width: 8),
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: _button(context, 1),
      ),
    ],
  );
}
