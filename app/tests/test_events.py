import uuid


def test_create_event_defaults(client, auth, treasurer, make_event):
    e = make_event("Gift for Rina")
    assert e["status"] == "active" and e["is_public"] is True
    assert e["target_amount"] is None and e["created_by"] == str(treasurer.id)
    assert "contributions" not in e


def test_event_validation(client, auth):
    bad = [
        {},
        {"title": ""},
        {"title": "x", "target_amount": -1},
        {"title": "x", "target_amount": "abc"},
        {"title": "x", "status": "archived"},
        {"title": "x", "event_date": "not-a-date"},
    ]
    for body in bad:
        assert client.post("/api/v1/events", json=body, headers=auth).status_code == 422, body


def test_update_event(client, auth, make_event):
    e = make_event(target_amount=100)
    res = client.patch(
        f"/api/v1/events/{e['id']}",
        json={"status": "completed", "is_public": False, "target_amount": None, "event_date": "2026-12-01"},
        headers=auth,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed" and body["is_public"] is False
    assert body["target_amount"] is None and body["event_date"] == "2026-12-01"
    assert body["title"] == e["title"]
    assert body["updated_at"] >= e["updated_at"]
    assert client.patch(f"/api/v1/events/{e['id']}", json={"title": None}, headers=auth).status_code == 422


def test_list_events_status_filter_and_pagination(client, auth, make_event):
    a = make_event("A")
    make_event("B")
    client.patch(f"/api/v1/events/{a['id']}", json={"status": "completed"}, headers=auth)
    done = client.get("/api/v1/events?status=completed", headers=auth).json()
    assert [i["title"] for i in done["items"]] == ["A"] and done["total"] == 1
    page = client.get("/api/v1/events?page=1&page_size=1", headers=auth).json()
    assert len(page["items"]) == 1 and page["total"] == 2
    assert client.get("/api/v1/events?status=bogus", headers=auth).status_code == 422


def test_missing_event_404(client, auth):
    missing = uuid.uuid4()
    assert client.get(f"/api/v1/events/{missing}", headers=auth).status_code == 404
    assert client.patch(f"/api/v1/events/{missing}", json={"title": "x"}, headers=auth).status_code == 404
    assert client.delete(f"/api/v1/events/{missing}", headers=auth).status_code == 404
    assert client.get(f"/api/v1/events/{missing}/summary", headers=auth).status_code == 404
    assert client.get(f"/api/v1/events/{missing}/contributions", headers=auth).status_code == 404


def test_delete_event_cascades_contributions_but_keeps_friends(
    client, auth, make_friend, make_event, make_contribution
):
    f, e = make_friend(), make_event()
    c = make_contribution(e["id"], f["id"])
    assert client.delete(f"/api/v1/events/{e['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/events/{e['id']}", headers=auth).status_code == 404
    assert client.patch(f"/api/v1/contributions/{c['id']}", json={"notes": "x"}, headers=auth).status_code == 404
    assert client.get(f"/api/v1/friends/{f['id']}", headers=auth).status_code == 200
    # friend is no longer referenced, so now deletable
    assert client.delete(f"/api/v1/friends/{f['id']}", headers=auth).status_code == 204
