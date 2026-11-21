import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/theme/app_colors.dart';
import 'package:academix/core/widgets/app_empty_state.dart';
import 'package:academix/core/widgets/app_error_widget.dart';
import 'package:academix/core/widgets/app_loader.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/classes/data/models/classroom_summary.dart';
import 'package:academix/features/classes/data/repositories/class_stream_repository.dart';
import 'package:academix/features/classes/presentation/screens/class_stream_screen.dart';
import 'package:academix/shared/enums/user_role.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class ClassesScreen extends StatefulWidget {
  const ClassesScreen({super.key, this.repository});

  final ClassStreamRepository? repository;

  @override
  State<ClassesScreen> createState() => _ClassesScreenState();
}

class _ClassesScreenState extends State<ClassesScreen> {
  late final _classActions = HttpClassStreamRepository();
  late final ClassStreamRepository _repository =
      widget.repository ?? _classActions;
  bool _isLoading = true;
  String? _errorMessage;
  List<ClassroomSummary> _classes = [];

  @override
  void initState() {
    super.initState();
    _loadClasses();
  }

  Future<void> _loadClasses() async {
    final token = context.read<AuthProvider>().token;
    if (token == null || token.isEmpty) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Please sign in again to view your classes.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final classes = await _repository.listClasses(token: token);
      if (!mounted) return;
      setState(() {
        _classes = classes;
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
        _errorMessage = 'Unable to load classes. Please try again.';
        _isLoading = false;
      });
    }
  }

  Future<void> _manageClass(bool isTeacher) async {
    final token = context.read<AuthProvider>().token;
    if (token == null || token.isEmpty) return;
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => _ClassActionDialog(
        isTeacher: isTeacher,
        save: (fields) => isTeacher
            ? _classActions.createClass(token, fields)
            : _classActions.joinClass(token, fields['class_code']!),
      ),
    );
    if (!mounted || saved != true) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(isTeacher ? 'Class created.' : 'Class joined.')),
    );
    await _loadClasses();
  }

  @override
  Widget build(BuildContext context) {
    final role = context.watch<AuthProvider>().currentUser?.role;
    final isTeacher = role == UserRole.teacher;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Classes'),
        actions: [
          if (isTeacher || role == UserRole.student)
            TextButton.icon(
              onPressed: () => _manageClass(isTeacher),
              icon: Icon(isTeacher ? Icons.add : Icons.group_add_outlined),
              label: Text(isTeacher ? 'Create class' : 'Join class'),
            ),
        ],
      ),
      body: _isLoading
          ? const AppLoader(message: 'Loading classes...')
          : _errorMessage != null
          ? Column(
              children: [
                Expanded(child: AppErrorWidget(message: _errorMessage!)),
                Padding(
                  padding: const EdgeInsets.only(bottom: 24),
                  child: OutlinedButton(
                    onPressed: _loadClasses,
                    child: const Text('Try again'),
                  ),
                ),
              ],
            )
          : RefreshIndicator(
              onRefresh: _loadClasses,
              child: _classes.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        const SizedBox(height: 160),
                        AppEmptyState(
                          title: 'No classes yet',
                          message: isTeacher
                              ? 'Create a class to get started.'
                              : 'Join a class with the code from your teacher.',
                        ),
                      ],
                    )
                  : ListView.separated(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(16),
                      itemCount: _classes.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final classroom = _classes[index];
                        return _ClassCard(
                          classroom: classroom,
                          onTap: () {
                            Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => ClassStreamScreen(
                                  classroom: classroom,
                                  isTeacher: isTeacher,
                                  repository: _repository,
                                ),
                              ),
                            );
                          },
                        );
                      },
                    ),
            ),
    );
  }
}

class _ClassActionDialog extends StatefulWidget {
  const _ClassActionDialog({required this.isTeacher, required this.save});

  final bool isTeacher;
  final Future<void> Function(Map<String, String>) save;

  @override
  State<_ClassActionDialog> createState() => _ClassActionDialogState();
}

class _ClassActionDialogState extends State<_ClassActionDialog> {
  final _form = GlobalKey<FormState>();
  final _values = <String, String>{};
  bool _saving = false;
  String? _error;

  Future<void> _submit() async {
    final form = _form.currentState!;
    if (_saving || !form.validate()) return;
    form.save();
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.save(_values);
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to save. Please try again.');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _field(String key, String label, int length) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextFormField(
      enabled: !_saving,
      decoration: InputDecoration(labelText: label, counterText: ''),
      maxLength: length,
      validator: (value) =>
          (value ?? '').trim().isEmpty ? 'Enter ${label.toLowerCase()}.' : null,
      onSaved: (value) => _values[key] = value!.trim(),
    ),
  );

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      scrollable: true,
      title: Text(widget.isTeacher ? 'Create class' : 'Join class'),
      content: Form(
        key: _form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.isTeacher) ...[
              _field('name', 'Class name', 150),
              _field('section', 'Section', 100),
              _field('subject', 'Subject', 100),
            ] else
              _field('class_code', 'Class code', 12),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _submit,
          child: Text(
            _saving ? 'Saving…' : (widget.isTeacher ? 'Create' : 'Join'),
          ),
        ),
      ],
    ),
  );
}

class _ClassCard extends StatelessWidget {
  const _ClassCard({required this.classroom, required this.onTap});

  final ClassroomSummary classroom;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: AppColors.card,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.class_rounded,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      classroom.name,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${classroom.subject} · ${classroom.section}',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}
