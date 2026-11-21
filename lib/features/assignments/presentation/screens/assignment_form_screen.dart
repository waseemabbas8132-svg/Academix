import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/widgets/app_button.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/services/assignment_file_picker.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class AssignmentFormScreen extends StatefulWidget {
  const AssignmentFormScreen({
    super.key,
    required this.classId,
    this.assignment,
    this.repository,
    this.filePicker,
  });

  final String classId;
  final Assignment? assignment;
  final AssignmentRepository? repository;
  final AssignmentFilePicker? filePicker;

  @override
  State<AssignmentFormScreen> createState() => _AssignmentFormScreenState();
}

class _AssignmentFormScreenState extends State<AssignmentFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final _titleController = TextEditingController(
    text: widget.assignment?.title ?? '',
  );
  late final _instructionsController = TextEditingController(
    text: widget.assignment?.instructions ?? '',
  );
  late final _marksController = TextEditingController(
    text: widget.assignment?.totalMarks.toString() ?? '',
  );
  late DateTime _dueDate =
      widget.assignment?.dueDate ?? DateTime.now().add(const Duration(days: 7));
  late final AssignmentRepository _repository =
      widget.repository ?? HttpAssignmentRepository();
  late final AssignmentFilePicker _filePicker =
      widget.filePicker ?? DeviceAssignmentFilePicker();
  final List<AssignmentUpload> _selectedFiles = [];
  Assignment? _savedAssignment;
  String? _errorMessage;
  bool _isSaving = false;
  bool _isPicking = false;

  Assignment? get _existing => _savedAssignment ?? widget.assignment;

  @override
  void dispose() {
    _titleController.dispose();
    _instructionsController.dispose();
    _marksController.dispose();
    super.dispose();
  }

  Future<void> _selectDueDate() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _dueDate,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (date == null || !mounted) return;

    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_dueDate),
    );
    if (time == null || !mounted) return;
    setState(() {
      _dueDate = DateTime(
        date.year,
        date.month,
        date.day,
        time.hour,
        time.minute,
      );
    });
  }

  Future<void> _pickFiles() async {
    setState(() {
      _isPicking = true;
      _errorMessage = null;
    });
    try {
      final files = await _filePicker.pickFiles();
      if (!mounted) return;
      setState(() => _selectedFiles.addAll(files));
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } catch (error) {
      if (mounted) setState(() => _errorMessage = error.toString());
    } finally {
      if (mounted) setState(() => _isPicking = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(() => _errorMessage = 'Please sign in again to continue.');
      return;
    }

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });
    try {
      final values = {
        'title': _titleController.text.trim(),
        'instructions': _instructionsController.text.trim(),
        'total_marks': _marksController.text.trim(),
        'due_date': _dueDate.toUtc().toIso8601String(),
      };
      final existing = _existing;
      final saved = existing == null
          ? await _repository.createAssignment(token, widget.classId, values)
          : await _repository.updateAssignment(token, existing.id, values);
      _savedAssignment = saved;

      if (_selectedFiles.isNotEmpty) {
        await _repository.uploadAssignmentFiles(
          token,
          saved.id,
          List<AssignmentUpload>.unmodifiable(_selectedFiles),
        );
        _selectedFiles.clear();
      }

      final refreshed = await _repository.getAssignment(token, saved.id);
      if (!mounted) return;
      Navigator.of(context).pop(refreshed);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = _existing == null
              ? error.message
              : 'Assignment saved, but an additional update failed: ${error.message}';
        });
      }
    } catch (_) {
      if (mounted) setState(() => _errorMessage = 'Unable to save the assignment.');
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEditing = _existing != null;
    return Scaffold(
      appBar: AppBar(
        title: Text(isEditing ? 'Edit assignment' : 'Create assignment'),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            TextFormField(
              controller: _titleController,
              maxLength: 200,
              decoration: const InputDecoration(labelText: 'Title'),
              validator: (value) => value == null || value.trim().isEmpty
                  ? 'Enter a title.'
                  : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _instructionsController,
              minLines: 4,
              maxLines: 8,
              maxLength: 20000,
              decoration: const InputDecoration(labelText: 'Instructions'),
              validator: (value) => value == null || value.trim().isEmpty
                  ? 'Enter instructions.'
                  : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _marksController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Total marks',
                suffixText: 'pts',
              ),
              validator: (value) {
                final marks = double.tryParse(value ?? '');
                return marks == null || marks <= 0
                    ? 'Enter a mark greater than zero.'
                    : null;
              },
            ),
            const SizedBox(height: 20),
            OutlinedButton.icon(
              onPressed: _selectDueDate,
              icon: const Icon(Icons.event_outlined),
              label: Text(
                'Due ${DateFormat.yMMMd().add_jm().format(_dueDate)}',
              ),
            ),
            const SizedBox(height: 20),
            OutlinedButton.icon(
              onPressed: _isPicking ? null : _pickFiles,
              icon: const Icon(Icons.attach_file_rounded),
              label: Text(_isPicking ? 'Selecting files...' : 'Add attachments'),
            ),
            for (var index = 0; index < _selectedFiles.length; index++)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.insert_drive_file_outlined),
                title: Text(_selectedFiles[index].name),
                trailing: IconButton(
                  tooltip: 'Remove ${_selectedFiles[index].name}',
                  onPressed: () => setState(() => _selectedFiles.removeAt(index)),
                  icon: const Icon(Icons.close),
                ),
              ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Text(
                _errorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 24),
            AppButton(
              label: isEditing ? 'Save changes' : 'Create assignment',
              isLoading: _isSaving,
              onPressed: _isSaving ? null : _save,
            ),
          ],
        ),
      ),
    );
  }
}
