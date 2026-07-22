from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

DATABASE_URL = "sqlite+aiosqlite:////database/studio.db"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"timeout": 15},
    echo=False
)

@event.listens_for(engine.sync_engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
