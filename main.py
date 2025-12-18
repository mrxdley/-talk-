import os, json, requests, asyncio, time, aiohttp, random, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from collections import deque
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  

from xai_sdk import Client, AsyncClient
from xai_sdk.chat import user, system

### VARIABLES ###
TELEGRAM_TOKEN=os.getenv("TELE_API_KEY")
TRINITY_KEY=os.getenv("TRINITY_KEY")
CHAT_ID=os.getenv("CHAT_ID")

contextFile = "context2.txt"
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
async def telegram_input():
    global last_update_id

    async with aiohttp.ClientSession() as session:
        while True:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id+1}"
            async with session.get(url) as resp:
                data = await resp.json()

            if data['result']:
                update = data['result'][-1]
                last_update_id = update['update_id']

                if 'message' in update and 'text' in update['message']:
                    return update['message']['text']

            await asyncio.sleep(0)  # yield to event loop

async def telegram_listener():
    """Constantly watches for new messages and signals the main loop."""
    global last_message_time, current_buffer
    while True:
        # This represents your bot getting a message
        new_prompt = await telegram_input() 
        
        # If we are currently in the middle of a stream, signal to kill it
        interrupt_event.set()

        # 2. Add to the buffer
        current_buffer.append(new_prompt)
        last_message_time = time.time()
        print(f"{last_message_time}: {new_prompt}")

        # 3. Start a background "Wait and See" task for this specific message
        asyncio.create_task(process_buffer_with_timeout())
        
        # Put the message in the queue for the main loop to process next
        #await input_queue.put(new_prompt)

async def judge_end(text):
    async with aiohttp.ClientSession() as session:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {TRINITY_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "arcee-ai/trinity-mini:free",
            "messages": [
                {"role": "system", "content": "Keep reasoning brief. System instructions are given in square brackets. Following is an excerpt of a SMS conversation between 2 close friends. Is USER A likely to type anything more - reply YES or NO"},
                {"role": "user", "content": text}
            ]
        }
        
        async with session.post(url, headers=headers, json=data) as response:
            result = await response.json()
            response_text = result['choices'][0]['message']['content']

            return response_text

async def process_buffer_with_timeout():
    global current_buffer, last_message_time
    with open(contextFile, "r") as c:
        context = deque(c, 10) #number of lines

    # Wait until the user has stopped sending messages for at least 3 seconds
    while (time.time() - last_message_time) < BUFFER_TIMEOUT:
        await asyncio.sleep(0.5)
    
    # Once the timeout hits, check if we still have a buffer to process
    if not current_buffer:
        return

    # Combine all "nag" messages into one block
    full_user_thought = "\n".join(current_buffer)
    print(full_user_thought)
    current_buffer = [] # Clear the buffer for next time

    # 4. ### SMALL MODEL HERE ###
    # Send 'full_user_thought' to a fast model (e.g., Llama-3-8B)
    # Prompt: "Is the user likely finished with their thought? Reply ONLY 'YES' or 'NO'."
    is_finished = await judge_end(full_user_thought)
    print(is_finished)

    if is_finished != ("YES" or "NO"): #quick sanitisation
        is_finished = "YES"
        
    if is_finished == "YES":
        # Hand off the combined block to the main Grok loop
        await input_queue.put(full_user_thought)
    else:
        # If the small model thinks they are still typing (e.g., they ended with "...")
        # we do nothing and wait for more messages to arrive.
        print("Small model predicts follow-up. Waiting...")

linesSent = 0

interrupt_event = asyncio.Event()
input_queue = asyncio.Queue()
current_buffer = []
last_message_time = 0
BUFFER_TIMEOUT = 6.0

async def main():
    global linesSent
    asyncio.create_task(telegram_listener())

    async with AsyncClient() as client:
        while True:
            interrupt_event.clear()

            with open(contextFile, "r") as c:
                context = c.read()
            with open(f"prompts/{promptVer}.md", "r") as p:
                prompts = p.read()

            #use tele as input
            prompt = await input_queue.get()

            interrupt_event.clear()

            if (linesSent>0):
                print(f"{timestamp()} INTERRUPT")
                #prompt = f"[interrupted you with: '{prompt}' after line + {linesSent}"
            linesSent = 0

            typing_task = asyncio.create_task(send_typing_async(CHAT_ID, 10))

            #sends context + prompt
            chat = client.chat.create(model="grok-4-fast")
            chat.append(system(prompts))
            chat.append(user(context + "\nUSER: " + prompt))

            full_response_content = ""
            current_line_buffer = ""
            try:
                # 3. Iterate through tokens as they arrive
                async for response_obj, chunk in chat.stream():
                        # if interrupt_event.is_set():
                        #     print(f"{timestamp()} INTERRUPT: stream killed mid-token.")
                        #     # Breaking here stops the generator and closes the xAI connection
                        #     break

                    if chunk.content:
                        token = chunk.content
                        full_response_content += token
                        current_line_buffer += token

                        # 4. Check for newline to trigger line-by-line sending
                        if "\n" in current_line_buffer:
                            # Split buffer in case multiple newlines arrived in one chunk
                            parts = current_line_buffer.split("\n")
                            # Send everything except the last part (which is the start of a new line)
                            for line in parts[:-1]:
                                if line.strip(): # Avoid sending empty bubbles
                                    await send_tele(CHAT_ID, line)
                                    await asyncio.sleep(random.randint(1,300)/100 + 0.7)  # realistic message delay
                                    linesSent += 1
                            
                            # Keep the remainder for the next iteration
                            current_line_buffer = parts[-1]

                # 5. Send any remaining text after the stream ends
                if current_line_buffer.strip():
                    await send_tele(CHAT_ID, current_line_buffer)
                    linesSent += 1

            except asyncio.CancelledError:
                print(f"Halted! Discarded generation after {linesSent} lines.")
                # The 'async for' is broken here, xAI stops sending tokens immediately.
                raise 
            finally:
                typing_task.cancel()
                #save to context
                with open(contextFile, "a") as c:
                    c.write(f"""\n{timestamp()} USER A: {prompt}\nUSER B: {full_response_content}\n""")

            #finished loop?
            await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main())