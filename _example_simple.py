import asyncio
import datetime
import random

import kmock.dsl
from kmock import RawHandler, Server


async def timer(kmock, r: kmock.dsl.Reaction):
    while True:
        i = random.randint(0, 5)
        try:
            # r[...] << (b'beep', str(i).encode(), b'::', lambda: datetime.datetime.now().isoformat(), None if i == 0 else ...)
            # kmock['get'][...] << (b'beep', str(i).encode(), b'::', lambda: datetime.datetime.now().isoformat(), None if i == 0 else ...)
            s = kmock['get'][...] << (b'beep', str(i).encode(), b'::', lambda: datetime.datetime.now().isoformat(), ...)

            # Turn everything into a response:
            # s = kmock['get'][...] << b'beep' << str(i).encode() << b'::' << (lambda: datetime.datetime.now().isoformat())

            kmock['post'][...] << (f'ive notified {len(s)} GETs\n'.encode(), ...)

            # Both to ?q=2 & ?q=3 streams and responses:
            # kmock['post'][...] << {'key': "I am become application/json, hopefully"}

        except Exception as e:
            print(repr(e))
        await asyncio.sleep(1)


async def main():
    async with RawHandler() as kmock, Server(kmock, port=12345):
        kmock['get /'][kmock.data({'key': 'secret'})] << b'wow, you are good!'
        kmock['get /?q=1'][:1] << 404 << b'hello'
        kmock['get /?q=1'] >> fn << 333 << b'world'
        kmock['/'][{'q': '3'}] << ...  # a whole response, not a stream!
        r = kmock['/'][{'q': '2'}] << b'PREFIX1' << b'PREFIX2' << (
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
        ) << b'SUFFIX'

        kmock[{'get', 'post'}][{'/path', '/root'}][::2][...] << b'boo'
        kmock[{'get', 'post'}][{'/path', '/root'}][1::2][...] << b'hoo'
        asyncio.create_task(timer(kmock, r))
        await asyncio.Event().wait()


def fn(req):
    print(f"<<< {req}")
    return True


if __name__ == '__main__':
    asyncio.run(main())
