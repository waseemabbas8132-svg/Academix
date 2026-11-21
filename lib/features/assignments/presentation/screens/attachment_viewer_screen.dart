import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/repositories/review_repository.dart';
import 'package:academix/features/assignments/data/services/assignment_file_picker.dart';

class AttachmentViewerScreen extends StatefulWidget {
  const AttachmentViewerScreen({
    super.key,
    required this.file,
    required this.repository,
    this.previews,
    this.filePicker,
  });
  final AssignmentFile file;
  final AssignmentRepository repository;
  final ReviewRepository? previews;
  final AssignmentFilePicker? filePicker;
  @override
  State<AttachmentViewerScreen> createState() => _AttachmentViewerState();
}

class _AttachmentViewerState extends State<AttachmentViewerScreen> {
  late final _api = widget.previews ?? ReviewRepository();
  final _transform = TransformationController();
  Uint8List? _bytes;
  int _page = 1, _count = 0;
  bool _loading = true, _downloading = false;
  String? _error;
  bool _downloadOnly = false;
  String get _token => context.read<AuthProvider>().token ?? '';
  @override
  void initState() {
    super.initState();
    _load(info: true);
  }

  @override
  void dispose() {
    _transform.dispose();
    super.dispose();
  }

  Future<void> _load({bool info = false}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      if (info) {
        final result = await _api.get(
          _token,
          '/files/${widget.file.id}/preview',
        );
        _count = result['page_count'] as int;
        _downloadOnly = result['kind'] == 'download_only';
      }
      final bytes = _downloadOnly
          ? null
          : await _api.page(_token, widget.file.id, _page);
      if (mounted) {
        _transform.value = Matrix4.identity();
        setState(() {
          _bytes = bytes;
          _loading = false;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Preview unavailable: $error';
        });
      }
    }
  }

  Future<void> _download() async {
    setState(() => _downloading = true);
    try {
      final bytes = await widget.repository.downloadFile(_token, widget.file);
      await (widget.filePicker ?? DeviceAssignmentFilePicker()).saveFile(
        widget.file,
        bytes,
      );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Original file saved.')));
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Download failed: $error')));
      }
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.file.filename),
      actions: [
        IconButton(
          tooltip: 'Fit to screen',
          onPressed: () => _transform.value = Matrix4.identity(),
          icon: const Icon(Icons.fit_screen),
        ),
        IconButton(
          tooltip: 'Download original',
          onPressed: _downloading ? null : _download,
          icon: const Icon(Icons.download_outlined),
        ),
      ],
    ),
    body: Column(
      children: [
        if (_count > 1)
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                tooltip: 'Previous page',
                onPressed: _loading || _page == 1
                    ? null
                    : () {
                        _page--;
                        _load();
                      },
                icon: const Icon(Icons.chevron_left),
              ),
              Text('Page $_page of $_count'),
              IconButton(
                tooltip: 'Next page',
                onPressed: _loading || _page == _count
                    ? null
                    : () {
                        _page++;
                        _load();
                      },
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null || _downloadOnly
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          _error ?? 'This document supports secure original download. In-app preview is unavailable.',
                        ),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          onPressed: _downloading ? null : _download,
                          icon: const Icon(Icons.download),
                          label: const Text('Download original'),
                        ),
                        if (_error != null)
                          TextButton(
                            onPressed: () => _load(info: true),
                            child: const Text('Retry preview'),
                          ),
                      ],
                    ),
                  ),
                )
              : LayoutBuilder(
                  builder: (context, size) => InteractiveViewer(
                    transformationController: _transform,
                    minScale: 0.5,
                    maxScale: 8,
                    child: SizedBox(
                      width: size.maxWidth,
                      height: size.maxHeight,
                      child: Image.memory(
                        _bytes!,
                        fit: BoxFit.contain,
                        errorBuilder: (_, error, stack) => const Center(
                          child: Text(
                            'Image cannot be displayed. Download the original.',
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
        ),
        const Padding(
          padding: EdgeInsets.all(8),
          child: Text(
            'Read-only preview • Pinch or scroll to zoom • Original file preserved',
          ),
        ),
      ],
    ),
  );
}
