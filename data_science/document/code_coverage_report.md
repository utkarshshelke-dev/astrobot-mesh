# Code Coverage Report

Below is the summary of the code coverage generated after running all tests.

```
Name                                                                                         Stmts   Miss Branch BrPart  Cover   Missing
----------------------------------------------------------------------------------------------------------------------------------------
data_science/sub_agents/bqml/prompts.py                                                          4      0      0      0 100.0%
data_science/sub_agents/bigquery/prompts.py                                                      1      0      0      0 100.0%
data_science/sub_agents/bigquery/chase_sql/sql_postprocessor/correction_prompt_template.py       1      0      0      0 100.0%
data_science/sub_agents/__init__.py                                                              3      0      0      0 100.0%
data_science/lib/__init__.py                                                                     4      0      0      0 100.0%
data_science/__init__.py                                                                        11      0      0      0 100.0%
data_science/sub_agents/analytics/prompts.py                                                     3      1      0      0  66.7%   183
data_science/sub_agents/bigquery/agent.py                                                       29      8      6      0  60.0%   45-46, 59-66
data_science/prompts.py                                                                         22      9      2      1  58.3%   14-17, 30-34
data_science/sub_agents/analytics/agent.py                                                      19     11      4      1  39.1%   17-32, 37-38
data_science/lib/channel_resolver.py                                                            84     50     28      3  34.8%   26, 30, 55, 66-67, 74-82, 87-97, 102-103, 108-109, 172-206, 214-215, 220-221, 226, 231, 236
data_science/sub_agents/bigquery/chase_sql/llm_utils.py                                         87     56     20      0  29.0%   100-111, 130-151, 166-176, 197-237
data_science/sub_agents/bqml/tools.py                                                           64     46     14      0  23.1%   24-32, 47-62, 75-90, 113-116, 137-142, 188-191, 227-262, 292-294
data_science/sub_agents/bigquery/chase_sql/chase_db_tools.py                                    53     39      8      0  23.0%   58-64, 76-83, 99-158
data_science/utils/utils.py                                                                     36     28      2      0  21.1%   24-28, 44-48, 61-70, 85-94
data_science/agent.py                                                                          323    236    140      6  21.0%   38-41, 54-63, 66-67, 70-71, 87-89, 130-139, 147-158, 163-183, 201-249, 258-265, 281-370, 375-378, 397-483, 493-509, 517-526, 537-538, 540-541, 551-555, 568, 584-589, 596-601, 624->626
data_science/utils/knowledge_manager.py                                                         67     52     14      0  18.5%   50-68, 104, 108, 112, 136-146, 180-227, 245, 261-271
data_science/sub_agents/bigquery/chase_sql/sql_postprocessor/sql_translator.py                 173    131     60      0  18.0%   42, 51, 72, 86, 129-139, 144-148, 153-155, 165-204, 209-222, 229-257, 264-276, 281-292, 299-312, 338-363, 392-435, 457-488
data_science/sub_agents/bqml/agent.py                                                           78     60     26      0  17.3%   16-24, 32-52, 79-81, 93-137
data_science/lib/sql_builder.py                                                                 53     46      6      0  11.9%   28-39, 55-98, 121-130, 155-168, 194-201
data_science/sub_agents/bigquery/tools.py                                                      574    515    230      0   7.3%   70-118, 127-134, 139-143, 148-155, 192-201, 205, 209, 219-226, 238-252, 267-313, 318-355, 385-390, 420-446, 465-522, 537-568, 585-625, 638-674, 693-717, 742-798, 824-891, 920-956, 1010-1210, 1228-1246, 1251-1263, 1268-1279, 1284-1299, 1304-1339, 1386-1567, 1620-1803
data_science/lib/question_router.py                                                             47     43     20      0   6.0%   31-80, 96-117
data_science/tools.py                                                                          690    660    296      0   3.0%   21-38, 43-52, 57-75, 92-95, 130-147, 158-166, 170-171, 179-233, 241-258, 263-305, 310-336, 341-370, 378-845, 850-941
data_science/sub_agents/bigquery/chase_sql/chase_constants.py                                    4      4      0      0   0.0%   17-23
----------------------------------------------------------------------------------------------------------------------------------------
TOTAL                                                                                         2430   1995    876     11  13.7%
```

A more detailed, interactive HTML report can be found at `htmlcov/index.html`.
