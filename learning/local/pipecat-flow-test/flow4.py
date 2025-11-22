#
# Copyright (c) 2024-2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License

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

from pipecat_flows import (
    FlowArgs,
    FlowManager,
    FlowsFunctionSchema,
    NodeConfig,
)

load_dotenv(override=True)

voice_ids={
    "general_bot":"6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
    "data_collector":"6a8a40f7-9284-4f1d-b839-16e205174254"
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
    """Transfer control to the next bot in the voice agentic meeting application

    Args:
        next_node (str): name of the next node (ex:data_collector,general_bot)
    """
    
    next_node = args['next_node']  
    
  
    #await flow_manager.push_frames(TTSSpeakFrame("Inside record_last_name_function  ,your lat name is being recorded brother"))
    await flow_manager.task.queue_frame(TTSSpeakFrame("Inside record_last_name_function, your last name is being recorded brother"))

    
    if next_node == 'data_collector':
        await flow_manager.task.queue_frame(
            TTSUpdateSettingsFrame({"voice": voice_ids['data_collector']})
        )
        return "done",create_data_collector()
    elif next_node =='general_bot':
        await flow_manager.task.queue_frame(
            TTSUpdateSettingsFrame({"voice": voice_ids['general_bot']})
        )
        return "done",create_generalbot()
    else:
        return "invalid next_node name",None

transfer_control_tool=FlowsFunctionSchema(
    name="transfer_control",
    description="Transfer control to the next AI Voice bot",
    required=['next_node'],
    handler=transfer_control,
    properties={'next_node':{'type':'string'}}
)

def create_generalbot()->NodeConfig:
    from prompts.flows_prompts import general_bot_meeting_suite_prompt
    
    return {
        "name": "initial",
        "role_messages": [
            {
                "role": "system",
                "content": general_bot_meeting_suite_prompt,
            }
        ],
        "task_messages": [
            {
                "role": "system",
                "content": "Say Hello ans start the conversation in kindful way and in short dont bore them understand it from previous conversation, keep your responses consice when needed and descriptive when needed",
            }
        ],
        "functions": [transfer_control_tool]
    }


def create_data_collector()->NodeConfig:
    from prompts.flows_prompts import general_bot_meeting_suite_prompt
    
    return {
        "name": "initial",
        "role_messages": [
            {
                "role": "system",
                "content": "You are a data collector bot,Your job is to collect data about user such as email,name and additional information based on the previous conversations we had with user, if user asks for any general information then use the function transfer_control('general_bot')",
            }
        ],
        "task_messages": [
            {
                "role": "system",
                "content": "Introduce yourself and tell what you are supposed to do in kindful way and in short dont bore them understand it from previous conversation",
            }
        ],
        "functions": [transfer_control_tool]
    }


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    stt = CartesiaSTTService(api_key=os.getenv("CARTESIA_API_KEY"))
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
#        voice_id="6a8a40f7-9284-4f1d-b839-16e205174254",  #soham - english
        voice_id="d01294a0-1ddd-4b92-80c9-6dbb7d40e564",    #soham - english + marathi
        text_filters=[MarkdownTextFilter()],
    )
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

    # Initialize flow manager
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
        await flow_manager.initialize(create_generalbot())

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




# # Flow nodes
# def create_initial_node() -> NodeConfig:
#     """Create the initial node of the flow.

#     Define the bot's role and task for the node as well as the function for it to call.
#     The function call includes a handler which provides the function call result to
#     Pipecat and then transitions to the next node.
#     """
#     record_favorite_color_func = FlowsFunctionSchema(
#         name="record_favorite_color_func",
#         description="Record the color the user said is their favorite.",
#         required=["color"],
#         handler=record_favorite_color_and_set_next_node,
#         properties={"color": {"type": "string"}},
#     )

#     record_first_name_tool = FlowsFunctionSchema(
#         name='record_first_name_func',
#         description='Records the first name of the user',
#         required=['first_name'],
#         handler=record_first_name_func,
#         properties={'first_name':{'type':'string'}}
#     )

#     return {
#         "name": "initial",
#         "role_messages": [
#             {
#                 "role": "system",
#                 "content": "You Neo, your job is to collect favourity color of the user and store it.You can speak in any language user speaks in , YOu have that capability as well as freedom",
#             }
#         ],
#         "task_messages": [
#             {
#                 "role": "system",
#                 "content": "Say 'Hello' and have good starter with out potential new customer",
#             }
#         ],
#         "functions": [record_favorite_color_func]
#     }

# async def record_last_name_function(args:FlowArgs,flow_manager:FlowManager)->tuple[str,NodeConfig]:
#     """
#         Records the last_name of the user
#     """
#     await flow_manager.task.queue_frame(
#         TTSUpdateSettingsFrame({"voice": "228fca29-3a0a-435c-8728-5cb483251068"})
#     )
#     #await flow_manager.push_frames(TTSSpeakFrame("Inside record_last_name_function  ,your lat name is being recorded brother"))
#     await flow_manager.task.queue_frame(TTSSpeakFrame("Inside record_last_name_function, your last name is being recorded brother"))

#     print(f'flow_manager : {flow_manager}')
#     print(f'Your last_name is : {args["last_name"]}')
#     return args['last_name'],None


# async def record_first_name_func(args:FlowArgs,flow_manager:FlowManager)-> tuple[str,NodeConfig]:
#     """
#         args:
#             first_name :(string) : first_name of the user
            
#     """
#     print(f"Your first name is : {args}")
#     return "some_default_name",None

# async def record_favorite_color_and_set_next_node(
#     args: FlowArgs, flow_manager: FlowManager
# ) -> tuple[str, NodeConfig]:
#     """Function handler that records the color then sets the next node.

#     Here "record" means print to the console, but any logic could go here;
#     Write to a database, make an API call, etc.
#     """
#     print(f"Your favorite color is: {args['color']}")
#     await flow_manager.task.queue_frame(TTSSpeakFrame("Inside record_favourite_color_function, your favourite color is being recorded brother"))
# #    return args["color"], create_end_node()
# #    return args["color"], None
#     return args['color'],create_second_node()



# def create_end_node() -> NodeConfig:
#     """End the conversation.

#     Flows transitions to this node when the user has answered the question.
#     It thanks the user and ends the conversation using the `end_conversation`
#     post-action.
#     """
#     return NodeConfig(
#         name="create_end_node",
#         task_messages=[
#             {
#                 "role": "system",
#                 "content": "YOu are here to end the conversation in friendly reminding way",
#             }
#         ],
#         post_actions=[{"type": "end_conversation",'text':"Thank you so much brother"}],
#     )

# def create_second_node()->NodeConfig:
#     """Create second node"""

#     record_last_name_tool=FlowsFunctionSchema(
#         name="record_last_name_tool",
#         description="Records last name of the user",
#         required=['last_name'],
#         handler=record_last_name_function,
#         properties={'last_name':{'type':'string'}}
#     )

#     return {
#         'name':'second_node',
#         'role_messages':[
#             {
#                 'role':'system',
#                 'content':'You are an onboarding assistant John,Your main job is to collect last_name of the user'
#             }
#         ],
#         'task_messages':[
#             {
#                 'role':'system',
#                 'content':'Say good afternoon to user and ask for their last name'
#             }
#         ],
#         'functions':[record_last_name_tool]
#     }


