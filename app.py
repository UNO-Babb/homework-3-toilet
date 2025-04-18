from flask import Flask, render_template, request, redirect, session
import random
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---- Database Setup ----
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            chips INTEGER,
            wins INTEGER,
            losses INTEGER,
            highest_chips INTEGER,
            games_played INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---- Utilities ----
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def new_deck():
    return [v + s for v in "23456789TJQKA" for s in "♠♥♦♣"]

def deal_card(deck):
    return deck.pop(random.randint(0, len(deck) - 1))

def hand_value(hand):
    value, aces = 0, 0
    for card in hand:
        rank = card[0]
        if rank in 'TJQK':
            value += 10
        elif rank == 'A':
            value += 11
            aces += 1
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

# ---- Routes ----
@app.route("/")
def index():
    if "username" not in session:
        return redirect("/signup")
    return render_template("index.html",
        player=session.get("player", []),
        dealer=session.get("dealer_shown", []),
        message=session.get("message", ""),
        game_over=session.get("game_over", False),
        bet=session.get("bet", 0),
        chips=session.get("chips", 0),
        wins=session.get("wins", 0),
        losses=session.get("losses", 0),
        highest=session.get("highest_chips", 0),
        deck=session.get("deck", [])
    )

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = hash_password(password)

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if c.fetchone():
            return "Username already exists."

        c.execute("INSERT INTO users (username, password, chips, wins, losses, highest_chips, games_played) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (username, hashed_password, 100, 0, 0, 0, 0))
        conn.commit()
        conn.close()
        return redirect("/login")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["username"] = user[1]
            session["chips"] = user[3]
            session["wins"] = user[4] or 0
            session["losses"] = user[5] or 0
            session["highest_chips"] = user[6]
            session["games_played"] = user[7]
            return redirect("/")
        return "Invalid login."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/bet", methods=["POST"])
def bet():
    bet = int(request.form["bet"])
    if bet > session["chips"] or bet <= 0:
        session["message"] = "Invalid bet amount."
        return redirect("/")

    deck = new_deck()
    player = [deal_card(deck), deal_card(deck)]
    dealer = [deal_card(deck), deal_card(deck)]

    session["deck"] = deck
    session["player"] = player
    session["dealer_full"] = dealer
    session["dealer_shown"] = [dealer[0]]
    session["bet"] = bet
    session["game_over"] = False
    session["message"] = ""

    if hand_value(player) == 21:
        session["message"] = "Blackjack! You win!"
        session["chips"] += int(1.5 * bet)
        update_stats(won=True)
        session["game_over"] = True

    return redirect("/")

@app.route("/hit")
def hit():
    if session.get("game_over", True) or "deck" not in session:
        return redirect("/")

    deck = session["deck"]
    player = session["player"]
    card = deal_card(deck)
    player.append(card)

    session["deck"] = deck
    session["player"] = player

    if hand_value(player) > 21:
        session["message"] = "You busted! Dealer wins."
        session["chips"] -= session["bet"]
        update_stats(won=False)
        session["game_over"] = True

    return redirect("/")

@app.route("/stand")
def stand():
    if session.get("game_over", True):
        return redirect("/")

    dealer = session["dealer_full"]
    deck = session["deck"]

    while hand_value(dealer) < 17:
        dealer.append(deal_card(deck))

    session["dealer_shown"] = dealer

    player_val = hand_value(session["player"])
    dealer_val = hand_value(dealer)
    bet = session["bet"]

    if dealer_val > 21 or player_val > dealer_val:
        session["message"] = f"You win! You gain {bet} chips."
        session["chips"] += bet
        update_stats(won=True)
    elif dealer_val > player_val:
        session["message"] = f"Dealer wins! You lose {bet} chips."
        session["chips"] -= bet
        update_stats(won=False)
    else:
        session["message"] = "It's a tie!"

    session["game_over"] = True
    return redirect("/")

@app.route("/reset")
def reset():
    keys_to_clear = ["player", "dealer_full", "dealer_shown", "deck", "bet", "message", "game_over"]
    for key in keys_to_clear:
        session.pop(key, None)
    return redirect("/")

def update_stats(won):
    username = session["username"]
    chips = session["chips"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    if won:
        session["wins"] += 1
        c.execute("UPDATE users SET wins = wins + 1 WHERE username = ?", (username,))
    else:
        session["losses"] += 1
        c.execute("UPDATE users SET losses = losses + 1 WHERE username = ?", (username,))

    session["games_played"] += 1
    c.execute("UPDATE users SET chips = ?, games_played = games_played + 1 WHERE username = ?", (chips, username))

    if chips > session["highest_chips"]:
        session["highest_chips"] = chips
        c.execute("UPDATE users SET highest_chips = ? WHERE username = ?", (chips, username))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    app.run(debug=True)
