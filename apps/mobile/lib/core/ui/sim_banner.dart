import 'package:flutter/material.dart';

// ┏━━ SIMULATION ━━ amber strip shown only while a simulator stands in for a real service
// ┃   (phase A: SMS codes going to notify-sim). The server says so ("sms_simulated": true);
// ┃   it is never true with a real SMS provider, so nothing is to change for production.
// ┗━━━━━━━━━━━━━━━━

/// Amber colour reserved for simulations, distinct from every palette of the app.
const simAmber = Color(0xFFFFB300);

class SimBanner extends StatelessWidget {
  const SimBanner({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Container(
    key: const Key('sim-banner'),
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: simAmber,
      borderRadius: BorderRadius.circular(8),
    ),
    child: Row(
      children: [
        const Icon(Icons.science, color: Colors.black87),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: Colors.black87,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}
