import 'package:flutter/material.dart';

/// Messenger of the root [MaterialApp]: lets services (push) show a message over whatever
/// screen is open.
final rootMessengerKey = GlobalKey<ScaffoldMessengerState>(
  debugLabel: 'root-messenger',
);

/// Shows [title] and [body] at the bottom of the current screen.
void showRootMessage(String title, String? body) {
  final messenger = rootMessengerKey.currentState;
  if (messenger == null) return;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 8),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
            if (body != null && body.isNotEmpty) Text(body),
          ],
        ),
      ),
    );
}
