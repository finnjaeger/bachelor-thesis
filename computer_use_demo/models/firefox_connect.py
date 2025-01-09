import requests


def get_firefox_current_url(debugging_port=9222):
    """
    Connects to Firefox's remote debugging API and retrieves the URL of the current active tab.

    :param debugging_port: The port number where Firefox debugging is running (default: 9222)
    :return: The URL of the active tab or None if no active tab is found.
    """
    try:
        # URL for the debugging endpoint
        base_url = f"http://localhost:{debugging_port}/json"

        # Send GET request to retrieve all active tabs
        response = requests.get(base_url)

        # Check if the response is successful
        if response.status_code != 200:
            print(
                f"Failed to connect to Firefox debugging port: {response.status_code}"
            )
            return None

        # Parse the JSON response
        tabs = response.json()

        # Loop through tabs to find the first page type tab
        for tab in tabs:
            if tab.get("type") == "page":
                # Return the URL of the tab
                return tab.get("url")

        # If no tabs of type "page" are found
        print("No active tabs found.")
        return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None
