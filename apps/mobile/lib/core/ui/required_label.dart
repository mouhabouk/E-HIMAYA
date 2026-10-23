import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';

/// Rule 2 (phase A): a required field shows its label followed by a red asterisk, and screen
/// readers hear "required". Use as `InputDecoration(label: RequiredLabel('Name'))`.
class RequiredLabel extends StatelessWidget {
  const RequiredLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Semantics(
      label: '$text, ${l10n.requiredSemantics}',
      excludeSemantics: true,
      child: Text.rich(
        TextSpan(
          text: text,
          children: [
            TextSpan(
              text: ' *',
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// "Fields marked * are required." shown at the top of a form with required fields.
class RequiredNote extends StatelessWidget {
  const RequiredNote({super.key});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Text(
      AppLocalizations.of(context).requiredNote,
      key: const Key('required-note'),
      style: Theme.of(context).textTheme.bodySmall,
    ),
  );
}
