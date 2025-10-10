import asyncio
from libraries import Companion

companion = Companion()

@companion.on("vmix", "input_1_loop")
async def input_remaining(value):
    print("Hello there!")
    await companion.run_connection_action("vmix", "videoActions", {"input": "1", "functionID": "PlayPause"})

async def main():
    await companion.run()

if __name__ == "__main__":
    asyncio.run(main())
