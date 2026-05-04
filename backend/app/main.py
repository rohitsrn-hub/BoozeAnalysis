from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.core.config import ALLOWED_ORIGINS
from app.routes.uploads import router as uploads_router
from app.routes.analytics import router as analytics_router
from app.routes.routes_extra import router as extra_router

app = FastAPI(title='BoozeAnalysis API', version='2.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/health')
async def health():
    return {'status': 'ok'}

app.include_router(uploads_router)
app.include_router(analytics_router)
app.include_router(extra_router)
