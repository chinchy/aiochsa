import json
import pkg_resources
from typing import AsyncIterable

from aiohttp import StreamReader
from lark import Lark, Transformer, v_args

from .record import Record
from .types import TypeRegistry


__all__ = ['parse_type']


type_parser = Lark(
    pkg_resources.resource_string(__name__, 'type.lark').decode()
)


@v_args(inline=True)
class TypeTransformer(Transformer):

    def __init__(self, types: TypeRegistry):
        self._types = types

    def start(self, type_):
        return type_

    def composite_type(self, name, *types):
        return self._types[name](*types)

    def simple_type(self, name, *params):
        return self._types[name]()


def parse_type(types: TypeRegistry, type_str):
    tree = type_parser.parse(type_str)
    return TypeTransformer(types).transform(tree)


async def parse_json_compact(
    types: TypeRegistry, content: StreamReader,
) -> AsyncIterable[Record]:
    response = json.loads(await content.read(), parse_float=str)

    names = []
    converters = []
    for column in response['meta']:
        names.append(column['name'])
        type_obj = parse_type(types, column['type'])
        converters.append(type_obj.from_json)

    for row in response['data']:
        yield Record(
            names = names,
            values = [
                converter(value)
                for converter, value in zip(converters, row)
            ]
        )


if __name__ == '__main__':
    # TODO Covert this to proper tests
    tree = type_parser.parse(
        r"Tuple("
            r"UInt8, "
            r"Tuple(UInt8, Nullable(Nothing), String, Array(String)), "
            r"Decimal(9, 2), "
            r"Date, "
            r"IPv4, IPv6,"
            r"Nullable(Enum8('' = -128, 'a' = 1, '\t\n\0\\\'' = 2))"
        r")",
    )

    print(tree.pretty())

    t = TypeTransformer(TypeRegistry()).transform(tree)
    print(t)
