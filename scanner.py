from dataclasses import dataclass
from enum import Enum, auto, unique
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from main import Lox


@unique
class TokenType(Enum):
    # single character
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COMMA = auto()
    DOT = auto()
    MINUS = auto()
    PLUS = auto()
    SEMICOLON = auto()
    SLASH = auto()
    STAR = auto()

    # one or two character
    BANG = auto()
    BANG_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()

    # literals
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()

    # keywords
    AND = auto()
    CLASS = auto()
    ELSE = auto()
    FALSE = auto()
    FUN = auto()
    FOR = auto()
    IF = auto()
    NIL = auto()
    OR = auto()
    PRINT = auto()
    RETURN = auto()
    SUPER = auto()
    THIS = auto()
    TRUE = auto()
    VAR = auto()
    WHILE = auto()

    EOF = auto()


@dataclass
class Token:
    type: TokenType
    lexeme: str
    literal: Any
    line: int

    def __repr__(self):
        return f"{self.type} {self.lexeme} {self.literal}"

    def __eq__(self, other: "Token"):
        return (self.type, self.lexeme, self.literal) == (other.type, other.lexeme, other.literal)

    def __hash__(self):
        return hash((self.type, self.lexeme, self.literal))


class Scanner:
    keywords: dict[str, TokenType] = {
        "and": TokenType.AND,
        "class": TokenType.CLASS,
        "else": TokenType.ELSE,
        "false": TokenType.FALSE,
        "for": TokenType.FOR,
        "fun": TokenType.FUN,
        "if": TokenType.IF,
        "nil": TokenType.NIL,
        "or": TokenType.OR,
        "print": TokenType.PRINT,
        "return": TokenType.RETURN,
        "super": TokenType.SUPER,
        "this": TokenType.THIS,
        "true": TokenType.TRUE,
        "var": TokenType.VAR,
        "while": TokenType.WHILE,
    }

    start: int
    current: int
    line: int
    tokens: list[Token]

    def __init__(self, lox: "Lox", source: str):
        self.lox = lox
        self.source = source
        self.tokens = []
        self.start = 0
        self.current = 0
        self.line = 1

    def scan_tokens(self) -> list[Token]:
        while not self.is_end:
            self.start = self.current
            self.scan_token()

        self.tokens.append(Token(TokenType.EOF, "", None, self.line))

        return self.tokens

    def scan_token(self):
        c = self.advance()
        match c:
            case "(":
                self.add_token(TokenType.LEFT_PAREN)
            case ")":
                self.add_token(TokenType.RIGHT_PAREN)
            case "{":
                self.add_token(TokenType.LEFT_BRACE)
            case "}":
                self.add_token(TokenType.RIGHT_BRACE)
            case ",":
                self.add_token(TokenType.COMMA)
            case ".":
                self.add_token(TokenType.DOT)
            case "-":
                self.add_token(TokenType.MINUS)
            case "+":
                self.add_token(TokenType.PLUS)
            case ";":
                self.add_token(TokenType.SEMICOLON)
            case "*":
                self.add_token(TokenType.STAR)
            case "!":
                self.add_token(TokenType.BANG_EQUAL if self.match("=") else TokenType.BANG)
            case "=":
                self.add_token(TokenType.EQUAL_EQUAL if self.match("=") else TokenType.EQUAL)
            case "<":
                self.add_token(TokenType.LESS_EQUAL if self.match("=") else TokenType.LESS)
            case ">":
                self.add_token(TokenType.GREATER_EQUAL if self.match("=") else TokenType.GREATER)
            case "/":
                if self.match("/"):
                    while self.peek() != "\n" and not self.is_end:
                        self.advance()
                elif self.match("*"):
                    while not (self.peek() == "*" and self.peek_next() == "/") and not self.is_end:
                        self.advance()
                    self.current += 2  # skipping */
                else:
                    self.add_token(TokenType.SLASH)
            case " " | "\r" | "\t":
                pass
            case "\n":
                self.line += 1
            case '"':
                self.string()
            case _:
                if self.is_digit(c):
                    self.number()
                elif self.is_alpha(c):
                    self.identifier()
                else:
                    self.lox.report(self.line, "", "Unexpected character")

    def advance(self) -> str:
        current, self.current = self.current, self.current + 1
        return self.source[current]

    def match(self, expected: str) -> bool:
        if self.is_end:
            return False
        if self.source[self.current] != expected:
            return False
        self.current += 1
        return True

    def peek(self) -> str:
        if self.is_end:
            return "\0"
        return self.source[self.current]

    def peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return "\0"
        return self.source[self.current + 1]

    def add_token(self, type_: TokenType, literal: Any = None):
        text = self.source[self.start : self.current]
        self.tokens.append(Token(type_, text, literal, self.line))

    def string(self) -> None:
        while self.peek() != '"' and not self.is_end:
            if self.peek() == "\n":
                self.line += 1
            self.advance()

        if self.is_end:
            self.lox.report(self.line, "", "Unterminated string.")
            return

        self.advance()

        value = self.source[self.start + 1:self.current - 1]
        self.add_token(TokenType.STRING, value)

    def number(self) -> None:
        while self.is_digit(self.peek()):
            self.advance()

        if self.peek() == "." and self.is_digit(self.peek_next()):
            self.advance()

            while self.is_digit(self.peek()):
                self.advance()

        self.add_token(TokenType.NUMBER, float(self.source[self.start:self.current]))

    def identifier(self):
        while self.is_alphanumeric(self.peek()):
            self.advance()

        text = self.source[self.start:self.current]
        try:
            self.add_token(self.keywords[text])
        except KeyError:
            self.add_token(TokenType.IDENTIFIER)

    @staticmethod
    def is_digit(c):
        return "0" <= c <= "9"

    @staticmethod
    def is_alpha(c):
        return ("a" <= c <= "z") or ("A" <= c <= "Z") or (c == "_")

    @classmethod
    def is_alphanumeric(cls, c):
        return cls.is_alpha(c) or cls.is_digit(c)

    @property
    def is_end(self) -> bool:
        return self.current >= len(self.source)
