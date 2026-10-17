class FriendlyError(Exception):
    """A problem the person using the app can understand: what happened, and what to do next."""

    def __init__(self, title, detail, fix, kind="error"):
        super().__init__(title)
        self.title = title
        self.detail = detail
        self.fix = fix
        self.kind = kind  # "error" stops the run; "warn" is a softer stop (limits, nothing broken)
