import uuid


def test_create_get_update_friend(client, auth, make_friend):
    f = make_friend("  Siti  ", nickname="Sit", phone="+62 812-3456")
    assert f["name"] == "Siti"  # trimmed
    got = client.get(f"/api/v1/friends/{f['id']}", headers=auth)
    assert got.status_code == 200 and got.json()["phone"] == "+62 812-3456"

    upd = client.patch(f"/api/v1/friends/{f['id']}", json={"nickname": None, "name": "Siti N"}, headers=auth)
    assert upd.status_code == 200
    assert upd.json()["name"] == "Siti N" and upd.json()["nickname"] is None
    assert upd.json()["phone"] == "+62 812-3456"  # untouched


def test_phone_need_not_be_unique(make_friend):
    make_friend("A", phone="0812345")
    make_friend("B", phone="0812345")


def test_friend_validation(client, auth):
    for body in ({}, {"name": "   "}, {"name": "x" * 121}, {"name": "A", "phone": "abc"}):
        res = client.post("/api/v1/friends", json=body, headers=auth)
        assert res.status_code == 422, body
    f = client.post("/api/v1/friends", json={"name": "A"}, headers=auth).json()
    res = client.patch(f"/api/v1/friends/{f['id']}", json={"name": None}, headers=auth)
    assert res.status_code == 422


def test_list_search_and_pagination(client, auth, make_friend):
    for n in ["Andi", "Budi", "Candra", "Dewi", "Eko"]:
        make_friend(n, nickname="Bud" if n == "Candra" else None)
    page = client.get("/api/v1/friends?page=2&page_size=2", headers=auth).json()
    assert page["total"] == 5 and page["page"] == 2 and page["page_size"] == 2
    assert [i["name"] for i in page["items"]] == ["Candra", "Dewi"]

    found = client.get("/api/v1/friends?search=bud", headers=auth).json()
    assert {i["name"] for i in found["items"]} == {"Budi", "Candra"}  # name + nickname
    assert client.get("/api/v1/friends?search=%25", headers=auth).json()["total"] == 0  # wildcard escaped


def test_page_size_bounded(client, auth):
    assert client.get("/api/v1/friends?page_size=101", headers=auth).status_code == 422
    assert client.get("/api/v1/friends?page_size=0", headers=auth).status_code == 422
    assert client.get("/api/v1/friends?page=0", headers=auth).status_code == 422


def test_missing_friend_404(client, auth):
    missing = uuid.uuid4()
    for method in ("get", "patch", "delete"):
        kw = {"json": {"name": "X"}} if method == "patch" else {}
        res = getattr(client, method)(f"/api/v1/friends/{missing}", headers=auth, **kw)
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"
    assert client.get("/api/v1/friends/not-a-uuid", headers=auth).status_code == 422


def test_delete_unreferenced_friend(client, auth, make_friend):
    f = make_friend()
    assert client.delete(f"/api/v1/friends/{f['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/friends/{f['id']}", headers=auth).status_code == 404


def test_cannot_delete_friend_with_history(client, auth, make_friend, make_event, make_contribution):
    f, e = make_friend(), make_event()
    make_contribution(e["id"], f["id"])
    res = client.delete(f"/api/v1/friends/{f['id']}", headers=auth)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "friend_in_use"
    assert client.get(f"/api/v1/friends/{f['id']}", headers=auth).status_code == 200
