import time
from functools import singledispatchmethod
from typing import Any, TYPE_CHECKING

from environment import Environment
from exceptions import InterpreterError, LoxRuntimeError, ReturnError
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
    LoxCallable,
    LoxFunction,
    Print,
    Return,
    Stmt,
    Unary,
    Var,
    Variable,
    While,
)
from scanner import Token, TokenType
from visitor import Visitor

if TYPE_CHECKING:
    from main import Lox


class Clock(LoxCallable):
    @property
    def arity(self) -> int:
        return 0

    def call(self, interpreter: "Interpreter", arguments: list[Any]):
        return time.time()

    def __str__(self):
        return "<native fn>"


global_env = Environment()
global_env.define(Token(TokenType.IDENTIFIER, "clock", None, 0), Clock())


class Interpreter(Visitor):
    lox: "Lox"
    locals: dict[Expr, int]
    globals: Environment = global_env
    environment: Environment

    def __init__(self, lox: "Lox"):
        self.lox = lox
        self.environment = global_env
        self.locals = {}

    def interpret(self, statements: list[Stmt]):
        try:
            for statement in statements:
                self.execute(statement)
        except LoxRuntimeError as e:
            self.lox.runtime_error(e)

    @staticmethod
    def stringify(value):
        if value is None:
            return "nil"
        if isinstance(value, float):
            text = str(value)
            if text.endswith(".0"):
                return text[:-2]
            return text
        return str(value)

    def execute(self, stmt: Stmt):
        return stmt.accept(self)

    @singledispatchmethod
    def visit(self, expr):
        raise NotImplementedError

    @visit.register
    def _(self, expr: Literal):
        return expr.value

    @visit.register
    def _(self, expr: Grouping):
        return self.evaluate(expr.expression)

    @visit.register
    def _(self, expr: Logical):
        left = self.evaluate(expr.left)

        if expr.operator.type == TokenType.OR:
            if self.is_truthy(left):
                return left
        else:
            if not self.is_truthy(left):
                return left

        return self.evaluate(expr.right)

    @visit.register
    def _(self, expr: Unary):
        right = self.evaluate(expr.right)

        match expr.operator.type:
            case TokenType.MINUS:
                self.check_number_operand(expr.operator, right)
                return -right
            case TokenType.BANG:
                return not self.is_truthy(right)

        raise InterpreterError("should be unreachable")

    @visit.register
    def _(self, expr: Binary):
        left = self.evaluate(expr.left)
        right = self.evaluate(expr.right)

        match expr.operator.type:
            case TokenType.GREATER:
                self.check_number_operands(expr.operator, left, right)
                return float(left) > float(right)
            case TokenType.GREATER_EQUAL:
                self.check_number_operands(expr.operator, left, right)
                return float(left) >= float(right)
            case TokenType.LESS:
                self.check_number_operands(expr.operator, left, right)
                return float(left) < float(right)
            case TokenType.LESS_EQUAL:
                self.check_number_operands(expr.operator, left, right)
                return float(left) <= float(right)
            case TokenType.EQUAL_EQUAL:
                return left == right
            case TokenType.BANG_EQUAL:
                return left != right
            case TokenType.MINUS:
                self.check_number_operands(expr.operator, left, right)
                return left - right
            case TokenType.PLUS:
                if (isinstance(left, float) and isinstance(right, float)) or (
                    isinstance(left, str) and isinstance(right, str)
                ):
                    return left + right
                raise LoxRuntimeError(expr.operator, "Operands must be two numbers or two strings.")
            case TokenType.SLASH:
                self.check_number_operands(expr.operator, left, right)
                return left / right
            case TokenType.STAR:
                self.check_number_operands(expr.operator, left, right)
                return left * right

        raise InterpreterError("should be unreachable")

    @visit.register
    def _(self, expr: Variable):
        return self.lookup_variable(expr.name, expr)

    @visit.register
    def _(self, expr: Assign):
        value = self.evaluate(expr.value)

        try:
            distance = self.locals[expr]
            self.environment.assign_at(distance, expr.name, value)
        except KeyError:
            self.globals.assign(expr.name, value)

        return value

    @visit.register
    def _(self, expr: Call):
        callee = self.evaluate(expr.callee)

        if not isinstance(callee, LoxCallable):
            raise LoxRuntimeError(expr.paren, "Can only call functions and classes")

        arguments: list[Any] = [self.evaluate(arg) for arg in expr.arguments]

        func: LoxCallable = callee

        if len(arguments) != func.arity:
            raise LoxRuntimeError(expr.paren, f"Expected {func.arity} arguments but got {len(arguments)}.")

        return func.call(self, arguments)

    @visit.register
    def _(self, stmt: Expression):
        return self.evaluate(stmt.expression)

    @visit.register
    def _(self, stmt: Function):
        func = LoxFunction(stmt, self.environment)
        if stmt.name is not None:
            self.environment.define(stmt.name, func)

    @visit.register
    def _(self, stmt: Print) -> None:
        value = self.evaluate(stmt.expression)
        print(self.stringify(value))

    @visit.register
    def _(self, stmt: Return) -> None:
        value = None

        if stmt.value is not None:
            value = self.evaluate(stmt.value)

        raise ReturnError(value)

    @visit.register
    def _(self, stmt: Var) -> None:
        value = None
        if stmt.initializer is not None:
            value = self.evaluate(stmt.initializer)

        self.environment.define(stmt.name, value)

    @visit.register
    def _(self, stmt: While) -> None:
        while self.is_truthy(self.evaluate(stmt.condition)):
            self.execute(stmt.body)

    @visit.register
    def _(self, stmt: Block) -> None:
        self.execute_block(stmt.statements, Environment(self.environment))

    @visit.register
    def _(self, stmt: If) -> None:
        if self.is_truthy(self.evaluate(stmt.condition)):
            self.execute(stmt.then_branch)
        elif stmt.else_branch is not None:
            self.execute(stmt.else_branch)

        return None

    def resolve(self, expr: Expr, depth: int):
        self.locals[expr] = depth

    def lookup_variable(self, name: Token, expr: Expr):
        try:
            distance = self.locals[expr]
            return self.environment.get_at(distance, name)
        except KeyError:
            return self.globals.get(name)

    def execute_block(self, statements: list[Stmt], environment: Environment):
        previous = self.environment

        self.environment = environment

        try:
            for statement in statements:
                self.execute(statement)
        finally:
            self.environment = previous

    def is_truthy(self, value) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return True

    def check_number_operand(self, operator: Token, operand: Any):
        if isinstance(operand, float):
            return
        raise LoxRuntimeError(operator, "Operand must be a number.")

    def check_number_operands(self, operator: Token, l_operand: Any, r_operand: Any):
        if isinstance(l_operand, float) and isinstance(r_operand, float):
            return
        raise LoxRuntimeError(operator, "Operands must be a number.")

    def evaluate(self, expr: Expr):
        return expr.accept(self)
