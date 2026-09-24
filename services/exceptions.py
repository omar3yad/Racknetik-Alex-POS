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

# Phase 4 — Subscription Exceptions
class PlanNotFoundError(Exception):
    def __init__(self, message: str = "Subscription plan not found"):
        self.message = message
        super().__init__(message)

class PlanNotActiveError(Exception):
    def __init__(self, message: str = "Subscription plan is not active"):
        self.message = message
        super().__init__(message)

class PlanLabelAlreadyExistsError(Exception):
    def __init__(self, message: str = "Subscription plan label already exists"):
        self.message = message
        super().__init__(message)

class SubscriberNotFoundError(Exception):
    def __init__(self, message: str = "Subscriber not found"):
        self.message = message
        super().__init__(message)

class SubscriberPlateAlreadyExistsError(Exception):
    def __init__(self, message: str = "Subscriber with this plate number already exists"):
        self.message = message
        super().__init__(message)

class SubscriptionNotFoundError(Exception):
    def __init__(self, message: str = "Subscription not found"):
        self.message = message
        super().__init__(message)

class SubscriptionNotActiveError(Exception):
    def __init__(self, message: str = "Subscription is not active"):
        self.message = message
        super().__init__(message)

class SubscriberAlreadyHasActiveSubscriptionError(Exception):
    def __init__(self, message: str = "Subscriber already has an active or pending subscription"):
        self.message = message
        super().__init__(message)

class SubscriptionDailyLimitReachedError(Exception):
    def __init__(self, message: str = "Daily entry limit reached for this subscription"):
        self.message = message
        super().__init__(message)

class ShiftAlreadyClosedError(Exception):
    def __init__(self, message: str = "Shift is already closed"):
        self.message = message
        super().__init__(message)

class PricingRuleNotFoundError(Exception):
    def __init__(self, message: str = "Pricing rule not found"):
        self.message = message
        super().__init__(message)

class RateLabelAlreadyExistsError(Exception):
    def __init__(self, message: str = "Pricing rule label already exists"):
        self.message = message
        super().__init__(message)

class InvalidDateRangeError(Exception):
    def __init__(self, message: str = "Invalid date range: start_date must be <= end_date"):
        self.message = message
        super().__init__(message)

class InvalidReportTypeError(Exception):
    def __init__(self, message: str = "Invalid report type"):
        self.message = message
        super().__init__(message)

class ShiftIdRequiredForPrintError(Exception):
    def __init__(self, message: str = "shift_id is required for shift print view"):
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
    "PlanNotFoundError",
    "PlanNotActiveError",
    "PlanLabelAlreadyExistsError",
    "SubscriberNotFoundError",
    "SubscriberPlateAlreadyExistsError",
    "SubscriptionNotFoundError",
    "SubscriptionNotActiveError",
    "SubscriberAlreadyHasActiveSubscriptionError",
    "SubscriptionDailyLimitReachedError",
    "ShiftAlreadyClosedError",
    "PricingRuleNotFoundError",
    "RateLabelAlreadyExistsError",
    "InvalidDateRangeError",
    "InvalidReportTypeError",
    "ShiftIdRequiredForPrintError",
]
