from fastapi import FastAPI

app = FastAPI(title="Multilingual Audio Guide")


@app.get("/health")
async def health() -> dict:
    """Kiểm tra app còn sống. Docker và CI dùng endpoint này để biết app đã sẵn sàng."""
    return {"status": "ok"}