class CardNotFoundError(Exception):
    def __init__(self, message: str = "Card not found"):
        self.message = message
        super().__init__(message)

class CardNotAvailableError(Exception):
    def __init__(self, message: str = "Card not available"):
        self.message = message
        super().__init__(message)

class CardAlreadyActiveError(Exception):
    def __init__(self, message: str = "Card already active"):
        self.message = message
        super().__init__(message)

class CardHasNoActiveSessionError(Exception):
    def __init__(self, message: str = "Card has no active session"):
        self.message = message
        super().__init__(message)

class InvalidBarcodeFormatError(Exception):
    def __init__(self, message: str = "Invalid barcode format"):
        self.message = message
        super().__init__(message)

class BulkCardConflictError(Exception):
    def __init__(self, conflicting_codes: list[str], message: str = "Bulk card creation conflicts"):
        self.conflicting_codes = conflicting_codes
        self.message = message
        super().__init__(message)

class SessionNotActiveError(Exception):
    def __init__(self, message: str = "Session is not active"):
        self.message = message
        super().__init__(message)

class SessionNotFoundError(Exception):
    def __init__(self, message: str = "Session not found"):
        self.message = message
        super().__init__(message)

class ShiftAlreadyOpenError(Exception):
    def __init__(self, message: str = "Shift is already open"):
        self.message = message
        super().__init__(message)

class NoActiveShiftError(Exception):
    def __init__(self, message: str = "No active shift"):
        self.message = message
        super().__init__(message)

class ShiftNotFoundError(Exception):
    def __init__(self, message: str = "Shift not found"):
        self.message = message
        super().__init__(message)

class ShiftNotOwnedError(Exception):
    def __init__(self, message: str = "Shift not owned by this operator"):
        self.message = message
        super().__init__(message)

class NoPricingRuleError(Exception):
    def __init__(self, message: str = "No active pricing rule found"):
        self.message = message
        super().__init__(message)

__all__ = [
    "CardNotFoundError",
    "CardNotAvailableError",
    "CardAlreadyActiveError",
    "CardHasNoActiveSessionError",
    "InvalidBarcodeFormatError",
    "BulkCardConflictError",
    "SessionNotActiveError",
    "SessionNotFoundError",
    "ShiftAlreadyOpenError",
    "NoActiveShiftError",
    "ShiftNotFoundError",
    "ShiftNotOwnedError",
    "NoPricingRuleError",
]
