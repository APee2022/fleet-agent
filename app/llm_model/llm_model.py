import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

load_dotenv()

gemini_llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.4,
)
openai_llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.4
)

llm_type = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" | "openai"
llm = gemini_llm if llm_type == "gemini" else openai_llm
