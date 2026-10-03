def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "Medi_Manage_Api"

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.data == b"Hello World"

def test_dox_endpoint(client):
    response = client.get("/dox")
    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data
