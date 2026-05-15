pytest (unit tests) — tests the code in isolation:

Does _clean_floats() handle NaN correctly?
Does _validate_chart_data() return a tuple of 2?
Does _ac5_walled_garden_check() block cross-client SQL?
No real BQ connection, no real LLM calls
Fast (~2.5 min), cheap ($0), deterministic
Measures code coverage (68.5%)

ADK eval — tests the agent behavior end-to-end:

Does the agent actually answer "top 5 channels by spend" correctly?
Does it use the right tools in the right order?
Does it refuse out-of-scope questions?
Real BQ connection + real Gemini LLM calls
Slow (~1.5 min per eval), costs money (~$2-3 for 28 evals)
Measures agent quality (tool trajectory score, response match score, LLM judge)

Think of it like testing a car:
pytestADK evalWhatUnit/component testsFull system testTestsIndividual functionsWhole agent pipelineSpeedFast (2.5 min)Slow (40-50 min)CostFree~$2-3CatchesCode bugsWrong answers, hallucinations, routing errorsCoverageCode linesAgent behaviors
You need both:

pytest catches broken functions before deployment
ADK eval catches wrong agent answers that pass unit tests

For example, _ac5_walled_garden_check() might pass all unit tests but the agent could still leak cross-client data if the prompt is wrong — only eval catches that.