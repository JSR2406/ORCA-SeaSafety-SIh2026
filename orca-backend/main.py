import uvicorn
from dotenv import load_dotenv

# Load all environment variables from .env
load_dotenv()

from api.server import app

if __name__ == "__main__":
    print("Starting ORCA Multi-Agent Backend...")
    # Run the FastAPI server using Uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
