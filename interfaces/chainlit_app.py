import chainlit as cl
from interfaces.eroski_chat_interface import get_global_chat_interface

chat_interface = get_global_chat_interface()

@cl.on_message
async def main(message):
    session_id = cl.user_session.get("session_id", "default")
    
    result = await chat_interface.process_message(
        message.content, 
        session_id
    )
    
    await cl.Message(content=result["response"]).send()