import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/widgets/app_error_widget.dart';
import 'package:academix/core/widgets/app_loader.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/repositories/ai_evaluation_repository.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/services/assignment_file_picker.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_form_screen.dart';
import 'package:academix/features/assignments/presentation/screens/ai_evaluation_screens.dart';
import 'package:academix/features/assignments/presentation/screens/submission_screens.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class AssignmentDetailsScreen extends StatefulWidget {
  const AssignmentDetailsScreen({
    super.key,
    required this.assignment,
    required this.isTeacher,
    required this.repository,
    this.filePicker,
  });

  final Assignment assignment;
  final bool isTeacher;
  final AssignmentRepository repository;
  final AssignmentFilePicker? filePicker;

  @override
  State<AssignmentDetailsScreen> createState() =>
      _AssignmentDetailsScreenState();
}

class _AssignmentDetailsScreenState extends State<AssignmentDetailsScreen> {
  late Assignment _assignment = widget.assignment;
  Submission? _mySubmission;
  StudentAssignmentRubric? _studentRubric;
  String? _studentRubricError;
  bool _isLoading = true;
  String? _errorMessage;
  bool _isChangingState = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Please sign in again to view this assignment.';
      });
      return;
    }
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final assignment = await widget.repository.getAssignment(
        token,
        widget.assignment.id,
      );
      Submission? submission;
      StudentAssignmentRubric? studentRubric;
      String? studentRubricError;
      if (!widget.isTeacher) {
        final submissions = await widget.repository.listMySubmissions(token);
        for (final item in submissions) {
          if (item.assignmentId == assignment.id) {
            submission = item;
            break;
          }
        }
        try {
          studentRubric = await widget.repository.getStudentRubric(
            token,
            assignment.id,
          );
        } on NotFoundException {
          studentRubric = null;
        } on ApiException catch (error) {
          studentRubricError = error.message;
        } catch (_) {
          studentRubricError = 'Unable to load the student-visible rubric.';
        }
      }
      if (!mounted) return;
      setState(() {
        _assignment = assignment;
        _mySubmission = submission;
        _studentRubric = studentRubric;
        _studentRubricError = studentRubricError;
        _isLoading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = error.message;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to load assignment details.';
        _isLoading = false;
      });
    }
  }

  Future<void> _editAssignment() async {
    final updated = await Navigator.of(context).push<Assignment>(
      MaterialPageRoute<Assignment>(
        builder: (_) => AssignmentFormScreen(
          classId: _assignment.classId,
          assignment: _assignment,
          repository: widget.repository,
          filePicker: widget.filePicker,
        ),
      ),
    );
    if (!mounted) return;
    if (updated != null) await _load();
  }

  Future<void> _setPublished(bool isPublished) async {
    final token = context.read<AuthProvider>().token;
    if (token == null) return;
    setState(() => _isChangingState = true);
    try {
      await widget.repository.setPublished(token, _assignment.id, isPublished);
      if (mounted) await _load();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } catch (_) {
      if (mounted) _showMessage('Unable to update assignment status.');
    } finally {
      if (mounted) setState(() => _isChangingState = false);
    }
  }

  Future<void> _archive() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive assignment?'),
        content: const Text(
          'Students will no longer see this assignment. Submission and grading history is retained.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Archive'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    final token = context.read<AuthProvider>().token;
    if (token == null) return;
    try {
      await widget.repository.archiveAssignment(token, _assignment.id);
      if (!mounted) return;
      Navigator.pop(context);
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } catch (_) {
      if (mounted) _showMessage('Unable to archive this assignment.');
    }
  }

  Future<void> _openSubmissionForm() async {
    final result = await Navigator.of(context).push<Submission>(
      MaterialPageRoute<Submission>(
        builder: (_) => SubmissionFormScreen(
          assignment: _assignment,
          existingSubmission: _mySubmission,
          repository: widget.repository,
          filePicker: widget.filePicker,
        ),
      ),
    );
    if (!mounted) return;
    if (result != null) await _load();
  }

  Future<void> _openMySubmission() async {
    final submission = _mySubmission;
    if (submission == null) return;
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => SubmissionDetailsScreen(
          submission: submission,
          isTeacher: false,
          repository: widget.repository,
          filePicker: widget.filePicker,
        ),
      ),
    );
    if (mounted) await _load();
  }

  Future<void> _openClassSubmissions() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => TeacherSubmissionsScreen(
          assignment: _assignment,
          repository: widget.repository,
          filePicker: widget.filePicker,
        ),
      ),
    );
    if (mounted) await _load();
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Assignment details'),
        actions: [
          if (widget.isTeacher && !_isLoading)
            PopupMenuButton<String>(
              onSelected: (action) {
                if (action == 'edit') _editAssignment();
                if (action == 'archive') _archive();
              },
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'edit', child: Text('Edit')),
                PopupMenuItem(value: 'archive', child: Text('Archive')),
              ],
            ),
        ],
      ),
      body: _isLoading
          ? const AppLoader(message: 'Loading assignment...')
          : _errorMessage != null
          ? Column(
              children: [
                Expanded(child: AppErrorWidget(message: _errorMessage!)),
                Padding(
                  padding: const EdgeInsets.only(bottom: 24),
                  child: OutlinedButton(
                    onPressed: _load,
                    child: const Text('Try again'),
                  ),
                ),
              ],
            )
          : _buildDetails(),
    );
  }

  Widget _buildDetails() {
    final dueText = DateFormat.yMMMd().add_jm().format(_assignment.dueDate);
    final overdue =
        _assignment.deadlineStatus == 'overdue' && !_assignment.isArchived;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          _assignment.title,
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            Chip(
              avatar: const Icon(Icons.score_outlined, size: 18),
              label: Text('${_assignment.totalMarks} points'),
            ),
            Chip(
              avatar: const Icon(Icons.event_outlined, size: 18),
              label: Text('Due $dueText'),
            ),
            if (widget.isTeacher)
              Chip(
                label: Text(_assignment.isPublished ? 'Published' : 'Draft'),
              ),
            if (!widget.isTeacher && overdue && _mySubmission == null)
              const Chip(
                label: Text('Overdue'),
                avatar: Icon(Icons.warning_amber_rounded, size: 18),
              ),
          ],
        ),
        const SizedBox(height: 20),
        Text('Instructions', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Text(_assignment.instructions),
        if (!widget.isTeacher) ...[
          const SizedBox(height: 24),
          Text(
            'Question rubric',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          if (_studentRubricError != null)
            AppErrorWidget(message: _studentRubricError!)
          else if (_studentRubric == null)
            const Text('No student-visible rubric has been provided.')
          else
            for (final question in _studentRubric!.questions)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${question.questionId} · ${question.maxMarks} marks',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 6),
                      Text(question.prompt),
                      for (final criterion in question.criteria)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            '${criterion.description} · ${criterion.marks} marks',
                          ),
                        ),
                      if (question.partialCreditRules.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        const Text('Scoring guidance'),
                        for (final rule in question.partialCreditRules)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(rule),
                          ),
                      ],
                    ],
                  ),
                ),
              ),
        ],
        if (_assignment.attachments.isNotEmpty) ...[
          const SizedBox(height: 24),
          Text('Attachments', style: Theme.of(context).textTheme.titleMedium),
          for (final file in _assignment.attachments)
            _DownloadableFileTile(
              file: file,
              repository: widget.repository,
              filePicker: widget.filePicker,
            ),
        ],
        if (widget.isTeacher) ...[
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Class progress',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  Text('${_assignment.submittedCount} submitted'),
                  Text('${_assignment.pendingCount} pending'),
                  Text('${_assignment.gradedCount} graded'),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).push<void>(
                      MaterialPageRoute<void>(
                        builder: (_) => AssignmentRubricEditorScreen(
                          assignmentId: _assignment.id,
                          assignmentTitle: _assignment.title,
                          totalMarks: _assignment.totalMarks,
                          repository: HttpAIEvaluationRepository(),
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.rule_outlined),
                    label: const Text('Configure rubric'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _openClassSubmissions,
                    icon: const Icon(Icons.people_outline_rounded),
                    label: const Text('View student submissions'),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      _assignment.isPublished ? 'Published' : 'Draft',
                    ),
                    value: _assignment.isPublished,
                    onChanged: _isChangingState ? null : _setPublished,
                  ),
                ],
              ),
            ),
          ),
        ] else ...[
          const SizedBox(height: 20),
          if (_mySubmission != null)
            Card(
              child: ListTile(
                leading: const Icon(Icons.assignment_turned_in_outlined),
                title: Text('Your submission: ${_mySubmission!.status}'),
                subtitle: _mySubmission!.isLate
                    ? const Text('Submitted late')
                    : null,
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: _openMySubmission,
              ),
            ),
          if (_mySubmission?.status != 'graded') ...[
            if (_mySubmission != null) const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: _openSubmissionForm,
              icon: const Icon(Icons.upload_file_outlined),
              label: Text(
                _mySubmission == null
                    ? 'Submit assignment'
                    : 'Update submission',
              ),
            ),
          ],
          if (_mySubmission?.marksObtained != null) ...[
            const SizedBox(height: 12),
            Text(
              'Grade: ${_mySubmission!.marksObtained} / ${_mySubmission!.totalMarks ?? _assignment.totalMarks}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (_mySubmission!.teacherFeedback != null)
              Text(_mySubmission!.teacherFeedback!),
          ],
        ],
      ],
    );
  }
}

class _DownloadableFileTile extends StatefulWidget {
  const _DownloadableFileTile({
    required this.file,
    required this.repository,
    this.filePicker,
  });

  final AssignmentFile file;
  final AssignmentRepository repository;
  final AssignmentFilePicker? filePicker;

  @override
  State<_DownloadableFileTile> createState() => _DownloadableFileTileState();
}

class _DownloadableFileTileState extends State<_DownloadableFileTile> {
  bool _isDownloading = false;

  Future<void> _download() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) return;
    setState(() => _isDownloading = true);
    try {
      final bytes = await widget.repository.downloadFile(token, widget.file);
      await (widget.filePicker ?? DeviceAssignmentFilePicker()).saveFile(
        widget.file,
        bytes,
      );
      if (mounted) _message('File saved.');
    } on ApiException catch (error) {
      if (mounted) _message(error.message);
    } catch (error) {
      if (mounted) _message(error.toString());
    } finally {
      if (mounted) setState(() => _isDownloading = false);
    }
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: EdgeInsets.zero,
    leading: const Icon(Icons.insert_drive_file_outlined),
    title: Text(widget.file.filename),
    subtitle: Text('${(widget.file.sizeBytes / 1024).ceil()} KB'),
    trailing: IconButton(
      tooltip: 'Download ${widget.file.filename}',
      onPressed: _isDownloading ? null : _download,
      icon: _isDownloading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.download_outlined),
    ),
  );
}
