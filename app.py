from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from textblob import TextBlob
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///brandmonitoring.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directories exist
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'logos'), exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_brand = db.Column(db.Boolean, default=False)
    brand_name = db.Column(db.String(100))
    logo_filename = db.Column(db.String(255))
    stores = db.Column(db.Integer, default=0)
    brand_reviews = db.relationship('BrandReview', backref='brand', foreign_keys='BrandReview.brand_id')
    reviews_given = db.relationship('BrandReview', backref='user', foreign_keys='BrandReview.user_id')

class BrandReview(db.Model):
    __tablename__ = 'brand_review'
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sentiment = db.Column(db.String(10))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    brands = User.query.filter_by(is_brand=True).all()
    return render_template('home.html', brands=brands)

@app.route('/brand/<int:brand_id>')
def brand_detail(brand_id):
    try:
        print(f"Accessing brand detail for ID: {brand_id}")  # Debug print
        brand = User.query.get_or_404(brand_id)
        
        if not brand:
            print(f"Brand not found with ID: {brand_id}")  # Debug print
            flash('Brand not found', 'error')
            return redirect(url_for('home'))
            
        if not brand.is_brand:
            print(f"Invalid brand (not a brand account) ID: {brand_id}")  # Debug print
            flash('Invalid brand', 'error')
            return redirect(url_for('home'))
        
        # Get reviews and calculate metrics
        reviews = BrandReview.query.filter_by(brand_id=brand_id).order_by(BrandReview.created_at.desc()).all()
        print(f"Found {len(reviews)} reviews for brand")  # Debug print
        
        # Calculate total reviews and average rating
        total_reviews = len(reviews)
        avg_rating = sum(review.rating for review in reviews) / total_reviews if total_reviews > 0 else 0
        
        # Calculate rating distribution
        rating_distribution = {
            1: len([r for r in reviews if r.rating == 1]),
            2: len([r for r in reviews if r.rating == 2]),
            3: len([r for r in reviews if r.rating == 3]),
            4: len([r for r in reviews if r.rating == 4]),
            5: len([r for r in reviews if r.rating == 5])
        }
        
        # Get the brand's website URL
        brand_url = {
            'adidas': 'adidas.com',
            'puma': 'puma.com',
            'crocs': 'crocs.com',
            'trends': 'trends.com',
            'max': 'maxfashion.com',
            'zara': 'zara.com',
            'boat': 'boat-lifestyle.com',
            'apple': 'apple.com',
            'lifestyle': 'lifestylestores.com'
        }.get(brand.username.lower(), f"{brand.username.lower()}.com")
        
        print(f"Rendering template with brand: {brand.brand_name}")  # Debug print
        return render_template(
            'brand_detail.html',
            brand=brand,
            reviews=reviews,
            brand_url=brand_url,
            total_reviews=total_reviews,
            avg_rating=avg_rating,
            rating_distribution=rating_distribution
        )
    except Exception as e:
        print(f"Error in brand_detail route: {str(e)}")  # Debug print
        app.logger.error(f"Error in brand_detail route: {str(e)}")
        flash('An error occurred while loading the brand details', 'error')
        return redirect(url_for('home'))

@app.route('/add_review/<int:brand_id>', methods=['POST'])
@login_required
def add_review(brand_id):
    brand = User.query.get_or_404(brand_id)
    if not brand.is_brand:
        flash('Invalid brand')
        return redirect(url_for('home'))

    comment = request.form.get('comment')
    review = BrandReview(
        rating=int(request.form.get('rating')),
        comment=comment,
        user_id=current_user.id,
        brand_id=brand_id,
        sentiment=analyze_sentiment(comment)
    )
    db.session.add(review)
    db.session.commit()
    flash('Review added successfully!')
    return redirect(url_for('brand_detail', brand_id=brand_id))

@app.route('/brand_dashboard')
@login_required
def brand_dashboard():
    if not current_user.is_brand:
        flash('Access denied')
        return redirect(url_for('home'))
    reviews = BrandReview.query.filter_by(brand_id=current_user.id).order_by(BrandReview.created_at.desc()).all()
    return render_template('brand_dashboard.html', reviews=reviews)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_brand = request.form.get('is_brand') == 'on'
        brand_name = request.form.get('brand_name') if is_brand else None
        logo = request.files.get('logo') if is_brand else None

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        # Handle logo upload for brands
        logo_filename = None
        if logo and is_brand:
            if logo.filename:
                filename = secure_filename(logo.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                logo_filename = f"{timestamp}_{filename}"
                logo.save(os.path.join(app.config['UPLOAD_FOLDER'], 'logos', logo_filename))

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_brand=is_brand,
            brand_name=brand_name,
            logo_filename=logo_filename
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/update_brand_logo', methods=['POST'])
@login_required
def update_brand_logo():
    if not current_user.is_brand:
        flash('Only brands can update their logo')
        return redirect(url_for('home'))

    if 'logo' not in request.files:
        flash('No logo file uploaded')
        return redirect(url_for('brand_dashboard'))

    logo = request.files['logo']
    if logo.filename == '':
        flash('No logo file selected')
        return redirect(url_for('brand_dashboard'))

    if logo and allowed_file(logo.filename):
        # Delete old logo if exists
        if current_user.logo_filename:
            old_logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'logos', current_user.logo_filename)
            if os.path.exists(old_logo_path):
                os.remove(old_logo_path)

        # Save new logo
        filename = secure_filename(logo.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        logo_filename = f"{timestamp}_{filename}"
        logo.save(os.path.join(app.config['UPLOAD_FOLDER'], 'logos', logo_filename))
        
        current_user.logo_filename = logo_filename
        db.session.commit()
        flash('Logo updated successfully!')
    else:
        flash('Invalid file type. Please upload a PNG, JPG, or JPEG file.')

    return redirect(url_for('brand_dashboard'))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_sentiment(text):
    analysis = TextBlob(text)
    # Get polarity score (-1 to 1)
    polarity = analysis.sentiment.polarity
    
    # Convert to sentiment category
    if polarity > 0.3:
        return 'Positive'
    elif polarity < -0.3:
        return 'Negative'
    else:
        return 'Neutral'

def populate_default_brands():
    # Default brands data
    default_brands = [
        {
            'username': 'adidas',
            'email': 'adidas@example.com',
            'password': 'password123',
            'brand_name': 'Adidas',
            'logo_filename': 'adidas-trefoil-logo-design.webp',
            'stores': 150
        },
        {
            'username': 'puma',
            'email': 'puma@example.com',
            'password': 'password123',
            'brand_name': 'Puma',
            'logo_filename': '360_F_202177215_ImnfbtEengMzSOzGISGZKvjt9gGFiynq.webp',
            'stores': 120
        },
        {
            'username': 'crocs',
            'email': 'crocs@example.com',
            'password': 'password123',
            'brand_name': 'Crocs',
            'logo_filename': 'crocs.webp',
            'stores': 80
        },
        {
            'username': 'trends',
            'email': 'trends@example.com',
            'password': 'password123',
            'brand_name': 'Trends',
            'logo_filename': '280.webp',
            'stores': 200
        },
        {
            'username': 'max',
            'email': 'max@example.com',
            'password': 'password123',
            'brand_name': 'Max',
            'logo_filename': '388ad7154062515e9148ef2fbbb31ba9daeafc6c-1096x619.webp',
            'stores': 175
        },
        {
            'username': 'zara',
            'email': 'zara@example.com',
            'password': 'password123',
            'brand_name': 'Zara',
            'logo_filename': '8d8UvSPK2Ue9qRzDG7JJ5F-1000-80.webp',
            'stores': 250
        },
        {
            'username': 'boat',
            'email': 'boat@example.com',
            'password': 'password123',
            'brand_name': 'Boat',
            'logo_filename': 'logaster-2020-08-t-boat-logo-6.webp',
            'stores': 50
        },
        {
            'username': 'apple',
            'email': 'apple@example.com',
            'password': 'password123',
            'brand_name': 'Apple',
            'logo_filename': 'Apple_logo_grey-624x400.webp',
            'stores': 100
        },
        {
            'username': 'lifestyle',
            'email': 'lifestyle@example.com',
            'password': 'password123',
            'brand_name': 'Lifestyle',
            'logo_filename': 'Lifestyle_Stores_-_New.webp',
            'stores': 90
        }
    ]

    # Add brands if they don't exist
    for brand_data in default_brands:
        if not User.query.filter_by(username=brand_data['username']).first():
            brand = User(
                username=brand_data['username'],
                email=brand_data['email'],
                password_hash=generate_password_hash(brand_data['password']),
                is_brand=True,
                brand_name=brand_data['brand_name'],
                logo_filename=brand_data['logo_filename'],
                stores=brand_data['stores']
            )
            db.session.add(brand)
    
    try:
        db.session.commit()
        print("Default brands populated successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error populating default brands: {str(e)}")

def populate_sample_reviews():
    # Sample users for reviews
    sample_users = [
        {'username': 'john_doe', 'email': 'john@example.com'},
        {'username': 'jane_smith', 'email': 'jane@example.com'},
        {'username': 'mike_wilson', 'email': 'mike@example.com'},
        {'username': 'sarah_brown', 'email': 'sarah@example.com'},
        {'username': 'alex_jones', 'email': 'alex@example.com'}
    ]

    # Sample review templates
    positive_reviews = [
        "Excellent brand! The quality is outstanding and customer service is top-notch.",
        "Really impressed with their products. Will definitely buy again!",
        "One of the best brands I've ever used. Highly recommended!",
        "Great experience with this brand. Their products are reliable and stylish.",
        "Amazing quality and value for money. Love their products!"
    ]

    neutral_reviews = [
        "Decent brand with average products. Nothing special but gets the job done.",
        "Products are okay, could be better but not bad.",
        "Average experience, met basic expectations.",
        "Fair quality for the price. Might consider buying again.",
        "Reasonable products but room for improvement."
    ]

    negative_reviews = [
        "Disappointed with the quality. Expected better from this brand.",
        "Customer service needs improvement. Products are mediocre.",
        "Not worth the price. Will think twice before buying again.",
        "Had issues with their products. Needs better quality control.",
        "Below average experience. Would not recommend."
    ]

    # Create sample users if they don't exist
    for user_data in sample_users:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=generate_password_hash('password123'),
                is_brand=False
            )
            db.session.add(user)
    
    try:
        db.session.commit()
        print("Sample users created successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sample users: {str(e)}")
        return

    # Get all brands and users
    brands = User.query.filter_by(is_brand=True).all()
    users = User.query.filter_by(is_brand=False).all()

    # Add reviews for each brand
    for brand in brands:
        # Clear existing reviews
        BrandReview.query.filter_by(brand_id=brand.id).delete()
        
        # Add 5-10 random reviews per brand
        num_reviews = random.randint(5, 10)
        for _ in range(num_reviews):
            # Random user
            user = random.choice(users)
            
            # Random rating (weighted towards positive)
            rating = random.choices([5,4,3,2,1], weights=[0.4,0.3,0.15,0.1,0.05])[0]
            
            # Select review text based on rating
            if rating >= 4:
                comment = random.choice(positive_reviews)
            elif rating <= 2:
                comment = random.choice(negative_reviews)
            else:
                comment = random.choice(neutral_reviews)

            # Random date within last 30 days
            days_ago = random.randint(0, 30)
            review_date = datetime.utcnow() - timedelta(days=days_ago)

            review = BrandReview(
                rating=rating,
                comment=comment,
                user_id=user.id,
                brand_id=brand.id,
                created_at=review_date,
                sentiment=analyze_sentiment(comment)
            )
            db.session.add(review)

    try:
        db.session.commit()
        print("Sample reviews added successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error adding sample data: {str(e)}")

@app.route('/analytics')
def analytics():
    brands = User.query.filter_by(is_brand=True).all()
    return render_template('analytics.html', brands=brands)

if __name__ == '__main__':
    with app.app_context():
        # Drop all tables and recreate
        db.drop_all()
        db.create_all()
        
        # Check if tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print("Created tables:", tables)
        
        # Populate default brands
        populate_default_brands()
        
        # Populate sample reviews
        populate_sample_reviews()
        
    app.run(debug=True,host='0.0.0.0',port=5000) 