"""
api/routes/auth_routes.py
==========================
Re-exports the auth router from api/auth.py.
The actual route handler lives in api/auth.py (alongside RBAC deps).

WHO OWNS THIS: Backend team
"""
from api.auth import router  # noqa: F401 — re-export for main.py include