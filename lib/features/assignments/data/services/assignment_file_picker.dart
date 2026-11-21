import 'package:flutter/foundation.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:file_picker/file_picker.dart';

abstract interface class AssignmentFilePicker {
  Future<List<AssignmentUpload>> pickFiles();

  Future<void> saveFile(AssignmentFile file, Uint8List bytes);
}

class DeviceAssignmentFilePicker implements AssignmentFilePicker {
  static const _allowedExtensions = [
    'pdf',
    'jpg',
    'jpeg',
    'png',
    'doc',
    'docx',
  ];

  @override
  Future<List<AssignmentUpload>> pickFiles() async {
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: _allowedExtensions,
      allowMultiple: true,
      withData: true,
    );
    if (result == null) return [];

    final selected = <AssignmentUpload>[];
    for (final file in result.files) {
      final bytes = file.bytes;
      if (bytes == null) {
        throw StateError('Unable to read ${file.name}. Please choose it again.');
      }
      selected.add(AssignmentUpload(name: file.name, bytes: bytes));
    }
    return selected;
  }

  @override
  Future<void> saveFile(AssignmentFile file, Uint8List bytes) async {
    final savedPath = await FilePicker.saveFile(
      fileName: file.filename,
      bytes: bytes,
    );
    if (savedPath == null && !kIsWeb) {
      throw StateError('File save was cancelled.');
    }
  }
}
