from __future__ import annotations
import sys, requests
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api"
print("health", requests.get(base + "/health", timeout=10).status_code)
r = requests.post(base + "/auth/login", json={"email":"admin@apg-secure.com","password":"admin123"}, timeout=10)
print("login", r.status_code)
if r.ok:
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    print("monitoring", requests.get(base + "/admin/monitoring", headers=h, timeout=10).status_code)
    print("pdf", requests.get(base + "/admin/export/security-report.pdf", headers=h, timeout=20).status_code)
