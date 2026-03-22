import asyncio
import os
from cradle.config import Config
from cradle.memory import Memory

async def main():
    config = Config.from_env()
    mem = Memory(config)
    
    print("Fetching memories via MCP search...")
    all_memories = await mem.search()
    print(f"Total memories found: {len(all_memories)}")
    
    # We want to aggressively delete all accumulated reflections and completed tasks
    # except maybe the 50 most recent ones.
    reflections = []
    
    for m in all_memories:
        tags = m.get("tags", [])
        if "reflection" in tags or "self-evolution" in tags or "completed_task" in tags:
            reflections.append(m)
            
    print(f"Found {len(reflections)} cleanup targets.")
    
    if len(reflections) <= 50:
        print("Nothing to clean up.")
        return
        
    overflow = reflections[:-50]
    print(f"Deleting {len(overflow)} ancient memories...")
    
    success = 0
    fail = 0
    
    # Process in smaller batches
    for i in range(0, len(overflow), 20):
        batch = overflow[i:i+20]
        results = await asyncio.gather(
            *[mem.forget(m.get("key")) for m in batch if m.get("key")],
            return_exceptions=True
        )
        
        for r in results:
            if isinstance(r, bool) and r:
                success += 1
            else:
                fail += 1
                
        print(f"Batch {i//20 + 1}/{(len(overflow) + 19) // 20}: {success} OK, {fail} Fail")
        
    print(f"Cleanup finished! Deleted {success} memories.")
    await mem.close()

if __name__ == "__main__":
    asyncio.run(main())
