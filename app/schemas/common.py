"""通用响应模型。"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页响应外壳：当前页数据 + 总数 + 当前窗口。"""

    items: list[T]
    total: int
    limit: int
    offset: int
