# src/batch_processing/exceptions.py

class BatchProcessingError(Exception):
    """Base exception for batch processing errors"""
    pass

class SessionCreationError(BatchProcessingError):
    """Raised when there's an error creating a new session"""
    pass

class FileProcessingError(BatchProcessingError):
    """Raised when there's an error processing a specific file"""
    pass

class TimestampError(BatchProcessingError):
    """Raised when there's an error handling timestamps"""
    pass