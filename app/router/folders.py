from fastapi import APIRouter
from starlette import status

router = APIRouter(prefix="/folders", tags=["folders"])

@router.post("/folders", status_code=status.HTTP_200_OK)
async def create_folder():
    pass
