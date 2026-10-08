from typing import List
from fastapi import APIRouter, HTTPException
from app.models.gmail import Thread, Email
from app.schemas.gmail import GmailOverviewResponse
from app.services.gmail_service import gmail_service

router = APIRouter(prefix="/gmail")

@router.get("/overview", response_model=GmailOverviewResponse)
def get_gmail_overview():
    return gmail_service.get_overview()

@router.get("/emails", response_model=List[Email])
def get_emails():
    return gmail_service.get_emails()

@router.get("/threads", response_model=List[Thread])
def get_threads():
    return gmail_service.get_threads()

@router.get("/threads/{thread_id}", response_model=Thread)
def get_thread_by_id(thread_id: str):
    thread = gmail_service.get_thread_by_id(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread with ID '{thread_id}' not found.")
    return thread
