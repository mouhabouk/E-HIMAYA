// Screenshots and on-screen regions of the mobile apps for the flowchart atlas (Yamen, 2026-11-13).
//
// Used by atlas_citizen_test.dart and atlas_staff_test.dart, which run only when ATLAS_OUT names a folder:
//   ATLAS_OUT=/tmp/atlas-mobile flutter test test/atlas
// Each screen is pumped with the fakes of the widget tests ([SIM] data, no network), then written as
// <ATLAS_OUT>/shots/<id>.png with <ATLAS_OUT>/<id>.json: the regions a flowchart box points at and the requests
// the screen sent to the API while it opened.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

final String? atlasOut = Platform.environment['ATLAS_OUT'];
final bool atlasSkip = atlasOut == null || atlasOut!.isEmpty;

/// ATLAS_ONLY=id,id retakes only those screens.
Set<String>? atlasOnly() {
  final v = Platform.environment['ATLAS_ONLY'];
  return v == null || v.isEmpty
      ? null
      : v.split(',').map((e) => e.trim()).toSet();
}

/// Scrolls the widget of [key] into view and taps it, then lets the window open.
Future<void> tapKey(WidgetTester tester, String key) async {
  final f = find.byKey(Key(key), skipOffstage: false);
  if (f.evaluate().isEmpty) {
    // A lazy list builds its rows only near the screen: scroll down until the row exists.
    final lists = find.byWidgetPredicate(
      (w) => w is Scrollable && w.axisDirection == AxisDirection.down,
    );
    if (lists.evaluate().isNotEmpty) {
      await tester
          .scrollUntilVisible(
            find.byKey(Key(key)),
            300,
            scrollable: lists.first,
            maxScrolls: 30,
          )
          .catchError((_) {});
    }
  }
  if (f.evaluate().isEmpty) {
    File('$atlasOut/missed.txt')
        .writeAsStringSync('no key $key\n', mode: FileMode.append);
    return;
  }
  await tester.ensureVisible(f.first);
  await tester.pump();
  await tester.tap(f.first, warnIfMissed: false);
  await tester
      .pumpAndSettle(
        const Duration(milliseconds: 50),
        EnginePhase.sendSemanticsUpdate,
        const Duration(seconds: 5),
      )
      .catchError((_) => 0);
}

/// The phone of the screenshots: 390 × 844 logical pixels, drawn at 2×.
const atlasPhone = Size(390, 844);
const atlasRatio = 2.0;

/// Real glyphs instead of the test font: the app's Arabic font and the Material icons of the SDK.
Future<void> loadAtlasFonts() async {
  final arabic = FontLoader('IBMPlexSansArabic');
  for (final w in ['Regular', 'Medium', 'SemiBold', 'Bold']) {
    arabic.addFont(_bytes('assets/fonts/IBMPlexSansArabic-$w.ttf'));
  }
  await arabic.load();
  final sdk =
      Platform.environment['FLUTTER_ROOT'] ??
      File(Platform.resolvedExecutable).parent.parent.parent.parent.parent.path;
  final fonts = '$sdk/bin/cache/artifacts/material_fonts';
  final icons = FontLoader('MaterialIcons')
    ..addFont(_bytes('$fonts/MaterialIcons-Regular.otf'));
  await icons.load();
  final roboto = FontLoader('Roboto');
  for (final w in ['Regular', 'Medium', 'Bold']) {
    roboto.addFont(_bytes('$fonts/Roboto-$w.ttf'));
  }
  await roboto.load();
}

Future<ByteData> _bytes(String path) async =>
    ByteData.sublistView(File(path).readAsBytesSync());

/// Platform plugins the host tests do not have (the audio recorder), answered with nothing.
void quietPlugins() {
  final m = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  m.setMockMethodCallHandler(
    const MethodChannel('com.llfbandit.record/messages'),
    (_) async => null,
  );
  final tmp = Directory.systemTemp.createTempSync('atlas').path;
  m.setMockMethodCallHandler(
    const MethodChannel('plugins.flutter.io/path_provider'),
    (_) async => tmp,
  );
}

void sizePhone(WidgetTester tester, {double height = 844}) {
  tester.view.physicalSize = Size(
    atlasPhone.width * atlasRatio,
    height * atlasRatio,
  );
  tester.view.devicePixelRatio = atlasRatio;
}

String _text(Element e) {
  final parts = <String>[];
  void visit(Element c) {
    final w = c.widget;
    if (w is Text) {
      parts.add(w.data ?? w.textSpan?.toPlainText() ?? '');
    } else if (w is RichText) {
      parts.add(w.text.toPlainText());
      return;
    } else if (w is EditableText) {
      parts.add(w.controller.text);
    } else if (w is TextField && w.decoration?.labelText != null) {
      parts.add(w.decoration!.labelText!);
    }
    c.visitChildren(visit);
  }

  visit(e);
  final clean = <String>[];
  for (final p in parts) {
    final t = p
        .replaceAll(
          RegExp(r'[\u{E000}-\u{F8FF}\u{F0000}-\u{FFFFD}]', unicode: true),
          '',
        )
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    if (t.isNotEmpty && !clean.contains(t)) clean.add(t);
  }
  return clean.join(' · ');
}

/// The regions of the screen, in reading order: bars, tabs, fields, buttons, list entries and cards.
List<Map<String, Object?>> regions(WidgetTester tester) {
  final out = <Map<String, Object?>>[];
  final seen = <Rect>[];
  void add(String kind, Finder f, {int max = 6, String? label}) {
    var n = 0;
    for (final e in f.evaluate()) {
      if (n >= max) break;
      final ro = e.renderObject;
      if (ro is! RenderBox || !ro.hasSize || !ro.attached) continue;
      final r = ro.localToGlobal(Offset.zero) & ro.size;
      if (r.width < 24 ||
          r.height < 16 ||
          r.top >= tester.view.physicalSize.height / atlasRatio ||
          r.bottom <= 0) {
        continue;
      }
      if (seen.any(
        (s) =>
            (s.left - r.left).abs() < 3 &&
            (s.top - r.top).abs() < 3 &&
            (s.width - r.width).abs() < 3,
      )) {
        continue;
      }
      final t = label ?? _text(e);
      if (t.runes.length < 2 && kind != 'map') continue;
      seen.add(r);
      n++;
      out.add({
        'kind': kind,
        'label': t.length > 90 ? t.substring(0, 90) : t,
        'x': (r.left * atlasRatio).round(),
        'y': (r.top * atlasRatio).round(),
        'w': (r.width * atlasRatio).round(),
        'h': (r.height * atlasRatio).round(),
      });
    }
  }

  // An open window (dialog or bottom sheet): it is the region of the card, and its own parts follow it.
  final win = find.byWidgetPredicate(
    (w) => w is Dialog || w is AlertDialog || w is BottomSheet,
  );
  if (win.evaluate().isNotEmpty) {
    add('window', win.last, max: 1);
    for (final (k, f, n) in [
      ('form', find.byType(TextField), 4),
      ('action', find.byType(FilledButton), 3),
      ('action', find.byType(TextButton), 3),
      ('action', find.byType(OutlinedButton), 2),
      ('section', find.byType(ChoiceChip), 8),
      ('section', find.byType(FilterChip), 8),
      ('section', find.byType(ListTile), 6),
    ]) {
      add(
        k,
        find.descendant(of: win.last, matching: f),
        max: n,
      );
    }
    return out;
  }
  add('title', find.byType(AppBar), max: 1);
  add('tabs', find.byType(TabBar), max: 1);
  add('tabs', find.byType(SegmentedButton<Object?>), max: 1);
  add('form', find.byType(TextField), max: 4);
  add('form', find.byType(DropdownButtonFormField<Object?>), max: 2);
  add('action', find.byType(FilledButton), max: 3);
  add('action', find.byType(ElevatedButton), max: 2);
  add('action', find.byType(FloatingActionButton), max: 1);
  add('section', find.byType(ListTile), max: 7);
  add('section', find.byType(Card), max: 5);
  add('action', find.byType(OutlinedButton), max: 2);
  add('menu', find.byType(NavigationBar), max: 1, label: 'شريط التنقل السفلي');
  // The app's own keyed widgets (the keys the widget tests use): the SOS button, the cards, the steps.
  add(
    'section',
    find.byWidgetPredicate(
      (w) =>
          w.key is ValueKey<String> &&
          !(w is Text || w is Icon || w is Scrollable),
    ),
    max: 8,
  );
  out.sort((a, b) {
    final dy = (a['y']! as int) - (b['y']! as int);
    if (dy.abs() < 14) return (b['x']! as int) - (a['x']! as int);
    return dy;
  });
  return out;
}

/// Writes the screenshot, the regions and the requests seen since [since] for the screen [id].
Future<void> shot(
  WidgetTester tester,
  String id, {
  FakeAdapter? adapter,
  int since = 0,
  Map<String, Object?> extra = const {},
}) async {
  await tester
      .pumpAndSettle(
        const Duration(milliseconds: 50),
        EnginePhase.sendSemanticsUpdate,
        const Duration(seconds: 5),
      )
      .catchError((_) => 0);
  // A long screen is shown whole: the phone grows to the length of its first scrolling list.
  final scroll = find
      .byType(Scrollable)
      .evaluate()
      .map((e) => (e as StatefulElement).state as ScrollableState)
      .where(
        (s) =>
            s.position.axis == Axis.vertical && s.position.hasContentDimensions,
      );
  // A window (dialog or sheet) is shown on the phone as it opens, not on a page grown under it.
  final window = find
      .byWidgetPredicate(
        (w) => w is Dialog || w is AlertDialog || w is BottomSheet,
        skipOffstage: false,
      )
      .evaluate()
      .isNotEmpty;
  final extra2 = scroll.isEmpty || window
      ? 0.0
      : scroll
            .map((s) => s.position.maxScrollExtent)
            .reduce((a, b) => a > b ? a : b);
  if (extra2 > 0) {
    sizePhone(
      tester,
      height: (atlasPhone.height + extra2).clamp(atlasPhone.height, 2400),
    );
    await tester
        .pumpAndSettle(
          const Duration(milliseconds: 50),
          EnginePhase.sendSemanticsUpdate,
          const Duration(seconds: 5),
        )
        .catchError((_) => 0);
  }
  final view = tester.binding.renderViews.first;
  final layer = view.debugLayer! as OffsetLayer;
  final size = tester.view.physicalSize / atlasRatio;
  final png = await tester.runAsync(() async {
    final image = await layer.toImage(Offset.zero & tester.view.physicalSize);
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    return data!.buffer.asUint8List();
  });
  final dir = Directory('$atlasOut/shots')..createSync(recursive: true);
  File('${dir.path}/$id.png').writeAsBytesSync(png!);
  final calls = adapter == null
      ? const <Map<String, String>>[]
      : adapter.requests
            .skip(since)
            .map((r) => {'verb': r.method, 'path': r.path})
            .toList();
  final title = find.descendant(
    of: find.byType(AppBar),
    matching: find.byType(Text),
  );
  File('$atlasOut/$id.json').writeAsStringSync(
    const JsonEncoder.withIndent(' ').convert({
      'id': id,
      'shot': 'shots/$id.png',
      'width': (size.width * atlasRatio).round(),
      'height': (size.height * atlasRatio).round(),
      'title': title.evaluate().isEmpty ? '' : _text(title.evaluate().first),
      'regions': regions(tester),
      'api': calls,
      ...extra,
    }),
  );
}
