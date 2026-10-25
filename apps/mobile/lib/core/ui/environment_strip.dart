import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/update/app_release.dart';
import '../../l10n/app_localizations.dart';
import 'sim_banner.dart';

/// Backlog G3: a thin amber strip above every screen while the server says the data is test data
/// (development, field pilot, exercise), so nobody takes a test report for a real one. Nothing in
/// production. The value comes with `GET /api/v1/app/version` (fetched by the update check, never
/// by the strip) and is kept for offline starts.
class EnvironmentStrip extends ConsumerWidget {
  const EnvironmentStrip({super.key, required this.child});

  final Widget child;

  static String? label(AppLocalizations l10n, String? environment) =>
      switch (environment) {
        'development' => l10n.envBannerDevelopment,
        'pilot' => l10n.envBannerPilot,
        'training' => l10n.envBannerTraining,
        _ => null,
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final environment = ref.watch(environmentProvider);
    final text = label(AppLocalizations.of(context), environment);
    if (text == null) return child;
    return Column(
      children: [
        Material(
          key: const Key('environment-strip'),
          color: simAmber,
          child: SafeArea(
            bottom: false,
            child: Semantics(
              liveRegion: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 4,
                ),
                child: Row(
                  children: [
                    const Icon(Icons.science, size: 16, color: Colors.black87),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        text,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.black87,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        Expanded(
          child: MediaQuery.removePadding(
            context: context,
            removeTop: true,
            child: child,
          ),
        ),
      ],
    );
  }
}
