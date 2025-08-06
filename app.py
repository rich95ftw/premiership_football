import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
import pandas as pd
import sqlite3

# --- 1. Data Setup ---
# Load match data from the CSV file
file_path = r"C:\Users\RichardWood\Documents\premiership_football\data\epl-2025-GMTStandardTime.csv"
try:
    df_matches = pd.read_csv(file_path)
    # Convert the combined 'Date' column to datetime objects for easier handling
    df_matches['Date'] = pd.to_datetime(df_matches['Date'], format='%d/%m/%Y %H:%M')
except FileNotFoundError:
    print("Error: The CSV file was not found at the specified path.")
    exit()

# Get a list of all teams for the dropdown menus
teams = sorted(df_matches['Home Team'].unique())

# Initialize the SQLite database and table for commentary
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

# --- 2. Dashboard Layout ---
app = dash.Dash(__name__)

app.layout = html.Div(children=[
    # Top Bar: Team Selection
    html.Div(children=[
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

    html.Div(style={'display': 'flex', 'padding': '20px'}, children=[
        # Left Panel: Game Info
        html.Div(children=[
            html.H3('Game Info'),
            html.Div(id='game-info-output')
        ], style={'flex': 1, 'paddingRight': '20px', 'borderRight': '1px solid #ddd'}),

        # Right Panel: User Commentary
        html.Div(children=[
            html.H3('User Commentary'),
            dcc.Textarea(
                id='commentary-textarea',
                style={'width': '100%', 'height': 200, 'marginBottom': '10px'}
            ),
            html.Button('Save Commentary', id='save-button', n_clicks=0),
            html.Div(id='save-status-output', style={'marginTop': '10px'})
        ], style={'flex': 1, 'paddingLeft': '20px'})
    ])
])

# --- 3. Callbacks ---
# Callback to update game info and load commentary
@app.callback(
    [Output('game-info-output', 'children'),
     Output('commentary-textarea', 'value'),
     Output('validation-message', 'children')],
    [Input('home-team-dropdown', 'value'),
     Input('away-team-dropdown', 'value')]
)
def update_dashboard(home_team, away_team):
    # Check for team selection
    if not home_team or not away_team:
        return (html.P("Please select both a home and an away team."), "", "")

    # Validation: Home and away teams must be different
    if home_team == away_team:
        return (html.P("Please select two different teams."), "", "Home and away teams cannot be the same!")

    # Find the selected match info
    match = df_matches[
        (df_matches['Home Team'] == home_team) & (df_matches['Away Team'] == away_team)
    ].iloc[0]

    # Find next/previous games for home and away teams
    match_index = match.name
    home_next_game = df_matches[(df_matches['Home Team'] == home_team) | (df_matches['Away Team'] == home_team)].loc[df_matches.index > match_index].head(1)
    home_prev_game = df_matches[(df_matches['Home Team'] == home_team) | (df_matches['Away Team'] == home_team)].loc[df_matches.index < match_index].tail(1)
    away_next_game = df_matches[(df_matches['Home Team'] == away_team) | (df_matches['Away Team'] == away_team)].loc[df_matches.index > match_index].head(1)
    away_prev_game = df_matches[(df_matches['Home Team'] == away_team) | (df_matches['Away Team'] == away_team)].loc[df_matches.index < match_index].tail(1)

    # Format the output for the 'Game Info' panel
    game_info = html.Div([
        html.P(f"Match Date: {match['Date'].strftime('%d/%m/%Y')}"),
        html.P(f"Match Time: {match['Date'].strftime('%H:%M:%S')}"),
        html.P(f"Home Team: {match['Home Team']}"),
        html.P(f"Away Team: {match['Away Team']}"),
        html.Hr(),
        html.H5(f"Previous game for {home_team}:"),
        html.P(f"vs. {home_prev_game['Away Team'].iloc[0]} on {home_prev_game['Date'].iloc[0].strftime('%d/%m/%Y')}" if not home_prev_game.empty else "No previous game found"),
        html.H5(f"Next game for {home_team}:"),
        html.P(f"vs. {home_next_game['Away Team'].iloc[0]} on {home_next_game['Date'].iloc[0].strftime('%d/%m/%Y')}" if not home_next_game.empty else "No next game found"),
        html.Hr(),
        html.H5(f"Previous game for {away_team}:"),
        html.P(f"vs. {away_prev_game['Home Team'].iloc[0]} on {away_prev_game['Date'].iloc[0].strftime('%d/%m/%Y')}" if not away_prev_game.empty else "No previous game found"),
        html.H5(f"Next game for {away_team}:"),
        html.P(f"vs. {away_next_game['Home Team'].iloc[0]} on {away_next_game['Date'].iloc[0].strftime('%d/%m/%Y')}" if not away_next_game.empty else "No next game found")
    ])

    # Load existing commentary from the database
    conn = sqlite3.connect('commentary.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT commentary FROM game_commentary WHERE home_team = ? AND away_team = ?",
        (home_team, away_team)
    )
    commentary_data = cursor.fetchone()
    conn.close()

    commentary_text = commentary_data[0] if commentary_data else ""

    return game_info, commentary_text, ""

# Callback to save commentary
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

if __name__ == '__main__':
    app.run(debug=True)