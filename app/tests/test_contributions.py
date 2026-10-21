import uuid
from datetime import datetime


def _paid(client, auth, cid):
    return client.patch(f"/api/v1/contributions/{cid}", json={"payment_status": "paid"}, headers=auth)


def test_create_defaults_to_pending(make_friend, make_event, make_contribution):
    f, e = make_friend("Dina"), make_event()
    c = make_contribution(e["id"], f["id"], 75_000, notes="cash")
    assert c["payment_status"] == "pending" and c["paid_at"] is None
    assert c["amount"] == 75_000 and c["notes"] == "cash"
    assert c["friend"] == {"id": f["id"], "name": "Dina", "nickname": None}


def test_duplicate_participation_conflict(client, auth, make_friend, make_event, make_contribution):
    f, e = make_friend(), make_event()
    make_contribution(e["id"], f["id"])
    res = client.post(
        f"/api/v1/events/{e['id']}/contributions",
        json={"friend_id": f["id"], "amount": 1000},
        headers=auth,
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "duplicate_contribution"
    # same friend in a different event is fine
    make_contribution(make_event("Other")["id"], f["id"])


def test_create_validation_and_missing_refs(client, auth, make_friend, make_event):
    f, e = make_friend(), make_event()
    url = f"/api/v1/events/{e['id']}/contributions"
    for amount in (0, -1, "x", 10**13):
        assert client.post(url, json={"friend_id": f["id"], "amount": amount}, headers=auth).status_code == 422
    assert client.post(url, json={"amount": 5}, headers=auth).status_code == 422
    assert client.post(url, json={"friend_id": str(uuid.uuid4()), "amount": 5}, headers=auth).status_code == 404
    res = client.post(
        f"/api/v1/events/{uuid.uuid4()}/contributions", json={"friend_id": f["id"], "amount": 5}, headers=auth
    )
    assert res.status_code == 404


def test_pending_to_paid_sets_paid_at_and_back_clears_it(client, auth, make_friend, make_event, make_contribution):
    c = make_contribution(make_event()["id"], make_friend()["id"])
    res = _paid(client, auth, c["id"])
    assert res.status_code == 200
    paid_at = datetime.fromisoformat(res.json()["paid_at"])
    assert paid_at.tzinfo is not None

    # paid -> paid keeps the original timestamp
    again = _paid(client, auth, c["id"]).json()
    assert datetime.fromisoformat(again["paid_at"]) == paid_at

    back = client.patch(f"/api/v1/contributions/{c['id']}", json={"payment_status": "pending"}, headers=auth)
    assert back.json()["payment_status"] == "pending" and back.json()["paid_at"] is None


def test_amount_change_does_not_alter_status(client, auth, make_friend, make_event, make_contribution):
    c = make_contribution(make_event()["id"], make_friend()["id"], 10_000)
    pending = client.patch(f"/api/v1/contributions/{c['id']}", json={"amount": 20_000}, headers=auth).json()
    assert pending["amount"] == 20_000 and pending["payment_status"] == "pending" and pending["paid_at"] is None

    paid = _paid(client, auth, c["id"]).json()
    after = client.patch(f"/api/v1/contributions/{c['id']}", json={"amount": 30_000}, headers=auth).json()
    assert after["payment_status"] == "paid" and after["paid_at"] == paid["paid_at"]


def test_update_validation_and_notes(client, auth, make_friend, make_event, make_contribution):
    c = make_contribution(make_event()["id"], make_friend()["id"], notes="hi")
    url = f"/api/v1/contributions/{c['id']}"
    for body in ({"amount": 0}, {"amount": None}, {"payment_status": "refunded"}, {"payment_status": None}):
        assert client.patch(url, json=body, headers=auth).status_code == 422, body
    assert client.patch(url, json={"notes": None}, headers=auth).json()["notes"] is None
    assert client.patch(f"/api/v1/contributions/{uuid.uuid4()}", json={"notes": "x"}, headers=auth).status_code == 404


def test_list_filter_and_delete(client, auth, make_friend, make_event, make_contribution):
    e = make_event()
    a = make_contribution(e["id"], make_friend("Ani")["id"])
    make_contribution(e["id"], make_friend("Bayu")["id"])
    _paid(client, auth, a["id"])
    url = f"/api/v1/events/{e['id']}/contributions"

    everyone = client.get(url, headers=auth).json()
    assert everyone["total"] == 2 and [i["friend"]["name"] for i in everyone["items"]] == ["Ani", "Bayu"]
    paid = client.get(url + "?payment_status=paid", headers=auth).json()
    assert [i["id"] for i in paid["items"]] == [a["id"]]
    assert client.get(url + "?payment_status=nope", headers=auth).status_code == 422

    assert client.delete(f"/api/v1/contributions/{a['id']}", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/contributions/{a['id']}", headers=auth).status_code == 404
    assert client.get(url, headers=auth).json()["total"] == 1
