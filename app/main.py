from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.agents.main_agent import run_general_chat_agent
from app.models.schemas import PromptRequest, AgentResponse

app = FastAPI(title="Fleet Synthetic Data Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

@app.get("/")
def root():
    return {"status": "ok", "service": "fleet-synth-agent"}

@app.post("/prompt", response_model=AgentResponse)
def user_prompt(req: PromptRequest):
    # You can prepend params as natural language if provided
    if req.params:
        req_text = f"{req.prompt}\n\nParams: {req.params}"
    else:
        req_text = req.prompt
    print(f"Prompt: {req_text}")
    result = run_general_chat_agent(req_text, session_id="default")
    return AgentResponse(response=result["response"], tool_result=result.get("tool_result"))
