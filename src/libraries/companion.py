import asyncio
import websockets
import json
import itertools
import re
from collections import defaultdict

class Companion:
    def __init__(self, url="ws://127.0.0.1:16621"):
        self.url = url
        self.variables = {}

        # Handler types
        self._handlers = defaultdict(lambda: defaultdict(list))
        self._wildcards = defaultdict(list)
        self._regex = defaultdict(list)

        self._pending = {}  # async wait-for-return
        self._id_counter = itertools.count(10)
        self._ws = None

    # --------------------
    # Decorators
    # --------------------
    def on(self, connection, variable=None):
        """
        Register a handler for a specific connection/variable.
        Can also accept a flat string like "vmix:input_1_remaining".
        """
        if variable is None and ":" in connection:
            connection, variable = connection.split(":", 1)

        def decorator(func):
            if variable:
                self._handlers[connection][variable].append(func)
            else:  # whole connection
                self._handlers[connection]["_all"].append(func)
            return func
        return decorator

    def on_prefix(self, connection, prefix):
        """Register a handler for variables starting with prefix."""
        def decorator(func):
            self._wildcards[connection].append((prefix, func))
            return func
        return decorator

    def on_regex(self, connection, pattern):
        """Register a handler for variables matching regex."""
        regex = re.compile(pattern)
        def decorator(func):
            self._regex[connection].append((regex, func))
            return func
        return decorator

    # --------------------
    # Public API
    # --------------------
    async def query(self, path, params=None):
        """Perform a one-shot query and return result."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected yet")
        req_id = next(self._id_counter)
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        message = {
            "id": req_id,
            "method": "query",
            "params": {"path": path} if not params else {"path": path, **params}
        }
        await self._ws.send(json.dumps(message))
        return await fut

    def get_variable(self, connection, var, default=None):
        """Get cached variable value."""
        return self.variables.get(connection, {}).get(var, default)

    # --------------------
    # Internal Dispatch
    # --------------------
    async def _dispatch(self, connection, updates):
        # connection-wide handlers
        for h in self._handlers[connection].get("_all", []):
            await self._maybe_await(h, updates)

        for var, value in updates.items():
            # exact variable handlers
            for h in self._handlers[connection].get(var, []):
                await self._maybe_await(h, value)

            # prefix handlers
            for prefix, h in self._wildcards[connection]:
                if var.startswith(prefix):
                    await self._maybe_await(h, (var, value))

            # regex handlers
            for regex, h in self._regex[connection]:
                if regex.match(var):
                    await self._maybe_await(h, (var, value))

    async def _maybe_await(self, handler, arg):
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(arg)
            else:
                handler(arg)
        except Exception as e:
            print(f"⚠️ Handler error: {e}")

    # --------------------
    # Main loop
    # --------------------
    async def run(self):
        connect_repeat = 1
        while True:
            try:
                async with websockets.connect(self.url) as ws:
                    self._ws = ws
                    connect_repeat = 1
                    print("✅ Connected to Companion")

                    # Initial query
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "query",
                        "params": {"path": "variables.values"}
                    }))

                    # Subscribe to changes
                    await ws.send(json.dumps({
                        "id": 2,
                        "method": "subscription",
                        "params": {"path": "variables.values"}
                    }))

                    async for message in ws:
                        data = json.loads(message)

                        # fulfill queries
                        if "id" in data and data["id"] in self._pending:
                            fut = self._pending.pop(data["id"])
                            fut.set_result(data.get("result"))
                            continue

                        # initial query response
                        if data.get("id") == 1 and "result" in data:
                            result = data["result"]
                            if isinstance(result, dict):
                                self.variables.update(result)
                            print(f"📥 Cached variables for {len(self.variables)} connections")
                            for connection in self.variables:
                                print(connection)

                        # variable change events
                        if data.get("event") == "variables_changed":
                            payload = data.get("payload", {})
                            # update cache first in case a function needs to access the latest data
                            for conn, updates in payload.items():
                                conn_vars = self.variables.setdefault(conn, {})
                                conn_vars.update(updates)
                            # dispatch
                            for conn, updates in payload.items():
                                await self._dispatch(conn, updates)

            except (OSError, websockets.exceptions.ConnectionClosedError) as e:
                print(f"⚠️ Connection error: {e}")
                print(f"🔄 Reconnecting ({connect_repeat})...")
                await asyncio.sleep(min(connect_repeat, 5))
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                print(f"🔄 Reconnecting ({connect_repeat})...")
                await asyncio.sleep(min(connect_repeat, 5))
            finally:
                if self._ws:
                    await self._ws.close()  # force close
                self._ws = None
                connect_repeat += 1
