# Gemini SDK Migration: Gemini 3 Pro Support

**Document Version:** 2025.12.12.1  
**Status:** 🔄 Pending Implementation  
**Related:** Phase 5 AI Assistant  

---

## Overview

Migrate the Google/Gemini AI provider from the legacy `google-generativeai` SDK to the new `google-genai` SDK to enable **Gemini 3 Pro** support with advanced reasoning and function calling capabilities.

---

## Why This Migration?

| Feature | Old SDK | New SDK |
|---------|---------|---------|
| Gemini 3 Pro | ❌ Not supported | ✅ Full support |
| Thinking Levels | ❌ | ✅ Control reasoning depth |
| Thought Signatures | ❌ | ✅ Multi-turn function calling |
| Async Support | Partial | ✅ Native async |
| Google Recommended | ❌ Legacy | ✅ Active development |

---

## Scope

### Files to Modify
- `app/services/ai/google_provider.py` - Complete rewrite
- `requirements.txt` - Add `google-genai>=1.0.0`

### Models After Migration
| Model | Purpose |
|-------|---------|
| `gemini-3-pro-preview` | Most capable, advanced reasoning |
| `gemini-2.5-pro` | Balanced performance |
| `gemini-2.5-flash` | Fast responses |
| `gemini-2.0-flash` | Default (cost efficient) |

---

## Key Implementation Details

### New SDK Pattern
```python
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents="Your prompt",
    config=types.GenerateContentConfig(
        temperature=1.0,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(thinking_level="high")
    ),
)
```

### Thinking Levels (Gemini 3 Only)
- `low` - Fast responses, minimal reasoning
- `medium` - Balanced (currently not supported by API)
- `high` - Deep reasoning (default for Gemini 3)

### Temperature Warning
Gemini 3 is optimized for `temperature=1.0`. Lower values may cause looping or degraded performance.

### Thought Signatures
Required for multi-turn function calling. The SDK handles this automatically, but signatures must be preserved in conversation history.

---

## Tasks

1. **Update requirements.txt** - Add `google-genai>=1.0.0`
2. **Rewrite GoogleProvider** - New SDK patterns
3. **Update message conversion** - New `types.Content` format
4. **Update tool definitions** - New `types.Tool` format
5. **Add thinking_level parameter** - For Gemini 3 models
6. **Update validate_key()** - New client pattern
7. **Update count_tokens()** - New API method
8. **Handle async properly** - Use `client.aio.models.*`

---

## Documentation Links

- **Gemini 3 Developer Guide:** https://ai.google.dev/gemini-api/docs/gemini-3
- **SDK Migration Guide:** https://ai.google.dev/gemini-api/docs/migrate
- **Function Calling:** https://ai.google.dev/gemini-api/docs/function-calling
- **Thinking Levels:** https://ai.google.dev/gemini-api/docs/thinking
- **Thought Signatures:** https://ai.google.dev/gemini-api/docs/thought-signatures

---

## Testing Checklist

- [ ] API key validation works (Test button in Settings)
- [ ] Basic chat with Gemini 2.0 Flash
- [ ] Chat with Gemini 3 Pro Preview
- [ ] Streaming responses work
- [ ] Token counting works
- [ ] Function calling works (for future CRM updates)

---

## Future: CRM Update Workflow

Once Gemini 3 Pro is working, we'll implement function calling for AI-suggested profile updates:

```
User: "Research John Smith at Acme Capital"
    ↓
AI researches via web search
    ↓
AI calls: update_person_profile(person_id=123, fields={...})
    ↓
User sees: "AI suggests these updates:" [Approve] [Edit] [Reject]
    ↓
User approves → Database updated
```

This requires the Thought Signatures feature from Gemini 3.
