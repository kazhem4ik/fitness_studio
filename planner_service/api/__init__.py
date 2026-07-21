from planner_service.api.auth import router as auth_router
from planner_service.api.appointments import router as appointments_router
from planner_service.api.clients import router as clients_router
from planner_service.api.finances import router as finances_router

__all__ = ["auth_router", "appointments_router", "clients_router", "finances_router"]
