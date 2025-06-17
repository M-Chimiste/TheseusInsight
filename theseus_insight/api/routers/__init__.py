from .papers import router as papers_router
from .settings import router as settings_router
from .model_providers import router as model_providers_router
from .runs_and_tasks import router as runs_and_tasks_router
from .logs import router as logs_router
from .newsletters_and_podcasts import router as newsletters_and_podcasts_router
from .actions import router as actions_router
from .database import router as database_router
from .research_agent import router as research_agent_router
from .model_catalog import router as model_catalog_router
from .websockets import router as websockets_router, manager as websocket_manager

# List of all routers for easy importing in main.py
all_routers = [
    papers_router,
    settings_router,
    model_providers_router,
    runs_and_tasks_router,
    logs_router,
    newsletters_and_podcasts_router,
    actions_router,
    database_router,
    research_agent_router,
    model_catalog_router,
    websockets_router
]

__all__ = [
    "papers_router",
    "settings_router", 
    "model_providers_router",
    "runs_and_tasks_router",
    "logs_router",
    "newsletters_and_podcasts_router",
    "actions_router",
    "database_router",
    "research_agent_router",
    "model_catalog_router",
    "websockets_router",
    "websocket_manager",
    "all_routers"
] 