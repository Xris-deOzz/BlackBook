# Deploying Perun's BlackBook to Synology NAS

This guide walks you through deploying Perun's BlackBook to a Synology NAS with remote access via Tailscale.

## Deployment Status: COMPLETE

| Item | Value |
|------|-------|
| **NAS Model** | Synology DS220+ |
| **Server Name** | BearCave |
| **DSM Version** | 7.3.2-86009 |
| **RAM** | 2GB (tight - optimized config included) |
| **CPU** | Intel Celeron J4025 (2 cores, 2GHz) |
| **Tailscale Domain** | `bearcave.tail1d5888.ts.net` |
| **Access URL** | `https://bearcave.tail1d5888.ts.net/` |
| **Deployed** | December 16, 2025 |

## Prerequisites

- Synology NAS with Container Manager (Docker) support
- SSH access to NAS (recommended)
- Google Cloud Console account (for OAuth)
- Tailscale account (free tier works)

## Pre-Migration: Export Database from Windows

**IMPORTANT:** Do this BEFORE setting up Synology to migrate your existing data.

### Step 0.1: Export Current Database

Open PowerShell in your project folder and run:

```powershell
cd C:\Users\ossow\OneDrive\PerunsBlackBook
.\scripts\export_database.bat
```

This creates a backup file in `backups\` folder.

### Step 0.2: Note Your Current .env Values

You'll need these values for Synology:
- `ENCRYPTION_KEY` (CRITICAL - same key needed to decrypt OAuth tokens)
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY` (Gemini)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SYNOLOGY NAS                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Docker (Container Manager)              │   │
│  │  ┌─────────────┐    ┌─────────────┐                 │   │
│  │  │ blackbook-db│    │blackbook-app│                 │   │
│  │  │ PostgreSQL  │◄──►│   FastAPI   │                 │   │
│  │  │   :5432     │    │    :8000    │                 │   │
│  │  └─────────────┘    └──────┬──────┘                 │   │
│  └────────────────────────────┼────────────────────────┘   │
│                               │                             │
│  ┌────────────────────────────┼────────────────────────┐   │
│  │              Tailscale VPN (secure access)           │   │
│  └────────────────────────────┼────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
        ┌─────┴─────┐    ┌─────┴─────┐    ┌─────┴─────┐
        │  Desktop  │    │  Mobile   │    │  Laptop   │
        │  Browser  │    │  Browser  │    │  Browser  │
        └───────────┘    └───────────┘    └───────────┘
```

## Step 1: Prepare Synology NAS

### 1.1 Enable SSH (recommended)

1. Open DSM (Synology web interface)
2. Go to **Control Panel** → **Terminal & SNMP**
3. Enable SSH service
4. Note your NAS IP address

### 1.2 Install Container Manager

1. Open **Package Center**
2. Search for "Container Manager" (or "Docker" on older DSM)
3. Install it

### 1.3 Create Directory Structure

SSH into your NAS:

```bash
ssh admin@YOUR_NAS_IP
```

Create the required directories:

```bash
sudo mkdir -p /volume1/docker/blackbook/{postgres_data,backups,data,scripts}
sudo chown -R 1000:1000 /volume1/docker/blackbook
```

## Step 2: Copy Project Files

### Option A: Using Git (recommended)

```bash
cd /volume1/docker/blackbook
git clone https://github.com/Xris-deOzz/BlackBook.git .
```

### Option B: Using SCP

From your development machine:

```bash
scp -r PerunsBlackBook/* admin@YOUR_NAS_IP:/volume1/docker/blackbook/
```

### Option C: Using Synology File Station

1. Open File Station
2. Navigate to `/docker/blackbook`
3. Upload all project files

## Step 3: Configure Environment

### 3.1 Create .env file

```bash
cd /volume1/docker/blackbook
cp .env.production.example .env
nano .env  # or use your preferred editor
```

### 3.2 Generate Secure Keys

Generate the required secrets:

```bash
# Generate DB_PASSWORD
openssl rand -base64 32

# Generate SECRET_KEY
openssl rand -hex 32

# Generate ENCRYPTION_KEY
openssl rand -base64 32
```

### 3.3 Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Go to **APIs & Services** → **OAuth consent screen**
   - Configure consent screen (Internal or External)
   - Add scopes: `email`, `profile`, `openid`, plus Gmail and Calendar APIs
4. Go to **APIs & Services** → **Credentials**
   - Create OAuth 2.0 Client ID (Web application)
   - Add authorized redirect URI: `http://YOUR_TAILSCALE_IP:8000/auth/google/callback`
5. Copy Client ID and Secret to your `.env` file

### 3.4 Sample .env Configuration

```env
DB_NAME=perunsblackbook
DB_USER=blackbook
DB_PASSWORD=your_generated_password_here

SECRET_KEY=your_generated_secret_key_here
ENCRYPTION_KEY=your_generated_encryption_key_here

GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://100.x.x.x:8000/auth/google/callback
```

## Step 4: Deploy with Docker

### 4.1 Build and Start Containers

```bash
cd /volume1/docker/blackbook
docker-compose -f docker-compose.prod.yml up -d --build
```

### 4.2 Check Container Status

```bash
docker ps
docker logs blackbook-app
docker logs blackbook-db
```

### 4.3 Verify Deployment

Open a browser and navigate to:
```
http://YOUR_NAS_LOCAL_IP:8000
```

You should see the BlackBook dashboard.

## Step 5: Setup Tailscale (Remote Access)

### 5.1 Install Tailscale on Synology

1. Go to **Package Center** → **Settings** → **Package Sources**
2. Add: `https://pkgs.tailscale.com/stable/synology`
3. Go back to Package Center
4. Search for "Tailscale" and install it

### 5.2 Configure Tailscale

1. Open Tailscale from the main menu
2. Click "Log In"
3. Authenticate with your Tailscale account
4. Note the Tailscale IP assigned to your NAS (e.g., 100.x.x.x)

### 5.3 Enable MagicDNS (Required for HTTPS)

1. Go to https://login.tailscale.com/admin/dns
2. Enable **MagicDNS** if not already enabled
3. Your NAS gets a domain like: `bearcave.tail1d5888.ts.net`

### 5.4 Setup Tailscale Serve (HTTPS)

**IMPORTANT:** Google OAuth requires HTTPS for redirect URIs. Use Tailscale Serve:

```bash
# SSH into Synology
ssh admin@YOUR_NAS_IP

# Enable HTTPS proxy for BlackBook
sudo tailscale serve --bg http://localhost:8000
```

This creates:
- `https://bearcave.tail1d5888.ts.net/` → `http://localhost:8000`
- Automatic TLS certificate from Let's Encrypt
- No port needed in URL

Verify it's running:
```bash
tailscale serve status
```

### 5.5 Install Tailscale on Other Devices

Install Tailscale on:
- Your laptops: https://tailscale.com/download
- Your Google Pixel: Install from Play Store

**All devices must be signed into the same Tailscale account to access BlackBook.**

### 5.6 Update Google OAuth Redirect URI

Update `GOOGLE_REDIRECT_URI` in your `.env` file with the HTTPS URL:

```env
GOOGLE_REDIRECT_URI=https://bearcave.tail1d5888.ts.net/auth/google/callback
```

Restart the app:
```bash
docker-compose -f docker-compose.prod.yml restart app
```

## Step 6: Setup PWA on Mobile

### 6.1 Add to Home Screen (Android/Chrome)

1. Open Chrome on your Pixel 9
2. Navigate to `http://YOUR_TAILSCALE_IP:8000`
3. Tap the three-dot menu
4. Select "Add to Home screen"
5. Name it "BlackBook"

### 6.2 Add to Home Screen (iOS/Safari)

1. Open Safari
2. Navigate to `http://YOUR_TAILSCALE_IP:8000`
3. Tap the Share button
4. Select "Add to Home Screen"

## Step 7: Setup Automated Backups

### 7.1 Copy Backup Script

```bash
cp /volume1/docker/blackbook/scripts/backup.sh /volume1/docker/blackbook/scripts/
chmod +x /volume1/docker/blackbook/scripts/backup.sh
```

### 7.2 Create Scheduled Task

1. Open DSM
2. Go to **Control Panel** → **Task Scheduler**
3. Create → Scheduled Task → User-defined script
4. Configure:
   - Task: BlackBook Backup
   - User: root
   - Schedule: Daily at 3:00 AM
   - User-defined script: `/volume1/docker/blackbook/scripts/backup.sh`
5. Enable email notification (optional but recommended)

### 7.3 Test Backup

```bash
/volume1/docker/blackbook/scripts/backup.sh
ls -la /volume1/docker/blackbook/backups/
```

## Maintenance

### View Logs

```bash
docker logs -f blackbook-app
docker logs -f blackbook-db
```

### Restart Services

```bash
cd /volume1/docker/blackbook
docker-compose -f docker-compose.prod.yml restart
```

### Update Application

```bash
cd /volume1/docker/blackbook
git pull origin main  # if using git
docker-compose -f docker-compose.prod.yml up -d --build
```

### Restore from Backup

```bash
/volume1/docker/blackbook/scripts/restore.sh /volume1/docker/blackbook/backups/backup_YYYYMMDD_HHMMSS.sql.gz
```

## Troubleshooting

### Container won't start

```bash
docker logs blackbook-app
docker logs blackbook-db
```

Check for:
- Missing environment variables
- Port conflicts
- Permission issues

### Can't connect via Tailscale

1. Verify Tailscale is running on both devices
2. Check Tailscale admin console for device status
3. Try `ping YOUR_TAILSCALE_IP` from client device

### Google OAuth Error: redirect_uri_mismatch

**Common causes:**

1. **Wrong Client ID** - If you have multiple OAuth clients, make sure `.env` uses the same Client ID where you configured the redirect URI

2. **HTTP vs HTTPS mismatch** - Use HTTPS with Tailscale Serve:
   ```env
   GOOGLE_REDIRECT_URI=https://bearcave.tail1d5888.ts.net/auth/google/callback
   ```

3. **Redirect URI not added** - Go to Google Cloud Console → Credentials → Your OAuth Client → Add the exact redirect URI

**To diagnose:**
1. Check which Client ID your app is using (in `.env`)
2. Go to Google Cloud Console → Credentials
3. Find that specific OAuth Client ID
4. Verify the redirect URI is listed under "Authorized redirect URIs"

### Database Connection Issues

```bash
docker exec -it blackbook-db psql -U blackbook -d perunsblackbook
```

If it fails, check:
- DB credentials in `.env`
- Database container health: `docker ps`

## Security Notes

1. **Never expose port 8000 to the public internet** - Use Tailscale for remote access
2. **Keep your `.env` file secure** - Never commit it to version control
3. **Backup your ENCRYPTION_KEY** - Encrypted data cannot be recovered without it
4. **Enable 2FA on Tailscale** - Add an extra layer of security
5. **Regularly update containers** - `docker-compose pull && docker-compose up -d`

---

## Code Updates with GitHub

The codebase is version-controlled with Git and can be pushed to GitHub for easy updates.

### Initial Setup (Windows Development Machine)

```bash
cd C:\Users\ossow\OneDrive\PerunsBlackBook

# Already initialized - just add remote
git remote add origin https://github.com/Xris-deOzz/BlackBook.git
git push -u origin master
```

### Clone to Synology (First Time)

```bash
cd /volume1/docker/blackbook
git clone https://github.com/Xris-deOzz/BlackBook.git .
```

### Update Workflow

**1. Make changes on Windows with Claude Code**

```bash
# After making changes
git add .
git commit -m "Description of changes"
git push
```

**2. Pull and deploy on Synology**

```bash
ssh admin@bearcave
cd /volume1/docker/blackbook
git pull
sudo docker-compose -f docker-compose.prod.yml down
sudo docker-compose -f docker-compose.prod.yml build
sudo docker-compose -f docker-compose.prod.yml up -d
```

### Quick Deploy Script

Create `/volume1/docker/blackbook/deploy.sh`:

```bash
#!/bin/bash
cd /volume1/docker/blackbook
git pull
sudo docker-compose -f docker-compose.prod.yml down
sudo docker-compose -f docker-compose.prod.yml build --no-cache
sudo docker-compose -f docker-compose.prod.yml up -d
echo "Deploy complete! Check: https://bearcave.tail1d5888.ts.net/"
```

Make executable: `chmod +x deploy.sh`

Run: `./deploy.sh`

---

## What's Deployed

As of December 16, 2025:

| Metric | Count |
|--------|-------|
| **People** | 5,215 |
| **Organizations** | 1,867 |
| **Google Accounts** | 2 (krzysiek.ossowski@gmail.com, krzysztof@wolfstrom.com) |

### Icons Generated

Custom lightning bolt logo icons at all PWA sizes:
- 16, 32, 48, 72, 96, 128, 144, 152, 192, 384, 512px
- favicon.ico (multi-size)
- apple-touch-icon.png (180px)
