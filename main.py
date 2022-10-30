import argparse
from pathlib import Path

from environment import Environment
from exceptions import LoxError, LoxRuntimeError
from interpreter import Interpreter
from parser import Parser
from scanner import Scanner, Token, TokenType


class Lox:
    has_error: bool
    has_runtime_error: bool

    environment: Environment

    def __init__(self):
        self.has_error = False
        self.has_runtime_error = False
        self.environment = Environment()

    def run_file(self, path: Path):
        with path.open() as f:
            self.run(f.read())
        if self.has_error or self.has_runtime_error:
            raise LoxError

    def run(self, line: str):
        scanner = Scanner(self, line)
        tokens = scanner.scan_tokens()
        parser = Parser(self, tokens)
        statements = parser.parse()
        interpreter = Interpreter(self, self.environment)
        interpreter.interpret(statements)

    def run_prompt(self):
        while True:
            try:
                line = input("> ")
                self.run(line)
                self.has_error = False
            except EOFError:
                break

    def error(self, token: Token, message: str):
        if token.type == TokenType.EOF:
            self.report(token.line, "at end", message)
        else:
            self.report(token.line, f"at '{token.lexeme}'", message)

    def runtime_error(self, e: LoxRuntimeError):
        print(e.args[0] + f"\n [line {e.token.line}]")
        self.has_runtime_error = True

    def report(self, line: int, where: str, message: str):
        print(f"[line {line}] Error {where}: {message}")
        self.has_error = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path, nargs="?")
    args = parser.parse_args()
    lox = Lox()

    if args.script:
        lox.run_file(args.script)
    else:
        lox.run_prompt()
