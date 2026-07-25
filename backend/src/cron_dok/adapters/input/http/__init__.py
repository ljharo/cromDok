"""HTTP input adapter: FastAPI routers, schemas and dependency wiring.

This is the only layer where FastAPI ``Depends`` is allowed (spec 8.4);
services and domain stay framework-free.
"""
