import json
import uuid

SENSITIVE = [
    "password",
    "hash",
    "email",
    "treasurer@example.com",
    "created_by",
    "081299998888",
    "+6281",
    "secret-note",
    "paid_at",
    "is_public",
    "nickname",
]


def _scenario(client, auth, make_friend, make_event, make_contribution):
    f = make_friend("Citra", nickname="Cit", phone="081299998888")
    e = make_event("Public gift", description="For Rina", target_amount=200_000)
    c = make_contribution(e["id"], f["id"], 100_000, notes="secret-note")
    client.patch(f"/api/v1/contributions/{c['id']}", json={"payment_status": "paid"}, headers=auth)
    return e


def test_public_endpoints_need_no_auth_and_show_public_event(
    client, auth, make_friend, make_event, make_contribution
):
    e = _scenario(client, auth, make_friend, make_event, make_contribution)

    listing = client.get("/api/v1/public/events").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == e["id"]

    detail = client.get(f"/api/v1/public/events/{e['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "Public gift" and body["status"] == "active"
    assert body["participants"] == [{"name": "Citra", "payment_status": "paid"}]

    summary = client.get(f"/api/v1/public/events/{e['id']}/summary").json()
    assert summary["total_collected"] == 100_000 and summary["progress_percent"] == 50


def test_public_responses_do_not_leak_sensitive_fields(
    client, auth, make_friend, make_event, make_contribution
):
    e = _scenario(client, auth, make_friend, make_event, make_contribution)
    for path in ("", f"/{e['id']}", f"/{e['id']}/summary"):
        text = json.dumps(client.get(f"/api/v1/public/events{path}").json()).lower()
        for needle in SENSITIVE:
            assert needle.lower() not in text, (path, needle)
    detail = client.get(f"/api/v1/public/events/{e['id']}").json()
    assert set(detail) == {"id", "title", "description", "event_date", "target_amount", "status", "participants"}
    assert set(detail["participants"][0]) == {"name", "payment_status"}


def test_private_event_hidden_everywhere_publicly(client, auth, make_event):
    private = make_event("Secret", is_public=False)
    public = make_event("Open")
    listing = client.get("/api/v1/public/events").json()
    assert [i["id"] for i in listing["items"]] == [public["id"]] and listing["total"] == 1

    for path in ("", "/summary"):
        res = client.get(f"/api/v1/public/events/{private['id']}{path}")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"

    # Visibility is independent of authentication: even the treasurer's token
    # does not make a private event reachable via /public.
    assert client.get(f"/api/v1/public/events/{private['id']}", headers=auth).status_code == 404

    # Flipping visibility takes effect immediately, both directions.
    client.patch(f"/api/v1/events/{private['id']}", json={"is_public": True}, headers=auth)
    assert client.get(f"/api/v1/public/events/{private['id']}").status_code == 200
    client.patch(f"/api/v1/events/{public['id']}", json={"is_public": False}, headers=auth)
    assert client.get(f"/api/v1/public/events/{public['id']}").status_code == 404


def test_public_unknown_event_404_and_read_only(client, auth, make_event):
    assert client.get(f"/api/v1/public/events/{uuid.uuid4()}").status_code == 404
    e = make_event()
    for method in ("post", "patch", "delete", "put"):
        assert getattr(client, method)(f"/api/v1/public/events/{e['id']}").status_code == 405


def test_public_list_status_filter_and_pagination(client, auth, make_event):
    a = make_event("A")
    make_event("B")
    client.patch(f"/api/v1/events/{a['id']}", json={"status": "completed"}, headers=auth)
    done = client.get("/api/v1/public/events?status=completed").json()
    assert [i["title"] for i in done["items"]] == ["A"]
    assert client.get("/api/v1/public/events?page_size=101").status_code == 422
