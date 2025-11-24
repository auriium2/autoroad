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
         
# constraint related bug hit list
- 2.005ening: 2.005 was getting placed after 2.013 for some ungodly reason. It turns out the reason this was happening was 2.013 had a dependency on (2.005/2.051) and 2.051 had a single prereq 'permission of instructor', which our tokenizer and parser block turned into a single prereq group with nothing in it. (it was a prereq group with something in it, and then it gets deleted by the validator in the parser). This gives you a prereq group that is completely empty, which is then marked instantly as satisfied. This was done because previously weird strings like 'permission o' or 'ballet training' and other stupid shit instructors would put would sneak past my shitty handmade tokenizer, but now that we have a robust tokenizer and parser that doesnt happen, so what ended up happening was 2.051 was instantly satisfied and there was no need to the optimizer to handle it correctly.
- the course 7-ening: course 7
