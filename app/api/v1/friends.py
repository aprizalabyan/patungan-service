import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DbSession, PaginationParams, get_current_user
from app.schemas.common import Page
from app.schemas.friend import FriendCreate, FriendRead, FriendUpdate
from app.services import friends as service

router = APIRouter(
    prefix="/friends", tags=["friends"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=Page[FriendRead])
def list_friends(
    db: DbSession,
    pagination: PaginationParams,
    search: Annotated[str | None, Query(max_length=100)] = None,
):
    items, total = service.list_friends(
        db, search=search, page=pagination.page, page_size=pagination.page_size
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("", response_model=FriendRead, status_code=status.HTTP_201_CREATED)
def create_friend(body: FriendCreate, db: DbSession):
    return service.create_friend(db, body)


@router.get("/{friend_id}", response_model=FriendRead)
def get_friend(friend_id: uuid.UUID, db: DbSession):
    return service.get_friend(db, friend_id)


@router.patch("/{friend_id}", response_model=FriendRead)
def update_friend(friend_id: uuid.UUID, body: FriendUpdate, db: DbSession):
    return service.update_friend(db, friend_id, body)


@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_friend(friend_id: uuid.UUID, db: DbSession):
    service.delete_friend(db, friend_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
