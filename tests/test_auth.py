from app.models.user import UserModel


def test_auth_flow(client, db_session):
    # 1. Create a user
    user = UserModel(
        id="usr_1",
        name="Akua Mensah",
        role="bursar",
        pin="1234"
    )
    db_session.add(user)
    db_session.commit()

    # 2. List users
    users_res = client.get("/users")
    assert users_res.status_code == 200
    users_data = users_res.json()
    assert len(users_data) == 1
    assert users_data[0]["id"] == "usr_1"
    assert users_data[0]["name"] == "Akua Mensah"

    # 3. Failed login
    bad_login = client.post("/auth/login", json={"user_id": "usr_1", "pin": "9999"})
    assert bad_login.status_code == 401
    assert "Invalid PIN" in bad_login.json()["detail"]

    # 4. Successful login
    good_login = client.post("/auth/login", json={"user_id": "usr_1", "pin": "1234"})
    assert good_login.status_code == 200
    token = good_login.json()["token"]
    assert token.startswith("token_usr_1_")
    assert good_login.json()["user"]["name"] == "Akua Mensah"
    assert good_login.json()["user"]["role"] == "bursar"

    # 5. /auth/me with Bearer token
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["id"] == "usr_1"
    assert me_res.json()["role"] == "bursar"
