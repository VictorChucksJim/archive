from tests.conftest import register_user


def test_create_and_list_folder(client):
    register_user(client, email="folders1@example.com")

    resp = client.post("/api/folders", json={"name": "Personal"})
    assert resp.status_code == 201
    folder = resp.json()
    assert folder["name"] == "Personal"
    assert folder["parent_id"] is None

    listing = client.get("/api/folders")
    assert listing.status_code == 200
    assert any(f["id"] == folder["id"] for f in listing.json())


def test_nested_folder_creation(client):
    register_user(client, email="folders2@example.com")

    parent = client.post("/api/folders", json={"name": "Work"}).json()
    child = client.post("/api/folders", json={"name": "Reports", "parent_id": parent["id"]})
    assert child.status_code == 201
    assert child.json()["parent_id"] == parent["id"]

    children = client.get("/api/folders", params={"parent_id": parent["id"]})
    assert len(children.json()) == 1
    assert children.json()[0]["name"] == "Reports"


def test_rename_folder(client):
    register_user(client, email="folders3@example.com")
    folder = client.post("/api/folders", json={"name": "Old Name"}).json()

    resp = client.patch(f"/api/folders/{folder['id']}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_delete_folder_excluded_from_listing(client):
    register_user(client, email="folders4@example.com")
    folder = client.post("/api/folders", json={"name": "Temp"}).json()

    delete_resp = client.delete(f"/api/folders/{folder['id']}")
    assert delete_resp.status_code == 204

    listing = client.get("/api/folders")
    assert all(f["id"] != folder["id"] for f in listing.json())


def test_cannot_use_nonexistent_folder_as_parent(client):
    register_user(client, email="folders5@example.com")
    resp = client.post("/api/folders", json={"name": "Orphan", "parent_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 404
