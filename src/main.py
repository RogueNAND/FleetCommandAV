import asyncio
from libraries import Companion

companion = Companion()

@companion.on_change("vmix", variable="input_1_loop")
async def input_remaining(value):
    await companion.run_connection_action("vmix", "videoActions", {"input": "1", "functionID": "PlayPause"})

@companion.on_button_down(page=1, x=0, y=0)
async def test(value):
    await companion.run_connection_action("vmix", "videoActions", {"input": "1", "functionID": "PlayPause"})

async def main():
    await companion.run()

if __name__ == "__main__":
    asyncio.run(main())
