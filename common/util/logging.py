from typing import Any


def log(msg_type: str, message: Any):
    print(f'==================== {msg_type.upper()} ========================')
    print(message)
    print('========================================================')