import 'package:academix/core/theme/app_colors.dart';
import 'package:academix/core/theme/app_dimensions.dart';
import 'package:academix/core/theme/app_text_styles.dart';
import 'package:academix/core/utils/validators.dart';
import 'package:academix/core/widgets/app_button.dart';
import 'package:academix/core/widgets/app_text_field.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController(text: 'teacher@academix.app');
  final _passwordController = TextEditingController(text: 'password123');

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppDimensions.pagePadding),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                elevation: 0,
                color: AppColors.card,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppDimensions.cardRadius),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 54,
                          height: 54,
                          decoration: BoxDecoration(
                            color: AppColors.primary.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: const Icon(
                            Icons.school_rounded,
                            color: AppColors.primary,
                            size: 28,
                          ),
                        ),
                        const SizedBox(height: 20),
                        const Text(
                          'Welcome back',
                          style: AppTextStyles.heading2,
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Sign in to manage classrooms, submissions, and AI-assisted grading.',
                          style: AppTextStyles.bodySmall,
                        ),
                        const SizedBox(height: 28),
                        AppTextField(
                          controller: _emailController,
                          label: 'Email',
                          hintText: 'user@academix.app',
                          prefixIcon: Icons.email_outlined,
                          keyboardType: TextInputType.emailAddress,
                          validator: Validators.email,
                        ),
                        const SizedBox(height: 18),
                        AppTextField(
                          controller: _passwordController,
                          label: 'Password',
                          hintText: 'Enter password',
                          prefixIcon: Icons.lock_outline,
                          obscureText: true,
                          validator: (value) => Validators.password(value),
                        ),
                        const SizedBox(height: 24),
                        if (authProvider.errorMessage != null) ...[
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppColors.danger.withValues(alpha: 0.08),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              authProvider.errorMessage!,
                              style: const TextStyle(color: AppColors.danger),
                            ),
                          ),
                          const SizedBox(height: 14),
                        ],
                        AppButton(
                          label: 'Sign In',
                          icon: Icons.login_rounded,
                          isLoading: authProvider.isLoading,
                          onPressed: () async {
                            if (_formKey.currentState?.validate() ?? false) {
                              await authProvider.login(
                                context: context,
                                email: _emailController.text.trim(),
                                password: _passwordController.text,
                              );
                            }
                          },
                        ),
                        const SizedBox(height: 18),
                        Wrap(
                          alignment: WrapAlignment.center,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            TextButton(
                              onPressed: authProvider.isLoading
                                  ? null
                                  : () {
                                      _emailController.text =
                                          'teacher@academix.app';
                                      _passwordController.text = 'password123';
                                    },
                              child: const Text('Teacher demo'),
                            ),
                            TextButton(
                              onPressed: authProvider.isLoading
                                  ? null
                                  : () {
                                      _emailController.text =
                                          'student@academix.app';
                                      _passwordController.text = 'password123';
                                    },
                              child: const Text('Student demo'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
