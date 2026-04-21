"""Deprecated — Procore HTTP client.

Rex OS no longer calls the Procore API directly. All reads go through
RexAppDbClient against the old rex-procore Railway DB. If anything
instantiates this class, it's a stale import — fix the call site.
"""


class ProcoreClient:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "ProcoreClient is deprecated. Use RexAppDbClient via "
            "app.services.connectors.procore.rex_app_pool.get_rex_app_pool "
            "and query procore.* tables on the Rex App DB instead."
        )
