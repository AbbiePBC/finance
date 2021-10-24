import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

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
    user_id = session["user_id"]
    rows = db.execute("SELECT * FROM purchases WHERE user_id == ?", user_id)
    stock_datas = []
    total = 0
    print("length of rows =",  len(rows))
    if len(rows) == 0:
        cash = 10000
        total = cash
        stock_datas.append({
            "stock": ' ',
            "price": ' ',
            "shares": ' ',
        })
    else:
        for i in range(len(rows)):
            symbol = rows[i]["symbol"]
    
            if not symbol:
                return apology("symbol not recognised")
            stock_info = lookup(symbol)
            price = int(stock_info['price'])
            total += (rows[i]["shares"] * price)
            subtotal = price * rows[i]["shares"]
            stock_datas.append({
                "stock": rows[i]["symbol"],
                "price": usd(stock_info["price"]),
                "shares": rows[i]["shares"],
                "subtotal": usd(subtotal)
            })
        cash = rows[0]["cash"]
        total += cash
    return render_template("index.html", stock_datas=stock_datas, cash=(usd(cash)), total=(usd(total)))
   # will need to delete shares if sold?


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        retvals = lookup(symbol)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("invalid number of shares")
    
        if retvals is None:
            return apology("symbol not in database")

        elif not shares or not symbol:
            return apology("all fields required")

        elif (int(shares)) <= 0:
            return apology("invalid number of shares")

        else:
            cost = shares * int(retvals['price'])
            user_id = session["user_id"]
            rows = db.execute("SELECT cash FROM users WHERE id == ?", user_id)
            current_cash = rows[0]["cash"]
        if cost > current_cash:
            return apology("insufficient funds")
        else:
            current_cash = current_cash - cost
            db.execute("INSERT INTO purchases (transaction, user_id, symbol, shares, price, cash) VALUES (?, ?, ?, ?, ?, ?)",
                       "BOUGHT", user_id, symbol, shares, retvals['price'], current_cash)

            return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock_info = lookup(symbol)

        if not symbol or stock_info == None:
            return apology("please enter a valid symbol")
        else:
            return render_template("quoted.html", stock_data={
                'symbol': stock_info['symbol'],
                'price': usd(stock_info['price'])
            })

    else:
        return render_template("quote.html")
    return apology("quote failed")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE username == ?", username)
        print("rows = ", len(rows))

        if not username or not password or not confirmation:
            return apology("all fields required")

        elif password != confirmation:
            return apology("passwords did not match")

        elif len(rows) != 0:
            return apology("username not unique")

        hash_password = generate_password_hash(password)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    SYMBOLS = []
    user_id = session["user_id"]
    persons_stocks = db.execute("SELECT * FROM purchases WHERE user_id == ?", user_id)
    shares = int(persons_stocks[0]["shares"])
    for row in persons_stocks:
        SYMBOLS.append(row["symbol"])

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("enter a symbol")

        else:
            # sell (if have enough) and then

            if request.form.get("symbol") not in SYMBOLS:
                return apology("stock unavailable")

            if shares > int(request.form.get("shares")):
                return apology("insufficent shares available")
            else:
                shares += int(request.form.get("shares"))
                info = lookup("symbol")
                money = shares * retvals['price']
                
                db.execute("INSERT INTO purchases (transaction, user_id, symbol, shares, price, cash) VALUES (?, ?, ?, ?, ?, ?)",
                       "sold", user_id, symbol,  shares, retvals['price'], persons_stocks[0]["cash"] - money)
                return render_template("/")
    else:
        return render_template("sell.html", symbols=SYMBOLS)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

