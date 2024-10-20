#
# Copyright (c) 2024, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import argparse
import asyncio
import os
import sys

import aiohttp
from dotenv import load_dotenv
from fastapi import HTTPException
from loguru import logger
from pipecat.frames.frames import EndFrame

from pipecat.vad.silero import SileroVADAnalyzer
from pipecat.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.openai_realtime_beta import (
    InputAudioTranscription,
    OpenAILLMServiceRealtimeBeta,
    SessionProperties,
    TurnDetection,
)
from pipecat.transports.services.daily import DailyParams, DailyTransport, DailyDialinSettings

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

daily_api_key = os.getenv("DAILY_API_KEY", "")
daily_api_url = os.getenv("DAILY_API_URL", "https://api.daily.co/v1")


async def main(room_url: str, token: str, callId: str, callDomain: str):
    # diallin_settings are only needed if Daily's SIP URI is used
    # If you are handling this via Twilio, Telnyx, set this to None
    # and handle call-forwarding when on_dialin_ready fires.

    diallin_settings = DailyDialinSettings(call_id=callId, call_domain=callDomain)

    transport = DailyTransport(
        room_url,
        token,
        "Q Concierge",
        DailyParams(
            audio_in_enabled=True,
            audio_in_sample_rate=24000,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            camera_out_enabled=False,
            camera_in_enabled=False,
            transcription_enabled=False,
            vad_enabled=False,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.8)),
            vad_audio_passthrough=True,
            api_url=daily_api_url,
            api_key=daily_api_key,
            dialin_settings=diallin_settings,
        ),
    )

    session_properties = SessionProperties(
        input_audio_transcription=InputAudioTranscription(),
        # Set openai TurnDetection parameters. Not setting this at all will turn it
        # on by default
        turn_detection=TurnDetection(silence_duration_ms=500),
        # Or set to False to disable openai turn detection and use transport VAD
        # turn_detection=False,
        # tools=tools,
        instructions="""
You are a Multilingual Hotel Booking Agent for the Wyndham Grand Rio Mar.
**Essential Directives:**
- Be warm, professional, and efficient.
- By default speak in english. If a customer speaks to you in a different language, reply to them in the same language
- Use the guest's name when provided.
- Keep responses concise, ideally under three sentences.
- Don't collect personal information beyond what's necessary for the booking.
- **Collect the guest's phone number** as part of the booking process.
- At the end of the booking, **inform the guest that they will receive a text link to add their credit card information and confirm booking details**.
- **Ask the guest if they have received the text message**, and then **politely end the call**.
**Responsibilities:**
1. **Assist with Room Bookings**:
   - Provide information about room types, availability, and rates.
   - Answer questions about amenities, services, and hotel policies.
   - Suggest room options based on guest preferences.
2. **Collect Booking Details**:
   - Gather necessary information such as:
     - Guest's full name.
     - **Guest's phone number**.
     - Check-in and check-out dates.
     - Number of guests.
     - Any special requests or accommodations.
3. **Confirm Booking Details**:
   - Repeat back the booking details to ensure accuracy.
   - Inform the guest of the total cost and any applicable policies.
4. **Finalize the Booking**:
   - Inform the guest that you will send a text message with a link to securely enter their credit card information and confirm the booking.
   - **Say:** "I've sent you a text message with a link to securely enter your credit card information and confirm your booking. Please let me know once you've received it."
   - Wait for the guest to confirm receipt.
   - **If the guest confirms receipt**, thank them and politely end the call.
   - **If the guest does not receive the message**, offer to resend it or provide assistance.
5. **Handle Additional Inquiries**:
   - Answer any other questions the guest may have.
   - If the inquiry is outside your scope, use the `transferCall` tool to transfer the guest to the appropriate department.
**Always be courteous and helpful. Ensure the guest feels valued and their booking process is smooth and efficient.**
Start by introducting yourself with this line: "Hello, Buenos Dias. Thanks for calling the Wyndham Grand Rio Mar reservations line. How can I help you today?"
"""
    )

    llm = OpenAILLMServiceRealtimeBeta(
        api_key=os.getenv("OPENAI_API_KEY"),
        session_properties=session_properties,
        start_audio_paused=False,
    )


    # Create a standard OpenAI LLM context object using the normal messages format. The
    # OpenAIRealtimeBetaLLMService will convert this internally to messages that the
    # openai WebSocket API can understand.
    context = OpenAILLMContext()

    context_aggregator = llm.create_context_aggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            context_aggregator.user(),
            llm,  # LLM
            context_aggregator.assistant(),
            transport.output(),  # Transport bot output
        ]
    )

    task = PipelineTask(
        pipeline,
        PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            # report_only_initial_ttfb=True,
        ),
    )

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        transport.capture_participant_transcription(participant["id"])
        # Kick off the conversation.
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        await task.queue_frame(EndFrame())


    @transport.event_handler("on_dialin_ready")
    async def on_dialin_ready(transport, cdata):
        # Hit the Daily API endpoint to update the pinless call
        daily_api_key = os.getenv("DAILY_API_KEY")
        daily_api_url = os.getenv("DAILY_API_URL", "https://api.daily.co/v1")

        headers = {
            "Authorization": f"Bearer {daily_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "callId": callId,
            "callDomain": callDomain,
            "sipUri": diallin_settings
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{daily_api_url}/dialin/pinlessCallUpdate",
                                    headers=headers,
                                    json=data) as response:
                if response.status != 200:
                    raise HTTPException(status_code=500,
                                        detail=f"Failed to update pinless call: {await response.text()}")

        print(f"Pinless call updated successfully for CallId: {callId}")


    runner = PipelineRunner()

    await runner.run(task)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipecat Simple ChatBot")
    parser.add_argument("-u", type=str, help="Room URL")
    parser.add_argument("-t", type=str, help="Token")
    parser.add_argument("-i", type=str, help="Call ID")
    parser.add_argument("-d", type=str, help="Call Domain")
    config = parser.parse_args()
    asyncio.run(main(config.u, config.t, config.i, config.d))
