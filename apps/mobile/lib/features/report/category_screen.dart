import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'category_labels.dart';

/// FR-A-040: category grid (SOS has its own one-touch button and is not offered here).
class CategoryScreen extends StatelessWidget {
  const CategoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.newReportTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              sliver: SliverToBoxAdapter(
                child: Text(
                  l10n.chooseCategory,
                  style: theme.textTheme.titleLarge,
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.all(16),
              sliver: SliverGrid.extent(
                maxCrossAxisExtent: 200,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                // Accessibility: taller cards as the text grows, so labels never clip.
                childAspectRatio:
                    1.15 /
                    (MediaQuery.textScalerOf(context).scale(10) / 10).clamp(
                      1.0,
                      3.0,
                    ),
                children: [
                  for (final c in ReportCategory.grid)
                    Card(
                      key: Key('category-${c.wire}'),
                      clipBehavior: Clip.antiAlias,
                      child: InkWell(
                        onTap: () => context.push(Routes.newReportFor(c)),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                categoryIcon(c),
                                size: 44,
                                color: theme.colorScheme.primary,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                categoryLabel(l10n, c),
                                textAlign: TextAlign.center,
                                style: theme.textTheme.titleSmall,
                              ),
                            ],
                          ),
                        ),
                      ),
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
