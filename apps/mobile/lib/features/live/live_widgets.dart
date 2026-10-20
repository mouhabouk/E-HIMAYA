import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/providers.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';

/// `mm:ss` (or `h:mm:ss`), always left to right.
String formatLiveDuration(Duration d) {
  final s = d.isNegative ? Duration.zero : d;
  final mm = (s.inMinutes % 60).toString().padLeft(2, '0');
  final ss = (s.inSeconds % 60).toString().padLeft(2, '0');
  return s.inHours > 0 ? '${s.inHours}:$mm:$ss' : '$mm:$ss';
}

/// Rebuilds every second with the time elapsed since [since] (null: zero).
class _Ticking extends ConsumerStatefulWidget {
  const _Ticking({required this.since, required this.builder});

  final DateTime? since;
  final Widget Function(BuildContext context, Duration elapsed) builder;

  @override
  ConsumerState<_Ticking> createState() => _TickingState();
}

class _TickingState extends ConsumerState<_Ticking> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final since = widget.since;
    final elapsed = since == null
        ? Duration.zero
        : ref.read(clockProvider)().difference(since);
    return widget.builder(context, elapsed);
  }
}

/// FR-A-052: the big red pulsing "مباشر / EN DIRECT / LIVE" pill with the elapsed time. The
/// pulse stops when the system asks for reduced motion; the text and colour stay.
class LiveIndicator extends StatefulWidget {
  const LiveIndicator({super.key, required this.startedAt});

  final DateTime? startedAt;

  @override
  State<LiveIndicator> createState() => _LiveIndicatorState();
}

class _LiveIndicatorState extends State<LiveIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _pulse
        ..stop()
        ..value = 1;
    } else if (!_pulse.isAnimating) {
      _pulse.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    return _Ticking(
      since: widget.startedAt,
      builder: (context, elapsed) {
        final time = formatLiveDuration(elapsed);
        return Semantics(
          key: const Key('live-indicator'),
          container: true,
          liveRegion: true,
          label: '${l10n.liveBadge}. ${l10n.liveSemanticsOnAir(time)}',
          excludeSemantics: true,
          child: AnimatedBuilder(
            animation: _pulse,
            builder: (context, child) => DecoratedBox(
              decoration: BoxDecoration(
                color: sosRed,
                borderRadius: BorderRadius.circular(28),
                boxShadow: [
                  BoxShadow(
                    color: sosRed.withValues(alpha: 0.35 + 0.4 * _pulse.value),
                    blurRadius: 6 + 14 * _pulse.value,
                    spreadRadius: 1 + 4 * _pulse.value,
                  ),
                ],
              ),
              child: child,
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  FadeTransition(
                    opacity: Tween<double>(begin: 0.35, end: 1).animate(_pulse),
                    child: const Icon(
                      Icons.fiber_manual_record,
                      color: Colors.white,
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    l10n.liveBadge,
                    style: text.titleLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    time,
                    key: const Key('live-elapsed'),
                    textDirection: TextDirection.ltr,
                    style: text.titleLarge?.copyWith(
                      color: Colors.white,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Remaining time, shown during the last minutes before `max_duration_s`.
class LiveRemaining extends StatelessWidget {
  const LiveRemaining({
    super.key,
    required this.startedAt,
    required this.maxDuration,
    this.showWithin = const Duration(minutes: 2),
  });

  final DateTime? startedAt;
  final Duration maxDuration;
  final Duration showWithin;

  @override
  Widget build(BuildContext context) => _Ticking(
    since: startedAt,
    builder: (context, elapsed) {
      final left = maxDuration - elapsed;
      if (startedAt == null || left > showWithin) {
        return const SizedBox.shrink();
      }
      return LivePill(
        icon: Icons.timer_outlined,
        text: AppLocalizations.of(context).liveEndsIn(formatLiveDuration(left)),
      );
    },
  );
}

/// Dark translucent pill over the camera picture (status, report code, location).
class LivePill extends StatelessWidget {
  const LivePill({
    super.key,
    required this.icon,
    required this.text,
    this.color,
  });

  final IconData icon;
  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
    decoration: BoxDecoration(
      color: color ?? Colors.black.withValues(alpha: 0.6),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: Colors.white, size: 18),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            text,
            style: Theme.of(context).textTheme.bodyMedium
                ?.copyWith(color: Colors.white),
          ),
        ),
      ],
    ),
  );
}

// ┏━━ SIMULATION ━━ Amber "وضع المحاكاة" band shown when the API answered `"simulated": true`
// ┃ (phase 6 §6). PRODUCTION: nothing to remove: a real stream is never flagged simulated.
// ┗━━━━━━━━━━━━━━━━
/// Same amber band as the push simulator's, so a test stream is never taken for a real one.
class LiveSimulationBand extends StatelessWidget {
  const LiveSimulationBand({super.key});

  static const _background = Color(0xFFFFB300); // amber 600
  static const _foreground = Color(0xFF3E2723);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    return Semantics(
      container: true,
      liveRegion: true,
      child: Container(
        key: const Key('live-simulation-band'),
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        color: _background,
        child: Row(
          children: [
            const Icon(Icons.science_outlined, color: _foreground),
            const SizedBox(width: 8),
            Expanded(
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: '${l10n.liveSimulationBadge} · ',
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    TextSpan(text: l10n.liveSimulationHelp),
                  ],
                ),
                style: text.bodySmall?.copyWith(color: _foreground),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
