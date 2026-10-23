import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/app_config.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_client.dart';
import '../../core/logging/log.dart';
import '../../core/storage/app_prefs.dart';

final _log = logger('update');

/// Latest release announced by the server (`GET /api/v1/app/version`, setting `app.release`).
class AppRelease {
  const AppRelease({
    required this.latestVersion,
    required this.latestBuild,
    required this.minBuild,
    required this.notes,
    required this.channel,
    this.downloadUrl,
    this.smsSimulated = false,
  });

  final String latestVersion;
  final int latestBuild;
  final int minBuild;
  final Map<String, String> notes;

  /// `server` (stage 1: the APK is on our server) or `play` (stage 2: the store listing).
  final String channel;
  final String? downloadUrl;

  /// SIMULATION: SMS codes go to the development gateway notify-sim.
  final bool smsSimulated;

  static AppRelease? tryParse(Map<String, Object?> json) {
    try {
      final notes = (json['notes'] as Map?)?.cast<String, Object?>() ?? {};
      return AppRelease(
        latestVersion: json['latest_version']! as String,
        latestBuild: (json['latest_build']! as num).toInt(),
        minBuild: (json['min_build']! as num).toInt(),
        notes: {
          for (final e in notes.entries)
            if (e.value is String) e.key: e.value! as String,
        },
        channel: json['channel'] as String? ?? 'server',
        downloadUrl: json['download_url'] as String?,
        smsSimulated: json['sms_simulated'] == true,
      );
    } on Object {
      return null;
    }
  }

  bool get updateAvailable => AppConfig.appBuild < latestBuild;

  /// Below the oldest build still allowed: the update cannot be skipped.
  bool get mandatory => AppConfig.appBuild < minBuild;

  /// Where "Update" goes: the server download (stage 1) or the store page (stage 2).
  Uri get updateUri => channel == 'play' || downloadUrl == null
      ? Uri.parse(
          'https://play.google.com/store/apps/details?id=${AppConfig.applicationId}',
        )
      : Uri.parse(downloadUrl!);

  String notesFor(String lang) => notes[lang]?.trim() ?? '';
}

/// The app asks at start and then at most once a day; the last answer is kept for offline starts.
class AppReleaseController extends AsyncNotifier<AppRelease?> {
  static const checkEvery = Duration(hours: 24);

  @override
  Future<AppRelease?> build() async {
    final prefs = ref.read(appPrefsProvider);
    final cachedRaw = prefs.releaseJson;
    final cached = cachedRaw == null
        ? null
        : AppRelease.tryParse(jsonDecode(cachedRaw) as Map<String, Object?>);
    final now = ref.read(clockProvider)();
    final checkedAt = prefs.releaseCheckedAt;
    if (cached != null &&
        checkedAt != null &&
        now.difference(checkedAt) < checkEvery &&
        !cached.mandatory) {
      return cached;
    }
    return await _fetch(now) ?? cached;
  }

  Future<AppRelease?> _fetch(DateTime now) async {
    try {
      final r = await ref
          .read(apiDioProvider)
          .get<Map<String, Object?>>(
            '/api/v1/app/version',
            queryParameters: {
              'platform': 'android',
              'build': AppConfig.appBuild,
            },
          );
      final body = r.data;
      final release = body == null ? null : AppRelease.tryParse(body);
      if (release != null) {
        await ref.read(appPrefsProvider).setRelease(jsonEncode(body), now);
      }
      return release;
    } on DioException catch (e) {
      _log.info('version check failed: ${e.type.name}');
      return null;
    }
  }

  /// "Later" on an optional update: not offered again for this build.
  Future<void> postpone(AppRelease release) =>
      ref.read(appPrefsProvider).setUpdatePostponedBuild(release.latestBuild);
}

final appReleaseProvider =
    AsyncNotifierProvider<AppReleaseController, AppRelease?>(
      AppReleaseController.new,
    );
