import requests
import json
import os

# --- Configuration ---
CLOUD_RUN_URL = "https://astrobot-ds-866797370377.us-central1.run.app/run" # Corrected: Uses /run endpoint
APP_NAME = "data_science" # The name of your data science agent application

# --- Queries to demonstrate the agent ---
queries = [
    "What was the total ad spend last year?",
    "How does the bot define last year? It should offer L12Months or full calendar year of 2024. We have lots of date flags in GVMM, calendar/fiscal/business should all be in consideration",
    "What was the revenue last year?",
    "Break it out by month, by channel?",
    "Channel, region/geo,", # This seems like an incomplete query, might need to be phrased as a question
    "What were last month’s spend and ROAS by channel?",
    "What was total spend yesterday vs 7-day and 28-day averages?",
    "Is today’s data complete or still updating?",
    "Any zeros, duplicates, or sudden ±50% spikes I should flag?",
    "Does channel spend sum to the account total (within ~1%)?",
    "Any channel at /usr/bin/bash spend or /usr/bin/bash conversions unexpectedly?",
    "Any campaign’s spend up/down >20% day-over-day?",
    "Blended ROAS move >20% vs prior day/week?",
    "CPA/CAC change >20% anywhere?",
    "What does new vs returning customer mix look like?",
    "Define the business goal: revenue, gross profit, subscriptions, qualified leads, or something else?",
    "Spike in view-through conversions share (attribution shift)?",
    "Daily pacing on track vs plan and month-end target?",
    "Identify the attribution model and lookback windows per channel (last-click, data-driven, MMM, blended).",
    "Budgets capping early in the day (lost impression share)?",
    "Diminishing Returns: At what spend level does Social or Search stop producing incremental Transactions (the 'Saturation Point')?",
    "Efficiency Ranking: If we ranked channels by 'Transactions per Dollar Spent,' which three channels consistently sit at the bottom?",
    "Budget Reallocation: Based on historical performance, how should the next 00k be distributed across these channels to maximize total Transactions?",
]

def run_demo(url: str, app_name: str, query_list: list[str]):
    headers = {
        "Content-Type": "application/json"
    }

    print(f"--- Starting Data Science Agent Demo ---")
    print(f"Agent URL: {url}\n")

    for i, query in enumerate(query_list):
        print(f"--- Query {i+1}/{len(query_list)} ---")
        print(f"User: {query}")

        payload = {
            "app_name": app_name,
            "user_id": "demo_user", # A static user ID for demonstration purposes
            "session_id": f"demo-session-{i+1}", # Unique session ID for each query
            "new_message": {
                "parts": [
                    {
                        "text": query
                    }
                ]
            },
            "streaming": False,
            "config": {}
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

            agent_response = response.json()
            # The /run endpoint returns a list of Events. We need to extract the relevant content.
            print("Agent:")
            if agent_response and isinstance(agent_response, list):
                for event in agent_response:
                    if "content" in event and event["content"]:
                        # Extract text from content parts
                        if "parts" in event["content"] and event["content"]["parts"]:
                            for part in event["content"]["parts"]:
                                if "text" in part:
                                    print(f"  {part['text']}")
                                else:
                                    print(f"  {json.dumps(part, indent=2)}")
                        else:
                             print(f"  {json.dumps(event['content'], indent=2)}")
                    elif "actions" in event and event["actions"]:
                        # If no content, maybe there are actions (e.g., tool calls)
                        print(f"  [Action]: {json.dumps(event['actions'], indent=2)}")
                    else:
                        print(f"  [Event]: {json.dumps(event, indent=2)}")
            else:
                print(f"  {json.dumps(agent_response, indent=2)}")

        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
        except json.JSONDecodeError:
            print(f"Failed to decode JSON response: {response.text}")
        print("\n" + "="*80 + "\n") # Separator for readability

if __name__ == "__main__":
    run_demo(CLOUD_RUN_URL, APP_NAME, queries)
