from typing import Any

from scanner import Token


class LoxError(Exception):
    pass


class InterpreterError(LoxError):
    pass


class LoxRuntimeError(InterpreterError):
    token: Token

    def __init__(self, token=None, message=None, *args):
        super().__init__(message, *args)
        self.token = token


class ReturnError(InterpreterError):
    value: Any

    def __init__(self, value: Any):
        super().__init__()
        self.value = value
