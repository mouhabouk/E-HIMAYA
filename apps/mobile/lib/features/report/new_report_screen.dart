import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/http/models.dart';
import '../../core/logging/log.dart';
import '../../core/media/media_rules.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/sync/report_queue.dart';
import '../../core/sync/sync_scheduler.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'audio_recorder_panel.dart';
import 'category_labels.dart';
import 'location_picker.dart';

final _log = logger('report.new');

final imagePickerProvider = Provider<ImagePicker>((ref) => ImagePicker());

/// FR-A-040..047: optional text (language = UI language), GPS + map pin, photos/videos,
/// voice message, then saved to the encrypted queue with a temporary code.
class NewReportScreen extends ConsumerStatefulWidget {
  const NewReportScreen({super.key, required this.category});

  final ReportCategory category;

  @override
  ConsumerState<NewReportScreen> createState() => _NewReportScreenState();
}

class _NewReportScreenState extends ConsumerState<NewReportScreen> {
  final _text = TextEditingController();
  final _attachments = <DraftAttachment>[];
  GeoPoint? _location;
  String? _audioPath;
  bool _submitting = false;

  static const _maxTextLength = 4000;

  int get _fileCount => _attachments.length + (_audioPath == null ? 0 : 1);

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  void _snack(String message) =>
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));

  Future<void> _pick(MediaKind kind, ImageSource source) async {
    final l10n = AppLocalizations.of(context);
    if (_fileCount >= MediaRules.maxFilesPerReport) {
      _snack(l10n.attachmentLimit(MediaRules.maxFilesPerReport));
      return;
    }
    final picker = ref.read(imagePickerProvider);
    List<XFile> files;
    try {
      if (kind == MediaKind.image && source == ImageSource.gallery) {
        files = await picker.pickMultiImage(
          imageQuality: 90,
          limit: MediaRules.maxFilesPerReport - _fileCount,
        );
      } else if (kind == MediaKind.image) {
        final f = await picker.pickImage(source: source, imageQuality: 90);
        files = [?f];
      } else {
        final f = await picker.pickVideo(
          source: source,
          maxDuration: const Duration(minutes: 5),
        );
        files = [?f];
      }
    } on Exception catch (e) {
      _log.info('picker failed: ${e.runtimeType}');
      _snack(l10n.pickerFailed);
      return;
    }
    for (final f in files) {
      if (_fileCount >= MediaRules.maxFilesPerReport) {
        _snack(l10n.attachmentLimit(MediaRules.maxFilesPerReport));
        break;
      }
      final mime = MediaRules.mimeFor(f.path);
      if (mime == null || MediaRules.kindOfMime(mime) != kind) {
        _snack(l10n.attachmentUnsupported);
        continue;
      }
      final size = await File(f.path).length();
      if (size > MediaRules.maxBytes(kind)) {
        _snack(
          l10n.attachmentTooLarge(MediaRules.maxBytes(kind) ~/ (1024 * 1024)),
        );
        continue;
      }
      setState(
        () => _attachments.add(
          DraftAttachment(path: f.path, kind: kind, mime: mime),
        ),
      );
    }
  }

  Future<void> _submit() async {
    final l10n = AppLocalizations.of(context);
    final location = _location;
    if (location == null) {
      _snack(l10n.reportNeedsLocation);
      return;
    }
    if (!location.isInTunisiaBox) {
      _snack(l10n.locationOutsideTunisia);
      return;
    }
    setState(() => _submitting = true);
    final router = GoRouter.of(context);
    try {
      final audio = _audioPath;
      final queued = await ref
          .read(reportQueueProvider)
          .enqueue(
            ReportDraft(
              category: widget.category,
              location: location,
              text: _text.text,
              lang: ref.read(localeCodeProvider),
              attachments: [
                ..._attachments,
                if (audio != null)
                  DraftAttachment(
                    path: audio,
                    kind: MediaKind.audio,
                    mime: 'audio/mp4',
                    deleteSourceAfterQueue: true,
                  ),
              ],
            ),
          );
      unawaited(ref.read(requestSyncProvider)());
      unawaited(
        router.pushReplacement(
          Uri(
            path: Routes.reportQueued,
            queryParameters: {'code': queued.tempCode},
          ).toString(),
        ),
      );
    } on Exception catch (e) {
      _log.warning('enqueue failed: ${e.runtimeType}');
      if (mounted) {
        setState(() => _submitting = false);
        _snack(l10n.reportSaveFailed);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(categoryLabel(l10n, widget.category)),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: AbsorbPointer(
          absorbing: _submitting,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(l10n.reportLocation, style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              LocationPicker(onChanged: (p) => _location = p),
              const SizedBox(height: 24),
              TextField(
                key: const Key('report-text'),
                controller: _text,
                maxLines: 5,
                minLines: 3,
                maxLength: _maxTextLength,
                decoration: InputDecoration(
                  labelText: l10n.reportDescription,
                  hintText: l10n.reportDescriptionHint,
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 16),
              Text(l10n.reportAttachments, style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => _pick(MediaKind.image, ImageSource.camera),
                    icon: const Icon(Icons.photo_camera),
                    label: Text(l10n.attachTakePhoto),
                  ),
                  OutlinedButton.icon(
                    onPressed: () =>
                        _pick(MediaKind.image, ImageSource.gallery),
                    icon: const Icon(Icons.photo_library),
                    label: Text(l10n.attachPickPhoto),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _pick(MediaKind.video, ImageSource.camera),
                    icon: const Icon(Icons.videocam),
                    label: Text(l10n.attachRecordVideo),
                  ),
                  OutlinedButton.icon(
                    onPressed: () =>
                        _pick(MediaKind.video, ImageSource.gallery),
                    icon: const Icon(Icons.video_library),
                    label: Text(l10n.attachPickVideo),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              for (final (i, a) in _attachments.indexed)
                Card(
                  child: ListTile(
                    leading: a.kind == MediaKind.image
                        ? ClipRRect(
                            borderRadius: BorderRadius.circular(6),
                            child: Image.file(
                              File(a.path),
                              width: 56,
                              height: 56,
                              fit: BoxFit.cover,
                              cacheWidth: 112,
                              errorBuilder: (_, _, _) =>
                                  const Icon(Icons.image),
                            ),
                          )
                        : const Icon(Icons.movie, size: 40),
                    title: Text(
                      a.kind == MediaKind.image
                          ? l10n.attachmentPhoto(i + 1)
                          : l10n.attachmentVideo(i + 1),
                    ),
                    trailing: IconButton(
                      tooltip: l10n.removeAttachment,
                      icon: const Icon(Icons.close),
                      onPressed: () => setState(() => _attachments.removeAt(i)),
                    ),
                  ),
                ),
              const SizedBox(height: 8),
              AudioRecorderPanel(
                onChanged: (path) => setState(() => _audioPath = path),
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                key: const Key('report-submit'),
                onPressed: _submitting ? null : _submit,
                icon: _submitting
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send),
                label: Text(l10n.reportSubmit),
              ),
              const SizedBox(height: 8),
              Text(l10n.reportOfflineNote, style: theme.textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}
