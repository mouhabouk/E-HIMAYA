import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/brand.dart';
import '../../l10n/app_localizations.dart';
import 'welcome_controller.dart';
import 'welcome_scaffold.dart';

/// Five introduction cards (addition 7): welcome, run by the Office, when, how, where.
class IntroScreen extends ConsumerStatefulWidget {
  const IntroScreen({super.key});

  @override
  ConsumerState<IntroScreen> createState() => _IntroScreenState();
}

class _IntroScreenState extends ConsumerState<IntroScreen> {
  final _pages = PageController();
  int _index = 0;

  static const _icons = [
    null,
    Icons.account_balance,
    Icons.local_fire_department,
    Icons.touch_app,
    Icons.map_outlined,
  ];

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  void _done() => ref.read(welcomeProvider.notifier).introSeen();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final cards = [
      (l10n.intro1Title, l10n.intro1Body),
      (l10n.intro2Title, l10n.intro2Body),
      (l10n.intro3Title, l10n.intro3Body),
      (l10n.intro4Title, l10n.intro4Body),
      (l10n.intro5Title, l10n.intro5Body),
    ];
    final last = _index == cards.length - 1;
    return WelcomeScaffold(
      bottom: Row(
        children: [
          TextButton(
            key: const Key('intro-skip'),
            onPressed: _done,
            child: Text(l10n.introSkip),
          ),
          Expanded(
            child: Semantics(
              label: l10n.introPage(_index + 1, cards.length),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var i = 0; i < cards.length; i++)
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      width: i == _index ? 20 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: i == _index
                            ? theme.colorScheme.primary
                            : theme.colorScheme.outlineVariant,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                ],
              ),
            ),
          ),
          FilledButton(
            key: const Key('intro-next'),
            onPressed: last
                ? _done
                : () => _pages.nextPage(
                    duration: const Duration(milliseconds: 250),
                    curve: Curves.easeOut,
                  ),
            child: Text(l10n.actionContinue),
          ),
        ],
      ),
      body: PageView.builder(
        controller: _pages,
        itemCount: cards.length,
        onPageChanged: (i) => setState(() => _index = i),
        itemBuilder: (_, i) => ListView(
          key: Key('intro-card-${i + 1}'),
          padding: const EdgeInsets.all(24),
          children: [
            const SizedBox(height: 16),
            Center(
              child: _icons[i] == null
                  ? const BrandLogo(size: 140)
                  : CircleAvatar(
                      radius: 64,
                      backgroundColor: theme.colorScheme.primaryContainer,
                      child: Icon(
                        _icons[i],
                        size: 64,
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
            ),
            const SizedBox(height: 32),
            Semantics(
              header: true,
              child: Text(
                cards[i].$1,
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              cards[i].$2,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyLarge,
            ),
          ],
        ),
      ),
    );
  }
}
