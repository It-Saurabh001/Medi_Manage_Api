from flask import Blueprint


class ApiBlueprint(Blueprint):
    """Blueprint mounted under config `API_PREFIX` with `strict_slashes=False` on every rule.

    The prefix is applied at registration time, so `app.register_blueprint(bp)` with no
    url_prefix is enough (keeps app/routes/__init__.py append-only).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Must be the first deferred function so every rule sees the prefix.
        self.record(self._apply_api_prefix)

    @staticmethod
    def _apply_api_prefix(state):
        prefix = (state.app.config.get("API_PREFIX") or "").rstrip("/")
        extra = state.url_prefix or ""
        state.url_prefix = f"{prefix}{extra}" or None

    def add_url_rule(self, rule, endpoint=None, view_func=None, provide_automatic_options=None, **options):
        options.setdefault("strict_slashes", False)
        return super().add_url_rule(rule, endpoint, view_func, provide_automatic_options, **options)
