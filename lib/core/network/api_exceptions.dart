class ApiException implements Exception {
  const ApiException({required this.message, this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() =>
      'ApiException(statusCode: $statusCode, message: $message)';
}

class UnauthorizedException extends ApiException {
  const UnauthorizedException({super.statusCode = 401, required super.message});
}

class ForbiddenException extends ApiException {
  const ForbiddenException({super.statusCode = 403, required super.message});
}

class NotFoundException extends ApiException {
  const NotFoundException({super.statusCode = 404, required super.message});
}

class ConflictException extends ApiException {
  const ConflictException({super.statusCode = 409, required super.message});
}

class ValidationException extends ApiException {
  const ValidationException({
    required super.statusCode,
    required super.message,
  });
}

class NetworkException extends ApiException {
  const NetworkException({super.statusCode, required super.message});
}

class ServerException extends ApiException {
  const ServerException({super.statusCode = 500, required super.message});
}
