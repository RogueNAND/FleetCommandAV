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

        # handler registries
        self._handlers = defaultdict(lambda: defaultdict(list))
        self._wildcards = defaultdict(list)
        self._regex = defaultdict(list)

        # requests and communication
        self._pending = {}
        self._id_counter = itertools.count(10)
        self._send_queue = asyncio.Queue()
        self._ws = None

        # running tasks
        self._sender_task = None
        self._receiver_task = None

    # ----------------------------------------------------------------------
    # Decorators
    # ----------------------------------------------------------------------
    def on(self, connection, variable=None):
        """Register handler for a specific connection/variable."""
        if variable is None and ":" in connection:
            connection, variable = connection.split(":", 1)
        def decorator(func):
            self._handlers[connection][variable or "_all"].append(func)
            return func
        return decorator

    def on_prefix(self, connection, prefix):
        def decorator(func):
            self._wildcards[connection].append((prefix, func))
            return func
        return decorator

    def on_regex(self, connection, pattern):
        regex = re.compile(pattern)
        def decorator(func):
            self._regex[connection].append((regex, func))
            return func
        return decorator

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------
    async def query(self, path, **params):
        return await self.call("query", path=path, **params)

    async def call(self, method, **params):
        if not self._ws:
            raise RuntimeError("WebSocket not connected yet")

        req_id = next(self._id_counter)
        fut = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        message = {"id": req_id, "method": method, "params": params}
        await self._send_queue.put(message)

        try:
            return await asyncio.wait_for(fut, timeout=1)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise RuntimeError(f"Timeout waiting for response to '{method}'")

    async def run_connection_action(self, connection_name, action_id, options=None):
        return await self.call(
            "runConnectionAction",
            connectionName=connection_name,
            actionId=action_id,
            options=options or {},
            extras={"surfaceId": "python-direct"}
        )

    async def run_actions(self, actions, **extras):
        return await self.call("runMultipleActions", actions=actions, **extras)

    def get_variable(self, connection, var, default=None):
        return self.variables.get(connection, {}).get(var, default)

    # ----------------------------------------------------------------------
    # Internal Dispatch
    # ----------------------------------------------------------------------
    async def _dispatch(self, connection, updates):
        """Schedule handlers as background tasks."""
        # _all handlers
        for h in self._handlers[connection].get("_all", []):
            asyncio.create_task(self._safe_handler_call(h, updates))

        for var, value in updates.items():
            # exact match
            for h in self._handlers[connection].get(var, []):
                asyncio.create_task(self._safe_handler_call(h, value))
            # prefix match
            for prefix, h in self._wildcards[connection]:
                if var.startswith(prefix):
                    asyncio.create_task(self._safe_handler_call(h, (var, value)))
            # regex match
            for regex, h in self._regex[connection]:
                if regex.match(var):
                    asyncio.create_task(self._safe_handler_call(h, (var, value)))

    async def _safe_handler_call(self, handler, arg):
        """Run handler safely in its own task."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(arg)
            else:
                handler(arg)
        except Exception as e:
            print(f"⚠️ Handler error in {handler.__name__}: {e}")

    # ----------------------------------------------------------------------
    # Communication Loops
    # ----------------------------------------------------------------------
    async def _send_loop(self):
        while self._ws:
            msg = await self._send_queue.get()
            try:
                await self._ws.send(json.dumps(msg))
            except Exception as e:
                fut = self._pending.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.set_exception(e)

    async def _recv_loop(self):
        async for raw in self._ws:
            data = json.loads(raw)

            # resolve pending futures
            if "id" in data and data["id"] in self._pending:
                fut = self._pending.pop(data["id"])
                if "result" in data:
                    fut.set_result(data["result"])
                elif "error" in data:
                    fut.set_exception(RuntimeError(data["error"]))
                else:
                    fut.set_result(None)
                continue

            # variable snapshot
            if data.get("id") == 1 and "result" in data:
                result = data["result"]
                if isinstance(result, dict):
                    self.variables.update(result)
                print(f"📥 Cached variables for {len(self.variables)} connections")
                continue

            # variable change
            if data.get("event") == "variables_changed":
                payload = data.get("payload", {})
                for conn, updates in payload.items():
                    self.variables.setdefault(conn, {}).update(updates)
                    await self._dispatch(conn, updates)

            # button events
            elif data.get("event") == "updateButtonState":
                print(f"🎛 Button update: {data.get('payload')}")

            # unknown
            else:
                print("🔔 Event:", data.get("event"), data.get("payload"))

    # ----------------------------------------------------------------------
    # Main entry
    # ----------------------------------------------------------------------
    async def run(self):
        reconnect_delay = 1
        while True:
            try:
                async with websockets.connect(self.url) as ws:
                    self._ws = ws
                    print("✅ Connected to Companion WebSocketBridge")

                    self._sender_task = asyncio.create_task(self._send_loop())
                    self._receiver_task = asyncio.create_task(self._recv_loop())

                    # initial variable snapshot
                    await self._send_queue.put({
                        "id": 1,
                        "method": "query.variables"
                    })

                    await asyncio.gather(self._sender_task, self._receiver_task)

            except (OSError, websockets.exceptions.ConnectionClosedError) as e:
                print(f"⚠️ Connection lost: {e}")
                await asyncio.sleep(min(reconnect_delay, 5))
                reconnect_delay = min(reconnect_delay + 1, 10)

            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                await asyncio.sleep(min(reconnect_delay, 5))

            finally:
                if self._ws:
                    await self._ws.close()
                self._ws = None
                self._sender_task = None
                self._receiver_task = None
