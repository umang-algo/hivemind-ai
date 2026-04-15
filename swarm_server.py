from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Swarm Terminal Viewer")

# Mount public directory
app.mount("/static", StaticFiles(directory="swarm_public"), name="static")

@app.get("/")
def read_index():
    return FileResponse("swarm_public/index.html")
