import sys, os
import pytest   # REQUIRED for fixtures

# Ensure Jenkins can import app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

@pytest.fixture
def client():
    """Provide a Flask test client for the app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_login_page_shows(client):
    """Check that login page loads."""
    rv = client.get('/login')
    assert b'Login' in rv.data


def test_login_success(client):
    """Valid login → dashboard."""
    rv = client.post(
        '/login',
        data={'username': 'alice', 'password': 'password123'},
        follow_redirects=True
    )
    # Updated app.py now shows "Welcome" on dashboard
    assert b'Welcome' in rv.data or b'Dashboard' in rv.data


def test_login_failure(client):
    """Invalid login should flash an error."""
    rv = client.post(
        '/login',
        data={'username': 'alice', 'password': 'wrongpass'},
        follow_redirects=True
    )
    assert b'Invalid username or password' in rv.data


def test_force_failure_for_notification():
    """
    This test intentionally fails when FORCE_FAIL=true.
    Used for Jenkins → Confluence → Email → RTM integration testing.
    """
    force_fail = os.getenv("FORCE_FAIL", "true").lower() == "true"

    if force_fail:
        assert False, "Intentional failure for CI/CD test result notification"
    else:
        assert True
