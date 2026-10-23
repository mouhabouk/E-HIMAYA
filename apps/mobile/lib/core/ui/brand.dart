import 'package:flutter/material.dart';

/// Logo of the Office (addition 1). Decorative next to the app's name: hidden from screen readers.
class BrandLogo extends StatelessWidget {
  const BrandLogo({super.key, this.size = 40});

  final double size;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: Image.asset(
      'assets/brand/logo.png',
      width: size,
      height: size,
      fit: BoxFit.contain,
    ),
  );
}
