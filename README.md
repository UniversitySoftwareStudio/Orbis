# TODO

Development road:

- [x] Initialize the project
- [x] Set a proper architecture
- [ ] Add simple RAG implementation
- [ ] Add intent detection to RAG via keywords and Google API
- [ ] ...

*misc*

- [ ] Add github-actions for quality, security, etc...
- [ ] Understanding how to implement singleton pattern (model should be init once only)
- [ ] Understanding how to develop db structure strategy (embeddings + schemas)
- [ ] Understanding RAG to complex RAG need (Why we need it and etc...)

As the complexity increase in the system we will have more control over data which will allow use to execute more comples queries with complex RAG. Let's see where this takes us.

If structure looks complex, we can review it later.

# Running Instructions

- To run the ASP.NET Core backend, while inside ./api, run `dotnet watch run --project ControllerLayer` in terminal or navigate to ./api/ControllerLayer and run `dotnet watch run` in terminal
- To run the React frontend, while inside ./web, run `./run.sh` in terminal