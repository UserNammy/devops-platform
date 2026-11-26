from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_checks_database(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_metrics_exposes_prometheus_format(client: TestClient) -> None:
    client.get("/health")
    client.get("/doesnotexist")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert 'http_requests_total{method="GET",route="/health",status="200"}' in body
    # Raw paths must not leak into labels: the route template is used instead.
    assert 'route="/{code}"' in body
    assert "doesnotexist" not in body
    assert "shortener_links_created_total" in body
