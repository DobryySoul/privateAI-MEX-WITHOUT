from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine, AsyncSession
from settings.config import config

URL = f"mysql+aiomysql://{config.DB.user}:{config.DB.password}@{config.DB.host}/{config.DB.database}?charset=utf8mb4"

engine = create_async_engine(
    URL,
    echo=False,
    pool_size=1000,
    max_overflow=2000,
    connect_args={"connect_timeout": 30}
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(AsyncAttrs, DeclarativeBase):
    pass

