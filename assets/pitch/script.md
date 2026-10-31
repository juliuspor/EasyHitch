# Easy+Hitch: pitch script

Three minutes, four slides, three people. Rehearse to 2:45, so 15 seconds stay
spare for laughs and a slow demo.

| Who | Role |
|---|---|
| **Bjoern** | The rider who is late again. Bike, helmet, and a bell if there is one |
| **Julius** | Drives the phone in the demo, closes the tech part |
| **Niklas** | On the laptop (deck and screen), walks through the tech |

Say the name as "Easy and Hitch". Deck keys: → next, ← back, F full screen,
T timer (yellow at 2:30, red at 3:00), N notes.

| Time | Slide | Beat |
|---|---|---|
| 0:00 | 1 · Hello | Bjoern is late: no free bike spot |
| 0:30 | 2 · Demo | Live: the map, free spots, the rack in 3D |
| 1:20 | 3 · Tech | Edge, AWS, AI model, end user |
| 2:10 | 3 · Tech | "Where do I download this?" Plug it into your agent |
| 2:35 | 4 · Finale | "Easy+Hitch!" Fireworks, thank you |

---

## 0:00 · Late again (slide 1, Hello)

*Deck on slide 1 in full screen. Julius and Niklas stand by the screen as if
in a meeting at the Endress+Hauser office. Niklas presses T to start the
timer.*

**Julius:** "Okay, let's start the meeting. Where's Bjoern?"

**Niklas:** *(checks the time)* "Late. Again."

*Bjoern rushes in, pushing the bike, helmet still on, out of breath.*

**Bjoern:** "Sorry I'm late to the meeting again, I didn't find a biking spot
in time. Three laps around the campus!"

**Julius:** "Aah, have you ever checked out Easy+Hitch?"

**Bjoern:** "Nooo, what is that?"

**Niklas:** "It's a new app piloting on the Endress campus for exactly this
use case."

**Julius:** "They are installing little cameras around the campus to track
free biking spots right now."

**Bjoern:** "How does that work?"

*Niklas presses → for slide 2 and switches the screen to the live demo. On
the way, the hamster reaches the E+H office and shouts "FULL?!", same problem
as Bjoern.*

## 0:30 · The demo (slide 2, live)

*Screen: the live 3D drive down the road to the bike stand. Julius holds the
phone, mirrored on the screen.*

**Julius:** "Imagine you ride down that road, you pick the next biking spot
that has a free parking spot. It will 3D guide you to the exact parking lot
and will directly tell you which ones are free, before you even arrive at the
parking lot."

*Show the map: every station with its free spots.*

**Julius:** "Here's the whole campus, every bike stand and its free spots,
live."

*Tap the closest station that still has room. The card shows "[N] of [M]
free". Read the station and the numbers off the screen, for example
Christoph-Merian-Ring South.*

**Julius:** "[Station], [N] of [M] free. Directions are one tap away."

*Tap **View in 3D**: the rack in 3D, a bike on every taken spot.*

**Julius:** "And here's the rack in 3D. Every bike is taken, every gap is
yours."

**Bjoern:** "Okay, that would have saved me three laps this morning."

*Niklas switches the screen back to the deck and presses → for slide 3.*

## 1:20 · How it works (slide 3, Tech)

*Point at each cluster as you name it, left to right. The hamster pops "PIIs
removed", "Zero tracking" and "Edge computing" on its own, so don't wait for
it.*

**Niklas:** *(Edge)* "So how does it work? Four blocks. The edge: a tiny ESP32
camera at the bike stand. Before a picture even leaves it, YOLO finds faces,
PP-OCR finds licence plates, and we directly pixelate them."

**Niklas:** *(AWS and AI model)* "Then AWS. A Lambda cuts out every spot and
asks Jev, a decision model on OpenRouter, one question per spot: bike, yes or
no? No training data, and we only pay when a bike comes or goes."

**Julius:** *(DynamoDB)* "Then the picture is gone. DynamoDB only keeps 'spot
12 taken, spot 13 free'. No images, nobody tracked."

**Julius:** *(End user)* "On the right, the end user: the app with the 3D
view. And this box down here, AI agents. Keep that in mind."

**Julius:** "All of this is built and in our repo, running on the photos E+H
gave us."

## 2:10 · Where do I get it? (slide 3)

**Bjoern:** "Aaaaah, that's amazing though, where do I need to download this?"

**Niklas:** "Well you can download it,"

**Julius:** "but you can also directly plug it into your Grok bot, Muse or
OpenClaw directly if you want to."

**Niklas:** "You don't need to get the app even."

**Bjoern:** "So my AI tells me where to park, and I'm never late again?"

**Julius:** "Exactly."

*Niklas presses → for slide 4. The deck zooms in on the hamster at the tech
stand.*

## 2:35 · Finale (slide 4)

*About two seconds after the click, the hamster says "Easy+Hitch!". Say it
with the hamster, all three together.*

**All:** "Easy+Hitch!"

*Bjoern rings the bike bell. The hamster backflips off the tech stand,
fireworks go off, and the logo falls in.*

**Julius:** "You ride, we find the spot. Thank you!"

*Stop. Smile. Wait for the jury.*

---

## If something breaks

- **The live demo hangs:** go back to the deck's slide 2. Its phone plays the
  app on its own, and the same lines still fit.
- **No backend:** turn on **Demo data** in the app's settings (or launch with
  `-demoMode YES`). Built-in stations change every four seconds.
- **Running long:** drop "Three laps around the campus!" and Bjoern's
  "never late again" exchange. That saves about 8 seconds.
- **Clicked too far:** ← goes back, Home jumps to slide 1.

## If the jury asks

- **What is real today?** The whole pipeline is built: the camera pipeline,
  the backend on AWS Lambda, the iOS app and the MCP server. It runs on the
  photos from the hosts, and Jev read them live in 1 to 3 seconds per camera.
  The XIAO firmware builds, and running it on the board itself is next.
- **Stands without a camera?** A simulator fills the slots no camera reports,
  so the map is never empty. A new camera takes its slots over.
- **Privacy?** Faces and plates are pixelated before a frame leaves the edge.
  Frames stay in memory and are never written to disk. DynamoDB keeps slot
  states only, and nothing links a slot to a person.
- **How accurate?** On the recorded frames, 47 of 55 slots matched after two
  readings. A slot only flips on a sure answer, or on two unsure answers that
  agree.
- **What does it cost?** Low-cost camera boards, and a serverless backend
  that costs next to nothing while nobody parks. Jev is asked only about
  slots that changed, so we pay per bike that comes or goes, not per frame.
- **A new bike stand?** Mount a camera and draw its slot boxes once
  (a calibration). No training.
- **Which agents?** Any agent that speaks MCP. The MCP server answers the
  same questions as the app, and Claude Code connects with one command.

## Before we go on

- [ ] Bjoern: bike, helmet, bell
- [ ] Backend running with the simulator on (`BACKEND_SIMULATION=on`), the app
      connected to it, Demo data ready as plan B
- [ ] Phone mirrored on the screen, the 3D drive loaded
- [ ] Deck in full screen on slide 1 (F), the hamster has rolled out
- [ ] One full run with the timer (T)
