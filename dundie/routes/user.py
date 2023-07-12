from typing import List

from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from sqlmodel import Session, select
from dundie.models.user import (
    User,
    UserResponse,
    UserResponseWithBalance,
    UserRequest,
    UserProfilePatchRequest,
    UserPasswordPatchRequest
)
from dundie.db import ActiveSession
from dundie.auth import SuperUser, AuthenticatedUser, CanChangeUserPassword
from sqlalchemy.exc import IntegrityError
from dundie.tasks.user import try_to_send_pwd_reset_email

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import parse_obj_as
from dundie.auth import ShowBalanceField


router = APIRouter()


@router.get(
    "/",
    response_model=List[UserResponse] | List[UserResponseWithBalance],
    response_model_exclude_unset=True
)
async def list_users(
        *,
        session: Session = ActiveSession,
        show_balance_field: bool = ShowBalanceField,
):
    """List all users from database"""
    users = session.exec(select(User)).all()
    # TODO: pagination
    if show_balance_field:
        users_with_balance = parse_obj_as(List[UserResponseWithBalance], users)
        return JSONResponse(jsonable_encoder(users_with_balance))

    return users


@router.get("/{username}/", response_model=UserResponse | UserResponseWithBalance, response_model_exclude_unset=True)
async def get_user_by_username(
    *,
    session: Session = ActiveSession,
    show_balance_field: bool = ShowBalanceField,
    username: str,
):
    """Get single user by username"""
    query = select(User).where(User.username == username)
    user = session.exec(query).first()
    if not user:
        raise HTTPException(status_code=404, detail="User Not Found")

    if show_balance_field:
        user_with_balance = parse_obj_as(UserResponseWithBalance, user)
        return JSONResponse(jsonable_encoder(user_with_balance))

    return user


@router.post("/", response_model=UserResponse, status_code=201, dependencies=[SuperUser])
async def create_user(*, session: Session = ActiveSession, user: UserRequest):
    """Creates a new user"""
    # LBYL
    if session.exec(select(User).where(User.email == user.email)).first():
        raise HTTPException(status_code=409, detail="User email already exists.")

    db_user = User.from_orm(user)
    session.add(db_user)
    # EAFP
    try:
        session.commit()
    except IntegrityError:
        raise HTTPException(
            status_code=500,
            detail="Database IntegrityError"
        )
    session.refresh(db_user)
    return db_user


@router.patch("/{username}/", response_model=UserResponse)
async def update_user(
    *,
    session: Session = ActiveSession,
    patch_data: UserProfilePatchRequest,
    current_user: User = AuthenticatedUser,
    username: str
):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id != current_user.id and not current_user.superuser:
        raise HTTPException(status_code=403, detail="You can only update your own profile")

    # Update
    if patch_data.avatar is not None:
        user.avatar = patch_data.avatar

    if patch_data.bio is not None:
        user.bio = patch_data.bio

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/{username}/password/", response_model=UserResponse)
async def change_password(
    *,
    session: Session = ActiveSession,
    patch_data: UserPasswordPatchRequest,
    user: User = CanChangeUserPassword
):
    user.password = patch_data.hashed_password  # pyright: ignore
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/pwd_reset_token/")
async def send_password_reset_token(
    *,
    email: str = Body(embed=True),
    background_tasks: BackgroundTasks,
):
    """Sends an email with the token to reset password."""

    background_tasks.add_task(try_to_send_pwd_reset_email, email=email)

    return {
        "message": "If we found a user with that email, we sent a password reset token to it."
    }
