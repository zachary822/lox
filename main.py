import argparse
import sys
from pathlib import Path

from exceptions import LoxRuntimeError
from interpreter import Interpreter
from parser import Parser
from resolver import Resolver
from scanner import Scanner, Token, TokenType


class Lox:
    has_error: bool
    has_runtime_error: bool

    def __init__(self):
        self.has_error = False
        self.has_runtime_error = False

    def run_file(self, path: Path):
        with path.open() as f:
            self.run(f.read())
        if self.has_error or self.has_runtime_error:
            sys.exit(1)

    def run(self, line: str):
        scanner = Scanner(self, line)
        tokens = scanner.scan_tokens()
        parser = Parser(self, tokens)
        statements = parser.parse()

        if self.has_error:
            return

        interpreter = Interpreter(self)
        resolver = Resolver(self, interpreter)

        resolver.resolve(statements)

        if self.has_error:
            return

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
        print(e.args[0] + f"\n [line {e.token.line}]", file=sys.stderr)
        self.has_runtime_error = True

    def report(self, line: int, where: str, message: str):
        print(f"[line {line}] Error {where}: {message}", file=sys.stderr)
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
