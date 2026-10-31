# Easy+Hitch pitch script

3mins max.

## Scene in endress office

*bjoern will come in with a bike and a helmet.*

**Bjoern:** "sorry im late tothe meeting again, i didnt find a biking spot in
time."

**Niklas & Julius:** "aah, have you ever checked out easy & hitch?"

**Bjoern:** "nooo, what is that?"

**Niklas & Julius:** "its a new app piloting on the endress campus for exactly
this use case, they are installing little cameras around the campus to track
free biking spots right now."

**Bjoern:** "how does that work?"

## Demo

*(in the background the live 3d drive to the parking lot)*

**Niklas & Julius:** "Imagine you ride down that road, you pick the next biking
spot that has a free parking spot. It will 3d guide you to the exact parking
lot and will directly tell you which ones are free, before you even arrive at
the parking lot."

## Architecture slide

*Then we will skip to the architecture slide.*

**Niklas & Julius:** "So how does it work? On the left you have the edge, a tiny
ESP32 camera at the bike stand, and before a picture even leaves the edge,
YOLO finds the faces and PP-OCR finds the licence plates and we directly
pixelate them. Then it goes to AWS, a Lambda cuts out every spot that changed
and asks Jev, a decision model on OpenRouter, exactly one question per spot:
is there a bike, yes or no. No training data needed, and you only pay when a
bike actually comes or goes. Then the picture is gone directly, DynamoDB only
keeps which spots are taken and which are free, no images, nobody gets
tracked. And on the right you have the end user, the app with the 3D view, and
down here the AI agents, keep that in mind."

## After the architecture

**Bjoern:** "aaaaah, thats amazing though where do i need to download this?"

**Niklas & Julius:** "Well you can download it, but you can also directly plug
it into your grok bot, muse or openclaw directly if you want to. you dont need
to get the app even."
