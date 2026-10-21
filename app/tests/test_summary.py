def _setup(client, auth, make_friend, make_event, make_contribution, **event_kw):
    e = make_event(**event_kw)
    ids = []
    for name, amount in [("A", 100_000), ("B", 50_000), ("C", 25_000)]:
        ids.append(make_contribution(e["id"], make_friend(name)["id"], amount)["id"])
    return e, ids


def test_empty_event_summary(client, auth, make_event):
    e = make_event(target_amount=1_000_000)
    s = client.get(f"/api/v1/events/{e['id']}/summary", headers=auth).json()
    assert s == {
        "event_id": e["id"],
        "total_participants": 0,
        "paid_count": 0,
        "pending_count": 0,
        "total_collected": 0,
        "total_pending": 0,
        "target_amount": 1_000_000,
        "progress_percent": 0,
    }


def test_summary_counts_only_paid_as_collected(client, auth, make_friend, make_event, make_contribution):
    e, ids = _setup(client, auth, make_friend, make_event, make_contribution, target_amount=400_000)
    client.patch(f"/api/v1/contributions/{ids[0]}", json={"payment_status": "paid"}, headers=auth)
    client.patch(f"/api/v1/contributions/{ids[2]}", json={"payment_status": "paid"}, headers=auth)
    s = client.get(f"/api/v1/events/{e['id']}/summary", headers=auth).json()
    assert (s["total_participants"], s["paid_count"], s["pending_count"]) == (3, 2, 1)
    assert s["total_collected"] == 125_000
    assert s["total_pending"] == 50_000
    assert s["progress_percent"] == 31  # floor(125000*100/400000) = 31

    # moving a contribution back to pending removes it from collected
    client.patch(f"/api/v1/contributions/{ids[0]}", json={"payment_status": "pending"}, headers=auth)
    s = client.get(f"/api/v1/events/{e['id']}/summary", headers=auth).json()
    assert s["total_collected"] == 25_000 and s["total_pending"] == 150_000


def test_progress_not_capped_and_null_without_target(client, auth, make_friend, make_event, make_contribution):
    e, ids = _setup(client, auth, make_friend, make_event, make_contribution, target_amount=100_000)
    client.patch(f"/api/v1/contributions/{ids[0]}", json={"payment_status": "paid"}, headers=auth)
    client.patch(f"/api/v1/contributions/{ids[1]}", json={"payment_status": "paid"}, headers=auth)
    assert client.get(f"/api/v1/events/{e['id']}/summary", headers=auth).json()["progress_percent"] == 150

    client.patch(f"/api/v1/events/{e['id']}", json={"target_amount": 0}, headers=auth)
    s = client.get(f"/api/v1/events/{e['id']}/summary", headers=auth).json()
    assert s["target_amount"] == 0 and s["progress_percent"] is None

    client.patch(f"/api/v1/events/{e['id']}", json={"target_amount": None}, headers=auth)
    s = client.get(f"/api/v1/events/{e['id']}/summary", headers=auth).json()
    assert s["target_amount"] is None and s["progress_percent"] is None
    assert s["total_collected"] == 150_000
