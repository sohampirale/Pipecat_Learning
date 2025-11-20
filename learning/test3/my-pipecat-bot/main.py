from dotenv import load_dotenv
load_dotenv()

# bot.py - Gemini Voice AI Bot (Fixed Install)
import os
import asyncio

# Core imports (top-level after [all] extras)
import pipecat.pipeline
print(dir(pipecat.pipeline))
from pipecat.pipeline import Pipeline

from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

# Services
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService  # Gemini
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.transports.webrtc import create_webrtc_transport

async def main():
    # 1. Local WebRTC transport
    transport = await create_webrtc_transport()

    # 2. Services
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
    
    # Gemini LLM
    llm = GoogleLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model="gemini-2.0-flash-exp",  # Latest fast model (or "gemini-1.5-flash")
        system_instruction="You are a helpful AI assistant. Keep responses short and fun."
    )
    
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="71a7ad14-091c-4e8e-a314-022ece01c121"  # Natural voice
    )

    # 3. Pipeline
    pipeline = Pipeline([
        transport.input(),   # Mic input
        stt,                 # Audio → Text
        llm,                 # Gemini thinks
        tts,                 # Text → Audio
        transport.output(),  # Play reply
    ])

    # 4. Run
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    print("Gemini Bot ready! Open: http://localhost:7860/client in Chrome.")
    await runner.run(task)

if __name__ == "__main__":
    asyncio.run(main())