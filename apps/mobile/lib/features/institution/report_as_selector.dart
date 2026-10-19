import 'package:flutter/material.dart';

import '../../core/http/models.dart';
import '../../l10n/app_localizations.dart';

/// "Report as: Myself / `<institution>`" (FR-A-080). Shown only when the account belongs to at
/// least one `active` institution. [value] null means the user themselves.
class ReportAsSelector extends StatelessWidget {
  const ReportAsSelector({
    super.key,
    required this.orgs,
    required this.value,
    required this.onChanged,
    this.title,
  });

  final List<MyOrg> orgs;
  final String? value;
  final ValueChanged<String?> onChanged;

  /// Defaults to "Report as" (as a heading); a custom title is shown as body text.
  final String? title;

  /// Radio value of "Myself" (institution ids are UUIDs, never empty).
  static const _self = '';

  @override
  Widget build(BuildContext context) {
    if (orgs.isEmpty) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Column(
      key: const Key('report-as'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          header: true,
          child: Text(
            title ?? l10n.reportAsTitle,
            style: title == null
                ? theme.textTheme.titleMedium
                : theme.textTheme.bodyMedium,
          ),
        ),
        RadioGroup<String>(
          groupValue: value ?? _self,
          onChanged: (v) {
            if (v != null) onChanged(v == _self ? null : v);
          },
          child: Column(
            children: [
              RadioListTile<String>(
                key: const Key('report-as-self'),
                value: _self,
                contentPadding: EdgeInsets.zero,
                secondary: const Icon(Icons.person),
                title: Text(l10n.reportAsSelf),
              ),
              for (final org in orgs)
                RadioListTile<String>(
                  key: Key('report-as-${org.id}'),
                  value: org.id,
                  contentPadding: EdgeInsets.zero,
                  secondary: const Icon(Icons.apartment),
                  title: Text(org.name),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
