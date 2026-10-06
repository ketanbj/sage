"""CPU exception names exported by the pinned Einsums Python module."""


class rank_error(ValueError):
    pass


class dimension_error(ValueError):
    pass


class SingularError(RuntimeError):
    pass


class ConvergenceError(RuntimeError):
    pass


for _name in (
    "tensor_compat_error",
    "num_argument_error",
    "not_enough_args",
    "too_many_args",
    "access_denied",
    "todo_error",
    "not_implemented",
    "bad_logic",
    "uninitialized_error",
    "system_error",
    "enum_error",
):
    globals()[_name] = type(_name, (RuntimeError,), {"__module__": __name__})
