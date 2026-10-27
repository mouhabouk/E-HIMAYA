import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/ui/brand.dart';
import '../core/ui/language_bar.dart';
import '../core/ui/tokens.dart';
import '../l10n/app_localizations.dart';
import 'staff_app.dart' show staffLauncherProvider;
import 'staff_controller.dart';

/// Language and theme in every app bar of the staff app (design system rule 1).
List<Widget> staffBarActions() => const [
  LanguageMenuAction(),
  ThemeToggleAction(),
];

/// The dark bar of the field app (phase P4b, design §5.2): the logo, the screen's title and a
/// short line under it (the vehicle and the place).
class StaffAppBar extends StatelessWidget implements PreferredSizeWidget {
  const StaffAppBar({
    super.key,
    required this.title,
    this.subtitle,
    this.actions = const [],
  });

  final String title;
  final String? subtitle;
  final List<Widget> actions;

  @override
  Size get preferredSize => const Size.fromHeight(64);

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final bg = dark ? Neutrals.dark.card : Neutrals.light.ink;
    final sub = subtitle;
    return AppBar(
      backgroundColor: bg,
      foregroundColor: Colors.white,
      toolbarHeight: 64,
      systemOverlayStyle: SystemUiOverlayStyle.light,
      titleSpacing: 8,
      title: Row(
        children: [
          const BrandLogo(size: 34),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 19,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (sub != null && sub.isNotEmpty)
                  Text(
                    sub,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xFFC9D1E6),
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
      actions: [...staffBarActions(), ...actions],
    );
  }
}

/// Under the bar: green "connected · updated N s ago", or amber "no connection · last copy".
class ConnectionStrip extends ConsumerStatefulWidget {
  const ConnectionStrip({super.key});

  @override
  ConsumerState<ConnectionStrip> createState() => _ConnectionStripState();
}

class _ConnectionStripState extends ConsumerState<ConnectionStrip> {
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (offline, sync, pending) = ref.watch(
      staffControllerProvider.select((s) => (s.offline, s.lastSync, s.pending)),
    );
    if (!offline && sync == null && pending == 0) {
      return const SizedBox.shrink();
    }
    if (pending > 0) return const MissionPendingBar();
    final tone = offline ? Tone.amber : Tone.green;
    final c = tone.colors(context);
    final String text;
    if (offline) {
      text = l10n.staffOffline;
    } else {
      final ago = DateTime.now()
          .difference(sync ?? DateTime.now())
          .inSeconds
          .clamp(0, 1 << 30);
      text = ago < 60
          ? l10n.staffOnline(ago)
          : l10n.staffOnlineMinutes(ago ~/ 60);
    }
    return Container(
      key: Key(offline ? 'staff-offline' : 'staff-online'),
      width: double.infinity,
      color: c.tint,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
      child: Row(
        children: [
          Icon(
            offline ? Icons.cloud_off : Icons.circle,
            size: offline ? 16 : 10,
            color: offline ? c.onTint : c.fill,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(color: c.onTint, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

/// The writes kept on the phone (phase P4d, design §9.1): «N في الانتظار» with «أرسل الآن», and
/// «أرسل برسالة قصيرة» while a step or an alert waits and the phone can sign its messages.
class MissionPendingBar extends ConsumerWidget {
  const MissionPendingBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = Tone.amber.colors(context);
    final controller = ref.read(staffControllerProvider.notifier);
    final sms = s.smsCapable && s.smsWaiting.isNotEmpty;
    return Container(
      key: const Key('staff-pending'),
      width: double.infinity,
      color: c.tint,
      padding: const EdgeInsets.fromLTRB(16, 6, 8, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                s.offline ? Icons.cloud_off : Icons.schedule_send,
                size: 18,
                color: c.onTint,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  l10n.staffPending(s.pending),
                  style: TextStyle(
                    color: c.onTint,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          Wrap(
            alignment: WrapAlignment.end,
            spacing: 4,
            children: [
              TextButton.icon(
                key: const Key('staff-send-now'),
                onPressed: s.syncing
                    ? null
                    : () => unawaited(controller.sync()),
                icon: const Icon(Icons.sync, size: 18),
                label: Text(l10n.staffSendNow),
                style: TextButton.styleFrom(foregroundColor: c.onTint),
              ),
              if (sms)
                TextButton.icon(
                  key: const Key('staff-send-sms'),
                  onPressed: () async {
                    final messenger = ScaffoldMessenger.maybeOf(context);
                    final opened = await controller.sendBySms(
                      ref.read(staffLauncherProvider),
                    );
                    if (opened) {
                      messenger?.showSnackBar(
                        SnackBar(content: Text(l10n.staffSmsOpened)),
                      );
                    }
                  },
                  icon: const Icon(Icons.sms_outlined, size: 18),
                  label: Text(l10n.staffSendSms),
                  style: TextButton.styleFrom(foregroundColor: c.onTint),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
