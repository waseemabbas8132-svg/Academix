import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/theme/app_colors.dart';
import 'package:academix/core/widgets/app_empty_state.dart';
import 'package:academix/core/widgets/app_error_widget.dart';
import 'package:academix/core/widgets/app_loader.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_form_screen.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_list_screen.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/classes/data/models/announcement.dart';
import 'package:academix/features/classes/data/models/classroom_summary.dart';
import 'package:academix/features/classes/data/repositories/class_stream_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

class ClassStreamScreen extends StatefulWidget {
  const ClassStreamScreen({
    super.key,
    required this.classroom,
    required this.isTeacher,
    required this.repository,
    this.assignmentRepository,
  });

  final ClassroomSummary classroom;
  final bool isTeacher;
  final ClassStreamRepository repository;
  final AssignmentRepository? assignmentRepository;

  @override
  State<ClassStreamScreen> createState() => _ClassStreamScreenState();
}

class _ClassStreamScreenState extends State<ClassStreamScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  int _selectedTabIndex = 0;
  bool _isLoading = true;
  String? _errorMessage;
  List<Announcement> _announcements = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this)
      ..addListener(_handleTabChange);
    _loadAnnouncements();
  }

  @override
  void dispose() {
    _tabController
      ..removeListener(_handleTabChange)
      ..dispose();
    super.dispose();
  }

  void _handleTabChange() {
    if (_tabController.index != _selectedTabIndex &&
        !_tabController.indexIsChanging) {
      setState(() => _selectedTabIndex = _tabController.index);
    }
  }

  String? get _token => context.read<AuthProvider>().token;

  Future<void> _loadAnnouncements() async {
    final token = _token;
    if (token == null || token.isEmpty) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Please sign in again to view this class stream.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final announcements = await widget.repository.listAnnouncements(
        token: token,
        classId: widget.classroom.id,
      );
      if (!mounted) return;
      setState(() {
        _announcements = announcements;
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
        _errorMessage = 'Unable to load announcements. Please try again.';
        _isLoading = false;
      });
    }
  }

  Future<void> _composeAnnouncement({Announcement? existing}) async {
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _AnnouncementEditorDialog(announcement: existing),
    );
    if (result == null) return;

    final token = _token;
    if (token == null) return;
    try {
      if (existing == null) {
        await widget.repository.createAnnouncement(
          token: token,
          classId: widget.classroom.id,
          title: result['title']!,
          content: result['content']!,
        );
      } else {
        await widget.repository.updateAnnouncement(
          token: token,
          announcementId: existing.id,
          title: result['title']!,
          content: result['content']!,
        );
      }
      if (!mounted) return;
      _showMessage(
        existing == null ? 'Announcement posted.' : 'Announcement updated.',
      );
      await _loadAnnouncements();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } catch (_) {
      if (mounted) _showMessage('Unable to save the announcement.');
    }
  }

  Future<void> _togglePin(Announcement announcement) async {
    final token = _token;
    if (token == null) return;
    try {
      await widget.repository.setPinned(
        token: token,
        announcementId: announcement.id,
        isPinned: !announcement.isPinned,
      );
      await _loadAnnouncements();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } catch (_) {
      if (mounted) _showMessage('Unable to update the pinned status.');
    }
  }

  Future<void> _deleteAnnouncement(Announcement announcement) async {
    final shouldDelete = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete announcement?'),
        content: const Text(
          'This announcement will be removed for everyone in the class.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (shouldDelete != true) return;

    final token = _token;
    if (token == null) return;
    try {
      await widget.repository.deleteAnnouncement(
        token: token,
        announcementId: announcement.id,
      );
      if (!mounted) return;
      _showMessage('Announcement deleted.');
      await _loadAnnouncements();
    } on ApiException catch (error) {
      if (mounted) _showMessage(error.message);
    } catch (_) {
      if (mounted) _showMessage('Unable to delete the announcement.');
    }
  }

  int _assignmentListVersion = 0;

  Future<void> _createAssignment() async {
    final saved = await Navigator.of(context).push<Object>(
      MaterialPageRoute<Object>(
        builder: (_) => AssignmentFormScreen(classId: widget.classroom.id),
      ),
    );
    if (mounted && saved != null) setState(() => _assignmentListVersion++);
  }

  void _openRoster() {
    final token = context.read<AuthProvider>().token;
    if (token == null || token.isEmpty) return;
    Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => _ClassRosterScreen(
          classroom: widget.classroom,
          load: () => HttpClassStreamRepository().listStudents(
            token,
            widget.classroom.id,
          ),
        ),
      ),
    );
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
        title: Text(widget.classroom.name),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Stream', icon: Icon(Icons.dynamic_feed_outlined)),
            Tab(text: 'Assignments', icon: Icon(Icons.assignment_outlined)),
            Tab(text: 'About', icon: Icon(Icons.info_outline_rounded)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildStream(),
          ClassAssignmentsTab(
            key: ValueKey(_assignmentListVersion),
            classroom: widget.classroom,
            isTeacher: widget.isTeacher,
            repository: widget.assignmentRepository,
            enabled: _selectedTabIndex == 1,
          ),
          _ClassAboutTab(
            classroom: widget.classroom,
            onOpenRoster: widget.isTeacher ? _openRoster : null,
          ),
        ],
      ),
      floatingActionButton: widget.isTeacher && _selectedTabIndex == 0
          ? FloatingActionButton.extended(
              onPressed: _composeAnnouncement,
              icon: const Icon(Icons.add),
              label: const Text('Announcement'),
            )
          : widget.isTeacher && _selectedTabIndex == 1
          ? FloatingActionButton.extended(
              onPressed: _createAssignment,
              icon: const Icon(Icons.add),
              label: const Text('Assignment'),
            )
          : null,
    );
  }

  Widget _buildStream() {
    if (_isLoading) return const AppLoader(message: 'Loading stream...');
    if (_errorMessage != null) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          const SizedBox(height: 120),
          AppErrorWidget(message: _errorMessage!),
          Center(
            child: OutlinedButton(
              onPressed: _loadAnnouncements,
              child: const Text('Try again'),
            ),
          ),
        ],
      );
    }
    if (_announcements.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadAnnouncements,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: const [
            SizedBox(height: 120),
            AppEmptyState(
              title: 'No announcements yet',
              message: 'Class updates will appear here.',
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadAnnouncements,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        itemCount: _announcements.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (context, index) => _AnnouncementCard(
          announcement: _announcements[index],
          canManage: widget.isTeacher,
          onEdit: () => _composeAnnouncement(existing: _announcements[index]),
          onDelete: () => _deleteAnnouncement(_announcements[index]),
          onPin: () => _togglePin(_announcements[index]),
        ),
      ),
    );
  }
}

class _AnnouncementCard extends StatelessWidget {
  const _AnnouncementCard({
    required this.announcement,
    required this.canManage,
    required this.onEdit,
    required this.onDelete,
    required this.onPin,
  });

  final Announcement announcement;
  final bool canManage;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onPin;

  @override
  Widget build(BuildContext context) {
    final postedAt = DateFormat.yMMMd().add_jm().format(announcement.createdAt);
    return Card(
      color: announcement.isPinned
          ? AppColors.primary.withValues(alpha: 0.06)
          : AppColors.card,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (announcement.isPinned) ...[
                        Row(
                          children: [
                            const Icon(
                              Icons.push_pin_rounded,
                              size: 16,
                              color: AppColors.primary,
                            ),
                            const SizedBox(width: 5),
                            Text(
                              'Pinned',
                              style: Theme.of(context).textTheme.labelMedium
                                  ?.copyWith(
                                    color: AppColors.primary,
                                    fontWeight: FontWeight.w700,
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                      ],
                      Text(
                        announcement.title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ],
                  ),
                ),
                if (canManage)
                  PopupMenuButton<String>(
                    tooltip: 'Announcement actions',
                    onSelected: (action) {
                      switch (action) {
                        case 'edit':
                          onEdit();
                        case 'pin':
                          onPin();
                        case 'delete':
                          onDelete();
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(value: 'edit', child: Text('Edit')),
                      PopupMenuItem(
                        value: 'pin',
                        child: Text(announcement.isPinned ? 'Unpin' : 'Pin'),
                      ),
                      const PopupMenuItem(
                        value: 'delete',
                        child: Text('Delete'),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Text(announcement.content),
            const SizedBox(height: 16),
            Row(
              children: [
                const Icon(
                  Icons.person_outline_rounded,
                  size: 16,
                  color: AppColors.textSecondary,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    announcement.teacherId,
                    style: Theme.of(context).textTheme.bodySmall,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(postedAt, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ClassAboutTab extends StatelessWidget {
  const _ClassAboutTab({required this.classroom, this.onOpenRoster});

  final ClassroomSummary classroom;
  final VoidCallback? onOpenRoster;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(classroom.subject, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text('Section ${classroom.section}'),
        if (onOpenRoster != null) ...[
          if (classroom.classCode case final code?)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Class code'),
              subtitle: SelectableText(code),
              trailing: IconButton(
                tooltip: 'Copy class code',
                icon: const Icon(Icons.copy_outlined),
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: code));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Class code copied.')),
                    );
                  }
                },
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              onPressed: onOpenRoster,
              icon: const Icon(Icons.people_outline),
              label: const Text('Enrolled students'),
            ),
          ),
        ],
        if (classroom.room != null && classroom.room!.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text('Room ${classroom.room}'),
        ],
        if (classroom.teacherId != null) ...[
          const SizedBox(height: 8),
          Text('Teacher ${classroom.teacherId}'),
        ],
        if (classroom.description != null &&
            classroom.description!.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(classroom.description!),
        ],
      ],
    );
  }
}

class _ClassRosterScreen extends StatefulWidget {
  const _ClassRosterScreen({required this.classroom, required this.load});

  final ClassroomSummary classroom;
  final Future<List<({String name, String email})>> Function() load;

  @override
  State<_ClassRosterScreen> createState() => _ClassRosterScreenState();
}

class _ClassRosterScreenState extends State<_ClassRosterScreen> {
  late var _students = widget.load();

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Enrolled students')),
    body: FutureBuilder<List<({String name, String email})>>(
      future: _students,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const AppLoader(message: 'Loading students…');
        }
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const AppErrorWidget(
                  message: 'Unable to load enrolled students.',
                ),
                OutlinedButton(
                  onPressed: () => setState(() => _students = widget.load()),
                  child: const Text('Try again'),
                ),
              ],
            ),
          );
        }
        final students = snapshot.data!;
        if (students.isEmpty) {
          return const Center(
            child: AppEmptyState(
              title: 'No students yet',
              message: 'Share the class code to invite students.',
            ),
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            ListTile(title: Text(widget.classroom.name)),
            for (final student in students)
              ListTile(
                leading: const Icon(Icons.person_outline),
                title: Text(student.name),
                subtitle: Text(student.email),
              ),
          ],
        );
      },
    ),
  );
}

class _AnnouncementEditorDialog extends StatefulWidget {
  const _AnnouncementEditorDialog({this.announcement});

  final Announcement? announcement;

  @override
  State<_AnnouncementEditorDialog> createState() =>
      _AnnouncementEditorDialogState();
}

class _AnnouncementEditorDialogState extends State<_AnnouncementEditorDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _titleController = TextEditingController(
    text: widget.announcement?.title ?? '',
  );
  late final TextEditingController _contentController = TextEditingController(
    text: widget.announcement?.content ?? '',
  );

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
        widget.announcement == null
            ? 'Create announcement'
            : 'Edit announcement',
      ),
      content: Form(
        key: _formKey,
        child: SizedBox(
          width: 420,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: _titleController,
                  maxLength: 200,
                  decoration: const InputDecoration(labelText: 'Title'),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? 'Enter a title.'
                      : null,
                ),
                TextFormField(
                  controller: _contentController,
                  minLines: 3,
                  maxLines: 6,
                  maxLength: 10000,
                  decoration: const InputDecoration(labelText: 'Message'),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? 'Enter a message.'
                      : null,
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            if (!_formKey.currentState!.validate()) return;
            Navigator.pop(context, {
              'title': _titleController.text.trim(),
              'content': _contentController.text.trim(),
            });
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
