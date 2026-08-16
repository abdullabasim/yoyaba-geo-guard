"""Database access layer. Routers must go through these modules, never raw SQL."""

from app.crud.alert_crud import alert_crud
from app.crud.client_crud import client_crud
from app.crud.keyword_crud import keyword_crud
from app.crud.project_crud import project_crud
from app.crud.ranking_crud import ranking_crud
from app.crud.task_crud import task_log_crud
from app.crud.url_crud import target_url_crud
from app.crud.user_crud import user_crud

__all__ = [
    "alert_crud",
    "client_crud",
    "keyword_crud",
    "project_crud",
    "ranking_crud",
    "target_url_crud",
    "task_log_crud",
    "user_crud",
]
