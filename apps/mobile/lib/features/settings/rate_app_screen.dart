import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/app_config.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';

/// Rate the app (phase P5b, F-APP-143): five stars, each a 48-point target with its own label,
/// and an optional remark. Not a request: no answer comes back, "contact us" is for that.
class RateAppScreen extends ConsumerStatefulWidget {
  const RateAppScreen({super.key});

  @override
  ConsumerState<RateAppScreen> createState() => _RateAppScreenState();
}

class _RateAppScreenState extends ConsumerState<RateAppScreen> {
  final _remark = TextEditingController();
  int _stars = 0;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _remark.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    if (_stars == 0) {
      setState(() => _error = l10n.rateChooseStars);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(apiProvider)
          .rateApp(
            stars: _stars,
            remark: _remark.text,
            platform: Theme.of(context).platform == TargetPlatform.iOS
                ? 'ios'
                : 'android',
            build: AppConfig.appBuild,
            version: AppConfig.appVersion,
            locale: Localizations.localeOf(context).languageCode,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(l10n.rateThanks)));
      context.pop();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final n = Neutrals.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.rateTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(l10n.rateQuestion, style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
          Wrap(
            alignment: WrapAlignment.center,
            children: [
              for (var i = 1; i <= 5; i++)
                Semantics(
                  selected: i == _stars,
                  child: IconButton(
                    key: Key('rate-star-$i'),
                    iconSize: 40,
                    tooltip: l10n.rateStar(i),
                    onPressed: _busy ? null : () => setState(() => _stars = i),
                    // The count is in the label: the filled star is not the only sign.
                    icon: Icon(
                      i <= _stars
                          ? Icons.star_rounded
                          : Icons.star_border_rounded,
                      color: i <= _stars ? Hue.amber : n.muted,
                    ),
                  ),
                ),
            ],
          ),
          if (_stars > 0)
            Center(
              child: Text(
                l10n.rateStar(_stars),
                style: theme.textTheme.titleMedium,
              ),
            ),
          const SizedBox(height: 16),
          TextField(
            key: const Key('rate-remark'),
            controller: _remark,
            maxLength: 1000,
            minLines: 3,
            maxLines: 6,
            decoration: InputDecoration(labelText: l10n.rateRemark),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                _error!,
                key: const Key('rate-error'),
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ),
          FilledButton.icon(
            key: const Key('rate-send'),
            onPressed: _busy ? null : _send,
            icon: const Icon(Icons.send_rounded),
            label: Text(l10n.rateSend),
          ),
          const SizedBox(height: 16),
          TextButton(
            key: const Key('rate-contact'),
            onPressed: () => context.push(Routes.contact),
            child: Text(l10n.rateContactNote),
          ),
        ],
      ),
    );
  }
}
