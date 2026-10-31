from fastapi.testclient import TestClient

from parse_video_py.web import app

AUTH = ("admin", "admin123")


def new_client() -> TestClient:
    return TestClient(app)


def login(client: TestClient, username: str, password: str):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_default_credentials_are_admin_admin123():
    client = new_client()
    response = client.get("/api/settings/credentials", auth=AUTH)
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "admin"
    assert (
        client.get("/api/settings/credentials", auth=("admin", "wrong")).status_code
        == 401
    )


def test_home_redirects_to_login_when_unauthenticated():
    client = new_client()
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_login_page_is_accessible():
    client = new_client()
    response = client.get("/login")
    assert response.status_code == 200
    assert "登录" in response.text


def test_login_with_default_credentials_creates_session():
    client = new_client()
    response = login(client, "admin", "admin123")
    assert response.status_code == 303
    home = client.get("/")
    assert home.status_code == 200


def test_login_with_wrong_credentials_is_rejected():
    client = new_client()
    response = login(client, "admin", "wrong-password")
    assert response.status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 302


def test_api_routes_require_login():
    client = new_client()
    unauthenticated = client.get("/video/share/url/parse", params={"url": "x"})
    assert unauthenticated.status_code == 401

    client.cookies.clear()
    authenticated = client.get(
        "/video/share/url/parse", params={"url": "这不是链接"}, auth=AUTH
    )
    assert authenticated.status_code == 200
    assert authenticated.json()["code"] == 400


def test_healthz_is_open_without_login():
    client = new_client()
    assert client.get("/healthz").status_code == 200


def test_settings_change_credentials_and_relogin():
    client = new_client()
    assert login(client, "admin", "admin123").status_code == 303

    response = client.post(
        "/api/settings/credentials",
        json={"username": "boss", "password": "new-password"},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 200

    # 凭据变更后所有会话立即失效
    assert client.get("/", follow_redirects=False).status_code == 302

    assert login(client, "admin", "admin123").status_code == 401
    assert login(client, "boss", "new-password").status_code == 303
    assert client.get("/api/settings/credentials").json()["data"]["username"] == "boss"


def test_settings_rejects_empty_credentials():
    client = new_client()
    assert login(client, "admin", "admin123").status_code == 303
    response = client.post(
        "/api/settings/credentials", json={"username": "", "password": ""}
    )
    assert response.status_code == 200
    assert response.json()["code"] == 400


def test_logout_clears_session():
    client = new_client()
    assert login(client, "admin", "admin123").status_code == 303
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/", follow_redirects=False).status_code == 302
