import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/widgets/app_empty_state.dart';
import 'package:academix/core/widgets/app_error_widget.dart';
import 'package:academix/core/widgets/app_loader.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/presentation/screens/ai_evaluation_screens.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/services/assignment_file_picker.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:academix/features/assignments/data/repositories/review_repository.dart';
import 'package:academix/features/assignments/presentation/screens/manual_review_screen.dart';
import 'package:academix/features/assignments/presentation/screens/attachment_viewer_screen.dart';

class SubmissionFormScreen extends StatefulWidget {
  const SubmissionFormScreen({
    super.key,
    required this.assignment,
    required this.repository,
    this.existingSubmission,
    this.filePicker,
  });

  final Assignment assignment;
  final Submission? existingSubmission;
  final AssignmentRepository repository;
  final AssignmentFilePicker? filePicker;

  @override
  State<SubmissionFormScreen> createState() => _SubmissionFormScreenState();
}

class _SubmissionFormScreenState extends State<SubmissionFormScreen> {
  late final _textController = TextEditingController(
    text: widget.existingSubmission?.submissionText ?? '',
  );
  late final AssignmentFilePicker _filePicker =
      widget.filePicker ?? DeviceAssignmentFilePicker();
  final List<AssignmentUpload> _selectedFiles = [];
  String? _errorMessage;
  bool _isSaving = false;
  bool _isPicking = false;

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  Future<void> _pickFiles() async {
    setState(() {
      _isPicking = true;
      _errorMessage = null;
    });
    try {
      final files = await _filePicker.pickFiles();
      if (mounted) setState(() => _selectedFiles.addAll(files));
    } catch (error) {
      if (mounted) setState(() => _errorMessage = error.toString());
    } finally {
      if (mounted) setState(() => _isPicking = false);
    }
  }

  Future<void> _save({required bool asDraft}) async {
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(() => _errorMessage = 'Please sign in again to continue.');
      return;
    }
    if (!asDraft &&
        _textController.text.trim().isEmpty &&
        _selectedFiles.isEmpty) {
      setState(() => _errorMessage = 'Add text or attach a file to submit.');
      return;
    }

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });
    try {
      final submission = await widget.repository.submit(
        token,
        widget.assignment.id,
        text: _textController.text.trim(),
        isDraft: asDraft,
        files: List<AssignmentUpload>.unmodifiable(_selectedFiles),
      );
      if (!mounted) return;
      setState(() => _isSaving = false);
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(asDraft ? 'Draft saved' : 'Submission received'),
          content: Text(
            submission.isLate
                ? 'Your work was submitted after the due date and is marked late.'
                : 'Your assignment has been saved successfully.',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Done'),
            ),
          ],
        ),
      );
      if (mounted) Navigator.pop(context, submission);
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _errorMessage = 'Unable to save your submission.');
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final dueText = DateFormat.yMMMd().add_jm().format(
      widget.assignment.dueDate,
    );
    return Scaffold(
      appBar: AppBar(title: Text(widget.assignment.title)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text('Due $dueText · ${widget.assignment.totalMarks} points'),
          if (widget.assignment.deadlineStatus == 'overdue') ...[
            const SizedBox(height: 8),
            const Chip(
              avatar: Icon(Icons.warning_amber_rounded, size: 18),
              label: Text('Late submissions are accepted and marked late'),
            ),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: _textController,
            minLines: 5,
            maxLines: 12,
            maxLength: 50000,
            decoration: const InputDecoration(
              labelText: 'Your response',
              hintText: 'Write your answer or add files below.',
              alignLabelWithHint: true,
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _isPicking ? null : _pickFiles,
            icon: const Icon(Icons.attach_file_rounded),
            label: Text(_isPicking ? 'Selecting files...' : 'Attach files'),
          ),
          if (widget.existingSubmission != null)
            for (final file in widget.existingSubmission!.attachments)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.insert_drive_file_outlined),
                title: Text(file.filename),
                subtitle: const Text('Previously uploaded'),
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
            const SizedBox(height: 8),
            Text(
              _errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 20),
          OutlinedButton(
            onPressed: _isSaving ? null : () => _save(asDraft: true),
            child: const Text('Save draft'),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: _isSaving ? null : () => _save(asDraft: false),
            icon: _isSaving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send_rounded),
            label: Text(_isSaving ? 'Saving...' : 'Submit assignment'),
          ),
        ],
      ),
    );
  }
}

class MySubmissionsScreen extends StatefulWidget {
  const MySubmissionsScreen({super.key, required this.repository});

  final AssignmentRepository repository;

  @override
  State<MySubmissionsScreen> createState() => _MySubmissionsScreenState();
}

class _MySubmissionsScreenState extends State<MySubmissionsScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  List<Submission> _submissions = [];

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
        _errorMessage = 'Please sign in again to view submissions.';
      });
      return;
    }
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final submissions = await widget.repository.listMySubmissions(token);
      if (!mounted) return;
      setState(() {
        _submissions = submissions;
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
        _errorMessage = 'Unable to load your submissions.';
        _isLoading = false;
      });
    }
  }

  Future<void> _open(Submission submission) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => SubmissionDetailsScreen(
          submission: submission,
          isTeacher: false,
          repository: widget.repository,
        ),
      ),
    );
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My submissions')),
      body: _isLoading
          ? const AppLoader(message: 'Loading submissions...')
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
          : RefreshIndicator(
              onRefresh: _load,
              child: _submissions.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: const [
                        SizedBox(height: 160),
                        AppEmptyState(
                          title: 'No submissions yet',
                          message: 'Your submitted work and grades will appear here.',
                        ),
                      ],
                    )
                  : ListView.separated(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(16),
                      itemCount: _submissions.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final submission = _submissions[index];
                        return Card(
                          child: ListTile(
                            leading: const Icon(
                              Icons.assignment_turned_in_outlined,
                            ),
                            title: Text(
                              submission.assignmentTitle ??
                                  'Assignment submission',
                            ),
                            subtitle: Text(
                              '${_statusLabel(submission.status)}'
                              '${submission.isLate ? ' · Late' : ''}',
                            ),
                            trailing: const Icon(Icons.chevron_right_rounded),
                            onTap: () => _open(submission),
                          ),
                        );
                      },
                    ),
            ),
    );
  }
}

class TeacherSubmissionsScreen extends StatefulWidget {
  const TeacherSubmissionsScreen({
    super.key,
    required this.assignment,
    required this.repository,
    this.filePicker,
    this.reviews,
  });

  final Assignment assignment;
  final AssignmentRepository repository;
  final AssignmentFilePicker? filePicker;
  final ReviewRepository? reviews;

  @override
  State<TeacherSubmissionsScreen> createState() =>
      _TeacherSubmissionsScreenState();
}

class _TeacherSubmissionsScreenState extends State<TeacherSubmissionsScreen> {
  late final _reviews = widget.reviews ?? ReviewRepository();
  Map<String, dynamic>? _data;
  String _filter = 'all';
  String? _error;
  int _offset = 0;
  bool _loading = true;
  String get _token => context.read<AuthProvider>().token ?? '';
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _reviews.get(
        _token,
        '/assignments/${widget.assignment.id}/review-roster',
        query: {'state': _filter, 'offset': _offset, 'limit': 25},
      );
      if (mounted) {
        setState(() {
          _data = result;
          _loading = false;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Unable to load roster: $error';
        });
      }
    }
  }

  Future<void> _open(String id) async {
    try {
      final work = Submission.fromJson(
        await _reviews.get(_token, '/submissions/$id'),
      );
      if (!mounted) return;
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => SubmissionDetailsScreen(
            submission: work,
            isTeacher: true,
            repository: widget.repository,
            filePicker: widget.filePicker,
          ),
        ),
      );
      if (mounted) await _load();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Unable to open work: $error')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = (_data?['items'] as List? ?? []).cast<Map<String, dynamic>>();
    return Scaffold(
      appBar: AppBar(title: const Text('Student submissions')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: DropdownButtonFormField<String>(
              initialValue: _filter,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Review status'),
              items:
                  const {
                        'all': 'All students',
                        'submitted': 'Submitted',
                        'not_submitted': 'Not submitted',
                        'late': 'Late',
                        'under_review': 'Under review',
                        'draft': 'Draft (student or teacher)',
                        'reviewed': 'Reviewed',
                        'returned': 'Returned for revision',
                        'graded': 'Graded',
                        'released': 'Released',
                      }.entries
                      .map(
                        (e) => DropdownMenuItem(
                          value: e.key,
                          child: Text(e.value),
                        ),
                      )
                      .toList(),
              onChanged: (v) {
                if (v != null) {
                  setState(() {
                    _filter = v;
                    _offset = 0;
                  });
                  _load();
                }
              },
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_error!),
                        TextButton(
                          onPressed: _load,
                          child: const Text('Try again'),
                        ),
                      ],
                    ),
                  )
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      padding: const EdgeInsets.all(16),
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        if (rows.isEmpty)
                          const AppEmptyState(
                            title: 'No matching students',
                            message: 'Choose another status or refresh after new submissions.',
                          ),
                        for (final row in rows)
                          Card(
                            child: ListTile(
                              leading: Icon(
                                row['submission_id'] == null
                                    ? Icons.person_outline
                                    : Icons.assignment_outlined,
                              ),
                              title: Text(row['student_id'] as String),
                              subtitle: Text(
                                '${row['status']} | ${row['review_state'] ?? (row['status'] == 'graded' ? 'Grade published' : 'Review not started')}${row['is_late'] == true ? " | Late" : ""}',
                              ),
                              trailing: row['submission_id'] == null
                                  ? null
                                  : const Icon(Icons.chevron_right),
                              onTap: row['submission_id'] == null
                                  ? null
                                  : () => _open(row['submission_id'] as String),
                            ),
                          ),
                      ],
                    ),
                  ),
          ),
          if (_data != null)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextButton(
                  onPressed: _loading || _offset == 0
                      ? null
                      : () {
                          _offset -= 25;
                          _load();
                        },
                  child: const Text('Previous'),
                ),
                Text('${_data!['total']} students'),
                TextButton(
                  onPressed:
                      _loading || _offset + rows.length >= _data!['total']
                      ? null
                      : () {
                          _offset += 25;
                          _load();
                        },
                  child: const Text('Next'),
                ),
              ],
            ),
        ],
      ),
    );
  }
}

class SubmissionDetailsScreen extends StatefulWidget {
  const SubmissionDetailsScreen({
    super.key,
    required this.submission,
    required this.isTeacher,
    required this.repository,
    this.filePicker,
  });

  final Submission submission;
  final bool isTeacher;
  final AssignmentRepository repository;
  final AssignmentFilePicker? filePicker;

  @override
  State<SubmissionDetailsScreen> createState() =>
      _SubmissionDetailsScreenState();
}

class _SubmissionDetailsScreenState extends State<SubmissionDetailsScreen> {
  late Submission _submission = widget.submission;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    if (!widget.isTeacher) {
      _isLoading = true;
      _load();
    }
  }

  Future<void> _load() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Please sign in again to view your submission.';
      });
      return;
    }
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final submission = await widget.repository.getMySubmission(
        token,
        widget.submission.id,
      );
      if (!mounted) return;
      setState(() {
        _submission = submission;
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
        _errorMessage = 'Unable to load submission details.';
        _isLoading = false;
      });
    }
  }

  Future<void> _grade() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => ManualReviewScreen(
          submission: _submission,
          assignments: widget.repository,
        ),
      ),
    );
    if (mounted) await _loadTeacherSubmission();
  }

  Future<void> _openAIEvaluation() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => TeacherAIEvaluationScreen(
          assignmentId: _submission.assignmentId,
          assignmentTitle: _submission.assignmentTitle ?? 'Assignment',
          submissionId: _submission.id,
          totalMarks: _submission.totalMarks ?? 0,
          submission: _submission,
          assignmentRepository: widget.repository,
        ),
      ),
    );
    if (mounted) await _loadTeacherSubmission();
  }

  Future<void> _loadTeacherSubmission() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) return;
    try {
      final submissions = await widget.repository.listSubmissions(
        token,
        _submission.assignmentId,
      );
      final updated = submissions.where((item) => item.id == _submission.id);
      if (mounted && updated.isNotEmpty) {
        setState(() => _submission = updated.first);
      }
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to refresh the grade.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Submission review'),
        actions: [
          if (widget.isTeacher && _submission.status != 'draft')
            IconButton(
              tooltip: 'AI evaluation',
              onPressed: _openAIEvaluation,
              icon: const Icon(Icons.auto_awesome_outlined),
            ),
          if (widget.isTeacher && _submission.status != 'draft')
            IconButton(
              tooltip: 'Manual review and release',
              onPressed: _grade,
              icon: const Icon(Icons.rate_review_outlined),
            ),
        ],
      ),
      body: _isLoading
          ? const AppLoader(message: 'Loading submission...')
          : _errorMessage != null
          ? AppErrorWidget(message: _errorMessage!)
          : _buildDetails(),
    );
  }

  Widget _buildDetails() {
    final submittedText = _submission.submittedAt == null
        ? 'Draft'
        : DateFormat.yMMMd().add_jm().format(_submission.submittedAt!);
    final totalMarks = _submission.totalMarks;
    final percentage =
        _submission.marksObtained != null &&
            totalMarks != null &&
            totalMarks > 0
        ? _submission.marksObtained! / totalMarks * 100
        : null;
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          _submission.assignmentTitle ?? 'Submission',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            Chip(label: Text(_statusLabel(_submission.status))),
            if (_submission.isLate)
              const Chip(
                avatar: Icon(Icons.warning_amber_rounded, size: 18),
                label: Text('Late'),
              ),
          ],
        ),
        Text('Submitted $submittedText'),
        if (widget.isTeacher) ...[
          const SizedBox(height: 8),
          Text('Student: ${_submission.studentName ?? _submission.studentId}'),
        ],
        if (_submission.submissionText != null) ...[
          const SizedBox(height: 20),
          Text('Response', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(_submission.submissionText!),
        ],
        if (_submission.attachments.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(
            'Attached files',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          for (final file in _submission.attachments)
            _SubmissionDownloadTile(
              file: file,
              repository: widget.repository,
              filePicker: widget.filePicker,
            ),
        ],
        if (_submission.marksObtained != null) ...[
          const SizedBox(height: 20),
          Text(
            'Grade: ${_submission.marksObtained} / ${_submission.totalMarks ?? 0}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (percentage != null) ...[
            Text(
              'Published percentage: ${percentage.toStringAsFixed(1)}% · '
              'illustrative grade band ${_illustrativeGradeBand(percentage)} '
              '(not institution policy)',
            ),
          ],
          ReleasedQuestionMarks(submissionId: _submission.id),
        ],
        if (_submission.teacherFeedback != null &&
            _submission.teacherFeedback!.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            'Teacher feedback',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(_submission.teacherFeedback!),
        ],
        if (_submission.revisions.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(
            'Previous attempts',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          for (final revision in _submission.revisions)
            ExpansionTile(
              leading: CircleAvatar(child: Text('${revision.revisionNumber}')),
              title: Text(_statusLabel(revision.status)),
              subtitle: Text(
                revision.submittedAt == null
                    ? 'Draft saved'
                    : DateFormat.yMMMd().add_jm().format(revision.submittedAt!),
              ),
              children: [
                if (revision.submissionText != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: SelectableText(revision.submissionText!),
                  ),
                if (revision.marksObtained != null)
                  Text('Previous released grade: ${revision.marksObtained}'),
                if (revision.teacherFeedback != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(revision.teacherFeedback!),
                  ),
                for (final file in revision.attachments)
                  _SubmissionDownloadTile(
                    file: file,
                    repository: widget.repository,
                    filePicker: widget.filePicker,
                  ),
              ],
            ),
        ],
      ],
    );
  }
}

class GradeSubmissionScreen extends StatefulWidget {
  const GradeSubmissionScreen({
    super.key,
    required this.submission,
    required this.totalMarks,
    required this.repository,
  });

  final Submission submission;
  final double totalMarks;
  final AssignmentRepository repository;

  @override
  State<GradeSubmissionScreen> createState() => _GradeSubmissionScreenState();
}

class _GradeSubmissionScreenState extends State<GradeSubmissionScreen> {
  late final _marksController = TextEditingController(
    text: widget.submission.marksObtained?.toString() ?? '',
  );
  late final _feedbackController = TextEditingController(
    text: widget.submission.teacherFeedback ?? '',
  );
  String? _errorMessage;
  bool _isSaving = false;

  @override
  void dispose() {
    _marksController.dispose();
    _feedbackController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final marksText = _marksController.text.trim();
    final marks = marksText.isEmpty ? null : double.tryParse(marksText);
    final feedback = _feedbackController.text.trim();
    if (marksText.isNotEmpty &&
        (marks == null || marks < 0 || marks > widget.totalMarks)) {
      setState(
        () =>
            _errorMessage = 'Marks must be between 0 and ${widget.totalMarks}.',
      );
      return;
    }
    if (marks == null && feedback.isEmpty) {
      setState(
        () => _errorMessage =
            'Enter marks or feedback before returning the work.',
      );
      return;
    }
    final token = context.read<AuthProvider>().token;
    if (token == null) return;

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });
    try {
      final submission = await widget.repository.gradeSubmission(
        token,
        widget.submission.id,
        marks: marks,
        feedback: feedback,
      );
      if (mounted) Navigator.pop(context, submission);
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } catch (_) {
      if (mounted) setState(() => _errorMessage = 'Unable to save the grade.');
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Grade submission')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            '${widget.submission.studentId} · ${widget.submission.assignmentTitle ?? 'Assignment'}',
          ),
          const SizedBox(height: 20),
          TextFormField(
            controller: _marksController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: 'Marks',
              helperText: 'Optional; maximum ${widget.totalMarks}',
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _feedbackController,
            minLines: 4,
            maxLines: 8,
            maxLength: 20000,
            decoration: const InputDecoration(
              labelText: 'Teacher feedback',
              alignLabelWithHint: true,
              border: OutlineInputBorder(),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 8),
            Text(
              _errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _isSaving ? null : _save,
            child: Text(_isSaving ? 'Saving...' : 'Save grade and feedback'),
          ),
        ],
      ),
    );
  }
}

class _SubmissionDownloadTile extends StatefulWidget {
  const _SubmissionDownloadTile({
    required this.file,
    required this.repository,
    this.filePicker,
  });

  final AssignmentFile file;
  final AssignmentRepository repository;
  final AssignmentFilePicker? filePicker;

  @override
  State<_SubmissionDownloadTile> createState() =>
      _SubmissionDownloadTileState();
}

class _SubmissionDownloadTileState extends State<_SubmissionDownloadTile> {
  bool _loading = false;

  Future<void> _download() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) return;
    setState(() => _loading = true);
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
      if (mounted) setState(() => _loading = false);
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
    subtitle: const Text('Open read-only preview'),
    onTap: () => Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => AttachmentViewerScreen(
          file: widget.file,
          repository: widget.repository,
          filePicker: widget.filePicker,
        ),
      ),
    ),
    trailing: IconButton(
      tooltip: 'Download ${widget.file.filename}',
      onPressed: _loading ? null : _download,
      icon: _loading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.download_outlined),
    ),
  );
}

String _statusLabel(String status) => switch (status) {
  'draft' => 'Draft',
  'submitted' => 'Submitted',
  'returned' => 'Returned',
  'graded' => 'Graded',
  _ => status,
};

String _illustrativeGradeBand(double percentage) => switch (percentage) {
  >= 90 => 'A',
  >= 80 => 'B',
  >= 70 => 'C',
  >= 60 => 'D',
  _ => 'F',
};
