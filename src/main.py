import asyncio
import importlib
import pkgutil
import automations
from libraries import companion

def load_automations():
    # Dynamically import all modules in the `automations` package.
    for module_info in pkgutil.iter_modules(automations.__path__):
        module_name = f"{automations.__name__}.{module_info.name}"
        try:
            importlib.import_module(module_name)
            print(f"📦 Loaded automation: {module_name}")
        except Exception as e:
            print(f"❌ Failed to load {module_name}: {e}")

async def main():
    load_automations()
    await companion.run()

if __name__ == "__main__":
    asyncio.run(main())
