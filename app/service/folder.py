from pathlib import Path

from app.db.repository.node import get_child_nodes_by_parent_id, add_folder, get_node_by_path
from app.db.session import get_db_sess
from app.exception.node import InvalidNodeTypeError
from app.lib.utils import normalize_node_name
from app.models.document import BaseNode, Folder
from app.models.user import UserModel


class FolderService:
    def __init__(self):
        pass

    async def visit_folder(
        self,
        folder_id: int,
    ) -> list[BaseNode]:
        async with get_db_sess() as db_sess:
            child_nodes = await get_child_nodes_by_parent_id(
                db_sess,
                folder_id
            )
        return child_nodes

    async def create_user_directory(
        self,
        user: UserModel,
    ) -> Folder:
        home_folder_name = self._get_user_home_folder_name(user)
        folder = Folder(
            name=home_folder_name,
            path=Path(f"/{home_folder_name}")
        )
        async with get_db_sess() as db_sess:
            added_folder = await add_folder(db_sess, folder)
        return added_folder

    async def get_user_home_folder(self, user: UserModel) -> Folder:
        home_folder_name = self._get_user_home_folder_name(user)
        home_folder_path = Path(f"/{home_folder_name}")
        async with get_db_sess() as db_sess:
            home_folder = await get_node_by_path(db_sess, home_folder_path.as_posix())
        if not isinstance(home_folder, Folder):
            raise InvalidNodeTypeError
        return home_folder

    def _get_user_home_folder_name(self, user: UserModel) -> str:
        return normalize_node_name(user.username)