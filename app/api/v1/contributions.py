import uuid

from fastapi import APIRouter, Depends, Response

from app.api.deps import CurrentUser, DbSession, PaginationParams, get_current_user
from app.models import PaymentStatus
from app.schemas.common import Page
from app.schemas.contribution import ContributionCreate, ContributionRead, ContributionUpdate
from app.services import contributions as service
from app.services import events as event_service

router = APIRouter(tags=["contributions"], dependencies=[Depends(get_current_user)])


@router.get("/events/{event_id}/contributions", response_model=Page[ContributionRead])
def list_contributions(
    event_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    pagination: PaginationParams,
    payment_status: PaymentStatus | None = None,
):
    event = event_service.get_event(db, event_id, user_id=user.id)
    items, total = service.list_contributions(
        db,
        event.id,
        payment_status=payment_status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post(
    "/events/{event_id}/contributions", response_model=ContributionRead, status_code=201
)
def create_contribution(
    event_id: uuid.UUID, body: ContributionCreate, db: DbSession, user: CurrentUser
):
    event = event_service.get_event(db, event_id, user_id=user.id)
    return service.create_contribution(db, event, body)


@router.patch("/contributions/{contribution_id}", response_model=ContributionRead)
def update_contribution(
    contribution_id: uuid.UUID, body: ContributionUpdate, db: DbSession, user: CurrentUser
):
    return service.update_contribution(db, contribution_id, body, user_id=user.id)


@router.delete("/contributions/{contribution_id}", status_code=204)
def delete_contribution(contribution_id: uuid.UUID, db: DbSession, user: CurrentUser):
    service.delete_contribution(db, contribution_id, user_id=user.id)
    return Response(status_code=204)
