import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_client.dart';
import '../../core/logging/log.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/tokens.dart';

final _log = logger('app_features');

/// Phase 5 (Yamen 2026-11-01): what the system administrator closed in the citizen app (catalogue
/// keys such as `citizen_guide`) and the message they show, read from `GET /api/v1/app/features`
/// at start and each time the app comes back to the front. Nothing is hidden without network: the
/// server refuses a closed window anyway, and the emergency report and the SOS are never closed.
class AppFeatures {
  const AppFeatures({this.hidden = const {}, this.warn = false, this.text});

  final Set<String> hidden;
  final bool warn;

  /// The message by language code ('ar', 'fr', 'en'), or null.
  final Map<String, String>? text;

  bool shows(String key) =>
      !hidden.contains(key) && !hidden.contains(key.split('.').first);

  String? messageIn(String code) {
    final t = text;
    if (t == null) return null;
    final own = t[code]?.trim() ?? '';
    return own.isNotEmpty ? own : t['ar'];
  }

  static AppFeatures fromJson(Map<String, Object?> j) {
    final a = j['announcement'];
    return AppFeatures(
      hidden: {for (final k in j['hidden'] as List? ?? const []) k as String},
      warn: a is Map && a['tone'] == 'warn',
      text: a is Map && (a['ar'] as String? ?? '').trim().isNotEmpty
          ? {
              for (final l in const ['ar', 'fr', 'en'])
                l: a[l] as String? ?? '',
            }
          : null,
    );
  }
}

final appFeaturesProvider = FutureProvider<AppFeatures>((ref) async {
  try {
    final r = await ref
        .read(apiDioProvider)
        .get<Map<String, Object?>>(
          '/api/v1/app/features',
          queryParameters: {'surface': 'citizen_app'},
        );
    final body = r.data;
    return body == null ? const AppFeatures() : AppFeatures.fromJson(body);
  } on Object catch (e) {
    _log.info('features not read: $e');
    return const AppFeatures();
  }
});

/// What the administrator closed, nothing while unknown.
final shownFeaturesProvider = Provider<AppFeatures>(
  (ref) => ref.watch(appFeaturesProvider).value ?? const AppFeatures(),
);

/// Reads the administrator's choices again each time the app comes back to the front.
class AppFeaturesRefresher extends ConsumerStatefulWidget {
  const AppFeaturesRefresher({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<AppFeaturesRefresher> createState() =>
      _AppFeaturesRefresherState();
}

class _AppFeaturesRefresherState extends ConsumerState<AppFeaturesRefresher>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) ref.invalidate(appFeaturesProvider);
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

/// The administrator's message, on top of the home screen.
class AnnouncementCard extends ConsumerWidget {
  const AnnouncementCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final f = ref.watch(shownFeaturesProvider);
    final text = f.messageIn(ref.watch(localeCodeProvider));
    if (text == null) return const SizedBox.shrink();
    final c = (f.warn ? Tone.amber : Tone.sky).colors(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Semantics(
        liveRegion: true,
        child: Material(
          key: const Key('announcement'),
          color: c.tint,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(
                  f.warn ? Icons.warning_amber : Icons.campaign,
                  color: c.onTint,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    text,
                    style: TextStyle(
                      color: c.onTint,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
