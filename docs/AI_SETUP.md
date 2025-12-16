# AI Features Setup Guide

This guide covers how to set up and use the AI-powered research features in Perun's BlackBook.

## Overview

Perun's BlackBook includes AI-powered research capabilities that help you:
- Research people and companies using web search, video search, and podcast search
- Get AI suggestions for profile updates based on research
- Have natural conversations with AI about your contacts
- Use multiple AI providers (Claude, GPT-4, Gemini, or local models via Ollama)

## Quick Start

1. Navigate to **Settings > AI Providers** tab
2. Add an API key for at least one AI provider (Claude recommended)
3. Optionally add API keys for search providers (Brave Search, YouTube, Listen Notes)
4. Open any person or organization's profile
5. Click "AI Research" to open the chat sidebar
6. Start asking questions!

## AI Providers

### Supported Providers

| Provider | API Type | Cost | Best For |
|----------|----------|------|----------|
| **Claude (Anthropic)** | anthropic | ~$3/1M tokens | General research, high quality |
| **GPT-4 (OpenAI)** | openai | ~$3/1M tokens | Alternative to Claude |
| **Gemini (Google)** | google | ~$1.25/1M tokens | Budget-friendly option |
| **Ollama** | ollama | Free (local) | Privacy-focused, offline use |

### Getting API Keys

#### Anthropic (Claude)
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Create an API key in the dashboard
3. Paste it in Settings > AI Providers

#### OpenAI (GPT-4)
1. Sign up at [platform.openai.com](https://platform.openai.com)
2. Create an API key in API Keys section
3. Paste it in Settings > AI Providers

#### Google (Gemini)
1. Go to [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Paste it in Settings > AI Providers

#### Ollama (Local)
1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Run `ollama pull llama3` to download a model
3. Start Ollama: `ollama serve`
4. In Settings, enter the Ollama URL (default: `http://localhost:11434`)

## Search Providers

Search providers enable the AI to find real-time information about your contacts.

### Brave Search
- **Purpose**: Web and news search
- **Free tier**: 2,000 searches/month
- **Get key**: [api.search.brave.com](https://api.search.brave.com)

### YouTube Data API
- **Purpose**: Video/interview search
- **Free tier**: 10,000 quota units/day
- **Get key**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials) - Enable YouTube Data API v3

### Listen Notes
- **Purpose**: Podcast episode search
- **Free tier**: 300 requests/month
- **Get key**: [listennotes.com/api](https://www.listennotes.com/api/)

## Using AI Research

### Opening the AI Sidebar
1. Navigate to a person or organization's profile
2. Click the "AI Research" button (lightbulb icon) in the toolbar
3. The AI sidebar will slide in from the right

### Research Examples

**Finding recent news:**
```
What are the latest news articles about this person?
```

**Background research:**
```
What can you tell me about their professional background?
```

**Social media:**
```
Find their LinkedIn profile and recent activity
```

**Podcast appearances:**
```
Has this person appeared on any podcasts?
```

**Profile suggestions:**
```
Based on your research, suggest updates to their profile
```

### Quick Actions
The sidebar includes quick action buttons for common research tasks:
- Recent news
- Podcasts
- Background
- Suggest updates

### Understanding AI Suggestions

When the AI finds information that could update a profile, it will:
1. Create a suggestion with the field name and new value
2. Show the suggestion in the "Profile Updates" panel
3. Include a confidence score and source URL when available

You can:
- **Accept** individual suggestions to apply them
- **Reject** suggestions to dismiss them
- **Accept All** or **Reject All** for bulk actions

Each accepted suggestion creates a snapshot for easy rollback.

## Privacy & Data Access

### What Data is Shared
The AI can access:
- Basic profile information (name, title, company)
- Notes (if enabled in settings)
- Tags (if enabled)
- Interaction summaries (if enabled)
- LinkedIn URLs (if enabled)

### What is NEVER Shared
- Email addresses
- Phone numbers
- Detailed personal information

These are automatically stripped before any data is sent to external AI providers.

### Data Access Controls
Configure data access in **Settings > AI Providers > Data Access Controls**:
- Allow AI to see notes
- Allow AI to see tags
- Allow AI to see interaction history
- Allow AI to see LinkedIn URLs
- Auto-apply suggestions (use with caution)

## Usage Statistics

View your AI usage in **Settings > AI Providers**:
- Total conversations
- Total messages
- Token usage (input/output)
- Suggestions created/accepted/rejected

Token usage is tracked per-provider for cost estimation.

## Troubleshooting

### "No AI configured" message
1. Check that you have at least one AI provider with a valid API key
2. Ensure the provider is enabled (toggle switch is on)
3. Click "Test" to verify the API key works

### AI responses are slow
1. Cloud providers may have variable latency
2. For Ollama, ensure you have sufficient RAM/GPU
3. Try a different provider if issues persist

### Search isn't returning results
1. Verify search provider API keys are set and valid
2. Check that search providers are enabled
3. Some searches may genuinely have no results

### Suggestions not appearing
1. The AI must mention profile updates explicitly
2. Try asking: "Suggest profile updates based on your research"
3. Check that the suggested field is allowed (name, title, bio, etc.)

## Best Practices

1. **Start specific**: Ask about specific topics rather than broad questions
2. **Verify suggestions**: Always review AI suggestions before accepting
3. **Use snapshots**: Accepted suggestions create snapshots for easy undo
4. **Monitor costs**: Check usage statistics regularly if using cloud providers
5. **Try local first**: Use Ollama for testing to avoid API costs

## Technical Details

### Architecture
```
User Message
    │
    ├──► Context Builder (adds profile data)
    │
    ├──► Privacy Filter (removes sensitive data)
    │
    ├──► AI Provider (Claude/GPT/Gemini/Ollama)
    │
    ├──► Tool Execution (web search, podcast search, etc.)
    │
    └──► Suggestion Parser (extracts profile updates)
```

### Tool Capabilities
- `brave_search`: Web and news search
- `youtube_search`: Video search
- `podcast_search`: Podcast episode search
- `crm_lookup`: Look up related people/organizations in your CRM

### Conversation Storage
- All conversations are stored locally in your database
- Messages include token counts for usage tracking
- Conversations are linked to the person/organization they're about
