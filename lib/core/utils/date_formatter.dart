import 'package:intl/intl.dart';

class AcademixDateFormatter {
  const AcademixDateFormatter._();

  static String formatDate(DateTime dateTime) => DateFormat.yMMMMd().format(dateTime);

  static String formatShortDate(DateTime dateTime) => DateFormat.MMMd().format(dateTime);

  static String formatRelative(DateTime dateTime) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inDays > 0) {
      return '${difference.inDays}d ago';
    }
    if (difference.inHours > 0) {
      return '${difference.inHours}h ago';
    }
    if (difference.inMinutes > 0) {
      return '${difference.inMinutes}m ago';
    }
    return 'Just now';
  }
}
