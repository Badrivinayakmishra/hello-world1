# Local Development Guide

This guide will help you set up and run the Second Brain application on your local machine.

## Prerequisites

- Python 3.8+ (tested with Python 3.12)
- Node.js 18+
- OpenAI API key (already configured in `.env`)

## Quick Start

### Option 1: Using the Setup Script (Recommended)

```bash
# Run the setup script to install all dependencies
./setup_local.sh

# Start the backend (Terminal 1)
cd backend
source venv/bin/activate
python app_v2.py

# Start the frontend (Terminal 2)
cd frontend
npm run dev
```

### Option 2: Manual Setup

#### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Run the Flask server
python app_v2.py
```

The backend will start on `http://localhost:5003`

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will start on `http://localhost:3000`

## Environment Configuration

The `.env` file has been configured with:
- **OpenAI API**: Using your OpenAI API key
- **Database**: SQLite for local development
- **JWT Secret**: Auto-generated for local dev

### Optional Services

For full functionality, you can add these API keys to `.env`:

- **Pinecone** (Vector search): Get key from pinecone.io
- **Azure Speech** (Voice features): Get key from Azure portal
- **LlamaParse** (Document parsing): Get key from llamaindex.ai
- **Integration keys** (Gmail, Slack, Box): For syncing data

## Accessing the Application

1. Open your browser to `http://localhost:3000`
2. Sign up for a new account
3. Start using the knowledge management features

## Features Available Locally

With just the OpenAI API key:
- User signup/login
- Document upload
- AI-powered document classification
- Knowledge gap analysis
- RAG search
- Chat interface

Optional features (require additional API keys):
- Vector search (needs Pinecone)
- Voice transcription (needs Azure Speech)
- Gmail/Slack/Box integration (needs OAuth credentials)
- Advanced PDF parsing (needs LlamaParse)

## Troubleshooting

### Backend won't start

```bash
# Check if virtual environment is activated
which python  # Should point to venv/bin/python

# Check if dependencies are installed
pip list

# Check for errors in terminal
python app_v2.py  # Look for specific error messages
```

### Frontend won't start

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Check Node version
node --version  # Should be 18+
```

### Database errors

```bash
# Remove and recreate SQLite database
rm knowledge_vault.db
python app_v2.py  # Will recreate on startup
```

## Development Workflow

1. **Make changes** to backend code in `backend/`
2. **Restart Flask server** to see changes
3. **Frontend changes** hot-reload automatically
4. **Test locally** before committing

## Next Steps: Deploying to Production

Once local testing is complete, you can:
1. Push code to GitHub
2. Connect GitHub to Render
3. Set environment variables in Render dashboard
4. Deploy to production

See `DEPLOYMENT.md` for production deployment guide.

## Project Structure

```
use2ndbrain/
├── backend/              # Flask API server
│   ├── api/             # API route blueprints
│   ├── services/        # Business logic
│   ├── database/        # SQLAlchemy models
│   ├── vector_stores/   # Vector database
│   ├── connectors/      # Integration adapters
│   └── app_v2.py        # Main application
│
├── frontend/            # Next.js application
│   ├── app/            # Pages (App Router)
│   ├── components/     # React components
│   └── contexts/       # React contexts
│
├── .env                # Environment variables
└── setup_local.sh      # Setup automation script
```

## Questions or Issues?

- Check the CLAUDE.md file for project context
- Review the API documentation in the backend
- Open an issue on GitHub
