from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Visitor(ABC, Generic[T]):
    @abstractmethod
    def visit(self, expr: T):
        ...
