import 'package:academix/shared/enums/user_role.dart';

class User {
  const User({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
    this.department,
    this.token,
  });

  final String id;
  final String name;
  final String email;
  final UserRole role;
  final String? department;
  final String? token;

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'email': email,
        'role': role.name,
        'department': department,
        'token': token,
      };

  factory User.fromJson(Map<String, dynamic> json) {
    final roleValue = json['role']?.toString() ?? 'student';
    final parsedRole = UserRole.values.firstWhere(
      (role) => role.name == roleValue,
      orElse: () => UserRole.student,
    );

    return User(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      role: parsedRole,
      department: json['department']?.toString(),
      token: json['token']?.toString(),
    );
  }
}
