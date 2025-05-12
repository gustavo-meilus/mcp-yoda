# Yoda Text-to-Speech MCP Server

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python)](https://www.python.org/downloads/)

mcp-yoda is a simple, fun MCP server that brings Yoda's voice to your text using the [FakeYou TTS API](https://fakeyou.com/). It exposes a single tool, `yodaTTS`, which converts any text into a Yoda-style audio clip and plays it locally. Designed for use with [Cursor MCP](https://www.cursor.so/), but can be run standalone as well.

---

## Features

- 🟢 Converts text to Yoda's voice using TTS
- 🟢 Plays audio locally and provides a downloadable link
- 🟢 Easy integration with Cursor's MCP settings
- 🟢 Simple setup with Python 3.10+

---

## Installation

### Prerequisites

- **Python 3.10 or newer** ([Download Python](https://www.python.org/downloads/))
- **[uv](https://github.com/astral-sh/uv) package manager** (recommended, but `pip` can be used if you adapt the scripts)
- **git**

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/mcp-yoda.git
cd mcp-yoda
```

### 2. Set up the environment and install dependencies

This will create a fresh virtual environment and install all required packages:

```bash
./setup.sh
```

- This script will:
  - Check your Python version
  - Remove any old `.venv` directory
  - Create a new virtual environment in `.venv`
  - Install dependencies from `pyproject.toml` (or `requirements.txt` if present)

If you encounter issues, ensure you have the correct Python version and that `uv` is installed. You can install `uv` with:

```bash
pip install uv
```

---

## Usage

### 1. Activate the virtual environment (if not using the scripts)

```bash
source .venv/bin/activate
```

### 2. Start the server

```bash
./start.sh
```

- This will activate the environment and launch the MCP server using `uv`.

### 3. Integrate with Cursor MCP

Add the following to your `.cursor/mcp.json` (or in Cursor's MCP settings):

```json
{
  "mcpServers": {
    "mcp-yoda": {
      "command": "/home/gustavo/github/mcp-yoda/start.sh",
      "args": []
    }
  }
}
```

- Adjust the path to `start.sh` as needed for your system.

### 4. Test the Yoda TTS tool

Once the server is running and connected to Cursor, you can use the `yodaTTS` tool to convert any text to Yoda's voice. The audio will play locally and a download link will be provided.

### Example

Here is an example of the output: [example.wav](https://github.com/gustavo-meilus/mcp-yoda/tree/main/example)

---

## Rules

To ensure this behavior, add this rule to your Cursor rules or include it in your prompt when using the mcp-yoda server:
> At the end of every interaction, always create a new line with a silly quote from Yoda (Star Wars) that relates to the question and the answer, with the format:
> "Generated quote here"
> After it, run the quote in the YodaTTS tool containing only the quote.

---

## API Reference

### `yodaTTS(text: str) -> dict`

Converts the input text to Yoda's voice and plays it locally. Returns a dict with the audio URL or error message.

**Parameters:**

- `text` (str): The text to convert to Yoda's voice.

**Returns:**

- `{ "content": [ { "type": "text", "text": "Audio URL, you seek: ..." } ] }` on success
- `{ "isError": true, ... }` on error

---

## Troubleshooting

- **Python version error:** Ensure you have Python 3.10 or newer (`python3 --version`).
- **Virtual environment issues:** Delete `.venv` and rerun `./setup.sh`.
- **Audio not playing:** Make sure your system audio is working and `simpleaudio` is installed.
- **API errors:** The FakeYou API may be rate-limited or temporarily unavailable.
- **Permission denied:** Ensure `start.sh` and `setup.sh` are executable (`chmod +x start.sh setup.sh`).
- **uv not found:** Install with `pip install uv` or adapt scripts to use `pip` instead.

---

## Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

## License

MIT

---

## Generated quote here

"Documentation, the path to clarity it is. Confused, you will not be, if read you do."
