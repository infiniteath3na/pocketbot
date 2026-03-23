import asyncio
import json
import logging
import time
from typing import Dict, Optional, Callable, Any

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)

POCKET_WS_REGIONS = [
    "wss://api-us-north.po.market",
    "wss://api-us-south.po.market",
    "wss://api-eu.po.market",
    "wss://api-asia.po.market",
]
SOCKET_PATH = "/socket.io/?EIO=4&transport=websocket"
MAX_RETRIES = 3
RETRY_DELAY = 2.0


class PocketOptionClient:
    def __init__(self):
        self.ws: Optional[Any] = None
        self.ssid: Optional[str] = None
        self.is_demo: bool = True
        self.connected: bool = False
        self.authenticated: bool = False
        self._pending_orders: Dict[int, asyncio.Future] = {}
        self._request_counter: int = 1
        self._message_handlers: Dict[str, Callable] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._balance: float = 0.0
        self._open_trades: Dict[str, dict] = {}

    async def connect(self, ssid: str, is_demo: bool = True) -> bool:
        """Connect to PocketOption WebSocket and authenticate."""
        import os, json as _json
        self.ssid = ssid
        self.is_demo = is_demo
        uid = int(os.getenv("POCKET_OPTION_UID", "0"))

        for attempt in range(1, MAX_RETRIES + 1):
            region = POCKET_WS_REGIONS[(attempt - 1) % len(POCKET_WS_REGIONS)]
            url = region + SOCKET_PATH
            try:
                logger.info(f"Connecting to PocketOption {region} (attempt {attempt}/{MAX_RETRIES})...")
                self.ws = await websockets.connect(
                    url,
                    additional_headers={
                        "Origin": "https://m.pocketoption.com",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
                    },
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                )

                # Wait for Socket.IO handshake
                handshake = await asyncio.wait_for(self.ws.recv(), timeout=10)
                logger.debug(f"Handshake: {handshake}")

                # Send Socket.IO namespace connect
                await self.ws.send("40")

                # Wait for namespace ack
                try:
                    ack = await asyncio.wait_for(self.ws.recv(), timeout=5)
                    logger.debug(f"NS ack: {ack}")
                except asyncio.TimeoutError:
                    pass

                # Send auth with uid
                demo_flag = 1 if is_demo else 0
                auth_payload = _json.dumps({
                    "session": ssid,
                    "isDemo": demo_flag,
                    "uid": uid,
                    "platform": 1,
                    "isFastHistory": False,
                    "isOptimized": False,
                })
                auth_msg = f'42["auth",{auth_payload}]'
                await self.ws.send(auth_msg)
                logger.info("Auth message sent")

                # Wait for auth response
                auth_response = await asyncio.wait_for(self.ws.recv(), timeout=10)
                logger.debug(f"Auth response: {str(auth_response)[:100]}")

                self.connected = True
                self.authenticated = True

                # Start background tasks
                self._receive_task = asyncio.create_task(self._receive_loop())
                self._ping_task = asyncio.create_task(self._ping_loop())

                logger.info("Successfully connected to PocketOption")
                return True

            except asyncio.TimeoutError:
                logger.error(f"Connection timeout (attempt {attempt})")
            except WebSocketException as e:
                logger.error(f"WebSocket error (attempt {attempt}): {e}")
            except Exception as e:
                logger.error(f"Connection error (attempt {attempt}): {e}")

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)

        logger.error("Failed to connect to PocketOption after all retries")
        self.connected = False
        return False

    async def _ping_loop(self):
        """Send periodic ping to keep connection alive."""
        while self.connected and self.ws:
            try:
                await asyncio.sleep(25)
                if self.ws and not self.ws.closed:
                    await self.ws.send("2")  # Socket.IO ping
            except Exception as e:
                logger.error(f"Ping error: {e}")
                break

    async def _receive_loop(self):
        """Receive and process incoming WebSocket messages."""
        while self.connected and self.ws:
            try:
                message = await self.ws.recv()
                if isinstance(message, bytes):
                    try:
                        await self._handle_message(message.decode("utf-8"))
                    except Exception:
                        pass
                    continue
                await self._handle_message(message)
            except ConnectionClosed:
                logger.warning("PocketOption connection closed")
                self.connected = False
                self.authenticated = False
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break

    async def _handle_message(self, message: str):
        """Parse and handle incoming Socket.IO messages."""
        try:
            # Socket.IO ping/pong
            if message == "2":
                await self.ws.send("3")
                return
            if message == "3":
                return

            # Socket.IO binary attachment events start with 451-
            if message.startswith("451-["):
                import re as _re
                m = _re.match(r'451-\["([^"]+)",.*\]', message)
                # binary payload follows as next message — store event name
                if m:
                    self._pending_binary_event = m.group(1)
                return

            # Handle binary payload for pending event
            if hasattr(self, "_pending_binary_event") and self._pending_binary_event:
                event_name = self._pending_binary_event
                self._pending_binary_event = None
                try:
                    import json as _json
                    event_data = _json.loads(message)
                    if not isinstance(event_data, dict):
                        event_data = {"data": event_data}
                except Exception:
                    event_data = {}
                # Re-process as a normal event
                if event_name == "successauth":
                    logger.info("Authentication confirmed (binary)")
                    self.authenticated = True
                    balance = event_data.get("balance", event_data.get("demo_balance", 0.0))
                    if isinstance(balance, (int, float)):
                        self._balance = float(balance)
                    logger.info(f"Balance from auth: {self._balance}")
                elif event_name == "updateBalance":
                    b = event_data.get("balance", self._balance)
                    if isinstance(b, (int, float)):
                        self._balance = float(b)
                return

            # Socket.IO event messages start with 42
            if message.startswith("42"):
                data_str = message[2:]
                try:
                    data = json.loads(data_str)
                    event_name = data[0] if len(data) > 0 else ""
                    event_data = data[1] if len(data) > 1 else {}

                    if event_name == "successauth":
                        logger.info("Authentication confirmed")
                        self.authenticated = True
                        self._balance = float(event_data.get("balance", 0.0))
                        try:
                            await self.ws.send('42["getBalance",{}]')
                        except Exception:
                            pass

                    elif event_name == "updateBalance":
                        self._balance = event_data.get("balance", self._balance)

                    elif event_name == "successopenOrder":
                        order_id = str(event_data.get("requestId", ""))
                        request_id = event_data.get("requestId")
                        if request_id in self._pending_orders:
                            future = self._pending_orders.pop(request_id)
                            if not future.done():
                                future.set_result(event_data)
                        self._open_trades[str(event_data.get("id", order_id))] = event_data
                        logger.info(f"Order opened: {event_data.get('id')}")

                    elif event_name == "closeOrder":
                        trade_id = str(event_data.get("id", ""))
                        if trade_id in self._open_trades:
                            del self._open_trades[trade_id]
                        profit = event_data.get("profit", 0)
                        result = "WIN" if profit > 0 else "LOSS"
                        logger.info(f"Order closed: {trade_id}, result: {result}, profit: {profit}")

                        # Notify any registered handler
                        handler = self._message_handlers.get("trade_closed")
                        if handler:
                            await handler(event_data)

                    elif event_name == "failopenOrder":
                        request_id = event_data.get("requestId")
                        if request_id in self._pending_orders:
                            future = self._pending_orders.pop(request_id)
                            if not future.done():
                                future.set_exception(Exception(f"Order failed: {event_data}"))
                        logger.error(f"Order failed: {event_data}")

                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON message: {message[:100]}")

            # Handle Socket.IO connection events
            elif message.startswith("0"):
                logger.debug("Socket.IO connection established")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def place_trade(
        self,
        asset: str,
        amount: float,
        action: str,  # "call" or "put"
        expiry_seconds: int = 60,
        is_demo: Optional[bool] = None,
    ) -> Optional[dict]:
        """Place a binary options trade on PocketOption."""
        if not self.connected or not self.ws:
            raise ConnectionError("Not connected to PocketOption")

        if is_demo is None:
            is_demo = self.is_demo

        request_id = self._request_counter
        self._request_counter += 1

        demo_flag = 1 if is_demo else 0
        action_lower = action.lower()  # "call" or "put"

        # Map asset to OTC format if needed
        asset_name = f"{asset}_otc" if not asset.endswith("_otc") else asset

        order_payload = {
            "asset": asset_name,
            "amount": amount,
            "action": action_lower,
            "isDemo": demo_flag,
            "requestId": request_id,
            "optionType": 100,
            "time": expiry_seconds,
        }

        message = f'42["openOrder",{json.dumps(order_payload)}]'

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_orders[request_id] = future

        try:
            await self.ws.send(message)
            logger.info(f"Trade placed: {asset_name} {action_lower} ${amount} ({expiry_seconds}s)")

            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=15.0)
            return result

        except asyncio.TimeoutError:
            self._pending_orders.pop(request_id, None)
            logger.error(f"Trade response timeout for request {request_id}")
            raise TimeoutError(f"No response for trade request {request_id}")
        except Exception as e:
            self._pending_orders.pop(request_id, None)
            logger.error(f"Trade placement error: {e}")
            raise

    def register_handler(self, event: str, handler: Callable):
        """Register a callback for a specific event."""
        self._message_handlers[event] = handler

    async def get_balance(self) -> float:
        """Return cached balance."""
        return self._balance

    async def disconnect(self):
        """Cleanly disconnect from PocketOption."""
        self.connected = False
        self.authenticated = False

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.debug(f"Error closing websocket: {e}")
            finally:
                self.ws = None

        logger.info("Disconnected from PocketOption")

    @property
    def open_trades(self) -> Dict[str, dict]:
        return self._open_trades.copy()

    @property
    def balance(self) -> float:
        return self._balance
