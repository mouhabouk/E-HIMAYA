import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/a11y/listen_action.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/notify_models.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import 'tips_providers.dart';

/// Safety tips by hazard (FR-A-062), readable offline.
class TipsScreen extends ConsumerWidget {
  const TipsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final tips = ref.watch(safetyTipsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.tipsTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(safetyTipsProvider.notifier).refresh(),
        child: tips.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(24),
            children: [Text(errorMessageFor(l10n, e))],
          ),
          data: (data) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(l10n.tipsIntro),
              const SizedBox(height: 12),
              for (final tip in data.items)
                NavCard(
                  key: Key('tip-${tip.hazard.wire}'),
                  icon: tipHazardIcon(tip.hazard),
                  tone: Tone.green,
                  title: _title(l10n, tip, lang),
                  onTap: () => context.push(Routes.tip(tip.hazard.wire)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

String _title(AppLocalizations l10n, SafetyTip tip, String lang) {
  final title = tip.textFor(lang).title;
  return title.trim().isEmpty ? tipHazardLabel(l10n, tip.hazard) : title;
}

class TipDetailScreen extends ConsumerWidget {
  const TipDetailScreen({super.key, required this.hazard});

  final String hazard;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final lang = ref.watch(localeCodeProvider);
    final tips = ref.watch(safetyTipsProvider).value;
    final tip = tips?.items.where((t) => t.hazard.wire == hazard).firstOrNull;
    if (tip == null) {
      return Scaffold(
        appBar: AppBar(
          title: Text(l10n.tipsTitle),
          actions: const [StandardAppBarActions()],
        ),
        body: Center(
          child: tips == null
              ? const CircularProgressIndicator()
              : Text(l10n.errorNotFound),
        ),
      );
    }
    final text = tip.textFor(lang);
    final title = _title(l10n, tip, lang);
    final spoken = [
      title,
      if (text.doItems.isNotEmpty) ...[l10n.tipsDo, ...text.doItems],
      if (text.dontItems.isNotEmpty) ...[l10n.tipsDont, ...text.dontItems],
    ].join('\n');
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          ListenAction(id: 'tip-$hazard-$lang', text: spoken),
          const StandardAppBarActions(),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _TipList(
            key: const Key('tip-do'),
            title: l10n.tipsDo,
            items: text.doItems,
            icon: Icons.check_circle,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: 16),
          _TipList(
            key: const Key('tip-dont'),
            title: l10n.tipsDont,
            items: text.dontItems,
            icon: Icons.cancel,
            color: theme.colorScheme.error,
          ),
        ],
      ),
    );
  }
}

class _TipList extends StatelessWidget {
  const _TipList({
    super.key,
    required this.title,
    required this.items,
    required this.icon,
    required this.color,
  });

  final String title;
  final List<String> items;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(
                title,
                style: Theme.of(context).textTheme.titleMedium
                    ?.copyWith(color: color),
              ),
            ),
            const SizedBox(height: 8),
            for (final item in items)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(icon, color: color, size: 20),
                    const SizedBox(width: 12),
                    Expanded(child: Text(item)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
