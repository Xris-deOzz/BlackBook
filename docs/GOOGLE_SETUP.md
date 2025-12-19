# Google Cloud Project Setup Guide

**Document Version:** 2025.12.18.1
**Purpose:** Step-by-step instructions for setting up Google OAuth for Perun's BlackBook Gmail, Calendar, Contacts, and People API integration.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2025.12.18.1 | 2025-12-18 | Added Push to Google feature - bidirectional contacts sync now implemented; Updated feature enablement table |
| 2025.12.16.2 | 2025-12-16 | Verified all scopes working; Added Gmail compose utility; Added Workspace admin setup for custom domains; Updated troubleshooting section |
| 2025.12.16.1 | 2025-12-16 | Added comprehensive scope list including Gmail send/compose, Calendar events (read/write), People API (organization, phone, emails, birthday), Contacts API |
| 2025.12.08.1 | 2025-12-08 | Initial version with basic Gmail and Calendar readonly scopes |

---

## Overview

Perun's BlackBook integrates with Google services to:
- **Gmail:** Fetch email history, compose/send emails (Christmas emails feature)
- **Calendar:** Retrieve and create calendar events and meetings
- **Contacts:** Import and sync Google Contacts
- **People API:** Enrich contact profiles with work history, organization info, phone numbers

This requires a Google Cloud project with OAuth 2.0 credentials and appropriate scopes.

---

## Prerequisites

- A Google account (the same one you'll connect to BlackBook)
- Access to [Google Cloud Console](https://console.cloud.google.com/)

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)

2. Click the project dropdown at the top of the page (next to "Google Cloud")

3. Click **"New Project"** in the modal that appears

4. Enter project details:
   - **Project name:** `Perun's BlackBook` (or any name you prefer)
   - **Organization:** Leave as "No organization" (unless you have a Google Workspace org)
   - **Location:** Leave as default

5. Click **"Create"**

6. Wait for the project to be created (may take 30 seconds)

7. Make sure your new project is selected in the project dropdown

---

## Step 2: Enable Required APIs

1. In the left sidebar, navigate to **"APIs & Services"** → **"Library"**

2. Search for and enable each of these APIs:

   | API | Search Term | Purpose |
   |-----|-------------|---------|
   | Gmail API | `Gmail API` | Email read/send |
   | Google Calendar API | `Google Calendar API` | Calendar events |
   | People API | `People API` | Contact enrichment |
   | Contacts API | `Contacts API` | Google Contacts sync |

3. Verify all APIs are enabled:
   - Go to **"APIs & Services"** → **"Enabled APIs & services"**
   - You should see all four APIs listed

---

## Step 3: Configure OAuth Consent Screen

Before creating credentials, you must configure the OAuth consent screen.

1. In the left sidebar, go to **"APIs & Services"** → **"OAuth consent screen"**

2. Select **"External"** user type (unless you have Google Workspace, then choose "Internal")
   - Click **"Create"**

3. Fill in the **App Information**:
   - **App name:** `Perun's BlackBook`
   - **User support email:** Select your email from dropdown
   - **App logo:** (Optional) Skip for now

4. **App domain** section: Leave all fields blank (optional for development)

5. **Developer contact information:**
   - Enter your email address

6. Click **"Save and Continue"**

---

## Step 4: Configure OAuth Scopes

### Complete Scope Reference

The following scopes are configured for BlackBook (as of 2025.12.16):

#### Non-Sensitive Scopes
| API | Scope | Description | BlackBook Use |
|-----|-------|-------------|---------------|
| - | `.../auth/userinfo.email` | See primary Google Account email | User identification |
| - | `.../auth/userinfo.profile` | See personal info publicly available | User profile display |
| Gmail API | `.../auth/gmail.labels` | See and edit email labels | Future: email organization |
| Google Calendar API | `.../auth/calendar.calendarlist.readonly` | List of calendars subscribed to | Calendar selection |
| Google Calendar API | `.../auth/calendar.events.freebusy` | See availability on calendars | Meeting scheduling |
| People API | `.../auth/user.birthday.read` | See exact date of birth | Contact enrichment |
| People API | `.../auth/user.emails.read` | See all email addresses | Contact enrichment |
| People API | `.../auth/user.organization.read` | See education, work history, org info | **Key for CRM enrichment** |
| People API | `.../auth/user.phonenumbers.read` | See personal phone numbers | Contact enrichment |

#### Sensitive Scopes
| API | Scope | Description | BlackBook Use |
|-----|-------|-------------|---------------|
| - | `.../auth/calendar.readonly` | Download any calendar you can access | View calendar events |
| - | `.../auth/contacts.readonly` | See and download contacts | Import Google Contacts |
| - | `.../auth/contacts` | Edit, download, delete contacts | Sync contacts bidirectionally |
| Gmail API | `.../auth/gmail.send` | **Send email on your behalf** | **Christmas emails feature** |
| Google Calendar API | `.../auth/calendar.calendarlist` | Add/remove calendars subscribed to | Calendar management |
| Google Calendar API | `.../auth/calendar.calendars` | Change properties, create secondary calendars | Future: create CRM calendar |
| Google Calendar API | `.../auth/calendar.events` | **View and edit events on all calendars** | Create meetings with contacts |
| Google Calendar API | `.../auth/calendar.events.readonly` | View events on all calendars | View meeting history |
| People API | `.../auth/contacts.other.readonly` | See "Other contacts" (auto-saved) | **Import email-only contacts** |
| People API | `.../auth/profile.emails.read` | See all Google Account email addresses | Contact matching |

#### Restricted Scopes (Require Extra Justification)
| API | Scope | Description | BlackBook Use |
|-----|-------|-------------|---------------|
| Gmail API | `.../auth/gmail.readonly` | View email messages and settings | Email history for contacts |
| Gmail API | `.../auth/gmail.compose` | **Manage drafts and send emails** | **Compose emails from CRM** |
| Gmail API | `.../auth/gmail.settings.basic` | Edit email settings and filters | Future: CRM email filters |

### Adding Scopes in Google Cloud Console

7. On the **Scopes** page, click **"Add or Remove Scopes"**

8. Add all scopes listed above by:
   - Using the filter box to search
   - Or manually entering the full scope URL

9. Click **"Update"** to confirm scope selection

10. Click **"Save and Continue"**

### Test Users

11. On the **Test users** page, click **"Add Users"**

12. Enter all the Gmail addresses you want to connect:
    - `ossowski.chris@gmail.com`
    - `chris@blackperun.com`
    - `xris.chosser@gmail.com`
    - (any other accounts)

13. Click **"Add"**

14. Click **"Save and Continue"**

### Summary

15. Review your settings on the Summary page

16. Click **"Back to Dashboard"**

---

## Step 5: Create OAuth 2.0 Credentials

1. In the left sidebar, go to **"APIs & Services"** → **"Credentials"**

2. Click **"+ Create Credentials"** at the top

3. Select **"OAuth client ID"**

4. Configure the OAuth client:
   - **Application type:** `Web application`
   - **Name:** `BlackBook Web Client`

5. Under **Authorized redirect URIs**, click **"+ Add URI"** and enter:
   ```
   http://localhost:8000/auth/google/callback
   ```

   **For Synology deployment**, also add:
   ```
   http://<your-nas-ip>:8000/auth/google/callback
   http://<your-nas-hostname>:8000/auth/google/callback
   ```

   Example:
   ```
   http://192.168.1.100:8000/auth/google/callback
   http://synology.local:8000/auth/google/callback
   ```

6. Click **"Create"**

7. A modal will appear with your credentials:
   - **Client ID:** `xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com`
   - **Client Secret:** `GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx`

8. **Important:** Click **"Download JSON"** to save the credentials file

9. Copy the **Client ID** and **Client Secret** — you'll need these for the `.env` file

---

## Step 6: Configure BlackBook Environment

1. Open your `.env` file in the BlackBook project directory

2. Add the following variables:

   ```env
   # Google OAuth Configuration
   GOOGLE_CLIENT_ID=xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

   # Encryption key for storing OAuth tokens securely
   # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ENCRYPTION_KEY=your-generated-encryption-key-here
   ```

3. Generate an encryption key by running this command in PowerShell:

   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Copy the output and paste it as the `ENCRYPTION_KEY` value.

---

## Step 7: Update BlackBook OAuth Scopes (Code)

The application code must request the same scopes configured in Google Cloud. Update `app/services/google_auth.py`:

```python
# OAuth Scopes - must match Google Cloud Console configuration
GOOGLE_SCOPES = [
    # Non-sensitive scopes
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/user.birthday.read",
    "https://www.googleapis.com/auth/user.emails.read",
    "https://www.googleapis.com/auth/user.organization.read",
    "https://www.googleapis.com/auth/user.phonenumbers.read",
    
    # Sensitive scopes
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.calendarlist",
    "https://www.googleapis.com/auth/calendar.calendars",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "https://www.googleapis.com/auth/profile.emails.read",
    
    # Restricted scopes
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]
```

---

## Step 8: Verify Setup

After completing the BlackBook OAuth implementation, verify the setup:

1. Start BlackBook:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

2. Navigate to `http://localhost:8000/settings`

3. Click **"Connect Google Account"**

4. You should see Google's OAuth consent screen with the new permissions

5. Select the account you want to connect

6. Review and approve the requested permissions (you'll see more than before)

7. You should be redirected back to BlackBook with the account connected

---

## Feature Enablement by Scope

| Feature | Required Scopes | Status |
|---------|-----------------|--------|
| Email history viewing | `gmail.readonly` | ✅ Implemented |
| Calendar event viewing | `calendar.readonly` | ✅ Implemented |
| Import Google Contacts | `contacts.readonly` | ✅ Implemented |
| Import "Other" contacts | `contacts.other.readonly` | ✅ Implemented |
| **Push contacts to Google** | `contacts` | ✅ Implemented (2025-12-18) |
| **Send emails from CRM** | `gmail.send`, `gmail.compose` | 🔄 Ready to implement |
| **Create calendar events** | `calendar.events` | 🔄 Ready to implement |
| **Enrich profiles with work history** | `user.organization.read` | 🔄 Ready to implement |
| **Add phone numbers to profiles** | `user.phonenumbers.read` | 🔄 Ready to implement |
| Check calendar availability | `calendar.events.freebusy` | 🔄 Future |

---

## Google Workspace Domain Setup (Custom Domains)

If connecting a Google Workspace account (e.g., `chris@blackperun.com`), additional admin configuration is required.

### Why Workspace Accounts May Fail

Workspace accounts are managed by domain administrators who can restrict which third-party apps can access organization data. Even if the account is listed as a test user in Google Cloud Console, the Workspace admin must explicitly trust the app.

### Add BlackBook as Trusted App

1. Sign in to **Google Admin Console**: https://admin.google.com
   - You must be a Workspace administrator

2. Navigate to **Security** → **Access and data control** → **API controls**

3. Click **"MANAGE APP ACCESS"**

4. Click **"Add App"** → **"OAuth App Name or Client ID"**

5. Enter the BlackBook OAuth Client ID:
   ```
   154555900230-l9lhevrpfu3molr7v868782k7d1bi11i.apps.googleusercontent.com
   ```

6. Click **"Search"** and select **"BlackBook"**

7. Configure access:
   - **Scope:** Select your organization unit (e.g., `blackperun.com`)
   - **Access to Google Data:** Set to **"Trusted"**

8. Click **"Finish"**

9. Wait 30 seconds, then try connecting the Workspace account in BlackBook

---

## Troubleshooting

### "Access blocked: This app's request is invalid"

**Cause:** Redirect URI mismatch

**Fix:** 
- Go to Google Cloud Console → Credentials → Your OAuth Client
- Verify the redirect URI exactly matches what BlackBook is using
- Check for trailing slashes, http vs https, port numbers

### "Error 403: access_denied"

**Cause:** One of the following:
1. Your email is not in the test users list
2. Scope mismatch between code and Google Cloud Console
3. Google Workspace domain restrictions (for custom domain accounts)

**Fix for Test Users:**
- Go to OAuth consent screen → Audience → Test users
- **Remove** the email address (click trash icon)
- **Re-add** the same email address
- Save and try connecting again

**Fix for Scope Mismatch:**
- Verify scopes in `app/services/google_auth.py` match exactly what's enabled in Google Cloud Console → OAuth consent screen → Scopes
- Both sensitive and non-sensitive scopes must match

**Fix for Workspace Accounts:**
- See "Google Workspace Domain Setup" section above
- Add BlackBook as a trusted app in admin.google.com

### "Error 400: malformed request"

**Cause:** Invalid scope requested in the OAuth flow

**Fix:**
- One or more scopes in the code are not enabled in Google Cloud Console
- Check the error details for the exact scopes being requested
- Compare against scopes enabled in OAuth consent screen

### "This app isn't verified"

**Expected behavior** during development. Click:
1. "Advanced"
2. "Go to Perun's BlackBook (unsafe)"

This warning appears because the app hasn't gone through Google's verification process. For personal/self-hosted use, this is fine.

### Token Refresh Errors

If you see "invalid_grant" errors after some time:

**Cause:** Refresh token expired or revoked

**Fix:**
- Disconnect the account in BlackBook settings
- Reconnect and re-authorize

### "Scope has changed" or Re-authorization Required

**Cause:** You added new scopes after initial authorization

**Fix:**
- This is expected! Users must re-authorize to grant new permissions
- Disconnect and reconnect the account in BlackBook settings
- Remove and re-add the test user in Google Cloud Console if issues persist

---

## Publishing the App (Optional)

If you want to:
- Remove the "unverified app" warning
- Allow users outside your test list to connect
- Use the app without re-authorizing every 7 days

You'll need to **publish** the app and potentially go through Google's verification process.

**Note:** Restricted scopes (like `gmail.readonly`, `gmail.compose`) require additional verification including a security assessment. For a self-hosted personal CRM, staying in "Testing" mode is typically sufficient.

---

## Security Notes

1. **Never commit credentials to git**
   - `.env` is in `.gitignore`
   - Keep the downloaded JSON credentials file secure

2. **Encryption key**
   - The `ENCRYPTION_KEY` encrypts OAuth refresh tokens in the database
   - If you lose this key, users will need to re-connect their accounts
   - Back up this key securely

3. **Scope awareness**
   - With `gmail.send`, BlackBook CAN send emails on your behalf
   - With `calendar.events`, BlackBook CAN create/modify calendar events
   - With `contacts`, BlackBook CAN modify your Google Contacts
   - Use these features responsibly

4. **Token storage**
   - Refresh tokens are AES-256 encrypted before storing in PostgreSQL
   - Access tokens are short-lived and not stored

---

## Reference Links

- [Google Cloud Console](https://console.cloud.google.com/)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [People API Documentation](https://developers.google.com/people)
- [Contacts API Documentation](https://developers.google.com/contacts)
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
