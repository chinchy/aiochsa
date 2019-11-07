import asyncio
from datetime import datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa

import aiochsa
from aiochsa import error_codes
from aiochsa.dialect import ClickhouseSaDialect


def pytest_collection_modifyitems(items):
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker('asyncio')


@pytest.fixture(scope='session')
def dsn(docker_services):
    docker_services.start('clickhouse-server')
    public_port = docker_services.wait_for_service('clickhouse-server', 8123)
    return f'clickhouse://{docker_services.docker_ip}:{public_port}'


@pytest.fixture
async def pool(dsn):
    async with aiochsa.create_pool(dsn) as pool:
        yield pool


@pytest.fixture
async def conn(dsn):
    async with aiochsa.connect(dsn) as conn:
        yield conn


@pytest.fixture
def recreate_table(conn):

    async def _recreate(table_name, create_ddl):
        try:
            await conn.execute(f'DROP TABLE {table_name}')
        except aiochsa.DBException as exc:
            if exc.code != error_codes.UNKNOWN_TABLE:
                raise

        await conn.execute(create_ddl)

    return _recreate


TEST1_CREATE_DDL = '''\
CREATE TABLE test1
(
    id UInt64,
    enum Enum8(''=0, 'ONE'=1, 'TWO'=2),
    name String,
    timestamp DateTime,
    amount Decimal64(9)
)
ENGINE = MergeTree()
ORDER BY id
'''


@pytest.fixture
async def table_test1(recreate_table):
    await recreate_table('test1', TEST1_CREATE_DDL)

    return sa.Table(
        'test1', sa.MetaData(),
        sa.Column('id', sa.Integer),
        sa.Column('enum', sa.Enum, default=''),
        sa.Column('name', sa.String),
        sa.Column('timestamp', sa.DateTime, default=datetime.utcnow),
        sa.Column('amount', sa.DECIMAL, default=Decimal(0)),
    )


TEST2_CREATE_DDL = '''\
CREATE TABLE test2
(
    title String,
    num UInt64
)
ENGINE = MergeTree()
ORDER BY num
'''


@pytest.fixture
async def table_test2(recreate_table):
    await recreate_table('test2', TEST2_CREATE_DDL)

    return sa.Table(
        'test2', sa.MetaData(),
        sa.Column('title', sa.String),
        sa.Column('num', sa.Integer),
    )


TABLE_FOR_TYPE_DDL_TEMPLATE = '''\
CREATE TABLE test_for_type
(
    value {type}
)
ENGINE = Log()
'''


@pytest.fixture
def table_for_type(recreate_table):

    async def _create(sa_type):
        if isinstance(sa_type, type):
            sa_type = sa_type()
        type_str = sa_type.compile(dialect=ClickhouseSaDialect())

        create_ddl = TABLE_FOR_TYPE_DDL_TEMPLATE.format(type=type_str)
        await recreate_table('test_for_type', create_ddl)

        return sa.Table(
            'test_for_type', sa.MetaData(),
            sa.Column('value', sa_type),
        )

    return _create
