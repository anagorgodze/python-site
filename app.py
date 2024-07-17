import os
from flask import Flask, render_template, redirect, request, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = "your_secret_key"
db = SQLAlchemy(app)

@app.before_request
def load_user():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            session['is_admin'] = user.is_admin
        else:
            session.pop('is_admin', None)
    else:
        session.pop('is_admin', None)

cart_items = db.Table('cart_items',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True)
)

favorite_items = db.Table('favorite_items',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    password = db.Column(db.String(30))
    is_admin = db.Column(db.Boolean, default=False)
    cart_items = db.relationship('Product', secondary=cart_items, backref=db.backref('users_in_cart', lazy='dynamic'))
    favorite_items = db.relationship('Product', secondary=favorite_items, backref=db.backref('users_in_favorites', lazy='dynamic'))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Integer)
    name = db.Column(db.String(30))
    image = db.Column(db.String(500))

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

def add_to_session(product_id):
    products = session.get('products', [])
    products.append(product_id)
    session['products'] = products
    session.modified = True

def get_cart_products(user_id):
    user = User.query.get(user_id)
    return user.cart_items

def get_favorite_products(user_id):
    user = User.query.get(user_id)
    return user.favorite_items

# Decorator for checking admin role
def admin_required(func):
    def wrapper(*args, **kwargs):
        if 'user' in session and session['user'].get('is_admin'):
            return func(*args, **kwargs)
        else:
            return redirect(url_for('login'))
    wrapper.__name__ = func.__name__
    return wrapper

def check_in_session(id, key='favorites'):
    if key not in session:
        return False
    return id in session.get(key)
    
def check_in_cart(id):
    if 'cart' not in session:
        return False
    return id in session.get('cart')

def check_in_favorites(id):
    if 'favorites' not in session:
        return False
    return id in session.get('favorites')

@app.route("/")
def main():
    return render_template("main.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        print(role)
        if role == "admin":
            user = User(username=username, password=password, is_admin=True)
        else:
            user = User(username=username, password=password, is_admin=False)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))

@app.route("/login")
def login():
    return render_template("login.html")

@app.route('/about')
def about():
    return render_template('about.html')

@app.route("/account")
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('login'))

    cart_products = get_cart_products(user_id)
    favorite_products = get_favorite_products(user_id)

    # Fetch all contact messages
    contacts = Contact.query.all()

    return render_template('account.html', contacts=contacts, cart_products=cart_products, favorite_products=favorite_products)

@app.route('/delete_contact/<int:id>', methods=['POST'])
def delete_contact(id):
    contact = Contact.query.get(id)
    if contact:
        db.session.delete(contact)
        db.session.commit()
        flash('Message deleted successfully!')
    return redirect(url_for('account'))


@app.route('/products')
def products():
    products = Product.query.all()
    print(session)
    search_term = request.args.get('search')
    if search_term:
        products = Product.query.filter(Product.name.contains(search_term)).all()
    else:
        products = Product.query.all()
    return render_template('products.html', products=products, check_in_session=check_in_session, check_in_cart=check_in_cart, check_in_favorites=check_in_favorites)

@app.route("/login", methods=["POST"])
def login_post():
    username = request.form["username"]
    password = request.form["password"]
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        session['user_id'] = user.id
        session['user'] = {'id': user.id, "is_admin": user.is_admin }
        session.modified = True
        return redirect(url_for("main"))
    return redirect(url_for("login"))

@app.route('/contacts', methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]
        
        if not name or not email or not message:
            flash('All fields are required!')
            return redirect(url_for('contact'))

        new_contact = Contact(name=name, email=email, message=message)
        db.session.add(new_contact)
        db.session.commit()
        flash('Message sent successfully!')
        return redirect(url_for('contact'))
    return render_template("contact.html")

@app.route("/products", methods=["POST"])
@admin_required
def add_products():
    name = request.form["name"]
    price = request.form["price"]
    image = request.files["image"]
    if image.filename == "":
        return "No selected file"
    filename = "".join(image.filename.split())
    image.save(os.path.join("static", filename))
    full_path = os.path.join("static", filename)
    product = Product(name=name, price=price, image=full_path)
    db.session.add(product)
    db.session.commit()
    return redirect(url_for("products"))

@app.route("/wishlist")
def wishlist():
    if "favorites" not in session or not session["favorites"]:
        products = []
    else:
        favorite_ids = session["favorites"]
        products = Product.query.filter(Product.id.in_(favorite_ids)).all()
    return render_template("wishlist.html", products=products)

@app.route("/favorites")
def favorites():
    if 'products' not in session:
        return 'No products found'

    ids = session.get("products")
    products = Product.query.filter(Product.id.in_(ids)).all()

    return render_template("favourites.html", queryset=products)

@app.route("/add_to_favorite/<int:id>")
def add_to_favorite(id):
    if "favorites" not in session:
        session["favorites"] = []
    if not check_in_session(id, key='favorites'):
        session["favorites"].append(id)
        session.modified = True
    return redirect(url_for("products"))

@app.route("/remove_from_favorites/<int:id>")
def remove_from_favorites(id):
    if check_in_session(id, key='favorites'):
        session["favorites"].remove(id)
        session.modified = True
    return redirect(url_for("products"))

@app.route("/add_to_cart/<int:id>")
def add_to_cart(id):
    if "cart" not in session:
        session["cart"] = []
    if not check_in_session(id, key='cart'):
        session["cart"].append(id)
        session.modified = True
    return redirect(url_for("products"))

@app.route("/remove_from_cart/<int:id>")
def remove_from_cart(id):
    if check_in_session(id, key='cart'):
        session["cart"].remove(id)
        session.modified = True
    return redirect(url_for("products"))

# @app.route("/logout", methods=["POST"])
# def logout_post():
#     if 'user' in session:
#         session.pop('user')
#         session.modified = True
#         return redirect(url_for("main"))
#     return redirect(url_for("logout"))

@app.route("/logout", methods=["POST", "GET"])
def logout_post():
    
    session.clear()  # Clear the entire session
    return redirect(url_for("main"))

@app.route('/logout')
def logout():
    return render_template('logout.html')




@app.route("/cart")
def cart():
    if "cart" not in session or not session["cart"]:
        products = []
        total_amount = 0
    else:
        cart_ids = session["cart"]
        products = Product.query.filter(Product.id.in_(cart_ids)).all()
        total_amount = sum(product.price for product in products)
        print(products)
    return render_template("cart.html", products=products, total_amount=total_amount)


if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    with app.app_context():
        db.create_all()
    app.run(debug=True)
