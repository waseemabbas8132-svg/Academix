class FileUtils {
  const FileUtils._();

  static String getFileExtension(String fileName) {
    final dotIndex = fileName.lastIndexOf('.');
    if (dotIndex == -1 || dotIndex == fileName.length - 1) {
      return '';
    }
    return fileName.substring(dotIndex + 1).toLowerCase();
  }

  static bool isSupportedSubmission(String fileName) {
    final extension = getFileExtension(fileName);
    return const {'pdf', 'png', 'jpg', 'jpeg'}.contains(extension);
  }
}
