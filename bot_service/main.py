from fastapi import FastAPI

app = FastAPI(title="Fitness Studio Bot Service")

@app.get("/")
async def root():
    return {"message": "Fitness Studio Bot API is running"}
