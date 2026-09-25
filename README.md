# jev-MORPH


> **An agentic Windows desktop assistant that turns natural-language tasks into executable actions.**

jev-MORPH is a personal AI desktop agent built around a simple idea:

**You give it a task. JEV decides what should happen next. MORPH executes the action. The result becomes context for the next decision.**

Instead of relying on a fixed command for every workflow, jev-MORPH is designed to handle multi-step tasks through an agent loop.

---

## ✨ What is jev-MORPH?

jev-MORPH combines:

- **JEV** for action decisions
- **LLM-based parameter extraction** for turning natural language into structured inputs
- **Windows UI automation** for desktop actions
- **Structured action history** for maintaining task state
- **Gmail integration** for email sending with confirmation
- **Browser automation** for web searches
- **Safe, explicit action tools** instead of uncontrolled desktop inspection

The goal is not to build a chatbot that tells you what to click.

The goal is to build an agent that can **decide, act, observe the result, and continue**.

---

## 🧠 Core Agent Loop

```text
USER TASK
    ↓
JEV-MORPH DECIDES NEXT ACTION
    ↓
PARAMETER EXTRACTION
    ↓
SAFE ACTION TOOL
    ↓
ACTION RESULT
    ↓
STRUCTURED ACTION HISTORY
    ↓
JEV-MORPH DECIDES AGAIN
    ↓
DONE
    ↓
WAIT FOR NEXT TASK
```

Example:

```text
User:
"Open Notepad, type hello, then send an email saying testing morph."

        ↓

1. open_app
   app = notepad

        ↓

2. type_text
   text = hello

        ↓

3. send_email
   recipient = ...
   body = testing morph

        ↓

4. done
```

The important part is that the agent keeps track of what actually happened instead of treating every step as an isolated command.

---

## 🚀 Current Capabilities

jev-MORPH currently exposes these action types:

| Action | Status | Description |
|---|---|---|
| `open_app` | ✅ | Opens supported Windows applications |
| `type_text` | ✅ | Types text into the focused application |
| `search` | ✅ | Performs a browser search through the desktop |
| `calculate` | 🛠️ | Interacts with Windows Calculator |
| `wait` | ✅ | Pauses for a specified amount of time |
| `send_email` | ✅ | Sends Gmail messages after confirmation |
| `send_message` | 🚧 | Action is defined; WhatsApp integration is not currently connected |
| `done` | ✅ | Marks a task as complete |

### Example inputs

```text
open notepad
```

```text
type hello world
```

```text
search for AI agents
```

```text
calculate 125 * 8
```

```text
send an email to someone@example.com saying "testing morph"
```

And multi-step tasks:

```text
open notepad, type hello, then send an email saying testing morph
```

---

## 🏗️ Architecture

The project is intentionally built around small, explicit action tools rather than unrestricted desktop control.

### Decision Layer

JEV receives:

- the original task
- available actions
- current desktop state
- structured action history

It then selects the next action.

### Parameter Layer

A second model extracts the parameters needed by that action.

For example:

```json
{
  "action": "send_email",
  "parameters": {
    "recipient": "someone@example.com",
    "subject": "message from jev-morph",
    "body": "testing morph"
  }
}
```

### Execution Layer

The selected action is passed to a specific executor such as:

```text
execute_open_app()
execute_type_text()
execute_search()
execute_calculate()
execute_wait()
execute_send_email()
execute_send_message()
```

### State / History

Each completed step is stored in structured form:

```python
{
    "step": 1,
    "action": "open_app",
    "parameters": {
        "app": "notepad"
    },
    "status": "success",
    "result": "Notepad opened and focused."
}
```

This gives the agent a factual record of what already happened.

---

## 🔐 Safety Philosophy

jev-MORPH is intentionally **not** designed as a system that blindly controls every part of the desktop.

The project currently uses:

- explicit action types
- supported application allowlists
- parameter validation
- action results
- structured history
- confirmation before sending email
- bounded execution steps

The idea is:

> **Give the agent useful tools, not unlimited control.**

This also keeps the system easier to debug and improve.

---

## 📧 Gmail Integration

jev-MORPH can send emails through the Gmail API.

Before sending, the agent displays a preview and asks for confirmation.

Example:

```text
EMAIL PREVIEW

To: someone@example.com
Subject: message from jev-morph

testing morph

Send this? y
```

The default subject is:

```text
message from jev-morph
```

### Required files

Gmail authentication uses:

```text
credentials.json
token.json
```

These files should **never be committed to Git**.

---

## 🌐 Browser Search

The `search` action uses the desktop browser rather than treating search as a separate chatbot feature.

The intended flow is:

```text
search request
    ↓
open/focus browser
    ↓
focus address bar
    ↓
enter query
    ↓
submit
```

This keeps search inside the same desktop-agent execution model.

---

## 🖥️ Windows Focus & UI Automation

jev-MORPH uses Windows-specific automation tools to:

- detect the foreground window
- focus supported application windows
- interact with UI controls
- send keyboard input

The project is currently **Windows-only**.

---

## Tech Stack

- **Python**
- **OpenRouter**
- **JEV (`typesafe/jev-1.13`)**
- **OpenAI GPT-4o-mini** for parameter extraction
- **pywinauto**
- **pywin32**
- **Gmail API**
- **httpx**
- **python-dotenv**

---

## 📁 Project Structure

A simplified view:

```text
jev-agent/
│
├── main agent Python file
├── .env
├── credentials.json
├── token.json
├── README.md
└── .gitignore
```

Secrets and authentication files should remain local.

Recommended `.gitignore` entries:

```gitignore
.env
credentials.json
token.json
.venv/
__pycache__/
```

---

## ⚙️ Setup

### 1. Clone the project

```bash
git clone <your-repository-url>
cd jev-agent
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install httpx python-dotenv pywinauto pywin32 google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 4. Configure environment variables

Create:

```text
.env
```

and add your OpenRouter key:

```env
OPENROUTER_API_KEY=your_key_here
```

Do not commit the `.env` file.

### 5. Gmail setup

Place your Google OAuth desktop credentials in:

```text
credentials.json
```

On first authenticated use, Gmail OAuth will create:

```text
token.json
```

---

## ▶️ Running jev-MORPH

From PowerShell:

```powershell
python <main2>.py
```

Then enter a natural-language task, for example:

```text
open notepad and type hello
```

or:

```text
send an email to someone@example.com saying testing morph
```

---

## 🧪 Example Workflow

Input:

```text
open notepad, type hello, then draft an email saying testing morph
```

Conceptually:

```text
STEP 1
→ JEV chooses open_app

STEP 2
→ JEV chooses type_text

STEP 3
→ JEV chooses send_email

STEP 4
→ JEV chooses done

final architecture:
                    USER TASK
                       ↓
                 JEV-MORPH CORE
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
        AGENTIC ACTION      COMMUNICATION
              ↓                 ↓
       ┌──────────────┐    ┌──────────────┐
       │ open_app     │    │ send_email   │
       │ type_text    │    │ send_message │
       │ calculate    │    │              │
       │ search       │    │ Gmail        │
       │ press_key    │    │ WhatsApp     │
       │ wait         │    │              │
       └──────────────┘    └──────────────┘
              ↓                 ↓
              └────────┬────────┘
                       ↓
                  RESULT/STATE
                       ↓
                 JEV DECIDES AGAIN
                       ↓
                     DONE
```

Every step produces a structured result that becomes part of the next decision.

---

##  Current Limitations

jev-MORPH is an active project and several areas are still being improved.

Current limitations include:

- Windows-only operation
- search reliability is still being hardened
- Calculator UI automation is still being refined
- WhatsApp messaging is not currently connected
- the agent still needs stronger planning for complex nested workflows
- desktop automation depends on application-specific UI behavior

These limitations are part of the development process rather than hidden behind a polished demo.

---

##  Roadmap

### Near term

- Improve multi-step task planning
- Make nested workflows more reliable
- Improve browser search execution
- Make Calculator interaction robust
- Reduce accidental repeated actions

### Next stage

- Better task/subgoal tracking
- More desktop applications
- More reliable UI control discovery
- Better recovery from failed actions
- Richer action results

### Long term

The goal is to evolve jev-MORPH from a collection of desktop actions into a more capable **general-purpose personal desktop agent** that can translate natural-language goals into safe, observable workflows.

---

## 🎯 Project Philosophy

jev-MORPH is being built around a simple principle:

> **The agent should figure out the next useful action — not force the user to describe every button press.**

The project is intentionally being built step by step, with failures and edge cases becoming part of the engineering process.

---

## 📌 Project Status

**Status: Active Development 🚀**

jev-MORPH is a learning-driven agentic AI project focused on:

```text
Natural Language
      ↓
Reasoning
      ↓
Action
      ↓
Observation
      ↓
Iteration
```

Built with Python, JEV, LLMs, Windows automation, and a lot of debugging. 😄

---

## 👤 Author

Built as an independent agentic-AI project.

**jev-MORPH**  
*Think. Act. Observe. Repeat.*
