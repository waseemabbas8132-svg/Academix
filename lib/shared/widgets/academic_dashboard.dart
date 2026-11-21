import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/repositories/demo_ai_evaluation_repository.dart';
import 'package:academix/features/assignments/data/repositories/review_repository.dart';
import 'package:academix/features/assignments/presentation/screens/ai_evaluation_screens.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_details_screen.dart';
import 'package:academix/features/assignments/presentation/screens/submission_screens.dart';
import 'package:academix/features/classes/presentation/screens/classes_screen.dart';

class AcademicDashboard extends StatefulWidget {
  const AcademicDashboard({
    super.key,
    required this.role,
    this.mode = 'home',
    this.repository,
  });
  final String role, mode;
  final ReviewRepository? repository;
  @override
  State<AcademicDashboard> createState() => _AcademicDashboardState();
}

class _AcademicDashboardState extends State<AcademicDashboard> {
  late final _api = widget.repository ?? ReviewRepository();
  final _assignments = HttpAssignmentRepository();
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = true;
  int _offset = 0;
  String get _token => context.read<AuthProvider>().token ?? '';
  bool get _teacher => widget.role == 'teacher';
  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant AcademicDashboard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.mode != widget.mode || oldWidget.role != widget.role) {
      _offset = 0;
      _load();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.get(
        _token,
        '/${widget.role}/dashboard',
        query: {
          'offset': _offset,
          'limit': 25,
          'timezone_offset_minutes': DateTime.now().timeZoneOffset.inMinutes,
        },
      );
      if (mounted) {
        setState(() {
          _data = data;
          _loading = false;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = 'Dashboard unavailable: $error';
          _loading = false;
        });
      }
    }
  }

  Future<void> _openAssignment(String id) async {
    try {
      final assignment = await _assignments.getAssignment(_token, id);
      if (!mounted) return;
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => AssignmentDetailsScreen(
            assignment: assignment,
            isTeacher: _teacher,
            repository: _assignments,
          ),
        ),
      );
      if (mounted) await _load();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Unable to open assignment: $error')),
        );
      }
    }
  }

  Future<void> _openActivity(Map<String, dynamic> row) async {
    if (row['submission_id'] == null) {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(builder: (_) => const ClassesScreen()),
      );
      return;
    }
    try {
      final submission = _teacher
          ? Submission.fromJson(
              await _api.get(_token, '/submissions/${row['submission_id']}'),
            )
          : await _assignments.getMySubmission(_token, row['submission_id']);
      if (!mounted) return;
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => SubmissionDetailsScreen(
            submission: submission,
            isTeacher: _teacher,
            repository: _assignments,
          ),
        ),
      );
      if (mounted) await _load();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Unable to open update: $error')),
        );
      }
    }
  }

  String _date(dynamic value) {
    final parsed = DateTime.tryParse('$value');
    return parsed == null
        ? 'Time unavailable'
        : DateFormat.yMMMd().add_jm().format(parsed.toLocal());
  }

  String _label(String value) => value.replaceAll('_', ' ');
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.mode == 'calendar'
            ? 'Assignment deadlines'
            : widget.mode == 'notifications'
            ? 'Recent classroom updates'
            : _teacher
            ? 'Teacher Home'
            : 'Student Home',
      ),
      actions: [
        IconButton(
          tooltip: 'Refresh dashboard',
          onPressed: _loading ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : _error != null
        ? Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_error!),
                  TextButton(onPressed: _load, child: const Text('Try again')),
                ],
              ),
            ),
          )
        : RefreshIndicator(
            onRefresh: _load,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1250),
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(20),
                  children: [
                    if (widget.mode == 'home') ...[
                      Text(
                        '${_data!['message']}',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Updated ${_date(_data!['server_now'])} • Deadline labels calculated by the server',
                      ),
                      const SizedBox(height: 20),
                      LayoutBuilder(
                        builder: (context, constraints) {
                          final width = constraints.maxWidth >= 850
                              ? (constraints.maxWidth - 48) / 4
                              : constraints.maxWidth >= 480
                              ? (constraints.maxWidth - 16) / 2
                              : constraints.maxWidth;
                          final stats =
                              _data!['statistics'] as Map<String, dynamic>;
                          return Wrap(
                            spacing: 16,
                            runSpacing: 16,
                            children: [
                              for (final entry in stats.entries)
                                SizedBox(
                                  width: width,
                                  child: Card(
                                    child: Padding(
                                      padding: const EdgeInsets.all(18),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '${entry.value}',
                                            style: Theme.of(context)
                                                .textTheme
                                                .headlineMedium,
                                          ),
                                          Text(_label(entry.key)),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                          );
                        },
                      ),
                      const SizedBox(height: 20),
                    ],
                    if (widget.mode == 'home' && _teacher) ...[
                      Card(
                        child: ListTile(
                          leading: const Icon(Icons.science_outlined),
                          title: const Text('Open isolated AI evaluation demo'),
                          subtitle: const Text(
                            'Synthetic handwritten sample · no live AI or student records',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () {
                            final submission = createDemoWaterCycleSubmission();
                            Navigator.of(context).push<void>(
                              MaterialPageRoute<void>(
                                builder: (_) => TeacherAIEvaluationScreen(
                                  assignmentId: demoAIWaterCycleAssignmentId,
                                  assignmentTitle:
                                      demoAIWaterCycleAssignmentTitle,
                                  submissionId: demoAIWaterCycleSubmissionId,
                                  totalMarks: 20,
                                  submission: submission,
                                  repository: DemoAIEvaluationRepository(),
                                  isDemoFixture: true,
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                      const SizedBox(height: 8),
                    ],
                    if (widget.mode != 'notifications') ...[
                      Text(
                        'Active assignment deadlines',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const Text(
                        'Overdue work remains visible. Late submissions are accepted and flagged under existing rules.',
                      ),
                      if ((_data!['deadlines'] as List).isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text('No active assignments on this page.'),
                        ),
                      for (final row in _data!['deadlines'] as List)
                        Card(
                          child: ListTile(
                            leading: const Icon(Icons.event_note),
                            title: Text('${row['title']}'),
                            subtitle: Text(
                              '${_date(row['due_date'])}\n${_label(row['status'])} • ${_label(row['submission_status'])}',
                            ),
                            isThreeLine: true,
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => _openAssignment(row['assignment_id']),
                          ),
                        ),
                    ],
                    if (widget.mode != 'calendar') ...[
                      const SizedBox(height: 20),
                      Text(
                        'Recent classroom activity and feedback',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const Text(
                        'Latest updates; refreshing retrieves current submission and release states.',
                      ),
                      if ((_data!['activity'] as List).isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text('No classroom activity yet.'),
                        ),
                      for (final row in _data!['activity'] as List)
                        Card(
                          child: ListTile(
                            leading: Icon(
                              row['kind'] == 'announcement'
                                  ? Icons.campaign_outlined
                                  : Icons.assignment_turned_in_outlined,
                            ),
                            title: Text('${row['title']}'),
                            subtitle: Text(
                              '${_date(row['at'])} • ${row['status'] ?? 'Announcement'}${row['marks_obtained'] != null ? ' • Released ${row['marks_obtained']} marks' : ''}\n${row['feedback'] ?? ''}',
                            ),
                            onTap: () =>
                                _openActivity(Map<String, dynamic>.from(row)),
                          ),
                        ),
                    ],
                    if (widget.mode == 'home') ...[
                      const SizedBox(height: 20),
                      Text(
                        'Released grade performance',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      if ((_data!['performance'] as List).isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text(
                            'Performance summaries appear after grades are released.',
                          ),
                        ),
                      for (final row in _data!['performance'] as List)
                        ListTile(
                          title: Text('${row['title']}'),
                          subtitle: Text(
                            '${row['released']} released grades • Average ${(row['average'] as num).toStringAsFixed(2)} / ${row['total_marks']}',
                          ),
                          onTap: () => _openAssignment(row['assignment_id']),
                        ),
                      const Divider(),
                      Text(
                        _teacher ? 'Student progress' : 'Your progress',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const Text(
                        'Average percentage across released assignments; unreleased work is excluded.',
                      ),
                      for (final row in _data!['progress'] as List)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${row['student_id']} • ${row['released']} released assignments • ${(row['average_percent'] as num).toStringAsFixed(1)}%',
                              ),
                              const SizedBox(height: 6),
                              LinearProgressIndicator(
                                value: ((row['average_percent'] as num) / 100)
                                    .clamp(0, 1)
                                    .toDouble(),
                              ),
                            ],
                          ),
                        ),
                      if (_teacher) ...[
                        const Divider(),
                        Text(
                          'Question performance',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        Text('${_data!['question_analytics_scope']}'),
                        if ((_data!['question_performance'] as List).isEmpty)
                          const Text(
                            'No current released manual question reviews yet. Existing total-only grades cannot provide question analytics.',
                          ),
                        for (final row
                            in _data!['question_performance'] as List)
                          ListTile(
                            title: Text(
                              '${row['question_id']} • ${row['prompt']}',
                            ),
                            subtitle: Text(
                              '${row['samples']} released reviews • Average ${(row['average'] as num).toStringAsFixed(2)} / ${row['max_marks']}',
                            ),
                          ),
                      ],
                    ],
                    if (widget.mode != 'notifications')
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          TextButton(
                            onPressed: _offset == 0
                                ? null
                                : () {
                                    _offset -= 25;
                                    _load();
                                  },
                            child: const Text('Previous page'),
                          ),
                          Text('Page ${_offset ~/ 25 + 1}'),
                          TextButton(
                            onPressed:
                                _offset + 25 <
                                        (_data!['total_assignments'] as int) ||
                                    _offset + 25 <
                                        (_data!['total_performance_assignments']
                                            as int) ||
                                    _offset + 25 <
                                        (_data!['total_progress_students']
                                            as int)
                                ? () {
                                    _offset += 25;
                                    _load();
                                  }
                                : null,
                            child: const Text('Next page'),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ),
          ),
  );
}

class AcademicProfile extends StatelessWidget {
  const AcademicProfile({super.key});
  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircleAvatar(
                radius: 32,
                child: Icon(Icons.person, size: 32),
              ),
              const SizedBox(height: 16),
              Text(
                user?.name ?? 'Signed-in account',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text(user?.email ?? 'Account details unavailable'),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () =>
                    context.read<AuthProvider>().logout(context: context),
                icon: const Icon(Icons.logout),
                label: const Text('Sign out'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
