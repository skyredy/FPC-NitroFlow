def prepare(store):
    for row in store.rows("SELECT * FROM orders WHERE state IN ('ready','delivered')"):
        store.enqueue(row["id"], "credentials", "credentials:"+row["id"])
        if row["state"] == "delivered":
            store.enqueue(row["id"], "completion", "completion:"+row["id"])
            store.enqueue(row["id"], "reminder", "reminder:"+row["id"], row["delivered_at"]+86400)
