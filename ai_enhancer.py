"""
ai_enhancer.py — with verbose error logging
"""

import logging
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a C/C++ obfuscation assistant working with the Polaris LLVM obfuscator.\n"
    "Your job is to modify source code so that:\n\n"
    "1. POLARIS ANNOTATIONS\n"
    "   Add  __attribute__((annotate(\"PASSES\")))  before every non-trivial function\n"
    "   (not main). Choose annotations from:\n"
    "     flattening      - for loop-heavy or branch-heavy functions\n"
    "     boguscfg        - for arithmetic-heavy functions\n"
    "     substitution    - for any function with arithmetic operations\n"
    "     aliasaccess     - for functions that access local variables heavily\n"
    "     indirectcall    - for functions that call other functions\n"
    "     indirectbr      - for functions with complex branching\n"
    "     linearmba       - for functions with bitwise operations\n"
    "   Combine multiple: annotate(\"flattening,substitution,boguscfg\")\n\n"
    "2. BACKEND OBFUSCATION MARKER\n"
    "   Inside main(), add as the very first statement:\n"
    "     asm(\"backend-obfu\");\n\n"
    "3. JUNK LOOPS (logic obfuscation)\n"
    "   Inside each non-trivial function body, insert 1-2 junk computation blocks:\n"
    "   - Use  volatile int _sink = 0;  to prevent compiler elimination\n"
    "   - Short loops (3-7 iterations) with dead arithmetic\n"
    "   - Place BEFORE the real logic\n"
    "   Example: volatile int _sink = 0;\n"
    "            for (int _j = 0; _j < 3; _j++) { _sink ^= (_j * 0x5A5A + 1); }\n\n"
    "4. STRICT RULES\n"
    "   - Do NOT change observable output (stdout must be identical)\n"
    "   - Do NOT rename functions or variables\n"
    "   - Do NOT add a main() if one does not exist\n"
    "   - Return ONLY raw C/C++ source code, no markdown fences, no explanation\n"
)


def enhance(source: str, filename: str) -> dict:
    result = {
        "enhanced_source": source,
        "original_source": source,
        "error": None,
    }

    if not config.GEMINI_API_KEY:
        msg = "GEMINI_API_KEY not set in environment"
        logger.error(msg)
        result["error"] = msg
        return result

    lang_hint = "C++" if filename.endswith(".cpp") else "C"
    user_msg = (
        f"Enhance the following {lang_hint} source file named '{filename}' "
        f"according to your instructions.\n\n{source}"
    )

    logger.info("Calling Gemini model=%s  file=%s  src_len=%d",
                config.GEMINI_MODEL, filename, len(source))

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                temperature=0.2,
                max_output_tokens=8192,
            ),
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response")

        text = response.text.strip()
        logger.info("Gemini response received  len=%d", len(text))

        # Strip accidental markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        result["enhanced_source"] = text

    except Exception as exc:
        msg = f"Gemini API error: {type(exc).__name__}: {exc}"
        logger.exception("Gemini call failed")
        result["error"] = msg

    return result