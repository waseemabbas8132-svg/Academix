import 'dart:async';

import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/widgets/app_empty_state.dart';
import 'package:academix/core/widgets/app_error_widget.dart';
import 'package:academix/core/widgets/app_loader.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/models/ai_evaluation.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/repositories/ai_evaluation_repository.dart';
import 'package:academix/features/assignments/data/repositories/demo_ai_evaluation_repository.dart';
import 'package:academix/features/assignments/presentation/screens/attachment_viewer_screen.dart';
import 'package:academix/features/assignments/presentation/screens/demo_submission_preview_screen.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class TeacherAIEvaluationScreen extends StatefulWidget {
  const TeacherAIEvaluationScreen({
    super.key,
    required this.assignmentId,
    required this.assignmentTitle,
    required this.submissionId,
    required this.totalMarks,
    this.submission,
    this.assignmentRepository,
    this.repository,
    this.isDemoFixture = false,
  });

  final String assignmentId;
  final String assignmentTitle;
  final String submissionId;
  final double totalMarks;
  final Submission? submission;
  final AssignmentRepository? assignmentRepository;
  final AIEvaluationRepository? repository;
  final bool isDemoFixture;

  @override
  State<TeacherAIEvaluationScreen> createState() =>
      _TeacherAIEvaluationScreenState();
}

class _TeacherAIEvaluationScreenState extends State<TeacherAIEvaluationScreen> {
  late final AIEvaluationRepository _repository =
      widget.repository ?? HttpAIEvaluationRepository();
  late final AssignmentRepository _assignmentRepository =
      widget.assignmentRepository ?? HttpAssignmentRepository();
  final _feedbackController = TextEditingController();
  final Map<String, TextEditingController> _markControllers = {};
  final Map<String, TextEditingController> _questionFeedbackControllers = {};
  final Map<String, String> _originalQuestionFeedback = {};
  String? _controllerEvaluationId;
  EvaluationJob? _job;
  AssignmentRubric? _rubric;
  Timer? _pollTimer;
  String? _errorMessage;
  String? _rubricError;
  String? _publicationError;
  bool _isLoading = true;
  bool _isWorking = false;
  bool _isGradePublished = false;
  bool get _hasSampleEvaluation =>
      _job?.evaluation?.feedbackItems.any(
        (item) => item.kind == 'demonstration_sample',
      ) ??
      false;

  @override
  void initState() {
    super.initState();
    _refresh();
    _loadRubric();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _feedbackController.dispose();
    for (final controller in _markControllers.values) {
      controller.dispose();
    }
    for (final controller in _questionFeedbackControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  String? get _token =>
      widget.isDemoFixture ? '' : context.read<AuthProvider>().token;

  Future<void> _loadRubric() async {
    final token = _token;
    if (token == null) return;
    try {
      final rubric = await _repository.getRubric(token, widget.assignmentId);
      if (!mounted) return;
      setState(() {
        _rubric = rubric;
        _rubricError = null;
      });
    } on NotFoundException {
      if (mounted) setState(() => _rubric = null);
    } on ApiException catch (error) {
      if (mounted) setState(() => _rubricError = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _rubricError = 'Unable to load assignment rubric.');
      }
    }
  }

  Future<void> _refresh({bool silent = false}) async {
    final token = _token;
    if (token == null) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Please sign in again to review this evaluation.';
        });
      }
      return;
    }
    if (!silent) {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });
    }
    try {
      final job = await _repository.getLatest(token, widget.submissionId);
      if (!mounted) return;
      var isGradePublished = false;
      String? publicationError;
      final evaluation = job?.evaluation;
      if (evaluation?.reviewStatus == 'approved' &&
          evaluation?.approvedMarks != null &&
          evaluation?.teacherFeedback != null) {
        try {
          isGradePublished = await _repository.isGradePublished(
            token,
            widget.submissionId,
            approvedMarks: evaluation!.approvedMarks!,
            teacherFeedback: evaluation.teacherFeedback!,
          );
        } on ApiException catch (error) {
          publicationError = error.message;
        } catch (_) {
          publicationError = 'Unable to verify grade publication status.';
        }
      }
      if (!mounted) return;
      setState(() {
        _job = job;
        _isGradePublished = isGradePublished;
        _publicationError = publicationError;
        _isLoading = false;
        _errorMessage = null;
      });
      _syncReviewControllers(job?.evaluation);
      _updatePolling(job);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = error.message;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Unable to load evaluation status.';
        _isLoading = false;
      });
    }
  }

  void _updatePolling(EvaluationJob? job) {
    if (job?.status == 'pending' || job?.status == 'processing') {
      _pollTimer ??= Timer.periodic(
        const Duration(seconds: 3),
        (_) => _refresh(silent: true),
      );
    } else {
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  String? _savedQuestionFeedback(AIEvaluation evaluation, String questionId) {
    for (final item in evaluation.feedbackItems.reversed) {
      if (item.kind == 'teacher_question_feedback' &&
          item.details['question_id'] == questionId) {
        return item.message;
      }
    }
    return null;
  }

  void _syncReviewControllers(AIEvaluation? evaluation) {
    if (evaluation == null) return;
    if (_controllerEvaluationId == evaluation.id) return;
    _controllerEvaluationId = evaluation.id;
    _feedbackController.text = evaluation.teacherFeedback ?? '';
    for (final controller in _markControllers.values) {
      controller.dispose();
    }
    _markControllers
      ..clear()
      ..addEntries(
        evaluation.questions.map(
          (question) => MapEntry(
            question.questionId,
            TextEditingController(
              text:
                  question.teacherMarks?.toString() ??
                  question.suggestedMarks?.toString() ??
                  '',
            ),
          ),
        ),
      );
    for (final controller in _questionFeedbackControllers.values) {
      controller.dispose();
    }
    _questionFeedbackControllers
      ..clear()
      ..addEntries(
        evaluation.questions.map(
          (question) => MapEntry(
            question.questionId,
            TextEditingController(
              text:
                  _savedQuestionFeedback(evaluation, question.questionId) ?? '',
            ),
          ),
        ),
      );
    _originalQuestionFeedback
      ..clear()
      ..addEntries(
        evaluation.questions.map(
          (question) => MapEntry(
            question.questionId,
            _savedQuestionFeedback(evaluation, question.questionId) ?? '',
          ),
        ),
      );
  }

  Future<void> _saveReview(AIEvaluation evaluation) async {
    final token = _token;
    if (token == null) return;
    final questionMarks = <String, double?>{};
    for (final question in evaluation.questions) {
      final text = _markControllers[question.questionId]?.text.trim() ?? '';
      if (text.isEmpty) {
        questionMarks[question.questionId] = null;
        continue;
      }
      final mark = double.tryParse(text);
      if (mark == null ||
          !mark.isFinite ||
          mark < 0 ||
          mark > question.maximumMarks ||
          (mark * 100 - (mark * 100).round()).abs() > 0.000001) {
        _showMessage(
          'Enter a finite mark from 0 to ${question.maximumMarks} with at most two decimals for ${question.questionId}.',
        );
        return;
      }
      questionMarks[question.questionId] = mark;
    }
    final questionFeedback = <String, String>{};
    for (final question in evaluation.questions) {
      final text =
          _questionFeedbackControllers[question.questionId]?.text.trim() ?? '';
      if (text != _originalQuestionFeedback[question.questionId]) {
        questionFeedback[question.questionId] = text;
      }
    }
    setState(() => _isWorking = true);
    try {
      await _repository.saveReview(
        token,
        evaluation.id,
        feedback: _feedbackController.text.trim(),
        questionMarks: questionMarks,
        questionFeedback: questionFeedback,
      );
      if (!mounted) return;
      _originalQuestionFeedback.addAll(questionFeedback);
      _showMessage('Teacher review changes saved privately.');
      setState(() => _isWorking = false);
      await _refresh();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.message;
          _isWorking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to save teacher review changes.';
          _isWorking = false;
        });
      }
    }
  }

  Future<void> _configureRubric() async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => AssignmentRubricEditorScreen(
          assignmentId: widget.assignmentId,
          assignmentTitle: widget.assignmentTitle,
          totalMarks: widget.totalMarks,
          repository: _repository,
        ),
      ),
    );
    if (saved == true && mounted) {
      _showMessage('Answer key and rubric saved.');
    }
  }

  Future<void> _request({bool force = false}) async {
    final token = _token;
    if (token == null) return;
    setState(() {
      _isWorking = true;
      _errorMessage = null;
    });
    try {
      final job = await _repository.request(
        token,
        widget.submissionId,
        force: force,
      );
      if (!mounted) return;
      setState(() {
        _job = job;
        _isWorking = false;
      });
      _syncReviewControllers(job.evaluation);
      _updatePolling(job);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.message;
          _isWorking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to start AI evaluation.';
          _isWorking = false;
        });
      }
    }
  }

  Future<void> _retry() async {
    final token = _token;
    final job = _job;
    if (token == null || job == null) return;
    setState(() => _isWorking = true);
    try {
      final updated = await _repository.retry(token, job.id);
      if (!mounted) return;
      setState(() {
        _job = updated;
        _isWorking = false;
        _errorMessage = null;
      });
      _syncReviewControllers(updated.evaluation);
      _updatePolling(updated);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.message;
          _isWorking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to retry AI evaluation.';
          _isWorking = false;
        });
      }
    }
  }

  Future<void> _approve(AIEvaluation evaluation) async {
    final token = _token;
    if (token == null) return;
    final questionMarks = <String, double>{};
    for (final question in evaluation.questions) {
      final mark = double.tryParse(
        _markControllers[question.questionId]?.text.trim() ?? '',
      );
      if (mark == null ||
          !mark.isFinite ||
          mark < 0 ||
          mark > question.maximumMarks ||
          (mark * 100 - (mark * 100).round()).abs() > 0.000001) {
        _showMessage(
          'Enter a finite mark from 0 to ${question.maximumMarks} with at most two decimals for ${question.questionId}.',
        );
        return;
      }
      questionMarks[question.questionId] = mark;
    }
    if (questionMarks.length != evaluation.questions.length ||
        evaluation.questions.isEmpty) {
      _showMessage('Every rubric question needs a teacher-entered mark.');
      return;
    }
    final feedback = _feedbackController.text.trim();
    if (feedback.isEmpty) {
      _showMessage('Add teacher feedback before approving the evaluation.');
      return;
    }
    final marks = double.parse(
      questionMarks.values
          .fold<double>(0, (sum, item) => sum + item)
          .toStringAsFixed(2),
    );
    if (marks > widget.totalMarks) {
      _showMessage('Approved marks cannot exceed ${widget.totalMarks}.');
      return;
    }
    final questionFeedback = <String, String>{};
    for (final question in evaluation.questions) {
      final text =
          _questionFeedbackControllers[question.questionId]?.text.trim() ?? '';
      if (text != _originalQuestionFeedback[question.questionId]) {
        questionFeedback[question.questionId] = text;
      }
    }
    setState(() => _isWorking = true);
    try {
      await _repository.approve(
        token,
        evaluation.id,
        marks: marks,
        feedback: feedback,
        questionMarks: questionMarks,
        questionFeedback: questionFeedback,
      );
      if (!mounted) return;
      _showMessage('Evaluation approved. Publish the grade when ready.');
      setState(() => _isWorking = false);
      await _refresh();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.message;
          _isWorking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to approve this evaluation.';
          _isWorking = false;
        });
      }
    }
  }

  Future<void> _publish(AIEvaluation evaluation) async {
    final token = _token;
    if (token == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          widget.isDemoFixture
              ? 'Publish fixture grade?'
              : 'Publish official grade?',
        ),
        content: Text(
          widget.isDemoFixture
              ? 'This only changes the in-memory demonstration fixture. No student, backend, or database record will be changed.'
              : 'The student will be able to see the approved marks and teacher feedback.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(
              widget.isDemoFixture ? 'Publish fixture grade' : 'Publish grade',
            ),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _isWorking = true);
    try {
      await _repository.publish(token, evaluation.id);
      if (!mounted) return;
      _showMessage(
        widget.isDemoFixture
            ? 'Fixture grade published locally. No backend or student record changed.'
            : 'Official grade published to the student.',
      );
      setState(() => _isWorking = false);
      await _refresh();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.message;
          _isWorking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to publish the approved grade.';
          _isWorking = false;
        });
      }
    }
  }

  Future<void> _reject(AIEvaluation evaluation) async {
    final reasonController = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          widget.isDemoFixture
              ? 'Reject demonstration suggestion?'
              : 'Reject AI evaluation?',
        ),
        content: TextField(
          controller: reasonController,
          autofocus: true,
          maxLength: 2000,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(
            labelText: 'Reason',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, reasonController.text.trim()),
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    reasonController.dispose();
    if (reason == null || reason.isEmpty) return;
    final token = _token;
    if (token == null) return;
    setState(() => _isWorking = true);
    try {
      await _repository.reject(token, evaluation.id, reason);
      if (!mounted) return;
      _showMessage(
        widget.isDemoFixture
            ? 'Demonstration suggestion rejected locally. No grade was released.'
            : 'AI evaluation rejected. No grade was released.',
      );
      setState(() => _isWorking = false);
      await _refresh();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = error.message;
          _isWorking = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Unable to reject this evaluation.';
          _isWorking = false;
        });
      }
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.isDemoFixture ? 'AI evaluation demo' : 'AI evaluation',
      ),
      actions: [
        IconButton(
          tooltip: 'Refresh status',
          onPressed: _isLoading ? null : _refresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    ),
    body: _isLoading
        ? const AppLoader(message: 'Loading evaluation...')
        : RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(20),
              children: [
                if (widget.isDemoFixture || _hasSampleEvaluation) ...[
                  Card(
                    color: Theme.of(context).colorScheme.errorContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        widget.isDemoFixture ? demoAIFixtureDisclosure : 'DEMO/SAMPLE EVALUATION — NOT GENERATED BY LIVE AI',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                Text(
                  widget.assignmentTitle,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  widget.isDemoFixture
                      ? 'All answers, marks, confidence values, and feedback below are synthetic fixture examples. Review actions change only in-memory demo state; no AI was run and no student grade will be changed.'
                      : _hasSampleEvaluation
                      ? 'The sample answer text and marks below are illustrative and were entered for this demo. No OCR or AI ran. Teacher edits, approval, and publication use the normal backend workflow.'
                      : 'AI marks are suggestions only. A teacher must review and approve '
                            'them before an official grade is released.',
                ),
                if (widget.submission != null) ...[
                  const SizedBox(height: 12),
                  _buildSubmissionDetails(widget.submission!),
                ],
                if (_rubricError != null) ...[
                  const SizedBox(height: 12),
                  AppErrorWidget(message: _rubricError!),
                ],
                if (_rubric != null) ...[
                  const SizedBox(height: 12),
                  _buildRubric(_rubric!),
                ],
                if (_errorMessage != null) ...[
                  const SizedBox(height: 16),
                  AppErrorWidget(message: _errorMessage!),
                ],
                const SizedBox(height: 16),
                if (!widget.isDemoFixture)
                  OutlinedButton.icon(
                    onPressed: _isWorking ? null : _configureRubric,
                    icon: const Icon(Icons.rule_folder_outlined),
                    label: const Text('Configure answer key and rubric'),
                  ),
                if (_job == null) ...[
                  const SizedBox(height: 16),
                  const AppEmptyState(
                    title: 'No evaluation yet',
                    message: 'Configure a rubric, then request document extraction and evaluation.',
                  ),
                  if (!widget.isDemoFixture)
                    FilledButton.icon(
                      onPressed: _isWorking ? null : () => _request(),
                      icon: const Icon(Icons.auto_awesome_outlined),
                      label: Text(
                        _isWorking ? 'Starting...' : 'Request evaluation',
                      ),
                    ),
                ] else ...[
                  const SizedBox(height: 16),
                  _buildJob(_job!),
                ],
              ],
            ),
          ),
  );

  Widget _buildJob(EvaluationJob job) {
    final evaluation = job.evaluation;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_publicationError != null) ...[
          AppErrorWidget(message: _publicationError!),
        ],
        Card(
          child: ListTile(
            leading: job.status == 'processing' || job.status == 'pending'
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(
                    job.status == 'completed'
                        ? Icons.check_circle_outline_rounded
                        : Icons.error_outline_rounded,
                  ),
            title: Text('Status: ${job.status}'),
            subtitle: widget.isDemoFixture
                ? const Text(
                    'Preloaded fixture state · no backend job or AI run',
                  )
                : job.errorSummary == null
                ? Text('Attempt ${job.attemptCount}')
                : Text('Processing could not finish: ${job.errorSummary}'),
          ),
        ),
        if (job.status == 'failed' && !widget.isDemoFixture)
          FilledButton.icon(
            onPressed: _isWorking ? null : _retry,
            icon: const Icon(Icons.replay_rounded),
            label: Text(_isWorking ? 'Retrying...' : 'Retry evaluation'),
          ),
        if (job.status == 'completed' && evaluation != null) ...[
          const SizedBox(height: 12),
          _buildEvaluation(evaluation),
        ],
        if (job.extractedAnswers.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(
            widget.isDemoFixture
                ? 'Illustrative extracted answer examples'
                : 'Extracted text',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          for (final answer in job.extractedAnswers)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.isDemoFixture
                          ? 'Illustrative extracted text · not live OCR'
                                '${answer.pageNumber == null ? '' : ' · sample page ${answer.pageNumber}'}'
                          : '${answer.source.replaceAll('_', ' ')}'
                                '${answer.pageNumber == null ? '' : ' · page ${answer.pageNumber}'}',
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                    Text(
                      'Segment ${answer.segmentNumber}'
                      '${answer.ocrConfidence == null
                          ? ''
                          : widget.isDemoFixture
                          ? ' · illustrative confidence ${answer.ocrConfidence!.toStringAsFixed(2)}'
                          : ' · OCR confidence ${answer.ocrConfidence!.toStringAsFixed(2)}'}'
                      '${answer.needsReview ? ' · manual review required' : ''}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (answer.needsReview) ...[
                      const SizedBox(height: 4),
                      const Text(
                        'Extracted text needs review; compare with the original file.',
                        style: TextStyle(color: Colors.deepOrange),
                      ),
                    ],
                    const SizedBox(height: 8),
                    SelectableText(
                      answer.text.isEmpty
                          ? 'No readable text extracted; check the original.'
                          : answer.text,
                    ),
                  ],
                ),
              ),
            ),
        ],
        if (job.status == 'completed' &&
            evaluation != null &&
            !widget.isDemoFixture)
          OutlinedButton.icon(
            onPressed: _isWorking ? null : () => _request(force: true),
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Run a new evaluation'),
          ),
      ],
    );
  }

  Widget _buildSubmissionDetails(Submission submission) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Submission', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text('Student: ${submission.studentName ?? submission.studentId}'),
          Text('Submission ID: ${submission.id}'),
          Text('Status: ${submission.status}'),
          if (submission.submittedAt != null)
            Text('Submitted: ${submission.submittedAt!.toLocal()}'),
          if (submission.submissionText?.isNotEmpty ?? false) ...[
            const SizedBox(height: 12),
            const Text('Submitted text'),
            SelectableText(submission.submissionText!),
          ],
          if (widget.isDemoFixture)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.image_search_outlined),
              title: const Text('View original handwritten sample'),
              subtitle: const Text('Two synthetic PNG pages · local assets'),
              trailing: const Icon(Icons.open_in_new_rounded),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (_) => const DemoSubmissionPreviewScreen(),
                ),
              ),
            ),
          for (final file in submission.attachments) ...[
            const SizedBox(height: 8),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.insert_drive_file_outlined),
              title: Text(file.filename),
              subtitle: Text(
                '${file.contentType} · ${file.sizeBytes} bytes · original preserved',
              ),
              trailing: const Icon(Icons.open_in_new_rounded),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (_) => AttachmentViewerScreen(
                    file: file,
                    repository: _assignmentRepository,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    ),
  );

  Widget _buildRubric(AssignmentRubric rubric) => Card(
    child: ExpansionTile(
      title: Text(
        'Assignment questions and rubric (${rubric.questions.length})',
      ),
      children: [
        for (final question in rubric.questions)
          ListTile(
            title: Text('${question.questionId} · ${question.maxMarks} marks'),
            subtitle: Text(
              [
                question.prompt,
                ...question.criteria.map(
                  (criterion) =>
                      '${criterion.description} (${criterion.marks} marks)',
                ),
                if (question.modelAnswer?.isNotEmpty ?? false)
                  'Model answer: ${question.modelAnswer}',
                if (question.acceptableAnswers.isNotEmpty)
                  'Acceptable answers: ${question.acceptableAnswers.join(' · ')}',
              ].join('\n'),
            ),
          ),
      ],
    ),
  );

  Widget _buildEvaluation(AIEvaluation evaluation) {
    final pendingReview = evaluation.reviewStatus == 'pending';
    final marks = evaluation.approvedMarks ?? evaluation.suggestedTotal;
    final percentage = marks == null || evaluation.maximumMarks <= 0
        ? null
        : marks / evaluation.maximumMarks * 100;
    final gradeBand = percentage == null
        ? null
        : percentage >= 90
        ? 'A'
        : percentage >= 80
        ? 'B'
        : percentage >= 70
        ? 'C'
        : percentage >= 60
        ? 'D'
        : 'F';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  evaluation.suggestedTotal == null
                      ? 'No marks suggested'
                      : '${widget.isDemoFixture
                            ? 'Illustrative fixture marks'
                            : _hasSampleEvaluation
                            ? 'Illustrative sample marks'
                            : 'Suggested'}: ${evaluation.suggestedTotal} / ${evaluation.maximumMarks}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 6),
                Text(
                  widget.isDemoFixture || _hasSampleEvaluation
                      ? 'Sample confidence: not measured'
                      : 'Heuristic signal: ${evaluation.confidence.toStringAsFixed(2)} (uncalibrated)',
                ),
                if (evaluation.reviewStatus == 'approved' &&
                    evaluation.approvedMarks != null)
                  Text(
                    'Teacher-approved total: ${evaluation.approvedMarks} / ${evaluation.maximumMarks}',
                  ),
                if (percentage != null)
                  Text(
                    '${widget.isDemoFixture
                        ? evaluation.reviewStatus == 'approved'
                              ? 'Approved fixture'
                              : 'Provisional fixture'
                        : evaluation.reviewStatus == 'approved'
                        ? 'Approved'
                        : 'Suggested'} percentage: ${percentage.toStringAsFixed(1)}% · illustrative grade band $gradeBand (not institution policy)',
                  ),
                if (evaluation.reviewStatus == 'approved')
                  Text(
                    _isGradePublished
                        ? widget.isDemoFixture
                              ? 'Published locally in this fixture only; no real student record was changed.'
                              : 'Official grade: published to student'
                        : widget.isDemoFixture
                        ? 'Approved in-memory fixture only; it is not published to a student.'
                        : 'Approved provisionally; the student cannot see this grade yet.',
                    style: TextStyle(
                      color: _isGradePublished
                          ? Colors.green.shade700
                          : Colors.deepOrange,
                    ),
                  ),
                if (evaluation.reviewStatus == 'approved' &&
                    evaluation.teacherFeedback != null)
                  Text('Teacher feedback: ${evaluation.teacherFeedback}'),
                Text(
                  '${widget.isDemoFixture || _hasSampleEvaluation ? 'Sample source' : 'Model'}: ${evaluation.modelName} (${evaluation.modelVersion})',
                ),
                const SizedBox(height: 8),
                Text(evaluation.explanation),
                if (evaluation.feedback.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(evaluation.feedback),
                ],
              ],
            ),
          ),
        ),
        for (final item in evaluation.feedbackItems)
          Card(
            child: ListTile(
              leading: Icon(
                item.kind == 'similarity_signal'
                    ? Icons.content_copy_outlined
                    : Icons.info_outline_rounded,
              ),
              title: Text(item.kind.replaceAll('_', ' ')),
              subtitle: Text(
                [
                  item.message,
                  if (item.similarityScore != null)
                    'Similarity signal: ${(item.similarityScore! * 100).round()}%',
                  if (item.otherSubmissionId != null)
                    'Related submission: ${item.otherSubmissionId}',
                  if (item.details['matching_segments'] is List)
                    'Matching text: ${(item.details['matching_segments'] as List).join(' · ')}',
                ].join('\n'),
              ),
            ),
          ),
        for (final question in evaluation.questions) ...[
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    question.questionId,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    question.suggestedMarks == null
                        ? 'No reliable mark suggested / ${question.maximumMarks}'
                        : '${_hasSampleEvaluation ? 'Illustrative sample' : 'Suggested'} ${question.suggestedMarks} / ${question.maximumMarks}',
                  ),
                  if (question.questionId.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      _rubric?.questions
                              .where(
                                (item) =>
                                    item.questionId == question.questionId,
                              )
                              .map((item) => item.prompt)
                              .firstOrNull ??
                          'Question prompt unavailable.',
                    ),
                    for (final criterion
                        in _rubric?.questions
                                .where(
                                  (item) =>
                                      item.questionId == question.questionId,
                                )
                                .expand((item) => item.criteria) ??
                            const <RubricCriterion>[])
                      Text(
                        'Criterion: ${criterion.description} · ${criterion.marks} marks',
                      ),
                  ],
                  Text(
                    _hasSampleEvaluation
                        ? 'Sample confidence: not measured'
                        : 'Heuristic signal: ${question.confidence.toStringAsFixed(2)} (uncalibrated)',
                  ),
                  if (evaluation.reviewStatus == 'approved' &&
                      question.teacherMarks != null)
                    Text(
                      'Teacher-approved ${question.teacherMarks} / ${question.maximumMarks}',
                    ),
                  if (question.needsReview)
                    const Text(
                      'Manual review required.',
                      style: TextStyle(color: Colors.deepOrange),
                    ),
                  const SizedBox(height: 8),
                  Text(question.explanation),
                  if (question.feedback.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      '${widget.isDemoFixture || _hasSampleEvaluation ? 'Sample feedback' : 'AI feedback'}: ${question.feedback}',
                    ),
                  ],
                  if (_savedQuestionFeedback(evaluation, question.questionId)
                      case final teacherQuestionFeedback?)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text('Teacher feedback: $teacherQuestionFeedback'),
                    ),
                  if (question.evidence.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text('Quoted evidence: ${question.evidence.join(' · ')}'),
                  ],
                  if (pendingReview) ...[
                    const SizedBox(height: 12),
                    TextField(
                      controller: _markControllers[question.questionId],
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: InputDecoration(
                        labelText: 'Teacher-approved marks',
                        helperText: 'Maximum ${question.maximumMarks}',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller:
                          _questionFeedbackControllers[question.questionId],
                      minLines: 1,
                      maxLines: 4,
                      maxLength: 5000,
                      decoration: const InputDecoration(
                        labelText:
                            'Teacher feedback for this answer (optional)',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
        if (pendingReview) ...[
          const SizedBox(height: 12),
          TextField(
            controller: _feedbackController,
            minLines: 3,
            maxLines: 6,
            maxLength: 20000,
            decoration: const InputDecoration(
              labelText: 'Teacher feedback for student',
              border: OutlineInputBorder(),
            ),
          ),
          FilledButton.icon(
            onPressed: _isWorking ? null : () => _approve(evaluation),
            icon: const Icon(Icons.verified_outlined),
            label: Text(_isWorking ? 'Saving...' : 'Approve evaluation'),
          ),
          OutlinedButton.icon(
            onPressed: _isWorking ? null : () => _saveReview(evaluation),
            icon: const Icon(Icons.save_outlined),
            label: Text(
              _isWorking ? 'Saving...' : 'Save review changes privately',
            ),
          ),
          TextButton.icon(
            onPressed: _isWorking ? null : () => _reject(evaluation),
            icon: const Icon(Icons.cancel_outlined),
            label: const Text('Reject suggestion'),
          ),
        ] else ...[
          Chip(label: Text('Review ${evaluation.reviewStatus}')),
          if (evaluation.reviewStatus == 'approved' && !_isGradePublished)
            FilledButton.icon(
              onPressed: _isWorking ? null : () => _publish(evaluation),
              icon: const Icon(Icons.publish_rounded),
              label: Text(
                _isWorking
                    ? 'Publishing...'
                    : widget.isDemoFixture
                    ? 'Publish fixture grade locally'
                    : 'Publish approved grade',
              ),
            ),
        ],
      ],
    );
  }
}

class AssignmentRubricEditorScreen extends StatefulWidget {
  const AssignmentRubricEditorScreen({
    super.key,
    required this.assignmentId,
    required this.assignmentTitle,
    required this.totalMarks,
    required this.repository,
  });

  final String assignmentId;
  final String assignmentTitle;
  final double totalMarks;
  final AIEvaluationRepository repository;

  @override
  State<AssignmentRubricEditorScreen> createState() =>
      _AssignmentRubricEditorScreenState();
}

class _AssignmentRubricEditorScreenState
    extends State<AssignmentRubricEditorScreen> {
  final _answerController = TextEditingController();
  final _instructionsController = TextEditingController();
  final List<_RubricQuestionFields> _questions = [];
  String? _errorMessage;
  bool _isLoading = true;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _answerController.dispose();
    _instructionsController.dispose();
    for (final question in _questions) {
      question.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Please sign in again to configure the rubric.';
      });
      return;
    }
    try {
      final rubric = await widget.repository.getRubric(
        token,
        widget.assignmentId,
      );
      _answerController.text = rubric.modelAnswer ?? '';
      _instructionsController.text = rubric.teacherInstructions ?? '';
      for (final question in rubric.questions) {
        _questions.add(_RubricQuestionFields.fromQuestion(question));
      }
    } on NotFoundException {
      _questions.add(_RubricQuestionFields(questionId: 'q1'));
    } on ApiException catch (error) {
      _errorMessage = error.message;
    } catch (_) {
      _errorMessage = 'Unable to load the answer key.';
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _addQuestion() {
    final existing = _questions
        .map((question) => question.questionId.text.trim().toLowerCase())
        .toSet();
    var index = _questions.length + 1;
    while (existing.contains('q$index')) {
      index++;
    }
    setState(() {
      _questions.add(_RubricQuestionFields(questionId: 'q$index'));
    });
  }

  void _removeQuestion(_RubricQuestionFields question) {
    setState(() => _questions.remove(question));
    question.dispose();
  }

  void _addCriterion(_RubricQuestionFields question) {
    setState(() => question.criteria.add(_CriterionFields()));
  }

  void _removeCriterion(_CriterionFields criterion) {
    for (final question in _questions) {
      if (question.criteria.remove(criterion)) {
        setState(() {});
        criterion.dispose();
        return;
      }
    }
  }

  Future<void> _save() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(
        () => _errorMessage = 'Please sign in again to save the rubric.',
      );
      return;
    }
    if (_questions.isEmpty) {
      setState(() => _errorMessage = 'Add at least one rubric question.');
      return;
    }
    final questionJson = <Map<String, dynamic>>[];
    var total = 0.0;
    for (final question in _questions) {
      final marks = double.tryParse(question.marks.text.trim());
      if (question.prompt.text.trim().isEmpty ||
          marks == null ||
          marks <= 0 ||
          question.questionId.text.trim().isEmpty) {
        setState(
          () => _errorMessage =
              'Enter a question, ID, and positive maximum mark.',
        );
        return;
      }
      total = double.parse((total + marks).toStringAsFixed(2));
      final criteriaJson = <Map<String, dynamic>>[];
      var criteriaTotal = 0.0;
      for (final criterion in question.criteria) {
        final criterionMarks = double.tryParse(criterion.marks.text.trim());
        if (criterion.description.text.trim().isEmpty ||
            criterionMarks == null ||
            criterionMarks <= 0) {
          setState(
            () => _errorMessage = 'Enter a description and positive mark for each scoring criterion.',
          );
          return;
        }
        criteriaTotal = double.parse(
          (criteriaTotal + criterionMarks).toStringAsFixed(2),
        );
        final keywords = _lines(criterion.keywords.text);
        final concepts = _lines(criterion.concepts.text);
        if (keywords.length > 30 || concepts.length > 30) {
          setState(
            () => _errorMessage =
                'Use no more than 30 keywords or concepts per criterion.',
          );
          return;
        }
        criteriaJson.add({
          'description': criterion.description.text.trim(),
          'marks': criterionMarks,
          'keywords': keywords,
          'concepts': concepts,
        });
      }
      if (criteriaTotal > marks) {
        setState(
          () => _errorMessage =
              'Scoring criterion marks exceed the maximum for ${question.questionId.text.trim()}.',
        );
        return;
      }
      final acceptableAnswers = _lines(question.acceptableAnswers.text);
      final partialCreditRules = _lines(question.partialCredit.text);
      if (acceptableAnswers.length > 20 || partialCreditRules.length > 30) {
        setState(
          () => _errorMessage = 'A question supports up to 20 alternatives and 30 partial-credit rules.',
        );
        return;
      }
      questionJson.add({
        'question_id': question.questionId.text.trim(),
        'prompt': question.prompt.text.trim(),
        'max_marks': marks,
        'model_answer': _nullableText(question.modelAnswer.text),
        'acceptable_answers': acceptableAnswers,
        'criteria': criteriaJson,
        'partial_credit_rules': partialCreditRules,
      });
    }
    if (total > widget.totalMarks) {
      setState(
        () => _errorMessage =
            'Rubric marks ($total) exceed the assignment total (${widget.totalMarks}).',
      );
      return;
    }
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });
    try {
      await widget.repository.saveRubric(token, widget.assignmentId, {
        'model_answer': _nullableText(_answerController.text),
        'teacher_instructions': _nullableText(_instructionsController.text),
        'questions': questionJson,
      });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } catch (_) {
      if (mounted) setState(() => _errorMessage = 'Unable to save the rubric.');
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Answer key and rubric')),
    body: _isLoading
        ? const AppLoader(message: 'Loading rubric...')
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                '${widget.assignmentTitle} · ${widget.totalMarks} points',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _answerController,
                minLines: 3,
                maxLines: 8,
                maxLength: 30000,
                decoration: const InputDecoration(
                  labelText: 'Overall model answer (optional)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _instructionsController,
                minLines: 2,
                maxLines: 6,
                maxLength: 10000,
                decoration: const InputDecoration(
                  labelText: 'Teacher evaluation instructions (optional)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              Text('Questions', style: Theme.of(context).textTheme.titleLarge),
              for (final question in _questions)
                _RubricQuestionEditor(
                  question: question,
                  onRemove: _questions.length > 1
                      ? () => _removeQuestion(question)
                      : null,
                  onAddCriterion: () => _addCriterion(question),
                  onRemoveCriterion: _removeCriterion,
                ),
              TextButton.icon(
                onPressed: _addQuestion,
                icon: const Icon(Icons.add_rounded),
                label: const Text('Add question'),
              ),
              if (_errorMessage != null) ...[
                const SizedBox(height: 8),
                Text(
                  _errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _isSaving ? null : _save,
                child: Text(
                  _isSaving ? 'Saving...' : 'Save answer key and rubric',
                ),
              ),
            ],
          ),
  );
}

class _RubricQuestionFields {
  _RubricQuestionFields({required String questionId})
    : questionId = TextEditingController(text: questionId);

  factory _RubricQuestionFields.fromQuestion(RubricQuestion question) {
    final fields = _RubricQuestionFields(questionId: question.questionId)
      ..prompt.text = question.prompt
      ..marks.text = question.maxMarks.toString()
      ..modelAnswer.text = question.modelAnswer ?? ''
      ..acceptableAnswers.text = question.acceptableAnswers.join('\n')
      ..partialCredit.text = question.partialCreditRules.join('\n')
      ..criteria.addAll(question.criteria.map(_CriterionFields.fromCriterion));
    return fields;
  }

  final TextEditingController questionId;
  final TextEditingController prompt = TextEditingController();
  final TextEditingController marks = TextEditingController();
  final TextEditingController modelAnswer = TextEditingController();
  final TextEditingController acceptableAnswers = TextEditingController();
  final TextEditingController partialCredit = TextEditingController();
  final List<_CriterionFields> criteria = [];

  void dispose() {
    questionId.dispose();
    prompt.dispose();
    marks.dispose();
    modelAnswer.dispose();
    acceptableAnswers.dispose();
    partialCredit.dispose();
    for (final criterion in criteria) {
      criterion.dispose();
    }
  }
}

class _RubricQuestionEditor extends StatelessWidget {
  const _RubricQuestionEditor({
    required this.question,
    required this.onAddCriterion,
    required this.onRemoveCriterion,
    this.onRemove,
  });

  final _RubricQuestionFields question;
  final VoidCallback? onRemove;
  final VoidCallback onAddCriterion;
  final ValueChanged<_CriterionFields> onRemoveCriterion;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(top: 12),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: question.questionId,
                  decoration: const InputDecoration(labelText: 'Question ID'),
                ),
              ),
              if (onRemove != null)
                IconButton(
                  tooltip: 'Remove question',
                  onPressed: onRemove,
                  icon: const Icon(Icons.delete_outline_rounded),
                ),
            ],
          ),
          TextField(
            controller: question.prompt,
            minLines: 2,
            maxLines: 4,
            maxLength: 4000,
            decoration: const InputDecoration(labelText: 'Question prompt'),
          ),
          TextField(
            controller: question.marks,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Maximum marks'),
          ),
          TextField(
            controller: question.modelAnswer,
            minLines: 2,
            maxLines: 5,
            maxLength: 10000,
            decoration: const InputDecoration(
              labelText: 'Model answer (optional)',
            ),
          ),
          TextField(
            controller: question.acceptableAnswers,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(
              labelText: 'Other acceptable answers (one per line)',
            ),
          ),
          TextField(
            controller: question.partialCredit,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(
              labelText: 'Partial-credit rules (one per line)',
            ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Scoring criteria',
              style: Theme.of(context).textTheme.titleSmall,
            ),
          ),
          for (final criterion in question.criteria)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: criterion.marks,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Criterion marks',
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Remove criterion',
                          onPressed: () => onRemoveCriterion(criterion),
                          icon: const Icon(Icons.delete_outline_rounded),
                        ),
                      ],
                    ),
                    TextField(
                      controller: criterion.description,
                      minLines: 1,
                      maxLines: 3,
                      maxLength: 1000,
                      decoration: const InputDecoration(
                        labelText: 'Criterion description',
                      ),
                    ),
                    TextField(
                      controller: criterion.keywords,
                      minLines: 1,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Keywords (one per line)',
                      ),
                    ),
                    TextField(
                      controller: criterion.concepts,
                      minLines: 1,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Concepts (one per line)',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: onAddCriterion,
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add scoring criterion'),
            ),
          ),
        ],
      ),
    ),
  );
}

class _CriterionFields {
  _CriterionFields();

  factory _CriterionFields.fromCriterion(RubricCriterion criterion) =>
      _CriterionFields()
        ..description.text = criterion.description
        ..marks.text = criterion.marks.toString()
        ..keywords.text = criterion.keywords.join('\n')
        ..concepts.text = criterion.concepts.join('\n');

  final TextEditingController description = TextEditingController();
  final TextEditingController marks = TextEditingController();
  final TextEditingController keywords = TextEditingController();
  final TextEditingController concepts = TextEditingController();

  void dispose() {
    description.dispose();
    marks.dispose();
    keywords.dispose();
    concepts.dispose();
  }
}

String? _nullableText(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}

List<String> _lines(String value) => value
    .split('\n')
    .map((item) => item.trim())
    .where((item) => item.isNotEmpty)
    .toList();
