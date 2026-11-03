"""Заглушка aiohttp для запуска тестов без интернета и без установленного aiohttp."""
import sys
import types


def install():
    try:
        import aiohttp  # noqa
        return
    except ImportError:
        pass
    m = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientTimeout:
        def __init__(self, total=None):
            self.total = total

    class ClientSession:
        closed = False

        async def close(self):
            self.closed = True

    class FormData:
        def __init__(self):
            self.fields = []

        def add_field(self, *a, **k):
            self.fields.append((a, k))

    m.ClientError, m.ClientTimeout, m.ClientSession, m.FormData = \
        ClientError, ClientTimeout, ClientSession, FormData
    sys.modules["aiohttp"] = m
