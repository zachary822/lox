from collections import deque
from functools import singledispatchmethod
from typing import TYPE_CHECKING
from enum import Enum, auto

from interpreter import Interpreter
from parser import (
    Assign,
    Binary,
    Block,
    Call,
    Expr,
    Expression,
    Function,
    Grouping,
    If,
    Literal,
    Logical,
    Print,
    Return,
    Stmt,
    Unary,
    Var,
    Variable,
    While,
)
from scanner import Token
from visitor import Visitor

if TYPE_CHECKING:
    from main import Lox


class FunctionType(Enum):
    NONE = auto()
    FUNCTION = auto()


class Resolver(Visitor):
    lox: "Lox"
    interpreter: Interpreter
    scopes: deque[dict[Token, bool]]
    current_function: FunctionType

    def __init__(self, lox: "Lox", interpreter: Interpreter):
        self.lox = lox
        self.interpreter = interpreter
        self.scopes = deque()

        self.current_function = FunctionType.NONE

    @singledispatchmethod
    def visit(self, stmt):
        raise NotImplementedError

    @visit.register
    def _(self, stmt: Block):
        self.begin_scope()
        self.resolve(stmt.statements)
        self.end_scope()

    @visit.register
    def _(self, stmt: Var):
        self.declare(stmt.name)
        if stmt.initializer is not None:
            self.resolve(stmt.initializer)
        self.define(stmt.name)

    @visit.register
    def _(self, expr: Variable):
        if self.scopes and self.scopes[-1].get(expr.name) is False:
            self.lox.error(expr.name, "Can't read local variable in its own initializer.")

        self.resolve_local(expr, expr.name)

    @visit.register
    def _(self, expr: Assign):
        self.resolve(expr.value)
        self.resolve_local(expr, expr.name)

    @visit.register
    def _(self, stmt: Function):
        self.declare(stmt.name)
        self.define(stmt.name)

        self.resolve(stmt, FunctionType.FUNCTION)

    @visit.register
    def _(self, stmt: Expression):
        self.resolve(stmt.expression)

    @visit.register
    def _(self, stmt: If):
        self.resolve(stmt.condition)
        self.resolve(stmt.then_branch)

        if stmt.else_branch is not None:
            self.resolve(stmt.else_branch)

    @visit.register
    def _(self, stmt: Print):
        self.resolve(stmt.expression)

    @visit.register
    def _(self, stmt: Return):
        if self.current_function == FunctionType.NONE:
            self.lox.error(stmt.keyword, "Can't return from top-level code.")

        if stmt.value is not None:
            self.resolve(stmt.value)

    @visit.register
    def _(self, stmt: While):
        self.resolve(stmt.condition)
        self.resolve(stmt.body)

    @visit.register
    def _(self, expr: Binary):
        self.resolve(expr.left)
        self.resolve(expr.right)

    @visit.register
    def _(self, expr: Call):
        self.resolve(expr.callee)

        for argument in expr.arguments:
            self.resolve(argument)

    @visit.register
    def _(self, expr: Grouping):
        self.resolve(expr.expression)

    @visit.register
    def _(self, expr: Literal):
        pass

    @visit.register
    def _(self, expr: Logical):
        self.resolve(expr.left)
        self.resolve(expr.right)

    @visit.register
    def _(self, expr: Unary):
        self.resolve(expr.right)

    @singledispatchmethod
    def resolve(self, obj):
        raise NotImplementedError

    @resolve.register
    def _(self, expr: Expr):
        expr.accept(self)

    @resolve.register
    def _(self, stmt: Stmt):
        stmt.accept(self)

    @resolve.register(list)
    def _(self, statements: list[Stmt]):
        for statement in statements:
            statement.accept(self)

    @resolve.register
    def _(self, func: Function, func_type: FunctionType):
        enclosing_function = self.current_function
        self.current_function = func_type

        self.begin_scope()
        for param in func.params:
            self.declare(param)
            self.define(param)

        self.resolve(func.body)
        self.end_scope()

        self.current_function = enclosing_function

    def begin_scope(self):
        self.scopes.append({})

    def end_scope(self):
        self.scopes.pop()

    def declare(self, name: Token):
        if not self.scopes:
            return
        scope = self.scopes[-1]

        if name in scope:
            self.lox.error(name, "Already a variable with this name in this scope.")

        scope[name] = False

    def define(self, name: Token):
        if not self.scopes:
            return
        scope = self.scopes[-1]
        scope[name] = True

    def resolve_local(self, expr: Expr, name: Token):
        for i, scope in zip(range(len(self.scopes) - 1, -1, -1), reversed(self.scopes)):
            if name in scope:
                self.interpreter.resolve(expr, len(self.scopes) - 1 - i)
                break
