"""A 'Hello-World' introduction to Pipecat Flows.

Requirements:
- CARTESIA_API_KEY
- GOOGLE_API_KEY

Run the example:
uv run hello_world.py
"""

import os

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.stt import CartesiaSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
from pipecat.frames.frames import TTSSpeakFrame,TTSUpdateSettingsFrame
from pipecat.services.deepgram import DeepgramSTTService

from deepgram import LiveOptions
from pipecat.transcriptions.language import Language

from pipecat_flows import (
    FlowArgs,
    FlowManager,
    FlowsFunctionSchema,
    NodeConfig,
)

load_dotenv()
print('CARTESIA_API_KEY : ',os.getenv('CARTESIA_API_KEY'))

# # For Hindi
# live_options = LiveOptions(
#     model="nova-2",
#     language=Language.HI,  # Hindi
# )

# For Marathi
live_options = LiveOptions(
    model="nova-2",
    language=Language.MR,  # Marathi
)



voice_ids={
    "general_bot":{
        'male':"13524ffb-a918-499a-ae97-c98c7c4408c4",
        'female':"26403c37-80c1-4a1a-8692-540551ca2ae5"
    },
    'personalizer_bot':{
        'male':'5cad89c9-d88a-4832-89fb-55f2f16d13d3',
        'female':'607167f6-9bf2-473c-accc-ac7b3b66b30b'
    },
    'pre_onboarding_bot':{
        'male':'228fca29-3a0a-435c-8728-5cb483251068',
        'female':'f9836c6e-a0bd-460e-9d3c-f7299fa60f94'
    }
}

#"general_bot":"6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
#"data_collector":"6a8a40f7-9284-4f1d-b839-16e205174254"

gender_of_bots={
    'general_bot':'male',
    'personalizer_bot':"female",
    'pre_onboarding_bot':'male'
}

transport_params = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
        audio_in_sample_rate=8000,
        audio_out_sample_rate=8000
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    ),
}

async def transfer_control(args:FlowArgs,flow_manager:FlowManager)->tuple[str,NodeConfig]:
    """
    Transfer control to the next bot in the voice agentic meeting application.

    Args:
        args: Dictionary containing at least 'next_node'
        flow_manager: The flow manager instance

    Returns:
        Tuple of (status, NodeConfig or None)
    """
    
    #current_node=flow_manager.state['current_node']
    
    next_node = args['next_node']  
    
    if next_node == 'personalizer_bot':
        await flow_manager.task.queue_frame(
            TTSUpdateSettingsFrame({"voice": voice_ids['personalizer_bot'][gender_of_bots['personalizer_bot']]})
        )
        return "done",create_personalizer_bot()
    elif next_node =='general_bot':
        await flow_manager.task.queue_frame(
            TTSUpdateSettingsFrame({"voice": voice_ids['general_bot'][gender_of_bots['general_bot']]})
        )
        return "done",create_generalbot()
    elif next_node=='pre_onboarding_bot':
        await flow_manager.task.queue_frame(
            TTSUpdateSettingsFrame({"voice": voice_ids['pre_onboarding_bot'][gender_of_bots['pre_onboarding_bot']]})
        )
        return "done",create_pre_onboarding_bot()
    else:
        return "invalid next_node name",None

transfer_control_tool=FlowsFunctionSchema(
    name="transfer_control",
    description="Transfer control to the next AI Voice bot, accept only 3 strings as next_node 1.'general_bot', 2.'personalizer_bot' 3.'pre_onboarding_bot",
    required=['next_node'],
    handler=transfer_control,
    properties={'next_node':{'type':'string'}}
)

def create_node1()->NodeConfig:
    from prompts import node1_system_prompt
    
    return {
        "name": "initial",
        "role_messages": [
            {
                "role": "system",
                "content": node1_system_prompt,
            }
        ],
        "task_messages": [
            {
                "role": "system",
                "content": "Start the conversation by saying hello to the user",
            }
        ],
        "functions": []
    }

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    # stt = CartesiaSTTService(api_key=os.getenv("CARTESIA_API_KEY"))
    # stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        live_options=live_options,
    )
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
        text_filters=[MarkdownTextFilter()],
    )
#    llm = GoogleLLMService(api_key=os.getenv("GOOGLE_API_KEY"), model="gemini-1.5-flash-8b")
    llm = GoogleLLMService(api_key=os.getenv("GOOGLE_API_KEY"), model="gemini-2.0-flash-lite")


    context = LLMContext()
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            stt,  # STT
            context_aggregator.user(),  # User responses
            llm,  # LLM
            tts,  # TTS
            transport.output(),  # Transport bot output
            context_aggregator.assistant(),  # Assistant spoken responses
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator,
        transport=transport,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        # Kick off the conversation.
        await flow_manager.initialize(create_node1())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)

async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat Cloud."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)

if __name__ == "__main__":
    from pipecat.runner.run import main

    main()

