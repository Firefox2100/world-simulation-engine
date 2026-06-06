from typing import Annotated
from fastapi import Request, Depends

from world_simulation_engine.service import DatabaseService


def get_database_service(request: Request) -> DatabaseService:
    return request.app.state.database_service


db_dep = Annotated[DatabaseService, Depends(get_database_service)]
