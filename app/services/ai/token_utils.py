"""
Token counting utilities for AI providers.

Provides consistent token counting across different providers,
with accurate counting for OpenAI and estimation for others.
"""

from functools import lru_cache


# Approximate characters per token for estimation
CHARS_PER_TOKEN_ESTIMATE = 4


@lru_cache(maxsize=8)
def _get_tiktoken_encoding(model: str):
    """
    Get tiktoken encoding for a model.

    Caches encodings for performance.
    """
    try:
        import tiktoken

        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to cl100k_base for unknown models
            return tiktoken.get_encoding("cl100k_base")
    except ImportError:
        return None


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text for the given model.

    Uses tiktoken for accurate OpenAI token counts,
    estimates for other models.

    Args:
        text: The text to count tokens for
        model: The model name (affects tokenization)

    Returns:
        Number of tokens
    """
    # Try tiktoken first (most accurate)
    encoding = _get_tiktoken_encoding(model)
    if encoding:
        return len(encoding.encode(text))

    # Fall back to estimation
    return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count without external libraries.

    Uses a rough heuristic of ~4 characters per token,
    which is approximately correct for English text.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0

    # Rough estimate: ~4 chars per token for English
    char_count = len(text)
    estimated = char_count // CHARS_PER_TOKEN_ESTIMATE

    # Adjust for whitespace and punctuation
    # These tend to be their own tokens
    word_count = len(text.split())
    punctuation_count = sum(1 for c in text if c in ".,!?;:\"'()-[]{}/<>")

    # Weighted estimate
    return max(1, (estimated + word_count + punctuation_count) // 2)


def count_message_tokens(
    messages: list[dict],
    model: str = "gpt-4",
) -> int:
    """
    Count tokens for a list of chat messages.

    Includes token overhead for message formatting.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: The model name

    Returns:
        Total token count including overhead
    """
    total = 0

    for message in messages:
        # Each message has overhead tokens
        # For GPT-4, approximately 4 tokens per message
        total += 4

        # Count tokens in role
        role = message.get("role", "")
        total += count_tokens(role, model)

        # Count tokens in content
        content = message.get("content", "")
        total += count_tokens(content, model)

        # Name field if present
        if "name" in message:
            total += count_tokens(message["name"], model)
            total += 1  # Extra token for name field

    # Add reply priming tokens (usually 3)
    total += 3

    return total


def truncate_to_token_limit(
    text: str,
    max_tokens: int,
    model: str = "gpt-4",
) -> str:
    """
    Truncate text to fit within a token limit.

    Tries to break at word boundaries for cleaner truncation.

    Args:
        text: The text to truncate
        max_tokens: Maximum tokens allowed
        model: The model name

    Returns:
        Truncated text
    """
    if not text:
        return text

    current_tokens = count_tokens(text, model)
    if current_tokens <= max_tokens:
        return text

    # Binary search for the right length
    words = text.split()
    low, high = 0, len(words)

    while low < high:
        mid = (low + high + 1) // 2
        truncated = " ".join(words[:mid])

        if count_tokens(truncated, model) <= max_tokens:
            low = mid
        else:
            high = mid - 1

    truncated = " ".join(words[:low])

    # Add ellipsis if truncated
    if low < len(words):
        truncated = truncated.rstrip(".,!?") + "..."

    return truncated


def get_model_context_limit(model: str) -> int:
    """
    Get the context window size for a model.

    Returns:
        Maximum tokens for the model's context window
    """
    # Model context limits (approximate)
    context_limits = {
        # OpenAI
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        # Anthropic
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-haiku-20241022": 200000,
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
        # Google
        "gemini-1.5-pro": 1000000,
        "gemini-1.5-flash": 1000000,
        "gemini-pro": 32000,
    }

    # Return known limit or default
    return context_limits.get(model, 4096)


def calculate_max_output_tokens(
    input_tokens: int,
    model: str,
    reserved_ratio: float = 0.25,
) -> int:
    """
    Calculate maximum output tokens given input.

    Reserves space for both input and response within context limit.

    Args:
        input_tokens: Number of input tokens
        model: The model name
        reserved_ratio: Ratio of context to reserve for output

    Returns:
        Maximum output tokens
    """
    context_limit = get_model_context_limit(model)
    available = context_limit - input_tokens

    # Reserve at least 25% of context for output, max 4096
    min_output = int(context_limit * reserved_ratio)
    max_output = min(4096, available)

    return max(min_output, max_output)
