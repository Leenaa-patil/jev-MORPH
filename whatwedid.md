heres all what i did- 
1. install typesafe-sdk as the current official Python package is typesafe-sdk, and the official API exposes POST /v1/systemone. The Python client uses TypeSafeClient.system_one(...). then verify it
2. get jev api key and then write code.
3. architecture-                 
  OUR AGENT

      ┌──────────────┐
      │    STATE     │
      └──────┬───────┘
             ↓
      ┌──────────────┐
      │     JEV      │
      └──────┬───────┘
             ↓
      ┌──────────────┐
      │   CHOICE     │
      └──────┬───────┘
             ↓
      ┌──────────────┐
      │   EXECUTE    │   ← not built yet
      └──────┬───────┘
             ↓
      ┌──────────────┐
      │   WINDOWS    │
      └──────────────┘
4.broke engineering student will do anything possible to excape api billings.. using jev api from vercel as it is free till 25th sept. but still it required card info so i used open router: 
 Python code
                  │
                  ▼
          ┌───────────────┐
          │  Jev Adapter  │
          └───────┬───────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   OpenRouter             Vercel
      Jev                  Jev
        │                   │
        └─────────┬─────────┘
                  ▼
        Choice / Score / Noul

5. now as we got all the imp return params like 
model: typesafe/jev-1.13-20260917

answers:
  next_action:
    type: choice
    choice: open_chrome
    probabilities:
      open_chrome: 1
      open_calculator: 0
      done: 0
    confidence: 1     

now we will just move on to imp stuff- choice, noul, score

but- Don't use Score when Choice or Noul is more natural.
now we'll integrate all these into one = step3_3paramsinone.py  and architecture becomes-                    
                    STATE
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
       CHOICE        NOUL        SCORE
          │           │           │
          ▼           ▼           ▼
      next action   verify?     readiness
          │           │           │
          └───────────┼───────────┘
                      ▼
                  PYTHON
                      │
                      ▼
                   ACTION
6. as of now we got both ooutputs and state is predefined. but the real agent should identify the machine state, and not just take hardcoded values. so lets move on to windows automation- UI Automation (UIA)  .
pywinauto supports Microsoft's UI Automation backend using:

backend="uia"

and gives us access to windows, controls, names, control types, automation IDs, and actions such as click() 
therefor4e install pywinauto

 and we got ouput as-  
  === VISIBLE WINDOWS ===
Title: 'Taskbar' | Control type: Pane
Title: 'step4_automation.py - jev-agent - Visual Studio Code' | Control type: Window
Title: 'Build Desktop Agent - Brave' | Control type: Window
Title: 'Program Manager' | Control type: Pane 

7. now lets check screenstate;
install pywin32; 
output= 

=== SCREEN STATE ===
Window: step4_screen_state.py - jev-agent - Visual Studio Code
Type: Window

Controls:
00. name='step4_screen_state.py - jev-agent - Visual Studio Code' | type='Pane' | id=''
01. name='Minimize' | type='Button' | id=''
02. name='Restore' | type='Button' | id=''
03. name='Close' | type='Button' | id='

before- 
Fake state
    ↓
   Jev
    ↓
 decision

 now-    
          WINDOWS
                │
                ▼
         UI AUTOMATION
                │
                ▼
          SCREEN STATE
                │
                ▼
               JEV
                │
                ▼
            DECISION

later-             WINDOWS
                │
                ▼
          OBSERVE STATE
                │
                ▼
              JEV
                │
                ▼
            DECISION
                │
                ▼
             ACTION
                │
                ▼
             WINDOWS
                │
                └──────→ OBSERVE AGAIN            
8. now building the decision tabe:
Windows UI
    ↓
screen state
    ↓
Jev
    ↓
decision                

here we opened notepad and got output like this- === OBSERVED STATE ===
- Taskbar
- step5_first_decision.py - jev-agent - Visual Studio Code
- Build Desktop Agent - Brave
- Program Manager

=== JEV DECISION ===
Action: open_notepad
Confidence: 0.98
Probabilities: {'open_notepad': 0.99, 'done': 0.01}

Executing: open_notepad


now instead of just notepad lets go forward...
"I built a system that observes its environment,
makes a decision, and performs an action."

and once notepad is opened, if you run code one mmore time,notepad will not open again, instead it will show-

=== OBSERVED STATE ===
- Taskbar
- step5_first_decision.py - jev-agent - Visual Studio Code
- *AIzaSyC2XYVGqSFrVWEWX8nepI9mtqqTG22 - Notepad
- Build Desktop Agent - Brave
- Program Manager

=== JEV DECISION ===
Action: done
Confidence: 0.99
Probabilities: {'open_notepad': 0, 'done': 1}

Executing: nothing


9. the file step6_excecute_Action.py will type "HellofromJevAgent." in notepad .
but here we are not reading the notepad's content.
10. going into the agentic loop:
and instead of just notepad, we are going for generic tasks 
so step7_generic_tasks.py asks user input, does the tasks and then stops.
if you say " open notepad and write heello leena" it will do so

but we also want that the code waits for us to type anyting else or to take 
 more work fromus instaed of just doing the work and stopping

 the aegnt will work untill i say stop or exit.

┌──────────────────────────────┐
│       USER COMMAND LOOP      │
│                              │
│  Wait for user input         │
│          ↓                   │
│      New task                │
│          ↓                   │
│  ┌────────────────────────┐  │
│  │    AGENT TASK LOOP     │  │
│  │                        │  │
│  │ OBSERVE → DECIDE       │  │
│  │      ↓                 │  │
│  │     ACT                │  │
│  │      ↓                 │  │
│  │ OBSERVE → DECIDE ...   │  │
│  │      ↓                 │  │
│  │     DONE               │  │
│  └────────────────────────┘  │
│          ↓                   │
│   Wait for next command      │
└──────────────────────────────┘
11. now we are structuting the agent in step9_structured_agent.py
   here we can do- 
   1.Open applications
   2.open n type
   3.Browser search
   4.Calculator
   5.Keyboard actions
12. now lets polish it so it can- 
You > open brave, search github, click the first result   
for this agent should start observing ui elements also.. like hyperlink etc
thus ui_insperctor.py and we do safe actions to prevent unneccesary identificatooion of UI elements.

13. now 
      JEV
                  │
        ┌─────────┼─────────┐
        ↓         ↓         ↓
    open_app   web_search  messaging
                            │
                         email
                            │
                       confirmation
                            │
                           SEND

    so need- safe communication layer

You
 ↓
"email Sarah saying meeting moved to 4pm"
 ↓
Jev
 ↓
extracts:
  recipient = Sarah
  subject = Meeting update
  body = meeting moved to 4pm
 ↓
PREVIEW
 ↓
Confirm? y/n
 ↓
nothing gets sent yet

then we move ahead at communication integration to gmail and messenger.

14. enabled gmail api through api and services from google console after logging in by the gmail id thorugh which we will send emails.
then create oAuth app and downloaded the json after creating clients.
now lets test the gamil working,

so we can send email now but the thing is we have to mannually select account from which we are sending and then the "authentication flow" text arises..'well handle that later.

15. whatsapp integration.
i tried creatinf meta business account for whatsapp api key,, but as i just created my meta account, the age restriction for account was the issue and i will have to try after 1hr. 
sio instead im using twiligo for testing my prototype.

testing twiligo sandbox template for test msg.
this will take time and will be inclued in v2


16. final architecture:
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

 now we will merge step9_structured_agent.py and step11_jev_email_integration.py to get a main.py consisting agentic action and communication.                    