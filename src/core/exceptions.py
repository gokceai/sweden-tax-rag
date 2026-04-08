class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ConfigurationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class InfrastructureError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=503)


class DataIntegrityError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=500)

