# Claude Autocomplete

A desktop application that provides real-time text suggestions using Claude AI.

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the project root with your Claude API key:
   ```
   CLAUDE_API_KEY=your_api_key_here
   ```
5. Run the application:
   ```bash
   python claude_autocomplete.py
   ```

## Usage

- Type in the text field to see suggestions
- Press Tab to accept a suggestion
- Use Ctrl+Enter for new lines
- The window stays on top for easy access while working in other applications

## Security Note

- Never commit your `.env` file or expose your API key
- The `.gitignore` file is configured to exclude sensitive information

## Features

- System-wide text monitoring
- AI-powered text suggestions using Claude
- Simple keyboard controls (Tab to accept, Esc to dismiss)
- Clean, minimal interface
- Works in any text input field

## Controls

- Tab: Accept the current suggestion
- Esc: Dismiss the current suggestion

## Note

The application requires an internet connection to communicate with Claude's API. 