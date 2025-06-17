import os
from typing import Any

class ProjectManager:
    """
    Manages project-related utilities, such as directory structures.
    """

    DEFAULT_UPLOAD_BASE_DIR = "data/uploads"

    @classmethod
    def get_project_upload_dir(cls, project_id: int, app_config: Any) -> str:
        """
        Determines the upload directory for a given project.

        Args:
            project_id (int): The ID of the project.
            app_config (dict): The Flask application configuration object.
                               Expected to behave like a dictionary.

        Returns:
            str: The absolute or relative path to the project's upload directory.
        """
        upload_base_dir = app_config.get("UPLOAD_FOLDER", cls.DEFAULT_UPLOAD_BASE_DIR)
        project_specific_dir = f"project_{project_id}"
        return os.path.join(upload_base_dir, project_specific_dir)
