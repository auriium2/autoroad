# autoroad

## architecture: frontend
- i used nextjs/react for the frontend since react is well known by llms and i don't want to debug frontend myself when i don't have to
- i tried to avoid as much backend surface as possible by routing as much work as possible to the fireroad api via cors. 
- this means I don't have to maintain boilerplate for authentication, etc, and can focus on the optimization logic on the backend

## architecture: backend
- i used python/fastapi for the optimizer endpoint. python was chosen ~~so i can get a job~~ so i can use the ortools library for integer programming. fastapi was chosen for its speed and ease of use.
- serverless!!!!!!!!!
- the workers are designed to be horizontally scalable, since all they have to do is run the optimization and then die

## ai usage
- frontend built entirely with ai assistance. the frontend design, however, was mine. I used a combination of claude and copilot to generate the frontend code. I had to do some manual work to connect the frontend to the backend, but overall it was a huge time saver.
- backend unit testing, regression testing, etc done by ai. no human should be forced to write unit tests.
- please employ me

# le architecture
please fill this out later

frontend -> fireroad api(fireroad.mit.edu) -> fetch single data
         -> next.js proxy(auriium.xyz) -> fetch bulk data
         -> autoroad api(google cloud) -> google cloud server ->
