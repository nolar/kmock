import asyncio
import datetime
import random

from kmock import RawHandler, Server


async def timer(r):
    while True:
        i = random.randint(0, 5)
        r << (b'beep', str(i).encode(), b'::', lambda: datetime.datetime.now().isoformat(), None if i == 0 else ...)
        await asyncio.sleep(5)


async def main():
    async with RawHandler() as kmock, Server(kmock, port=12345):
        s = kmock['get /?q=1'] << b'first'
        r = kmock['get']['/'][{'q': 'query'}] << (
            'hello as a str',
            b'hello as bytes\n',
            lambda: datetime.datetime.now().isoformat(),
            lambda: asyncio.sleep(1),
            lambda: datetime.datetime.now().isoformat(),
            b'world\n',
            (
                'sub1',
                ...,
                'subEND',
            ),
            b'really bye\n',
        )
        # r = kmock['/'] << (
        #     'hello as a str',
        #     b'hello as bytes\n',
        #     lambda: datetime.datetime.now().isoformat(),
        #     lambda: asyncio.sleep(1),
        #     lambda: datetime.datetime.now().isoformat(),
        #     b'world\n',
        #     (
        #         'sub1',
        #         ...,
        #         'subEND',
        #     ),
        #     b'really bye\n',
        # )
        asyncio.create_task(timer(r))
        await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
