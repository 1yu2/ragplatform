class AppError(Exception):
    def __init__(self, message: str, code: int = 1000):
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(AppError):
    def __init__(self, message: str = "resource not found"):
        super().__init__(message=message, code=1004)


class ValidationError(AppError):
    def __init__(self, message: str = "validation failed"):
        super().__init__(message=message, code=1001)
