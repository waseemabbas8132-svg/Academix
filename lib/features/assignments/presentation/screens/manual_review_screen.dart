import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/ai_evaluation.dart';
import 'package:academix/features/assignments/data/repositories/review_repository.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/repositories/ai_evaluation_repository.dart';
import 'package:academix/features/assignments/presentation/screens/attachment_viewer_screen.dart';
import 'package:academix/features/assignments/presentation/screens/ai_evaluation_screens.dart';

class ManualReviewScreen extends StatefulWidget {
  const ManualReviewScreen({
    super.key,
    required this.submission,
    required this.assignments,
    this.reviews,
    this.ai,
  });
  final Submission submission;
  final AssignmentRepository assignments;
  final ReviewRepository? reviews;
  final AIEvaluationRepository? ai;
  @override
  State<ManualReviewScreen> createState() => _ManualReviewState();
}

class _ManualReviewState extends State<ManualReviewScreen> {
  late final _api = widget.reviews ?? ReviewRepository();
  late final _aiApi = widget.ai ?? HttpAIEvaluationRepository();
  final _form = GlobalKey<FormState>();
  final _overall = TextEditingController(),
      _override = TextEditingController(),
      _reason = TextEditingController();
  final Map<String, TextEditingController> _marks = {}, _feedback = {};
  Map<String, dynamic>? _context;
  AIEvaluation? _suggestion;
  bool _loading = true, _saving = false, _dirty = false;
  String? _error, _aiError;
  String get _token => context.read<AuthProvider>().token ?? '';
  String get _id => widget.submission.id;
  Map<String, dynamic>? get _latest =>
      _context?['latest'] as Map<String, dynamic>?;
  List<Map<String, dynamic>> get _questions =>
      (_context?['questions'] as List? ?? []).cast<Map<String, dynamic>>();
  @override
  void initState() {
    super.initState();
    _load();
    _loadAI();
  }

  @override
  void dispose() {
    for (final c in [
      ..._marks.values,
      ..._feedback.values,
      _overall,
      _override,
      _reason,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _loadAI() async {
    try {
      final job = await _aiApi.getLatest(_token, _id);
      if (mounted) setState(() => _suggestion = job?.evaluation);
    } catch (_) {
      if (mounted) {
        setState(
          () => _aiError = 'Existing AI suggestions could not be loaded. Manual review remains available.',
        );
      }
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _api.get(_token, '/submissions/$_id/review');
      if (!mounted) return;
      for (final c in [..._marks.values, ..._feedback.values]) {
        c.dispose();
      }
      _marks.clear();
      _feedback.clear();
      _context = result;
      final saved = result['stale'] == true ? null : _latest;
      final savedQuestions = (saved?['questions'] as List? ?? [])
          .cast<Map<String, dynamic>>();
      for (final q in _questions) {
        final found = savedQuestions.where(
          (s) => s['question_id'] == q['question_id'],
        );
        final previous = found.isEmpty ? null : found.first;
        _marks[q['question_id']] = TextEditingController(
          text: previous?['marks']?.toString() ?? '',
        );
        _feedback[q['question_id']] = TextEditingController(
          text: previous?['feedback']?.toString() ?? '',
        );
      }
      _overall.text = saved?['overall_feedback']?.toString() ?? '';
      _override.text = saved?['total_override']?.toString() ?? '';
      _reason.text = saved?['override_reason']?.toString() ?? '';
      setState(() {
        _loading = false;
        _dirty = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Unable to load private review: $e';
          _loading = false;
        });
      }
    }
  }

  Map<String, dynamic> _version() => {
    'expected_version': _latest?['version'] ?? 0,
    'source_updated_at': _context!['source_updated_at'],
    'rubric_signature': _context!['rubric_signature'],
  };
  String? _validateMark(
    String? value,
    dynamic maximum, {
    bool optional = true,
  }) {
    if (value == null || value.trim().isEmpty) {
      return optional ? null : 'Enter a mark.';
    }
    final number = double.tryParse(value);
    if (!RegExp(r'^\d+(\.\d{1,2})?$').hasMatch(value) ||
        number == null ||
        !number.isFinite ||
        number < 0 ||
        number > double.parse('$maximum')) {
      return 'Enter 0–$maximum, with at most 2 decimal places.';
    }
    return null;
  }

  Future<void> _save(String state) async {
    if (!_form.currentState!.validate()) return;
    if (state == 'reviewed' &&
        (_marks.values.any((c) => c.text.trim().isEmpty) ||
            _overall.text.trim().isEmpty)) {
      _message(
        'Complete every question mark and overall feedback before marking reviewed.',
      );
      return;
    }
    setState(() => _saving = true);
    try {
      await _api.save(_token, _id, {
        ..._version(),
        'state': state,
        'questions': [
          for (final q in _questions)
            {
              'question_id': q['question_id'],
              'marks': _marks[q['question_id']]!.text.isEmpty
                  ? null
                  : _marks[q['question_id']]!.text,
              'feedback': _feedback[q['question_id']]!.text,
            },
        ],
        'overall_feedback': _overall.text,
        'total_override': _override.text.isEmpty ? null : _override.text,
        'override_reason': _reason.text,
      });
      if (mounted) {
        await _load();
        if (mounted) {
          _message(
            state == 'draft'
                ? 'Private draft saved.'
                : 'Review saved. Ready for explicit release.',
          );
        }
      }
    } catch (e) {
      if (mounted) _message('Review not saved: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _message(String message) =>
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
  Future<void> _release() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Release official grade?'),
        content: Text(
          'Release ${_latest?['total']} / ${_context!['total_marks']} and feedback to ${widget.submission.studentId}? This updates the official grade.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Release grade'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _action('release', {});
  }

  Future<void> _return() async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Return for revision'),
        content: TextField(
          controller: controller,
          maxLength: 20000,
          minLines: 3,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: 'Required revision reason',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              if (controller.text.trim().isNotEmpty) {
                Navigator.pop(ctx, controller.text.trim());
              }
            },
            child: const Text('Return work'),
          ),
        ],
      ),
    );
    // The dialog route may animate after completion; dispose next frame.
    Future<void>.delayed(const Duration(seconds: 1), controller.dispose);
    if (reason == null || !mounted) return;
    await _action('return', {'reason': reason});
  }

  Future<void> _action(String action, Map<String, dynamic> extra) async {
    setState(() => _saving = true);
    try {
      await _api.action(_token, _id, action, {..._version(), ...extra});
      if (mounted) {
        await _load();
        if (mounted) {
          _message(
            action == 'release'
                ? 'Official grade released.'
                : 'Revision requested.',
          );
        }
      }
    } catch (e) {
      if (mounted) _message('Action failed: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _history() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            ReviewHistoryScreen(api: _api, token: _token, submissionId: _id),
      ),
    );
  }

  Future<void> _criteria() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => AssignmentRubricEditorScreen(
          assignmentId: widget.submission.assignmentId,
          assignmentTitle: widget.submission.assignmentTitle ?? 'Assignment',
          totalMarks: widget.submission.totalMarks ?? 0,
          repository: _aiApi,
        ),
      ),
    );
    if (mounted) await _load();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_dirty || _saving,
    onPopInvokedWithResult: (didPop, result) async {
      if (didPop) return;
      final discard = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Discard unsaved edits?'),
          content: const Text(
            'Your last saved private draft remains available. New edits will be discarded.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Keep editing'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Discard edits'),
            ),
          ],
        ),
      );
      if (discard == true && mounted) {
        setState(() => _dirty = false);
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) Navigator.pop(context);
        });
      }
    },
    child: Scaffold(
      appBar: AppBar(
        title: const Text('Manual review'),
        actions: [
          IconButton(
            tooltip: 'Grading history',
            onPressed: _saving ? null : _history,
            icon: const Icon(Icons.history),
          ),
          IconButton(
            tooltip: 'Question criteria',
            onPressed: _saving || _dirty ? null : _criteria,
            icon: const Icon(Icons.rule),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_error!),
                  TextButton(onPressed: _load, child: const Text('Retry')),
                ],
              ),
            )
          : Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1100),
                child: Form(
                  key: _form,
                  onChanged: () {
                    if (!_dirty) {
                      setState(() => _dirty = true);
                    } else {
                      setState(() {});
                    }
                  },
                  child: ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      Text(
                        widget.submission.studentId,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      Text(
                        'Attempt ${_context!['source_revision']} • Official status: ${_context!['official_status']}',
                      ),
                      Text(
                        'Official released total: ${_context!['official_marks'] ?? 'Not released'} / ${_context!['total_marks']}',
                      ),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Text(
                            _dirty
                                ? 'Unsaved changes — students cannot see this review.'
                                : 'Saved review: ${_latest?['state'] ?? 'Not started'} • ${_latest?['created_at'] ?? ''} • ${_latest?['actor'] ?? ''}',
                          ),
                        ),
                      ),
                      if (_context!['stale'] == true)
                        const Text(
                          'Previous review belongs to older work or criteria. Start a new review; old history is preserved.',
                          style: TextStyle(color: Colors.deepOrange),
                        ),
                      ExpansionTile(
                        initiallyExpanded: true,
                        title: const Text('Original student response'),
                        children: [
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: SelectableText(
                              _context!['source_text'] as String? ??
                                  'File-based submission',
                            ),
                          ),
                          for (final file
                              in (_context!['source_files'] as List? ?? []).map(
                                (f) => AssignmentFile.fromJson(
                                  f as Map<String, dynamic>,
                                ),
                              ))
                            ListTile(
                              title: Text(file.filename),
                              leading: const Icon(Icons.description_outlined),
                              trailing: const Icon(Icons.open_in_full),
                              onTap: () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => AttachmentViewerScreen(
                                    file: file,
                                    repository: widget.assignments,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                      if (_aiError != null) Text(_aiError!),
                      if (_suggestion != null)
                        ExpansionTile(
                          title: Text(
                            'Existing AI suggestions • ${_suggestion!.reviewStatus}',
                          ),
                          children: [
                            const Padding(
                              padding: EdgeInsets.all(12),
                              child: Text(
                                'Read-only suggestions may relate to earlier work. Check the source in AI review. No AI values are copied into this review. Manual release is independent.',
                              ),
                            ),
                            Text(
                              'AI proposed total: ${_suggestion!.suggestedTotal ?? 'Unscored'} • Previously AI-approved: ${_suggestion!.approvedMarks ?? 'Not approved'}',
                            ),
                            Text(_suggestion!.feedback),
                            for (final q in _suggestion!.questions)
                              ListTile(
                                title: Text(
                                  '${q.questionId}: AI suggestion ${q.suggestedMarks ?? 'Unscored'} / ${q.maximumMarks}',
                                ),
                                subtitle: Text(
                                  '${q.explanation}\n${q.feedback}\nAI-review teacher mark: ${q.teacherMarks ?? 'Not approved'}',
                                ),
                              ),
                            for (final signal in _suggestion!.feedbackItems)
                              ListTile(
                                title: Text(signal.kind),
                                subtitle: Text(signal.message),
                              ),
                          ],
                        ),
                      const SizedBox(height: 16),
                      for (final q in _questions)
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '${q['question_id']} • ${q['max_marks']} maximum',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium,
                                ),
                                SelectableText('${q['prompt']}'),
                                for (final criterion
                                    in (q['criteria'] as List? ?? []))
                                  Text(
                                    '• ${criterion['description']} (${criterion['marks']} marks)',
                                  ),
                                const SizedBox(height: 12),
                                TextFormField(
                                  controller: _marks[q['question_id']],
                                  enabled: !_saving,
                                  keyboardType:
                                      const TextInputType.numberWithOptions(
                                        decimal: true,
                                      ),
                                  decoration: InputDecoration(
                                    labelText:
                                        'Teacher mark ${q['question_id']}',
                                  ),
                                  validator: (value) =>
                                      _validateMark(value, q['max_marks']),
                                ),
                                const SizedBox(height: 8),
                                TextFormField(
                                  controller: _feedback[q['question_id']],
                                  enabled: !_saving,
                                  maxLength: 5000,
                                  minLines: 1,
                                  maxLines: 4,
                                  decoration: InputDecoration(
                                    labelText: 'Feedback ${q['question_id']}',
                                  ),
                                ),
                                if (_suggestion != null)
                                  Text(
                                    'AI suggestion: ${_suggestion!.questions.where((s) => s.questionId == q['question_id']).map((s) => s.suggestedMarks ?? 'Unscored').join(', ')} • Your mark: ${_marks[q['question_id']]!.text.isEmpty ? 'Not entered' : _marks[q['question_id']]!.text}',
                                  ),
                              ],
                            ),
                          ),
                        ),
                      Text(
                        'Calculated teacher total: ${_marks.values.fold<double>(0, (sum, c) => sum + (double.tryParse(c.text) ?? 0)).toStringAsFixed(2)} / ${_context!['total_marks']}',
                      ),
                      TextFormField(
                        controller: _overall,
                        enabled: !_saving,
                        maxLength: 20000,
                        minLines: 2,
                        maxLines: 6,
                        decoration: const InputDecoration(
                          labelText: 'Overall teacher feedback',
                        ),
                      ),
                      ExpansionTile(
                        title: const Text(
                          'Justified total override (owning teacher)',
                        ),
                        children: [
                          TextFormField(
                            controller: _override,
                            enabled: !_saving,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Override total (optional)',
                            ),
                            validator: (v) =>
                                _validateMark(v, _context!['total_marks']),
                          ),
                          TextFormField(
                            controller: _reason,
                            enabled: !_saving,
                            maxLength: 5000,
                            decoration: const InputDecoration(
                              labelText: 'Override justification',
                            ),
                            validator: (v) =>
                                _override.text.isNotEmpty &&
                                    (v ?? '').trim().isEmpty
                                ? 'Explain why you are overriding the calculated total.'
                                : null,
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          OutlinedButton.icon(
                            onPressed: _saving ? null : () => _save('draft'),
                            icon: const Icon(Icons.save_outlined),
                            label: Text(
                              _saving ? 'Saving…' : 'Save private draft',
                            ),
                          ),
                          FilledButton.tonal(
                            onPressed: _saving ? null : () => _save('reviewed'),
                            child: const Text('Mark reviewed'),
                          ),
                          FilledButton.icon(
                            onPressed:
                                _saving ||
                                    _dirty ||
                                    _context!['stale'] == true ||
                                    _latest?['state'] != 'reviewed'
                                ? null
                                : _release,
                            icon: const Icon(Icons.publish),
                            label: const Text('Release official grade'),
                          ),
                          OutlinedButton(
                            onPressed: _saving ? null : _return,
                            child: const Text('Return for revision'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 32),
                    ],
                  ),
                ),
              ),
            ),
    ),
  );
}

class ReviewHistoryScreen extends StatefulWidget {
  const ReviewHistoryScreen({
    super.key,
    required this.api,
    required this.token,
    required this.submissionId,
  });
  final ReviewRepository api;
  final String token, submissionId;
  @override
  State<ReviewHistoryScreen> createState() => _HistoryState();
}

class _HistoryState extends State<ReviewHistoryScreen> {
  int _offset = 0;
  late Future<Map<String, dynamic>> _request = _load();
  Future<Map<String, dynamic>> _load() => widget.api.get(
    widget.token,
    '/submissions/${widget.submissionId}/review/history',
    query: {'offset': _offset, 'limit': 25},
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Private grading history')),
    body: FutureBuilder<Map<String, dynamic>>(
      future: _request,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: TextButton(
              onPressed: () => setState(() => _request = _load()),
              child: const Text('History failed. Retry'),
            ),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final data = snapshot.data!;
        final rows = data['items'] as List;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (rows.isEmpty) const Text('No saved reviews yet.'),
            for (final r in rows)
              ExpansionTile(
                title: Text(
                  'Version ${r['version']} • ${r['state']} • Attempt ${r['source_revision']}',
                ),
                subtitle: Text('${r['actor']} • ${r['created_at']}'),
                children: [
                  if (r['total'] != null)
                    Text(
                      'Total ${r['total']} • Calculated ${r['calculated_total']}',
                    ),
                  if (r['override_reason'] != null)
                    Text('Override justification: ${r['override_reason']}'),
                  Text('${r['overall_feedback'] ?? r['reason'] ?? ''}'),
                  for (final q in (r['questions'] as List? ?? []))
                    ListTile(
                      title: Text(
                        '${q['question_id']} • ${q['marks'] ?? 'Incomplete'} / ${q['max_marks']}',
                      ),
                      subtitle: Text('${q['feedback']}'),
                    ),
                ],
              ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextButton(
                  onPressed: _offset == 0
                      ? null
                      : () {
                          setState(() {
                            _offset -= 25;
                            _request = _load();
                          });
                        },
                  child: const Text('Newer'),
                ),
                Text('${data['total']} versions'),
                TextButton(
                  onPressed: _offset + rows.length >= data['total']
                      ? null
                      : () {
                          setState(() {
                            _offset += 25;
                            _request = _load();
                          });
                        },
                  child: const Text('Older'),
                ),
              ],
            ),
          ],
        );
      },
    ),
  );
}

class ReleasedQuestionMarks extends StatefulWidget {
  const ReleasedQuestionMarks({
    super.key,
    required this.submissionId,
    this.repository,
  });
  final String submissionId;
  final ReviewRepository? repository;
  @override
  State<ReleasedQuestionMarks> createState() => _ReleasedMarksState();
}

class _ReleasedMarksState extends State<ReleasedQuestionMarks> {
  late Future<Map<String, dynamic>?> _request = _load();
  Future<Map<String, dynamic>?> _load() =>
      (widget.repository ?? ReviewRepository()).released(
        context.read<AuthProvider>().token ?? '',
        widget.submissionId,
      );
  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>?>(
    future: _request,
    builder: (context, snapshot) {
      if (snapshot.hasError) {
        return TextButton(
          onPressed: () => setState(() => _request = _load()),
          child: const Text('Question marks unavailable. Retry'),
        );
      }
      if (!snapshot.hasData) return const SizedBox.shrink();
      return ExpansionTile(
        title: const Text('Released question marks'),
        subtitle: Text('Released ${snapshot.data!['released_at']}'),
        children: [
          for (final q in snapshot.data!['questions'] as List)
            ListTile(
              title: Text(
                '${q['question_id']}: ${q['marks']} / ${q['max_marks']}',
              ),
              subtitle: Text('${q['feedback']}'),
            ),
        ],
      );
    },
  );
}
