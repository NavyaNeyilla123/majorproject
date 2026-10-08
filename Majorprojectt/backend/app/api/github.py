from typing import List
from fastapi import APIRouter
from app.models.github import Repository, Issue, PullRequest, Commit, Review
from app.schemas.github import GitHubOverviewResponse
from app.services.github_service import github_service

router = APIRouter(prefix="/github")

@router.get("/overview", response_model=GitHubOverviewResponse)
def get_github_overview():
    return github_service.get_overview()

@router.get("/repositories", response_model=List[Repository])
def get_repositories():
    return github_service.get_repositories()

@router.get("/issues", response_model=List[Issue])
def get_issues():
    return github_service.get_issues()

@router.get("/pull-requests", response_model=List[PullRequest])
def get_pull_requests():
    return github_service.get_pull_requests()

@router.get("/commits", response_model=List[Commit])
def get_commits():
    return github_service.get_commits()

@router.get("/reviews", response_model=List[Review])
def get_reviews():
    return github_service.get_reviews()
