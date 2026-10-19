import 'package:path/path.dart' as p;

import '../http/models.dart';

/// Media limits and accepted types (contract §4).
abstract final class MediaRules {
  static const maxFilesPerReport = 10;
  static const maxImageBytes = 20 * 1024 * 1024;
  static const maxVideoBytes = 300 * 1024 * 1024;
  static const maxAudioBytes = 30 * 1024 * 1024;
  static const maxAudioDuration = Duration(minutes: 5);

  static int maxBytes(MediaKind kind) => switch (kind) {
    MediaKind.image => maxImageBytes,
    MediaKind.video => maxVideoBytes,
    MediaKind.audio => maxAudioBytes,
  };

  static const _mimeByExtension = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.heic': 'image/heic',
    '.heif': 'image/heif',
    '.webp': 'image/webp',
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.3gp': 'video/3gpp',
    '.webm': 'video/webm',
    '.m4a': 'audio/mp4',
    '.aac': 'audio/aac',
    '.mp3': 'audio/mpeg',
    '.ogg': 'audio/ogg',
    '.wav': 'audio/wav',
  };

  /// MIME type accepted by the server for [path], or null when the format is not accepted.
  static String? mimeFor(String path) =>
      _mimeByExtension[p.extension(path).toLowerCase()];

  static MediaKind? kindOfMime(String mime) {
    if (mime.startsWith('image/')) return MediaKind.image;
    if (mime.startsWith('video/')) return MediaKind.video;
    if (mime.startsWith('audio/')) return MediaKind.audio;
    return null;
  }
}
