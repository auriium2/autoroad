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
- Ah, you think vibe coding is your ally? You merely adopted the full stack. I was born in it, molded by it. I didn't touch the grass until I was already a man, by then it was nothing to me but frightening!

# le architecture
please fill this out later

frontend -> next.js proxy(auriium.xyz) -> fireroad api to fetch bulk data
         -> autoroad api(google cloud) -> google cloud server ->
