from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.models import Base, ResultFile, ResultVersion


def test_result_files_flush_after_parent_with_foreign_keys_enabled():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            version = ResultVersion(
                id="test-version",
                label="Test version",
                status="active",
                params={},
                manifest={},
                panel_checksum="0" * 64,
                result_files=[
                    ResultFile(name="one.csv", compressed_content=b"one", sha256="1" * 64),
                    ResultFile(name="two.csv", compressed_content=b"two", sha256="2" * 64),
                ],
            )
            session.add(version)
            session.flush()

            stored_version = session.get(ResultVersion, "test-version")
            stored_files = session.execute(select(ResultFile).where(ResultFile.version_id == "test-version")).scalars().all()
            assert stored_version is not None
            assert {row.name for row in stored_files} == {"one.csv", "two.csv"}
            session.rollback()
    finally:
        engine.dispose()
