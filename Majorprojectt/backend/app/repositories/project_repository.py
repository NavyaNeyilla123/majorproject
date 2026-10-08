from typing import List, Optional
from app.core.data_loader import data_loader
from app.models.project import Project

class ProjectRepository:
    def get_projects(self) -> List[Project]:
        raw = data_loader.load_json("projects/projects.json")
        return [Project(**item) for item in raw]

    def get_project_by_id(self, project_id: str) -> Optional[Project]:
        for proj in self.get_projects():
            if proj.id == project_id or proj.code == project_id:
                return proj
        return None

project_repository = ProjectRepository()
