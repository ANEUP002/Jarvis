from providers.ollama_provider import generate


def run(input_text: str, model: str = "codellama"):
    prompt = f"""
You are an expert software engineer.

Your responsibilities:
- Write clean, correct, production-quality code
- Follow best practices
- Use meaningful variable names
- Include comments if helpful

Guidelines:
- Be precise
- Do not include unnecessary explanations
- If explanation is needed, keep it brief

Task:
{input_text}

Return only the code (and brief explanation if necessary).
""".strip()

    output = generate(prompt, model=model)

    return {
        "response": output
    }