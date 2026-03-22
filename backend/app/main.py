from fastapi import FastAPI

app = FastAPI(title="A-Share Research Assistant API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}