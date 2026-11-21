import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/theme/app_colors.dart';
import 'package:academix/core/widgets/app_empty_state.dart';
import 'package:academix/core/widgets/app_error_widget.dart';
import 'package:academix/core/widgets/app_loader.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_details_screen.dart';
import 'package:academix/features/assignments/presentation/screens/submission_screens.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/classes/data/models/classroom_summary.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class ClassAssignmentsTab extends StatefulWidget {
  const ClassAssignmentsTab({
    super.key,
    required this.classroom,
    required this.isTeacher,
    this.repository,
    this.enabled = true,
  });

  final ClassroomSummary classroom;
  final bool isTeacher;
  final AssignmentRepository? repository;
  final bool enabled;

  @override
  State<ClassAssignmentsTab> createState() => _ClassAssignmentsTabState();
}

class _ClassAssignmentsTabState extends State<ClassAssignmentsTab> {
  late final AssignmentRepository _repository =
      widget.repository ?? HttpAssignmentRepository();
  bool _isLoading = true;
  String? _errorMessage;
  List<Assignment> _assignments = [];

  @override
  void initState() {
    super.initState();
    if (widget.enabled) _load();
  }

  @override
  void didUpdateWidget(covariant ClassAssignmentsTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!oldWidget.enabled && widget.enabled) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _load();
      });
    }
  }

  Future<void> _load() async {
    final token = context.read<AuthProvider>().token;
    if (token == null) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Please sign in again to view assignments.';
      });
      return;
    }
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final assignments = await _repository.listClassAssignments(
        token,
        widget.classroom.id,
      );
      if (!mounted) return;
      setState(() {
        _assignments = assignments;
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
        _errorMessage = 'Unable to load assignments.';
        _isLoading = false;
      });
    }
  }

  Future<void> _openAssignment(Assignment assignment) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => AssignmentDetailsScreen(
          assignment: assignment,
          isTeacher: widget.isTeacher,
          repository: _repository,
        ),
      ),
    );
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled && _assignments.isEmpty) {
      return const SizedBox.shrink();
    }
    if (_isLoading) return const AppLoader(message: 'Loading assignments...');
    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AppErrorWidget(message: _errorMessage!),
              OutlinedButton(onPressed: _load, child: const Text('Try again')),
            ],
          ),
        ),
      );
    }
    if (_assignments.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: const [
            SizedBox(height: 120),
            AppEmptyState(
              title: 'No assignments yet',
              message: 'New class assignments will appear here.',
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        itemCount: _assignments.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (context, index) => _AssignmentCard(
          assignment: _assignments[index],
          isTeacher: widget.isTeacher,
          onTap: () => _openAssignment(_assignments[index]),
        ),
      ),
    );
  }
}

class StudentAssignmentsScreen extends StatefulWidget {
  const StudentAssignmentsScreen({super.key, this.repository});

  final AssignmentRepository? repository;

  @override
  State<StudentAssignmentsScreen> createState() =>
      _StudentAssignmentsScreenState();
}

class _StudentAssignmentsScreenState extends State<StudentAssignmentsScreen> {
  late final AssignmentRepository _repository =
      widget.repository ?? HttpAssignmentRepository();
  bool _isLoading = true;
  String? _errorMessage;
  List<Assignment> _assignments = [];
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
        _errorMessage = 'Please sign in again to view assignments.';
      });
      return;
    }
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final results = await Future.wait([
        _repository.listStudentAssignments(token),
        _repository.listMySubmissions(token),
      ]);
      if (!mounted) return;
      setState(() {
        _assignments = results[0] as List<Assignment>;
        _submissions = results[1] as List<Submission>;
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
        _errorMessage = 'Unable to load your assignments.';
        _isLoading = false;
      });
    }
  }

  Future<void> _openAssignment(Assignment assignment) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => AssignmentDetailsScreen(
          assignment: assignment,
          isTeacher: false,
          repository: _repository,
        ),
      ),
    );
    if (mounted) _load();
  }

  Future<void> _openSubmissions() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => MySubmissionsScreen(repository: _repository),
      ),
    );
    if (mounted) _load();
  }

  String _groupFor(Assignment assignment) {
    final submission = _submissionFor(assignment);
    if (submission != null) {
      if (submission.status == 'graded') return 'Graded';
      if (submission.status == 'returned') return 'Returned';
      if (submission.status == 'submitted') {
        return submission.isLate ? 'Submitted late' : 'Submitted';
      }
    }
    return switch (assignment.deadlineStatus) {
      'overdue' => 'Overdue',
      'due_today' => 'Due today',
      'upcoming' => 'Upcoming',
      _ => 'Pending',
    };
  }

  Submission? _submissionFor(Assignment assignment) {
    for (final submission in _submissions) {
      if (submission.assignmentId == assignment.id) return submission;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Assignments'),
        actions: [
          IconButton(
            tooltip: 'My submissions',
            onPressed: _openSubmissions,
            icon: const Icon(Icons.assignment_turned_in_outlined),
          ),
        ],
      ),
      body: _isLoading
          ? const AppLoader(message: 'Loading your work...')
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
              child: _assignments.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: const [
                        SizedBox(height: 160),
                        AppEmptyState(
                          title: 'No assignments yet',
                          message:
                              'Published class assignments will show here.',
                        ),
                      ],
                    )
                  : ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(16),
                      children: [
                        for (final group in const [
                          'Overdue',
                          'Due today',
                          'Upcoming',
                          'Pending',
                          'Submitted late',
                          'Submitted',
                          'Returned',
                          'Graded',
                        ])
                          ..._groupedAssignments(group),
                      ],
                    ),
            ),
    );
  }

  List<Widget> _groupedAssignments(String group) {
    final assignments = _assignments
        .where((assignment) => _groupFor(assignment) == group)
        .toList();
    if (assignments.isEmpty) return [];
    return [
      Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 8),
        child: Text(group, style: Theme.of(context).textTheme.titleMedium),
      ),
      for (final assignment in assignments)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: _AssignmentCard(
            assignment: assignment,
            isTeacher: false,
            statusLabel: group,
            onTap: () => _openAssignment(assignment),
          ),
        ),
    ];
  }
}

class _AssignmentCard extends StatelessWidget {
  const _AssignmentCard({
    required this.assignment,
    required this.isTeacher,
    required this.onTap,
    this.statusLabel,
  });

  final Assignment assignment;
  final bool isTeacher;
  final String? statusLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final dueText = DateFormat.yMMMd().add_jm().format(assignment.dueDate);
    return Card(
      color: AppColors.card,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.assignment_outlined,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      assignment.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  if (statusLabel != null)
                    Chip(
                      label: Text(statusLabel!),
                      visualDensity: VisualDensity.compact,
                    )
                  else
                    Chip(
                      label: Text(
                        assignment.isPublished ? 'Published' : 'Draft',
                      ),
                      visualDensity: VisualDensity.compact,
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Text('Due $dueText · ${assignment.totalMarks} points'),
              if (isTeacher) ...[
                const SizedBox(height: 8),
                Text(
                  '${assignment.submittedCount} submitted · '
                  '${assignment.pendingCount} pending · '
                  '${assignment.gradedCount} graded',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
              const Align(
                alignment: Alignment.centerRight,
                child: Icon(Icons.chevron_right_rounded),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
