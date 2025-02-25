# Spotify Wrapped Flask App

## Overview
This is a Flask-based web application that allows Spotify users to view their Spotify Wrapped. The app fetches data from the Spotify API and displays it in a visually appealing UI with animations and interactive charts.

## Features
- **User Authentication**: Log in with Spotify to access personalized Wrapped data.
- **Top Artists & Songs**: View your most-listened-to artists and songs.
- **Listening Stats**: Minutes listened, favorite genres, and ranking percentile.
- **Trends & Changes**: See how your music taste has evolved.
- **Year Selection**: Browse Wrapped data from 2022, 2023, 2024, and 2025.
- **Charts & Visuals**: Interactive graphs for genres, listening times, and trends.

## Installation
### Prerequisites
- Python 3.10+
- Spotify Developer Account
- Flask & Dependencies

### Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/KolwaBrad/spotify-wrapped-flask.git
   cd spotify-wrapped-flask
    ```
2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # For Unix/macOS
venv\Scripts\activate     # For Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. **Set up Spotify API credentials**
   * Go to Spotify Developer Dashboard
   * Create an app and note the **Client ID** and **Client Secret**.
   * Set the redirect URI to: `http://127.0.0.1:5000/callback`
   * Create a `.env` file and add:

```bash
ENVSPOTIFY_CLIENT_ID=your_client_id
ENVSPOTIFY_CLIENT_SECRET=your_client_secret
```
## Running the App
```bash
flask run
```
The app will be available at: `http://127.0.0.1:5000`

## API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET | Redirects user to Spotify login |
| `/callback` | GET | Handles authentication callback |



## License
MIT License

## Author
[KolwaBra] - GitHub: [https://github.com/KolwaBrad/]
