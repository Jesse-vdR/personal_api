from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user_profile import UserProfileIn, UserProfileOut

router = APIRouter(prefix="/v1/training/profile", tags=["training"])


@router.get("", response_model=UserProfileOut)
def get_profile(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> UserProfile:
    profile = session.get(UserProfile, user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile not set")
    return profile


@router.put("", response_model=UserProfileOut)
def put_profile(
    payload: UserProfileIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> UserProfile:
    profile = session.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id, body=payload.body)
        session.add(profile)
    else:
        profile.body = payload.body
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> None:
    profile = session.get(UserProfile, user.id)
    if profile is None:
        return
    session.delete(profile)
    session.commit()
