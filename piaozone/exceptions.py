class PiaozoneError(Exception):
    """SDK errors never include credentials, URLs or raw vendor responses."""


class AuthenticationError(PiaozoneError):
    pass


class ProtocolError(PiaozoneError):
    pass


class TransportError(PiaozoneError):
    """The outcome may be unknown. Query the original serial number; do not reissue."""
