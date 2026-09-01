from fastapi import FastAPI
from src.routes.user_routes import user_router

app = FastAPI(title="Fil Rouge Immobilier API")
app.include_router(user_router)

# @app.get("/health")
# async def health_check():
#     return {"status": "ok"}