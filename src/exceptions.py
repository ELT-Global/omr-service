"""
Custom exception classes for the OMR project.
"""

class OMRError(Exception):
    """Base class for OMR-related errors."""
    pass

class ResourceNotFoundError(OMRError, FileNotFoundError):
    """Raised when a required file (template, marker, etc.) is missing."""
    pass

class ProcessingError(OMRError):
    """Raised when an error occurs during image processing."""
    pass

class TemplateError(OMRError):
    """Raised when there is an issue with the template configuration."""
    pass
