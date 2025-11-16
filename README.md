# autoroad


## architecture: frontend
- i used nextjs/react for the frontend since react is well known by llms and i don't want to debug frontend myself when i don't have to
- i tried to avoid as much backend surface as possible by routing as much work as possible to the fireroad api via cors. 
- this means I don't have to maintain boilerplate for authentication, etc, and can focus on the optimization logic on the backend

## architecture: backend
- i used python/fastapi for the optimizer endpoint. python was chosen ~~so i can get a job~~ so i can use the ortools library for integer programming. fastapi was chosen for its speed and ease of use.
- the backend has the unglorified task of offloading optimization work to workers who run the integer programming solver, and then stream results back to the frontend via redis streams.
- the workers are designed to be horizontally scalable, since all they have to do is run the optimization and then die

## ai usage
- frontend built entirely with ai assistance
- backend unit testing, regression testing, etc done by ai
- please employ me
