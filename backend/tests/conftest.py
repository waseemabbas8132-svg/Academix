from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import AcademicClass, Announcement, ClassMembership  # noqa: F401
from app.services.file_storage import LocalFileStorage, get_file_storage

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def isolate_upload_storage(tmp_path_factory: pytest.TempPathFactory):
    storage = LocalFileStorage(tmp_path_factory.mktemp("academix-uploads"), 1024 * 1024)
    app.dependency_overrides[get_file_storage] = lambda: storage
    yield
    app.dependency_overrides.pop(get_file_storage, None)
