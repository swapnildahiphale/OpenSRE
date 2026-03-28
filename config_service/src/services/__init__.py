"""Services package.

Note: legacy services (alert-matching, direct DB models from other repos) have been removed.
The current service entrypoint is `ConfigServiceRDS`.
"""

from .config_service_rds import ConfigServiceRDS

__all__ = ["ConfigServiceRDS"]
