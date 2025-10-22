from . import companion

"""
🚀 Companion Automation API

Event-based decorators:
  @companion.on_change(connection, variable)
  @companion.on_change(connection, prefix="prefix_")
  @companion.on_change(connection, suffix="_suffix")
  @companion.on_change(connection, regex=r"^pattern.*$")
  @companion.on_button_down(page, x, y)
  @companion.on_button_up(page, x, y)
  @companion.on_rotate(page, x, y)

Utilities:
  companion.action(connection, action_id, options={})   → Run any action on any connection
  companion.var(connection, var_name, default=None)     → Access current variable values

💡 Tip:
  Create additional Python files in this directory to organize your automations!
"""

# EXAMPLE 1: Log uptime every second
@companion.on_change("internal", variable="time_s")
async def print_uptime_every_second(event):
    uptime = companion.var("internal", "uptime")
    print(f"🕒 Companion uptime: {uptime}s")


# EXAMPLE 2: React to a variable prefix (e.g. all VMix inputs)
@companion.on_change("vmix", prefix="input_")
async def vmix_input_change(event):
    var, value = event
    print(f"🎬 VMix variable changed: {var} = {value}")


# EXAMPLE 3: React to a button press on page 1, column 2, row 3
@companion.on_button_down(page=1, x=2, y=3)
async def handle_button_down(event):
    print("🔘 Button (1,2,3) pressed!")

    # Run an example action (pause VMix input #1)
    await companion.action("vmix", "videoActions", {"input": "1", "inputType": False, "functionID": "Pause"})


# EXAMPLE 4: Handle Stream Deck+ rotary knob rotation
@companion.on_rotate(page=1, x=1, y=1)
async def handle_knob_rotate(event):
    direction = "right" if event.get("direction") else "left"
    print(f"🎛️ Knob rotated {direction} at (1,1,1)")
