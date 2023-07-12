"""User related data models"""
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
from dundie.security import HashedPassword, get_password_hash
from pydantic import BaseModel, root_validator
from fastapi import HTTPException, status

if TYPE_CHECKING:
    from dundie.models.transaction import Transaction, Balance


class User(SQLModel, table=True):
    """Represents the User Model"""

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, nullable=False)
    username: str = Field(unique=True, nullable=False)
    avatar: Optional[str] = None
    bio: Optional[str] = None
    password: HashedPassword
    name: str = Field(nullable=False)
    dept: str = Field(nullable=False)
    currency: str = Field(nullable=False)

    # Populates a `.user` on `Transaction`
    incomes: Optional[list["Transaction"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"primaryjoin": 'User.id == Transaction.user_id'},
    )
    # Populates a `.from_user` on `Transaction`
    expenses: Optional[list["Transaction"]] = Relationship(
        back_populates="from_user",
        sa_relationship_kwargs={"primaryjoin": 'User.id == Transaction.from_id'},
    )
    # Populates a `.user` on `Balance`
    _balance: Optional["Balance"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "dynamic"}
    )

    @property
    def balance(self) -> int:
        """Returns the current balance of the user"""
        if (user_balance := self._balance.first()) is not None:  # pyright: ignore
            return user_balance.value
        return 0

    @property
    def superuser(self):
        """"Users belonging to management dept are admins."""
        return self.dept == "management"


def generate_username(name: str) -> str:
    """Generate a slug from user.name.
    "Bruno Rocha"" -> "bruno-rocha"
    "MIchael Scott" -> "michael-scott"
    # TODO: library slugify
    """
    return name.lower().replace(" ", "-")


class UserResponse(BaseModel):
    """Serializer for when we send a response to the client"""

    name: str
    username: str
    dept: str
    avatar: Optional[str] = None
    bio: Optional[str] = None
    currency: str


class UserResponseWithBalance(UserResponse):
    balance: Optional[int] = None

    @root_validator(pre=True)
    def set_balance(cls, values):
        instance = values['_sa_instance_state'].object
        values['balance'] = instance.balance
        return values


class UserRequest(BaseModel):
    """Serializer for when we get the user data from the client."""

    name: str
    email: str
    dept: str
    password: str
    username: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    currency: str = "USD"

    @root_validator(pre=True)
    def generate_username_if_not_set(cls, values):
        """Generates username"""
        if values.get("username") is None:
            values["username"] = generate_username(values["name"])
        return values


class UserProfilePatchRequest(BaseModel):
    """Serializer for when client wants to partially update user."""

    avatar: Optional[str] = None
    bio: Optional[str] = None

    @root_validator(pre=True)
    def ensure_values(cls, values):
        if not values:
            raise HTTPException(status_code=400, detail="Bad request, no data informed")
        return values


class UserPasswordPatchRequest(BaseModel):

    password: str
    password_confirm: str

    @root_validator(pre=True)
    def check_passwords_match(cls, values):
        """Checks if passwords match"""
        if values.get("password") != values.get("password_confirm"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
        return values

    @property
    def hashed_password(self) -> str:
        return get_password_hash(self.password)
