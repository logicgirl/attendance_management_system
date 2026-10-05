from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints

StudentId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$"
    ),
]

# Student names and departments are title-cased, as in the desktop app
TitleCaseStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    AfterValidator(str.title),
]

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

Email = Annotated[EmailStr, AfterValidator(str.lower)]

# bcrypt only uses the first 72 bytes
Password = Annotated[str, StringConstraints(min_length=8, max_length=72)]
