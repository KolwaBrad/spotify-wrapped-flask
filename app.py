import os
import json
import datetime
from flask import Flask, redirect, request, session, render_template, url_for, jsonify
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from collections import Counter, defaultdict
from itertools import groupby
from operator import itemgetter
import calendar
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Configure Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv('ENVSPOTIFY_CLIENT_ID')  # Replace with your actual client ID
SPOTIFY_CLIENT_SECRET = os.getenv('ENVSPOTIFY_CLIENT_SECRET')  # Replace with your actual client secret
SPOTIFY_REDIRECT_URI = "http://localhost:5000/callback"
SCOPE = "user-read-private user-read-email user-top-read user-read-recently-played user-read-playback-state playlist-read-private user-library-read"

# Initialize Spotify OAuth
sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SCOPE
)

# Helper function to get or refresh Spotify token
def get_token():
    token_info = session.get('token_info', None)
    if not token_info:
        return None
    
    now = int(datetime.datetime.now().timestamp())
    is_expired = token_info['expires_at'] - now < 60
    
    if is_expired:
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    
    return token_info

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Login route to authenticate with Spotify
@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# Callback route after Spotify authentication
@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('wrapped'))

# Wrapped dashboard route
@app.route('/wrapped')
def wrapped():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))
    
    # Get Spotify client
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    # Get user profile
    user_profile = sp.current_user()
    
    # Return the wrapped template
    return render_template('wrapped.html', user=user_profile)

# API endpoint to get all wrapped data
@app.route('/api/wrapped-data')
def get_wrapped_data():
    token_info = get_token()
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    # Get top artists (short, medium, and long term)
    top_artists_short = sp.current_user_top_artists(limit=10, time_range='short_term')
    top_artists_medium = sp.current_user_top_artists(limit=10, time_range='medium_term')
    top_artists_long = sp.current_user_top_artists(limit=50, time_range='long_term')
    
    # Get top tracks (short, medium, and long term)
    top_tracks_short = sp.current_user_top_tracks(limit=50, time_range='short_term')
    top_tracks_medium = sp.current_user_top_tracks(limit=50, time_range='medium_term')
    top_tracks_long = sp.current_user_top_tracks(limit=50, time_range='long_term')
    
    # Get recently played tracks (for better analysis)
    recently_played = sp.current_user_recently_played(limit=50)
    
    # Get saved tracks (for better analysis)
    saved_tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    saved_tracks.extend(results['items'])
    while results['next']:
        results = sp.next(results)
        saved_tracks.extend(results['items'])
        if len(saved_tracks) >= 200:  # Limit to 200 tracks to avoid too many requests
            break
    
    # Get playlists
    playlists = sp.current_user_playlists(limit=50)
    
    # Extract genres from top artists
    genres = []
    for artist in top_artists_long['items']:
        genres.extend(artist['genres'])
    
    # Count genre occurrences
    genre_counts = Counter(genres)
    top_genres = [{"genre": genre, "count": count} for genre, count in genre_counts.most_common(10)]
    
    # Estimate total listening time (approximate based on available data)
    # Spotify API doesn't provide exact listening time, so this is an approximation
    avg_track_duration_ms = sum(track['duration_ms'] for track in top_tracks_long['items']) / len(top_tracks_long['items'])
    estimated_tracks_per_day = 20  # Assumption: average listener plays ~20 tracks per day
    days_in_year = 365
    estimated_minutes_listened = (avg_track_duration_ms * estimated_tracks_per_day * days_in_year) / (1000 * 60)
    
    # Extract record labels (requires additional API calls)
    record_labels = {}
    for artist in top_artists_long['items'][:10]:  # Limit to top 10 to avoid too many requests
        artist_albums = sp.artist_albums(artist['id'], limit=1)
        if artist_albums['items']:
            label = artist_albums['items'][0].get('label', 'Unknown')
            if label in record_labels:
                record_labels[label] += 1
            else:
                record_labels[label] = 1
    
    top_labels = [{"label": label, "count": count} for label, count in sorted(record_labels.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    # Analyze time-based listening patterns
    day_night_tracks = {"day": [], "night": []}
    weekday_tracks = {day: [] for day in calendar.day_name}
    monthly_tracks = {month: [] for month in calendar.month_name[1:]}
    
    # Process recently played tracks for time patterns
    for item in recently_played['items']:
        played_at = datetime.datetime.strptime(item['played_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        track = item['track']
        
        # Day vs Night
        hour = played_at.hour
        if 6 <= hour < 18:  # Day: 6 AM to 6 PM
            day_night_tracks["day"].append(track)
        else:  # Night: 6 PM to 6 AM
            day_night_tracks["night"].append(track)
        
        # Weekday
        weekday = calendar.day_name[played_at.weekday()]
        weekday_tracks[weekday].append(track)
        
        # Month
        month = calendar.month_name[played_at.month]
        monthly_tracks[month].append(track)
    
    # Count most common tracks for each time period
    day_tracks = [track['name'] for track in day_night_tracks["day"]]
    night_tracks = [track['name'] for track in day_night_tracks["night"]]
    
    day_top_tracks = Counter(day_tracks).most_common(5)
    night_top_tracks = Counter(night_tracks).most_common(5)
    
    # Extract top 5 tracks for each weekday
    weekday_top_tracks = {}
    for day, tracks in weekday_tracks.items():
        track_names = [track['name'] for track in tracks]
        weekday_top_tracks[day] = Counter(track_names).most_common(5)
    
    # Extract top 5 tracks for each month
    monthly_top_tracks = {}
    for month, tracks in monthly_tracks.items():
        track_names = [track['name'] for track in tracks]
        monthly_top_tracks[month] = Counter(track_names).most_common(5)
    
    # Find "guilty pleasure" (track that's very different from usual taste)
    # Simplified approach: find tracks with genres least common in user's top genres
    guilty_pleasure = None
    if top_tracks_medium['items']:
        # Get a random track from medium-term that's not in short-term top 10
        short_term_ids = [track['id'] for track in top_tracks_short['items'][:10]]
        potential_guilty_pleasures = [track for track in top_tracks_medium['items'] if track['id'] not in short_term_ids]
        
        if potential_guilty_pleasures:
            guilty_pleasure = {
                "name": potential_guilty_pleasures[0]['name'],
                "artist": potential_guilty_pleasures[0]['artists'][0]['name'],
                "image": potential_guilty_pleasures[0]['album']['images'][0]['url'] if potential_guilty_pleasures[0]['album']['images'] else None
            }
    
    # Prepare first played track (approximation using oldest saved track)
    first_played = None
    if saved_tracks:
        # Sort by added date
        saved_tracks.sort(key=lambda x: x['added_at'])
        oldest_track = saved_tracks[0]['track']
        first_played = {
            "name": oldest_track['name'],
            "artist": oldest_track['artists'][0]['name'],
            "image": oldest_track['album']['images'][0]['url'] if oldest_track['album']['images'] else None,
            "date": saved_tracks[0]['added_at']
        }
    
    # Prepare most played track
    most_played = None
    if top_tracks_long['items']:
        track = top_tracks_long['items'][0]
        most_played = {
            "name": track['name'],
            "artist": track['artists'][0]['name'],
            "image": track['album']['images'][0]['url'] if track['album']['images'] else None
        }
    
    # Analyze seasonal listening
    # Simplified approach using medium-term listening history
    seasonal_breakdown = {
        "winter": [],
        "spring": [],
        "summer": [],
        "fall": []
    }
    
    # For a mock demo, just divide top tracks evenly among seasons
    tracks_per_season = len(top_tracks_medium['items']) // 4
    seasonal_breakdown["winter"] = top_tracks_medium['items'][:tracks_per_season]
    seasonal_breakdown["spring"] = top_tracks_medium['items'][tracks_per_season:2*tracks_per_season]
    seasonal_breakdown["summer"] = top_tracks_medium['items'][2*tracks_per_season:3*tracks_per_season]
    seasonal_breakdown["fall"] = top_tracks_medium['items'][3*tracks_per_season:]
    
    # Simplified for demo: convert seasonal breakdowns to just track names and artists
    seasonal_tracks = {}
    for season, tracks in seasonal_breakdown.items():
        seasonal_tracks[season] = [
            {"name": track['name'], "artist": track['artists'][0]['name']} 
            for track in tracks
        ]
    
    # Format top artists
    formatted_top_artists = [
        {
            "name": artist['name'],
            "image": artist['images'][0]['url'] if artist['images'] else None,
            "genres": artist['genres'],
            "popularity": artist['popularity']
        }
        for artist in top_artists_long['items'][:10]
    ]
    
    # Format top tracks
    formatted_top_tracks = [
        {
            "name": track['name'],
            "artist": track['artists'][0]['name'],
            "image": track['album']['images'][0]['url'] if track['album']['images'] else None,
            "preview_url": track['preview_url']
        }
        for track in top_tracks_long['items'][:10]
    ]
    
    # Find top collaborations
    collaborations = []
    for track in top_tracks_long['items']:
        if len(track['artists']) > 1:
            artists = [artist['name'] for artist in track['artists']]
            collaborations.append({
                "track": track['name'],
                "artists": artists,
                "image": track['album']['images'][0]['url'] if track['album']['images'] else None
            })
    
    # Sort collaborations by track popularity
    top_collaborations = sorted(collaborations, key=lambda x: top_tracks_long['items'].index(next(
        track for track in top_tracks_long['items'] if track['name'] == x['track']
    )))[:5]
    
    # Find "most surprising" artist/song (artist with least plays in top 50)
    # Simplified approach: use the least popular artist from top artists
    most_surprising = None
    if top_artists_long['items']:
        least_popular = min(top_artists_long['items'], key=lambda x: x['popularity'])
        most_surprising = {
            "name": least_popular['name'],
            "image": least_popular['images'][0]['url'] if least_popular['images'] else None
        }
    
    # Calculate listener percentile (mock data for demo)
    # In real app, this would need Spotify-provided data
    import random
    listener_percentile = random.randint(1, 20)
    
    # Future predictions based on recent listening
    # Simplified approach: recommend similar artists to top artists
    future_predictions = []
    if top_artists_short['items']:
        top_artist_id = top_artists_short['items'][0]['id']
        future_predictions = []
        if top_artists_short['items']:
            top_artist_id = top_artists_short['items'][0]['id']
            try:
                related_artists = sp.artist_related_artists(top_artist_id)
                future_predictions = [
                    {
                        "name": artist['name'],
                        "image": artist['images'][0]['url'] if artist['images'] else None,
                        "genres": artist['genres']
                    }
                    for artist in related_artists['artists'][:5]
                ]
            except spotipy.exceptions.SpotifyException as e:
                print(f"Error fetching related artists: {e}")
                future_predictions = []  # Set to empty list if error occurs

    
    # Listening streaks (mock data for demo)
    # In a real app, this would require more historical data
    listening_streaks = {
        "artist": {
            "name": formatted_top_artists[0]['name'] if formatted_top_artists else "Unknown",
            "streak": random.randint(3, 14)
        },
        "track": {
            "name": formatted_top_tracks[0]['name'] if formatted_top_tracks else "Unknown",
            "artist": formatted_top_tracks[0]['artist'] if formatted_top_tracks else "Unknown",
            "streak": random.randint(2, 7)
        }
    }
    
    # Mock "most played in a single day" (would require daily listening history)
    most_played_day = None
    if formatted_top_tracks:
        track = formatted_top_tracks[0]
        most_played_day = {
            "name": track['name'],
            "artist": track['artist'],
            "date": (datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 180))).strftime("%B %d, %Y"),
            "plays": random.randint(5, 20)
        }
    
    # Compile all data
    wrapped_data = {
        "top_artists": formatted_top_artists,
        "top_songs": formatted_top_tracks,
        "top_genres": top_genres,
        "minutes_listened": int(estimated_minutes_listened),
        "first_played": first_played,
        "most_played": most_played,
        "trends": {
            "short_term": [artist['name'] for artist in top_artists_short['items'][:5]],
            "medium_term": [artist['name'] for artist in top_artists_medium['items'][:5]],
            "long_term": [artist['name'] for artist in top_artists_long['items'][:5]]
        },
        "day_night_trends": {
            "day": [{"name": name, "count": count} for name, count in day_top_tracks],
            "night": [{"name": name, "count": count} for name, count in night_top_tracks]
        },
        "weekday_tracks": weekday_top_tracks,
        "monthly_tracks": monthly_top_tracks,
        "top_collaborations": top_collaborations,
        "most_surprising": most_surprising,
        "listener_percentile": listener_percentile,
        "guilty_pleasure": guilty_pleasure,
        "seasonal_breakdown": seasonal_tracks,
        "most_played_day": most_played_day,
        "listening_streaks": listening_streaks,
        "favorite_labels": top_labels,
        "future_predictions": future_predictions
    }
    
    return jsonify(wrapped_data)

if __name__ == '__main__':
    app.run(debug=True)