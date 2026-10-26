import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/a11y/listen_action.dart';
import '../../core/http/error_messages.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/sim_banner.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import 'guide_models.dart';
import 'guide_providers.dart';

/// Emergency hub, phase B1: the topics (fires, fractures, first aid…), readable offline and
/// reachable before the terms are accepted, like the emergency numbers.
class GuideTopicsScreen extends ConsumerWidget {
  const GuideTopicsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final guide = ref.watch(emergencyGuideProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.guideTitle),
        actions: const [LanguageMenuAction()],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(emergencyGuideProvider.notifier).refresh(),
        child: guide.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(24),
            children: [Text(errorMessageFor(l10n, e))],
          ),
          data: (data) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              Text(l10n.guideIntro),
              const SizedBox(height: 12),
              const _Call198Button(),
              const SizedBox(height: 12),
              if (data.topics.isEmpty) Text(l10n.guideEmpty),
              for (final topic in data.topics)
                Card(
                  child: ListTile(
                    key: Key('guide-topic-${topic.key}'),
                    minTileHeight: 72,
                    leading: _TopicBadge(topic: topic),
                    title: Text(topic.titleFor(lang)),
                    subtitle: Text(l10n.guideItemsCount(topic.items.length)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push(Routes.guideTopic(topic.key)),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The items of one topic, in the editors' order. Items awaiting medical validation carry the
/// amber [SIM] tag.
class GuideTopicScreen extends ConsumerWidget {
  const GuideTopicScreen({super.key, required this.topicKey});

  final String topicKey;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final guide = ref.watch(emergencyGuideProvider).value;
    final topic = guide?.topic(topicKey);
    if (topic == null) return _Missing(loading: guide == null);
    return Scaffold(
      appBar: AppBar(
        title: Text(topic.titleFor(lang)),
        actions: const [LanguageMenuAction()],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (topic.hasSimulated) SimBanner(text: l10n.guideSimBanner),
          if (topic.items.isEmpty) Text(l10n.guideEmpty),
          for (final item in topic.items)
            Card(
              child: ListTile(
                key: Key('guide-item-${item.id}'),
                minTileHeight: 64,
                leading: _TopicBadge(topic: topic, size: 20),
                title: Text(item.textFor(lang).title),
                subtitle: item.validated ? null : const _SimTag(),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push(Routes.guideItem(topic.key, item.id)),
              ),
            ),
        ],
      ),
    );
  }
}

/// One item: when to call 198 at once, the numbered steps, and what not to do.
class GuideItemScreen extends ConsumerWidget {
  const GuideItemScreen({
    super.key,
    required this.topicKey,
    required this.itemId,
  });

  final String topicKey;
  final String itemId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final lang = ref.watch(localeCodeProvider);
    final guide = ref.watch(emergencyGuideProvider).value;
    final item = guide
        ?.topic(topicKey)
        ?.items
        .where((i) => i.id == itemId)
        .firstOrNull;
    if (item == null) return _Missing(loading: guide == null);
    final text = item.textFor(lang);
    // Read aloud in the order of the page: when to call, the numbered steps, what not to do.
    final spoken = [
      text.title,
      if (text.call.isNotEmpty) ...[l10n.guideCallNow, ...text.call],
      if (text.steps.isNotEmpty) ...[
        l10n.guideSteps,
        for (final (i, s) in text.steps.indexed) '${i + 1}. $s',
      ],
      if (text.dont.isNotEmpty) ...[l10n.guideDont, ...text.dont],
    ].join('\n');
    return Scaffold(
      appBar: AppBar(
        title: Text(text.title),
        actions: [
          ListenAction(id: 'guide-$itemId-$lang', text: spoken),
          const LanguageMenuAction(),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!item.validated) SimBanner(text: l10n.guideSimBanner),
          if (item.call198) ...[
            const _Call198Button(),
            const SizedBox(height: 12),
          ],
          if (text.call.isNotEmpty)
            _Section(
              key: const Key('guide-call'),
              title: l10n.guideCallNow,
              color: theme.colorScheme.error,
              icon: Icons.phone_in_talk,
              lines: text.call,
            ),
          if (text.steps.isNotEmpty)
            _Section(
              key: const Key('guide-steps'),
              title: l10n.guideSteps,
              color: theme.colorScheme.primary,
              lines: text.steps,
              numbered: true,
            ),
          if (text.dont.isNotEmpty)
            _Section(
              key: const Key('guide-dont'),
              title: l10n.guideDont,
              color: theme.colorScheme.error,
              icon: Icons.cancel,
              lines: text.dont,
            ),
        ],
      ),
    );
  }
}

class _Missing extends StatelessWidget {
  const _Missing({required this.loading});

  final bool loading;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.guideTitle),
        actions: const [LanguageMenuAction()],
      ),
      body: Center(
        child: loading
            ? const CircularProgressIndicator()
            : Text(l10n.errorNotFound),
      ),
    );
  }
}

class _TopicBadge extends StatelessWidget {
  const _TopicBadge({required this.topic, this.size = 28});

  final GuideTopic topic;
  final double size;

  @override
  Widget build(BuildContext context) => CircleAvatar(
    radius: size * 0.8,
    backgroundColor: guideColour(topic.colour),
    child: Icon(guideIcon(topic.icon), color: Colors.white, size: size),
  );
}

class _SimTag extends StatelessWidget {
  const _SimTag();

  @override
  Widget build(BuildContext context) => Align(
    alignment: AlignmentDirectional.centerStart,
    child: Container(
      key: const Key('guide-sim-tag'),
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: simAmber,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        AppLocalizations.of(context).guideSimTag,
        style: const TextStyle(color: Colors.black87, fontSize: 12),
      ),
    ),
  );
}

/// Dials 198 with the phone's own dialer: works without network.
class _Call198Button extends ConsumerWidget {
  const _Call198Button();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final civil = emergencyNumbers.first;
    return FilledButton.icon(
      key: const Key('guide-call-198'),
      style: FilledButton.styleFrom(
        backgroundColor: Theme.of(context).colorScheme.error,
        minimumSize: const Size.fromHeight(56),
      ),
      icon: const Icon(Icons.call),
      label: Text(l10n.guideCall198),
      onPressed: () async {
        final ok = await ref.read(dialerProvider)(civil.telUri);
        if (!ok && context.mounted) {
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(l10n.dialFailed)));
        }
      },
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    super.key,
    required this.title,
    required this.color,
    required this.lines,
    this.icon,
    this.numbered = false,
  });

  final String title;
  final Color color;
  final List<String> lines;
  final IconData? icon;
  final bool numbered;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
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
                style: theme.textTheme.titleMedium?.copyWith(color: color),
              ),
            ),
            const SizedBox(height: 8),
            for (final (n, line) in lines.indexed)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (numbered)
                      CircleAvatar(
                        radius: 12,
                        backgroundColor: color,
                        child: Text(
                          '${n + 1}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                          ),
                        ),
                      )
                    else
                      Icon(icon, size: 20, color: color),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(line, style: theme.textTheme.bodyLarge),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
