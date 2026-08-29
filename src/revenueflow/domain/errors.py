class DomainError(Exception):
    """Base for every RevenueFlow domain error."""


class IngestError(DomainError):
    """Raised when an inbound event cannot be normalized or accepted."""


class LLMError(DomainError):
    """Raised when a model call fails or returns an unusable result."""


class ToolError(DomainError):
    """Raised when an agent tool cannot fulfill its contract."""


class ChannelError(DomainError):
    """Raised when a channel adapter cannot deliver or parse a message."""
