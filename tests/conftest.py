import os


os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/cygnet_energy")


def pytest_addoption(parser) -> None:
    parser.addoption("--cov", action="store", default=None)
    parser.addoption("--cov-report", action="append", default=[])
