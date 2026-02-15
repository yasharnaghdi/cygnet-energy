import os

os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/cygnet_energy")
os.environ.setdefault("AUTH_BYPASS_DEV", "true")
