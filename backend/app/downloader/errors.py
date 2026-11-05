class DownloaderError(Exception):
    """Base error for all downloader engines."""


class InvalidUrlError(DownloaderError):
    """The supplied URL is not a supported Instagram URL."""


class EngineUnavailableError(DownloaderError):
    """The upstream engine is temporarily unavailable."""


class RateLimitedError(EngineUnavailableError):
    """The upstream engine asked us to slow down."""


class ContentNotFoundError(DownloaderError):
    """The post does not exist, is private, or is otherwise inaccessible."""


class ProtocolError(DownloaderError):
    """The upstream engine returned an unexpected payload."""


class DownloadTimeoutError(EngineUnavailableError):
    """The upstream engine did not answer in time."""
