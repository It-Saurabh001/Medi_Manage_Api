import os
import pytest
from flask_jwt_extended import create_access_token
from app import create_app
from app.integrations.email.base import EmailSender
from app.services.db_init import createTable, updateTable

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

@pytest.fixture(scope="session")
def test_db_path():
    db_file = "test_medical_shop.db"
    yield db_file
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass

@pytest.fixture
def app(test_db_path):
    os.environ["DATABASE_NAME"] = test_db_path
    os.environ["FLASK_ENV"] = "testing"

    application = create_app("testing")
    fake_sender = FakeEmailSender()
    application.extensions["email_sender"] = fake_sender

    with application.app_context():
        createTable()
        updateTable()

    yield application

    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def fake_email_sender(app):
    return app.extensions["email_sender"]

@pytest.fixture
def make_headers(app):
    def _make(identity, role):
        with app.app_context():
            token = create_access_token(identity=identity, additional_claims={"role": role})
            return {"Authorization": f"Bearer {token}"}
    return _make
