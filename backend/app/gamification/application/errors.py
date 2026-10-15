class EpisodeFlowError(Exception):
    """Stable failure from the adaptive-episode use cases."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PlayError(Exception):
    """Stable failure from the pilot session API. ``status_code`` is HTTP-shaped."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)
