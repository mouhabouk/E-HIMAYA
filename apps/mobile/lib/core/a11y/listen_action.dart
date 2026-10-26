import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../settings/settings_controller.dart';
import 'speech.dart';

/// App bar button that reads the page aloud with the phone's voice, and stops it (NFR-10).
/// Leaving the page stops the reading.
class ListenAction extends ConsumerStatefulWidget {
  const ListenAction({super.key, required this.id, required this.text});

  /// Identifies the text, so only this page's button shows «stop».
  final String id;
  final String text;

  @override
  ConsumerState<ListenAction> createState() => _ListenActionState();
}

class _ListenActionState extends ConsumerState<ListenAction> {
  late final SpeakingController _speaking = ref.read(speakingProvider.notifier);

  @override
  void dispose() {
    // After this frame: providers cannot change while the tree is being torn down. When the
    // whole app is closing the controller is already gone, and the voice with it.
    final id = widget.id;
    unawaited(Future(() => _speaking.stopIf(id)).catchError((Object _) {}));
    super.dispose();
  }

  Future<void> _toggle() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final r = await _speaking.toggle(
      widget.id,
      widget.text,
      ref.read(localeCodeProvider),
    );
    final message = switch (r) {
      SpeechStart.noVoice => l10n.listenNoVoice,
      SpeechStart.failed => l10n.listenFailed,
      _ => null,
    };
    if (message != null) {
      messenger.showSnackBar(SnackBar(content: Text(message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final on = ref.watch(speakingProvider) == widget.id;
    return IconButton(
      key: const Key('listen-action'),
      tooltip: on ? l10n.listenStop : l10n.listenAction,
      isSelected: on,
      onPressed: widget.text.trim().isEmpty ? null : _toggle,
      icon: Icon(on ? Icons.stop_circle_outlined : Icons.volume_up_rounded),
    );
  }
}
