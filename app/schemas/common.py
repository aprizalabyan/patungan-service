from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

T = TypeVar("T")

MAX_PAGE_SIZE = 100
# Upper bound for any Rupiah amount accepted from clients (1 trillion).
MAX_AMOUNT = 1_000_000_000_000


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PatchModel(BaseModel):
    """Base for PATCH bodies. Fields named in `non_nullable` may be omitted but,
    if sent, must not be null."""

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_explicit_null(self) -> "PatchModel":
        for name in self.model_fields_set & self.non_nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
