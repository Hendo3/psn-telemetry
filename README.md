# psn-telemetry

A data collection and visualization tool for PlayStation Network telemetry data.

## Overview

psn-telemetry is designed to collect, process, and visualize telemetry data from PlayStation Network (PSN). It provides insights into network performance, user activity, and system health through comprehensive data analysis and graphical representations.

## Features

- **Data Extraction**: Collect telemetry data from various PSN endpoints.
- **Sanitization**:
  - Removes telemetry errors (e.g., games with high playtime counts but zero trophies earned).
  - Normalizes titles to handle duplicates across different regions or console versions.
- **Analytics**: Classifies games based on playtime, trophy completion rates, and user engagement.
- **Visualization**: Generates a high density scatter plot to visualize user activity and game performance.

## Requirements

- Python 3.11+
- Required Python packages (listed in `requirements.txt`)

## Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/Hendo3/psn-telemetry.git
cd psn-telemetry

python -m venv venv
source venv/bin/activate  #Linux/Mac
venv\Scripts\activate    #Windows

pip install -r requirements.txt
```

## Configuration

This tool requires a valid PSN account and appropriate permissions to access telemetry data. Ensure you have the necessary credentials and API access.

1. Log in to your PSN account.
2. Navigate to <https://ca.account.sony.com/api/v1/ssocookie> and retrieve your SSO cookie.
3. Copy the SSO cookie value.
4. Create a `token.json` file in the project root with the following structure:

```json
{
 "np_sso": "YOUR_SSO_COOKIE_HERE"
}
```

NOTE: The `token.json` file is ignored by git to prevent accidental exposure of sensitive information.

## Usage

1. Run the extractor script to download and process PSN Data. This will create a JSON dump with your username.

```bash
python extractor.py
```

1. Generate the scatter plot visualization:

Run the visualizer to create the dashboard image. The script automatically detects the most recent JSON dump in the directory.

```bash
python visualizer.py
```

This will output a PNG file named after your PSN ID containing:

- Top 15 Most Played Games.
- Library Distribution (Games count by playtime range).
- Account Composition (Trophy completion rates).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
