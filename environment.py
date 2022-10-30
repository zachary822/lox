from typing import Any, Optional

from exceptions import LoxRuntimeError
from scanner import Token


class Environment:
    values: dict[Token, Any]
    enclosing: "Environment"

    def __init__(self, enclosing: Optional["Environment"] = None):
        self.enclosing = enclosing
        self.values = {}

    def set_global(self, env: "Environment") -> None:
        if self.enclosing is env:
            return

        if self.enclosing is None:
            self.enclosing = env
        else:
            self.enclosing.set_global(env)

    def define(self, name: Token, value: Any):
        self.values[name] = value

    def get(self, name: Token):
        try:
            return self.values[name]
        except KeyError as e:
            if self.enclosing is not None:
                return self.enclosing.get(name)
            raise LoxRuntimeError(name, f"Undefined variable '{name.lexeme}'.") from e

    def assign(self, name: Token, value: Any):
        if name in self.values:
            self.values[name] = value
            return

        if self.enclosing is not None:
            self.enclosing.assign(name, value)
            return

        raise LoxRuntimeError(name, f"Undefined variable '{name.lexeme}'.")
