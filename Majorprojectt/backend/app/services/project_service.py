from typing import List, Optional
from app.repositories.project_repository import project_repository
from app.repositories.github_repository import github_repository
from app.repositories.gmail_repository import gmail_repository
from app.models.project import Project
from app.schemas.project import ProjectDetailResponse

class ProjectService:
    def get_projects(self) -> List[Project]:
        return project_repository.get_projects()

    def get_project_by_id(self, project_id: str) -> Optional[ProjectDetailResponse]:
        proj = project_repository.get_project_by_id(project_id)
        if not proj:
            # Default to first project if requested ID isn't matched
            projects = project_repository.get_projects()
            if not projects:
                return None
            proj = projects[0]
            
        all_issues = github_repository.get_issues()
        all_prs = github_repository.get_pull_requests()
        all_threads = gmail_repository.get_threads()
        all_emails = gmail_repository.get_emails()

        proj_issues = [i for i in all_issues if i.project_id == proj.id or i.repository in proj.repositories]
        proj_prs = [p for p in all_prs if p.project_id == proj.id or p.repository in proj.repositories]
        proj_threads = [t for t in all_threads if t.project_id == proj.id]

        return ProjectDetailResponse(
            project=proj,
            health_score=proj.health_score if proj.health_score is not None else 0,
            open_issues_count=len([i for i in proj_issues if i.status == "open"]),
            active_prs_count=len([p for p in proj_prs if p.status != "merged" and p.status != "closed"]),
            relevant_emails_count=len([e for e in all_emails if e.project_id == proj.id]),
            linked_repositories_count=len(proj.repositories),
            issues=proj_issues,
            pull_requests=proj_prs,
            threads=proj_threads
        )

project_service = ProjectService()
