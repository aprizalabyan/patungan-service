"""Management commands. Usage: python -m app.cli create-treasurer --name NAME --email EMAIL

The password is read from the PATUNGAN_TREASURER_PASSWORD environment variable
if set, otherwise prompted for (hidden). There is intentionally no HTTP
registration endpoint.
"""

import argparse
import getpass
import os
import sys

from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


def create_treasurer(name: str, email: str, password: str) -> None:
    try:
        email = TypeAdapter(EmailStr).validate_python(email).lower()
    except ValidationError:
        sys.exit("error: invalid email address")
    if not name.strip():
        sys.exit("error: name must not be empty")
    if len(password) < 8:
        sys.exit("error: password must be at least 8 characters")

    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            sys.exit(f"error: a user with email {email} already exists")
        db.add(User(name=name.strip(), email=email, password_hash=hash_password(password)))
        db.commit()
    print(f"Created treasurer {email}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-treasurer", help="Create the treasurer account")
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    args = parser.parse_args()

    password = os.environ.get("PATUNGAN_TREASURER_PASSWORD")
    if not password:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            sys.exit("error: passwords do not match")
    create_treasurer(args.name, args.email, password)


if __name__ == "__main__":
    main()
