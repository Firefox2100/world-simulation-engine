from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Landmark
from .utils import db_dep


landmark_router = APIRouter(
    tags=["Landmark"],
)


class LandmarkCreate(BaseModel):
    name: str = Field(..., description="Name of the landmark")
    description: str = Field(..., description="Description of the landmark")


class LandmarkUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the landmark")
    description: Optional[str] = Field(None, description="Description of the landmark")


class LandmarkLocationUpdate(BaseModel):
    location_id: str = Field(..., description="Location that contains the landmark")


@landmark_router.get("/landmarks", response_model=list[Landmark])
async def list_landmarks(
        db: db_dep,
        world_id: Optional[str] = Query(None, description="Optionally filter by world"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
        location_id: Optional[str] = Query(None, description="Optionally filter by location"),
):
    return await db.location.list_landmarks(
        world_id=world_id,
        simulation_id=simulation_id,
        location_id=location_id,
    )


@landmark_router.get("/landmarks/{landmark_id}", response_model=Landmark)
async def get_landmark(landmark_id: str, db: db_dep):
    landmark = await db.location.get_landmark(landmark_id)
    if not landmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Landmark {landmark_id} not found",
        )

    return landmark


@landmark_router.patch("/landmarks/{landmark_id}", response_model=Landmark)
async def update_landmark(landmark_id: str, landmark_data: LandmarkUpdate, db: db_dep):
    landmark = await db.location.update_landmark(
        landmark_id,
        landmark_data.model_dump(exclude_unset=True),
    )
    if not landmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Landmark {landmark_id} not found",
        )

    return landmark


@landmark_router.delete("/landmarks/{landmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_landmark(landmark_id: str, db: db_dep):
    deleted = await db.location.delete_landmark(landmark_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Landmark {landmark_id} not found",
        )


@landmark_router.put("/landmarks/{landmark_id}/location", response_model=Landmark)
async def set_landmark_location(
        landmark_id: str,
        location_data: LandmarkLocationUpdate,
        db: db_dep,
):
    if not await db.location.get_landmark(landmark_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Landmark {landmark_id} not found",
        )
    if not await db.location.get_location(location_data.location_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_data.location_id} not found",
        )

    landmark = await db.location.move_landmark_to_location(
        landmark_id,
        location_data.location_id,
    )
    if not landmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Landmark {landmark_id} not found",
        )

    return landmark


@landmark_router.post("/locations/{location_id}/landmarks", response_model=Landmark)
async def create_landmark(location_id: str, landmark_data: LandmarkCreate, db: db_dep):
    if not await db.location.get_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    landmark = Landmark(**landmark_data.model_dump())
    created_landmark = await db.location.create_landmark(landmark, location_id)
    if not created_landmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    return created_landmark
