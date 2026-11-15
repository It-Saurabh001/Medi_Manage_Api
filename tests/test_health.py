def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "Medi_Manage_Api"


def test_ready_endpoint(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["checks"]["database"] == "ok"


def test_root_greeting_removed(client):
    """Part 3: the legacy `/` "Hello World" route was removed (use GET /api/v1)."""
    assert client.get("/").status_code == 404


def test_dox_redirects_to_swagger_ui(client):
    response = client.get("/dox")
    assert response.status_code == 301
    assert response.headers["Location"].endswith("/api/docs")
    page = client.get("/api/docs")
    assert page.status_code == 200
    assert b"swagger-ui" in page.data
