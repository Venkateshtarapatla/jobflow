def test_sync_endpoint_runs_job_inline(client):
    response = client.post("/benchmark/sync", json={"job_type": "fibonacci", "payload": {"n": 10}})
    assert response.status_code == 200
    assert response.json() == {"result": {"n": 10, "value": 55}}
