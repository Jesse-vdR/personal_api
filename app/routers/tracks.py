from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session
from app.models.track import Track
from app.models.user import User
from app.schemas.track import TrackIn, TrackOut, TrackPatch

router = APIRouter(prefix="/v1/training/tracks", tags=["training"])


def _get_owned(session: Session, user: User, track_id: int) -> Track:
    track = session.get(Track, track_id)
    if track is None or track.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "track not found")
    return track


@router.get("", response_model=list[TrackOut])
def list_tracks(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> list[Track]:
    stmt = select(Track).where(Track.user_id == user.id).order_by(Track.slug.asc())
    return list(session.scalars(stmt).all())


@router.get("/{track_id}", response_model=TrackOut)
def get_track(
    track_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Track:
    return _get_owned(session, user, track_id)


@router.post("", response_model=TrackOut, status_code=status.HTTP_201_CREATED)
def create_track(
    payload: TrackIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Track:
    track = Track(
        user_id=user.id,
        slug=payload.slug,
        display=payload.display,
        stages=payload.stages,
    )
    session.add(track)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"track slug already exists: {payload.slug}"
        ) from exc
    session.refresh(track)
    return track


@router.patch("/{track_id}", response_model=TrackOut)
def update_track(
    track_id: int,
    payload: TrackPatch,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> Track:
    track = _get_owned(session, user, track_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(track, k, v)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "slug conflicts with another track"
        ) from exc
    session.refresh(track)
    return track


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_track(
    track_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(require_session)],
) -> None:
    track = _get_owned(session, user, track_id)
    session.delete(track)
    session.commit()
