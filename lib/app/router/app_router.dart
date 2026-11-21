import 'package:academix/app/router/route_names.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/authentication/presentation/screens/login_screen.dart';
import 'package:academix/features/dashboard/presentation/screens/dashboard_screen.dart';
import 'package:academix/features/students/presentation/screens/student_dashboard_screen.dart';
import 'package:academix/features/teachers/presentation/screens/teacher_dashboard_screen.dart';
import 'package:academix/shared/enums/user_role.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: RouteNames.login,
  redirect: (context, state) {
    final authProvider = context.read<AuthProvider>();
    final isLoginRoute = state.matchedLocation == RouteNames.login;

    if (!authProvider.isAuthenticated && !isLoginRoute) {
      return RouteNames.login;
    }

    if (authProvider.isAuthenticated) {
      final dashboard = switch (authProvider.currentUser?.role) {
        UserRole.teacher => RouteNames.teacherDashboard,
        UserRole.student => RouteNames.studentDashboard,
        UserRole.admin => RouteNames.dashboard,
        null => RouteNames.login,
      };
      if (state.matchedLocation != dashboard) return dashboard;
    }

    return null;
  },
  routes: <RouteBase>[
    GoRoute(
      path: RouteNames.splash,
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: RouteNames.login,
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: RouteNames.dashboard,
      builder: (context, state) => const DashboardScreen(),
    ),
    GoRoute(
      path: RouteNames.teacherDashboard,
      builder: (context, state) => const TeacherDashboardScreen(),
    ),
    GoRoute(
      path: RouteNames.studentDashboard,
      builder: (context, state) => const StudentDashboardScreen(),
    ),
  ],
);
