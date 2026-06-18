"""Domain-specific exceptions for the weatheryear module."""


class WeatherYearError(Exception):
    """Base exception for weather-year preprocessing and conversion errors."""


class MissingRequiredColumnsError(WeatherYearError):
    """Raised when required columns are missing from an input table."""


class MalformedTechnologyFolderError(WeatherYearError):
    """Raised when a technology folder name does not match expected patterns."""


class EmptyMergeResultError(WeatherYearError):
    """Raised when a merge/combine operation produces an empty output."""
