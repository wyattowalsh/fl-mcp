"""Minimal loguru shim."""

class _Logger:
    def remove(self):
        return None

    def add(self, *args, **kwargs):
        return None

    def info(self, message):
        print(message)


logger = _Logger()
