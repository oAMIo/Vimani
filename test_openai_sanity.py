import os

from openai import OpenAI


def main() -> None:
    """
    One-off sanity check script for OpenAI connectivity.

    - Reads OPENAI_API_KEY from the environment
    - Makes a single OpenAI Responses API call
    - Prints the raw text response
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set in the environment.")
        return

    client = OpenAI(api_key=api_key)

    print("Calling OpenAI Responses API...")
    response = client.responses.create(
        model=os.getenv("VIMANI_PLANNER_MODEL", "gpt-4.1-mini"),
        input="Say a short hello message to confirm connectivity.",
        response_format={"type": "text"},
    )

    try:
        text = response.output[0].content[0].text  # type: ignore[attr-defined]
        print("OpenAI response text:")
        print(text.value)
    except Exception as exc:  # pragma: no cover - defensive
        print("ERROR: Unexpected response shape from OpenAI:", repr(exc))
        print("Full response object:", response)


if __name__ == "__main__":
    main()




