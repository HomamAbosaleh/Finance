import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    prices = {}
    TOTAL = 0
    cash = (db.execute("SELECT * FROM users WHERE user_id = ?", session["user_id"]))[0]['cash']
    rows = db.execute("SELECT * FROM stocks WHERE user_id = ?", session["user_id"])
    for row in rows:
        company = lookup(row['symbol'])
        prices[row['symbol']] = [company['price'], company['name']]
        TOTAL += prices[row['symbol']][0] * row['share']
    return render_template("index.html", cash=cash, rows=rows, prices=prices, TOTAL=TOTAL, status= session['status'])

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    HISTORY = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
    print(HISTORY)
    return render_template("history.html", histories=HISTORY)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["user_id"]
        session['status'] = "loggedIn"
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":

        return render_template("register.html")

    else:
        # checking for missing inputs
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide password again", 400)

        # checking for invalid inputs
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password fields do not match", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) == 1:
            return apology("user already exists", 400)

        # storing the inputs
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")));

        session["user_id"] = (db.execute("SELECT user_id FROM users WHERE username = ?", request.form.get("username")))[0]["user_id"]
        session['status'] = "Registered"
        return redirect("/")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":

        return render_template("quote.html")

    else:
        if lookup(request.form.get("symbol")) != None:
            return render_template("quote.html", stock = lookup(request.form.get("symbol")))
        else:
            return apology("Invalid Symbol", 400)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        # returning the stocks information
        rows = db.execute("SELECT symbol FROM stocks WHERE user_id = ?", session['user_id'])
        return render_template("sell.html", rows=rows)
    else:
        # checking for inputs errors
        if request.form.get("Selection-form") is None:
            return apology("Invalid Symbol", 403)
        elif not request.form.get("share"):
            return apology("Invalid Shares", 403)

        # checking for vaild number of shares
        existingShares = float(db.execute("SELECT share FROM stocks WHERE (user_id = ? AND symbol = ?)", session["user_id"], request.form.get("Selection-form"))[0]['share'])
        if float(request.form.get("share")) > existingShares:
            return apology("Check number of shares", 403)

        # changing the number of shares in the datebase
        newStocks = existingShares - float(request.form.get("share"))
        if newStocks == 0:
            db.execute("DELETE FROM stocks WHERE (user_id = ? AND symbol = ?)", session["user_id"], request.form.get("Selection-form"))
        else:
            db.execute("UPDATE stocks SET share = ? WHERE (user_id = ? AND symbol = ?)", newStocks, session["user_id"], request.form.get("Selection-form"))

        # registring the sold shares
        db.execute("INSERT INTO history (user_id, symbol, share, price,sold, date) VALUES (?, ?, ?, ?, 1, ?)", session["user_id"], request.form.get("Selection-form"), request.form.get("share"), lookup(request.form.get("Selection-form"))['price'], "{:%Y-%m-%d %H:%M:%2S}".format(datetime.now()))

        # update the user's cash
        userCash = db.execute("SELECT cash FROM users WHERE user_id = ?", session["user_id"])[0]['cash']
        price = lookup(request.form.get("Selection-form"))['price'] * float(request.form.get("share"))
        db.execute("UPDATE users SET cash = ? WHERE user_id = ?", (userCash + price), session["user_id"])

        session['status'] = "Sold"
    return redirect("/")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        stockInformation = lookup(request.form.get("symbol"))
        if (request.form.get("shares").isnumeric() == False) or ("." in request.form.get("shares")) or ("-" in request.form.get("shares")):
            return apology("Shares must be integer and not negative", 400)
        if stockInformation != None:
            price = float(stockInformation['price']) * float(request.form.get("shares"))
            userCash = db.execute("SELECT cash FROM users WHERE user_id = ?", session["user_id"])[0]['cash']
            if userCash >= price:
                rows = db.execute("SELECT * FROM stocks WHERE symbol = ?", request.form.get("symbol"))
                if len(rows) == 0:
                    db.execute("INSERT INTO stocks (user_id, symbol, share) VALUES (?, ?, ?)", session["user_id"], request.form.get("symbol"), float(request.form.get("shares")))
                    db.execute("INSERT INTO history (user_id, symbol, share, price, sold, date) VALUES (?, ?, ?, ?, 0, ?)", session["user_id"], request.form.get("symbol"), float(request.form.get("shares")), float(stockInformation['price']), "{:%Y-%m-%d %H:%M:%2S}".format(datetime.now()))
                else:
                    existingShares = float(db.execute("SELECT share FROM stocks WHERE (user_id = ? AND symbol = ?)", session["user_id"], request.form.get("symbol"))[0]['share'])
                    db.execute("UPDATE stocks SET share = ? WHERE (user_id = ? AND symbol = ?)", existingShares + float(request.form.get("shares")), session["user_id"], request.form.get("symbol"))
                    db.execute("INSERT INTO history (user_id, symbol, share, price, sold, date) VALUES (?, ?, ?, ?, 0, ?)", session["user_id"], request.form.get("symbol"), float(request.form.get("shares")), float(stockInformation['price']), "{:%Y-%m-%d %H:%M:%2S}".format(datetime.now()))
                db.execute("UPDATE users SET cash = ? WHERE user_id = ?", (userCash - price), session["user_id"])
                session['status'] = "Bought"
            else:
                apology("Not Enough Cash", 400)
            return redirect("/")
        else:
            return apology("Invalid Symbol", 400)

@app.route("/validate")
def validate():
    user = request.args.get("q")
    row = db.execute("SELECT username FROM finance WHERE username = ?", user)
    return jsonify(row)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)