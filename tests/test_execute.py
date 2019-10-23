from datetime import date, datetime
from decimal import Decimal
from enum import Enum

import pytest
import sqlalchemy as sa


async def test_ddl(conn, test_table):
    await conn.execute(sa.DDL(f'DROP TABLE {test_table.name}'))


@pytest.mark.xfail(
    raises=TypeError,
    # Is the game worth the candle? For it compilation can't be separated from
    # execution.
    reason='Execution of default is not supported yet',
)
async def test_execute_default(conn, test_table):
    ts_before = datetime.utcnow().replace(microsecond=0)
    now = await conn.fetchval(test_table.c.timestamp.default)
    ts_after = datetime.utcnow().replace(microsecond=0)
    assert ts_before <= now <= ts_after


async def test_func(conn):
    ts_before = datetime.utcnow().replace(microsecond=0)
    now = await conn.fetchval(sa.func.now())
    ts_after = datetime.utcnow().replace(microsecond=0)
    assert ts_before <= now <= ts_after


async def test_func_params(conn):
    result = await conn.fetchval(
        sa.func.plus(sa.bindparam('a'), sa.bindparam('b'))
            .params({'a': 12, 'b': 23})
    )
    assert result == 35


async def test_func_params_args(conn):
    result = await conn.fetchval(
        sa.func.plus(sa.bindparam('a'), sa.bindparam('b')),
        {'a': 12, 'b': 23},
    )
    assert result == 35


async def test_simple_round(conn, test_table):
    now = datetime.utcnow().replace(microsecond=0)
    values = {
        'id': 1,
        'enum': 'ONE',
        'name': 'test',
        'timestamp': now,
        'amount': Decimal('1.23'),
    }
    await conn.execute(
        test_table.insert()
            .values(values)
    )

    rows = await conn.fetch(test_table.select())
    row = await conn.fetchrow(test_table.select())
    assert rows == [row]
    assert row == values


async def test_non_ascii(conn, test_table):
    sample = 'зразок'
    await conn.execute(
        test_table.insert()
            .values(id=1, name=sample)
    )
    name = await conn.fetchval(
        sa.select([test_table.c.name])
            .where(test_table.c.id == 1)
    )
    assert name == sample


async def test_enum(conn, test_table):

    class EnumType(str, Enum):
        ONE = 'ONE'
        TWO = 'TWO'

    await conn.execute(
        test_table.insert()
            .values(id=1, enum=EnumType.ONE)
    )
    value = await conn.fetchval(
        sa.select([test_table.c.enum])
            .where(test_table.c.id == 1)
    )
    assert value == EnumType.ONE


async def test_unsupported_type(conn):
    with pytest.raises(TypeError):
        await conn.fetchval(
            sa.select([sa.bindparam('a')])
                .params(a=...)
        )


async def test_defaults(conn, test_table):
    ts_before = datetime.utcnow().replace(microsecond=0)
    values = {
        'id': 1,
        'enum': 'ONE',
        'name': 'test',
    }
    await conn.execute(
        test_table.insert()
            .values(values)
    )
    ts_after = datetime.utcnow().replace(microsecond=0)

    row = await conn.fetchrow(test_table.select())
    for field, value in values.items():
        assert row[field] == value
    assert ts_before <= row['timestamp'] <= ts_after
    assert row['amount'] == Decimal(0)


async def test_insert_multiple(conn, test_table):
    values = [
        {
            'id': i + 1,
            'name': f'test{i + 1}',
            'enum': 'TWO' if i % 2 else 'ONE',
        }
        for i in range(6)
    ]
    await conn.execute(
        test_table.insert()
            .values(values)
    )

    rows = await conn.fetch(
        sa.select([test_table.c.id])
            .where(test_table.c.enum == 'ONE')
            .order_by(test_table.c.id.desc())
    )
    assert [item_id for (item_id,) in rows] == [5, 3, 1]


async def test_insert_multiple_args(conn, test_table):
    values = [
        {'id': i + 1, 'name': f'test{i + 1}'}
        for i in range(3)
    ]
    await conn.execute(
        test_table.insert(), *values,
    )

    rows = await conn.fetch(
        sa.select([test_table.c.id, test_table.c.name])
    )
    assert rows == values


async def test_join(conn, test_table):
    await conn.execute(
        test_table.insert(),
        *[
            {'id': i + 1, 'name': f'test{i + 1}'}
            for i in range(3)
        ],
    )

    test_alias = test_table.alias()
    rows = await conn.fetch (
        sa.select([test_table.c.id, test_alias.c.id])
            .select_from(
                test_table.join(
                    test_alias,
                    test_alias.c.id == test_table.c.id,
                )
            )
    )
    assert {tuple(row) for row in rows} == {(1, 1), (2, 2), (3, 3)}


async def test_select_params(conn, test_table):
    await conn.execute(
        test_table.insert(),
        *[
            {'id': i + 1, 'name': f'test{i + 1}'}
            for i in range(3)
        ],
    )

    rows = await conn.fetch(
        sa.select([test_table.c.id])
            .where(test_table.c.id >= sa.bindparam('min_id'))
            .params(min_id=2)
    )
    assert [item_id for (item_id,) in rows] == [2, 3]


async def test_select_params_args(conn, test_table):
    await conn.execute(
        test_table.insert(),
        *[
            {'id': i + 1, 'name': f'test{i + 1}'}
            for i in range(3)
        ],
    )

    rows = await conn.fetch(
        sa.select([test_table.c.id])
            .where(test_table.c.id >= sa.bindparam('min_id')),
        {'min_id': 2},
    )
    assert [item_id for (item_id,) in rows] == [2, 3]


async def test_nested_structures(conn):
    value = await conn.fetchval(
        r"SELECT ("
            r"1, "
            r"(2, NULL, 'a\nb\tc\0d\'', ['a', '\'']),"
            r"1.23, toDecimal32('1.23', 2), toDate('2000-01-01')"
        r")"
    )
    assert value == (
        1,
        (2, None, 'a\nb\tc\0d\'', ['a', '\'']),
        1.23, Decimal('1.23'), date(2000, 1, 1)
    )
