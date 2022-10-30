from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

from environment import Environment
from exceptions import LoxError, ReturnError
from scanner import Token, TokenType
from visitor import Visitor

if TYPE_CHECKING:
    from main import Lox
    from interpreter import Interpreter


class ParseError(LoxError):
    pass


class LoxCallable(ABC):
    @property
    @abstractmethod
    def arity(self) -> int:
        ...

    @abstractmethod
    def call(self, interpreter: "Interpreter", arguments: list[Any]):
        ...


class LoxFunction(LoxCallable):
    declaration: "Function"
    closure: Environment

    def __init__(self, declaration: "Function", closure: Environment):
        self.declaration = declaration
        self.closure = closure

    @property
    def arity(self) -> int:
        return len(self.declaration.params)

    def call(self, interpreter: "Interpreter", arguments: list[Any]):
        environment = Environment(self.closure)

        for param, argument in zip(self.declaration.params, arguments):
            environment.define(param, argument)

        try:
            interpreter.execute_block(self.declaration.body, environment)
        except ReturnError as e:
            return e.value

    def __str__(self):
        if self.declaration.name is not None:
            return f"<fn {self.declaration.name.lexeme}>"
        return "<fn>"


class Expr(ABC):
    def accept(self, visitor: "Visitor[Expr]"):
        return visitor.visit(self)


class Assign(Expr):
    name: Token
    value: Expr

    def __init__(self, name: Token, value: Expr):
        self.name = name
        self.value = value


class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr

    def __init__(self, left: Expr, operator: Token, right: Expr):
        self.left = left
        self.operator = operator
        self.right = right


class Call(Expr):
    callee: Expr
    paren: Token
    arguments: list[Expr]

    def __init__(self, callee: Expr, paren: Token, arguments: list[Expr]):
        self.callee = callee
        self.paren = paren
        self.arguments = arguments


class Grouping(Expr):
    expression: Expr

    def __init__(self, expression: Expr):
        self.expression = expression


class Literal(Expr):
    def __init__(self, value: Any):
        self.value = value


class Logical(Expr):
    left: Expr
    operator: Token
    right: Expr

    def __init__(self, left: Expr, operator: Token, right: Expr):
        self.left = left
        self.operator = operator
        self.right = right


class Unary(Expr):
    operator: Token
    right: Expr

    def __init__(self, operator: Token, right: Expr):
        self.operator = operator
        self.right = right


class Variable(Expr):
    name: Token

    def __init__(self, name: Token):
        self.name = name


class Stmt(ABC):
    def accept(self, visitor: "Visitor[Stmt]"):
        return visitor.visit(self)


class Expression(Stmt):
    expression: Optional[Expr]

    def __init__(self, expression: Optional[Expr]):
        self.expression = expression


class Function(Stmt, Expr):
    name: Optional[Token]
    params: list[Token]
    body: list[Stmt]

    def __init__(self, name: Optional[Token], params: list[Token], body: list[Stmt]):
        self.name = name
        self.params = params
        self.body = body


class If(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt

    def __init__(self, condition: Expr, then_branch: Stmt, else_branch: Stmt):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch


class Print(Stmt):
    expression: Expr

    def __init__(self, expression: Expr):
        self.expression = expression


class Return(Stmt):
    keyword: Token
    value: Expr

    def __init__(self, keyword: Token, value: Expr):
        self.keyword = keyword
        self.value = value


class Var(Stmt):
    name: Token
    initializer: Optional[Expr]

    def __init__(self, name: Token, initializer: Expr):
        self.name = name
        self.initializer = initializer


class While(Stmt):
    condition: Expr
    body: Stmt

    def __init__(self, condition: Expr, body: Stmt):
        self.condition = condition
        self.body = body


class Block(Stmt):
    statements: list[Stmt]

    def __init__(self, statements: list[Stmt]):
        self.statements = statements


class Parser:
    tokens: list[Token]
    current: int

    def __init__(self, lox: "Lox", tokens: list[Token]):
        self.lox = lox
        self.tokens = tokens
        self.current = 0

    def parse(self) -> list[Stmt]:
        statements: list[Stmt] = []
        while not self.is_at_end:
            statements.append(self.declaration())

        return statements

    def declaration(self):
        try:
            if self.match(TokenType.FUN):
                return self.function("function")
            if self.match(TokenType.VAR):
                return self.var_declaration()
            return self.statement()
        except ParseError:
            self.synchronize()
            return None

    def statement(self) -> Stmt:
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.PRINT):
            return self.print_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.LEFT_BRACE):
            return Block(self.block())
        return self.expression_statement()

    def expression_statement(self) -> Stmt:
        value: Optional[Expr] = None
        if not self.check(TokenType.SEMICOLON):
            value = self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after value.")
        return Expression(value)

    def print_statement(self) -> Stmt:
        value = self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after value.")
        return Print(value)

    def return_statement(self):
        keyword = self.previous()
        value = None
        if not self.check(TokenType.SEMICOLON):
            value = self.expression()

        self.consume(TokenType.SEMICOLON, "Expect ';' after return value.")
        return Return(keyword, value)

    def while_statement(self) -> Stmt:
        self.consume(TokenType.LEFT_PAREN, "Expect '(' after 'while'.")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after condition.")
        body = self.statement()

        return While(condition, body)

    def block(self) -> list[Stmt]:
        statements: list[Stmt] = []

        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end:
            statements.append(self.declaration())

        self.consume(TokenType.RIGHT_BRACE, "Expect '}' after block.")

        return statements

    def function(self, kind: str):
        name: Optional[Token] = None
        if self.check(TokenType.IDENTIFIER):
            name = self.consume(TokenType.IDENTIFIER, f"Expect {kind} name")

        self.consume(TokenType.LEFT_PAREN, f"Expect '(' after {kind} name.")

        parameters: list[Token] = []
        if not self.check(TokenType.RIGHT_PAREN):
            while True:
                if len(parameters) >= 255:
                    self.error(self.peek(), "Can't have more than 255 parameters.")

                parameters.append(self.consume(TokenType.IDENTIFIER, "Expect parameter name."))

                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after parameters.")

        self.consume(TokenType.LEFT_BRACE, f"Expect '{{' before {kind} body.")
        body = self.block()

        return Function(name, parameters, body)

    def var_declaration(self):
        name = self.consume(TokenType.IDENTIFIER, "Expect variable name.")

        initializer: Optional[Expr] = None

        if self.match(TokenType.EQUAL):
            initializer = self.expression()

        self.consume(TokenType.SEMICOLON, "Expect ';' after variable declaration")
        return Var(name, initializer)

    def for_statement(self) -> Stmt:
        self.consume(TokenType.LEFT_PAREN, "Expect '(' after for.")

        initializer: Optional[Stmt]
        if self.match(TokenType.SEMICOLON):
            initializer = None
        elif self.match(TokenType.VAR):
            initializer = self.var_declaration()
        else:
            initializer = self.expression_statement()

        condition: Optional[Expr] = None
        if not self.check(TokenType.SEMICOLON):
            condition = self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after loop condition.")

        increment: Optional[Expr] = None
        if not self.check(TokenType.RIGHT_PAREN):
            increment = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after for clauses.")

        body = self.statement()

        if increment is not None:
            body = Block(
                [
                    body,
                    Expression(increment),
                ]
            )

        if condition is None:
            condition = Literal(True)

        body = While(condition, body)

        if initializer is not None:
            body = Block(
                [
                    initializer,
                    body,
                ]
            )

        return body

    def if_statement(self) -> Stmt:
        self.consume(TokenType.LEFT_PAREN, "Expect '(' after 'if'.")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after if condition")
        then_branch = self.statement()
        else_branch = None
        if self.match(TokenType.ELSE):
            else_branch = self.statement()

        return If(condition, then_branch, else_branch)

    def expression(self) -> Expr:
        return self.assignment()

    def assignment(self) -> Expr:
        expr = self.logical_or()

        if self.match(TokenType.EQUAL):
            equals = self.previous()
            value = self.assignment()

            if isinstance(expr, Variable):
                name = expr.name
                return Assign(name, value)

            self.error(equals, "Invalid assignment target.")

        return expr

    def logical_or(self) -> Expr:
        expr = self.logical_and()

        while self.match(TokenType.OR):
            operator = self.previous()
            right = self.logical_and()
            expr = Logical(expr, operator, right)

        return expr

    def logical_and(self) -> Expr:
        expr = self.equality()

        while self.match(TokenType.AND):
            operator = self.previous()
            right = self.equality()
            expr = Logical(expr, operator, right)

        return expr

    def equality(self) -> Expr:
        expr = self.comparison()

        while self.match(TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL):
            operator = self.previous()
            right = self.comparison()
            expr = Binary(expr, operator, right)

        return expr

    def comparison(self) -> Expr:
        expr = self.term()

        while self.match(TokenType.GREATER, TokenType.GREATER_EQUAL, TokenType.LESS, TokenType.LESS_EQUAL):
            operator = self.previous()
            right = self.term()
            expr = Binary(expr, operator, right)

        return expr

    def term(self) -> Expr:
        expr = self.factor()

        while self.match(TokenType.MINUS, TokenType.PLUS):
            operator = self.previous()
            right = self.factor()
            expr = Binary(expr, operator, right)

        return expr

    def factor(self) -> Expr:
        expr = self.unary()

        while self.match(TokenType.SLASH, TokenType.STAR):
            operator = self.previous()
            right = self.unary()
            expr = Binary(expr, operator, right)

        return expr

    def unary(self) -> Expr:
        if self.match(TokenType.BANG, TokenType.MINUS):
            operator = self.previous()
            right = self.unary()
            return Unary(operator, right)
        return self.call()

    def call(self) -> Expr:
        expr = self.primary()

        while True:
            if self.match(TokenType.LEFT_PAREN):
                expr = self.finish_call(expr)
            else:
                break

        return expr

    def finish_call(self, callee: Expr) -> Call:
        arguments = []

        if not self.check(TokenType.RIGHT_PAREN):
            while True:
                arguments.append(self.expression())
                if len(arguments) >= 255:
                    self.error(self.peek(), "Can't have more than 255 arguments.")
                if not self.match(TokenType.COMMA):
                    break

        paren = self.consume(TokenType.RIGHT_PAREN, "Expect ')' after arguments.")

        return Call(callee, paren, arguments)

    def primary(self) -> Expr:
        if self.match(TokenType.FALSE):
            return Literal(False)
        if self.match(TokenType.TRUE):
            return Literal(True)
        if self.match(TokenType.NIL):
            return Literal(None)

        if self.match(TokenType.NUMBER, TokenType.STRING):
            return Literal(self.previous().literal)

        if self.match(TokenType.FUN):
            return self.function("function")

        if self.match(TokenType.IDENTIFIER):
            return Variable(self.previous())

        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expect ')' after expression.")
            return Grouping(expr)
        raise self.error(self.peek(), "Expect expression.")

    def match(self, *types: TokenType) -> bool:
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def advance(self):
        if not self.is_at_end:
            self.current += 1
        return self.previous()

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def check(self, type_: TokenType) -> bool:
        if self.is_at_end:
            return False
        return self.peek().type == type_

    def peek(self) -> Token:
        return self.tokens[self.current]

    def consume(self, type_: TokenType, message: str):
        if self.check(type_):
            return self.advance()
        raise self.error(self.peek(), message)

    def error(self, token, message):
        self.lox.error(token, message)
        return ParseError

    def synchronize(self):
        self.advance()

        while not self.is_at_end:
            if self.previous().type == TokenType.SEMICOLON:
                return
            match self.peek().type:
                case (
                    TokenType.CLASS
                    | TokenType.FUN
                    | TokenType.VAR
                    | TokenType.FOR
                    | TokenType.IF
                    | TokenType.WHILE
                    | TokenType.PRINT
                    | TokenType.RETURN
                ):
                    return
            self.advance()

    @property
    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF
