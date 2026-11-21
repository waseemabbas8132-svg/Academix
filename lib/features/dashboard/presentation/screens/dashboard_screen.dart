import 'package:academix/core/theme/app_colors.dart';
import 'package:academix/core/theme/app_text_styles.dart';
import 'package:flutter/material.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final modules = [
      _DashboardCard(
        title: 'Classrooms',
        subtitle: 'Manage live class cohorts and attendance.',
        icon: Icons.class_rounded,
        color: AppColors.primary,
      ),
      _DashboardCard(
        title: 'Assignments',
        subtitle: 'Create rubrics, deadlines, and AI review flows.',
        icon: Icons.assignment_rounded,
        color: AppColors.warning,
      ),
      _DashboardCard(
        title: 'Submissions',
        subtitle: 'Track OCR, approval, and grading confidence.',
        icon: Icons.upload_file_rounded,
        color: AppColors.success,
      ),
      _DashboardCard(
        title: 'Analytics',
        subtitle: 'Review classroom performance reports and trends.',
        icon: Icons.analytics_rounded,
        color: AppColors.accent,
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Academix Dashboard'),
        actions: [
          IconButton(
            onPressed: () {},
            icon: const Icon(Icons.notifications_none_rounded),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Overview', style: AppTextStyles.heading2),
              const SizedBox(height: 8),
              const Text(
                'Operational snapshot across teaching, submissions, and AI-assisted evaluation.',
                style: AppTextStyles.bodySmall,
              ),
              const SizedBox(height: 20),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 16,
                  childAspectRatio: 1.15,
                ),
                itemCount: modules.length,
                itemBuilder: (context, index) => modules[index],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  const _DashboardCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.card,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () {},
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color),
              ),
              const SizedBox(height: 16),
              Text(title, style: AppTextStyles.title),
              const SizedBox(height: 8),
              Text(subtitle, style: AppTextStyles.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}
