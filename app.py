import datetime
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyngrok import ngrok

from db import DBclient
from llm import llm, openai_moderate
from models import Analyzer, Transcriber
from prompts import reflect_prompt

load_dotenv()
ngrok.set_auth_token(os.getenv("NGROK_TOKEN"))

running = {"status": "running"}
success = {"status": "success"}
fail = {"status": "fail"}


analyzer = Analyzer()
transriber = Transcriber()
db = DBclient()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_response(entity, type):
    uid = entity.get("uid", entity.get("userId", None))
    if not uid:
        return fail

    results = analyzer.analyze(entity["content"])

    outdict = dict(
        uid=uid,
        type=type,
        createdAt=entity.get("createdAt", datetime.datetime.now()),
    )
    results = results | outdict
    db.add_sentiment(uid, results)
    print(results)
    return success


@app.post("/reflect")
async def reflect(prompt: str, user_id: str, background_tasks: BackgroundTasks) -> str:
    response = await llm(reflect_prompt, prompt)
    chat = dict(
        content=prompt,
        uid=user_id,
    )
    background_tasks.add_task(process_response, chat, "chat")
    return response


@app.post("/analyze_post")
async def analyze_post(room_id: str, post_id: str, background_tasks: BackgroundTasks):
    post = db.get_post(room_id, post_id)
    background_tasks.add_task(process_response, post, "post")
    return running


@app.post("/analyze_note")
async def analyze_note(user_id: str, note_id: str, background_tasks: BackgroundTasks):
    note = db.get_note(user_id, note_id)
    background_tasks.add_task(process_response, note, "note")
    return running


@app.post("/moderate")
async def moderate(text: str) -> str:
    response = await openai_moderate(text)
    return response


if __name__ == "__main__":
    public_url = ngrok.connect(8000)
    print(f" * ngrok tunnel available at {public_url}")

    uvicorn.run(app, host="0.0.0.0", port=8000)
