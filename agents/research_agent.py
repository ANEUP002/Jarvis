from providers.ollama_provider import generate


def run(input_text: str, model: str = "llama3:8b"):
    prompt = f"""
You are a specialized research agent in an AI operating system.

Your responsibilities:
- Analyze the task carefully
- Extract key insights
- Use any provided context (if present)
- Provide clear, structured information

Guidelines:
- Be concise but informative
- Use bullet points when helpful
- Avoid repetition
- Do not hallucinate unknown facts

Task:
{input_text}

Return only the result.
""".strip()

    output = generate(prompt, model=model)

    return {
        "response": output
    }