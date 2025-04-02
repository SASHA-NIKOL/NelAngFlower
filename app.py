from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from wtforms import StringField, FloatField, SelectField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.secret_key = 'your_secret_key'
# Возвращаем SQLite вместо MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Модели базы данных
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)

    def __str__(self):
        return self.name


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    order_items = db.Column(db.String(200), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.String(200), nullable=False)
    comment = db.Column(db.String(500))


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    review = db.Column(db.String(500), nullable=False)
    date = db.Column(db.String(20), nullable=False)


# Context processor для категорий
@app.context_processor
def utility_processor():
    def get_categories():
        return Category.query.all()

    return dict(get_categories=get_categories)


# Кастомное представление для Product
class ProductView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

    form_columns = ['name', 'price', 'image', 'category_id']

    def scaffold_form(self):
        form_class = super(ProductView, self).scaffold_form()
        form_class.name = StringField('Название', validators=[DataRequired()])
        form_class.price = FloatField('Цена', validators=[DataRequired()])
        form_class.image = StringField('Изображение', validators=[DataRequired()])
        form_class.category_id = SelectField(
            'Категория',
            coerce=int,
            validators=[DataRequired()]
        )
        return form_class

    def create_form(self, obj=None):
        form = super(ProductView, self).create_form(obj)
        form.category_id.choices = [(c.id, c.name) for c in db.session.query(Category).order_by('name').all()]
        default_category = db.session.query(Category).first()
        if default_category:
            form.category_id.default = default_category.id
            form.process()
        return form

    def edit_form(self, obj=None):
        form = super(ProductView, self).edit_form(obj)
        form.category_id.choices = [(c.id, c.name) for c in db.session.query(Category).order_by('name').all()]
        return form

    def on_model_change(self, form, model, is_created):
        print(
            f"Creating product: name={form.name.data}, price={form.price.data}, image={form.image.data}, category_id={form.category_id.data}")
        model.name = form.name.data
        model.price = form.price.data
        model.image = form.image.data
        model.category_id = form.category_id.data

    column_list = ['id', 'name', 'price', 'image', 'category']
    column_labels = {'category': 'Категория'}


# Настройка Flask-Admin
admin = Admin(app, name='Букет мечты', template_mode='bootstrap4')
admin.add_view(ModelView(Category, db.session))
admin.add_view(ModelView(Order, db.session))
admin.add_view(ModelView(Review, db.session))
admin.add_view(ModelView(User, db.session))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Инициализация базы данных
def init_db():
    db.create_all()

    if not User.query.first():
        admin_user = User(username='admin', password='admin123')
        db.session.add(admin_user)

    if not Category.query.first():
        categories = [
            Category(name="Розы"),
            Category(name="Тюльпаны"),
            Category(name="Смешанные букеты")
        ]
        db.session.add_all(categories)
        db.session.commit()

    if not Product.query.first():
        products = [
            Product(name="Букет роз классический", price=1500.0, image="/static/images/rose_bouquet.jpg",
                    category_id=1),
            Product(name="Тюльпаны весенние", price=1000.0, image="/static/images/tulips.jpg", category_id=2),
            Product(name="Лилии и розы", price=2000.0, image="/static/images/lilies.jpg", category_id=3)
        ]
        db.session.add_all(products)

    if not Review.query.first():
        reviews = [
            Review(name="Анна", review="Отличный сервис, цветы свежие!", date="2025-03-01"),
            Review(name="Игорь", review="Доставка вовремя, рекомендую!", date="2025-03-02")
        ]
        db.session.add_all(reviews)

    db.session.commit()


@app.route('/')
def index():
    categories = Category.query.all()
    products = Product.query.all()
    cart_count = sum(session['cart'].values()) if 'cart' in session and isinstance(session['cart'], dict) else 0
    return render_template('index.html', categories=categories, products=products, cart_count=cart_count)


@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = {}
    elif isinstance(session['cart'], list):
        new_cart = {}
        for pid in session['cart']:
            new_cart[str(pid)] = new_cart.get(str(pid), 0) + 1
        session['cart'] = new_cart
    session['cart'][str(product_id)] = session['cart'].get(str(product_id), 0) + 1
    session.modified = True
    return redirect(url_for('index'))


@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'cart' in session:
        if isinstance(session['cart'], list):
            new_cart = {}
            for pid in session['cart']:
                new_cart[str(pid)] = new_cart.get(str(pid), 0) + 1
            session['cart'] = new_cart
        if str(product_id) in session['cart']:
            if session['cart'][str(product_id)] > 1:
                session['cart'][str(product_id)] -= 1
            else:
                del session['cart'][str(product_id)]
            session.modified = True
    return redirect(url_for('cart'))


@app.route('/cart')
def cart():
    if 'cart' not in session or not session['cart']:
        return render_template('cart.html', cart_items=[], total_price=0, cart_count=0)

    if isinstance(session['cart'], list):
        new_cart = {}
        for product_id in session['cart']:
            new_cart[str(product_id)] = new_cart.get(str(product_id), 0) + 1
        session['cart'] = new_cart
        session.modified = True

    product_ids = list(session['cart'].keys())
    products = Product.query.filter(Product.id.in_(product_ids)).all()

    cart_items = []
    total_price = 0
    for product in products:
        quantity = session['cart'][str(product.id)]
        subtotal = product.price * quantity
        cart_items.append((product, quantity, subtotal))
        total_price += subtotal

    cart_count = sum(session['cart'].values())
    return render_template('cart.html', cart_items=cart_items, total_price=total_price, cart_count=cart_count)


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'cart' not in session or not session['cart']:
        return redirect(url_for('cart'))

    if isinstance(session['cart'], list):
        new_cart = {}
        for product_id in session['cart']:
            new_cart[str(product_id)] = new_cart.get(str(product_id), 0) + 1
        session['cart'] = new_cart
        session.modified = True

    if request.method == 'POST':
        recipient_name = request.form['recipient_name']
        phone = request.form['phone']
        delivery_address = request.form['delivery_address']
        comment = request.form.get('comment', '')

        product_ids = list(session['cart'].keys())
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        total_price = sum(product.price * session['cart'][str(product.id)] for product in products)
        order_items = ','.join(f"{pid}:{qty}" for pid, qty in session['cart'].items())

        new_order = Order(
            recipient_name=recipient_name,
            phone=phone,
            order_items=order_items,
            total_price=total_price,
            delivery_address=delivery_address,
            comment=comment
        )
        db.session.add(new_order)
        db.session.commit()

        session['cart'] = {}
        session.modified = True
        return redirect(url_for('index'))

    cart_count = sum(session['cart'].values())
    return render_template('checkout.html', cart_count=cart_count)


@app.route('/contacts')
def contacts():
    cart_count = sum(session['cart'].values()) if 'cart' in session and isinstance(session['cart'], dict) else 0
    return render_template('contacts.html', cart_count=cart_count)


@app.route('/promotions')
def promotions():
    cart_count = sum(session['cart'].values()) if 'cart' in session and isinstance(session['cart'], dict) else 0
    return render_template('promotions.html', cart_count=cart_count)


@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        name = request.form['name']
        review = request.form['review']
        date = request.form['date']
        new_review = Review(name=name, review=review, date=date)
        db.session.add(new_review)
        db.session.commit()

    reviews = Review.query.all()
    cart_count = sum(session['cart'].values()) if 'cart' in session and isinstance(session['cart'], dict) else 0
    return render_template('reviews.html', reviews=reviews, cart_count=cart_count)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect('/admin/')
        flash('Неверный логин или пароль')

    cart_count = sum(session['cart'].values()) if 'cart' in session and isinstance(session['cart'], dict) else 0
    return render_template('login.html', cart_count=cart_count)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_redirect():
    return redirect('/admin/')


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)