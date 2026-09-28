import asyncio
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import config
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_PLANNER, MODEL_CONTENT, WORDS_PER_MINUTE

import edge_tts
import uuid
import os

app = FastAPI(title="AI Audio Tour Guide")

# Create audio dir if not exists
AUDIO_DIR = "static/assets/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

class TourRequest(BaseModel):
    location: str
    interests: List[str]
    duration: int

class TourResponse(BaseModel):
    location: str
    content: str
    audio_url: str

async def generate_audio_file(text: str) -> str:
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    # Filter markdown for TTS
    import re
    clean_text = re.sub(r'#+\s*', '', text) # Remove # headers
    clean_text = re.sub(r'\*+', '', clean_text) # Remove * bold/italic
    
    # We use a neutral, high-quality voice
    voice = "en-US-GuyNeural"
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save(filepath)
    
    # Verify file exists and has content
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        raise Exception("Failed to generate audio file content.")
    
    return f"/static/assets/audio/{filename}"

async def call_openrouter(messages: list, model: str):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/houyc1217/ai_audio_tour_guide",
        "X-Title": "AI Audio Tour Guide"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Error calling OpenRouter: {e}")
            raise HTTPException(status_code=500, detail=f"AI Service Error: {str(e)}")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/intro.html")
async def read_intro():
    return FileResponse("static/intro.html")

@app.post("/api/generate-tour", response_model=TourResponse)
async def generate_tour(request: TourRequest):
    # Step 1: Create a plan
    plan_prompt = f"""
    Create a brief itinerary for a {request.duration}-minute audio tour of {request.location}.
    The user is interested in: {', '.join(request.interests)}.
    Keep the plan concise, list 3-5 key points.
    """
    
    plan = await call_openrouter([{"role": "user", "content": plan_prompt}], MODEL_PLANNER)
    
    # Step 2: Generate the script
    target_words = request.duration * WORDS_PER_MINUTE
    content_prompt = f"""
    You are an expert local tour guide for {request.location}.
    Based on this plan: {plan}
    
    Write a natural, conversational audio tour script in English.
    Interests to highlight: {', '.join(request.interests)}.
    Target length: approximately {target_words} words.
    
    Formatting Instructions:
    - Use Markdown for structure.
    - Use # for the main title (The Tour of ...).
    - Use ## for sections (e.g. ## Stop 1: ..., ## Conclusion).
    - Use **bold** for major landmarks and key terms.
    - Avoid code blocks or tables.
    - Keep paragraphs relatively short for easy reading.
    - Make it sound like a friendly, engaging guide walking alongside the visitor.
    - Include sensory details (what to see, hear, smell).
    - Add natural transitions.
    """
    
    full_content = await call_openrouter([{"role": "user", "content": content_prompt}], MODEL_CONTENT)
    
    # Step 3: Generate Audio
    audio_url = await generate_audio_file(full_content)
    
    return TourResponse(location=request.location, content=full_content, audio_url=audio_url)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
