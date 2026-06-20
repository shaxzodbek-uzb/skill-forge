"""A tiny greeter library used to demo skill-forge."""

__all__ = ["greet", "farewell"]


def greet(name: str) -> str:
    return f"Hello, {name}!"


def farewell(name: str) -> str:
    return f"Goodbye, {name}!"
