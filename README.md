## Completed

- University rules modeling
- Chunk quality experimentation (100w vs 150w)

TODOs
 
* more embedding models
* generating more ground truths
* deploying llm models locally and integrating third parties.
* experimenting the more embedding models with the more ground truths
* creating ground truths for LLM quality experimentation
* experimenting the LLM quality with the new ground truths
* creating complete school UML diagram and implementing it.
* Implementing core agent and required agents in the system
* Testing the best prompt for the best outcome. (agents)
* Complete first MVP that has all of our use cases working.
* Sİnce use cases working, make sure all apis are complete.
* Since all api contracts now complete, completely finish the frontend (minimally! - otherwise it will create more work)

This is the point where we can even stop working on the project, our achievement is seeing our event agent outputs internship events which was our problem.

Urgent TODOs:

* Complete DB schema according to use cases.
    - Implement typical school system entities
    - Research fastapi session implementation.
* ingesting almost all of the courses and documents we can find

## USE CASES

### Chatbot

A RAG based chatbot system that has access to all non-sensitive university data that will be able to answer various queries of users (instructors & students alike)

### Event System

A RAG based system that will periodically check university regulations and course rules in order to create various events (like informing students a deadline of a homework/project submission, suggesting students to take actions such as registering to erasmus programmes, etc.)

### Submission Check

A simple AI based system that will compare a document submitted aganist a ruleset (something like submission guidelines - a good example can be a homework submission guide that an instructor has provided) to give information to the user before submission about whether the submission is valid or not.

### SIS Related

A "Student Information System". Students and instructors can login, there can be departments, courses, sections, registrations, rules & guidelines, etc. to provide a comprehensive online platform for entirety of a university.