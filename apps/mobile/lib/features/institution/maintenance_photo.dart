import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/http/api_client.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/media/media_rules.dart';
import '../../core/tus/tus_client.dart';

/// Largest photo the server accepts for a maintenance (phase P2b).
const maintenancePhotoMaxBytes = 10 * 1024 * 1024;

/// Takes the maintenance photo with the camera (null when cancelled). Tests replace it.
final maintenancePhotoPickerProvider = Provider<Future<File?> Function()>(
  (ref) => () async {
    final f = await ImagePicker().pickImage(
      source: ImageSource.camera,
      imageQuality: 80,
      maxWidth: 2048,
    );
    return f == null ? null : File(f.path);
  },
);

/// tus client of the institution documents (same tusd, same identity header as the reports).
final orgTusProvider = Provider<TusClient>(
  (ref) => TusClient(ref.watch(tusDioProvider)),
);

/// Why a photo cannot be sent.
enum PhotoProblem { unsupported, tooLarge }

/// JPEG or PNG of at most 10 MB, or the problem.
Future<PhotoProblem?> checkMaintenancePhoto(File file) async {
  final mime = MediaRules.mimeFor(file.path);
  if (mime != 'image/jpeg' && mime != 'image/png') {
    return PhotoProblem.unsupported;
  }
  return await file.length() > maintenancePhotoMaxBytes
      ? PhotoProblem.tooLarge
      : null;
}

/// Sends a maintenance photo as a `maintenance_photo` document of the institution and returns
/// the document id. The server re-reads the file and keeps it only if its SHA-256 matches.
Future<String> uploadMaintenancePhoto({
  required EHimayaApi api,
  required TusClient tus,
  required String orgId,
  required File file,
  required String title,
}) async {
  final documentId = await api.createOrgDocument(
    orgId,
    'maintenance_photo',
    title,
  );
  final digest = sha256.convert(await file.readAsBytes()).toString();
  await tus.upload(
    file: file,
    metadata: {
      'target': 'org_document',
      'document_id': documentId,
      'filetype': MediaRules.mimeFor(file.path)!,
      'sha256': digest,
      'filename': file.uri.pathSegments.last,
    },
    onProgress: (_, _) async {},
  );
  return documentId;
}
