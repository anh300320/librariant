from fastapi import APIRouter, Depends
from starlette import status

from app.router.dependencies import get_folder_service
from app.schema.folder import FolderResponse, FolderAsset
from app.service.folder import FolderService

router = APIRouter(prefix="/folders", tags=["folders"])

@router.post("/{folder_id}", status_code=status.HTTP_200_OK)
async def get(
    folder_id: int,
    folder_service: FolderService = Depends(get_folder_service)
) -> FolderResponse:
    child_nodes = await folder_service.visit_folder(folder_id)
    data = [
        FolderAsset(
            id=node.id,
            name=node.name,
            created_at=node.created_at,
        )
        for node in child_nodes
    ]
    return FolderResponse(data=data)
