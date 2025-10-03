import asyncio
from libraries import Companion

companion = Companion()

# @companion.on("vmix")
# def input1_handler(value):
#     print(value)

# @companion.on("vmix:input_1_remaining")
# def input1_handler(value):
#     print("Exact:", value)
#
# @companion.on("vmix", "input_2_remaining")
# def input2_handler(value):
#     print("Two Remaining:", value)
#
@companion.on_prefix("vmix", "input_1_")
def prefix_handler(event):
    var, val = event
    print("Prefix:", var, "=", val)
#
# @companion.on_regex("vmix", r"input_\d+_playing")
# def regex_handler(event):
#     var, val = event
#     print("Regex:", var, "=", val)

async def main():
    await companion.run()

if __name__ == "__main__":
    asyncio.run(main())
