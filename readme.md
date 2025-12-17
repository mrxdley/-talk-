
# (talk)

A WIP AI chatbot that's designed to almost flawlessly mimic real text conversation.  
100% modifiable by the user, to allow for context imports, changed personalities, different emotion weights, etc.  
Integrates via Telegram to add to immersion.
 


## Planned

- Streaming Grok responses
- Allowing user to interupt generation, and for model to work around this
- Letting the user prompt with multiple lines, and accurately discerning where a response is appropriate
- Making ChatID universal, so bot is accessible to everyone
- Hosting the bot on PythonEverywhere for usage PythonEverywhere

## Roadmap
- Implementing the first agentic responses
    - Developing the scheduler (decides when to prompt itself automatically)
    - Adding an "emotion engine" - weights attached to feelings that modify the model's response times, tone,  etc.
- Adding a context summarisation system
    - Automatically compresses context window at 128k tokens (using dirt cheap model)
    - Has a "memories" file, that the model can search through and import tiny portions of relevant context. Helpful for navigating extremely long timespans of conversation
- Making everything modular via bot settings - clearing memory, changing emotion weight modifiers, etc.
 


## Installation

Git Clone, then install xai-sdk with pip3

```bash
  pip3 install xai-sdk
```
Keys for xAI, telegram, etc. will have to be provided by the user  
Telegram bot setup is extremely straightforward, use @BotFather and get your token.
    