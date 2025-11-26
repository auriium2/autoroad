# autoroad
> fixed horizon trajectory optimization for your mit degree

# TLDR
- pick classes you *want* to take
- pick degrees and concentrations you want
- pick semester or 4year goals that matter to *you*
- let autoroad fill out the rest

## How do I use this?
Try it out at [autoroad.auriium.xyz](https://autoroad.auriium.xyz)

## Why does this exist?

To plan one (1) feasible degree at mit, you have to consider:
- the degree requirements of the girs
  - all of the girs and their placement
  - which of the girs to take (some are worse than others)
  - the hass requirement, which states that you must
    - take at least 8 humanities classes
    - from these 8, one of each must be a hass h, hass a, hass s
  - you must also take 4 ci-h writing-type classes (which *may or may not also be hasses*)
    - two must be ci-h classes (writing type under the hass requirement)
    - two must be ci-m classes (writing type under the major)
    - not all hasses are ci-type
  - you must take a REST (Restricted Elective in SomeThing) class
- the degree requirements of your current degree
  - depending on your major, these can be arbitrarily nested [in increasingly convoluted ways](https://fireroad.mit.edu/requirements/edit/major6-3new).
- the class requirements of your mandatory [humanities concentration](https://registrar.mit.edu/registration-academics/academic-requirements/hass-requirement/hass-concentrations)
  - this is *not the same thing* as the hasses OR ci-types
  - yes, you have to have a humanities concentration at mit
  - no, i do not want a concentration in linguistics
- the fact that all of these courses have *prerequisites* that may break down if you fail or decide to take a different class

If you want your degree to not kill you or make you bald, you have to consider and exploit:
- classes have different amounts of units
- classes have different amounts of hours (you want less of these)
- classes have different ratings and enrollments (do not take a class rated under 5)

As both a fake mechanical engineer and a fake CS major, trying to solve this convoluted mess by hand for *two different degrees* was wasting time. So, I sat down and built autoroad!

## How does it work?

Define binary decision variables for every (course, semester) pair. Add constraints:
- Prerequisites must come before dependent courses
- Degree requirements (reverse-engineered from Fireroad's source)
- Unit caps, no double-counting, user pins

Then optimize across 11 objectives with diminishing returns:
- Minimize total units
- Balance workload per semester
- Avoid finals conflicts
- Minimize friday classes
- Prioritize requirement satisfaction
- etc.

The solver runs multi-threaded and streams solutions in real-time over SSE.

## Stack

**Backend**: Python, FastAPI, OR-Tools  
**Frontend**: Next.js + React  
**Deploy**: Vercel + Google Cloud Run

## Important Lessons for prospective contributors
- or tools's integer programming is nondeterministic when you run it via xtest
- fireroad's distinct threshold progress api is logically incorrect

## AI Usage
- Ah, you think vibe coding is your ally? You merely adopted the full stack. I was born in it, molded by it. I didn't touch the grass until I was already a man, by then it was nothing to me but frightening!

## Testing
- Autoroad has an extensive integration test suite that you can run using pytest -m slow, and a variety of more simple unit tests
 - The integration test suite is battle tested (literally) and has already caught like 14 huge bugs with the old requirements constraint builder. If it fails your code is probably not working
 - The fuzzer tests and unit tests are less reliable, since they are ai generated, but can still catch simple mistakes
 - As the integration test suite runs the optimizer for every test case, it's recommended to use the github workflow as it parallelizes testing using testing matrix.

## Credits
- auriium2
- ricardo ochoa for telling me to add category weighting
- reactflow, for their great graph library
- SIPB, for making and maintaining the fireroad api and the original Courseroad!
