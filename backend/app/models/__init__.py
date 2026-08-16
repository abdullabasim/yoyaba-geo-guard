"""SQLAlchemy models.

All models are imported here so that ``Base.metadata`` is fully populated for
Alembic autogenerate and for relationship string resolution.
"""

from app.models.ai_alert import AIAlert
from app.models.base import ActiveMixin, Base, TimestampMixin
from app.models.client import Client
from app.models.enums import CheckInterval, IssueType, TaskStatus
from app.models.keyword import (
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_LOCATION_CODE,
    Keyword,
)
from app.models.project import Project
from app.models.rankings_history import RankingsHistory
from app.models.service_control import (
    SERVICE_METADATA,
    ServiceControl,
    ServiceKey,
)
from app.models.target_url import TargetURL
from app.models.task_execution_log import (
    MAX_ERROR_MESSAGE_LENGTH,
    TaskExecutionLog,
)
from app.models.user import User

__all__ = [
    "DEFAULT_LANGUAGE_CODE",
    "DEFAULT_LOCATION_CODE",
    "MAX_ERROR_MESSAGE_LENGTH",
    "SERVICE_METADATA",
    "AIAlert",
    "ActiveMixin",
    "Base",
    "CheckInterval",
    "Client",
    "IssueType",
    "Keyword",
    "Project",
    "RankingsHistory",
    "ServiceControl",
    "ServiceKey",
    "TargetURL",
    "TaskExecutionLog",
    "TaskStatus",
    "TimestampMixin",
    "User",
]
