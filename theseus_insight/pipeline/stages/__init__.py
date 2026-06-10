"""run_async pipeline stages extracted from TheseusInsight (B9).

Each stage is `async def run(ti, ...)` taking the TheseusInsight
instance as its context — the facade's configuration, checkpoint
adapter, and helpers travel with it. Checkpoint stage keys and the
save/load order inside each stage are frozen contracts.
"""
