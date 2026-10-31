# Easy+Hitch pitch script

3mins max.

## Scene in endress office

*bjoern will come in with a bike and a helmet.*

**Bjoern:** "sorry im late to the meeting again, i didnt find a biking spot in
time."

**Julius:** "aah, have you ever checked out easy & hitch?"

**Bjoern:** "nooo, what is that?"

**Julius:** "its a new app piloting on the endress campus for solving exactly
this problem, they are installing little cameras around the campus to track
free biking spots right now."

**Bjoern:** "how does that work?"

## Demo

*(in the background the live 3d drive to the parking lot)*

**Julius:** "Imagine you ride down that road, you pick the next biking
spot that has a free parking spot. It will 3d guide you to the exact parking
lot and will directly tell you which ones are free, before you even arrive at
the parking lot."

## Architecture slide

*Then we will skip to the architecture slide.*

**Niklas** "So how does it work? On the left you have the edge, a tiny
ESP32 camera at the bike stand, and before a picture even leaves the edge,
we have vision models finding the data protection relevant stuff and pixelate them. Then it goes to AWS. We cut out every spot that changed
and asks Jev, a decision model, exactly one question every five seconds:
is there a bike, yes or no. Then the picture is gone directly, DynamoDB only
keeps which spots are taken and which are free. All images are deleted instantly, nobody gets tracked. And on the right you have the end user, using the app with the 3D view or connecting his agent via MCP. 

## After the architecture

**Bjoern:** "aaaaah, thats amazing though where do i need to download this?"

**Niklas & Julius:** "Well you can download it, but you can also directly plug
it into your grok bot, muse or openclaw directly if you want to. you dont need
to get the app even."
