class EpisodeFlowError(Exception):
    """Stable failure from the adaptive-episode use cases."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
