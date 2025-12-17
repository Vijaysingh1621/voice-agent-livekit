from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, room_io
from livekit.plugins import google, noise_cancellation
from google.genai import types

from instructions import FULL_INSTRUCTIONS, GREETING_INSTRUCTION

load_dotenv(".env")


async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint for the Truliv voice agent"""
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-12-2025",
            voice="Puck",
            temperature=0.85,
            instructions=FULL_INSTRUCTIONS,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=FULL_INSTRUCTIONS),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            ),
        ),
    )

    await session.generate_reply(
        instructions=GREETING_INSTRUCTION
    )


# Run as a script
if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="truliv")
    )
