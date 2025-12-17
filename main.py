import os, json
from dotenv import load_dotenv
import asyncio
from datetime import datetime

load_dotenv()  
with open('prompts.json', 'r') as f:
    prompts = json.load(f)

from xai_sdk import Client
from xai_sdk.chat import user, system
from xai_sdk import AsyncClient

client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    timeout=3600, # Override default timeout with longer timeout for reasoning models
)

def build_context(conversation):
    return

def timestamp():
    now = datetime.now()
    return now.strftime("[%d/%m/%y %H:%M]")

async def main():
    client = Client()

    while True:
        with open("context.txt", "r") as c:
            context = c.read()

        #wait for input
        prompt = input(">>> ")

        chat = client.chat.create(model="grok-4-fast")
        chat.append(
            system(prompts["sys_prompt"]),
        )
        chat.append(
            user(context + "\nUSER: " + prompt)
        )

        response = chat.sample()
        print(response.content)

        #save to context
        with open("context.txt", "a") as c:
            c.write(f"""\n{timestamp()} USER: {prompt}
                    RESPONSE: {response.content}""")
        #finished loop?

asyncio.run(main())
