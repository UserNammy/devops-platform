from fastapi.testclient import TestClient


def create(client: TestClient, url: str = "https://example.com/page", **extra) -> dict:
    response = client.post("/api/links", json={"url": url, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_link_generates_code(client: TestClient) -> None:
    body = create(client)

    assert len(body["code"]) == 7
    assert body["target_url"] == "https://example.com/page"
    assert body["short_url"] == f"https://sho.rt/{body['code']}"
    assert body["clicks"] == 0


def test_create_link_with_custom_code(client: TestClient) -> None:
    body = create(client, code="my-alias")

    assert body["code"] == "my-alias"


def test_duplicate_custom_code_returns_409(client: TestClient) -> None:
    create(client, code="taken")

    response = client.post("/api/links", json={"url": "https://other.example", "code": "taken"})

    assert response.status_code == 409


def test_invalid_url_is_rejected(client: TestClient) -> None:
    response = client.post("/api/links", json={"url": "not a url"})

    assert response.status_code == 422


def test_invalid_custom_code_is_rejected(client: TestClient) -> None:
    response = client.post("/api/links", json={"url": "https://example.com", "code": "a b"})

    assert response.status_code == 422


def test_redirect_increments_clicks(client: TestClient) -> None:
    code = create(client)["code"]

    for _ in range(3):
        response = client.get(f"/{code}")
        assert response.status_code == 307
        assert response.headers["location"] == "https://example.com/page"

    assert client.get(f"/api/links/{code}").json()["clicks"] == 3


def test_unknown_code_returns_404(client: TestClient) -> None:
    assert client.get("/doesnotexist").status_code == 404
    assert client.get("/api/links/doesnotexist").status_code == 404


def test_delete_link(client: TestClient) -> None:
    code = create(client)["code"]

    assert client.delete(f"/api/links/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
