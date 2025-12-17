import os, json, requests, asyncio, time, aiohttp, random, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  
with open('prompts.json', 'r') as f:
    prompts = json.load(f)

from xai_sdk import Client, AsyncClient
from xai_sdk.chat import user, system

### VARIABLES ###
TELEGRAM_TOKEN=os.getenv("TELE_API_KEY")
CHAT_ID=os.getenv("CHAT_ID")

contextFile = "context copy.txt"
promptVer = "1.1"

client = Client(
    api_key=os.getenv("XAI_API_KEY"),
    timeout=3600, # Override default timeout with longer timeout for reasoning models
)

def timestamp():
    now = datetime.now()
    return now.strftime("[%d/%m/%y %H:%M]")


### TELEGRAM ###
async def send_tele(chat_id, text):
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        async with session.post(url, json=payload) as response:
            return await response.json()


async def send_typing_async(chat_id, duration=5):
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
        payload = {"chat_id": chat_id, "action": "typing"}
        
        # Start typing
        await session.post(url, json=payload)
        
        # Keep typing indicator alive
        while duration > 0:
            await asyncio.sleep(4)  # Telegram needs refresh every <5s
            await session.post(url, json=payload)
            duration -= 4

last_update_id = 0
def telegram_input():
    global last_update_id

    # Wait for user reply
    while True:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id+1}"
        response = requests.get(url).json()
        
        if response['result']:
            update = response['result'][-1]
            last_update_id = update['update_id']
            
            if 'message' in update and 'text' in update['message']:
                user_input = update['message']['text']
                return user_input
        
        time.sleep(1)  #determines interval in which messages are checked for.

async def send_lines_async(text):
    lines = text.split('\n')
    
    for line in lines:
        if line.strip():
            await send_tele(CHAT_ID, line)
            await asyncio.sleep(random.randint(1,300)/100 + 0.7)  # Async delay

async def main():
    async with AsyncClient() as client:
        while True:
            with open(contextFile, "r") as c:
                context = c.read()

            #wait for input
            #prompt = input(">>> ")

            #use tele as input
            prompt = telegram_input()

            typing_task = asyncio.create_task(send_typing_async(CHAT_ID, 10))

            #sends context + prompt
            chat = client.chat.create(model="grok-4-fast")
            chat.append(
                system(prompts[promptVer]),
            )
            chat.append(
                user(context + "\nUSER: " + prompt)
            )

            #provides response
            response = await chat.sample()  
            typing_task.cancel()

            print(response.content)
            #pushes to tele
            await send_lines_async(response.content)

            #cleans up shit
            clean_text = response.content.encode('ascii', 'ignore').decode('ascii')

            #save to context
            with open(contextFile, "a") as c:
                c.write(f"""\n{timestamp()} USER: {prompt}
                        RESPONSE: {clean_text}\n""")
            #finished loop?

asyncio.run(main()) #doesnt hang
