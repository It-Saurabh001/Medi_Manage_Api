import os
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.integrations.email.base import EmailSender
from app.services.db_init import init_db


class FakeEmailSender(EmailSender):
    """Test double for EmailSender recording all sent messages in-memory."""

    def __init__(self):
        self.sent_messages = []

    def send(self, to: str, subject: str, body: str) -> bool:
        self.sent_messages.append({
            "to": to,
            "subject": subject,
            "body": body,
        })
        return True

    def clear(self):
        self.sent_messages.clear()


def _remove_db_files(path):
    for suffix in ("", "-wal", "-shm"):
        try:
            if os.path.exists(path + suffix):
                os.remove(path + suffix)
        except OSError:
            pass


@pytest.fixture(scope="session")
def test_db_path():
    db_file = "test_medical_shop.db"
    yield db_file
    _remove_db_files(db_file)


@pytest.fixture
def app(test_db_path):
    _remove_db_files(test_db_path)
    os.environ["DATABASE_NAME"] = test_db_path
    os.environ["FLASK_ENV"] = "testing"

    application = create_app("testing")
    application.config["DATABASE_NAME"] = test_db_path
    fake_sender = FakeEmailSender()
    application.extensions["email_sender"] = fake_sender

    with application.app_context():
        init_db(backup=False)

    yield application

    _remove_db_files(test_db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_email_sender(app):
    return app.extensions["email_sender"]


@pytest.fixture
def make_headers(app):
    def _make(identity, role, expires_delta=None):
        with app.app_context():
            kwargs = {"expires_delta": expires_delta} if expires_delta is not None else {}
            token = create_access_token(identity=identity, additional_claims={"role": role}, **kwargs)
            return {"Authorization": f"Bearer {token}"}
    return _make


@pytest.fixture
def admin_headers(make_headers):
    return make_headers("AID_test_admin", "admin")


@pytest.fixture
def user_headers(make_headers):
    return make_headers("UID_test_user", "user")


@pytest.fixture
def api(app):
    """API_PREFIX from config, e.g. '/api/v1'."""
    return app.config["API_PREFIX"].rstrip("/")


@pytest.fixture
def expired_headers(make_headers):
    return make_headers("AID_test_admin", "admin", expires_delta=timedelta(seconds=-10))
