import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import pandas as pd
import sqlite3

# --- 1. Data Setup ---
file_path = r"C:\Users\RichardWood\Documents\premiership_football\data\epl-2025-GMTStandardTime.csv"

try:
    df_matches = pd.read_csv(file_path)
    df_matches['Date'] = pd.to_datetime(df_matches['Date'], format='%d/%m/%Y %H:%M')
except FileNotFoundError:
    print("Error: The CSV file was not found at the specified path.")
    exit()

teams = sorted(df_matches['Home Team'].unique())

def init_db():
    conn = sqlite3.connect('commentary.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_commentary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team TEXT,
            away_team TEXT,
            commentary TEXT,
            UNIQUE(home_team, away_team)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 2. App Setup ---
app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div([
        html.H1('Premier League Dashboard', style={'textAlign': 'center'}),

        dcc.Dropdown(
            id='home-team-dropdown',
            options=[{'label': i, 'value': i} for i in teams],
            placeholder="Select a Home Team",
            style={'width': '48%', 'display': 'inline-block', 'marginRight': '4%'}
        ),

        dcc.Dropdown(
            id='away-team-dropdown',
            options=[{'label': i, 'value': i} for i in teams],
            placeholder="Select an Away Team",
            style={'width': '48%', 'display': 'inline-block'}
        ),

        html.P(id='validation-message', style={'color': 'red'})
    ], style={'padding': '20px', 'borderBottom': '1px solid #ddd'}),

    html.Button("See Calendar", id="calendar-button", n_clicks=0),
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='calendar-nav', data=False),

    html.Div(style={'display': 'flex', 'padding': '20px'}, children=[
        html.Div([
            html.H3('Game Info'),
            html.Div(id='game-info-output')
        ], style={'flex': 1, 'paddingRight': '20px', 'borderRight': '1px solid #ddd'}),

        html.Div([
            html.H3('User Commentary'),
            dcc.Textarea(id='commentary-textarea', style={'width': '100%', 'height': 200}),
            html.Button('Save Commentary', id='save-button', n_clicks=0),
            html.Div(id='save-status-output', style={'marginTop': '10px'})
        ], style={'flex': 1, 'paddingLeft': '20px'})
    ])
])

# --- 3. Helper Functions ---
def get_match(home_team, away_team):
    match = df_matches[
        (df_matches['Home Team'] == home_team) &
        (df_matches['Away Team'] == away_team)
    ]
    return match.iloc[0] if not match.empty else None

def get_team_matches(team):
    return df_matches[
        (df_matches['Home Team'] == team) |
        (df_matches['Away Team'] == team)
    ].sort_values('Date')

def get_prev_next_game(team, match_date):
    matches = get_team_matches(team)
    prev_game = matches[matches['Date'] < match_date].tail(1)
    next_game = matches[matches['Date'] > match_date].head(1)
    return prev_game, next_game

def format_game_summary(game, perspective_team, is_next_game, reference_date):
    if game.empty:
        return "No game found"

    row = game.iloc[0]
    is_home = row['Home Team'] == perspective_team
    opponent = row['Away Team'] if is_home else row['Home Team']
    location = "Home game" if is_home else "Away game"
    match_date = row['Date']
    match_day = match_date.strftime('%A')

    # Calculate days difference relative to reference_date
    delta_days = (match_date.date() - reference_date.date()).days

    if is_next_game:
        prefix = f"In {delta_days} days:"
    else:
        prefix = f"{abs(delta_days)} days ago:"

    date_str = match_date.strftime('%d/%m/%Y')
    return f"{prefix} {location} vs. {opponent} on {match_day} {date_str}"

def load_commentary(home_team, away_team):
    conn = sqlite3.connect('commentary.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT commentary FROM game_commentary WHERE home_team = ? AND away_team = ?",
        (home_team, away_team)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else ""

# --- 4. Callbacks ---
@app.callback(
    Output('url', 'pathname'),
    Input('calendar-button', 'n_clicks'),
    prevent_initial_call=True
)
def go_to_calendar(n_clicks):
    return '/calendar'

@app.callback(
    [Output('game-info-output', 'children'),
     Output('commentary-textarea', 'value'),
     Output('validation-message', 'children')],
    [Input('home-team-dropdown', 'value'),
     Input('away-team-dropdown', 'value')]
)
def update_dashboard(home_team, away_team):
    if not home_team or not away_team:
        return html.P("Please select both a home and an away team."), "", ""

    if home_team == away_team:
        return html.P("Please select two different teams."), "", "Home and away teams cannot be the same!"

    match = get_match(home_team, away_team)
    if match is None:
        return html.P("Match not found."), "", ""

    match_date = match['Date']
    commentary_text = load_commentary(home_team, away_team)

    home_prev, home_next = get_prev_next_game(home_team, match_date)
    away_prev, away_next = get_prev_next_game(away_team, match_date)

    game_info = html.Div([
        html.P(f"Match Date: {match_date.strftime('%d/%m/%Y')}"),
        html.P(f"Match Day: {match_date.strftime('%A')}"),
        html.P(f"Match Time: {match_date.strftime('%H:%M:%S')}"),
        html.P(f"Home Team: {home_team}"),
        html.P(f"Away Team: {away_team}"),
        html.P(f"Location: {match['Location']}"),
        html.Hr(),

        html.H5(f"Previous game for {home_team}:"),
        html.P(format_game_summary(home_prev, home_team, is_next_game=False, reference_date=match_date)),

        html.H5(f"Next game for {home_team}:"),
        html.P(format_game_summary(home_next, home_team, is_next_game=True, reference_date=match_date)),

        html.Hr(),

        html.H5(f"Previous game for {away_team}:"),
        html.P(format_game_summary(away_prev, away_team, is_next_game=False, reference_date=match_date)),

        html.H5(f"Next game for {away_team}:"),
        html.P(format_game_summary(away_next, away_team, is_next_game=True, reference_date=match_date)),
    ])

    return game_info, commentary_text, ""

@app.callback(
    Output('save-status-output', 'children'),
    [Input('save-button', 'n_clicks')],
    [State('home-team-dropdown', 'value'),
     State('away-team-dropdown', 'value'),
     State('commentary-textarea', 'value')]
)
def save_commentary(n_clicks, home_team, away_team, commentary):
    if n_clicks > 0 and home_team and away_team and home_team != away_team:
        try:
            conn = sqlite3.connect('commentary.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO game_commentary (home_team, away_team, commentary) VALUES (?, ?, ?)",
                (home_team, away_team, commentary)
            )
            conn.commit()
            conn.close()
            return html.Div("Commentary saved successfully!", style={'color': 'green'})
        except Exception as e:
            return html.Div(f"Error saving commentary: {e}", style={'color': 'red'})
    return ""

# --- 5. Run App ---
if __name__ == '__main__':
    app.run(debug=True)