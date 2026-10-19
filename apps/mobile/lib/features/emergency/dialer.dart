import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

/// Opens the native dialer. Returns false when the device cannot place calls.
typedef Dialer = Future<bool> Function(Uri telUri);

Future<bool> _launchDialer(Uri telUri) async {
  try {
    return await launchUrl(telUri, mode: LaunchMode.externalApplication);
  } on Exception {
    return false;
  }
}

final dialerProvider = Provider<Dialer>((ref) => _launchDialer);
