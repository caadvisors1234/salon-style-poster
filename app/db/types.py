"""
カスタムのSQLAlchemyデータ型を定義します。
"""
import uuid
from sqlalchemy import types, Dialect

class Guid(types.TypeDecorator):
    """
    プラットフォーム非依存のGUID型。

    PostgreSQLではUUID、それ以外のDBではCHAR(32)を使用します。
    """
    impl = types.CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(types.UUID())
        else:
            return dialect.type_descriptor(types.CHAR(32))

    def process_bind_param(self, value, dialect: Dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # UUIDをハイフンなしの16進数文字列に変換
                return "%.32x" % value.int

    def process_result_value(self, value, dialect: Dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value
