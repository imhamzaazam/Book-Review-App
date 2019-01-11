import os
import requests
from flask import Flask, session, render_template, request, redirect, jsonify, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from helpers import *

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """REGISTER USER"""
    if request.method == "POST": 
        
        if not request.form.get("username"):
            return render_template("register.html", message="Must provide username")
        elif not request.form.get("password"):
            return render_template("register.html", message="Must provide password")
        elif request.form.get("password") != request.form.get("passwordagain"):
            return render_template("register.html", message="Password doesn't match")

        user = db.execute("Select username from users where username = :username", {"username": request.form.get("username")}).fetchone() 

        if user is None:
            db.execute("Insert into users (username, password, name) values (:username, :password, :name)", {"username" : request.form.get("username"), "password" : request.form.get("password"), "name" : request.form.get("name")})
            db.commit()
            return render_template("register.html", message="You have successfully registered")
        else: 
            return render_template("register.html", message="Username is taken")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("login.html", message="Please Enter Username")
        elif not request.form.get("password"):
            return render_template("login.html", message="Please Enter Password")
        
        User = db.execute("select * from users where username =:username AND password = :password", {"username": request.form.get("username"), "password": request.form.get("password")}).fetchone()
        if User is None: 
            return render_template("login.html", message="Invalid username or password")
        
        session["uname"] = User.username
        session["user_id"] = User["id"]
   
        return render_template("index.html", message="SUCCESS")
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "POST": 
        book_query = request.form.get("search")
        book_query_like = '%' + book_query + '%' 

        books = db.execute("SELECT * FROM books WHERE isbn LIKE :book_query_like OR title LIKE :book_query_like OR author LIKE :book_query_like",
        {"book_query_like": book_query_like}).fetchall()

        return render_template("search.html", username=session["user_id"], no_books = (len(books) == 0), books=books)

    return render_template("search.html")

@app.route("/book/<int:book_id>", methods=["GET", "POST"])
@login_required
def book(book_id):
    
    book = db.execute("SELECT * FROM books WHERE id = :book_id", {"book_id": book_id}).fetchone()
    if book is None:
        return render_template("details.html", no_book=True)


    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book_id}).fetchall()
    #Call for GoodReads api
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
    params={"key": "4qQ33gRusyHcS7NP277GQ", "isbns": book.isbn})

    if res.status_code != 200:
        raise Exception("Error: API request unsuccessful.")

    data = res.json()
    rating_num = data["books"][0]["work_ratings_count"]
    api_avg_rate = data["books"][0]["average_rating"]
    if request.method == "POST":
        # take review inputs
        review_text = request.form.get("review_text")
        avg_rate = request.form.get("avg_rate")

        #user = db.execute("SELECT user_id FROM reviews where user_id = :user_id AND book_id = :book_id", {"id": session['user_id'], "book_id": book_id}).fetchone()
        user = db.execute("SELECT user_id FROM reviews WHERE user_id = :id AND book_id= :book_id",
        {"id": session['user_id'], "book_id": book_id}).fetchone()
        
        if user is None:
            db.execute("INSERT INTO REVIEWS (text, rating, book_id, user_id) values (:review_text, :avg_rate, :book_id  ,:user_id)", {"review_text": review_text, "avg_rate": avg_rate, "book_id": book_id, "user_id": session['user_id']})
            db.commit()
        else:
            return render_template("details.html", message="You have already submitted a review", book=book, reviews=reviews, rating_num=rating_num, api_avg_rate=api_avg_rate, username=session["uname"] )
        
        reviews = db.execute("SELECT * FROM REVIEWS where book_id = :book_id", {"book_id": book_id}).fetchall()
        
        return render_template("details.html", book=book, reviews=reviews, rating_num=rating_num, api_avg_rate=api_avg_rate, username=session["uname"] )
    return render_template("details.html", book=book, reviews=reviews, rating_num=rating_num, api_avg_rate=api_avg_rate, username=session["uname"])
@app.route("/api/<string:isbn>")
def api(isbn):
    book = db.execute("Select id, title, author, year, isbn from books where isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None: 
        return jsonify({"error": "Invalid book isbn"}), 404

    res = requests.get("https://www.goodreads.com/book/review_counts.json",
    params={"key": "4qQ33gRusyHcS7NP277GQ", "isbns": isbn})

    if res.status_code !=200:
        raise Exception("Error: API request unsuccessful")

    data = res.json()
    rating_num = data["books"][0]["work_ratings_count"]
    api_avg_rate = data["books"][0]["average_rating"]

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "review_count": rating_num,
        "average_score": float(api_avg_rate) 

    })
