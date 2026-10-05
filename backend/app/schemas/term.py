import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

TermName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


class TermCreate(BaseModel):
    name: TermName
    start_date: dt.date
    end_date: dt.date

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TermUpdate(BaseModel):
    name: TermName | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class TermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: dt.date
    end_date: dt.date
