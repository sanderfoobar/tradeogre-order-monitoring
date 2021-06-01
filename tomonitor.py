#!/usr/bin/python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

"""
Usage:

1) copy the 2 cookies from browser into this script
2) install virtualenv, install `aiohttp`
     - `virtualenv -p /usr/bin/python3 venv && source venv/bin/activate && pip install aiohttp`
3) will write .txt files to disk
"""

from datetime import datetime
from typing import Callable, List
import asyncio
import json

import aiohttp


COOKIE_CF_CLEARANCE = "bcea6d51759ffbadc0462b1af1bfcba8a66d9c22-1622477379-0-150"
COOKIE_JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOjYyOTMyLCJleHAiOjE2MjI0MTYzNTUsInByaXYiOjB9.w4IoPla-iK4qhg-90BeMCoh6kMnpDRDBDBebYv159SY"


class C:
    OK = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


now = lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S')
msg = lambda _m, ok=True: print(f"[{now()}] {C.WARN if ok else C.FAIL}[+] {_m}{C.ENDC}")
msg_trade = lambda _m, sell=True: print(f"[{now()}] {C.FAIL if sell else C.OK}{'⬇️' if sell else '⬆️'}  {_m}{C.ENDC}")
timeout = aiohttp.ClientTimeout(total=2)


class TradeOgreMarkets:
    async def trading_pairs(self) -> List[str]:
        msg("fetching available markets")
        async with aiohttp.ClientSession(cookies={
            "cf_clearance": COOKIE_CF_CLEARANCE,
            "jwt": COOKIE_JWT
        }, timeout=timeout) as client:
            async with client.get('https://tradeogre.com/api/v1/markets') as resp:
                body = await resp.text()
                pairs = [list(z.keys())[0] for z in json.loads(body)]
                msg(f"{len(pairs)} market pairs found")
                return pairs


class TradeOgreWS:
    def __init__(self, symbol, host: str = "tradeogre.com", port: int = 8443):
        self.host = host
        self.port = port
        self.symbol = symbol
        self.ses = aiohttp.ClientSession(timeout=timeout)
        self.f = open(f"data/{symbol}.txt", "wb")

        self._ws = None
        self._ws_connect_date = None
        self._loop_task: Callable = None

    async def connect(self):
        msg(f"Connecting to BTC-{self.symbol} websocket endpoint")

        try:
            self._ws = await self.ses.ws_connect(f"wss://{self.host}:{self.port}")
            self._ws_connect_date = datetime.now()
        except Exception as ex:
            msg(f"{ex.__class__.__name__} - {ex}", ok=False)
            exit()

        msg_hello = {"a": "auth", "cookie": f"jwt={COOKIE_JWT}"}
        msg_data = {"a": "submarket", "name": f"BTC-{self.symbol}"}

        await self._ws.send_bytes(json.dumps(msg_hello).encode())
        await self._ws.send_bytes(json.dumps(msg_data).encode())

        self._loop_task = asyncio.create_task(self.loop())

    async def loop(self):
        while True:
            buffer = await self._ws.receive()
            blob = json.loads(buffer.data)

            if blob['a'] != 'sub':
                continue

            sell = blob['t'] == "sell"
            data = blob['d']

            price = list(data.keys())[0]
            amount = list(data.values())[0]

            _msg = f"{'SELL' if sell else 'BUY'} {amount} {self.symbol} at a price of {price} BTC"
            self.f.write(f"[{now()}] {_msg}\n".encode())
            self.f.flush()
            msg_trade(_msg, sell=sell)

            # is it time to renew the connection?
            if(datetime.now() - self._ws_connect_date).total_seconds() > 3600:  # hour
                msg(f"renewing the websocket connection for {self.symbol}")
                await self._ws.close()
                await self.connect()
                break


async def main():
    # uncomment the following lines to track all trading pairs
    # markets = TradeOgreMarkets()
    # trading_pairs = await markets.trading_pairs()

    # hardcode some trading pairs for now
    trading_pairs = ["BTC-WOW", "BTC-XMR"]

    for t in trading_pairs:
        symbol = t.split("-", 1)[1]
        t = TradeOgreWS(symbol=symbol)
        await t.connect()

    # hack to keep the script running
    while True:
        await asyncio.sleep(1)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
